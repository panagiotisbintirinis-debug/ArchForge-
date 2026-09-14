from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
import math

from .mesh import MeshPayload
from .selection import SurfaceHit

Vec3 = Tuple[float, float, float]


@dataclass(frozen=True)
class MeshRayHit:
    entity_id: str
    triangle_index: int
    surface_role: str
    distance: float
    world_point: Vec3
    world_normal: Vec3


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def _scale(a: Vec3, s: float) -> Vec3:
    return (a[0]*s, a[1]*s, a[2]*s)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _normalize(v: Vec3) -> Vec3:
    n = math.sqrt(_dot(v, v))
    if n <= 1e-12:
        raise ValueError('cannot normalize zero vector')
    return (v[0]/n, v[1]/n, v[2]/n)


def _ray_triangle(origin: Vec3, direction: Vec3, a: Vec3, b: Vec3, c: Vec3) -> Optional[float]:
    """Return positive ray distance using Moller-Trumbore, or None."""
    e1, e2 = _sub(b, a), _sub(c, a)
    p = _cross(direction, e2)
    det = _dot(e1, p)
    if abs(det) <= 1e-12:
        return None
    inv = 1.0/det
    tvec = _sub(origin, a)
    u = _dot(tvec, p)*inv
    if u < -1e-12 or u > 1.0+1e-12:
        return None
    q = _cross(tvec, e1)
    v = _dot(direction, q)*inv
    if v < -1e-12 or u+v > 1.0+1e-12:
        return None
    t = _dot(e2, q)*inv
    return t if t >= 0.0 else None


def raycast_mesh(entity_id: str, mesh: MeshPayload, origin: Vec3, direction: Vec3) -> Optional[MeshRayHit]:
    d = _normalize(tuple(map(float, direction)))
    o = tuple(map(float, origin))
    best = None
    for idx, tri in enumerate(mesh.triangles):
        a, b, c = (mesh.vertices[i] for i in tri)
        t = _ray_triangle(o, d, a, b, c)
        if t is None or (best is not None and t >= best.distance):
            continue
        normal = _normalize(_cross(_sub(b, a), _sub(c, a)))
        best = MeshRayHit(entity_id, idx, mesh.triangle_surfaces[idx], t, _add(o, _scale(d, t)), normal)
    return best


def surface_hit_from_raycast(doc, hit: MeshRayHit) -> SurfaceHit:
    """Discard transient triangle identity and persist only semantic surface intent."""
    surface = SurfaceHit(hit.entity_id, hit.surface_role, hit.world_point, hit.world_normal)
    surface.validate(doc)
    return surface


def raycast_evaluation(doc, evaluation, origin: Vec3, direction: Vec3) -> Optional[SurfaceHit]:
    """Pick nearest deformable semantic surface from a tessellated evaluation."""
    candidates = []
    for body in evaluation.bodies:
        if not isinstance(body.payload, MeshPayload):
            continue
        raw = raycast_mesh(body.entity_id, body.payload, origin, direction)
        if raw is None:
            continue
        try:
            semantic = surface_hit_from_raycast(doc, raw)
        except ValueError:
            continue
        candidates.append((raw.distance, semantic))
    return min(candidates, key=lambda x: x[0])[1] if candidates else None
