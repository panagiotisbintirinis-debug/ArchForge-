from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List
import copy
from .model import Document, Entity

class Command:
    def do(self,doc:Document): raise NotImplementedError
    def undo(self,doc:Document): raise NotImplementedError

@dataclass
class AddEntity(Command):
    entity: Entity
    def do(self,doc): doc.add(self.entity.clone())
    def undo(self,doc): doc.remove(self.entity.id)

@dataclass
class UpdateEntity(Command):
    eid:str; changes:Dict[str,Any]; before:Dict[str,Any]|None=None
    def do(self,doc):
        if self.before is None:self.before=copy.deepcopy(doc.get(self.eid).params)
        doc.update(self.eid,self.changes)
    def undo(self,doc):
        e=doc.get(self.eid); e.params=copy.deepcopy(self.before);e.revision+=1;doc.mark_dirty(self.eid)

@dataclass
class UpdateEntities(Command):
    """Apply several semantic parameter updates as one undo/redo step."""
    changes:Dict[str,Dict[str,Any]]
    before:Dict[str,Dict[str,Any]]|None=None
    before_revisions:Dict[str,int]|None=None
    def do(self,doc):
        if self.before is None:
            self.before={eid:copy.deepcopy(doc.get(eid).params) for eid in self.changes}
            self.before_revisions={eid:doc.get(eid).revision for eid in self.changes}
        touched=[]
        try:
            for eid,delta in self.changes.items():doc.update(eid,delta);touched.append(eid)
        except Exception:
            for eid in touched:
                e=doc.get(eid);e.params=copy.deepcopy(self.before[eid]);e.revision=self.before_revisions[eid];doc.mark_dirty(eid)
            raise
    def undo(self,doc):
        for eid,p in self.before.items():
            e=doc.get(eid);e.params=copy.deepcopy(p);e.revision+=1;doc.mark_dirty(eid)

@dataclass
class MoveEntities(Command):
    ids:List[str]; dx:float;dy:float;dz:float=0.0;before:Dict[str,Dict[str,Any]]|None=None
    before_modifiers:Dict[str,Any]|None=None
    def do(self,doc):
        if self.before is None:
            self.before={i:copy.deepcopy(doc.get(i).params) for i in self.ids}
            self.before_modifiers={
                mid:copy.deepcopy(m)
                for mid,m in doc.surface_modifiers.items()
                if m.target.owner_id in self.ids
            }
        for i in self.ids:
            e=doc.get(i); p=e.params
            if e.kind in ('box','mechanical_part'):doc.update(i,{'x':p['x']+self.dx,'y':p['y']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='wall':doc.update(i,{'x1':p['x1']+self.dx,'x2':p['x2']+self.dx,'y1':p['y1']+self.dy,'y2':p['y2']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='pod':doc.update(i,{'cx':p['cx']+self.dx,'cy':p['cy']+self.dy,'floor_level':p['floor_level']+self.dz})
            elif e.kind in ('floor','room'):
                doc.update(i,{'points':[(x+self.dx,y+self.dy) for x,y in p['points']], 'z':p['z']+self.dz})
        for mid,m in doc.surface_modifiers.items():
            if m.target.owner_id in self.ids:
                sub=m.target.subregion
                if 'world_center' in sub and isinstance(sub['world_center'],(list,tuple)) and len(sub['world_center'])==3:
                    c=sub['world_center']
                    sub['world_center']=[c[0]+self.dx,c[1]+self.dy,c[2]+self.dz]
                if 'envelope_min' in sub and len(sub['envelope_min'])==3:
                    lo=sub['envelope_min']
                    sub['envelope_min']=[lo[0]+self.dx,lo[1]+self.dy,lo[2]+self.dz]
                if 'envelope_max' in sub and len(sub['envelope_max'])==3:
                    hi=sub['envelope_max']
                    sub['envelope_max']=[hi[0]+self.dx,hi[1]+self.dy,hi[2]+self.dz]
                doc.mark_dirty(m.target.owner_id)
    def undo(self,doc):
        for i,p in self.before.items():
            e=doc.get(i);e.params=copy.deepcopy(p);e.revision+=1;doc.mark_dirty(i)
        if self.before_modifiers:
            for mid,m in self.before_modifiers.items():
                doc.surface_modifiers[mid]=copy.deepcopy(m)
                doc.mark_dirty(m.target.owner_id)

class CreateRoomFloors(Command):
    """Create one topology-linked floor per active room as a single undo step."""
    def __init__(self,signatures:List[str],thickness:float=.15,offset_z:float=0.0):
        self.signatures=list(dict.fromkeys(signatures));self.thickness=float(thickness);self.offset_z=float(offset_z);self.entities:Dict[str,Entity]={}
    def do(self,doc):
        from archforge.architecture.rooms import find_room_face
        existing={e.params.get('room_signature') for e in doc.entities.values() if e.kind=='room_floor'}
        created=[]
        try:
            for sig in self.signatures:
                if sig in existing:continue
                found=find_room_face(doc,sig)
                if found is None:raise ValueError('room signature is not currently active')
                face,_=found
                e=self.entities.get(sig)
                if e is None:
                    e=Entity('room_floor',{'room_signature':sig,'thickness':self.thickness,'offset_z':self.offset_z},name='Auto Floor')
                    self.entities[sig]=e
                doc.add(e.clone());created.append(e.id)
                for wid in face.wall_ids:
                    if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):doc.add_dependency(wid,e.id)
        except Exception:
            for eid in reversed(created):
                if eid in doc.entities:doc.remove(eid)
            raise
    def undo(self,doc):
        for e in self.entities.values():
            if e.id in doc.entities:doc.remove(e.id)

class CommandStack:
    def __init__(self,doc):self.doc=doc;self.done=[];self.undone=[]
    def execute(self,c):c.do(self.doc);self.done.append(c);self.undone.clear()
    def undo(self):
        if not self.done:return
        c=self.done.pop();c.undo(self.doc);self.undone.append(c)
    def redo(self):
        if not self.undone:return
        c=self.undone.pop();c.do(self.doc);self.done.append(c)
