from __future__ import annotations
from dataclasses import dataclass
from typing import Dict,Tuple
@dataclass(frozen=True)
class SurfaceDescriptor:
 owner_id:str;role:str;deformable:bool=True;fabrication_surface:bool=True;description:str=''
 @property
 def key(self):return f'{self.owner_id}:{self.role}'
def _slab(label):return tuple((r,True,True,f'{label} {r}') for r in('top','bottom','edge'))
_KIND_ROLES:Dict[str,Tuple[Tuple[str,bool,bool,str],...]]={
 'wall':(('exterior',True,True,'wall exterior face'),('interior',True,True,'wall interior face'),('top',True,True,'wall top'),('start',True,True,'wall start return'),('end',True,True,'wall end return'),('bottom',False,True,'wall bottom')),
 'box':tuple((r,True,True,f'box {r} face') for r in('top','bottom','left','right','front','back')),
 'mechanical_part':tuple((r,True,True,f'mechanical part {r} face') for r in('top','bottom','left','right','front','back')),
 'pod':(('pod_shell',True,True,'curved pod shell'),('junction',True,True,'generated flat pod junction'),('floor',True,True,'pod floor')),
 'floor':_slab('floor'),'room_floor':_slab('derived room floor'),'room_ceiling':_slab('derived room ceiling'),'room_foundation':_slab('derived foundation'),'room_roof':_slab('derived roof'),
 'room':(('ceiling',True,False,'generated room ceiling'),('floor_boundary',False,False,'room floor boundary'))}
def surface_catalog(doc,owner_id):
 if owner_id not in doc.entities:raise ValueError('surface owner does not exist')
 e=doc.entities[owner_id];return tuple(SurfaceDescriptor(owner_id,*r) for r in _KIND_ROLES.get(e.kind,()))
def surface_roles(doc,owner_id):return tuple(s.role for s in surface_catalog(doc,owner_id))
def resolve_surface(doc,owner_id,role):
 for s in surface_catalog(doc,owner_id):
  if s.role==role:return s
 kind=doc.entities[owner_id].kind if owner_id in doc.entities else '<missing>';raise ValueError(f'unsupported semantic surface role {role!r} for {kind}')
def validate_surface_role(doc,owner_id,role,*,require_deformable=False):
 s=resolve_surface(doc,owner_id,role)
 if require_deformable and not s.deformable:raise ValueError(f'surface {s.key} is not deformable')
 return s
