from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any, Set
import copy, json, math, uuid

Vec3 = Tuple[float,float,float]

def _finite(v: float)->float:
    v=float(v)
    if not math.isfinite(v): raise ValueError('value must be finite')
    return v

def _positive(v: float)->float:
    v=_finite(v)
    if v <= 0: raise ValueError('dimension must be > 0')
    return v

def _room_signature(v)->str:
    v=str(v)
    if not v.startswith('room-') or len(v)<8:raise ValueError('invalid room signature')
    return v

def _polygon(v):
    from archforge.architecture.floors import validate_polygon
    return validate_polygon(v)

@dataclass
class WorkPlane:
    name: str = 'XY'
    origin: Vec3 = (0.0,0.0,0.0)
    u: Vec3 = (1.0,0.0,0.0)
    v: Vec3 = (0.0,1.0,0.0)
    def normal(self)->Vec3:
        ux,uy,uz=self.u;vx,vy,vz=self.v
        return (uy*vz-uz*vy, uz*vx-ux*vz, ux*vy-uy*vx)
    def world_delta(self, da:float, db:float)->Vec3:
        return tuple(da*self.u[i]+db*self.v[i] for i in range(3))
    def project(self, p: Vec3)->Tuple[float,float]:
        d=tuple(p[i]-self.origin[i] for i in range(3))
        return (sum(d[i]*self.u[i] for i in range(3)), sum(d[i]*self.v[i] for i in range(3)))
    def unproject(self, a: float,b: float)->Vec3:
        return tuple(self.origin[i]+a*self.u[i]+b*self.v[i] for i in range(3))

@dataclass
class Entity:
    kind: str
    params: Dict[str, Any]
    name: str = ''
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_id: Optional[str] = None
    locked: bool = False
    visible: bool = True
    revision: int = 0
    def clone(self): return copy.deepcopy(self)

SCHEMAS={
 'box': {'x':_finite,'y':_finite,'z':_finite,'width':_positive,'depth':_positive,'height':_positive,'rotation':_finite},
 'wall': {'x1':_finite,'y1':_finite,'z':_finite,'x2':_finite,'y2':_finite,'height':_positive,'thickness':_positive},
 'pod': {'cx':_finite,'cy':_finite,'floor_level':_finite,'diameter_x':_positive,'diameter_y':_positive,'height':_positive,'shell_thickness':_positive,'rotation':_finite},
 'floor': {'points':_polygon,'z':_finite,'thickness':_positive},
 'room': {'points':_polygon,'z':_finite,'height':_positive},
 'room_floor': {'room_signature':_room_signature,'thickness':_positive,'offset_z':_finite},
 'door': {'offset':_finite,'width':_positive,'height':_positive,'sill':_finite},
 'window': {'offset':_finite,'width':_positive,'height':_positive,'sill':_finite},
}

def validate_params(kind:str, params:Dict[str,Any])->Dict[str,Any]:
    out=copy.deepcopy(params)
    schema=SCHEMAS.get(kind,{})
    for k,fn in schema.items():
        if k in out: out[k]=fn(out[k])
    return out

class Document:
    def __init__(self):
        self.entities: Dict[str,Entity]={}
        self.children: Dict[str,List[str]]={}
        self.dependencies: Dict[str,Set[str]]={}
        self.selection: List[str]=[]
        self.dirty: Set[str]=set()
        self.levels={'Ground':0.0}
        self.work_plane=WorkPlane()
        self.materials={}
        self.constructions={}
        self.room_data: Dict[str,Dict[str,Any]]={}
    def add(self,e:Entity)->str:
        if e.id in self.entities: raise ValueError('duplicate id')
        e.params=validate_params(e.kind,e.params)
        if e.kind in ('door','window'):
            if not e.parent_id or e.parent_id not in self.entities or self.entities[e.parent_id].kind != 'wall':
                raise ValueError('door/window must be attached to an existing wall')
            from archforge.architecture.openings import validate_opening
            validate_opening(self.entities[e.parent_id].params,e.params,e.kind)
        self.entities[e.id]=e
        if e.parent_id:
            self.children.setdefault(e.parent_id,[]).append(e.id)
            if e.kind in ('door','window'):
                self.add_dependency(e.parent_id,e.id)
        self.mark_dirty(e.id)
        return e.id
    def get(self,eid:str)->Entity: return self.entities[eid]
    def update(self,eid:str,changes:Dict[str,Any]):
        e=self.get(eid)
        if e.locked: raise PermissionError('entity is locked')
        p=e.params.copy(); p.update(changes); p=validate_params(e.kind,p)
        if e.kind in ('door','window'):
            from archforge.architecture.openings import validate_opening
            validate_opening(self.get(e.parent_id).params,p,e.kind)
        elif e.kind=='wall':
            from archforge.architecture.openings import validate_opening
            for cid in self.children.get(eid,()):
                child=self.entities.get(cid)
                if child and child.kind in ('door','window'):
                    validate_opening(p,child.params,child.kind)
        e.params=p; e.revision+=1; self.mark_dirty(eid)
    def set_room_metadata(self,signature:str,**changes):
        if not isinstance(signature,str) or not signature.startswith('room-'):
            raise ValueError('invalid room signature')
        allowed={'name','use','floor_finish','ceiling_finish','notes'}
        unknown=set(changes)-allowed
        if unknown:raise ValueError('unsupported room metadata: '+', '.join(sorted(unknown)))
        data=copy.deepcopy(self.room_data.get(signature,{}))
        for key,value in changes.items():
            if value is None:data.pop(key,None)
            else:data[key]=str(value)
        if data:self.room_data[signature]=data
        else:self.room_data.pop(signature,None)
    def room_metadata(self,signature:str)->Dict[str,Any]:
        return copy.deepcopy(self.room_data.get(signature,{}))
    def active_room_faces(self,z:Optional[float]=None,tolerance:float=1e-5):
        from archforge.architecture.topology import room_faces
        if z is None:z=self.work_plane.origin[2]
        return room_faces(self,tolerance=tolerance,z=z)
    def mark_dirty(self,eid:str):
        stack=[eid]; seen=set()
        while stack:
            a=stack.pop()
            if a in seen: continue
            seen.add(a); self.dirty.add(a)
            stack.extend(self.dependencies.get(a,()))
    def add_dependency(self,source:str,dependent:str):
        if source==dependent: raise ValueError('self dependency')
        self.dependencies.setdefault(source,set()).add(dependent)
        if self._reachable(dependent,source):
            self.dependencies[source].remove(dependent); raise ValueError('dependency cycle')
    def _reachable(self,a,b):
        stack=[a]; seen=set()
        while stack:
            x=stack.pop()
            if x==b:return True
            if x in seen:continue
            seen.add(x);stack.extend(self.dependencies.get(x,()))
        return False
    def remove(self,eid:str)->Dict[str,Entity]:
        ids=[]
        def walk(x):
            for c in list(self.children.get(x,())): walk(c)
            ids.append(x)
        walk(eid)
        snap={i:self.entities[i].clone() for i in ids}
        for i in ids:
            self.entities.pop(i,None); self.children.pop(i,None); self.dependencies.pop(i,None)
            for s in self.dependencies.values(): s.discard(i)
            self.selection=[x for x in self.selection if x!=i]
            self.dirty.add(i)
        for kids in self.children.values(): kids[:]=[x for x in kids if x not in ids]
        return snap
    def select(self,ids:List[str],add=False):
        valid=[i for i in ids if i in self.entities]
        if add:
            for i in valid:
                if i not in self.selection:self.selection.append(i)
        else:self.selection=valid
    def to_dict(self):
        return {'format':5,'entities':[asdict(e) for e in self.entities.values()],
                'dependencies':{k:sorted(v) for k,v in self.dependencies.items()},
                'levels':self.levels,'work_plane':asdict(self.work_plane),'materials':self.materials,
                'constructions':self.constructions,'room_data':copy.deepcopy(self.room_data)}
    @classmethod
    def from_dict(cls,d):
        doc=cls(); doc.levels=d.get('levels',{'Ground':0.0}); wp=d.get('work_plane')
        if wp: doc.work_plane=WorkPlane(name=wp.get('name','XY'), origin=tuple(wp.get('origin',(0,0,0))), u=tuple(wp.get('u',(1,0,0))), v=tuple(wp.get('v',(0,1,0))))
        doc.materials=d.get('materials',{});doc.constructions=d.get('constructions',{})
        doc.room_data=copy.deepcopy(d.get('room_data',{}))
        raw_entities=list(d.get('entities',[]))
        deferred=[]
        for raw in raw_entities:
            if raw.get('kind') in ('door','window'): deferred.append(raw)
            else: doc.add(Entity(**raw))
        for raw in deferred: doc.add(Entity(**raw))
        for source,dependents in d.get('dependencies',{}).items():
            for dependent in dependents:
                if source in doc.entities and dependent in doc.entities and dependent not in doc.dependencies.get(source,set()):
                    doc.add_dependency(source,dependent)
        doc.dirty.clear(); return doc
    def save(self,path):
        with open(path,'w',encoding='utf8') as f: json.dump(self.to_dict(),f,indent=2)
    @classmethod
    def load(cls,path):
        with open(path,encoding='utf8') as f:return cls.from_dict(json.load(f))
