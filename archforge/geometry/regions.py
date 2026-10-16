"""Plan regions with holes: union / difference of polygons, offsets, triangulation.

A slab is a plan *region*: one or more islands, each an outer loop with holes
(an atrium, an inner balcony, a stair well).  Everything here is plain 2D
geometry (no Qt, no Document):

* ``region_loops(polygons, inside)`` — the boundary of the region where
  ``inside(x, y)`` holds, traced on the arrangement of every polygon edge
  (edges split where they cross or overlap).  Robust for touching, shared and
  collinear edges, which is what room faces on wall axes are made of.  Loops
  keep the region on their left: outer loops counter-clockwise, holes clockwise.
* ``group_loops`` — loops grouped into islands ``(outer, [holes])``.
* ``offset_loop`` — every edge pushed outwards (to the right) by its own
  distance, mitred corners with a bevel limit, a step where two collinear
  edges have different distances.
* ``triangulate_with_holes`` — ear clipping after bridging each hole to the
  outer loop (hole bridging as in "earcut"); triangles index the input points.
* ``prism_with_holes`` — closed (watertight) slab solid: top, bottom, outer
  edges and the inner sides of every hole.
"""
from __future__ import annotations

import math
from typing import Callable, Iterable, List, Sequence, Tuple

Point = Tuple[float, float]
Loop = List[Point]
Island = Tuple[Loop, List[Loop]]

# A bevel replaces a mitre farther than this many offsets from its corner.
MITER_LIMIT = 4.0


def signed_area(poly: Sequence[Point]) -> float:
    n = len(poly)
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))


def point_in_polygon(x: float, y: float, poly: Sequence[Point]) -> bool:
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def winding(x: float, y: float, poly: Sequence[Point]) -> int:
    """Winding number of ``poly`` around (x, y) (+1 inside a counter-clockwise loop)."""
    w = 0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cross = (x2 - x1) * (y - y1) - (x - x1) * (y2 - y1)
        if y1 <= y < y2 and cross > 0:
            w += 1
        elif y2 <= y < y1 and cross < 0:
            w -= 1
    return w


def simplify(loop: Sequence[Point], tolerance: float = 1e-7) -> Loop:
    """Drop repeated points and vertices that only subdivide a straight edge."""
    pts = [(float(x), float(y)) for x, y in loop]
    changed = True
    while changed and len(pts) > 3:
        changed = False
        n = len(pts)
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            ab = math.hypot(b[0] - a[0], b[1] - a[1])
            if ab <= tolerance:
                del pts[i]
                changed = True
                break
            ac = math.hypot(c[0] - a[0], c[1] - a[1])
            if ac <= tolerance:
                continue                                  # a spike back to the same point: keep
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            dot = (b[0] - a[0]) * (c[0] - a[0]) + (b[1] - a[1]) * (c[1] - a[1])
            if abs(cross) / ac <= tolerance and 0.0 < dot < ac * ac:
                del pts[i]
                changed = True
                break
    return pts


def _segments(polygons: Iterable[Sequence[Point]], tolerance: float):
    out = []
    for poly in polygons:
        pts = [(float(x), float(y)) for x, y in poly]
        n = len(pts)
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            if math.hypot(b[0] - a[0], b[1] - a[1]) > tolerance:
                out.append((a, b))
    return out


def _split(segments, tolerance):
    """Cut every segment where another one crosses, touches or overlaps it."""
    cuts = [[0.0, 1.0] for _ in segments]
    for i, (a, b) in enumerate(segments):
        rx, ry = b[0] - a[0], b[1] - a[1]
        li = math.hypot(rx, ry)
        for j in range(i + 1, len(segments)):
            c, d = segments[j]
            sx, sy = d[0] - c[0], d[1] - c[1]
            lj = math.hypot(sx, sy)
            if max(a[0], b[0]) < min(c[0], d[0]) - tolerance or max(c[0], d[0]) < min(a[0], b[0]) - tolerance \
                    or max(a[1], b[1]) < min(c[1], d[1]) - tolerance or max(c[1], d[1]) < min(a[1], b[1]) - tolerance:
                continue
            den = rx * sy - ry * sx
            qx, qy = c[0] - a[0], c[1] - a[1]
            if abs(den) > 1e-12 * li * lj:
                t = (qx * sy - qy * sx) / den
                u = (qx * ry - qy * rx) / den
                if -tolerance / li <= t <= 1 + tolerance / li and -tolerance / lj <= u <= 1 + tolerance / lj:
                    cuts[i].append(min(1.0, max(0.0, t)))
                    cuts[j].append(min(1.0, max(0.0, u)))
                continue
            # Parallel: only collinear overlaps matter; each takes the other's end points.
            if abs(qx * ry - qy * rx) / li > tolerance:
                continue
            for p in (c, d):
                t = ((p[0] - a[0]) * rx + (p[1] - a[1]) * ry) / (li * li)
                if 0.0 < t < 1.0:
                    cuts[i].append(t)
            for p in (a, b):
                u = ((p[0] - c[0]) * sx + (p[1] - c[1]) * sy) / (lj * lj)
                if 0.0 < u < 1.0:
                    cuts[j].append(u)
    return cuts


def region_loops(polygons: Iterable[Sequence[Point]], inside: Callable[[float, float], bool],
                 tolerance: float = 1e-6) -> List[Loop]:
    """Boundary loops of ``{p : inside(p)}``, traced on the edges of ``polygons``.

    ``polygons`` must contain every edge where ``inside`` changes value.
    Region on the left of each loop; collinear vertices removed.
    """
    segments = _segments(polygons, tolerance)
    if not segments:
        return []
    cuts = _split(segments, tolerance)
    nodes: List[Point] = []
    grid = {}
    cell = tolerance * 10.0

    def node(p):
        kx, ky = int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for k in grid.get((kx + dx, ky + dy), ()):
                    if math.hypot(nodes[k][0] - p[0], nodes[k][1] - p[1]) <= tolerance:
                        return k
        nodes.append((float(p[0]), float(p[1])))
        grid.setdefault((kx, ky), []).append(len(nodes) - 1)
        return len(nodes) - 1

    edges = set()
    for (a, b), ts in zip(segments, cuts):
        ts = sorted(set(ts))
        prev = None
        for t in ts:
            k = node((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            if prev is not None and k != prev:
                edges.add((min(prev, k), max(prev, k)))
            prev = k
    # Keep each edge once, directed with the region on its left.
    directed = {}
    for i, j in edges:
        (ax, ay), (bx, by) = nodes[i], nodes[j]
        length = math.hypot(bx - ax, by - ay)
        mx, my = (ax + bx) / 2, (ay + by) / 2
        eps = min(1e-4, length / 4)
        nx, ny = -(by - ay) / length * eps, (bx - ax) / length * eps
        left, right = bool(inside(mx + nx, my + ny)), bool(inside(mx - nx, my - ny))
        if left and not right:
            directed.setdefault(i, []).append(j)
        elif right and not left:
            directed.setdefault(j, []).append(i)
    loops = []
    while directed:
        u = next(iter(directed))
        start = u
        v = directed[u].pop()
        if not directed[u]:
            del directed[u]
        loop = [u]
        guard = len(edges) + 2
        while v != start and guard > 0:
            guard -= 1
            loop.append(v)
            outs = directed.get(v)
            if not outs:
                loop = []
                break
            if len(outs) == 1:
                w = outs.pop()
            else:
                # Several ways on (two islands touching at a corner): the leftmost turn closes the smallest loop.
                rx, ry = nodes[u][0] - nodes[v][0], nodes[u][1] - nodes[v][1]
                back = math.atan2(ry, rx)

                def clockwise(k):
                    a = math.atan2(nodes[k][1] - nodes[v][1], nodes[k][0] - nodes[v][0])
                    turn = (back - a) % (2 * math.pi)
                    return turn if turn > 1e-12 else 2 * math.pi
                w = min(outs, key=clockwise)
                outs.remove(w)
            if not outs:
                directed.pop(v, None)
            u, v = v, w
        if len(loop) >= 3:
            pts = simplify([nodes[k] for k in loop], tolerance)
            if len(pts) >= 3 and abs(signed_area(pts)) > tolerance * tolerance * 10:
                loops.append(pts)
    return loops


def group_loops(loops: Iterable[Sequence[Point]]) -> List[Island]:
    """Islands ``(outer, holes)``: each hole goes to the smallest outer loop around it."""
    outers = [list(lp) for lp in loops if signed_area(lp) > 0]
    holes = [list(lp) for lp in loops if signed_area(lp) < 0]
    islands = [(o, []) for o in sorted(outers, key=signed_area, reverse=True)]
    for h in holes:
        # A point just beside the hole (on its left = the slab side).
        (ax, ay), (bx, by) = h[0], h[1]
        length = math.hypot(bx - ax, by - ay) or 1.0
        px, py = (ax + bx) / 2 - (by - ay) / length * 1e-5, (ay + by) / 2 + (bx - ax) / length * 1e-5
        owners = [isl for isl in islands if point_in_polygon(px, py, isl[0])]
        if owners:
            min(owners, key=lambda isl: signed_area(isl[0]))[1].append(h)
    return islands


def region(adds: Iterable[Sequence[Point]], subs: Iterable[Sequence[Point]] = (),
           tolerance: float = 1e-6) -> List[Island]:
    """Union of ``adds`` minus every polygon of ``subs`` (nonzero winding for both)."""
    adds = [[(float(x), float(y)) for x, y in p] for p in adds if len(p) >= 3]
    subs = [[(float(x), float(y)) for x, y in p] for p in subs if len(p) >= 3]
    if not adds:
        return []

    def inside(x, y):
        return sum(winding(x, y, p) * (1 if signed_area(p) > 0 else -1) for p in adds) > 0 \
            and not any(winding(x, y, p) for p in subs)
    return group_loops(region_loops(adds + subs, inside, tolerance))


def islands_area(islands: Iterable[Island]) -> float:
    return sum(abs(signed_area(o)) - sum(abs(signed_area(h)) for h in hs) for o, hs in islands)


def offset_loop(loop: Sequence[Point], distances: Sequence[float], tolerance: float = 1e-9) -> Loop:
    """Push edge i (loop[i] → loop[i+1]) to its right by ``distances[i]``."""
    pts = [(float(x), float(y)) for x, y in loop]
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        nx, ny = dy / length, -dx / length
        o = float(distances[i])
        lines.append(((a[0] + nx * o, a[1] + ny * o), (dx, dy), (nx, ny), o))
    out = []
    for i in range(n):
        p0, d0, n0, o0 = lines[i - 1]
        p1, d1, n1, o1 = lines[i]
        v = pts[i]
        b0 = (v[0] + n0[0] * o0, v[1] + n0[1] * o0)
        b1 = (v[0] + n1[0] * o1, v[1] + n1[1] * o1)
        den = d0[0] * d1[1] - d0[1] * d1[0]
        if abs(den) <= 1e-12 * math.hypot(*d0) * math.hypot(*d1):
            out.append(b0)
            if math.hypot(b1[0] - b0[0], b1[1] - b0[1]) > tolerance:
                out.append(b1)                            # collinear edges, different distances: a step
            continue
        t = ((p1[0] - p0[0]) * d1[1] - (p1[1] - p0[1]) * d1[0]) / den
        corner = (p0[0] + t * d0[0], p0[1] + t * d0[1])
        if math.hypot(corner[0] - v[0], corner[1] - v[1]) > MITER_LIMIT * max(abs(o0), abs(o1), 1e-3):
            out.append(b0)
            if math.hypot(b1[0] - b0[0], b1[1] - b0[1]) > tolerance:
                out.append(b1)
            continue
        out.append(corner)
    return out


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _segments_cross(p, q, a, b, eps=1e-12):
    """True when segment p-q meets segment a-b anywhere but at a shared end point."""
    shared = {tuple(p), tuple(q)} & {tuple(a), tuple(b)}
    d1, d2, d3, d4 = _cross(p, q, a), _cross(p, q, b), _cross(a, b, p), _cross(a, b, q)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    if shared:
        return False

    def on(s, t, r):
        return abs(_cross(s, t, r)) <= eps and min(s[0], t[0]) - eps <= r[0] <= max(s[0], t[0]) + eps \
            and min(s[1], t[1]) - eps <= r[1] <= max(s[1], t[1]) + eps
    return on(p, q, a) or on(p, q, b) or on(a, b, p) or on(a, b, q)


def _in_wedge(pts, ring, k, target):
    """Is direction ring[k] → target inside the polygon's corner at ring[k] (counter-clockwise ring)?"""
    p = pts[ring[k]]
    prev, nxt = pts[ring[k - 1]], pts[ring[(k + 1) % len(ring)]]
    a_next = math.atan2(nxt[1] - p[1], nxt[0] - p[0])
    a_prev = math.atan2(prev[1] - p[1], prev[0] - p[0])
    a_t = math.atan2(target[1] - p[1], target[0] - p[0])
    sweep = (a_prev - a_next) % (2 * math.pi) or 2 * math.pi
    return 1e-12 < (a_t - a_next) % (2 * math.pi) < sweep - 1e-12


def triangulate_with_holes(outer: Sequence[Point], holes: Sequence[Sequence[Point]] = ()):
    """``(points, triangles)``: points = outer + holes in input order, counter-clockwise triangles."""
    outer = [(float(x), float(y)) for x, y in outer]
    holes = [[(float(x), float(y)) for x, y in h] for h in holes if len(h) >= 3]
    pts = list(outer)
    ring = list(range(len(outer)))
    if signed_area(outer) < 0:
        ring.reverse()
    hole_rings = []
    for h in holes:
        start = len(pts)
        pts.extend(h)
        idx = list(range(start, start + len(h)))
        if signed_area(h) > 0:
            idx.reverse()
        hole_rings.append(idx)
    hole_rings.sort(key=lambda idx: -max(pts[i][0] for i in idx))
    for done, idx in enumerate(hole_rings):
        m_pos = max(range(len(idx)), key=lambda k: (pts[idx[k]][0], -pts[idx[k]][1]))
        m = pts[idx[m_pos]]
        others = [r for r in hole_rings[done + 1:]]
        best = None
        for k in sorted(range(len(ring)), key=lambda k: math.hypot(pts[ring[k]][0] - m[0], pts[ring[k]][1] - m[1])):
            p = pts[ring[k]]
            if p == m or not _in_wedge(pts, ring, k, m):
                continue
            blocked = False
            for e in range(len(ring)):
                a, b = pts[ring[e]], pts[ring[(e + 1) % len(ring)]]
                if p in (a, b) and m not in (a, b) and _cross(a, b, m) != 0:
                    continue
                if _segments_cross(p, m, a, b):
                    blocked = True
                    break
            if not blocked:
                for r in [idx] + others:
                    for e in range(len(r)):
                        a, b = pts[r[e]], pts[r[(e + 1) % len(r)]]
                        if m in (a, b):
                            continue
                        if _segments_cross(p, m, a, b):
                            blocked = True
                            break
                    if blocked:
                        break
            if not blocked:
                best = k
                break
        if best is None:
            raise ValueError('hole cannot be bridged to the slab outline')
        cycle = idx[m_pos:] + idx[:m_pos]
        ring = ring[:best + 1] + cycle + [idx[m_pos], ring[best]] + ring[best + 1:]
    tris = []
    eps = 1e-14
    while len(ring) > 3:
        n = len(ring)
        found = False
        for j in range(n):
            ia, ib, ic = ring[j - 1], ring[j], ring[(j + 1) % n]
            a, b, c = pts[ia], pts[ib], pts[ic]
            if _cross(a, b, c) <= eps:
                continue
            blocked = False
            for k in range(n):
                q = pts[ring[k]]
                if q == a or q == b or q == c:
                    continue
                if _cross(a, b, q) >= -eps and _cross(b, c, q) >= -eps and _cross(c, a, q) >= -eps:
                    blocked = True
                    break
            if blocked:
                continue
            tris.append((ia, ib, ic))
            del ring[j]
            found = True
            break
        if not found:
            # Only zero-area corners left (a bridge doubling back): drop one of them.
            for j in range(n):
                a, b, c = pts[ring[j - 1]], pts[ring[j]], pts[ring[(j + 1) % n]]
                if abs(_cross(a, b, c)) <= 1e-12 and (b == a or b == c or
                                                     (b[0] - a[0]) * (c[0] - b[0]) + (b[1] - a[1]) * (c[1] - b[1]) < 0):
                    del ring[j]
                    found = True
                    break
            if not found:
                raise ValueError('slab outline cannot be triangulated')
    if len(ring) == 3 and _cross(pts[ring[0]], pts[ring[1]], pts[ring[2]]) > eps:
        tris.append(tuple(ring))
    return pts, tris


def prism_with_holes(islands: Iterable[Island], z: float, thickness: float, edge_role: str = 'edge',
                     hole_role: str = 'edge'):
    """``(vertices, triangles, roles)`` of a closed slab of the islands between z and z + thickness."""
    verts, tris, roles = [], [], []
    z0, z1 = float(z), float(z) + float(thickness)
    for outer, holes in islands:
        outer = simplify(outer)
        holes = [simplify(h) for h in holes]
        if signed_area(outer) < 0:
            outer = outer[::-1]
        holes = [h if signed_area(h) < 0 else h[::-1] for h in holes if len(h) >= 3]
        pts, top = triangulate_with_holes(outer, holes)
        base = len(verts)
        n = len(pts)
        verts.extend((x, y, z0) for x, y in pts)
        verts.extend((x, y, z1) for x, y in pts)
        for a, b, c in top:
            tris.append((base + n + a, base + n + b, base + n + c))
            tris.append((base + c, base + b, base + a))
            roles.extend(('top', 'bottom'))
        start = 0
        for k, loop in enumerate([outer] + holes):
            m = len(loop)
            for i in range(m):
                a, b = base + start + i, base + start + (i + 1) % m
                tris.append((a, b, b + n))
                tris.append((a, b + n, a + n))
                roles.extend((edge_role if k == 0 else hole_role,) * 2)
            start += m
    return tuple(verts), tuple(tris), tuple(roles)
