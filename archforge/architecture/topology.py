from __future__ import annotations

from dataclasses import dataclass
from math import atan2, hypot
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass(frozen=True)
class WallEdge:
    wall_id: str
    a: int
    b: int


@dataclass
class WallGraph:
    nodes: List[Point]
    edges: List[WallEdge]


def _dist(a: Point, b: Point) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _signed_area(poly: Sequence[Point]) -> float:
    return 0.5 * sum(
        poly[i][0] * poly[(i + 1) % len(poly)][1]
        - poly[(i + 1) % len(poly)][0] * poly[i][1]
        for i in range(len(poly))
    )


def polygon_area(poly: Sequence[Point]) -> float:
    return abs(_signed_area(poly))


def build_wall_graph(doc, tolerance: float = 1e-6, z: Optional[float] = None) -> WallGraph:
    """Build a 2D connectivity graph from visible semantic walls.

    Wall endpoints within ``tolerance`` are treated as the same topological node.
    If ``z`` is given, only walls whose base elevation matches it within tolerance are used.
    """
    if tolerance <= 0:
        raise ValueError('tolerance must be > 0')

    nodes: List[Point] = []
    edges: List[WallEdge] = []

    def node_for(p: Point) -> int:
        for i, q in enumerate(nodes):
            if _dist(p, q) <= tolerance:
                return i
        nodes.append((float(p[0]), float(p[1])))
        return len(nodes) - 1

    for eid, e in doc.entities.items():
        if e.kind != 'wall' or not e.visible:
            continue
        p = e.params
        if z is not None and abs(float(p['z']) - float(z)) > tolerance:
            continue
        a = (float(p['x1']), float(p['y1']))
        b = (float(p['x2']), float(p['y2']))
        if _dist(a, b) <= tolerance:
            continue
        ia = node_for(a)
        ib = node_for(b)
        if ia != ib:
            edges.append(WallEdge(eid, ia, ib))
    return WallGraph(nodes, edges)


def connected_components(graph: WallGraph) -> List[List[int]]:
    adj: Dict[int, List[int]] = {i: [] for i in range(len(graph.nodes))}
    for e in graph.edges:
        adj[e.a].append(e.b)
        adj[e.b].append(e.a)
    out: List[List[int]] = []
    seen = set()
    for start in range(len(graph.nodes)):
        if start in seen:
            continue
        stack = [start]
        comp: List[int] = []
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            comp.append(n)
            stack.extend(adj[n])
        out.append(comp)
    return out


def _halfedge_faces(graph: WallGraph) -> List[List[int]]:
    """Traverse planar straight-line graph faces using angularly ordered half-edges."""
    adjacency: Dict[int, List[int]] = {i: [] for i in range(len(graph.nodes))}
    for e in graph.edges:
        if e.b not in adjacency[e.a]:
            adjacency[e.a].append(e.b)
        if e.a not in adjacency[e.b]:
            adjacency[e.b].append(e.a)

    for n, nbrs in adjacency.items():
        x, y = graph.nodes[n]
        nbrs.sort(key=lambda m: atan2(graph.nodes[m][1] - y, graph.nodes[m][0] - x))

    visited = set()
    faces: List[List[int]] = []
    max_steps = max(1, 2 * len(graph.edges) + 5)

    for u, nbrs in adjacency.items():
        for v in nbrs:
            if (u, v) in visited:
                continue
            start = (u, v)
            cu, cv = start
            face: List[int] = []
            for _ in range(max_steps):
                if (cu, cv) in visited:
                    if (cu, cv) == start:
                        break
                    face = []
                    break
                visited.add((cu, cv))
                face.append(cu)
                around = adjacency.get(cv, [])
                if not around or cu not in around:
                    face = []
                    break
                # To keep the face on the left, take the neighbor immediately clockwise
                # from the incoming reverse edge in the CCW-sorted fan.
                idx = around.index(cu)
                nw = around[(idx - 1) % len(around)]
                cu, cv = cv, nw
                if (cu, cv) == start:
                    break
            else:
                face = []

            if len(face) >= 3 and (cu, cv) == start:
                faces.append(face)
    return faces


def closed_room_polygons(doc, tolerance: float = 1e-6, z: Optional[float] = None, min_area: float = 1e-6) -> List[List[Point]]:
    """Return bounded closed faces formed by connected walls.

    The result is purely derived topology; it does not create persistent room entities.
    Polygons are returned counter-clockwise and duplicate faces are removed.
    """
    graph = build_wall_graph(doc, tolerance=tolerance, z=z)
    raw = _halfedge_faces(graph)
    rooms: List[List[Point]] = []
    seen = set()

    for face in raw:
        poly = [graph.nodes[i] for i in face]
        area = _signed_area(poly)
        # With this traversal convention bounded faces are CCW; the unbounded face is CW.
        if area <= min_area:
            continue
        # Canonical cycle key, invariant to rotation.
        ids = list(face)
        rotations = [tuple(ids[i:] + ids[:i]) for i in range(len(ids))]
        key = min(rotations)
        if key in seen:
            continue
        seen.add(key)
        rooms.append(poly)

    rooms.sort(key=lambda p: (round(polygon_area(p), 12), tuple(p)))
    return rooms


def room_metrics(poly: Sequence[Point]) -> Dict[str, object]:
    if len(poly) < 3:
        raise ValueError('room polygon needs at least 3 points')
    area_signed = _signed_area(poly)
    area = abs(area_signed)
    if area <= 0:
        raise ValueError('room polygon area must be > 0')
    perimeter = sum(_dist(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))
    c = 1.0 / (6.0 * area_signed)
    cx = c * sum(
        (poly[i][0] + poly[(i + 1) % len(poly)][0])
        * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1])
        for i in range(len(poly))
    )
    cy = c * sum(
        (poly[i][1] + poly[(i + 1) % len(poly)][1])
        * (poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1])
        for i in range(len(poly))
    )
    return {'area': area, 'perimeter': perimeter, 'centroid': (cx, cy)}
