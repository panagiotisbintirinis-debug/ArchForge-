"""Each wall layer as its own band in plan: hatched by material, mitred at corners (spec §3 step 4, owner 30/10).

Shared by the plan (``core/plan_scene``), the section (``output/section_cut``) and the DXF export, so all three show
the same layers.  Plain geometry, no Qt.

* A layer is the band between two offsets of the wall axis; the exterior layer is on the outside face
  (``wall_face.outside_sign``), as ``wall_types.layer_lines``.
* **Corner (L)**: two walls whose axes end at the same point.  Every offset line runs on to the corner's bisector,
  so a layer meets the layer at the same depth of the other wall: the insulation goes round the corner unbroken
  (with equal build-ups; different ones still meet on the bisector).
* **T**: a wall that ends on another wall's side stops at that wall's face; the wall that goes on stays whole.
* Openings cut every band (the same cut as the wall fill).
* A wall end that meets nothing is square.

Joining order beyond that (e.g. a core that must run through a corner of two different build-ups) is not decided
here: the bisector is the rule for every pair.
"""
from __future__ import annotations

import math

TOL = 1e-3


def _axis(w):
    p = w.params
    a, b = (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))
    length = math.dist(a, b)
    if length < 1e-9:
        return None
    u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
    return a, b, u, (-u[1], u[0]), length, float(p.get("thickness", 0.2))


def _intersect(p, d, q, e):
    """Parameter s of p + d·s on the line q + e·r, or None when parallel."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12:
        return None
    return ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den


def _end_rule(w, axis, at_b, walls):
    """How the bands end at one end of ``w``: ``("miter", point, direction)`` / ``("face", point, direction)`` /
    None (square)."""
    a, b, u, n, length, t = axis
    p = b if at_b else a
    into = (-u[0], -u[1]) if at_b else u                      # from the end into this wall
    for o in walls:
        if o.id == w.id:
            continue
        oa = _axis(o)
        if oa is None:
            continue
        a2, b2, u2, n2, l2, t2 = oa
        for q, d2 in ((a2, u2), (b2, (-u2[0], -u2[1]))):
            if math.dist(p, q) <= TOL + 1e-9:
                s = (into[0] + d2[0], into[1] + d2[1])
                m = math.hypot(*s)
                if m < 1e-6 or abs(into[0] * d2[1] - into[1] * d2[0]) < 1e-6:
                    return None                                   # straight on (or folded back): square end
                return ("miter", p, (s[0] / m, s[1] / m))
    for o in walls:
        if o.id == w.id:
            continue
        oa = _axis(o)
        if oa is None:
            continue
        a2, b2, u2, n2, l2, t2 = oa
        along = (p[0] - a2[0]) * u2[0] + (p[1] - a2[1]) * u2[1]
        off = (p[0] - a2[0]) * n2[0] + (p[1] - a2[1]) * n2[1]
        if -TOL <= along <= l2 + TOL and abs(off) <= t2 / 2 + TOL:
            inside = (p[0] + into[0] * length / 2 - a2[0]) * n2[0] + (p[1] + into[1] * length / 2 - a2[1]) * n2[1]
            side = 1.0 if inside >= 0 else -1.0
            face = (a2[0] + n2[0] * side * t2 / 2, a2[1] + n2[1] * side * t2 / 2)
            return ("face", face, u2)
    return None


def _end_point(axis, at_b, rule, offset):
    a, b, u, n, length, t = axis
    p = b if at_b else a
    start = (p[0] + n[0] * offset, p[1] + n[1] * offset)
    if rule is None:
        return start
    s = _intersect(start, u, rule[1], rule[2])
    if s is None or abs(s) > max(1.0, 4 * t):                    # a near-parallel bisector: keep the end square
        return start
    return (start[0] + u[0] * s, start[1] + u[1] * s)


def offsets(doc, w):
    """``[(layer, outer offset, inner offset, index)]`` of a layered wall (offsets from the axis along its normal;
    ``index`` = the layer's place in its type, exterior first), else []."""
    from archforge.architecture.wall_face import outside_sign
    from archforge.architecture.wall_types import layers
    ls = layers(w.params.get("wall_type", "generic"), doc)
    if not ls:
        return []
    order = list(range(len(ls)))
    if outside_sign(doc, w.id) < 0:
        order.reverse()
    t = float(w.params.get("thickness", 0.2))
    total = sum(l[1] for l in ls)
    scale = t / total if total > 0 else 1.0
    out, o = [], t / 2
    for i in order:
        out.append((ls[i], o, o - ls[i][1] * scale, i))
        o -= ls[i][1] * scale
    return out


def _cuts(doc, w):
    from archforge.core.plan_scene import _opening_segment
    out = []
    t = float(w.params.get("thickness", 0.2)) / 2 + 0.01
    for o in doc.entities.values():
        if o.kind not in ("door", "window", "opening") or o.parent_id != w.id:
            continue
        seg = _opening_segment(doc, o)
        if seg is None:
            continue
        (ax, ay), (bx, by) = seg
        length = math.hypot(bx - ax, by - ay)
        if length <= 1e-9:
            continue
        nx, ny = -(by - ay) / length * t, (bx - ax) / length * t
        out.append([(ax - nx, ay - ny), (bx - nx, by - ny), (bx + nx, by + ny), (ax + nx, ay + ny)])
    return out


def _same_storey(doc, w):
    z = round(float(w.params.get("z", 0.0)), 4)
    return [e for e in doc.entities.values() if e.kind == "wall" and round(float(e.params.get("z", 0.0)), 4) == z]


def wall_bands(doc, w, walls=None):
    """``[{"layer", "index", "material", "hatch", "colour", "insulation", "islands": [(outer, holes)]}]``, side A
    first (``index``: the layer's place in its type)."""
    from archforge.construction.building_materials import material
    from archforge.geometry.regions import region
    axis = _axis(w)
    rows = offsets(doc, w)
    if axis is None or not rows:
        return []
    walls = _same_storey(doc, w) if walls is None else walls
    ra, rb = _end_rule(w, axis, False, walls), _end_rule(w, axis, True, walls)
    cuts = _cuts(doc, w)
    out = []
    for layer, o1, o2, index in rows:
        poly = [_end_point(axis, False, ra, o1), _end_point(axis, True, rb, o1),
                _end_point(axis, True, rb, o2), _end_point(axis, False, ra, o2)]
        islands = region([poly], cuts, tolerance=1e-6) if cuts else [(poly, [])]
        m = material(layer.material_id, doc)
        out.append({"layer": layer, "index": index, "material": m.id, "hatch": m.hatch, "colour": m.colour,
                    "insulation": m.insulation, "islands": islands})
    return out


def boundaries(doc, w, walls=None):
    """Plan lines between layers, mitred like the bands and broken at openings: ``[(points, insulation?)]``."""
    axis = _axis(w)
    rows = offsets(doc, w)
    if axis is None or len(rows) < 2:
        return []
    walls = _same_storey(doc, w) if walls is None else walls
    ra, rb = _end_rule(w, axis, False, walls), _end_rule(w, axis, True, walls)
    a, b, u, n, length, t = axis
    gaps = []
    for c in _cuts(doc, w):
        s = sorted(((q[0] - a[0]) * u[0] + (q[1] - a[1]) * u[1]) for q in c)
        gaps.append((s[0], s[-1]))
    out = []
    for k in range(len(rows) - 1):
        o = rows[k][2]
        insulation = rows[k][0][4] or rows[k + 1][0][4]
        p, q = _end_point(axis, False, ra, o), _end_point(axis, True, rb, o)
        s0 = (p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1]
        s1 = (q[0] - a[0]) * u[0] + (q[1] - a[1]) * u[1]
        pieces, cur = [], s0
        for g0, g1 in sorted(gaps):
            if g1 <= cur or g0 >= s1:
                continue
            if g0 > cur:
                pieces.append((cur, g0))
            cur = max(cur, g1)
        if cur < s1:
            pieces.append((cur, s1))
        for x0, x1 in pieces:
            if x1 - x0 > 1e-6:
                out.append(([(a[0] + u[0] * x0 + n[0] * o, a[1] + u[1] * x0 + n[1] * o),
                             (a[0] + u[0] * x1 + n[0] * o, a[1] + u[1] * x1 + n[1] * o)], insulation))
    return out
