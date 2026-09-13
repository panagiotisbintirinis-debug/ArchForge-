from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple, List
import copy
from .model import Document
from .commands import CommandStack, MoveEntities
from .interaction import WallDrawTransaction,WallEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction
from .snapping import best_snap

@dataclass
class PointerEvent:
    a:float;b:float;button:str='left';shift:bool=False;ctrl:bool=False;alt:bool=False
@dataclass
class PreviewState:
    kind:str='none';geometry:Dict[str,Any]=field(default_factory=dict);hud:Dict[str,float]=field(default_factory=dict);snap:Optional[Dict[str,Any]]=None;entity_id:Optional[str]=None

class IncrementalViewportAdapter:
    def __init__(self,doc:Document):self.doc=doc;self.known={}
    def consume(self):
        updates=[];removals=[]
        for eid in sorted(set(self.doc.dirty)):
            if eid in self.doc.entities:
                e=self.doc.entities[eid];updates.append((eid,e.kind,e.revision,copy.deepcopy(e.params),e.visible,e.locked));self.known[eid]=e.revision
            else:removals.append(eid);self.known.pop(eid,None)
        self.doc.dirty.clear();return {'updates':updates,'removals':removals}
    def full_sync(self):
        current=set(self.doc.entities);removals=[eid for eid in self.known if eid not in current];updates=[(eid,e.kind,e.revision,copy.deepcopy(e.params),e.visible,e.locked) for eid,e in self.doc.entities.items()];self.known={eid:e.revision for eid,e in self.doc.entities.items()};self.doc.dirty.clear();return {'updates':updates,'removals':removals}

class PointerController:
    def __init__(self,doc:Document,stack:CommandStack):
        self.doc=doc;self.stack=stack;self.tool='select';self.active=None;self.active_entity=None;self.active_handle=None;self.preview=PreviewState();self.grid=.1;self.snap_tolerance=.15;self.angle_increment=15.;self._move_start=None;self._move_before=None
    def set_tool(self,tool):
        if self.active is not None:self.cancel()
        self.tool=tool;self.preview=PreviewState()
    def set_target(self,entity_id,handle=None):self.active_entity=entity_id;self.active_handle=handle
    def _world(self,ev):return self.doc.work_plane.unproject(ev.a,ev.b)
    def _plan_xy(self,ev):x,y,_=self._world(ev);return x,y
    def pointer_down(self,ev):
        x,y=self._plan_xy(ev)
        if self.tool=='wall':
            sp=best_snap(self.doc,x,y,self.snap_tolerance,self.grid);sx,sy=(sp.x,sp.y) if sp else (x,y);self.active=WallDrawTransaction(self.doc,self.stack,(sx,sy),z=self.doc.work_plane.origin[2],grid=self.grid,snap_tol=self.snap_tolerance);self.preview=PreviewState('wall',{'x1':sx,'y1':sy,'x2':sx,'y2':sy,'z':self.doc.work_plane.origin[2]}, {},self._snap_dict(sp));return self.preview
        if self.tool=='move':
            ids=list(self.doc.selection)
            if not ids:return self.preview
            self._move_start=(x,y);self._move_before={eid:copy.deepcopy(self.doc.get(eid).params) for eid in ids};self.active='move';self.preview=PreviewState('move',{'entities':copy.deepcopy(self._move_before)},{'dx':0.,'dy':0.},None);return self.preview
        if self.tool=='stretch':
            if not self.active_entity or self.active_entity not in self.doc.entities:return self.preview
            e=self.doc.get(self.active_entity)
            if e.kind=='wall':self.active=WallEndpointStretchTransaction(self.doc,self.stack,e.id,1 if self.active_handle in ('1','start','endpoint1') else 2,self.grid,self.snap_tolerance)
            elif e.kind=='box':self.active=BoxStretchTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
            elif e.kind=='pod':self.active=PodStretchTransaction(self.doc,self.stack,e.id,self.active_handle or 'right')
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
        elif isinstance(self.active,WallEndpointStretchTransaction):hud=self.active.update(x,y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,BoxStretchTransaction):hud=self.active.update(x=x,y=y);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,PodStretchTransaction):
            hud=self.active.update(x=x) if self.active.handle in ('left','right') else self.active.update(y=y) if self.active.handle in ('top','bottom') else self.active.update(z=self._world(ev)[2]);self.preview=PreviewState('stretch',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif isinstance(self.active,RotateTransaction):hud=self.active.update_pointer(x,y,self._rotate_start_angle,snap=not ev.shift);self.preview=PreviewState('rotate',copy.deepcopy(self.active.preview),hud.values,None,self.active.eid)
        elif self.active=='move' and self._move_start is not None:
            dx=x-self._move_start[0];dy=y-self._move_start[1];previews={}
            for eid,p0 in self._move_before.items():
                e=self.doc.get(eid);p=copy.deepcopy(p0)
                if e.kind=='box':p.update(x=p0['x']+dx,y=p0['y']+dy)
                elif e.kind=='wall':p.update(x1=p0['x1']+dx,x2=p0['x2']+dx,y1=p0['y1']+dy,y2=p0['y2']+dy)
                elif e.kind=='pod':p.update(cx=p0['cx']+dx,cy=p0['cy']+dy)
                previews[eid]=p
            self.preview=PreviewState('move',{'entities':previews},{'dx':dx,'dy':dy,'distance':(dx*dx+dy*dy)**.5},None)
        return self.preview
    def pointer_up(self,ev,exact=None):
        if self.active is None:return self.preview
        self.pointer_move(ev);committed_id=None
        if isinstance(self.active,WallDrawTransaction):committed_id=self.active.commit((exact or {}).get('length'))
        elif isinstance(self.active,(WallEndpointStretchTransaction,BoxStretchTransaction,PodStretchTransaction,RotateTransaction)):self.active.commit();committed_id=getattr(self.active,'eid',None)
        elif self.active=='move':
            dx=self.preview.hud.get('dx',0.);dy=self.preview.hud.get('dy',0.)
            if abs(dx)>1e-12 or abs(dy)>1e-12:self.stack.execute(MoveEntities(list(self.doc.selection),dx,dy,0.))
        result=self.preview;result.entity_id=committed_id;self.active=None;self._move_start=None;self._move_before=None;return result
    def cancel(self):
        if hasattr(self.active,'cancel'):self.active.cancel()
        self.active=None;self._move_start=None;self._move_before=None;self.preview=PreviewState()
    @staticmethod
    def _snap_dict(sp):return None if sp is None else {'x':sp.x,'y':sp.y,'z':sp.z,'kind':sp.kind,'entity_id':sp.entity_id}
