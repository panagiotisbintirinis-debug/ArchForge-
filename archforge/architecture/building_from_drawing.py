"""A storey of a building from its plan drawing (owner 22/10: «να δώσει πλήρη απεικόνιση σε 3D»).

From one plan underlay (architecture/walls_from_lines.py + project/drawing_text.py):

* walls — pairs of dark lines;
* doors and windows — each «w: 0.90 | h: 2.30» label (window when it has «s:» = sill) goes to the gap between two
  collinear walls of the same thickness, about that wide, next to the label; the two walls become one wall with
  the opening in it.  CAD plans break the wall lines at every opening, so the gap is where the label says;
* room names — «BEDROOM / 9.60 sq.m.» names the room around it (Greek name and use, drawing_text.greek_room).

Pure geometry: lists in, lists out; ui/building_from_underlay.py turns them into entities (one undo).
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Tuple

ANGLE_TOL = math.radians(2.0)
AXIS_TOL = 0.05          # the two walls' axes are this close (m)
THICK_TOL = 0.05
GAP_SHORT = 0.20         # the drawn gap may be this much narrower than the label …
GAP_LONG = 0.40          # … or this much wider (frame, reveals)
REACH = 1.6              # the label is written within this distance of its gap (m)


@dataclass
class Opening:
    kind: str            # door / window
    centre: Tuple[float, float]
    width: float
    height: float
    sill: float
    label: object = None


def _dir(a, b):
    L = math.dist(a, b)
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L), L


def _gap(wa, wb, axis_tol=AXIS_TOL):
    """(gap start, gap end, merged wall) when wa and wb lie on one axis with a gap between them, else None."""
    (a1, a2, ta), (b1, b2, tb) = wa, wb
    if abs(ta - tb) > THICK_TOL or math.dist(a1, a2) < 1e-6 or math.dist(b1, b2) < 1e-6:
        return None
    (ux, uy), _ = _dir(a1, a2)
    (vx, vy), _ = _dir(b1, b2)
    if abs(ux * vy - uy * vx) > math.sin(ANGLE_TOL):
        return None
    nx, ny = -uy, ux
    if abs((b1[0] - a1[0]) * nx + (b1[1] - a1[1]) * ny) > axis_tol or abs((b2[0] - a1[0]) * nx + (b2[1] - a1[1]) * ny) > axis_tol:
        return None
    s = lambda p: (p[0] - a1[0]) * ux + (p[1] - a1[1]) * uy
    ia, ib = sorted((s(a1), s(a2))), sorted((s(b1), s(b2)))
    first, second = (ia, ib) if ia[0] <= ib[0] else (ib, ia)
    if second[0] <= first[1] + 1e-6:
        return None                                   # overlapping or touching: no gap
    at = lambda t: (a1[0] + ux * t, a1[1] + uy * t)
    return at(first[1]), at(second[0]), (at(first[0]), at(second[1]), (ta + tb) / 2)


def place_openings(walls, labels):
    """(walls with openings' pieces joined, [Opening], [labels without a place])."""
    walls = [tuple(w) for w in walls]
    placed, missing = [], []
    for lab in sorted(labels, key=lambda l: -l.width):          # wide ones first: they cannot take a narrow gap
        best = None
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                g = _gap(walls[i], walls[j])
                if g is None:
                    continue
                g0, g1, merged = g
                width = math.dist(g0, g1)
                if not (lab.width - GAP_SHORT <= width <= lab.width + GAP_LONG):
                    continue
                mid = ((g0[0] + g1[0]) / 2, (g0[1] + g1[1]) / 2)
                d = math.dist(mid, (lab.x, lab.y))
                if d > REACH:
                    continue
                # No preference for the label's direction: door labels are written along the open leaf,
                # across the wall (the owner's NEW VILLA PLAN), window labels along the wall.
                score = abs(width - lab.width) + 0.3 * d
                if best is None or score < best[0]:
                    best = (score, i, j, mid, merged)
        if best is None:
            missing.append(lab)
            continue
        _s, i, j, mid, merged = best
        walls = [w for k, w in enumerate(walls) if k not in (i, j)] + [merged]
        sill = float(lab.sill) if lab.sill is not None else 0.0
        placed.append(Opening(lab.kind, mid, float(lab.width), float(lab.height), sill, lab))
    return walls, placed, missing


def host_of(walls, point):
    """(wall index, offset of ``point`` along it) for the wall whose axis carries the point."""
    best = None
    for k, (a, b, t) in enumerate(walls):
        (ux, uy), L = _dir(a, b)
        s = (point[0] - a[0]) * ux + (point[1] - a[1]) * uy
        d = abs((point[0] - a[0]) * -uy + (point[1] - a[1]) * ux)
        if -1e-6 <= s <= L + 1e-6 and d <= t / 2 + 0.02 and (best is None or d < best[2]):
            best = (k, s, d)
    return None if best is None else best[:2]


def analyse_sheet(sheet, sim):
    """What ``building_from_underlay.build`` needs, for a sheet of a drawing set placed by ``sim`` (project/drawing_set):
    walls, openings in their gaps, room labels — in model metres, from the texts and lines read once."""
    from archforge.architecture.walls_from_lines import find_walls
    from archforge.project import drawing_text as T
    k = sheet.metres_per_pt
    to = sim.apply

    def placed(item):
        item.x, item.y = to((item.x * k, item.y * k))
        if hasattr(item, "angle"):
            item.angle = item.angle + sim.turn
        return item
    segs = [(*to((a, b)), *to((c, d))) for a, b, c, d in sheet.segments]
    walls, openings, missing = tidy(find_walls(segs), [placed(o) for o in T.openings(sheet.texts)])
    return {"walls": walls, "openings": openings, "missing": missing, "rooms": [placed(r) for r in T.rooms(sheet.texts)],
            "levels": [placed(l) for l in T.levels(sheet.texts)]}


# ---------------------------------------------------------------------------------------- tidying the found walls
# Owner 22/10: «αν δεν κλείνουν χώροι, κάτι είναι λάθος».  On the NEW VILLA PLAN not even the engine room closed:
# 157 walls for ~30 (a lining «wall» inside each concrete wall), a wall 0,8° off square, corners 2 cm apart, and
# facades in pieces with glazing between.  Rooms need the axes to meet exactly; these steps make them meet.

SQUARE_TOL = math.radians(2.0)     # walls this close to the building's square are squared
GAP_MAX = 3.20                     # pieces of one wall with a gap up to this become one wall with an opening (m)
WELD = 0.30                        # ends this close to another wall's axis meet it (m, beyond half thicknesses)


def _inside(w, v):
    """Wall w lies within wall v's band (parallel, along it, axis inside v's thickness)."""
    (a, b, _t), (p, q, t) = v, w
    L = math.dist(a, b)
    if L < 1e-9 or math.dist(p, q) < 1e-9:
        return False
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    if abs(u[0] * (q[1] - p[1]) - u[1] * (q[0] - p[0])) / math.dist(p, q) > 0.035:
        return False
    off = lambda r: (r[0] - a[0]) * -u[1] + (r[1] - a[1]) * u[0]
    al = lambda r: (r[0] - a[0]) * u[0] + (r[1] - a[1]) * u[1]
    lo, hi = sorted((al(p), al(q)))
    return abs((off(p) + off(q)) / 2) <= v[2] / 2 + t / 2 - 0.005 and lo >= -0.05 and hi <= L + 0.05


def dedupe(walls):
    """Drop walls lying inside a thicker one (a lining or cavity line read as a wall of its own)."""
    walls = [tuple(w) for w in walls]
    return [w for i, w in enumerate(walls)
            if not any(j != i and _inside(w, v) and (v[2] > w[2] + 1e-9 or (abs(v[2] - w[2]) <= 1e-9 and j < i))
                       for j, v in enumerate(walls))]


def merge_bands(walls, max_thickness=0.80):
    """Parallel walls whose bodies overlap (one concrete wall read as three pieces at 22,11 / 22,17 / 22,33, 36–45 cm)
    become one wall: along, the union; across, from the outermost face to the other.  Parallel walls never cross,
    so left apart they hang in the room graph and the room leaks between them."""
    walls = [tuple(w) for w in walls]
    changed = True
    while changed:
        changed = False
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                (a, b, t), (c, d, tv) = walls[i], walls[j]
                L = math.dist(a, b)
                if L < 1e-9 or math.dist(c, d) < 1e-9:
                    continue
                ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
                if abs(ux * (d[1] - c[1]) - uy * (d[0] - c[0])) / math.dist(c, d) > 0.02:
                    continue
                off = lambda p: (p[0] - a[0]) * -uy + (p[1] - a[1]) * ux
                al = lambda p: (p[0] - a[0]) * ux + (p[1] - a[1]) * uy
                o = (off(c) + off(d)) / 2
                if abs(o) >= (t + tv) / 2 - 0.01:
                    continue                                          # side by side, not one body
                lo1, hi1 = 0.0, L
                lo2, hi2 = sorted((al(c), al(d)))
                if min(hi1, hi2) - max(lo1, lo2) < -0.05:
                    continue                                          # one after the other with a gap
                lo, hi = min(lo1, lo2), max(hi1, hi2)
                f0, f1 = min(-t / 2, o - tv / 2), max(t / 2, o + tv / 2)
                if f1 - f0 > max_thickness:
                    continue
                mid = (f0 + f1) / 2
                at = lambda s_: (a[0] + ux * s_ - uy * mid, a[1] + uy * s_ + ux * mid)
                walls = [w for k, w in enumerate(walls) if k not in (i, j)] + [(at(lo), at(hi), round(f1 - f0, 3))]
                changed = True
                break
            if changed:
                break
    return walls


def square(walls):
    """Turn walls within 2° of the building's square onto it (about their middle)."""
    hist = Counter()
    for a, b, _t in walls:
        L = math.dist(a, b)
        hist[round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 90.0 * 2) / 2 % 90.0] += L
    if not hist:
        return list(walls)
    base = math.radians(max(hist.items(), key=lambda kv: kv[1])[0])
    out = []
    for a, b, t in walls:
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        k = round((ang - base) / (math.pi / 2))
        target = base + k * math.pi / 2
        if abs(ang - target) <= SQUARE_TOL:
            mx, my, h = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, math.dist(a, b) / 2
            a, b = (mx - h * math.cos(target), my - h * math.sin(target)), (mx + h * math.cos(target), my + h * math.sin(target))
        out.append((a, b, t))
    return out


def close_gaps(walls, gap_max=GAP_MAX):
    """Collinear pieces with a gap up to ``gap_max`` between them become one wall (the thicker); each gap is an
    opening (no joinery: glazing / a passage the drawing gives no «w: | h:» label for)."""
    walls = [tuple(w) for w in walls]
    openings = []
    changed = True
    while changed:
        changed = False
        best = None
        for i in range(len(walls)):
            for j in range(i + 1, len(walls)):
                a, b = walls[i], walls[j]
                # Pieces of different thickness flush on one face (a jamb beside a concrete wall): axes apart by
                # up to half the thicker.
                g = _gap((a[0], a[1], b[2]), b, max(AXIS_TOL, max(a[2], b[2]) / 2 + 0.02))
                if g is None:
                    continue
                g0, g1, merged = g
                w = math.dist(g0, g1)
                if w <= gap_max and (best is None or w < best[0]):
                    best = (w, i, j, g0, g1, (merged[0], merged[1], max(a[2], b[2])))
        if best is not None:
            w, i, j, g0, g1, merged = best
            walls = [x for k, x in enumerate(walls) if k not in (i, j)] + [merged]
            if w >= 0.40:
                openings.append(Opening("opening", ((g0[0] + g1[0]) / 2, (g0[1] + g1[1]) / 2), w, 2.20, 0.0))
            changed = True
    return walls, openings


def _cross(a1, a2, b1, b2):
    d = (a1[0] - a2[0]) * (b1[1] - b2[1]) - (a1[1] - a2[1]) * (b1[0] - b2[0])
    if abs(d) < 1e-12:
        return None
    t = ((a1[0] - b1[0]) * (b1[1] - b2[1]) - (a1[1] - b1[1]) * (b1[0] - b2[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


def weld(walls):
    """Each end goes onto the axis of the wall it stops at (L corner or T junction), then ends that are the
    same corner become one point — the walls meet exactly, as rooms need."""
    ws = [[list(a), list(b), t] for a, b, t in walls]
    for i, w in enumerate(ws):
        for e in (0, 1):
            p, other = w[e], w[1 - e]
            best = None
            for j, v in enumerate(ws):
                if i == j:
                    continue
                c = _cross(w[0], w[1], v[0], v[1])
                if c is None:
                    continue
                reach = v[2] / 2 + w[2] / 2 + WELD
                d = math.dist(c, p)
                L = math.dist(v[0], v[1])
                if L < 1e-9 or d > reach:
                    continue
                s = ((c[0] - v[0][0]) * (v[1][0] - v[0][0]) + (c[1] - v[0][1]) * (v[1][1] - v[0][1])) / (L * L)
                if not -(reach / L) <= s <= 1 + reach / L:
                    continue
                # Moving the end must not flip the wall or eat most of it.
                if math.dist(c, other) < 0.5 * math.dist(p, other):
                    continue
                if best is None or d < best[0]:
                    best = (d, c, j, s)
            if best is not None:
                _d, c, j, s = best
                w[e] = list(c)
                v = ws[j]                                   # an L corner: the other wall reaches the crossing too
                if s < 0:
                    v[0] = list(c)
                elif s > 1:
                    v[1] = list(c)
    # Same corner, one point.
    pts = [p for w in ws for p in (w[0], w[1])]
    for p in pts:
        for q in pts:
            if p is not q and 0 < math.dist(p, q) <= 0.03:
                q[0], q[1] = p[0], p[1]
    return [(tuple(a), tuple(b), t) for a, b, t in ws if math.dist(a, b) >= 0.10]


END_REACH = 1.30                  # a free end facing a wall this close is carried to it (m, beyond its face)
CORNER_REACH = 1.10               # a free end with nothing ahead is joined to the nearest wall beside within this


def reach_from_free_ends(walls, reach=END_REACH):
    """A wall end touching nothing, facing a wall body within ``reach``: the wall goes on to that wall's axis —
    a piece the drawing fills without lines (the NEW VILLA's concrete corner between bathroom and cours anglais);
    a long reach is an opening, so a passage stays a passage."""
    walls = [list(w) for w in walls]
    openings = []

    def touches(p, t, k):
        return any(j != k and _seg_dist(p, v[0], v[1]) <= (t + v[2]) / 2 + 0.10 for j, v in enumerate(walls))
    for i in range(len(walls)):
        a, b, t = walls[i]
        L = math.dist(a, b)
        if L < 0.5 or t < 0.07:
            continue
        for e in (0, 1):
            p, q = walls[i][e], walls[i][1 - e]
            if touches(p, t, i):
                continue
            ux, uy = (p[0] - q[0]) / L, (p[1] - q[1]) / L
            best = None
            for j, (c, d, tv) in enumerate(walls):
                if j == i:
                    continue
                hit = _cross(p, (p[0] + ux, p[1] + uy), c, d)
                M = math.dist(c, d)
                if hit is None or M < 1e-9:
                    continue
                along = (hit[0] - p[0]) * ux + (hit[1] - p[1]) * uy
                s = ((hit[0] - c[0]) * (d[0] - c[0]) + (hit[1] - c[1]) * (d[1] - c[1])) / (M * M)
                if 0 < along - tv / 2 <= reach and 0 <= s <= 1 and (best is None or along < best[0]):
                    best = (along, hit, tv)
            if best is not None:
                along, hit, tv = best
                gap = along - tv / 2
                walls[i][e] = hit
                if gap >= 0.60:
                    openings.append(Opening("opening", (p[0] + ux * gap / 2, p[1] + uy * gap / 2), gap, 2.20, 0.0))
                continue
            # Nothing ahead: the nearest wall beside, within the corner's reach, gets a piece of wall to it.
            near = None
            for j, (c, d, tv) in enumerate(walls):
                if j == i or math.dist(c, d) < 1e-9:
                    continue
                M2 = (d[0] - c[0]) ** 2 + (d[1] - c[1]) ** 2
                sj = max(0.0, min(1.0, ((p[0] - c[0]) * (d[0] - c[0]) + (p[1] - c[1]) * (d[1] - c[1])) / M2))
                foot = (c[0] + sj * (d[0] - c[0]), c[1] + sj * (d[1] - c[1]))
                dist = math.dist(p, foot)
                if (t + tv) / 2 < dist <= CORNER_REACH and (near is None or dist < near[0]):
                    near = (dist, foot, tv)
            if near is not None:
                walls.append([list(p), list(near[1]), max(t, near[2])])
    return [tuple(w) for w in walls], openings


def drop_stubs(walls, max_length=1.5):
    """Short pieces with an end touching nothing — a counter's edge, a wardrobe's side, a shower tray — go;
    repeated, as dropping one can free another."""
    walls = [tuple(w) for w in walls]
    while True:
        def free(k, p):
            return not any(j != k and _seg_dist(p, v[0], v[1]) <= (walls[k][2] + v[2]) / 2 + 0.05 for j, v in enumerate(walls))
        keep = [w for k, w in enumerate(walls) if math.dist(w[0], w[1]) > max_length or not (free(k, w[0]) or free(k, w[1]))]
        if len(keep) == len(walls):
            return keep
        walls = keep


def tidy(walls, labels):
    """dedupe → square → labelled openings into their gaps (between pieces, then between an end and a wall across)
    → overlapping parallel pieces merged → the other gaps closed as openings → loose furniture outlines out →
    free ends carried to the wall ahead / beside → corners welded."""
    walls = square(dedupe(walls))
    walls, placed, missing = place_openings(walls, labels)
    walls, at_ends, missing = place_at_ends(walls, missing)
    # Merged after the doors are in: a band of pieces would otherwise cover the door gaps.
    walls = merge_bands(walls)
    walls, gaps = close_gaps(walls)
    walls = drop_loose(walls)
    walls, reached = reach_from_free_ends(walls)
    return weld(drop_stubs(walls)), placed + at_ends + gaps + reached, missing


def place_at_ends(walls, labels):
    """A door between a wall's *end* and the body of a wall across (the leaf hinges at the frame against it: the
    NEW VILLA bedrooms): the end is carried to the other wall's axis and the opening goes in what was the gap.
    Only where a «w: … | h: …» label is next to that gap (an unlabelled one may be an open plan)."""
    walls = [list(w) for w in walls]
    placed, missing = [], []
    for lab in labels:
        best = None
        for i, (a, b, t) in enumerate(walls):
            L = math.dist(a, b)
            if L < 0.2:
                continue
            for e, p, q in ((1, b, a), (0, a, b)):
                ux, uy = (p[0] - q[0]) / L, (p[1] - q[1]) / L             # outwards from this end
                for j, (c, d, tv) in enumerate(walls):
                    if j == i:
                        continue
                    hit = _cross(p, (p[0] + ux, p[1] + uy), c, d)
                    if hit is None:
                        continue
                    along = (hit[0] - p[0]) * ux + (hit[1] - p[1]) * uy
                    gap = along - tv / 2
                    M = math.dist(c, d)
                    s = ((hit[0] - c[0]) * (d[0] - c[0]) + (hit[1] - c[1]) * (d[1] - c[1])) / (M * M) if M > 1e-9 else -1
                    if along <= 0 or not 0 <= s <= 1 or not (lab.width - GAP_SHORT <= gap <= lab.width + GAP_LONG):
                        continue
                    mid = (p[0] + ux * gap / 2, p[1] + uy * gap / 2)
                    dist = math.dist(mid, (lab.x, lab.y))
                    if dist > REACH:
                        continue
                    score = abs(gap - lab.width) + 0.3 * dist
                    if best is None or score < best[0]:
                        best = (score, i, e, hit, mid, gap)
        if best is None:
            missing.append(lab)
            continue
        _s, i, e, hit, mid, gap = best
        walls[i][e] = hit
        placed.append(Opening(lab.kind, mid, float(lab.width), float(lab.height),
                              float(lab.sill) if lab.sill is not None else 0.0, lab))
    return [tuple(w) for w in walls], placed, missing


def drop_loose(walls, keep_ratio=0.25):
    """Wall groups that touch nothing of the building — furniture outlines read as walls (the sofa) — are dropped:
    a group is kept when it is a good part (``keep_ratio``) of the longest group or has a thick wall in it."""
    n = len(walls)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x

    def touch(w, v):
        reach = (w[2] + v[2]) / 2 + 0.10
        return any(_seg_dist(p, v[0], v[1]) <= reach for p in (w[0], w[1])) or \
            any(_seg_dist(p, w[0], w[1]) <= reach for p in (v[0], v[1]))
    for i in range(n):
        for j in range(i + 1, n):
            if touch(walls[i], walls[j]):
                parent[find(i)] = find(j)
    length = Counter()
    for i, w in enumerate(walls):
        length[find(i)] += math.dist(w[0], w[1])
    thick = Counter()
    for i, w in enumerate(walls):
        thick[find(i)] = max(thick[find(i)], w[2])
    top = max(length.values(), default=0.0)
    main = max(length, key=length.get) if length else None
    xs = [p[0] for i, w in enumerate(walls) if find(i) == main for p in w[:2]]
    ys = [p[1] for i, w in enumerate(walls) if find(i) == main for p in w[:2]]
    box = (min(xs), min(ys), max(xs), max(ys)) if xs else None

    def within_building(g):
        pts = [p for i, w in enumerate(walls) if find(i) == g for p in w[:2]]
        return box is not None and all(box[0] < p[0] < box[2] and box[1] < p[1] < box[3] for p in pts)
    # A small group on its own inside the building is furniture (the sofa: 9 m of outline, a 25 cm back);
    # outside it, a thick group is a retaining wall and stays.
    return [w for i, w in enumerate(walls) if length[find(i)] >= keep_ratio * top
            or (thick[find(i)] >= 0.25 and not within_building(find(i)))]


def _seg_dist(p, a, b):
    L2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / L2))
    return math.dist(p, (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
