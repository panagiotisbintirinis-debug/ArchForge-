from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple
import math

from .backend import ContractBackend, GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue

Vec3=Tuple[float,float,float]
Tri=Tuple[int,int,int]

@dataclass(frozen=True)
class MeshPayload:
    """Viewport tessellation retaining semantic ownership per triangle."""
    vertices:Tuple[Vec3,...]
    triangles:Tuple[Tri,...]
    triangle_surfaces:Tuple[str,...]

    def __post_init__(self):
        if len(self.triangles)!=len(self.triangle_surfaces):
            raise ValueError('each triangle must retain one semantic surface key')


def _wall_mesh(p)->MeshPayload:
    x1,y1,z,x2,y2=map(float,(p['x1'],p['y1'],p['z'],p['x2'],p['y2']))
    h,t=float(p['height']),float(p['thickness']);dx,dy=x2-x1,y2-y1;L=math.hypot(dx,dy)
    if L<=1e-12: raise ValueError('wall has zero length')
    nx,ny=-dy/L*t/2,dx/L*t/2
    v=((x1+nx,y1+ny,z),(x2+nx,y2+ny,z),(x2-nx,y2-ny,z),(x1-nx,y1-ny,z),
       (x1+nx,y1+ny,z+h),(x2+nx,y2+ny,z+h),(x2-nx,y2-ny,z+h),(x1-nx,y1-ny,z+h))
    faces=[((0,1,5),(0,5,4),'exterior'),((3,7,6),(3,6,2),'interior'),
           ((4,5,6),(4,6,7),'top'),((0,4,7),(0,7,3),'start'),((1,2,6),(1,6,5),'end')]
    tris=[];roles=[]
    for a,b,r in faces:tris.extend((a,b));roles.extend((r,r))
    return MeshPayload(v,tuple(tris),tuple(roles))


def _box_mesh(p,transform=None)->MeshPayload:
    w,d,h=map(float,(p['width'],p['depth'],p['height']))
    local=[(0,0,0),(w,0,0),(w,d,0),(0,d,0),(0,0,h),(w,0,h),(w,d,h),(0,d,h)]
    if transform is not None:
        v=[tuple(sum(transform[r][c]*q[c] for c in range(3))+transform[r][3] for r in range(3)) for q in local]
    else:
        a=math.radians(float(p.get('rotation',0)));c,s=math.cos(a),math.sin(a);ox,oy,oz=map(float,(p['x'],p['y'],p['z']))
        v=[(ox+c*x-s*y,oy+s*x+c*y,oz+z) for x,y,z in local]
    quads=[(0,1,5,4,'side_1'),(1,2,6,5,'side_2'),(2,3,7,6,'side_3'),(3,0,4,7,'side_4'),(4,5,6,7,'top'),(3,2,1,0,'bottom')]
    tris=[];roles=[]
    for a,b,c,d,r in quads:tris.extend(((a,b,c),(a,c,d)));roles.extend((r,r))
    return MeshPayload(tuple(v),tuple(tris),tuple(roles))


def _pod_mesh(p,segments=24,rings=8)->MeshPayload:
    """Upper ellipsoid only: floor plane is the hard lower boundary."""
    cx,cy,z=map(float,(p['cx'],p['cy'],p['floor_level']));rx=float(p['diameter_x'])/2;ry=float(p['diameter_y'])/2;rz=float(p['height'])
    verts=[]
    for j in range(rings+1):
        phi=(math.pi/2)*(j/rings)
        rr=math.cos(phi);zz=z+rz*math.sin(phi)
        for i in range(segments):
            a=2*math.pi*i/segments;verts.append((cx+rx*rr*math.cos(a),cy+ry*rr*math.sin(a),zz))
    tris=[];roles=[]
    for j in range(rings):
        for i in range(segments):
            n=(i+1)%segments;a=j*segments+i;b=j*segments+n;c=(j+1)*segments+n;d=(j+1)*segments+i
            tris.extend(((a,b,c),(a,c,d)));roles.extend(('pod_shell','pod_shell'))
    return MeshPayload(tuple(verts),tuple(tris),tuple(roles))


def _payload(node):
    if node.semantic_kind=='wall':return _wall_mesh(node.params)
    if node.semantic_kind in ('box','mechanical_part'):return _box_mesh(node.params,node.transform)
    if node.semantic_kind=='pod':return _pod_mesh(node.params)
    raise ValueError(f'tessellation not implemented for {node.semantic_kind}')

class TessellatedPreviewBackend(GeometryBackend):
    """Actual triangle geometry for 3D viewport; never claims fabrication quality."""
    name='tessellated-preview'
    def evaluate_plan(self,doc,plan)->GeometryEvaluation:
        contract=ContractBackend().evaluate_plan(doc,plan);issues=list(contract.issues);bodies=[]
        for node in plan.geometry_nodes():
            base=contract.body(node.entity_id)
            try:
                mesh=_payload(node)
                bodies.append(GeometryBody(node.entity_id,node.semantic_kind,base.surface_keys,base.modifier_ids,mesh,quality='preview-mesh',modifiers_applied=False))
            except Exception as exc:
                issues.append(GeometryIssue('warning','tessellation_unavailable',str(exc),node.entity_id))
        return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
