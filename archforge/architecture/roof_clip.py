"""A terrace slab on a room the storey above covers only in part: the slab is the uncovered part.

The covered part is the upper storey's rooms plus its walls (their full
thickness).  The room's slab outline is cut on the grid of all their
coordinates: one outline when the open part is one piece (an L, a strip),
else rectangles (e.g. a terrace all round a smaller upper floor).  Always
computed from the current drawing, so plan, 3D and quantities agree and
follow any change of the upper floor.
"""
from __future__ import annotations

import math

MIN_PART = 0.04            # m² — slivers smaller than this are dropped


def _inside(poly, x, y):
    hit = False
    n = len(poly)
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def upper_cover(doc, base_z, tolerance=1e-5):
    """Polygons the storey above ``base_z`` stands on: its rooms and its walls."""
    zs = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"})
    above = [z for z in zs if z > base_z + 0.5]
    if not above:
        return []
    z = above[0]
    out = []
    try:
        out += [[(float(p[0]), float(p[1])) for p in f.polygon] for f in doc.active_room_faces(z=z, tolerance=tolerance)]
    except Exception:
        pass
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - z) > 0.05:
            continue
        p = e.params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-9:
            continue
        t = float(p.get("thickness", 0.2)) / 2
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy * t, ux * t
        ax, ay, bx, by = ax - ux * t, ay - uy * t, bx + ux * t, by + uy * t
        out.append([(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)])
    return out


def _cells(outer, cover):
    xs = sorted({round(p[0], 5) for poly in [outer] + cover for p in poly})
    ys = sorted({round(p[1], 5) for poly in [outer] + cover for p in poly})
    ox0, ox1 = min(p[0] for p in outer), max(p[0] for p in outer)
    oy0, oy1 = min(p[1] for p in outer), max(p[1] for p in outer)
    xs = [x for x in xs if ox0 - 1e-6 <= x <= ox1 + 1e-6]
    ys = [y for y in ys if oy0 - 1e-6 <= y <= oy1 + 1e-6]
    keep, covered = set(), 0
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if not _inside(outer, cx, cy):
                continue
            if any(_inside(c, cx, cy) for c in cover):
                covered += 1
            else:
                keep.add((i, j))
    return xs, ys, keep, covered


def _loops(xs, ys, keep):
    edges = {}
    for i, j in keep:
        corners = [(xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])]
        for k in range(4):
            a, b = corners[k], corners[(k + 1) % 4]
            if (b, a) in edges:
                del edges[(b, a)]
            else:
                edges[(a, b)] = True
    nxt = {}
    for a, b in edges:
        nxt.setdefault(a, []).append(b)
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, cur = [start], start
        while True:
            b = nxt[cur].pop()
            if not nxt[cur]:
                del nxt[cur]
            if b == start:
                break
            loop.append(b)
            cur = b
            if cur not in nxt:
                return None                                  # ambiguous pinch: fall back to rectangles
        # Drop collinear points.
        clean = [p for k, p in enumerate(loop)
                 if abs((p[0] - loop[k - 1][0]) * (loop[(k + 1) % len(loop)][1] - p[1])
                        - (p[1] - loop[k - 1][1]) * (loop[(k + 1) % len(loop)][0] - p[0])) > 1e-9]
        loops.append(clean)
    return loops


def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) / 2


def _rectangles(xs, ys, keep):
    runs = {}
    for j in range(len(ys) - 1):
        i = 0
        while i < len(xs) - 1:
            if (i, j) in keep:
                k = i
                while (k + 1, j) in keep:
                    k += 1
                runs.setdefault((i, k), []).append(j)
                i = k + 1
            else:
                i += 1
    out = []
    for (i, k), rows in runs.items():
        rows.sort()
        start = prev = rows[0]
        for j in rows[1:] + [None]:
            if j is not None and j == prev + 1:
                prev = j
                continue
            out.append([(xs[i], ys[start]), (xs[k + 1], ys[start]), (xs[k + 1], ys[prev + 1]), (xs[i], ys[prev + 1])])
            if j is not None:
                start = prev = j
    return out


def open_parts(outer, cover):
    """The uncovered part of ``outer``: ``None`` if nothing covers it, ``[]`` if all is covered, else polygons."""
    outer = [(float(x), float(y)) for x, y in outer]
    if not cover:
        return None
    xs, ys, keep, covered = _cells(outer, cover)
    if not covered:
        return None
    if not keep:
        return []
    loops = _loops(xs, ys, keep)
    if loops is not None and len(loops) == 1 and _area(loops[0]) > 0:
        return [loops[0]]
    return [r for r in _rectangles(xs, ys, keep) if abs(_area(r)) >= MIN_PART]
