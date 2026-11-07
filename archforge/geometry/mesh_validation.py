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
 findings:Tuple[MeshFinding,...];boundary_edges:int;nonmanifold_edges:int;orientation_conflicts:int;degenerate_triangles:int;duplicate_faces:int=0
 signed_volume:float=0.0   # Σ over triangles (divergence theorem): < 0 on a closed mesh = faces point inwards
 @property
 def manifold(self):return self.nonmanifold_edges==0 and self.orientation_conflicts==0 and self.degenerate_triangles==0 and self.duplicate_faces==0
 @property
 def watertight(self):return self.manifold and self.boundary_edges==0
 @property
 def inside_out(self):return self.watertight and self.signed_volume<0

def _area2(a,b,c):
 ux,uy,uz=b[0]-a[0],b[1]-a[1],b[2]-a[2];vx,vy,vz=c[0]-a[0],c[1]-a[1],c[2]-a[2]
 x,y,z=uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx;return math.sqrt(x*x+y*y+z*z)

def _geometric_face_key(mesh,tri):
 """Exact orientation-independent face key using physical vertex coordinates.

 This intentionally detects only exact coincident triangles. Near-coincident faces and
 general self-intersections require a later spatial-intersection validator rather than
 pretending a tolerance-bucket heuristic proves fabrication safety.
 """
 return tuple(sorted(tuple(float(v) for v in mesh.vertices[i]) for i in tri))

def validate_mesh(mesh,tolerance=1e-10):
 findings=[];edges=defaultdict(list);deg=0;duplicates=0;faces={}
 for ti,tri in enumerate(mesh.triangles):
  if len(set(tri))<3 or _area2(*(mesh.vertices[i] for i in tri))<=tolerance:
   deg+=1;findings.append(MeshFinding('error','degenerate_triangle','triangle has zero or near-zero area',ti));continue
  face_key=_geometric_face_key(mesh,tri)
  if face_key in faces:
   duplicates+=1;findings.append(MeshFinding('error','duplicate_face',f'triangle duplicates physical face {faces[face_key]}',ti))
  else:faces[face_key]=ti
  a,b,c=tri
  for u,v in ((a,b),(b,c),(c,a)):edges[tuple(sorted((u,v)))].append((ti,u,v))
 boundary=nonmanifold=conflicts=0
 for key,uses in edges.items():
  if len(uses)==1:boundary+=1
  elif len(uses)>2:nonmanifold+=1;findings.append(MeshFinding('error','nonmanifold_edge',f'edge {key} has {len(uses)} incident triangles'))
  elif uses[0][1:]==uses[1][1:]:conflicts+=1;findings.append(MeshFinding('error','orientation_conflict',f'edge {key} has equal directed winding'))
 if boundary:findings.append(MeshFinding('error','boundary_edges',f'{boundary} boundary edges leave mesh open'))
 V=mesh.vertices;vol=0.0
 for a,b,c in mesh.triangles:
  (x1,y1,z1),(x2,y2,z2),(x3,y3,z3)=V[a],V[b],V[c]
  vol+=(x1*(y2*z3-y3*z2)-x2*(y1*z3-y3*z1)+x3*(y1*z2-y2*z1))/6.0
 if boundary==0 and nonmanifold==0 and conflicts==0 and vol<0:
  findings.append(MeshFinding('error','inside_out',f'closed mesh with negative volume {vol:.6g}: faces point inwards'))
 return MeshValidation(tuple(findings),boundary,nonmanifold,conflicts,deg,duplicates,vol)


def welded(mesh, digits=6):
 """The same mesh with coincident vertices merged (rounded to ``digits``), so a solid built from separate faces
 (pool coping, stairs …) is checked as the closed shape it is on screen / in STL; triangles that collapse are dropped."""
 from .mesh import MeshPayload
 index={};verts=[];remap=[]
 for v in mesh.vertices:
  key=tuple(round(float(c),digits) for c in v)
  if key not in index:index[key]=len(verts);verts.append(tuple(float(c) for c in v))
  remap.append(index[key])
 tris=[];roles=[]
 for t,r in zip(mesh.triangles,mesh.triangle_surfaces):
  a,b,c=(remap[i] for i in t)
  if len({a,b,c})==3:tris.append((a,b,c));roles.append(r)
 return MeshPayload(tuple(verts),tuple(tris),tuple(roles))


def open_length(mesh, tol=1e-6):
 """Length of the boundary that is really open (m): after welding, edges along which the surface does not meet
 itself.  A T-junction (one long edge against two short ones of a touching part, e.g. a slab made of pieces) is
 closed geometrically and counts 0 — every point of such an edge is covered twice."""
 from collections import Counter
 w=welded(mesh);V=w.vertices;use=Counter()
 for a,b,c in w.triangles:
  for x,y in ((a,b),(b,c),(c,a)):use[(min(x,y),max(x,y))]+=1
 edges=[(V[a],V[b]) for (a,b),n in use.items() if n==1]
 def sub(p,q):return (p[0]-q[0],p[1]-q[1],p[2]-q[2])
 def dot(p,q):return p[0]*q[0]+p[1]*q[1]+p[2]*q[2]
 def on_line(p,a,d,L):
  r=sub(p,a);t=dot(r,d)
  off=sub(r,(d[0]*t,d[1]*t,d[2]*t));return dot(off,off)<=(tol*max(1.0,L))**2,t
 total=0.0
 for i,(a,b) in enumerate(edges):
  ab=sub(b,a);L=math.sqrt(dot(ab,ab))
  if L<=tol:continue
  d=(ab[0]/L,ab[1]/L,ab[2]/L);cuts={0.0,L};spans=[]
  for j,(c,e) in enumerate(edges):
   if j==i:continue
   oc,tc=on_line(c,a,d,L);oe,te=on_line(e,a,d,L)
   if oc and oe:
    lo,hi=sorted((tc,te))
    if hi>tol and lo<L-tol:spans.append((lo,hi));cuts.update(x for x in (lo,hi) if 0<x<L)
  cuts=sorted(cuts)
  for x0,x1 in zip(cuts,cuts[1:]):
   m=(x0+x1)/2
   if not any(lo-tol<=m<=hi+tol for lo,hi in spans):total+=x1-x0
 return total
