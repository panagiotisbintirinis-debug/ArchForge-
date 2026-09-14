from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import copy
from .model import Document, Entity, WorkPlane

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


def _legacy_world_modifier(mod):
    """True only for pre-parametric modifier state that still needs command-time translation."""
    region=mod.target.subregion or {}
    return (
        mod.params.get('mode')!='mechanism_clearance'
        and 'uv_center' not in region
        and 'world_center' in region
        and isinstance(region.get('world_center'),(list,tuple))
        and len(region['world_center'])==3
    )

@dataclass
class MoveEntities(Command):
    ids:List[str]; dx:float;dy:float;dz:float=0.0;before:Dict[str,Dict[str,Any]]|None=None;before_modifiers:Dict[str,Any]|None=None
    def do(self,doc):
        if self.before is None:
            self.before={i:copy.deepcopy(doc.get(i).params) for i in self.ids}
            self.before_modifiers={mid:copy.deepcopy(m) for mid,m in doc.surface_modifiers.items() if m.target.owner_id in self.ids and _legacy_world_modifier(m)}
        for i in self.ids:
            e=doc.get(i); p=e.params
            if e.kind in ('box','mechanical_part'):doc.update(i,{'x':p['x']+self.dx,'y':p['y']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='wall':doc.update(i,{'x1':p['x1']+self.dx,'x2':p['x2']+self.dx,'y1':p['y1']+self.dy,'y2':p['y2']+self.dy,'z':p['z']+self.dz})
            elif e.kind=='pod':doc.update(i,{'cx':p['cx']+self.dx,'cy':p['cy']+self.dy,'floor_level':p['floor_level']+self.dz})
            elif e.kind in ('floor','room'):
                doc.update(i,{'points':[(x+self.dx,y+self.dy) for x,y in p['points']], 'z':p['z']+self.dz})
        # Compatibility only: modern UV/local attachments are immutable semantic intent.
        # Old project files may still contain world-only sculpt centers, so translate those
        # until they can be migrated to an intrinsic surface frame.
        for mid,m in doc.surface_modifiers.items():
            if m.target.owner_id not in self.ids or not _legacy_world_modifier(m):continue
            c=m.target.subregion['world_center']
            m.target.subregion['world_center']=[c[0]+self.dx,c[1]+self.dy,c[2]+self.dz]
            doc.mark_dirty(m.target.owner_id)
    def undo(self,doc):
        for i,p in self.before.items():
            e=doc.get(i);e.params=copy.deepcopy(p);e.revision+=1;doc.mark_dirty(i)
        if self.before_modifiers:
            for mid,m in self.before_modifiers.items():
                doc.surface_modifiers[mid]=copy.deepcopy(m);doc.mark_dirty(m.target.owner_id)

class CreateRoomFloors(Command):
    """Create one topology-linked floor per persistent semantic room as one undo step."""
    def __init__(self,signatures:List[str],thickness:float=.15,offset_z:float=0.0):
        self.signatures=list(dict.fromkeys(signatures));self.thickness=float(thickness);self.offset_z=float(offset_z);self.entities:Dict[str,Entity]={}
    def do(self,doc):
        from archforge.architecture.rooms import find_room_face
        from archforge.architecture.room_identity import room_id_for_signature
        created=[]
        try:
            for sig in self.signatures:
                found=find_room_face(doc,sig)
                if found is None:raise ValueError('room signature is not currently active')
                face,z=found;room_id=room_id_for_signature(doc,sig,z=z)
                if any(e.kind=='room_floor' and (e.params.get('room_id')==room_id or e.params.get('room_signature')==sig) for e in doc.entities.values()):continue
                key=room_id or sig;e=self.entities.get(key)
                if e is None:
                    params={'room_signature':sig,'thickness':self.thickness,'offset_z':self.offset_z}
                    if room_id is not None:params['room_id']=room_id
                    e=Entity('room_floor',params,name='Auto Floor');self.entities[key]=e
                else:
                    e=e.clone();e.params['room_signature']=sig
                    if room_id is not None:e.params['room_id']=room_id
                doc.add(e);created.append(e.id)
                for wid in face.wall_ids:
                    if wid in doc.entities and e.id not in doc.dependencies.get(wid,set()):doc.add_dependency(wid,e.id)
        except Exception:
            for eid in reversed(created):
                if eid in doc.entities:doc.remove(eid)
            raise
    def undo(self,doc):
        for e in self.entities.values():
            if e.id in doc.entities:doc.remove(e.id)

@dataclass
class SetWorkPlane(Command):
    work_plane: WorkPlane
    before: Optional[WorkPlane] = None
    def do(self, doc: Document):
        if self.before is None:
            self.before = copy.deepcopy(doc.work_plane)
        doc.work_plane = copy.deepcopy(self.work_plane)
    def undo(self, doc: Document):
        if self.before is not None:
            doc.work_plane = copy.deepcopy(self.before)

@dataclass
class SetLevel(Command):
    name: str
    elevation: float
    before: Optional[float] = None
    had_before: bool = False
    def do(self, doc: Document):
        if not self.had_before and self.name in doc.levels:
            self.before = doc.levels[self.name]
            self.had_before = True
        doc.levels[self.name] = float(self.elevation)
    def undo(self, doc: Document):
        if self.had_before:
            doc.levels[self.name] = self.before
        else:
            doc.levels.pop(self.name, None)

@dataclass
class RemoveLevel(Command):
    name: str
    before: Optional[float] = None
    def do(self, doc: Document):
        if self.name not in doc.levels:
            raise KeyError(f"level '{self.name}' does not exist")
        self.before = doc.levels.pop(self.name)
    def undo(self, doc: Document):
        if self.before is not None:
            doc.levels[self.name] = self.before

@dataclass
class SetMaterial(Command):
    material_id: str
    properties: Dict[str, Any]
    before: Optional[Dict[str, Any]] = None
    had_before: bool = False
    def do(self, doc: Document):
        if not self.had_before and self.material_id in doc.materials:
            self.before = copy.deepcopy(doc.materials[self.material_id])
            self.had_before = True
        doc.materials[self.material_id] = copy.deepcopy(self.properties)
    def undo(self, doc: Document):
        if self.had_before:
            doc.materials[self.material_id] = copy.deepcopy(self.before)
        else:
            doc.materials.pop(self.material_id, None)

@dataclass
class SetConstruction(Command):
    construction_id: str
    properties: Dict[str, Any]
    before: Optional[Dict[str, Any]] = None
    had_before: bool = False
    def do(self, doc: Document):
        if not self.had_before and self.construction_id in doc.constructions:
            self.before = copy.deepcopy(doc.constructions[self.construction_id])
            self.had_before = True
        doc.constructions[self.construction_id] = copy.deepcopy(self.properties)
    def undo(self, doc: Document):
        if self.had_before:
            doc.constructions[self.construction_id] = copy.deepcopy(self.before)
        else:
            doc.constructions.pop(self.construction_id, None)

@dataclass
class AssignConstruction(Command):
    eid: str
    construction_id: Optional[str] = None
    material_id: Optional[str] = None
    before_construction: Optional[str] = None
    before_material: Optional[str] = None
    had_before: bool = False
    def do(self, doc: Document):
        e = doc.get(self.eid)
        if not self.had_before:
            self.before_construction = e.params.get('construction_id')
            self.before_material = e.params.get('material_id')
            self.had_before = True
        changes = {}
        if self.construction_id is not None:
            changes['construction_id'] = self.construction_id
        if self.material_id is not None:
            changes['material_id'] = self.material_id
        doc.update(self.eid, changes)
    def undo(self, doc: Document):
        changes = {}
        if self.construction_id is not None:
            if self.before_construction is not None:
                changes['construction_id'] = self.before_construction
            else:
                doc.get(self.eid).params.pop('construction_id', None)
        if self.material_id is not None:
            if self.before_material is not None:
                changes['material_id'] = self.before_material
            else:
                doc.get(self.eid).params.pop('material_id', None)
        if changes:
            doc.update(self.eid, changes)
        else:
            doc.mark_dirty(self.eid)

class CommandStack:
    def __init__(self,doc):self.doc=doc;self.done=[];self.undone=[]
    def execute(self,c):c.do(self.doc);self.done.append(c);self.undone.clear()
    def undo(self):
        if not self.done:return
        c=self.done.pop();c.undo(self.doc);self.undone.append(c)
    def redo(self):
        if not self.undone:return
        c=self.undone.pop();c.do(self.doc);self.done.append(c)
