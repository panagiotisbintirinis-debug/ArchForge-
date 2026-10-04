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
        self.doc=doc;self.stack=stack;self.tool='select';self.active=None;self.component_definition=None;self.active_entity=None;self.active_handle=None;self.preview=PreviewState();self.construction_grid=.10;self.grid=self.construction_grid;self.snap_tolerance=.10;self.angle_increment=15.;self.wall_angle_increment=90.;self.wall_angle_reference='relative';self.snap_enabled=True
    def set_tool(self,tool):
        if self.active is not None:self.cancel()
        self.tool=tool;self.preview=PreviewState()
    def set_component_definition(self,definition):
        self.component_definition=None if definition is None else dict(definition)

    def set_snap_enabled(self,enabled):
        self.snap_enabled=bool(enabled)
    def set_wall_angle_increment(self,increment):
        self.wall_angle_increment=None if increment is None else float(increment)
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
    def pointer_down(self,ev):
        x,y=self._plan_xy(ev)
        if self.tool=='wall':
            geometry_snap_enabled=self.snap_enabled and not ev.shift
            sp=best_snap(self.doc,x,y,self.snap_tolerance,self.grid) if geometry_snap_enabled else None
            sx,sy=(sp.x,sp.y) if sp else (x,y)
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
            self.active=WallDrawTransaction(
                self.doc,self.stack,(sx,sy),
                z=self.doc.work_plane.origin[2],
                grid=self.grid,
                snap_tol=self.snap_tolerance,
                snap_enabled=geometry_snap_enabled,
                angle_increment=self.wall_angle_increment,
                reference_angle_deg=(0.0 if self.wall_angle_reference=='global' else reference_angle),
                angle_enabled=not ev.shift,
            )
            self.active.source_reference_angle_deg=reference_angle
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
                height=max(0.05,next_z-active_z)
                self.active=StructuralColumnPlaceTransaction(
                    self.doc,self.stack,sx,sy,
                    z=active_z,height=height,
                    base_level=level_name,top_level=next_name,
                    grid=(self.grid if geometry_snap_enabled else None),
                    snap_tol=self.snap_tolerance,
                )
                hud=self.active.update(sx,sy)
                self.preview=PreviewState(
                    'structural-column',
                    copy.deepcopy(self.active.preview),
                    hud.values,
                    self._snap_dict(self.active.last_snap),
                )
                return self.preview

            beam_height=.30
            beam_z=next_z-beam_height
            self.active=StructuralBeamDrawTransaction(
                self.doc,self.stack,(sx,sy),
                z=beam_z,width=.20,height=beam_height,
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
            self.active=StairPlaceTransaction(self.doc,self.stack,(x,y))
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
            self.active=OpeningPlaceTransaction(
                self.doc,self.stack,opening_kind,x,y,
                tolerance=max(self.snap_tolerance,.35),
                shape=opening_shape,
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
            self.active.snap_enabled=self.snap_enabled and not ev.shift
            self.active.angle_enabled=not ev.shift
            hud=self.active.update(x,y);sx,sy=self.active.start;ex,ey=self.active.end
            snap_info=self._snap_dict(self.active.last_snap)
            if snap_info is None and self.active.angle_snapped:
                snap_info={
                    'x':ex,'y':ey,'z':self.active.z,
                    'kind':'angle','entity_id':'',
                }
            self.preview=PreviewState(
                'wall',
                {'x1':sx,'y1':sy,'x2':ex,'y2':ey,'z':self.active.z},
                hud.values,
                snap_info,
            )
        elif isinstance(self.active,ConnectedWallEndpointStretchTransaction):
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
        self.pointer_move(ev);committed_id=None
        if isinstance(self.active,WallDrawTransaction):committed_id=self.active.commit((exact or {}).get('length'))
        elif isinstance(self.active,(ConnectedWallEndpointStretchTransaction,WallEndpointStretchTransaction,StructuralBeamEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction,OpeningEditTransaction)):self.active.commit();committed_id=getattr(self.active,'eid',None)
        elif self.active.__class__.__name__=='ComponentPlaceTransaction':committed_id=self.active.commit()
        elif isinstance(self.active,StructuralColumnPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,StructuralBeamDrawTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,MEPTerminalPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,OpeningPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,StairPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,RampPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,MoveTransaction):
            if abs(self.active.dx)>1e-12 or abs(self.active.dy)>1e-12 or abs(self.active.dz)>1e-12:self.active.commit()
        result=self.preview;result.entity_id=committed_id;self.active=None;return result
    def cancel(self):
        if hasattr(self.active,'cancel'):self.active.cancel()
        self.active=None;self.preview=PreviewState()
