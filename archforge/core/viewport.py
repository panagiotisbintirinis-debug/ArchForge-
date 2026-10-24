from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
import copy
from .model import Document
from .commands import CommandStack
from .interaction import MoveTransaction,WallDrawTransaction,WallEndpointStretchTransaction,StructuralBeamEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction,OpeningPlaceTransaction,OpeningEditTransaction,StairPlaceTransaction,RampPlaceTransaction,MEPTerminalPlaceTransaction,StructuralColumnPlaceTransaction,StructuralBeamDrawTransaction
from .wall_junction import ConnectedWallEndpointStretchTransaction
from .snapping import best_snap

@dataclass
class PointerEvent:
    a:float;b:float;button:str='left';shift:bool=False;ctrl:bool=False;alt:bool=False

@dataclass
class PreviewState:
    kind:str='none';geometry:Dict[str,Any]=field(default_factory=dict);hud:Dict[str,float]=field(default_factory=dict);snap:Optional[Dict[str,Any]]=None;entity_id:Optional[str]=None

class IncrementalViewportAdapter:
    def __init__(self,doc):self.doc=doc;self.known={}
    def consume(self):
        updates=[];removals=[]
        for eid in sorted(set(self.doc.dirty)):
            if eid in self.doc.entities:
                e=self.doc.entities[eid];updates.append((eid,e.kind,e.revision,copy.deepcopy(e.params),e.visible,e.locked));self.known[eid]=e.revision
            else:removals.append(eid);self.known.pop(eid,None)
        self.doc.dirty.clear();return {'updates':updates,'removals':removals}
    def full_sync(self):
        current=set(self.doc.entities);removals=[eid for eid in self.known if eid not in current];updates=[]
        for eid,e in self.doc.entities.items():updates.append((eid,e.kind,e.revision,copy.deepcopy(e.params),e.visible,e.locked))
        self.known={eid:e.revision for eid,e in self.doc.entities.items()};self.doc.dirty.clear();return {'updates':updates,'removals':removals}

class PointerController:
    def __init__(self,doc,stack):
        self.doc=doc;self.stack=stack;self.tool='select';self.active=None;self.component_definition=None;self.active_entity=None;self.active_handle=None;self.preview=PreviewState();self.construction_grid=.10;self.grid=self.construction_grid;self.snap_tolerance=.10;self.angle_increment=15.;self.wall_angle_increment='magnet';self.wall_angle_reference='relative';self.snap_enabled=True;self.structural_preset={};self.wall_chain=None
    def cycle_option(self,step=1):
        # Tab / wheel during a live Stair or Ramp placement: next option.
        if isinstance(self.active,(StairPlaceTransaction,RampPlaceTransaction)):
            hud=self.active.cycle_candidate(step)
            kind='stair' if isinstance(self.active,StairPlaceTransaction) else 'ramp'
            values=getattr(hud,'values',None) or self.preview.hud
            self.preview=PreviewState(kind,copy.deepcopy(self.active.preview),values,None)
            return True
        return False
    def set_tool(self,tool):
        if self.active is not None:self.cancel()
        self.tool=tool;self.preview=PreviewState();self.opening_preset=None
    def set_component_definition(self,definition):
        self.component_definition=None if definition is None else dict(definition)

    def set_snap_enabled(self,enabled):
        self.snap_enabled=bool(enabled)
    def set_wall_angle_increment(self,increment):
        self.wall_angle_increment=None if increment is None else ('magnet' if increment=='magnet' else float(increment))
        if isinstance(self.active,WallDrawTransaction):
            self.active.angle_increment=self.wall_angle_increment
    def set_wall_angle_reference(self,mode):
        mode=str(mode).lower()
        if mode not in ('global','relative'):
            raise ValueError('wall angle reference must be global or relative')
        self.wall_angle_reference=mode
        if isinstance(self.active,WallDrawTransaction):
            if mode=='global':
                self.active.reference_angle_deg=0.0
            else:
                # Keep the reference captured when the current wall started.
                self.active.reference_angle_deg=float(getattr(self.active,'source_reference_angle_deg',self.active.reference_angle_deg))
    def set_target(self,entity_id,handle=None):self.active_entity=entity_id;self.active_handle=handle
    def _world(self,ev):return self.doc.work_plane.unproject(ev.a,ev.b)
    def _plan_xy(self,ev):x,y,_=self._world(ev);return x,y
    @staticmethod
    def _snap_dict(sp):return None if sp is None else {'x':sp.x,'y':sp.y,'z':sp.z,'kind':sp.kind,'entity_id':sp.entity_id}
    def _opening_preview(self,tx,kind='opening'):
        seg=tx.preview_segment();geom={'opening_kind':tx.kind,'host_id':tx.host_id,'params':copy.deepcopy(tx.preview)}
        if seg:geom.update({'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]})
        return PreviewState(kind,geom,{},None,getattr(tx,'eid',None))
    def _begin_wall(self,sp,x,y,shift=False):
        sx,sy=(sp.x,sp.y) if sp else (x,y)
        geometry_snap_enabled=self.snap_enabled and not shift
        reference_angle=0.0
        if sp is not None and sp.entity_id and sp.entity_id in self.doc.entities:
            ref=self.doc.get(sp.entity_id)
            if ref.kind=='wall':
                import math
                rp=ref.params
                reference_angle=math.degrees(math.atan2(
                    float(rp['y2'])-float(rp['y1']),
                    float(rp['x2'])-float(rp['x1']),
                ))
        # The project brief (wall system) sets what the wall tool draws.
        from archforge.project.brief import wall_defaults
        brief_type,brief_thickness=wall_defaults(self.doc)
        wall_height=2.7
        if self.doc.active_level_name()=='Basement':
            z=float(self.doc.work_plane.origin[2])
            above=[float(v) for v in self.doc.levels.values() if float(v)>z+1e-6]
            if above: wall_height=min(above)-z
        self.active=WallDrawTransaction(
            self.doc,self.stack,(sx,sy),
            z=self.doc.work_plane.origin[2],
            height=wall_height,
            thickness=brief_thickness,
            grid=self.grid,
            snap_tol=self.snap_tolerance,
            snap_enabled=geometry_snap_enabled,
            angle_increment=self.wall_angle_increment,
            reference_angle_deg=(0.0 if self.wall_angle_reference=='global' else reference_angle),
            angle_enabled=not shift,
        )
        self.active.source_reference_angle_deg=reference_angle
        self.active.wall_type=brief_type
        # The line drawn is a face of the wall (brief: exterior / interior dimensions).
        from archforge.project.brief import get_brief
        brief=get_brief(self.doc)
        self.active.reference=brief['measure'] if brief else None
        # Drawn by a face (wall_face.py): the body on one side of the line, from the first point on.
        self.active.face_side=self._face_side()
        if self.active.face_side:self.active.reference=None
        self.preview=PreviewState(
            'wall',
            {'x1':sx,'y1':sy,'x2':sx,'y2':sy,'z':self.doc.work_plane.origin[2]},
            {
                'reference_angle_deg':(
                    0.0 if self.wall_angle_reference=='global' else reference_angle
                ),
                'angle_reference_relative':1.0 if self.wall_angle_reference=='relative' else 0.0,
            },
            self._snap_dict(sp),
        )
        return self.preview
    def _face_side(self,live_dir=None):
        """+1 / -1 / 0: which side of the drawn line the wall's body takes (wall_face.py)."""
        from archforge.architecture.wall_face import SIDES,auto_side
        mode=getattr(self,'wall_face','auto')
        if mode!='auto':return SIDES[mode]
        from archforge.project.brief import get_brief
        brief=get_brief(self.doc)
        measure=brief['measure'] if brief else None
        if not measure:return 0
        return auto_side(measure)                 # fixed side, like Revit's location line (wall_face.py)
    def _face_run_for(self,start):
        """The outline being drawn by faces when a wall starts at ``start`` (its last wall ends there), else empty —
        click-click chains and walls dragged one after the other alike."""
        import math
        run=getattr(self,'_face_run',None)
        if run and run['segs'] and start is not None and math.dist(run['segs'][-1]['b'],tuple(start))<1e-6 \
                and run['segs'][-1]['id'] in self.doc.entities:
            return run
        return {}
    def flip_wall_face(self):
        """F while drawing walls: the body goes to the other side of the line (axis → left → right)."""
        side=self.active.face_side if isinstance(self.active,WallDrawTransaction) else self._face_side()
        self.wall_face={0:'left',1:'right',-1:'left'}[side] if side else 'left'
        if isinstance(self.active,WallDrawTransaction):
            self.active.face_side=self._face_side()
            if self.active.face_side:self.active.reference=None
        return self.wall_face
    def pointer_down(self,ev):
        x,y=self._plan_xy(ev)
        if self.tool=='wall' and self.wall_chain is not None and isinstance(self.active,WallDrawTransaction):
            # Click-click walls: the press of the next corner only ends the rubber segment (on release).
            return self.preview
        if self.tool=='wall':
            geometry_snap_enabled=self.snap_enabled and not ev.shift
            sp=best_snap(self.doc,x,y,self.snap_tolerance,self.grid) if geometry_snap_enabled else None
            return self._begin_wall(sp,x,y,ev.shift)
        if self.tool=='component':
            if not self.component_definition:return self.preview
            from archforge.components.placement import ComponentPlaceTransaction
            self.active=ComponentPlaceTransaction(
                self.doc,self.stack,x,y,self.component_definition,
                z=float(self.doc.work_plane.origin[2]),grid=self.grid,snap_tol=self.snap_tolerance,
            )
            self.preview=PreviewState('component',copy.deepcopy(self.active.preview),{},self._snap_dict(self.active.last_snap))
            return self.preview
        if self.tool in ('structural_column','structural_beam'):
            active_z=float(self.doc.work_plane.origin[2])
            level_name=self.doc.active_level_name()
            above=sorted(
                (float(z),str(name))
                for name,z in self.doc.levels.items()
                if float(z)>active_z+1e-9
            )
            if above:
                next_z,next_name=above[0]
            else:
                next_z,next_name=active_z+2.70,'Unassigned'

            geometry_snap_enabled=self.snap_enabled and not ev.shift
            sp=best_snap(self.doc,x,y,self.snap_tolerance,self.grid) if geometry_snap_enabled else None
            sx,sy=(float(sp.x),float(sp.y)) if sp is not None else (x,y)

            if self.tool=='structural_column':
                self.active=StructuralColumnPlaceTransaction(
                    self.doc,self.stack,x,y,
                    z=active_z,
                    **{k:v for k,v in getattr(self,'structural_preset',{}).items() if k in ('width','depth','construction','section','role','wall')},
                    base_level=level_name,
                    grid=(self.grid if geometry_snap_enabled else None),
                    snap_tol=self.snap_tolerance,
                    snap_enabled=geometry_snap_enabled,
                    follow_walls=True,
                )
                hud=self.active.update(x,y)
                self.preview=PreviewState(
                    'structural-column',
                    copy.deepcopy(self.active.preview),
                    hud.values,
                    self._snap_dict(self.active.last_snap),
                )
                return self.preview

            preset=getattr(self,'structural_preset',{}) if self.tool=='structural_beam' else {}
            beam_height=float(preset.get('height',.30))
            from archforge.structure.column_wall import storey_member_top
            beam_z=storey_member_top(self.doc,sx,sy,active_z)-beam_height
            self.active=StructuralBeamDrawTransaction(
                self.doc,self.stack,(sx,sy),
                z=beam_z,width=float(preset.get('width',.20)),height=beam_height,
                # The beam physically sits under the next level, but belongs to
                # the storey from which the human authored it. Keeping that
                # ownership on the active level prevents a just-created beam
                # from disappearing from the Structural plan.
                level=level_name,
                grid=(self.grid if geometry_snap_enabled else None),
                snap_tol=self.snap_tolerance,
                angle_increment=self.angle_increment,
            )
            self.preview=PreviewState(
                'structural-beam',
                copy.deepcopy(self.active.preview),
                {'length':0.0,'z':beam_z,'width':.20,'height':beam_height},
                self._snap_dict(sp),
            )
            return self.preview
        if self.tool in ('mep_hydraulic','mep_electrical','mep_hvac'):
            system_type=self.tool.replace('mep_','')
            self.active=MEPTerminalPlaceTransaction(
                self.doc,self.stack,system_type,x,y,
                level_z=self.doc.work_plane.origin[2],
                elevation=0.50,
                grid=self.grid,
                snap_tol=self.snap_tolerance,
                snap_enabled=self.snap_enabled and not ev.shift,
            )
            hud=self.active.update(x,y)
            self.preview=PreviewState(
                'mep-terminal',
                copy.deepcopy(self.active.preview),
                hud.values,
                self._snap_dict(self.active.last_snap),
            )
            return self.preview
        if self.tool=='stair':
            self.active=StairPlaceTransaction(self.doc,self.stack,(x,y),layout=getattr(self,'stair_layout',None))
            hud=self.active.update(x,y)
            self.preview=PreviewState('stair',copy.deepcopy(self.active.preview),hud.values,None)
            return self.preview
        if self.tool=='ramp':
            self.active=RampPlaceTransaction(self.doc,self.stack,(x,y))
            hud=self.active.update(x,y)
            self.preview=PreviewState('ramp',copy.deepcopy(self.active.preview),hud.values,None)
            return self.preview
        if self.tool in ('door','window','opening_rect','opening_arch'):
            opening_kind='opening' if self.tool.startswith('opening_') else self.tool
            opening_shape='arch' if self.tool=='opening_arch' else 'rectangle'
            preset=getattr(self,'opening_preset',None)
            preset=preset if preset and preset.get('kind')==opening_kind else {}
            self.active=OpeningPlaceTransaction(
                self.doc,self.stack,opening_kind,x,y,
                tolerance=max(self.snap_tolerance,.35),
                shape=opening_shape,
                width=preset.get('width'),height=preset.get('height'),sill=preset.get('sill'),
                extra=preset.get('params'),name=preset.get('name'),
            )
            hud=self.active.update(x,y);seg=self.active.preview_segment()
            geom={
                'opening_kind':opening_kind,
                'opening_shape':opening_shape,
                'host_id':self.active.host_id,
                'params':copy.deepcopy(self.active.preview),
            }
            if seg:geom.update({'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]})
            self.preview=PreviewState('opening',geom,hud.values,None);return self.preview
        if self.tool=='move':
            ids=list(self.doc.selection)
            if not ids:return self.preview
            if len(ids)==1 and self.doc.get(ids[0]).kind in ('door','window','opening'):
                self.active=OpeningEditTransaction(self.doc,self.stack,ids[0],'move')
                hud=self.active.update(x,y);seg=self.active.preview_segment();geom={'opening_kind':self.active.kind,'host_id':self.active.host_id,'params':copy.deepcopy(self.active.preview),'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]};self.preview=PreviewState('opening-edit',geom,hud.values,None,ids[0]);return self.preview
            if len(ids)==1 and self.doc.get(ids[0]).kind=='wall':
                # A wall joined to others moves perpendicular to itself and keeps its junctions.
                from archforge.architecture.wall_edit import is_joined
                if is_joined(self.doc,ids[0]):return self.begin_wall_move(ids[0],ev.a,ev.b)
            self.active=MoveTransaction(self.doc,self.stack,ids,origin=(x,y,self.doc.work_plane.origin[2]),grid=self.grid,snap_tol=self.snap_tolerance);self.preview=PreviewState('move',{'entities':copy.deepcopy(self.active.preview)},{'dx':0.,'dy':0.,'distance':0.},None);return self.preview
        if self.tool=='stretch':
            if not self.active_entity or self.active_entity not in self.doc.entities:return self.preview
            e=self.doc.get(self.active_entity)
            if e.kind=='wall':self.active=ConnectedWallEndpointStretchTransaction(self.doc,self.stack,e.id,1 if self.active_handle in ('1','start','endpoint1') else 2,self.grid,self.snap_tolerance)
            elif e.kind=='box':self.active=BoxStretchTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            elif e.kind=='pod':self.active=PodStretchTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            elif e.kind=='structural_beam':
                if self.active_handle in ('endpoint1','start','1'):endpoint=1
                elif self.active_handle in ('endpoint2','end','2'):endpoint=2
                else:
                    d1=hypot(x-float(e.params['x1']),y-float(e.params['y1']))
                    d2=hypot(x-float(e.params['x2']),y-float(e.params['y2']))
                    endpoint=1 if d1<=d2 else 2
                self.active=StructuralBeamEndpointStretchTransaction(
                    self.doc,self.stack,e.id,endpoint,
                    grid=self.grid,snap_tol=self.snap_tolerance,
                    snap_enabled=self.snap_enabled and not ev.shift,
                )
            elif e.kind in ('door','window','opening'):self.active=OpeningEditTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            else:raise ValueError('stretch unsupported for entity kind')
            return self.pointer_move(ev)
        if self.tool=='rotate':
            if not self.active_entity or self.active_entity not in self.doc.entities:return self.preview
            self.active=RotateTransaction(self.doc,self.stack,self.active_entity,angle_increment=self.angle_increment);px,py=self.active.pivot;import math;self._rotate_start_angle=math.degrees(math.atan2(y-py,x-px));self.preview=PreviewState('rotate',copy.deepcopy(self.active.preview),{'angle_deg':0.,'pivot_x':px,'pivot_y':py},None,self.active_entity);return self.preview
        return self.preview
    def pointer_move(self,ev):
        x,y=self._plan_xy(ev)
        if isinstance(self.active,WallDrawTransaction):
            self.active.outline_start=tuple(self.wall_chain['first']) if self.wall_chain else None
            run=self._face_run_for(self.active.start) if self.wall_chain else {}
            segs=run.get('segs') or []
            # By a face: the first wall's drawn face, which the held angle may close on (WallDrawTransaction._face_close).
            self.active.outline_face_first=(tuple(segs[0]['a']),tuple(segs[0]['b'])) if len(segs)>=2 and segs[0]['id'] in self.doc.entities else None
            self.active.snap_enabled=self.snap_enabled and not ev.shift
            self.active.angle_enabled=not ev.shift
            # Ctrl: no corner autosnap (the angle magnet stays) — to stop near a corner on purpose.
            self.active.corner_enabled=not ev.ctrl
            hud=self.active.update(x,y);sx,sy=self.active.start;ex,ey=self.active.end
            snap_info=self._snap_dict(self.active.last_snap)
            if snap_info is None and self.active.angle_snapped:
                snap_info={
                    'x':ex,'y':ey,'z':self.active.z,
                    'kind':'angle','entity_id':'',
                }
            L=((ex-sx)**2+(ey-sy)**2)**.5
            if getattr(self,'wall_face','auto')=='auto' and L>1e-9:
                self.active.face_side=self._face_side(((ex-sx)/L,(ey-sy)/L))
                if self.active.face_side:self.active.reference=None
            self.preview=PreviewState(
                'wall',
                {'x1':sx,'y1':sy,'x2':ex,'y2':ey,'z':self.active.z,
                 'thickness':float(self.active.thickness),'face_side':int(getattr(self.active,'face_side',0) or 0),
                 **({'guide':self.active.guide} if getattr(self.active,'guide',None) else {})},
                hud.values,
                snap_info,
            )
        elif self.active.__class__.__name__=='WallMoveTransaction':
            self.preview=PreviewState('wall-move',self.active.update(x,y),{},None,self.active.eid)
        elif isinstance(self.active,ConnectedWallEndpointStretchTransaction):
            self.active.angle_enabled=not ev.shift
            hud=self.active.update(x,y);geom=copy.deepcopy(self.active.preview);geom['entities']=copy.deepcopy(self.active.previews);self.preview=PreviewState('stretch',geom,hud.values,None,self.active.eid)
        elif isinstance(self.active,WallEndpointStretchTransaction):hud=self.active.update(x,y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,StructuralBeamEndpointStretchTransaction):
            self.active.snap_enabled=self.snap_enabled and not ev.shift
            hud=self.active.update(x,y)
            self.preview=PreviewState(
                'stretch',copy.deepcopy(self.active.preview),hud.values,
                self._snap_dict(self.active.last_snap),self.active.eid,
            )
        elif isinstance(self.active,BoxStretchTransaction):hud=self.active.update(x=x,y=y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,PodStretchTransaction):
            hud=self.active.update(x=x) if self.active.handle in ('left','right') else self.active.update(y=y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,RotateTransaction):hud=self.active.update_pointer(x,y,self._rotate_start_angle,snap=self.snap_enabled and not ev.shift);self.preview=PreviewState('rotate',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif self.active.__class__.__name__=='ComponentPlaceTransaction':
            self.active.update(x,y)
            self.preview=PreviewState('component',copy.deepcopy(self.active.preview),{},self._snap_dict(self.active.last_snap))
        elif isinstance(self.active,StructuralColumnPlaceTransaction):
            self.active.snap_enabled=self.snap_enabled and not ev.shift
            self.active.grid=self.grid if self.active.snap_enabled else None
            hud=self.active.update(x,y)
            self.preview=PreviewState(
                'structural-column',
                copy.deepcopy(self.active.preview),
                hud.values,
                self._snap_dict(self.active.last_snap),
            )
        elif isinstance(self.active,StructuralBeamDrawTransaction):
            hud=self.active.update(x,y)
            sx,sy=self.active.start;ex,ey=self.active.end
            snap_info=self._snap_dict(self.active.last_snap)
            if snap_info is None and self.active.angle_snapped:
                snap_info={'x':ex,'y':ey,'z':self.active.z,'kind':'angle','entity_id':''}
            self.preview=PreviewState(
                'structural-beam',
                copy.deepcopy(self.active.preview),
                hud.values,
                snap_info,
            )
        elif isinstance(self.active,MEPTerminalPlaceTransaction):
            self.active.snap_enabled=self.snap_enabled and not ev.shift
            hud=self.active.update(x,y)
            self.preview=PreviewState(
                'mep-terminal',
                copy.deepcopy(self.active.preview),
                hud.values,
                self._snap_dict(self.active.last_snap),
            )
        elif isinstance(self.active,OpeningPlaceTransaction):
            hud=self.active.update(x,y);seg=self.active.preview_segment();geom={'opening_kind':self.active.kind,'host_id':self.active.host_id,'params':copy.deepcopy(self.active.preview)}
            if seg:geom.update({'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]})
            self.preview=PreviewState('opening',geom,hud.values,None)
        elif isinstance(self.active,OpeningEditTransaction):
            hud=self.active.update(x,y);seg=self.active.preview_segment();geom={'opening_kind':self.active.kind,'host_id':self.active.host_id,'params':copy.deepcopy(self.active.preview),'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]}
            self.preview=PreviewState('opening-edit',geom,hud.values,None,self.active.eid)
        elif isinstance(self.active,StairPlaceTransaction):
            hud=self.active.update(x,y)
            self.preview=PreviewState('stair',copy.deepcopy(self.active.preview),hud.values,None)
        elif isinstance(self.active,RampPlaceTransaction):
            hud=self.active.update(x,y)
            self.preview=PreviewState('ramp',copy.deepcopy(self.active.preview),hud.values,None)
        elif isinstance(self.active,MoveTransaction):
            hud=self.active.update_pointer(
                x,y,
                snap=self.snap_enabled and not ev.shift,
                axis_lock=bool(ev.ctrl),
            )
            values=dict(hud.values);values['distance']=(self.active.dx*self.active.dx+self.active.dy*self.active.dy)**.5
            self.preview=PreviewState('move',{'entities':copy.deepcopy(self.active.preview)},values,None)
        return self.preview
    def pointer_up(self,ev,exact=None):
        if self.active is None:return self.preview
        self.last_warning=None
        self.pointer_move(ev);committed_id=None
        if isinstance(self.active,WallDrawTransaction):
            tx=self.active
            import math
            if exact is None and math.hypot(tx.end[0]-tx.start[0],tx.end[1]-tx.start[1])<tx.min_length:
                if self.wall_chain is None:
                    # A click without a drag: click-click walls, one corner per click.
                    self.wall_chain={'first':tuple(tx.start),'count':0}
                    return self.preview
                # A second click on the same corner (double click): the chain ends.
                self.finish_wall_chain();return self.preview
            committed_id=self._commit_wall(exact)
            if self.wall_chain is not None:
                self.wall_chain['count']+=1
                ex,ey=tx.end;fx,fy=self.wall_chain['first']
                moved=getattr(tx,'moved_end',None)
                if moved and math.hypot(moved[0][0]-fx,moved[0][1]-fy)<1e-6:fx,fy=moved[1]   # the first corner moved to meet it
                if getattr(tx,'face_close',None) is not None:fx,fy=ex,ey            # closed on the first wall's face
                if committed_id is None or math.hypot(ex-fx,ey-fy)<1e-6:
                    # Back on the first corner: the outline is closed.
                    self.finish_wall_chain();result=self.preview;result.entity_id=committed_id;return result
                from .snapping import SnapPoint
                self._begin_wall(SnapPoint(ex,ey,float(tx.z),'endpoint',committed_id),ex,ey,ev.shift)
                result=copy.deepcopy(self.preview);result.entity_id=committed_id;return result
        elif self.active.__class__.__name__=='WallMoveTransaction':
            committed_id=self.active.commit();self.preview=PreviewState()
        elif isinstance(self.active,(ConnectedWallEndpointStretchTransaction,WallEndpointStretchTransaction,StructuralBeamEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction,OpeningEditTransaction)):
            self.active.commit();committed_id=getattr(self.active,'eid',None)
            if isinstance(self.active,(ConnectedWallEndpointStretchTransaction,WallEndpointStretchTransaction)) and committed_id in self.doc.entities:
                self._split_at_junctions(committed_id)
        elif self.active.__class__.__name__=='ComponentPlaceTransaction':committed_id=self.active.commit()
        elif isinstance(self.active,StructuralColumnPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,StructuralBeamDrawTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,MEPTerminalPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,OpeningPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,StairPlaceTransaction):
            fits=bool(self.active.preview.get('fits',True));committed_id=self.active.commit()
            self.last_warning=('Σκάλα: μπήκε μέσα στους τοίχους · η πλάκα του ορόφου ανοίγει μόνο όπου δεν μένουν 2,00 m '
                               'ύψος διέλευσης — ο υπόλοιπος χώρος από πάνω μένει · Ctrl+Z = αναίρεση' if fits else
                               '⚠ Η σκάλα μπήκε αλλά συγκρούεται (τοίχος, πόρτα, ντουλάπια ή άλλη σκάλα) — μετακίνησέ τη ή άλλαξε τύπο · Ctrl+Z = αναίρεση')
        elif isinstance(self.active,RampPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,MoveTransaction):
            if abs(self.active.dx)>1e-12 or abs(self.active.dy)>1e-12 or abs(self.active.dz)>1e-12:self.active.commit()
        result=self.preview;result.entity_id=committed_id;self.active=None;return result
    def _commit_face_wall(self,exact,interior,faces_before):
        """The wall drawn by a face: its axis half a wall to the body side; in a chain, the axes of consecutive walls
        meet (the previous wall's end moves to the crossing), and closing the outline joins the first wall too."""
        import math
        from archforge.architecture.wall_face import intersect,offset_segment
        from archforge.core.commands import UpdateEntity
        from archforge.project.brief import wall_is_interior
        tx=self.active
        a=tuple(tx.start);b=tuple(tx.end)
        length=(exact or {}).get('length')
        if length:
            L=math.dist(a,b)
            if L>0:b=(a[0]+(b[0]-a[0])/L*float(length),a[1]+(b[1]-a[1])/L*float(length))
        drawn={'x1':a[0],'y1':a[1],'x2':b[0],'y2':b[1]}
        self._face_partition=bool(interior and wall_is_interior(faces_before,drawn))
        if self._face_partition:tx.thickness=float(interior[1])
        side=tx.face_side;t=float(tx.thickness)
        chain=self._face_run_for(a)
        if not chain:
            chain=self._face_run={'segs':[],'turn':0,'first':a}       # a new outline starts here
        segs=chain['segs']
        prev=segs[-1] if segs else None
        auto=getattr(self,'wall_face','auto')=='auto'
        if prev is None and auto:
            # Alone so far: where its preview showed it — the drawn line is its face (owner 24/10: «η σχεδιαστική
            # γραμμή είναι τώρα το πάχος του τοίχου, αλλά όταν το κλείνεις… περνάει τη διάσταση προς τα μέσα»). The
            # next wall's turn says which side is inside; the body crosses over then, the drawn line stays the face.
            tx.start,tx.end=offset_segment(a,b,side,t)
            try:
                committed=tx.commit(None)
            finally:
                tx.start,tx.end=a,b
            segs.append({'a':a,'b':b,'side':side,'t':t,'id':committed,'applied':False})
            return committed
        na,nb=offset_segment(a,b,side,t)
        if prev is not None:
            if auto and len(segs)==1 and prev['side']!=side:
                prev['side']=side                                  # the first corner told which side is inside
            pa,pb=offset_segment(prev['a'],prev['b'],prev['side'],prev['t'])
            if prev.get('applied',True) and len(segs)>1:
                pa=(float(self.doc.get(prev['id']).params['x1']),float(self.doc.get(prev['id']).params['y1']))
            c=intersect(pa,pb,na,nb) or na
            changes={'x1':pa[0],'y1':pa[1],'x2':c[0],'y2':c[1]}
            if auto:changes['reference_applied']=True              # the brief's measure is done (no move at closing)
            self.stack.execute(UpdateEntity(prev['id'],changes))
            prev['applied']=True
            na=c
            chain['turn']=chain.get('turn') or 0
            if not chain['turn']:
                from archforge.architecture.wall_face import turn
                L1=math.dist(prev['a'],prev['b']);L2=math.dist(a,b)
                if L1>0 and L2>0:
                    chain['turn']=turn(((prev['b'][0]-prev['a'][0])/L1,(prev['b'][1]-prev['a'][1])/L1),((b[0]-a[0])/L2,(b[1]-a[1])/L2))
        first=chain.get('first')
        closed_on_face=getattr(tx,'face_close',None) is not None and not length     # on the first face line, not its corner
        closing=len(segs)>=2 and first is not None and (math.dist(b,first)<1e-6 or closed_on_face) and segs[0]['id'] in self.doc.entities
        tx.start,tx.end=na,nb
        try:
            committed=tx.commit(None)
        finally:
            tx.start,tx.end=a,b
        if auto and committed in self.doc.entities:
            self.stack.execute(UpdateEntity(committed,{'reference_applied':True}))
        if closing and committed in self.doc.entities:
            f=segs[0];fa,fb=offset_segment(f['a'],f['b'],f['side'],f['t'])
            fe=self.doc.get(f['id']).params
            c=intersect(na,nb,fa,fb) or nb
            self.stack.execute(UpdateEntity(committed,{'x2':c[0],'y2':c[1]}))
            self.stack.execute(UpdateEntity(f['id'],{'x1':c[0],'y1':c[1],'x2':float(fe['x2']),'y2':float(fe['y2'])}))
        segs.append({'a':a,'b':b,'side':side,'t':t,'id':committed})
        return committed
    def _commit_wall(self,exact=None):
        committed_id=None
        from archforge.project.brief import interior_wall_defaults,wall_is_interior
        interior=interior_wall_defaults(self.doc)
        faces_before=self.doc.active_room_faces(z=self.active.z) if interior else []
        rooms_before=len(faces_before) if interior else len(self.doc.active_room_faces(z=self.active.z))
        since=len(self.stack.done)
        if getattr(self.active,'face_side',0) and getattr(self,'wall_face','auto')=='auto' and interior and wall_is_interior(
                faces_before,{'x1':self.active.start[0],'y1':self.active.start[1],'x2':self.active.end[0],'y2':self.active.end[1]}):
            self.active.face_side=0                                # a partition inside a space: on its axis
        if getattr(self.active,'face_side',0):
            committed_id=self._commit_face_wall(exact,interior,faces_before)
        else:
            committed_id=self.active.commit((exact or {}).get('length'))
        face=bool(getattr(self.active,'face_side',0))
        if committed_id and interior and committed_id in self.doc.entities and (
                getattr(self,'_face_partition',False) if face else wall_is_interior(faces_before,self.doc.get(committed_id).params)):
            # A wall inside a closed space is a partition: the brief's interior wall type — same undo step.
            from archforge.core.commands import UpdateEntity
            itype,ithick,bearing=interior
            self.stack.amend(UpdateEntity(committed_id,{'wall_type':itype,'thickness':ithick,'load_bearing':bool(bearing)}))
        if committed_id and committed_id in self.doc.entities:
            # A wall ending on (or crossing) another one splits it there — same undo step.
            self._split_at_junctions(committed_id)
        if committed_id and getattr(self.active,'reference',None):
            # A wall that closes a space moves onto its axis — same undo step as the wall.
            from archforge.architecture.dimension_reference import ApplyDimensionReference
            apply=ApplyDimensionReference(self.active.z)
            from archforge.architecture.dimension_reference import plan as reference_plan
            if any(reference_plan(self.doc,self.active.z)):
                self.stack.amend(apply)
        if committed_id and getattr(self,'auto_floors',False):
            # A closed outline of walls has its floor without being asked (owner 14/10) — same undo step.
            # The storey slab follows the walls, so it is made once per storey; fences keep their ground.
            from archforge.architecture.storey_slabs import auto_floor_command
            command=auto_floor_command(self.doc,float(self.active.z))
            if command is not None:self.stack.amend(command)
        if committed_id and getattr(self,'auto_dimensions',True):
            # A space closes: its exterior dimensions appear by themselves (owner 24/10, as in Home Designer / Chief
            # Architect) — once per storey; turned off in CAD ▸ Διαστάσεις, they stay off.
            from archforge.architecture import dimensions as dims
            z=float(self.active.z)
            if dims.settings(self.doc,z) is None and len(self.doc.active_room_faces(z=z))>rooms_before:
                self.stack.amend(dims.set_auto(self.doc,z,exterior=True))
        self.stack.squash(since,'Τοίχος')       # the wall and its corner with the previous one: one undo step
        return committed_id
    def draw_room_box(self,clear_corners):
        """Δωμάτιο (ορθογώνιο): the walls around clear (inside) corners, each drawn by the wall tool's own commit
        (brief thickness, partitions, splits, the storey floor); sides lying on existing walls merge with them.
        The whole room is one undo step."""
        from archforge.architecture.room_box import inside_space, plan_room
        from archforge.project.brief import interior_wall_defaults, wall_defaults
        z=float(self.doc.work_plane.origin[2])
        thickness=float(wall_defaults(self.doc)[1])
        interior=interior_wall_defaults(self.doc)
        if interior and inside_space(self.doc,clear_corners,z):thickness=float(interior[1])   # a partition
        sides=plan_room(self.doc,list(clear_corners),z,thickness)
        if sides is None:raise ValueError('Το δωμάτιο χρειάζεται πλάτος και βάθος')
        if not sides:raise ValueError('οι τοίχοι υπάρχουν ήδη')
        since=len(self.stack.done);made=[]
        try:
            for a,b in sides:
                self._begin_wall(None,a[0],a[1],shift=True)        # exact corners: no magnet, no snapping
                self.active.thickness=thickness;self.active.face_side=0   # plan_room gives the axes already
                self.active.update(*b);made.append(self._commit_wall());self.active=None
        except Exception:
            self.active=None
            while len(self.stack.done)>since:self.stack.undo()
            self.stack.undone.clear()
            raise
        self.stack.squash(since,'Δωμάτιο')
        self.preview=PreviewState()
        return made
    def finish_wall_chain(self):
        """End click-click walls: drop the rubber segment, keep the walls already made."""
        if isinstance(self.active,WallDrawTransaction):self.active.cancel()
        self.active=None;self.wall_chain=None;self.preview=PreviewState()
    def begin_wall_move(self,eid,a,b):
        """Dragging a wall's body: it moves perpendicular to its axis with what is joined to it."""
        from archforge.architecture.wall_edit import WallMoveTransaction
        x,y=self._plan_xy(PointerEvent(a,b))
        self.active=WallMoveTransaction(self.doc,self.stack,eid,x,y)
        self.preview=PreviewState('wall-move',self.active.preview(),{},None,eid)
        return self.preview
    def _split_at_junctions(self,eid):
        from archforge.architecture.wall_edit import SplitWalls,junction_cuts
        cuts,warnings=junction_cuts(self.doc,eid)
        self.last_warning=' · '.join(warnings) or None
        if cuts:self.stack.amend(SplitWalls(cuts))
    def cancel(self):
        if hasattr(self.active,'cancel'):self.active.cancel()
        self.active=None;self.wall_chain=None;self.preview=PreviewState()
