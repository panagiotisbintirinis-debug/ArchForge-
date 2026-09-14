from __future__ import annotations
from dataclasses import dataclass
from typing import List,Tuple
import math
from .backend import ContractBackend,GeometryBackend,GeometryBody,GeometryEvaluation,GeometryIssue
Vec3=Tuple[float,float,float];Tri=Tuple[int,int,int]
@dataclass(frozen=True)
class MeshPayload:
 vertices:Tuple[Vec3,...];triangles:Tuple[Tri,...];triangle_surfaces:Tuple[str,...]
 def __post_init__(self):
  if len(self.triangles)!=len(self.triangle_surfaces):raise ValueError('each triangle must retain one semantic surface role')
  n=len(self.vertices)
  if any(i<0 or i>=n for t in self.triangles for i in t):raise ValueError('triangle references a missing vertex')
def _area2(p):return sum(p[i][0]*p[(i+1)%len(p)][1]-p[(i+1)%len(p)][0]*p[i][1] for i in range(len(p)))
def _inside(p,a,b,c):
 def cr(u,v,w):return(v[0]-u[0])*(w[1]-u[1])-(v[1]-u[1])*(w[0]-u[0])
 x,y,z=cr(a,b,p),cr(b,c,p),cr(c,a,p);return(x>=-1e-12 and y>=-1e-12 and z>=-1e-12)or(x<=1e-12 and y<=1e-12 and z<=1e-12)
def _triangulate(points):
 pts=[(float(x),float(y)) for x,y in points];area=_area2(pts)
 if len(pts)<3 or abs(area)<=1e-12:raise ValueError('invalid polygon')
 order=list(range(len(pts)));order=order if area>0 else list(reversed(order));out=[];guard=0
 while len(order)>3:
  guard+=1
  if guard>len(pts)**2:raise ValueError('polygon cannot be triangulated')
  found=False
  for j in range(len(order)):
   ia,ib,ic=order[j-1],order[j],order[(j+1)%len(order)];a,b,c=pts[ia],pts[ib],pts[ic]
   if (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])<=1e-12:continue
   if any(_inside(pts[k],a,b,c) for k in order if k not in(ia,ib,ic)):continue
   out.append((ia,ib,ic));del order[j];found=True;break
  if not found:raise ValueError('polygon invalid')
 out.append(tuple(order));return tuple(out)
def _wall_mesh(p):
 from .wall_detail import detailed_wall_geometry
 v,t,r=detailed_wall_geometry(p,target_step=.5);return MeshPayload(v,t,r)
def _box_mesh(p,transform=None):
 w,d,h=map(float,(p['width'],p['depth'],p['height']));local=[(0,0,0),(w,0,0),(w,d,0),(0,d,0),(0,0,h),(w,0,h),(w,d,h),(0,d,h)]
 if transform is not None:v=[tuple(sum(transform[r][c]*q[c] for c in range(3))+transform[r][3] for r in range(3)) for q in local]
 else:
  a=math.radians(float(p.get('rotation',0)));c,s=math.cos(a),math.sin(a);ox,oy,oz=map(float,(p['x'],p['y'],p['z']));v=[(ox+c*x-s*y,oy+s*x+c*y,oz+z) for x,y,z in local]
 quads=((0,1,5,4,'front'),(1,2,6,5,'right'),(2,3,7,6,'back'),(3,0,4,7,'left'),(4,5,6,7,'top'),(3,2,1,0,'bottom'));tris=[];roles=[]
 for a,b,c,d,r in quads:tris.extend(((a,b,c),(a,c,d)));roles.extend((r,r))
 return MeshPayload(tuple(v),tuple(tris),tuple(roles))
def _polygon_prism(points,z,thickness):
 pts=[(float(x),float(y)) for x,y in points];z=float(z);thickness=float(thickness);top=_triangulate(pts);n=len(pts);verts=tuple((x,y,z) for x,y in pts)+tuple((x,y,z+thickness) for x,y in pts);tris=[];roles=[]
 for a,b,c in top:tris.extend(((a+n,b+n,c+n),(c,b,a)));roles.extend(('top','bottom'))
 for i in range(n):j=(i+1)%n;tris.extend(((i,j,j+n),(i,j+n,i+n)));roles.extend(('edge','edge'))
 return MeshPayload(verts,tuple(tris),tuple(roles))
def _pod_mesh(p,segments=32,rings=12):
 cx,cy,z=map(float,(p['cx'],p['cy'],p['floor_level']));rx,ry,rz=float(p['diameter_x'])/2,float(p['diameter_y'])/2,float(p['height']);v=[]
 for j in range(rings+1):
  phi=math.pi/2*j/rings;rr=math.cos(phi);zz=z+rz*math.sin(phi)
  for i in range(segments):a=2*math.pi*i/segments;v.append((cx+rx*rr*math.cos(a),cy+ry*rr*math.sin(a),zz))
 tris=[];roles=[]
 for j in range(rings):
  for i in range(segments):n=(i+1)%segments;a=j*segments+i;b=j*segments+n;c=(j+1)*segments+n;d=(j+1)*segments+i;tris.extend(((a,b,c),(a,c,d)));roles.extend(('pod_shell','pod_shell'))
 return MeshPayload(tuple(v),tuple(tris),tuple(roles))
def _room_slab(doc,node):
 from archforge.architecture.rooms import find_room_face
 found=find_room_face(doc,node.params['room_signature'])
 if found is None:raise ValueError('derived room element has no currently closed room')
 face,z=found;p=node.params;return _polygon_prism(face.polygon,float(z)+float(p['offset_z']),p['thickness'])
def _payload(doc,node):
 k,p=node.semantic_kind,node.params
 if k=='wall':return _wall_mesh(p)
 if k in('box','mechanical_part'):return _box_mesh(p,node.transform)
 if k=='pod':return _pod_mesh(p)
 if k=='floor':return _polygon_prism(p['points'],p['z'],p['thickness'])
 if k in('room_floor','room_ceiling','room_foundation','room_roof'):return _room_slab(doc,node)
 raise ValueError(f'tessellation not implemented for {k}')
class TessellatedPreviewBackend(GeometryBackend):
 name='tessellated-preview'
 def evaluate_plan(self,doc,plan):
  contract=ContractBackend().evaluate_plan(doc,plan);issues=list(contract.issues);bodies=[]
  for node in plan.geometry_nodes():
   base=contract.body(node.entity_id)
   try:bodies.append(GeometryBody(node.entity_id,node.semantic_kind,base.surface_keys,base.modifier_ids,_payload(doc,node),quality='preview-mesh',modifiers_applied=False))
   except Exception as exc:issues.append(GeometryIssue('warning','tessellation_unavailable',str(exc),node.entity_id))
  return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
