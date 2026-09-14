from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional, Any, Set
import copy, json, math, uuid

Vec3=Tuple[float,float,float]
def _finite(v):
 v=float(v)
 if not math.isfinite(v):raise ValueError('value must be finite')
 return v
def _positive(v):
 v=_finite(v)
 if v<=0:raise ValueError('dimension must be > 0')
 return v
def _nonnegative(v):
 v=_finite(v)
 if v<0:raise ValueError('value must be >= 0')
 return v
def _nonempty(v):
 v=str(v)
 if not v:raise ValueError('value must be a non-empty string')
 return v
def _vec3(v):
 if not isinstance(v,(list,tuple)) or len(v)!=3:raise ValueError('value must be a 3-vector')
 return [_finite(x) for x in v]
def _room_signature(v):
 v=str(v)
 if not v.startswith('room-') or len(v)<8:raise ValueError('invalid room signature')
 return v
def _polygon(v):
 from archforge.architecture.floors import validate_polygon
 return validate_polygon(v)
@dataclass
class WorkPlane:
 name:str='XY';origin:Vec3=(0.,0.,0.);u:Vec3=(1.,0.,0.);v:Vec3=(0.,1.,0.)
 def normal(self):
  ux,uy,uz=self.u;vx,vy,vz=self.v;return(uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx)
 def world_delta(self,da,db):return tuple(da*self.u[i]+db*self.v[i] for i in range(3))
 def project(self,p):
  d=tuple(p[i]-self.origin[i] for i in range(3));return(sum(d[i]*self.u[i] for i in range(3)),sum(d[i]*self.v[i] for i in range(3)))
 def unproject(self,a,b):return tuple(self.origin[i]+a*self.u[i]+b*self.v[i] for i in range(3))
@dataclass
class Entity:
 kind:str;params:Dict[str,Any];name:str='';id:str=field(default_factory=lambda:str(uuid.uuid4()));parent_id:Optional[str]=None;locked:bool=False;visible:bool=True;revision:int=0
 def clone(self):return copy.deepcopy(self)
_ROOM_SLAB={'room_signature':_room_signature,'thickness':_positive,'offset_z':_finite}
_OPENING={'offset':_finite,'surface_u':_finite,'width':_positive,'height':_positive,'sill':_finite,'flat_margin':_nonnegative}
SCHEMAS={
 'box':{'x':_finite,'y':_finite,'z':_finite,'width':_positive,'depth':_positive,'height':_positive,'rotation':_finite},
 'wall':{'x1':_finite,'y1':_finite,'z':_finite,'x2':_finite,'y2':_finite,'height':_positive,'thickness':_positive},
 'pod':{'cx':_finite,'cy':_finite,'floor_level':_finite,'diameter_x':_positive,'diameter_y':_positive,'height':_positive,'shell_thickness':_positive,'rotation':_finite},
 'floor':{'points':_polygon,'z':_finite,'thickness':_positive},'room':{'points':_polygon,'z':_finite,'height':_positive},'room_floor':_ROOM_SLAB,
 'room_ceiling':_ROOM_SLAB,'room_foundation':_ROOM_SLAB,'room_roof':{**_ROOM_SLAB,'roof_type':_nonempty},
 'door':_OPENING,'window':_OPENING,
 'organic_opening_patch':{'opening_id':_nonempty,'host_id':_nonempty,'status':_nonempty},
 'mechanical_part':{'x':_finite,'y':_finite,'z':_finite,'width':_positive,'depth':_positive,'height':_positive,'rotation':_finite},
 'mechanical_joint':{'joint_type':_nonempty,'parent_part':_nonempty,'child_part':_nonempty,'anchor':_vec3,'axis':_vec3,'min_value':_finite,'max_value':_finite,'value':_finite},
 'mechanical_mount':{'host_id':_nonempty,'part_id':_nonempty,'surface_role':_nonempty,'clearance':_nonnegative,'embed_depth':_nonnegative}}
def validate_params(kind,params):
 out=copy.deepcopy(params)
 for k,fn in SCHEMAS.get(kind,{}).items():
  if k in out:out[k]=fn(out[k])
 return out
class Document:
 def __init__(self):
  self.entities={};self.children={};self.dependencies={};self.selection=[];self.dirty=set();self.levels={'Ground':0.0};self.work_plane=WorkPlane();self.materials={};self.constructions={};self.room_data={};self.room_bindings={};self.surface_modifiers={}
 def _validate_links(self,e):
  if e.kind in ('door','window'):
   if not e.parent_id or e.parent_id not in self.entities:raise ValueError('door/window must be attached to an existing wall or pod')
   host=self.entities[e.parent_id]
   if host.kind=='wall':
    from archforge.architecture.openings import validate_opening;validate_opening(host.params,e.params,e.kind)
   elif host.kind=='pod':
    from archforge.architecture.openings import validate_pod_opening;validate_pod_opening(host.params,e.params,e.kind)
   else:raise ValueError('door/window host must be a wall or pod')
  elif e.kind=='mechanical_joint':
   from archforge.kinematics.model import validate_joint;validate_joint(self,e)
  elif e.kind=='mechanical_mount':
   from archforge.kinematics.model import validate_mount;validate_mount(self,e)
 def _register_links(self,e):
  if e.parent_id:self.children.setdefault(e.parent_id,[]).append(e.id)
  if e.parent_id and e.kind in ('door','window'):self.add_dependency(e.parent_id,e.id)
  if e.kind=='mechanical_joint':self.add_dependency(e.params['parent_part'],e.id);self.add_dependency(e.params['child_part'],e.id)
  elif e.kind=='mechanical_mount':self.add_dependency(e.params['host_id'],e.id);self.add_dependency(e.params['part_id'],e.id)
 def add(self,e):
  if e.id in self.entities:raise ValueError('duplicate id')
  e.params=validate_params(e.kind,e.params);self._validate_links(e);self.entities[e.id]=e
  try:self._register_links(e)
  except Exception:
   self.entities.pop(e.id,None);raise
  self.mark_dirty(e.id);return e.id
 def get(self,eid):return self.entities[eid]
 def update(self,eid,changes):
  e=self.get(eid)
  if e.locked:raise PermissionError('entity is locked')
  p=e.params.copy();p.update(changes);p=validate_params(e.kind,p);candidate=e.clone();candidate.params=p
  if e.kind in ('door','window','mechanical_joint','mechanical_mount'):self._validate_links(candidate)
  elif e.kind=='wall':
   from archforge.architecture.openings import validate_opening
   for cid in self.children.get(eid,()):
    child=self.entities.get(cid)
    if child and child.kind in ('door','window'):validate_opening(p,child.params,child.kind)
  elif e.kind=='pod':
   from archforge.architecture.openings import validate_pod_opening
   for cid in self.children.get(eid,()):
    child=self.entities.get(cid)
    if child and child.kind in ('door','window'):validate_pod_opening(p,child.params,child.kind)
  if e.kind=='mechanical_joint' and (p['parent_part']!=e.params['parent_part'] or p['child_part']!=e.params['child_part']):raise ValueError('joint part references require explicit relink')
  if e.kind=='mechanical_mount' and (p['host_id']!=e.params['host_id'] or p['part_id']!=e.params['part_id']):raise ValueError('mount references require explicit relink')
  e.params=p;e.revision+=1;self.mark_dirty(eid)
 def set_room_metadata(self,signature,**changes):
  from archforge.architecture.room_identity import resolve_room_metadata_key
  key=resolve_room_metadata_key(self,signature);allowed={'name','use','floor_finish','ceiling_finish','notes'};data=copy.deepcopy(self.room_data.get(key,{}))
  if set(changes)-allowed:raise ValueError('unsupported room metadata')
  for k,v in changes.items():
   if v is None:data.pop(k,None)
   else:data[k]=str(v)
  if data:self.room_data[key]=data
  else:self.room_data.pop(key,None)
 def room_metadata(self,signature):
  from archforge.architecture.room_identity import resolve_room_metadata_key
  key=resolve_room_metadata_key(self,signature);return copy.deepcopy(self.room_data.get(key,self.room_data.get(signature,{})))
 def active_room_faces(self,z=None,tolerance=1e-5):
  from archforge.architecture.room_identity import reconcile_room_bindings
  return [face for face,_ in reconcile_room_bindings(self,z=self.work_plane.origin[2] if z is None else z,tolerance=tolerance)]
 def add_surface_modifier(self,m):
  from .modifiers import add_modifier;return add_modifier(self,m)
 def update_surface_modifier(self,mid,**changes):
  from .modifiers import update_modifier;return update_modifier(self,mid,**changes)
 def remove_surface_modifier(self,mid):
  from .modifiers import remove_modifier;return remove_modifier(self,mid)
 def mark_dirty(self,eid):
  stack=[eid];seen=set()
  while stack:
   a=stack.pop()
   if a in seen:continue
   seen.add(a);self.dirty.add(a);stack.extend(self.dependencies.get(a,()))
 def add_dependency(self,source,dependent):
  if source==dependent:raise ValueError('self dependency')
  self.dependencies.setdefault(source,set()).add(dependent)
  if self._reachable(dependent,source):self.dependencies[source].remove(dependent);raise ValueError('dependency cycle')
 def _reachable(self,a,b):
  stack=[a];seen=set()
  while stack:
   x=stack.pop()
   if x==b:return True
   if x in seen:continue
   seen.add(x);stack.extend(self.dependencies.get(x,()))
  return False
 def remove(self,eid):
  ids=[]
  def walk(x):
   for c in list(self.children.get(x,())):walk(c)
   if x not in ids:ids.append(x)
  walk(eid);changed=True
  while changed:
   changed=False
   for rid,e in list(self.entities.items()):
    if rid in ids:continue
    refs=[]
    if e.kind=='mechanical_joint':refs=[e.params.get('parent_part'),e.params.get('child_part')]
    elif e.kind=='mechanical_mount':refs=[e.params.get('host_id'),e.params.get('part_id')]
    if any(r in ids for r in refs):ids.append(rid);changed=True
  snap={i:self.entities[i].clone() for i in ids}
  for i in ids:
   self.entities.pop(i,None);self.children.pop(i,None);self.dependencies.pop(i,None)
   for s in self.dependencies.values():s.discard(i)
   self.selection=[x for x in self.selection if x!=i];self.dirty.add(i)
  for kids in self.children.values():kids[:]=[x for x in kids if x not in ids]
  for mid,m in list(self.surface_modifiers.items()):
   if m.target.owner_id in ids:self.surface_modifiers.pop(mid,None)
  return snap
 def select(self,ids,add=False):
  valid=[i for i in ids if i in self.entities]
  if add:
   for i in valid:
    if i not in self.selection:self.selection.append(i)
  else:self.selection=valid
 def to_dict(self):
  from .modifiers import modifier_to_dict
  return {'format':7,'entities':[asdict(e) for e in self.entities.values()],'dependencies':{k:sorted(v) for k,v in self.dependencies.items()},'levels':self.levels,'work_plane':asdict(self.work_plane),'materials':self.materials,'constructions':self.constructions,'room_data':copy.deepcopy(self.room_data),'room_bindings':copy.deepcopy(self.room_bindings),'surface_modifiers':[modifier_to_dict(m) for m in self.surface_modifiers.values()]}
 @classmethod
 def from_dict(cls,d):
  doc=cls();doc.levels=d.get('levels',{'Ground':0.0});wp=d.get('work_plane')
  if wp:doc.work_plane=WorkPlane(name=wp.get('name','XY'),origin=tuple(wp.get('origin',(0,0,0))),u=tuple(wp.get('u',(1,0,0))),v=tuple(wp.get('v',(0,1,0))))
  doc.materials=d.get('materials',{});doc.constructions=d.get('constructions',{});doc.room_data=copy.deepcopy(d.get('room_data',{}));doc.room_bindings=copy.deepcopy(d.get('room_bindings',{}));deferred=[]
  for raw in d.get('entities',[]):
   if raw.get('kind') in ('door','window','organic_opening_patch','mechanical_joint','mechanical_mount'):deferred.append(raw)
   else:doc.add(Entity(**raw))
  # Openings must load before their derived organic patch children.
  for raw in [r for r in deferred if r.get('kind') in ('door','window')]:doc.add(Entity(**raw))
  for raw in [r for r in deferred if r.get('kind') not in ('door','window')]:doc.add(Entity(**raw))
  for source,deps in d.get('dependencies',{}).items():
   for dep in deps:
    if source in doc.entities and dep in doc.entities and dep not in doc.dependencies.get(source,set()):doc.add_dependency(source,dep)
  from .modifiers import modifier_from_dict
  for raw in d.get('surface_modifiers',[]):doc.add_surface_modifier(modifier_from_dict(raw))
  doc.dirty.clear();return doc
 def save(self,path):
  with open(path,'w',encoding='utf8') as f:json.dump(self.to_dict(),f,indent=2)
 @classmethod
 def load(cls,path):
  with open(path,encoding='utf8') as f:return cls.from_dict(json.load(f))
