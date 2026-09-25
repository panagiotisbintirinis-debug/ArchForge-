from __future__ import annotations

from typing import Dict, List, Tuple
import math

from .backend import GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue
from .mesh import MeshPayload, TessellatedPreviewBackend
from .wall_detail import detailed_wall_geometry
from .surface_frame import resolve_modifier_for_node

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
    return x*x*(3.0-2.0*x)


def _surface_vertex_normals(mesh: MeshPayload, role: str) -> Dict[int,Vec3]:
    accum: Dict[int,Vec3]={}
    for idx,tri in enumerate(mesh.triangles):
        if mesh.triangle_surfaces[idx]!=role: continue
        a,b,c=(mesh.vertices[i] for i in tri)
        n=_normal(_cross(_sub(b,a),_sub(c,a)))
        for vi in tri: accum[vi]=_add(accum.get(vi,(0.0,0.0,0.0)),n)
    return {vi:_normal(v) for vi,v in accum.items()}


def _surface_neighbors(mesh: MeshPayload, role: str) -> Dict[int,set]:
    out: Dict[int,set]={}
    for idx,tri in enumerate(mesh.triangles):
        if mesh.triangle_surfaces[idx]!=role: continue
        for a in tri:
            out.setdefault(a,set()).update(b for b in tri if b!=a)
    return out


def apply_brush_modifier(mesh: MeshPayload, raw: dict) -> MeshPayload:
    """Apply one non-destructive viewport sculpt modifier on a semantic surface."""
    op=str(raw.get('operation',''))
    supported=('pull','push','inflate','recess','smooth','crease')
    if op not in supported:
        raise ValueError(f'preview mesh sculpt does not yet support {op}')
    target=raw.get('target') or {}; role=str(target.get('surface_role',''))
    region=target.get('subregion') or {}
    center=tuple(map(float,region.get('world_center',())))
    if len(center)!=3: raise ValueError('sculpt modifier requires world_center')
    radius=float(region.get('radius',0.0)); strength=float(region.get('strength',1.0)); falloff=str(region.get('falloff','smooth'))
    amount=float((raw.get('params') or {}).get('amount',0.0))
    if radius<=0 or amount<0 or not 0<=strength<=1: raise ValueError('invalid sculpt radius, strength, or amount')
    normals=_surface_vertex_normals(mesh,role)
    if not normals: raise ValueError(f'mesh exposes no triangles for semantic surface {role!r}')
    verts=list(mesh.vertices)

    if op=='smooth':
        neighbors=_surface_neighbors(mesh,role); source=tuple(verts)
        for vi in normals:
            distance=_length(_sub(source[vi],center)); w=_falloff(distance,radius,falloff)*strength
            ns=neighbors.get(vi,set())
            if w>0 and ns:
                avg=tuple(sum(source[j][k] for j in ns)/len(ns) for k in range(3))
                alpha=min(1.0,amount*w)
                verts[vi]=_add(source[vi],_scale(_sub(avg,source[vi]),alpha))
        return MeshPayload(tuple(verts),mesh.triangles,mesh.triangle_surfaces)

    sign=-1.0 if op in ('push','recess') else 1.0
    for vi,n in normals.items():
        distance=_length(_sub(verts[vi],center)); w=_falloff(distance,radius,falloff)*strength
        if op=='crease': w=w*w
        if w>0: verts[vi]=_add(verts[vi],_scale(n,sign*amount*w))
    return MeshPayload(tuple(verts),mesh.triangles,mesh.triangle_surfaces)


class SculptedPreviewBackend(GeometryBackend):
    """Preview backend that densifies only walls that actually need sculpt detail."""
    name='sculpted-preview'

    def __init__(self, *, dense_entity_ids=(), wall_target_step:float=.15):
        self.dense_entity_ids={str(eid) for eid in dense_entity_ids}
        self.wall_target_step=float(wall_target_step)
        if not math.isfinite(self.wall_target_step) or self.wall_target_step<=0:
            raise ValueError('wall_target_step must be finite and > 0')

    def _sculpt_base_mesh(self,node,body):
        needs_dense=(
            node.semantic_kind=='wall'
            and (
                bool(node.modifiers)
                or node.entity_id in self.dense_entity_ids
            )
        )
        if not needs_dense:
            return body.payload
        vertices,triangles,roles=detailed_wall_geometry(
            node.params,
            target_step=self.wall_target_step,
        )
        return MeshPayload(vertices,triangles,roles)

    def evaluate_plan(self,doc,plan)->GeometryEvaluation:
        base=TessellatedPreviewBackend().evaluate_plan(doc,plan);issues=list(base.issues);bodies:List[GeometryBody]=[]
        for node in plan.geometry_nodes():
            try: body=base.body(node.entity_id)
            except KeyError: continue
            mesh=self._sculpt_base_mesh(node,body);applied=[];failed=False
            for raw in node.modifiers:
                if not raw.get('enabled',True): continue
                try:
                    resolved=resolve_modifier_for_node(doc,node,raw)
                    mesh=apply_brush_modifier(mesh,resolved);applied.append(str(raw.get('id','')))
                except Exception as exc:
                    failed=True;issues.append(GeometryIssue('warning','preview_modifier_unapplied',str(exc),node.entity_id))
            bodies.append(GeometryBody(node.entity_id,node.semantic_kind,body.surface_keys,tuple(applied),mesh,
                                       quality='sculpted-preview-mesh',modifiers_applied=not failed,
                                       watertight=None,manifold=None))
        return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
