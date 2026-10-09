from __future__ import annotations
from dataclasses import dataclass
from math import hypot,atan2,degrees,radians,cos,sin
from typing import Optional,Tuple,Dict,Any,Sequence
from .model import Document,Entity
from .commands import CommandStack,AddEntity,UpdateEntity,MoveEntities,RotateEntities
from .snapping import best_snap

@dataclass
class HUD:
    values: Dict[str,float]

class MoveTransaction:
    """Translate one or more entities via pointer/gizmo interaction."""
    def __init__(self, doc: Document, stack: CommandStack, entity_ids: Sequence[str], origin: Optional[Tuple[float, float, float]] = None, grid: float = 0.1, snap_tol: float = 0.10):
        self.doc, self.stack = doc, stack
        self.ids = [str(eid) for eid in entity_ids]
        missing = [eid for eid in self.ids if eid not in doc.entities]
        if missing:
            raise KeyError(f"Entities not found: {missing}")
        # What sits on a moved piece (hob, hood, its water point) moves with it.
        from archforge.assistant.room_layout import followers
        from archforge.core.object_ops import group_ids
        self.ids = list(dict.fromkeys(g for eid in self.ids for g in group_ids(doc, eid)))
        self.ids += followers(doc, self.ids)
        self.origin = origin if origin is not None else (0.0, 0.0, 0.0)
        self.grid = grid
        self.snap_tol = snap_tol
        self.dx = 0.0
        self.dy = 0.0
        self.dz = 0.0
        self.cancelled = False
        self.last_snap_kind = None
        self.axis_lock = None
        self.before = {eid: doc.get(eid).params.copy() for eid in self.ids}
        self.preview = {eid: doc.get(eid).params.copy() for eid in self.ids}

    def update_delta(self, dx: float, dy: float, dz: float = 0.0) -> HUD:
        self.dx = float(dx)
        self.dy = float(dy)
        self.dz = float(dz)
        self._compute_preview()
        return HUD({'dx': self.dx, 'dy': self.dy, 'dz': self.dz})

    def update_pointer(
        self,
        x: float,
        y: float,
        z: Optional[float] = None,
        snap: bool = True,
        axis_lock: bool = False,
    ) -> HUD:
        px, py = float(x), float(y)
        ox, oy = float(self.origin[0]), float(self.origin[1])
        self.last_snap_kind = None
        self.axis_lock = None

        if axis_lock:
            raw_dx, raw_dy = px - ox, py - oy
            if abs(raw_dx) >= abs(raw_dy):
                py = oy
                self.axis_lock = 'x'
            else:
                px = ox
                self.axis_lock = 'y'

        proposed_dx, proposed_dy = px - ox, py - oy

        if snap:
            # Object-aware snapping: stairs/ramps touch physical wall faces,
            # while whole walls snap their own endpoint/midpoint geometry to
            # semantic points/centerlines of other walls.
            from .snapping import (
                snap_polygon_translation_to_wall_faces,
                snap_translation_points,
            )
            object_snap = None
            for eid in self.ids:
                entity = self.doc.get(eid)
                try:
                    if entity.kind == 'stair':
                        from archforge.architecture.stairs import candidate_from_params, stair_footprint
                        polygon = stair_footprint(candidate_from_params(self.before[eid]))
                        candidate_snap = snap_polygon_translation_to_wall_faces(
                            self.doc,
                            polygon,
                            proposed_dx,
                            proposed_dy,
                            min(self.snap_tol, 0.06),
                            exclude=set(self.ids),
                        )
                    elif entity.kind == 'ramp':
                        from archforge.architecture.ramps import candidate_from_params, ramp_footprint
                        polygon = ramp_footprint(candidate_from_params(self.before[eid]))
                        candidate_snap = snap_polygon_translation_to_wall_faces(
                            self.doc,
                            polygon,
                            proposed_dx,
                            proposed_dy,
                            min(self.snap_tol, 0.06),
                            exclude=set(self.ids),
                        )
                    elif entity.kind in ('cabinet', 'library_object'):
                        # Cabinets and fixtures click onto the wall behind them and onto the neighbour.
                        from archforge.assistant.fixture_snap import snap_correction
                        moved = dict(self.before[eid], x=float(self.before[eid]['x']) + proposed_dx,
                                     y=float(self.before[eid]['y']) + proposed_dy)
                        found = snap_correction(self.doc, eid, moved, ignore=set(self.ids))
                        candidate_snap = None if found is None else {
                            'correction': found[:2], 'kind': found[2], 'distance': -1.0}
                    elif entity.kind == 'wall':
                        p = self.before[eid]
                        probes = (
                            (float(p['x1']), float(p['y1'])),
                            (float(p['x2']), float(p['y2'])),
                            (
                                (float(p['x1']) + float(p['x2'])) / 2.0,
                                (float(p['y1']) + float(p['y2'])) / 2.0,
                            ),
                        )
                        candidate_snap = snap_translation_points(
                            self.doc,
                            probes,
                            proposed_dx,
                            proposed_dy,
                            min(self.snap_tol, 0.08),
                            exclude=set(self.ids),
                        )
                    else:
                        continue
                    if candidate_snap is None:
                        continue
                    cx, cy = candidate_snap['correction']
                    if self.axis_lock == 'x' and abs(cy) > 1e-8:
                        continue
                    if self.axis_lock == 'y' and abs(cx) > 1e-8:
                        continue
                    if object_snap is None or candidate_snap['distance'] < object_snap['distance']:
                        object_snap = candidate_snap
                except (KeyError, ValueError):
                    continue

            if object_snap is not None:
                cx, cy = object_snap['correction']
                proposed_dx += cx
                proposed_dy += cy
                px, py = ox + proposed_dx, oy + proposed_dy
                self.last_snap_kind = object_snap['kind']
            else:
                sp = best_snap(
                    self.doc,
                    px,
                    py,
                    self.snap_tol,
                    self.grid,
                    exclude=set(self.ids),
                )
                if sp:
                    if self.axis_lock == 'x':
                        px = sp.x
                        py = oy
                    elif self.axis_lock == 'y':
                        px = ox
                        py = sp.y
                    else:
                        px, py = sp.x, sp.y
                    self.last_snap_kind = sp.kind

        self.dx = px - ox
        self.dy = py - oy
        self.dz = (z - self.origin[2]) if z is not None else 0.0
        self._compute_preview()
        return HUD({
            'dx': self.dx,
            'dy': self.dy,
            'dz': self.dz,
            'x': px,
            'y': py,
            'snap': 1.0 if self.last_snap_kind else 0.0,
            'axis_locked': 1.0 if self.axis_lock else 0.0,
        })

    def _compute_preview(self):
        self.preview = {}
        for eid in self.ids:
            p = self.before[eid].copy()
            e = self.doc.get(eid)
            if e.kind in ('box', 'mechanical_part', 'cabinet', 'library_object', 'plumbing_point', 'ventilation_point'):
                p['x'] = p['x'] + self.dx
                p['y'] = p['y'] + self.dy
                p['z'] = p['z'] + self.dz
            elif e.kind == 'structural_column':
                p['x'] = p['x'] + self.dx
                p['y'] = p['y'] + self.dy
            elif e.kind == 'mep_terminal':
                p['x'] = p['x'] + self.dx
                p['y'] = p['y'] + self.dy
                p['elevation'] = p['elevation'] + self.dz
            elif e.kind == 'wall':
                p['x1'] = p['x1'] + self.dx
                p['x2'] = p['x2'] + self.dx
                p['y1'] = p['y1'] + self.dy
                p['y2'] = p['y2'] + self.dy
                p['z'] = p['z'] + self.dz
            elif e.kind == 'structural_beam':
                p['x1'] = p['x1'] + self.dx
                p['x2'] = p['x2'] + self.dx
                p['y1'] = p['y1'] + self.dy
                p['y2'] = p['y2'] + self.dy
            elif e.kind == 'pod':
                p['cx'] = p['cx'] + self.dx
                p['cy'] = p['cy'] + self.dy
                p['floor_level'] = p['floor_level'] + self.dz
            elif e.kind == 'slab_opening' and p.get('points'):
                p['points'] = [(qx + self.dx, qy + self.dy) for qx, qy in p['points']]
            elif e.kind in ('floor', 'room'):
                p['points'] = [(qx + self.dx, qy + self.dy) for qx, qy in p['points']]
                p['z'] = p['z'] + self.dz
            elif e.kind in ('stair', 'ramp'):
                p['x'] = p['x'] + self.dx
                p['y'] = p['y'] + self.dy
                # Vertical-circulation objects remain tied to floor elevations.
                # XY movement must not silently detach them vertically.
            self.preview[eid] = p

    def commit(self):
        if self.cancelled:
            raise RuntimeError('transaction cancelled')
        self.stack.execute(MoveEntities(self.ids, dx=self.dx, dy=self.dy, dz=self.dz))

    def cancel(self):
        self.cancelled = True
        self.preview = {eid: self.before[eid].copy() for eid in self.ids}


# Wall angle "magnets": 90° / 45° / 15° pull lightly (within these degrees) from the previous wall and the
# axes; any other angle stays free in whole degrees — no angle menu needed.
MAGNET='magnet'
MAGNET_STEPS=((90.0,4.0),(45.0,3.0),(15.0,1.5))


class WallDrawTransaction:
    def __init__(
        self,
        doc:Document,
        stack:CommandStack,
        start:Tuple[float,float],
        z=0.0,
        height=2.7,
        thickness=0.15,
        grid=0.1,
        snap_tol=0.15,
        snap_enabled=True,
        angle_increment=90.0,
        reference_angle_deg=0.0,
        angle_enabled=True,
        min_length=0.05,
    ):
        self.doc,self.stack=doc,stack
        self.start=(float(start[0]),float(start[1]))
        self.end=self.start
        self.z=z;self.height=height;self.thickness=thickness
        self.grid=grid;self.snap_tol=snap_tol
        self.snap_enabled=bool(snap_enabled)
        self.angle_increment=(None if angle_increment is None else (MAGNET if angle_increment==MAGNET else float(angle_increment)))
        self.reference_angle_deg=float(reference_angle_deg)
        self.angle_enabled=bool(angle_enabled)
        self.min_length=max(0.0,float(min_length))
        self.last_snap=None
        self.angle_snapped=False
        self.cancelled=False

    # A wall end near a corner closes onto it: corners pull from this far (m), not only from the snap tolerance.
    CORNER_CAPTURE=0.30

    def _corner_near(self,x,y):
        """Nearest wall end / corner of the active storey within the corner capture radius (not the start)."""
        from .snapping import SnapPoint
        radius=max(float(self.snap_tol),self.CORNER_CAPTURE);best=None
        for eid,e in self.doc.entities.items():
            if e.kind!='wall' or not e.visible or abs(float(e.params.get('z',0.0))-float(self.z))>1e-5:continue
            p=e.params
            for px,py in ((float(p['x1']),float(p['y1'])),(float(p['x2']),float(p['y2']))):
                if hypot(px-self.start[0],py-self.start[1])<=max(self.min_length,1e-6):continue
                d=hypot(px-x,py-y)
                if d<=radius and (best is None or d<best[0]):best=(d,SnapPoint(px,py,float(self.z),'endpoint',eid))
        return best[1] if best else None

    def _ray_hits_wall(self,ux,uy,x,y):
        """Where the constrained direction meets the axis of a wall the pointer is on (keeps the angle)."""
        from .snapping import SnapPoint
        sx,sy=self.start;best=None
        for eid,e in self.doc.entities.items():
            if e.kind!='wall' or not e.visible or abs(float(e.params.get('z',0.0))-float(self.z))>1e-5:continue
            p=e.params;ax,ay,bx,by=(float(p[k]) for k in ('x1','y1','x2','y2'))
            wx,wy=bx-ax,by-ay;L=hypot(wx,wy)
            if L<1e-9:continue
            # The pointer must be on (or right next to) that wall.
            t=max(0.0,min(1.0,((x-ax)*wx+(y-ay)*wy)/(L*L)))
            if hypot(ax+wx*t-x,ay+wy*t-y)>float(p.get('thickness',0.2))/2+float(self.snap_tol):continue
            den=ux*wy-uy*wx
            if abs(den)<1e-9:continue                      # parallel: no crossing
            r=((ax-sx)*wy-(ay-sy)*wx)/den                  # along the ray
            q=((ax-sx)*uy-(ay-sy)*ux)/den                  # along the wall
            if r<=self.min_length or q<-1e-6 or q>L+1e-6:continue
            hit=(sx+ux*r,sy+uy*r)
            d=hypot(hit[0]-x,hit[1]-y)
            if best is None or d<best[0]:best=(d,SnapPoint(hit[0],hit[1],float(self.z),'wall_on_axis',eid))
        return best[1] if best else None

    def previous_direction(self):
        """Direction (deg) from the start along the wall that ends there, or None (the corner's other side)."""
        if not hasattr(self,'_previous_direction'):
            self._previous_direction=None;best=1e-4
            for e in self.doc.entities.values():
                if e.kind!='wall' or abs(float(e.params.get('z',0.0))-float(self.z))>1e-5:continue
                p=e.params;a=(float(p['x1']),float(p['y1']));b=(float(p['x2']),float(p['y2']))
                for here,there in ((a,b),(b,a)):
                    d=hypot(here[0]-self.start[0],here[1]-self.start[1])
                    if d<=best and hypot(there[0]-here[0],there[1]-here[1])>1e-9:
                        best=d;self._previous_direction=degrees(atan2(there[1]-here[1],there[0]-here[0]))
        return self._previous_direction

    def _direction(self,x,y):
        """(angle deg, magnet step or 0) of the wall towards the pointer."""
        sx,sy=self.start
        raw=degrees(atan2(y-sy,x-sx))
        if self.angle_increment==MAGNET:
            bases=[b for b in (self.previous_direction(),self.reference_angle_deg,0.0) if b is not None]
            for step,tol in MAGNET_STEPS:
                for base in bases:
                    near=base+round((raw-base)/step)*step
                    if abs(raw-near)<=tol:
                        return near,step
            return float(round(raw)),0.0                       # free, in whole degrees
        rel=raw-self.reference_angle_deg
        return self.reference_angle_deg+round(rel/self.angle_increment)*self.angle_increment,float(self.angle_increment)

    def update(self,x,y):
        x=float(x);y=float(y)
        self.last_snap=None
        self.angle_snapped=False
        self.magnet=0.0
        sx,sy=self.start
        constrained=(self.angle_enabled and self.angle_increment is not None
                     and (self.angle_increment==MAGNET or self.angle_increment>0))

        # 1. Corners close the outline: a wall end near another wall's end lands exactly on it (autosnap).
        corner=self._corner_near(x,y) if self.snap_enabled else None
        if corner is not None:
            self.end=(corner.x,corner.y);self.last_snap=corner
        elif constrained and hypot(x-sx,y-sy)>1e-12:
            # 2. The angle (90° / 45° / 15°) is kept: snaps may set where the wall stops, never its direction.
            deg,self.magnet=self._direction(x,y)
            a=radians(deg)
            ux,uy=cos(a),sin(a)
            length=hypot(x-sx,y-sy)
            self.end=(sx+ux*length,sy+uy*length);self.angle_snapped=True
            hit=self._ray_hits_wall(ux,uy,x,y) if self.snap_enabled else None
            if hit is not None:
                # Reaching another wall: stop on its axis, along the same direction.
                self.end=(hit.x,hit.y);self.last_snap=hit
            elif self.snap_enabled:
                sp=best_snap(self.doc,self.end[0],self.end[1],self.snap_tol,grid=None)
                if sp is not None:
                    # A point next to the ray (alignment with a corner/midpoint): its projection on the ray.
                    k=max(0.0,(sp.x-sx)*ux+(sp.y-sy)*uy)
                    if hypot(sx+ux*k-sp.x,sy+uy*k-sp.y)<=self.snap_tol and k>self.min_length:
                        self.end=(sx+ux*k,sy+uy*k);self.last_snap=sp
        else:
            sp=best_snap(self.doc,x,y,self.snap_tol,grid=None) if self.snap_enabled else None
            if sp is not None:
                self.end=(sp.x,sp.y);self.last_snap=sp
            elif self.snap_enabled and self.grid:
                self.end=(round(x/self.grid)*self.grid,round(y/self.grid)*self.grid)
            else:
                self.end=(x,y)

        dx=self.end[0]-self.start[0];dy=self.end[1]-self.start[1]
        values={
            'length':hypot(dx,dy),
            'angle_deg':degrees(atan2(dy,dx)),
            'x':self.end[0],
            'y':self.end[1],
            'z':self.z,
            'angle_locked':1.0 if self.angle_snapped else 0.0,
            'magnet':float(getattr(self,'magnet',0.0)),
        }
        # The corner mark: the angle between the wall that ends here and the new one (0–180°).
        prev=self.previous_direction()
        if prev is not None and hypot(dx,dy)>1e-9:
            corner=abs((values['angle_deg']-prev+180.0)%360.0-180.0)
            values['corner_deg']=corner;values['previous_deg']=prev
        return HUD(values)
    def commit(self,exact_length:Optional[float]=None)->str:
        if self.cancelled:raise RuntimeError('transaction cancelled')
        sx,sy=self.start;ex,ey=self.end;dx,dy=ex-sx,ey-sy;L=hypot(dx,dy)
        if exact_length is not None:
            if exact_length<=0:raise ValueError('length must be > 0')
            if L==0:raise ValueError('cannot set exact length for zero direction')
            ex=sx+dx/L*exact_length;ey=sy+dy/L*exact_length;L=exact_length
        if L < self.min_length:
            raise ValueError(
                f'Ο τοίχος είναι πολύ κοντός ({L*100:.1f} cm)· τράβηξε ή κάνε κλικ τουλάχιστον {self.min_length*100:.0f} cm πιο πέρα'
            )
        params={'x1':sx,'y1':sy,'x2':ex,'y2':ey,'z':self.z,'height':self.height,'thickness':self.thickness}
        if getattr(self,'wall_type',None):params['wall_type']=self.wall_type
        if getattr(self,'reference',None) in ('exterior','interior'):params['reference']=self.reference
        e=Entity('wall',params,name='Wall')
        self.stack.execute(AddEntity(e));return e.id
    def cancel(self):self.cancelled=True

def _terrain_start_z(doc,origin,storey_z):
    from archforge.site.terrain import terrain_height_at
    from archforge.architecture.topology import room_faces
    lowest=min([float(v) for v in doc.levels.values()]+[0.0])
    if storey_z>lowest+1e-6:return None
    ground=terrain_height_at(doc,origin[0],origin[1])
    if ground is None:return None
    def inside(poly):
        x,y=origin;hit=False;n=len(poly)
        for i in range(n):
            (x1,y1),(x2,y2)=poly[i],poly[(i+1)%n]
            if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:hit=not hit
        return hit
    try:faces=doc.active_room_faces()
    except Exception:faces=[]
    if any(inside(f.polygon) for f in faces):return None
    return ground


class StairPlaceTransaction:
    """Live adaptive stair placement between the active level and the next level above."""
    def __init__(
        self,
        doc: Document,
        stack: CommandStack,
        origin: Tuple[float, float],
        *,
        width: float = 1.0,
        preferred_riser: float = 0.17,
        preferred_tread: float = 0.29,
        layout: Optional[str] = None,
    ):
        from archforge.architecture.stairs import upper_floor_landing
        self.doc,self.stack=doc,stack
        # Human-chosen stair type (straight/l/u/spiral); None = best fit.
        self.layout=str(layout) if layout else None
        self.origin=(float(origin[0]),float(origin[1]))
        self.width=float(width)
        self.preferred_riser=float(preferred_riser)
        self.preferred_tread=float(preferred_tread)
        self.lower_z=float(doc.work_plane.origin[2])
        landing=upper_floor_landing(doc,self.lower_z,self.origin)
        if landing is None:
            raise ValueError('Create an upper floor level before placing stairs')
        self.upper_floor_z=float(landing['floor_z'])
        self.upper_slab_thickness=float(landing['slab_thickness'])
        self.upper_z=float(landing['landing_z'])
        self.upper_level_name=str(landing['level_name'])
        # An external stair (outside every room) starts on the site terrain.
        ground=_terrain_start_z(doc,self.origin,self.lower_z)
        if ground is not None and ground<self.upper_z:self.lower_z=ground
        self.pointer=self.origin
        self.candidates=()
        self.active_index=0
        self.preview={}
        self.cancelled=False
        self.update(*self.origin)

    def update(self,x,y):
        from archforge.architecture.stairs import solve_stair_candidates,stair_footprint
        self.pointer=(float(x),float(y))
        self.candidates=solve_stair_candidates(
            self.lower_z,self.upper_z,self.origin,self.pointer,
            width=self.width,
            preferred_riser=self.preferred_riser,
            preferred_tread=self.preferred_tread,
            upper_floor_z=self.upper_floor_z,
            upper_slab_thickness=self.upper_slab_thickness,
        )
        if not self.candidates:
            raise ValueError('no stair solution available')
        # The four offered options are the best candidate of each distinct
        # layout, so straight, L, U and spiral are all reachable.
        firsts=[];rest=[];seen=set()
        for candidate in self.candidates:
            (rest if candidate.layout in seen else firsts).append(candidate);seen.add(candidate.layout)
        self.candidates=tuple(firsts+rest)
        if self.layout is not None:
            # Keep the chosen type while the pointer moves.
            chosen=next((i for i,c in enumerate(self.candidates[:4]) if c.layout==self.layout),None)
            if chosen is not None:self.active_index=chosen
        self.active_index=min(self.active_index,max(0,min(3,len(self.candidates)-1)))
        active=self.candidates[self.active_index]
        self.preview={
            'chosen':active.to_params(),
            'candidates':[candidate.to_params() for candidate in self.candidates[:4]],
            'active_index':self.active_index,
            'footprint':list(stair_footprint(active)),
            'upper_level_name':self.upper_level_name,
            'suggestions':list(active.suggestions),
        }
        return HUD({
            'risers':float(active.riser_count),
            'riser':active.riser_height,
            'tread':active.tread_depth,
            'width':active.width,
            'floor_height':active.floor_height,
            'option':float(self.active_index+1),
        })

    @property
    def active_candidate(self):
        if not self.candidates:
            raise ValueError('stair has no candidates')
        return self.candidates[self.active_index]

    def cycle_candidate(self, step=1):
        if not self.candidates:
            return self.preview
        count=min(4,len(self.candidates))
        self.active_index=(self.active_index+int(step))%count
        self.layout=self.candidates[self.active_index].layout
        return self.update(*self.pointer)

    def commit(self):
        if self.cancelled:
            raise RuntimeError('transaction cancelled')
        if not self.candidates:
            raise ValueError('stair has no valid preview')
        chosen=self.active_candidate
        entity=Entity('stair',chosen.to_params(),name='Stair')
        self.stack.execute(AddEntity(entity))
        self.doc.select([entity.id])
        return entity.id

    def cancel(self):
        self.cancelled=True
        self.candidates=()
        self.preview={}


class RampPlaceTransaction:
    """Live ramp placement with wheel-selectable slope alternatives."""
    def __init__(
        self,
        doc: Document,
        stack: CommandStack,
        origin: Tuple[float, float],
        *,
        width: float = 1.20,
        thickness: float = 0.15,
    ):
        self.doc,self.stack=doc,stack
        self.origin=(float(origin[0]),float(origin[1]))
        self.width=float(width)
        self.thickness=float(thickness)
        self.lower_z=float(doc.work_plane.origin[2])
        self.pointer=self.origin
        self.candidates=()
        self.active_index=0
        self.preview={}
        self.cancelled=False
        self.update(*self.origin)

    def update(self,x,y):
        from archforge.architecture.ramps import solve_ramp_candidates,ramp_footprint
        self.pointer=(float(x),float(y))
        self.candidates=solve_ramp_candidates(
            self.doc,self.lower_z,self.origin,self.pointer,
            width=self.width,
            thickness=self.thickness,
        )
        self.active_index=min(self.active_index,max(0,len(self.candidates)-1))
        active=self.candidates[self.active_index]
        self.preview={
            'chosen':active.to_params(),
            'candidates':[candidate.to_params() for candidate in self.candidates],
            'active_index':self.active_index,
            'footprint':list(ramp_footprint(active)),
        }
        return HUD({
            'slope_pct':active.slope_pct,
            'run_length':active.run_length,
            'rise':active.rise,
            'width':active.width,
            'option':float(self.active_index+1),
        })

    @property
    def active_candidate(self):
        if not self.candidates:
            raise ValueError('ramp has no candidates')
        return self.candidates[self.active_index]

    def cycle_candidate(self,step=1):
        if not self.candidates:return self.preview
        self.active_index=(self.active_index+int(step))%len(self.candidates)
        return self.update(*self.pointer)

    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        active=self.active_candidate
        entity=Entity('ramp',active.to_params(),name='Ramp')
        self.stack.execute(AddEntity(entity))
        self.doc.select([entity.id])
        return entity.id

    def cancel(self):
        self.cancelled=True
        self.candidates=()
        self.preview={}


class BoxStretchTransaction:
    def __init__(self,doc,stack,eid,handle):
        self.doc,self.stack,self.eid,self.handle=doc,stack,eid,handle;self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
    def update(self,x=None,y=None,z=None):
        p=self.before.copy();cx,cy=p['x'],p['y'];w,d,h=p['width'],p['depth'],p['height'];left,right=cx-w/2,cx+w/2;bottom,top=cy-d/2,cy+d/2
        if 'right' in self.handle and x is not None:right=x
        if 'left' in self.handle and x is not None:left=x
        if 'top' in self.handle and y is not None:top=y
        if 'bottom' in self.handle and y is not None:bottom=y
        if right<=left or top<=bottom:raise ValueError('stretch inverted object')
        p['x']=(left+right)/2;p['y']=(bottom+top)/2;p['width']=right-left;p['depth']=top-bottom
        if 'height' in self.handle and z is not None:
            if z<=p['z']:raise ValueError('height must remain above base')
            p['height']=z-p['z']
        self.preview=p;return HUD({'width':p['width'],'depth':p['depth'],'height':p['height'],'x':p['x'],'y':p['y'],'z':p['z']})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class RotateTransaction:
    def __init__(self,doc,stack,eid,pivot=None,angle_increment=15.0):
        self.doc,self.stack,self.eid=doc,stack,eid;self.before=doc.get(eid).params.copy();self.preview=self.before.copy();self.angle_increment=float(angle_increment) if angle_increment else None;self.angle=0.0;e=doc.get(eid);p=e.params
        if pivot is not None:self.pivot=pivot
        elif p.get('role')=='pergola':
            from archforge.core.object_ops import group_ids,pivot as group_pivot
            self.pivot=group_pivot(doc,group_ids(doc,eid))
        elif e.kind in ('box','structural_column'):self.pivot=(p['x'],p['y'])
        elif e.kind=='pod':self.pivot=(p['cx'],p['cy'])
        elif e.kind in ('wall','structural_beam'):self.pivot=((p['x1']+p['x2'])/2,(p['y1']+p['y2'])/2)
        elif e.kind=='stair':
            from archforge.architecture.stairs import candidate_from_params,stair_footprint
            poly=stair_footprint(candidate_from_params(p))
            self.pivot=((min(q[0] for q in poly)+max(q[0] for q in poly))/2,(min(q[1] for q in poly)+max(q[1] for q in poly))/2)
        elif e.kind=='ramp':
            from archforge.architecture.ramps import candidate_from_params,ramp_footprint
            poly=ramp_footprint(candidate_from_params(p))
            self.pivot=((min(q[0] for q in poly)+max(q[0] for q in poly))/2,(min(q[1] for q in poly)+max(q[1] for q in poly))/2)
        else:
            # Everything else the user places (object_ops): its centre; a pergola turns as one.
            from archforge.core.object_ops import ROTATABLE_KINDS,group_ids,pivot as group_pivot
            if e.kind not in ROTATABLE_KINDS:raise ValueError('rotation unsupported for entity kind')
            self.pivot=group_pivot(doc,group_ids(doc,eid))
    def update_angle(self,angle_deg,snap=True):
        a=float(angle_deg)
        if snap and self.angle_increment:a=round(a/self.angle_increment)*self.angle_increment
        self.angle=a
        from math import radians,cos,sin
        r=radians(a);c,s=cos(r),sin(r);px,py=self.pivot;p=self.before.copy();e=self.doc.get(self.eid)
        if e.kind in ('box','structural_column'):p['rotation']=(p.get('rotation',0.0)+a)%360.0
        elif e.kind in ('wall','structural_beam'):
            def rot(x,y):dx,dy=x-px,y-py;return px+dx*c-dy*s,py+dx*s+dy*c
            p['x1'],p['y1']=rot(p['x1'],p['y1']);p['x2'],p['y2']=rot(p['x2'],p['y2'])
        elif e.kind=='pod':p['rotation']=(p.get('rotation',0.0)+a)%360.0
        elif e.kind in ('stair','ramp'):
            dx,dy=float(p['x'])-px,float(p['y'])-py
            p['x']=px+dx*c-dy*s
            p['y']=py+dx*s+dy*c
            p['angle_deg']=(float(p.get('angle_deg',0.0))+a)%360.0
        elif e.kind=='railing':
            p['points']=[[px+(q[0]-px)*c-(q[1]-py)*s,py+(q[0]-px)*s+(q[1]-py)*c,*q[2:]] for q in p['points']]
        else:
            from archforge.core.object_ops import rotated_params
            p=rotated_params(e.kind,p,a,(px,py)) or p
        self.preview=p;return HUD({'angle_deg':a,'pivot_x':px,'pivot_y':py})
    def update_pointer(self,x,y,start_angle_deg=0.0,snap=True):return self.update_angle(degrees(atan2(y-self.pivot[1],x-self.pivot[0]))-float(start_angle_deg),snap)
    def commit(self):
        from archforge.core.object_ops import group_ids
        self.stack.execute(RotateEntities(group_ids(self.doc,self.eid),self.angle,pivot=self.pivot))
    def cancel(self):self.preview=self.before.copy()

class WallEndpointStretchTransaction:
    def __init__(self,doc,stack,eid,endpoint,grid=0.1,snap_tol=0.15):
        if endpoint not in (1,2):raise ValueError('endpoint must be 1 or 2')
        self.doc,self.stack,self.eid,self.endpoint=doc,stack,eid,endpoint;self.before=doc.get(eid).params.copy();self.preview=self.before.copy();self.grid=grid;self.snap_tol=snap_tol
    def update(self,x,y):
        sp=best_snap(self.doc,x,y,self.snap_tol,self.grid,{self.eid});x,y=(sp.x,sp.y) if sp else (x,y);p=self.before.copy();p[f'x{self.endpoint}']=x;p[f'y{self.endpoint}']=y;L=hypot(p['x2']-p['x1'],p['y2']-p['y1'])
        if L<=1e-9:raise ValueError('zero-length wall')
        self.preview=p;return HUD({'length':L,'angle_deg':degrees(atan2(p['y2']-p['y1'],p['x2']-p['x1'])),'x':x,'y':y,'z':p['z']})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class StructuralBeamEndpointStretchTransaction:
    """Stretch one beam endpoint while preserving its semantic section/elevation."""
    def __init__(self,doc,stack,eid,endpoint,grid=0.1,snap_tol=0.10,snap_enabled=True):
        if endpoint not in (1,2):raise ValueError('endpoint must be 1 or 2')
        if eid not in doc.entities or doc.get(eid).kind!='structural_beam':
            raise ValueError('beam endpoint stretch requires a structural_beam')
        self.doc,self.stack,self.eid,self.endpoint=doc,stack,eid,endpoint
        self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
        self.grid=grid;self.snap_tol=float(snap_tol);self.snap_enabled=bool(snap_enabled);self.last_snap=None

    def update(self,x,y):
        x,y=float(x),float(y);self.last_snap=None
        if self.snap_enabled:
            sp=best_snap(self.doc,x,y,self.snap_tol,self.grid,{self.eid})
            if sp is not None:
                x,y=float(sp.x),float(sp.y);self.last_snap=sp
        p=self.before.copy();p[f'x{self.endpoint}']=x;p[f'y{self.endpoint}']=y
        length=hypot(float(p['x2'])-float(p['x1']),float(p['y2'])-float(p['y1']))
        if length<0.05:raise ValueError('beam must remain at least 0.05 m long')
        self.preview=p
        return HUD({
            'length':length,
            'angle_deg':degrees(atan2(float(p['y2'])-float(p['y1']),float(p['x2'])-float(p['x1']))),
            'x':x,'y':y,'z':float(p['z']),
        })

    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()


class PodStretchTransaction:
    def __init__(self,doc,stack,eid,handle):
        if handle not in ('left','right','top','bottom','height'):raise ValueError('invalid pod handle')
        self.doc,self.stack,self.eid,self.handle=doc,stack,eid,handle;self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
    def update(self,x=None,y=None,z=None):
        p=self.before.copy();cx,cy=p['cx'],p['cy'];rx,ry=p['diameter_x']/2,p['diameter_y']/2;left,right=cx-rx,cx+rx;bottom,top=cy-ry,cy+ry
        if self.handle=='left' and x is not None:left=x
        elif self.handle=='right' and x is not None:right=x
        elif self.handle=='bottom' and y is not None:bottom=y
        elif self.handle=='top' and y is not None:top=y
        elif self.handle=='height' and z is not None:
            if z<=p['floor_level']:raise ValueError('pod top must remain above floor')
            p['height']=z-p['floor_level']
        if right<=left or top<=bottom:raise ValueError('stretch inverted pod')
        p['cx']=(left+right)/2;p['cy']=(bottom+top)/2;p['diameter_x']=right-left;p['diameter_y']=top-bottom;self.preview=p
        return HUD({'diameter_x':p['diameter_x'],'diameter_y':p['diameter_y'],'height':p['height'],'cx':p['cx'],'cy':p['cy'],'floor_level':p['floor_level']})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()

class VerticalStretchTransaction:
    def __init__(self,doc,stack,eid):
        self.doc,self.stack,self.eid=doc,stack,eid;self.before=doc.get(eid).params.copy();self.preview=self.before.copy()
        if doc.get(eid).kind not in ('wall','box','pod'):raise ValueError('vertical stretch unsupported for entity kind')
    def update(self,z):
        p=self.before.copy();e=self.doc.get(self.eid);z=float(z);base=p['z'] if e.kind in ('wall','box') else p['floor_level']
        if z<=base:raise ValueError('top must remain above base')
        p['height']=z-base;self.preview=p;return HUD({'height':p['height'],'base_z':base,'top_z':z})
    def commit(self):self.stack.execute(UpdateEntity(self.eid,self.preview))
    def cancel(self):self.preview=self.before.copy()


class StructuralColumnPlaceTransaction:
    """Place one semantic vertical Column/Post on the active storey."""
    def __init__(
        self,doc,stack,x,y,*,z,height,width=.25,depth=.25,rotation=0.0,
        role='structural',construction='reinforced_concrete',section='rectangular',
        base_level='Ground',top_level='Unassigned',grid=.10,snap_tol=.10,snap_enabled=True,
    ):
        self.doc,self.stack=doc,stack
        self.z=float(z);self.height=float(height);self.width=float(width);self.depth=float(depth)
        self.rotation=float(rotation);self.role=str(role);self.construction=str(construction);self.section=str(section)
        self.base_level=str(base_level);self.top_level=str(top_level)
        self.grid=grid;self.snap_tol=float(snap_tol);self.cancelled=False;self.last_snap=None
        self.snap_enabled=bool(snap_enabled);self._free_rotation=float(rotation)
        self.x=float(x);self.y=float(y);self.preview={}
        self.update(x,y)

    def update(self,x,y):
        # Snap ON: wall corners, slab corners, then a wall axis (aligned to the
        # wall), then the construction grid. Snap OFF / Shift: exactly here.
        from .snapping import COLUMN_SNAP_TOLERANCE,column_snap
        sp=None;rotation=None
        if self.snap_enabled:
            sp,rotation=column_snap(
                self.doc,float(x),float(y),max(self.snap_tol,COLUMN_SNAP_TOLERANCE),
                width=self.width,depth=self.depth,
            )
            if sp is None and self.grid:
                sp=best_snap(self.doc,float(x),float(y),self.snap_tol,self.grid)
        if sp is not None:
            self.x,self.y=float(sp.x),float(sp.y);self.last_snap=sp
        else:
            self.x,self.y=float(x),float(y);self.last_snap=None
        self.rotation=float(rotation)%360.0 if rotation is not None else self._free_rotation
        self.preview={
            'x':self.x,'y':self.y,'z':self.z,
            'width':self.width,'depth':self.depth,'height':self.height,
            'rotation':self.rotation,'role':self.role,'construction':self.construction,
            'section':self.section,'base_level':self.base_level,'top_level':self.top_level,
        }
        return HUD({'x':self.x,'y':self.y,'z':self.z,'height':self.height,'width':self.width,'depth':self.depth})

    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        e=Entity('structural_column',dict(self.preview),name='Column')
        self.stack.execute(AddEntity(e));return e.id

    def cancel(self):self.cancelled=True


class StructuralBeamDrawTransaction:
    """Draw one horizontal semantic Beam between two plan points."""
    def __init__(
        self,doc,stack,start,*,z,width=.20,height=.30,
        role='structural',construction='reinforced_concrete',section='rectangular',
        level='Ground',grid=.10,snap_tol=.10,angle_increment=15.0,
    ):
        self.doc,self.stack=doc,stack
        self.start=(float(start[0]),float(start[1]));self.end=self.start
        self.z=float(z);self.width=float(width);self.height=float(height)
        self.role=str(role);self.construction=str(construction);self.section=str(section);self.level=str(level)
        self.grid=grid;self.snap_tol=float(snap_tol)
        self.angle_increment=(None if angle_increment is None else float(angle_increment))
        self.cancelled=False;self.last_snap=None;self.angle_snapped=False
        self.preview={}
        self.update(*self.start)

    def update(self,x,y):
        x=float(x);y=float(y);self.last_snap=None;self.angle_snapped=False
        sp=best_snap(self.doc,x,y,self.snap_tol,self.grid)
        if sp is not None and hypot(float(sp.x)-self.start[0],float(sp.y)-self.start[1])>1e-9:
            self.end=(float(sp.x),float(sp.y));self.last_snap=sp
        else:
            sx,sy=self.start;dx,dy=x-sx,y-sy;length=hypot(dx,dy)
            if self.angle_increment is not None and self.angle_increment>0 and length>1e-12:
                raw=degrees(atan2(dy,dx));angle=round(raw/self.angle_increment)*self.angle_increment
                a=radians(angle);self.end=(sx+length*cos(a),sy+length*sin(a));self.angle_snapped=True
            else:self.end=(x,y)
        sx,sy=self.start;ex,ey=self.end
        self.preview={
            'x1':sx,'y1':sy,'x2':ex,'y2':ey,'z':self.z,
            'width':self.width,'height':self.height,
            'role':self.role,'construction':self.construction,'section':self.section,'level':self.level,
        }
        return HUD({'length':hypot(ex-sx,ey-sy),'x':ex,'y':ey,'z':self.z,'width':self.width,'height':self.height})

    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        sx,sy=self.start;ex,ey=self.end
        if hypot(ex-sx,ey-sy)<0.05:raise ValueError('beam drag is too short; move at least 0.05 m')
        e=Entity('structural_beam',dict(self.preview),name='Beam')
        self.stack.execute(AddEntity(e));return e.id

    def cancel(self):self.cancelled=True


class MEPTerminalPlaceTransaction:
    """Place one human-authored MEP connection point on the active storey."""
    def __init__(self, doc, stack, system_type, x, y, *, level_z=0.0, elevation=0.50, diameter=None, grid=0.10, snap_tol=0.10, snap_enabled=True):
        from archforge.core.router import nominal_diameter_for_system
        self.doc,self.stack=doc,stack
        self.system_type=str(system_type).lower()
        self.level_z=float(level_z)
        self.elevation=float(elevation)
        self.diameter=float(diameter if diameter is not None else nominal_diameter_for_system(self.system_type))
        self.grid=grid
        self.snap_tol=float(snap_tol)
        self.snap_enabled=bool(snap_enabled)
        self.cancelled=False
        self.last_snap=None
        self.x=float(x);self.y=float(y)
        self.update(x,y)

    def update(self,x,y):
        x=float(x);y=float(y)
        self.last_snap=None
        # MEP terminals intentionally do not snap to wall centerlines yet.
        # Until wall-face ports exist, only the soft construction grid is safe:
        # snapping to a wall centre can start an A* route inside a structural obstacle.
        sp=None
        if self.snap_enabled and self.grid:
            gx=round(x/self.grid)*self.grid
            gy=round(y/self.grid)*self.grid
            grid_tolerance=min(self.snap_tol,abs(float(self.grid))*0.20)
            if hypot(gx-x,gy-y)<=grid_tolerance:
                from .snapping import SnapPoint
                sp=SnapPoint(gx,gy,self.level_z,'construction_grid','')
        if sp is not None:
            self.x,self.y=float(sp.x),float(sp.y)
            self.last_snap=sp
        else:
            self.x,self.y=x,y
        return HUD({
            'x':self.x,
            'y':self.y,
            'level_z':self.level_z,
            'elevation':self.elevation,
            'diameter':self.diameter,
        })

    @property
    def preview(self):
        return {
            'x':self.x,
            'y':self.y,
            'level_z':self.level_z,
            'elevation':self.elevation,
            'system_type':self.system_type,
            'diameter':self.diameter,
        }

    def commit(self):
        if self.cancelled:
            raise RuntimeError('transaction cancelled')
        labels={
            'hydraulic':'Water Point',
            'electrical':'Electrical Point',
            'hvac':'HVAC Point',
        }
        e=Entity(
            'mep_terminal',
            dict(self.preview),
            name=labels.get(self.system_type,'MEP Point'),
        )
        self.stack.execute(AddEntity(e))
        return e.id

    def cancel(self):
        self.cancelled=True

class OpeningPlaceTransaction:
    """Attach a door/window frame or a frame-free architectural opening."""
    def __init__(
        self,doc,stack,kind,x,y,tolerance=0.35,width=None,height=None,sill=None,
        flat_margin=0.25,shape='rectangle',arch_rise=None,extra=None,name=None,
    ):
        if kind not in ('door','window','opening'):
            raise ValueError('opening kind must be door, window, or opening')
        self.doc,self.stack,self.kind=doc,stack,kind
        self.tolerance=float(tolerance);self.cancelled=False
        self.width=float(width if width is not None else (.9 if kind=='door' else (1.2 if kind=='window' else 1.0)))
        self.height=float(height if height is not None else (2.1 if kind=='door' else (1.2 if kind=='window' else 2.2)))
        self.sill=float(sill if sill is not None else (0.0 if kind in ('door','opening') else .9))
        self.flat_margin=float(flat_margin)
        self.shape=str(shape).lower() if kind=='opening' else 'rectangle'
        self.arch_rise=float(
            arch_rise if arch_rise is not None else min(self.width/2.0,self.height)
        )
        # Joinery preset (architecture/joinery.py): type parameters and a Greek name.
        self.extra=dict(extra or {}) if kind in ('door','window') else {};self.name=name
        self.host_id=None;self.host_kind=None;self.preview={}
        self.update(x,y)

    def update(self,x,y):
        from archforge.architecture.openings import nearest_opening_host,validate_opening,validate_pod_opening
        hit=nearest_opening_host(self.doc,x,y,self.tolerance)
        if hit is None:
            self.host_id=None;self.host_kind=None;self.preview={}
            return HUD({'valid':0.0})
        host=self.doc.get(hit['host_id'])

        # Frame-free architectural openings are currently wall-only by design.
        if self.kind=='opening' and host.kind!='wall':
            self.host_id=None;self.host_kind=None;self.preview={}
            return HUD({'valid':0.0})

        self.host_id=hit['host_id'];self.host_kind=hit['host_kind']
        if host.kind=='wall':
            p={'offset':hit['offset'],'width':self.width,'height':self.height,'sill':self.sill,**self.extra}
            if self.kind=='opening':
                p.update({'shape':self.shape,'arch_rise':self.arch_rise,'flat_margin':0.0})
            try:
                validate_opening(host.params,p,self.kind);valid=1.0
            except ValueError:
                valid=0.0
            self.preview=p
            hud={'offset':p['offset'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':hit['distance'],'valid':valid}
            if self.kind=='opening':
                hud['arch_rise']=p['arch_rise'] if p['shape']=='arch' else 0.0
            return HUD(hud)

        p={'surface_u':hit['surface_u'],'width':self.width,'height':self.height,'sill':self.sill,'flat_margin':self.flat_margin}
        try:
            validate_pod_opening(host.params,p,self.kind);valid=1.0
        except ValueError:
            valid=0.0
        self.preview=p
        return HUD({'surface_u':p['surface_u'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':hit['distance'],'valid':valid})

    def preview_segment(self):
        if not self.host_id or not self.preview:return None
        from archforge.architecture.openings import plan_segment,pod_opening_plan_segment
        host=self.doc.get(self.host_id)
        return plan_segment(host.params,self.preview) if host.kind=='wall' else pod_opening_plan_segment(host.params,{**self.preview,'_kind':self.kind})

    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        if not self.host_id or not self.preview:raise ValueError('opening must be placed on a valid host')
        host=self.doc.get(self.host_id)
        from archforge.architecture.openings import validate_opening,validate_pod_opening
        if host.kind=='wall':
            validate_opening(host.params,self.preview,self.kind)
        elif host.kind=='pod' and self.kind in ('door','window'):
            validate_pod_opening(host.params,self.preview,self.kind)
        else:
            raise ValueError('free architectural opening must be placed on a wall')
        name=self.name or {'door':'Door','window':'Window','opening':'Opening'}[self.kind]
        e=Entity(self.kind,dict(self.preview),name=name,parent_id=self.host_id)
        if host.kind=='pod':
            from .opening_commands import AddOpeningEntity
            self.stack.execute(AddOpeningEntity(e))
        else:
            self.stack.execute(AddEntity(e))
        return e.id

    def cancel(self):self.cancelled=True

class OpeningEditTransaction:
    """Move/stretch an opening in its host's semantic frame."""
    def __init__(self,doc,stack,eid,handle='move'):
        e=doc.get(eid)
        if e.kind not in ('door','window','opening'):raise ValueError('opening edit requires door/window/opening')
        if not e.parent_id or e.parent_id not in doc.entities or doc.get(e.parent_id).kind not in ('wall','pod'):raise ValueError('opening has no valid wall/pod host')
        if e.kind=='opening' and doc.get(e.parent_id).kind!='wall':raise ValueError('free architectural opening requires wall host')
        if handle not in ('move','left','right'):raise ValueError('opening handle must be move, left or right')
        self.doc,self.stack,self.eid,self.handle=doc,stack,eid,handle
        self.kind=e.kind;self.host_id=e.parent_id;self.before=e.params.copy();self.preview=e.params.copy();self.cancelled=False
    def update(self,x,y):
        host=self.doc.get(self.host_id);p=self.before.copy()
        if host.kind=='pod':
            from archforge.architecture.openings import project_to_pod,validate_pod_opening
            u,px,py,distance=project_to_pod(host.params,x,y)
            if self.handle=='move':p['surface_u']=u
            else:
                from archforge.architecture.openings import pod_opening_plan_segment
                a,b=pod_opening_plan_segment(host.params,{**self.before,'_kind':self.kind});fixed=b if self.handle=='left' else a
                width=hypot(float(x)-fixed[0],float(y)-fixed[1])
                if width<=1e-9:raise ValueError('opening width must remain positive')
                p['width']=width
                mu,_,_,_=project_to_pod(host.params,(float(x)+fixed[0])/2.0,(float(y)+fixed[1])/2.0);p['surface_u']=mu
            validate_pod_opening(host.params,p,self.kind);self.preview=p
            return HUD({'surface_u':p['surface_u'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':distance,'x':px,'y':py,'valid':1.0})
        from archforge.architecture.openings import project_to_wall,validate_opening
        wall=host.params;projected,px,py,distance=project_to_wall(wall,x,y)
        if self.handle=='move':p['offset']=projected
        else:
            left=self.before['offset']-self.before['width']/2;right=self.before['offset']+self.before['width']/2
            if self.handle=='left':left=projected
            else:right=projected
            if right-left<=1e-9:raise ValueError('opening width must remain positive')
            p['offset']=(left+right)/2;p['width']=right-left
        validate_opening(wall,p,self.kind);self.preview=p
        return HUD({'offset':p['offset'],'width':p['width'],'height':p['height'],'sill':p['sill'],'distance':distance,'x':px,'y':py,'valid':1.0})
    def preview_segment(self):
        from archforge.architecture.openings import plan_segment,pod_opening_plan_segment
        host=self.doc.get(self.host_id)
        return plan_segment(host.params,self.preview) if host.kind=='wall' else pod_opening_plan_segment(host.params,{**self.preview,'_kind':self.kind})
    def commit(self):
        if self.cancelled:raise RuntimeError('transaction cancelled')
        self.stack.execute(UpdateEntity(self.eid,self.preview));return self.eid
    def cancel(self):self.cancelled=True;self.preview=self.before.copy()