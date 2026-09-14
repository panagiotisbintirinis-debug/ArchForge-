from __future__ import annotations
from dataclasses import dataclass
from typing import Optional,Tuple
from collections import defaultdict
import math

@dataclass(frozen=True)
class MeshFinding:
 severity:str;code:str;message:str;triangle_index:Optional[int]=None
@dataclass(frozen=True)
class MeshValidation:
 findings:Tuple[MeshFinding,...];boundary_edges:int;nonmanifold_edges:int;orientation_conflicts:int;degenerate_triangles:int
 @property
 def manifold(self):return self.nonmanifold_edges==0 and self.orientation_conflicts==0 and self.degenerate_triangles==0
 @property
 def watertight(self):return self.manifold and self.boundary_edges==0

def _area2(a,b,c):
 ux,uy,uz=b[0]-a[0],b[1]-a[1],b[2]-a[2];vx,vy,vz=c[0]-a[0],c[1]-a[1],c[2]-a[2]
 x,y,z=uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx;return math.sqrt(x*x+y*y+z*z)

def validate_mesh(mesh,tolerance=1e-10):
 findings=[];edges=defaultdict(list);deg=0
 for ti,tri in enumerate(mesh.triangles):
  if len(set(tri))<3 or _area2(*(mesh.vertices[i] for i in tri))<=tolerance:
   deg+=1;findings.append(MeshFinding('error','degenerate_triangle','triangle has zero or near-zero area',ti));continue
  a,b,c=tri
  for u,v in ((a,b),(b,c),(c,a)):edges[tuple(sorted((u,v)))].append((ti,u,v))
 boundary=nonmanifold=conflicts=0
 for key,uses in edges.items():
  if len(uses)==1:boundary+=1
  elif len(uses)>2:nonmanifold+=1;findings.append(MeshFinding('error','nonmanifold_edge',f'edge {key} has {len(uses)} incident triangles'))
  elif uses[0][1:]==uses[1][1:]:conflicts+=1;findings.append(MeshFinding('error','orientation_conflict',f'edge {key} has equal directed winding'))
 if boundary:findings.append(MeshFinding('error','boundary_edges',f'{boundary} boundary edges leave mesh open'))
 return MeshValidation(tuple(findings),boundary,nonmanifold,conflicts,deg)
