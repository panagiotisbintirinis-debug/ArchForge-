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
 angle=math.radians(float(p.get('rotation',0.0)));cr,sr=math.cos(angle),math.sin(angle)
 for j in range(rings+1):
  phi=math.pi/2*j/rings;rr=math.cos(phi);zz=z+rz*math.sin(phi)
  for i in range(segments):
   a=2*math.pi*i/segments;lx=rx*rr*math.cos(a);ly=ry*rr*math.sin(a)
   v.append((cx+cr*lx-sr*ly,cy+sr*lx+cr*ly,zz))
 tris=[];roles=[]
 for j in range(rings):
  for i in range(segments):n=(i+1)%segments;a=j*segments+i;b=j*segments+n;c=(j+1)*segments+n;d=(j+1)*segments+i;tris.extend(((a,b,c),(a,c,d)));roles.extend(('pod_shell','pod_shell'))
 return MeshPayload(tuple(v),tuple(tris),tuple(roles))
def _compact_mesh(vertices,triangles,roles):
 used=sorted({i for tri in triangles for i in tri});remap={old:new for new,old in enumerate(used)}
 return MeshPayload(tuple(vertices[i] for i in used),tuple(tuple(remap[i] for i in tri) for tri in triangles),tuple(roles))
def _clip_mesh_halfspace(mesh,plane,keep_sign,tolerance=1e-9):
 """Clip a semantic preview mesh against one vertical half-space, sharing cut-edge vertices."""
 px,py=map(float,plane['point']);nx,ny=map(float,plane['normal']);vertices=list(mesh.vertices);out_tris=[];out_roles=[];edge_cache={}
 def distance(i):
  x,y,_=vertices[i];return (x-px)*nx+(y-py)*ny
 def intersection(a,b):
  key=(a,b) if a<b else (b,a)
  if key in edge_cache:return edge_cache[key]
  da,db=distance(a),distance(b);den=da-db
  if abs(den)<=1e-15:return a
  t=da/den;pa,pb=vertices[a],vertices[b]
  point=tuple(pa[k]+t*(pb[k]-pa[k]) for k in range(3));idx=len(vertices);vertices.append(point);edge_cache[key]=idx;return idx
 for tri,role in zip(mesh.triangles,mesh.triangle_surfaces):
  poly=list(tri);clipped=[];s=poly[-1];ds=keep_sign*distance(s);s_in=ds>=-tolerance
  for e in poly:
   de=keep_sign*distance(e);e_in=de>=-tolerance
   if e_in:
    if not s_in:clipped.append(intersection(s,e))
    clipped.append(e)
   elif s_in:clipped.append(intersection(s,e))
   s=e;s_in=e_in
  clean=[]
  for i in clipped:
   if not clean or clean[-1]!=i:clean.append(i)
  if len(clean)>1 and clean[0]==clean[-1]:clean.pop()
  if len(clean)<3:continue
  for j in range(1,len(clean)-1):
   candidate=(clean[0],clean[j],clean[j+1])
   a,b,c=(vertices[i] for i in candidate)
   ab=(b[0]-a[0],b[1]-a[1],b[2]-a[2]);ac=(c[0]-a[0],c[1]-a[1],c[2]-a[2])
   cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
   if sum(v*v for v in cross)<=1e-20:continue
   out_tris.append(candidate);out_roles.append(role)
 return _compact_mesh(vertices,out_tris,out_roles)
def _active_junction_planes_for_pod(doc,pod_id):
 from archforge.organic.biospectre import junction_plane,junction_section_polygon
 out=[]
 for entity in doc.entities.values():
  if entity.kind!='organic_junction' or entity.params.get('status')!='active':continue
  a_id,b_id=entity.params.get('component_a'),entity.params.get('component_b')
  if pod_id not in (a_id,b_id) or a_id not in doc.entities or b_id not in doc.entities:continue
  a,b=doc.get(a_id),doc.get(b_id)
  if a.kind!='pod' or b.kind!='pod':continue
  plane=junction_plane(a.params,b.params)
  if plane is None or junction_section_polygon(a.params,b.params) is None:continue
  pod=doc.get(pod_id);cx,cy=float(pod.params['cx']),float(pod.params['cy']);px,py=plane['point'];nx,ny=plane['normal'];signed=(cx-px)*nx+(cy-py)*ny
  if abs(signed)<=1e-12:continue
  out.append((plane,1.0 if signed>0 else -1.0))
 return out
def _pod_mesh_for_node(doc,node):
 mesh=_pod_mesh(node.params)
 for plane,keep_sign in _active_junction_planes_for_pod(doc,node.entity_id):mesh=_clip_mesh_halfspace(mesh,plane,keep_sign)
 return mesh
def _room_slab(doc,node):
 from archforge.architecture.rooms import room_slab_geometry
 g=room_slab_geometry(doc,doc.get(node.entity_id))
 if g is None:raise ValueError('derived room element has no currently closed room')
 return _polygon_prism(g['points'],g['z'],g['thickness'])
def _organic_junction_mesh(doc,node):
 from archforge.organic.biospectre import junction_plane,junction_section_polygon
 p=node.params
 if p.get('status')!='active':raise ValueError('organic junction is dormant')
 a_id,b_id=p.get('component_a'),p.get('component_b')
 if a_id not in doc.entities or b_id not in doc.entities:raise ValueError('organic junction source is missing')
 a,b=doc.get(a_id),doc.get(b_id)
 if a.kind!='pod' or b.kind!='pod':raise ValueError('organic junction sources must be pods')
 plane=junction_plane(a.params,b.params);points=junction_section_polygon(a.params,b.params)
 if plane is None or points is None:raise ValueError('organic junction has no current section')
 px,py=plane['point'];nx,ny=plane['normal'];tx,ty=-ny,nx
 local=[((x-px)*tx+(y-py)*ty,z) for x,y,z in points]
 tris=_triangulate(local)
 return MeshPayload(tuple(points),tuple(tris),tuple('junction' for _ in tris))
def _payload(doc,node):
 k,p=node.semantic_kind,node.params
 if k=='wall':return _wall_mesh(p)
 if k in('box','mechanical_part'):return _box_mesh(p,node.transform)
 if k=='pod':return _pod_mesh_for_node(doc,node)
 if k=='organic_junction':return _organic_junction_mesh(doc,node)
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