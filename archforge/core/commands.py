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
    """Apply several semantic parameter updates as one undo/redo step.

    If validation of any member fails, already-applied members are restored so callers
    never observe a partially moved wall junction.
    """
    changes:Dict[str,Dict[str,Any]]
    before:Dict[str,Dict[str,Any]]|None=None
    before_revisions:Dict[str,int]|None=None
    def do(self,doc):
        if self.before is None:
            self.before={eid:copy.deepcopy(doc.get(eid).params) for eid in self.changes}
            self.before_revisions={eid:doc.get(eid).revision for eid in self.changes}
        touched=[]
        try:
            for eid,delta in self.changes.items():
                doc.update(eid,delta);touched.append(eid)
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
    def do(self,doc):
        if self.before is None:self.before={i:copy.deepcopy(doc.get(i).params) for i in self.ids}
        for i in self.ids:
            e=doc.get(i); p=e.params
            if e.kind=='box':doc.update(i,{'x':p['x']+self.dx,'y':p['y']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='wall':doc.update(i,{'x1':p['x1']+self.dx,'x2':p['x2']+self.dx,'y1':p['y1']+self.dy,'y2':p['y2']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='pod':doc.update(i,{'cx':p['cx']+self.dx,'cy':p['cy']+self.dy,'floor_level':p['floor_level']+self.dz})
            elif e.kind in ('floor','room'):
                doc.update(i,{'points':[(x+self.dx,y+self.dy) for x,y in p['points']], 'z':p['z']+self.dz})
    def undo(self,doc):
        for i,p in self.before.items():
            e=doc.get(i);e.params=copy.deepcopy(p);e.revision+=1;doc.mark_dirty(i)

class CommandStack:
    def __init__(self,doc):self.doc=doc;self.done=[];self.undone=[]
    def execute(self,c):c.do(self.doc);self.done.append(c);self.undone.clear()
    def undo(self):
        if not self.done:return
        c=self.done.pop();c.undo(self.doc);self.undone.append(c)
    def redo(self):
        if not self.undone:return
        c=self.undone.pop();c.do(self.doc);self.done.append(c)
