from __future__ import annotations

from typing import Dict, List, Tuple
import math

from .backend import GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue
from .mesh import MeshPayload, TessellatedPreviewBackend

Vec3 = Tuple[float, float, float]


def _add(a,b): return (a[0]+b[0],a[1]+b[1],a[2]+b[2])
def _sub(a,b): return (a[0]-b[0],a[1]-b[1],a[2]-b[2])
def _scale(a,s): return (a[0]*s,a[1]*s,a[2]*s)
def _dot(a,b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def _cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _length(a): return math.sqrt(_dot(a,a))
def _normal(a):
    n=_length(a)
    return (0.0,0.0,0.0) if n<=1e-12 else (a[0]/n,a[1]/n,a[2]/n)


def _falloff(distance: float, radius: float, kind: str) -> float:
    if distance >= radius: return 0.0
    x=max(0.0,min(1.0,1.0-distance/radius))
    if kind=='constant': return 1.0
    if kind=='linear': return x
    if kind=='sharp': return x*x
    # smoothstep from edge(0) to center(1)
    return x*x*(3.0-2.0*x)


def _surface_vertex_normals(mesh: MeshPayload, role: str) -> Dict[int,Vec3]:
    accum: Dict[int,Vec3]={}
    for idx,tri in enumerate(mesh.triangles):
        if mesh.triangle_surfaces[idx]!=role: continue
        a,b,c=(mesh.vertices[i] for i in tri)
        n=_normal(_cross(_sub(b,a),_sub(c,a)))
        for vi in tri: accum[vi]=_add(accum.get(vi,(0.0,0.0,0.0)),n)
    return {vi:_normal(v) for vi,v in accum.items()}


def apply_brush_modifier(mesh: MeshPayload, raw: dict) -> MeshPayload:
    """Apply one non-destructive preview modifier to vertices of its semantic surface.

    This is deliberately a preview evaluator. It demonstrates the complete semantic
    sculpt chain but is not a CAD boolean or fabrication-quality remesher.
    """
    op=str(raw.get('operation',''))
    if op not in ('pull','push'):
        raise ValueError(f'preview mesh sculpt does not yet support {op}')
    target=raw.get('target') or {}; role=str(target.get('surface_role',''))
    region=target.get('subregion') or {}
    center=tuple(map(float,region.get('world_center',())))
    if len(center)!=3: raise ValueError('sculpt modifier requires world_center')
    radius=float(region.get('radius',0.0)); strength=float(region.get('strength',1.0)); falloff=str(region.get('falloff','smooth'))
    amount=float((raw.get('params') or {}).get('amount',0.0))
    if radius<=0 or amount<0: raise ValueError('invalid sculpt radius or amount')
    sign=1.0 if op=='pull' else -1.0
    normals=_surface_vertex_normals(mesh,role)
    if not normals: raise ValueError(f'mesh exposes no triangles for semantic surface {role!r}')
    verts=list(mesh.vertices)
    for vi,n in normals.items():
        distance=_length(_sub(verts[vi],center));w=_falloff(distance,radius,falloff)*strength
        if w>0: verts[vi]=_add(verts[vi],_scale(n,sign*amount*w))
    return MeshPayload(tuple(verts),mesh.triangles,mesh.triangle_surfaces)


class SculptedPreviewBackend(GeometryBackend):
    """Tessellated viewport backend with ordered pull/push modifiers evaluated."""
    name='sculpted-preview'

    def evaluate_plan(self,doc,plan)->GeometryEvaluation:
        base=TessellatedPreviewBackend().evaluate_plan(doc,plan);issues=list(base.issues);bodies:List[GeometryBody]=[]
        for node in plan.geometry_nodes():
            try: body=base.body(node.entity_id)
            except KeyError: continue
            mesh=body.payload;applied=[];failed=False
            for raw in node.modifiers:
                if not raw.get('enabled',True): continue
                try:
                    mesh=apply_brush_modifier(mesh,raw);applied.append(str(raw.get('id','')))
                except Exception as exc:
                    failed=True;issues.append(GeometryIssue('warning','preview_modifier_unapplied',str(exc),node.entity_id))
            bodies.append(GeometryBody(node.entity_id,node.semantic_kind,body.surface_keys,tuple(applied),mesh,
                                       quality='sculpted-preview-mesh',modifiers_applied=not failed,
                                       watertight=None,manifold=None))
        return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
