from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple
import math

from .backend import ContractBackend, GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue

Vec3 = Tuple[float, float, float]
Tri = Tuple[int, int, int]


@dataclass(frozen=True)
class MeshPayload:
    """Viewport tessellation retaining stable semantic ownership per triangle."""
    vertices: Tuple[Vec3, ...]
    triangles: Tuple[Tri, ...]
    triangle_surfaces: Tuple[str, ...]

    def __post_init__(self):
        if len(self.triangles) != len(self.triangle_surfaces):
            raise ValueError('each triangle must retain one semantic surface role')
        n = len(self.vertices)
        if any(i < 0 or i >= n for tri in self.triangles for i in tri):
            raise ValueError('triangle references a missing vertex')


def _area2(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly)))


def _inside_triangle(p, a, b, c):
    def cross(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    x, y, z = cross(a, b, p), cross(b, c, p), cross(c, a, p)
    return (x >= -1e-12 and y >= -1e-12 and z >= -1e-12) or (x <= 1e-12 and y <= 1e-12 and z <= 1e-12)


def _triangulate(points):
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < 3:
        raise ValueError('polygon needs at least three points')
    area = _area2(pts)
    if abs(area) <= 1e-12:
        raise ValueError('polygon area is zero')
    order = list(range(len(pts)))
    if area < 0:
        order.reverse()
    result = []
    guard = 0
    while len(order) > 3:
        guard += 1
        if guard > len(pts) * len(pts):
            raise ValueError('polygon cannot be triangulated')
        ear_found = False
        for j in range(len(order)):
            ia, ib, ic = order[j - 1], order[j], order[(j + 1) % len(order)]
            a, b, c = pts[ia], pts[ib], pts[ic]
            convex = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if convex <= 1e-12:
                continue
            if any(_inside_triangle(pts[k], a, b, c) for k in order if k not in (ia, ib, ic)):
                continue
            result.append((ia, ib, ic))
            del order[j]
            ear_found = True
            break
        if not ear_found:
            raise ValueError('polygon is self-intersecting or numerically invalid')
    result.append(tuple(order))
    return tuple(result)


def _wall_mesh(p) -> MeshPayload:
    x1, y1, z, x2, y2 = map(float, (p['x1'], p['y1'], p['z'], p['x2'], p['y2']))
    h, t = float(p['height']), float(p['thickness'])
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        raise ValueError('wall has zero length')
    nx, ny = -dy / length * t / 2.0, dx / length * t / 2.0
    v = ((x1 + nx, y1 + ny, z), (x2 + nx, y2 + ny, z),
         (x2 - nx, y2 - ny, z), (x1 - nx, y1 - ny, z),
         (x1 + nx, y1 + ny, z + h), (x2 + nx, y2 + ny, z + h),
         (x2 - nx, y2 - ny, z + h), (x1 - nx, y1 - ny, z + h))
    # Exterior is +normal of the wall centreline; interior is -normal. Winding is
    # deliberately outward so Pull means outward and Push means inward.
    faces = (((0,5,1),(0,4,5),'exterior'),
             ((3,2,6),(3,6,7),'interior'),
             ((4,5,6),(4,6,7),'top'),
             ((0,3,7),(0,7,4),'start'),
             ((1,5,6),(1,6,2),'end'),
             ((3,0,1),(3,1,2),'bottom'))
    tris, roles = [], []
    for a, b, role in faces:
        tris.extend((a,b)); roles.extend((role,role))
    return MeshPayload(v, tuple(tris), tuple(roles))


def _box_mesh(p, transform=None) -> MeshPayload:
    w, d, h = map(float, (p['width'], p['depth'], p['height']))
    local = [(0, 0, 0), (w, 0, 0), (w, d, 0), (0, d, 0),
             (0, 0, h), (w, 0, h), (w, d, h), (0, d, h)]
    if transform is not None:
        v = [tuple(sum(transform[r][c] * q[c] for c in range(3)) + transform[r][3] for r in range(3)) for q in local]
    else:
        a = math.radians(float(p.get('rotation', 0.0)))
        c, s = math.cos(a), math.sin(a)
        ox, oy, oz = map(float, (p['x'], p['y'], p['z']))
        v = [(ox + c*x - s*y, oy + s*x + c*y, oz + z) for x, y, z in local]
    quads = ((0, 1, 5, 4, 'front'), (1, 2, 6, 5, 'right'),
             (2, 3, 7, 6, 'back'), (3, 0, 4, 7, 'left'),
             (4, 5, 6, 7, 'top'), (3, 2, 1, 0, 'bottom'))
    tris, roles = [], []
    for a, b, c, d, role in quads:
        tris.extend(((a, b, c), (a, c, d)))
        roles.extend((role, role))
    return MeshPayload(tuple(v), tuple(tris), tuple(roles))


def _polygon_prism(points, z, thickness) -> MeshPayload:
    pts = [(float(x), float(y)) for x, y in points]
    z, thickness = float(z), float(thickness)
    if thickness <= 0:
        raise ValueError('thickness must be > 0')
    top_tris = _triangulate(pts)
    n = len(pts)
    verts = tuple((x, y, z) for x, y in pts) + tuple((x, y, z + thickness) for x, y in pts)
    tris, roles = [], []
    for a, b, c in top_tris:
        tris.append((a + n, b + n, c + n)); roles.append('top')
        tris.append((c, b, a)); roles.append('bottom')
    for i in range(n):
        j = (i + 1) % n
        tris.extend(((i, j, j+n), (i, j+n, i+n)))
        roles.extend(('edge', 'edge'))
    return MeshPayload(verts, tuple(tris), tuple(roles))


def _pod_mesh(p, segments=32, rings=12) -> MeshPayload:
    cx, cy, z = map(float, (p['cx'], p['cy'], p['floor_level']))
    rx, ry, rz = float(p['diameter_x']) / 2.0, float(p['diameter_y']) / 2.0, float(p['height'])
    verts = []
    for j in range(rings + 1):
        phi = (math.pi / 2.0) * (j / rings)
        radial, zz = math.cos(phi), z + rz * math.sin(phi)
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            verts.append((cx + rx * radial * math.cos(a), cy + ry * radial * math.sin(a), zz))
    tris, roles = [], []
    for j in range(rings):
        for i in range(segments):
            nxt = (i + 1) % segments
            a, b = j * segments + i, j * segments + nxt
            c, d = (j + 1) * segments + nxt, (j + 1) * segments + i
            tris.extend(((a, b, c), (a, c, d)))
            roles.extend(('pod_shell', 'pod_shell'))
    return MeshPayload(tuple(verts), tuple(tris), tuple(roles))


def _payload(doc, node):
    kind, p = node.semantic_kind, node.params
    if kind == 'wall': return _wall_mesh(p)
    if kind in ('box', 'mechanical_part'): return _box_mesh(p, node.transform)
    if kind == 'pod': return _pod_mesh(p)
    if kind == 'floor': return _polygon_prism(p['points'], p['z'], p['thickness'])
    if kind == 'room_floor':
        from archforge.architecture.rooms import room_floor_geometry
        g = room_floor_geometry(doc, doc.get(node.entity_id))
        if g is None: raise ValueError('room floor has no currently closed room')
        return _polygon_prism(g['points'], g['z'], g['thickness'])
    raise ValueError(f'tessellation not implemented for {kind}')


class TessellatedPreviewBackend(GeometryBackend):
    name = 'tessellated-preview'

    def evaluate_plan(self, doc, plan) -> GeometryEvaluation:
        contract = ContractBackend().evaluate_plan(doc, plan)
        issues = list(contract.issues); bodies: List[GeometryBody] = []
        for node in plan.geometry_nodes():
            base = contract.body(node.entity_id)
            try:
                mesh = _payload(doc, node)
                bodies.append(GeometryBody(node.entity_id,node.semantic_kind,base.surface_keys,
                                           base.modifier_ids,mesh,quality='preview-mesh',modifiers_applied=False))
            except Exception as exc:
                issues.append(GeometryIssue('warning','tessellation_unavailable',str(exc),node.entity_id))
        return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
