from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
import copy
from .model import Document
from .commands import CommandStack
from .interaction import MoveTransaction,WallDrawTransaction,WallEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction,OpeningPlaceTransaction,OpeningEditTransaction,StairPlaceTransaction,RampPlaceTransaction
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
        self.doc=doc;self.stack=stack;self.tool='select';self.active=None;self.active_entity=None;self.active_handle=None;self.preview=PreviewState();self.grid=.1;self.snap_tolerance=.15;self.angle_increment=15.
    def set_tool(self,tool):
        if self.active is not None:self.cancel()
        self.tool=tool;self.preview=PreviewState()
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
            sp=best_snap(self.doc,x,y,self.snap_tolerance,self.grid);sx,sy=(sp.x,sp.y) if sp else (x,y);self.active=WallDrawTransaction(self.doc,self.stack,(sx,sy),z=self.doc.work_plane.origin[2],grid=self.grid,snap_tol=self.snap_tolerance);self.preview=PreviewState('wall',{'x1':sx,'y1':sy,'x2':sx,'y2':sy,'z':self.doc.work_plane.origin[2]}, {}, self._snap_dict(sp));return self.preview
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
        if self.tool in ('door','window'):
            self.active=OpeningPlaceTransaction(self.doc,self.stack,self.tool,x,y,tolerance=max(self.snap_tolerance,.35));hud=self.active.update(x,y);seg=self.active.preview_segment();geom={'opening_kind':self.tool,'host_id':self.active.host_id,'params':copy.deepcopy(self.active.preview)}
            if seg:geom.update({'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]})
            self.preview=PreviewState('opening',geom,hud.values,None);return self.preview
        if self.tool=='move':
            ids=list(self.doc.selection)
            if not ids:return self.preview
            if len(ids)==1 and self.doc.get(ids[0]).kind in ('door','window'):
                self.active=OpeningEditTransaction(self.doc,self.stack,ids[0],'move')
                hud=self.active.update(x,y);seg=self.active.preview_segment();geom={'opening_kind':self.active.kind,'host_id':self.active.host_id,'params':copy.deepcopy(self.active.preview),'x1':seg[0][0],'y1':seg[0][1],'x2':seg[1][0],'y2':seg[1][1]};self.preview=PreviewState('opening-edit',geom,hud.values,None,ids[0]);return self.preview
            self.active=MoveTransaction(self.doc,self.stack,ids,origin=(x,y,self.doc.work_plane.origin[2]),grid=self.grid,snap_tol=self.snap_tolerance);self.preview=PreviewState('move',{'entities':copy.deepcopy(self.active.preview)},{'dx':0.,'dy':0.,'distance':0.},None);return self.preview
        if self.tool=='stretch':
            if not self.active_entity or self.active_entity not in self.doc.entities:return self.preview
            e=self.doc.get(self.active_entity)
            if e.kind=='wall':self.active=ConnectedWallEndpointStretchTransaction(self.doc,self.stack,e.id,1 if self.active_handle in ('1','start','endpoint1') else 2,self.grid,self.snap_tolerance)
            elif e.kind=='box':self.active=BoxStretchTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            elif e.kind=='pod':self.active=PodStretchTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            elif e.kind in ('door','window'):self.active=OpeningEditTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            else:raise ValueError('stretch unsupported for entity kind')
            return self.pointer_move(ev)
        if self.tool=='rotate':
            if not self.active_entity or self.active_entity not in self.doc.entities:return self.preview
            self.active=RotateTransaction(self.doc,self.stack,self.active_entity,angle_increment=self.angle_increment);px,py=self.active.pivot;import math;self._rotate_start_angle=math.degrees(math.atan2(y-py,x-px));self.preview=PreviewState('rotate',copy.deepcopy(self.active.preview),{'angle_deg':0.,'pivot_x':px,'pivot_y':py},None,self.active_entity);return self.preview
        return self.preview
    def pointer_move(self,ev):
        x,y=self._plan_xy(ev)
        if isinstance(self.active,WallDrawTransaction):
            hud=self.active.update(x,y);sx,sy=self.active.start;ex,ey=self.active.end;sp=best_snap(self.doc,x,y,self.snap_tolerance,self.grid);self.preview=PreviewState('wall',{'x1':sx,'y1':sy,'x2':ex,'y2':ey,'z':self.active.z},hud.values,self._snap_dict(sp))
        elif isinstance(self.active,ConnectedWallEndpointStretchTransaction):
            hud=self.active.update(x,y);geom=copy.deepcopy(self.active.preview);geom['entities']=copy.deepcopy(self.active.previews);self.preview=PreviewState('stretch',geom,hud.values,None,self.active.eid)
        elif isinstance(self.active,WallEndpointStretchTransaction):hud=self.active.update(x,y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,BoxStretchTransaction):hud=self.active.update(x=x,y=y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,PodStretchTransaction):
            hud=self.active.update(x=x) if self.active.handle in ('left','right') else self.active.update(y=y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,RotateTransaction):hud=self.active.update_pointer(x,y,self._rotate_start_angle,snap=not ev.shift);self.preview=PreviewState('rotate',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
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
            hud=self.active.update_pointer(x,y,snap=False);values=dict(hud.values);values['distance']=(self.active.dx*self.active.dx+self.active.dy*self.active.dy)**.5
            self.preview=PreviewState('move',{'entities':copy.deepcopy(self.active.preview)},values,None)
        return self.preview
    def pointer_up(self,ev,exact=None):
        if self.active is None:return self.preview
        self.pointer_move(ev);committed_id=None
        if isinstance(self.active,WallDrawTransaction):committed_id=self.active.commit((exact or {}).get('length'))
        elif isinstance(self.active,(ConnectedWallEndpointStretchTransaction,WallEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction,OpeningEditTransaction)):self.active.commit();committed_id=getattr(self.active,'eid',None)
        elif isinstance(self.active,OpeningPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,StairPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,RampPlaceTransaction):committed_id=self.active.commit()
        elif isinstance(self.active,MoveTransaction):
            if abs(self.active.dx)>1e-12 or abs(self.active.dy)>1e-12 or abs(self.active.dz)>1e-12:self.active.commit()
        result=self.preview;result.entity_id=committed_id;self.active=None;return result
    def cancel(self):
        if hasattr(self.active,'cancel'):self.active.cancel()
        self.active=None;self.preview=PreviewState()
