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


def generate_conduit_topology(path_vertices, diameter, segments=12):
 path=[tuple(map(float,point)) for point in path_vertices]
 radius=float(diameter)/2.0
 n=max(8,int(segments))
 rings=[]
 for i,center in enumerate(path):
  if i==0:
   tangent=tuple(path[1][k]-path[0][k] for k in range(3))
  elif i==len(path)-1:
   tangent=tuple(path[-1][k]-path[-2][k] for k in range(3))
  else:
   tangent=tuple(path[i+1][k]-path[i-1][k] for k in range(3))
  length=math.sqrt(sum(v*v for v in tangent))
  if length<=1e-12:raise ValueError('conduit path contains zero-length tangent')
  u=tuple(v/length for v in tangent)
  ref=(0.0,0.0,1.0) if abs(u[2])<0.9 else (0.0,1.0,0.0)
  v=(u[1]*ref[2]-u[2]*ref[1],u[2]*ref[0]-u[0]*ref[2],u[0]*ref[1]-u[1]*ref[0])
  vn=math.sqrt(sum(q*q for q in v))
  if vn<=1e-12:raise ValueError('conduit frame is degenerate')
  v=tuple(q/vn for q in v)
  w=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
  ring=[]
  for j in range(n):
   angle=2.0*math.pi*j/n;c0,s0=math.cos(angle),math.sin(angle)
   ring.append(tuple(center[k]+radius*(c0*v[k]+s0*w[k]) for k in range(3)))
  rings.append(ring)
 vertices=[point for ring in rings for point in ring]
 faces=[]
 for ring_index in range(len(rings)-1):
  a0=ring_index*n;b0=(ring_index+1)*n
  for j in range(n):
   q=(j+1)%n
   faces.append((a0+j,a0+q,b0+q,b0+j))
 faces.append(tuple(reversed(range(n))))
 base=(len(rings)-1)*n
 faces.append(tuple(base+j for j in range(n)))
 return tuple(vertices),tuple(faces)


def _authoritative_mesh(p):
 vertices=[tuple(map(float,point)) for point in p['vertices']]
 matrix=[float(v) for v in p['matrix']]
 def transform(point):
  x,y,z=point
  return (
   matrix[0]*x+matrix[1]*y+matrix[2]*z+matrix[3],
   matrix[4]*x+matrix[5]*y+matrix[6]*z+matrix[7],
   matrix[8]*x+matrix[9]*y+matrix[10]*z+matrix[11],
  )
 transformed=[transform(point) for point in vertices]
 triangles=[];roles=[]
 for face_index,face in enumerate(p['faces']):
  if len(face)<3:continue
  for i in range(1,len(face)-1):
   triangles.append((int(face[0]),int(face[i]),int(face[i+1])))
   roles.append(f'mesh_face:{face_index}')
 return MeshPayload(tuple(transformed),tuple(triangles),tuple(roles))

def _arboreal_branch_mesh(doc,node,segments=20):
 from archforge.organic.arboreal import arboreal_branch_geometry
 g=arboreal_branch_geometry(doc,node.entity_id);a=tuple(float(v) for v in g['start']);b=tuple(float(v) for v in g['end']);r0=float(g['root_radius']);r1=float(g['tip_radius'])
 axis=(b[0]-a[0],b[1]-a[1],b[2]-a[2]);length=math.sqrt(sum(v*v for v in axis))
 if length<=1e-12:raise ValueError('arboreal branch has zero length')
 u=tuple(v/length for v in axis);ref=(0.0,0.0,1.0) if abs(u[2])<0.9 else (0.0,1.0,0.0)
 v=(u[1]*ref[2]-u[2]*ref[1],u[2]*ref[0]-u[0]*ref[2],u[0]*ref[1]-u[1]*ref[0]);vn=math.sqrt(sum(q*q for q in v));v=tuple(q/vn for q in v)
 w=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]);n=max(8,int(segments));verts=[]
 for center,radius in ((a,r0),(b,r1)):
  for i in range(n):
   t=2.0*math.pi*i/n;c,s=math.cos(t),math.sin(t);off=tuple(radius*(c*v[k]+s*w[k]) for k in range(3));verts.append(tuple(center[k]+off[k] for k in range(3)))
 root_center=len(verts);verts.append(a);tip_center=len(verts);verts.append(b);tris=[];roles=[]
 for i in range(n):
  j=(i+1)%n;tris.extend(((i,j,n+j),(i,n+j,n+i)));roles.extend(('branch_shell','branch_shell'))
  tris.append((root_center,j,i));roles.append('branch_root')
  tris.append((tip_center,n+i,n+j));roles.append('branch_tip')
 return MeshPayload(tuple(verts),tuple(tris),tuple(roles))
def _compact_mesh(vertices,triangles,roles):
 used=sorted({i for tri in triangles for i in tri});remap={old:new for new,old in enumerate(used)}
 return MeshPayload(tuple(vertices[i] for i in used),tuple(tuple(remap[i] for i in tri) for tri in triangles),tuple(roles))
def _clip_mesh_scalar(mesh,scalar,keep_positive=True,tolerance=1e-9):
 """Clip a mesh against one scalar half-space while preserving exact edge intersections."""
 vertices=list(mesh.vertices);out_tris=[];out_roles=[];edge_cache={}
 def value(i):return float(scalar(vertices[i]))
 def intersection(a,b):
  key=(a,b) if a<b else (b,a)
  if key in edge_cache:return edge_cache[key]
  da,db=value(a),value(b);den=da-db
  if abs(den)<=1e-15:return a
  t=da/den;pa,pb=vertices[a],vertices[b]
  point=tuple(pa[k]+t*(pb[k]-pa[k]) for k in range(3));idx=len(vertices);vertices.append(point);edge_cache[key]=idx;return idx
 for tri,role in zip(mesh.triangles,mesh.triangle_surfaces):
  poly=list(tri);clipped=[];s=poly[-1];sv=value(s)*(1.0 if keep_positive else -1.0);s_in=sv>=-tolerance
  for e in poly:
   ev=value(e)*(1.0 if keep_positive else -1.0);e_in=ev>=-tolerance
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
   candidate=(clean[0],clean[j],clean[j+1]);a,b,c=(vertices[i] for i in candidate)
   ab=(b[0]-a[0],b[1]-a[1],b[2]-a[2]);ac=(c[0]-a[0],c[1]-a[1],c[2]-a[2]);cross=(ab[1]*ac[2]-ab[2]*ac[1],ab[2]*ac[0]-ab[0]*ac[2],ab[0]*ac[1]-ab[1]*ac[0])
   if sum(v*v for v in cross)<=1e-20:continue
   out_tris.append(candidate);out_roles.append(role)
 return _compact_mesh(vertices,out_tris,out_roles)
def _clip_mesh_halfspace(mesh,plane,keep_sign,tolerance=1e-9):
 px,py=map(float,plane['point']);nx,ny=map(float,plane['normal'])
 def plane_clip(source):
  return _clip_mesh_scalar(source,lambda v:(v[0]-px)*nx+(v[1]-py)*ny,keep_positive=keep_sign>0,tolerance=tolerance)
 if 'z0' not in plane or 'z1' not in plane:return plane_clip(mesh)
 z0,z1=float(plane['z0']),float(plane['z1'])
 if z1<=z0:return mesh
 below=_clip_mesh_scalar(mesh,lambda v:z0-v[2],True,tolerance)
 above=_clip_mesh_scalar(mesh,lambda v:v[2]-z1,True,tolerance)
 middle=_clip_mesh_scalar(mesh,lambda v:v[2]-z0,True,tolerance)
 middle=_clip_mesh_scalar(middle,lambda v:z1-v[2],True,tolerance)
 middle=plane_clip(middle)
 return _combine_meshes((below,middle,above),tolerance)
def _combine_meshes(meshes,tolerance=1e-9):
 vertices=[];triangles=[];roles=[];index={}
 scale=1.0/max(tolerance,1e-12)
 def key(v):return tuple(round(float(x)*scale) for x in v)
 for mesh in meshes:
  remap={}
  for i,v in enumerate(mesh.vertices):
   k=key(v);idx=index.get(k)
   if idx is None:idx=len(vertices);vertices.append(v);index[k]=idx
   remap[i]=idx
  for tri,role in zip(mesh.triangles,mesh.triangle_surfaces):
   mapped=tuple(remap[i] for i in tri)
   if len(set(mapped))==3:triangles.append(mapped);roles.append(role)
 return MeshPayload(tuple(vertices),tuple(triangles),tuple(roles))
def _subtract_opening_patch(mesh,geom):
 """Remove the curved shell projected behind one rectangular planar opening patch.

 The rectangle is interpreted in the patch's semantic tangent/Z frame and extruded along
 its normal. This is a preview trim, not a fabrication Boolean.
 """
 px,py=map(float,geom['plane']['point']);tx,ty=map(float,geom['plane']['tangent']);half=float(geom['patch_width'])/2.0;z0=float(geom['z0']);z1=float(geom['z1'])
 def q(v):return (v[0]-px)*tx+(v[1]-py)*ty
 left=_clip_mesh_scalar(mesh,lambda v:(-half)-q(v),True)
 right=_clip_mesh_scalar(mesh,lambda v:q(v)-half,True)
 middle=_clip_mesh_scalar(mesh,lambda v:q(v)+half,True);middle=_clip_mesh_scalar(middle,lambda v:half-q(v),True)
 bottom=_clip_mesh_scalar(middle,lambda v:z0-v[2],True)
 top=_clip_mesh_scalar(middle,lambda v:v[2]-z1,True)
 return _combine_meshes((left,right,bottom,top))
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
def _active_opening_patches_for_pod(doc,pod_id):
 from archforge.architecture.openings import pod_opening_patch_geometry,pod_opening_junction_conflict
 out=[]
 for entity in doc.entities.values():
  if entity.kind!='organic_opening_patch' or entity.params.get('status')!='active' or entity.params.get('host_id')!=pod_id:continue
  opening_id=entity.params.get('opening_id')
  if pod_opening_junction_conflict(doc,opening_id) is not None:continue
  geom=pod_opening_patch_geometry(doc,opening_id)
  if geom is not None:out.append(geom)
 return out
def _pod_mesh_for_node(doc,node):
 mesh=_pod_mesh(node.params)
 for plane,keep_sign in _active_junction_planes_for_pod(doc,node.entity_id):mesh=_clip_mesh_halfspace(mesh,plane,keep_sign)
 for geom in _active_opening_patches_for_pod(doc,node.entity_id):mesh=_subtract_opening_patch(mesh,geom)
 return mesh

def _oriented_prism(cx,cy,z0,width,depth,height,angle_deg):
 a=math.radians(float(angle_deg));ca,sa=math.cos(a),math.sin(a)
 hw,hd=float(width)/2.0,float(depth)/2.0
 local=[(-hd,-hw),(hd,-hw),(hd,hw),(-hd,hw)]
 plan=[(float(cx)+ca*x-sa*y,float(cy)+sa*x+ca*y) for x,y in local]
 verts=tuple((x,y,float(z0)) for x,y in plan)+tuple((x,y,float(z0)+float(height)) for x,y in plan)
 quads=((0,1,5,4,'riser'),(1,2,6,5,'edge'),(2,3,7,6,'riser'),(3,0,4,7,'edge'),(4,5,6,7,'tread'),(3,2,1,0,'bottom'))
 tris=[];roles=[]
 for a0,b0,c0,d0,role in quads:
  tris.extend(((a0,b0,c0),(a0,c0,d0)));roles.extend((role,role))
 return MeshPayload(verts,tuple(tris),tuple(roles))


def _stair_mesh(p):
 from archforge.architecture.stairs import candidate_from_params
 candidate=candidate_from_params(p)
 n=candidate.tread_count;t=candidate.tread_depth;r=candidate.riser_height
 width=candidate.width;z0=candidate.lower_z;angle=candidate.angle_deg;turn=candidate.turn_direction
 meshes=[]
 def world(local_x,local_y):
  a=math.radians(angle);ca,sa=math.cos(a),math.sin(a)
  return (candidate.origin[0]+ca*local_x-sa*local_y,candidate.origin[1]+sa*local_x+ca*local_y)
 def add_step(local_x,local_y,local_angle,index,depth=None):
  cx,cy=world(local_x,local_y)
  meshes.append(_oriented_prism(cx,cy,z0,width,float(depth or t),(index+1)*r,angle+local_angle))
 if candidate.layout=='straight':
  for i in range(n):add_step((i+.5)*t,0.0,0.0,i)
 elif candidate.layout=='l':
  first=max(1,n//2);second=n-first
  for i in range(first):add_step((i+.5)*t,0.0,0.0,i)
  landing_x=first*t+candidate.landing_depth/2.0
  lx,ly=world(landing_x,turn*candidate.landing_depth/2.0)
  meshes.append(_oriented_prism(lx,ly,z0,candidate.landing_depth,candidate.landing_depth,first*r,angle))
  for j in range(second):
   local_x=first*t+candidate.landing_depth/2.0
   local_y=turn*(candidate.landing_depth+(j+.5)*t)
   add_step(local_x,local_y,90.0*turn,first+j)
 elif candidate.layout=='u':
  first=max(1,n//2);second=n-first;offset=turn*(width+0.20)
  for i in range(first):add_step((i+.5)*t,0.0,0.0,i)
  landing_x=first*t+candidate.landing_depth/2.0
  landing_y=offset/2.0
  lx,ly=world(landing_x,landing_y)
  meshes.append(_oriented_prism(lx,ly,z0,abs(offset)+width,candidate.landing_depth,first*r,angle))
  for j in range(second):
   local_x=first*t+candidate.landing_depth-(j+.5)*t
   add_step(local_x,offset,180.0,first+j)
 elif candidate.layout=='spiral':
  inner=max(0.12,width*.20);outer=max(width,0.85)+width*.45
  sweep=turn*2.0*math.pi
  for i in range(n):
   a0=sweep*i/n;a1=sweep*(i+1)/n
   points=[(inner*math.cos(a0),inner*math.sin(a0)),(outer*math.cos(a0),outer*math.sin(a0)),(outer*math.cos(a1),outer*math.sin(a1)),(inner*math.cos(a1),inner*math.sin(a1))]
   plan=[world(x,y) for x,y in points];top=z0+(i+1)*r
   verts=tuple((x,y,z0) for x,y in plan)+tuple((x,y,top) for x,y in plan)
   quads=((0,1,5,4,'riser'),(1,2,6,5,'edge'),(2,3,7,6,'riser'),(3,0,4,7,'edge'),(4,5,6,7,'tread'),(3,2,1,0,'bottom'))
   tris=[];roles=[]
   for aa,bb,cc,dd,role in quads:tris.extend(((aa,bb,cc),(aa,cc,dd)));roles.extend((role,role))
   meshes.append(MeshPayload(verts,tuple(tris),tuple(roles)))
 else:
  raise ValueError(f'stair mesh layout not implemented: {candidate.layout}')
 if not meshes:raise ValueError('stair generated no steps')
 return _combine_meshes(tuple(meshes),1e-8)


def _ramp_mesh(p):
 from archforge.architecture.ramps import candidate_from_params
 candidate=candidate_from_params(p)
 a=math.radians(candidate.angle_deg);ux,uy=math.cos(a),math.sin(a);vx,vy=-uy,ux
 ox,oy=candidate.origin;run=float(candidate.run_length);half=float(candidate.width)/2.0
 z0=float(candidate.lower_z);z1=float(candidate.upper_z);th=float(candidate.thickness)
 def point(along,across,z):
  return (ox+ux*along+vx*across,oy+uy*along+vy*across,z)
 verts=(
  point(0.0,-half,z0-th),point(run,-half,z1-th),
  point(run,half,z1-th),point(0.0,half,z0-th),
  point(0.0,-half,z0),point(run,-half,z1),
  point(run,half,z1),point(0.0,half,z0),
 )
 quads=(
  (0,1,5,4,'ramp_side'),
  (1,2,6,5,'ramp_end'),
  (2,3,7,6,'ramp_side'),
  (3,0,4,7,'ramp_start'),
  (4,5,6,7,'ramp_surface'),
  (3,2,1,0,'ramp_bottom'),
 )
 tris=[];roles=[]
 for aa,bb,cc,dd,role in quads:
  tris.extend(((aa,bb,cc),(aa,cc,dd)));roles.extend((role,role))
 return MeshPayload(tuple(verts),tuple(tris),tuple(roles))


def _point_in_polygon_xy(point,polygon):
 x,y=map(float,point);inside=False
 pts=[(float(a),float(b)) for a,b in polygon];j=len(pts)-1
 for i,(xi,yi) in enumerate(pts):
  xj,yj=pts[j]
  if ((yi>y)!=(yj>y)):
   at=xj+(y-yj)*(xi-xj)/(yi-yj)
   if x<at:inside=not inside
  j=i
 return inside


def _rect_hole_side_mesh(xmin,xmax,ymin,ymax,z0,z1):
 verts=[];tris=[];roles=[]
 def quad(a,b,c,d):
  base=len(verts);verts.extend((a,b,c,d));tris.extend(((base,base+1,base+2),(base,base+2,base+3)));roles.extend(('stair_opening_edge','stair_opening_edge'))
 quad((xmin,ymin,z0),(xmin,ymax,z0),(xmin,ymax,z1),(xmin,ymin,z1))
 quad((xmax,ymax,z0),(xmax,ymin,z0),(xmax,ymin,z1),(xmax,ymax,z1))
 quad((xmax,ymin,z0),(xmin,ymin,z0),(xmin,ymin,z1),(xmax,ymin,z1))
 quad((xmin,ymax,z0),(xmax,ymax,z0),(xmax,ymax,z1),(xmin,ymax,z1))
 return MeshPayload(tuple(verts),tuple(tris),tuple(roles))


def _subtract_rectangular_slab_hole(mesh,opening,z0,z1):
 xs=[float(p[0]) for p in opening];ys=[float(p[1]) for p in opening]
 xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
 left=_clip_mesh_scalar(mesh,lambda v:xmin-v[0],True)
 right=_clip_mesh_scalar(mesh,lambda v:v[0]-xmax,True)
 middle=_clip_mesh_scalar(mesh,lambda v:v[0]-xmin,True)
 middle=_clip_mesh_scalar(middle,lambda v:xmax-v[0],True)
 front=_clip_mesh_scalar(middle,lambda v:ymin-v[1],True)
 back=_clip_mesh_scalar(middle,lambda v:v[1]-ymax,True)
 sides=_rect_hole_side_mesh(xmin,xmax,ymin,ymax,float(z0),float(z1))
 return _combine_meshes((left,right,front,back,sides),1e-8)

def _apply_vertical_openings_to_slab(doc,mesh,points,slab_z,thickness):
 from archforge.architecture.stairs import candidate_from_params as stair_candidate,stair_opening_polygon
 from archforge.architecture.ramps import candidate_from_params as ramp_candidate,ramp_opening_polygon
 slab_z=float(slab_z);thickness=float(thickness)
 for entity in doc.entities.values():
  if entity.kind not in ('stair','ramp'):continue
  upper_floor_z=float(entity.params.get('upper_floor_z',entity.params['upper_z']))
  if abs(upper_floor_z-slab_z)>1e-5:continue
  if entity.kind=='stair':
   opening=stair_opening_polygon(stair_candidate(entity.params))
  else:
   opening=ramp_opening_polygon(ramp_candidate(entity.params))
  if not opening:continue
  # The opening may legitimately cross a room boundary. Requiring every
  # envelope corner to sit inside one slab prevented any cut at all.
  cx=sum(float(p[0]) for p in opening)/len(opening)
  cy=sum(float(p[1]) for p in opening)/len(opening)
  overlaps=(
   _point_in_polygon_xy((cx,cy),points)
   or any(_point_in_polygon_xy(point,points) for point in opening)
   or any(_point_in_polygon_xy(point,opening) for point in points)
  )
  if overlaps:
   mesh=_subtract_rectangular_slab_hole(mesh,opening,slab_z,slab_z+thickness)
 return mesh

def _floor_slab(doc,node):
 p=node.params
 mesh=_polygon_prism(p['points'],p['z'],p['thickness'])
 return _apply_vertical_openings_to_slab(doc,mesh,p['points'],p['z'],p['thickness'])

def _room_slab(doc,node):
 from archforge.architecture.rooms import room_slab_geometry
 g=room_slab_geometry(doc,doc.get(node.entity_id))
 if g is None:raise ValueError('derived room element has no currently closed room')
 mesh=_polygon_prism(g['points'],g['z'],g['thickness'])
 if node.semantic_kind in ('room_floor','room_ceiling','room_roof'):
  mesh=_apply_vertical_openings_to_slab(doc,mesh,g['points'],g['z'],g['thickness'])
 return mesh
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
def _organic_opening_patch_mesh(doc,node):
 from archforge.architecture.openings import pod_opening_patch_geometry,pod_opening_junction_conflict
 if node.params.get('status')!='active':raise ValueError('organic opening patch is dormant')
 opening_id=node.params.get('opening_id')
 junction_id=pod_opening_junction_conflict(doc,opening_id)
 if junction_id is not None:raise ValueError(f'organic opening patch conflicts with active junction {junction_id}')
 g=pod_opening_patch_geometry(doc,opening_id)
 if g is None:raise ValueError('organic opening patch has no current host geometry')
 if opening_id not in doc.entities:raise ValueError('organic opening patch opening is missing')
 opening=doc.get(opening_id)
 if opening.kind not in ('door','window'):raise ValueError('organic opening patch source must be door/window')
 host=doc.get(node.params.get('host_id'))
 if host.kind!='pod':raise ValueError('organic opening patch host must be pod')
 px,py=map(float,g['plane']['point']);tx,ty=map(float,g['plane']['tangent'])
 outer_half=float(g['patch_width'])/2.0;inner_half=float(opening.params['width'])/2.0
 z0=float(g['z0']);z1=float(g['z1']);open_z0=float(host.params['floor_level'])+float(opening.params.get('sill',0.0));open_z1=open_z0+float(opening.params['height'])
 vertices=[];triangles=[];roles=[]
 def point(q,z):return (px+tx*q,py+ty*q,z)
 def add_rect(q0,q1,za,zb):
  if q1-q0<=1e-12 or zb-za<=1e-12:return
  base=len(vertices);vertices.extend((point(q0,za),point(q1,za),point(q1,zb),point(q0,zb)))
  triangles.extend(((base,base+1,base+2),(base,base+2,base+3)));roles.extend(('opening_patch','opening_patch'))
 # Side jambs span the full flat patch height. The inner center stays empty.
 add_rect(-outer_half,-inner_half,z0,z1)
 add_rect(inner_half,outer_half,z0,z1)
 # Door openings reach the floor, so this strip naturally disappears for sill==0.
 add_rect(-inner_half,inner_half,z0,min(open_z0,z1))
 add_rect(-inner_half,inner_half,max(open_z1,z0),z1)
 if not triangles:raise ValueError('organic opening patch has no planar frame area')
 return MeshPayload(tuple(vertices),tuple(triangles),tuple(roles))
def _payload(doc,node):
 k,p=node.semantic_kind,node.params
 if k=='wall':return _wall_mesh(p)
 if k in('box','mechanical_part'):return _box_mesh(p,node.transform)
 if k=='pod':return _pod_mesh_for_node(doc,node)
 if k=='mesh':return _authoritative_mesh(p)
 if k=='stair':return _stair_mesh(p)
 if k=='ramp':return _ramp_mesh(p)
 if k=='arboreal_branch':return _arboreal_branch_mesh(doc,node)
 if k=='organic_junction':return _organic_junction_mesh(doc,node)
 if k=='organic_opening_patch':return _organic_opening_patch_mesh(doc,node)
 if k=='floor':return _floor_slab(doc,node)
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