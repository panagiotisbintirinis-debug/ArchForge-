"""Τοίχοι από το υπόβαθρο (owner 21/10: «ανέβασα ένα PDF αλλά δεν το ανοίγει ως κτίριο»).

An engineer's drawing (DXF, or a PDF exported from CAD) draws a wall as two parallel lines its thickness apart.
This finds those pairs and proposes walls: the axis halfway between the lines, the thickness their distance.
It is a proposal, never the design: the walls are made by one undoable command, selected, for the human to keep,
correct or delete.  Scanned drawings have no lines to read — they are traced by hand.

* Pairs: two segments at the same angle (±1°), 6–70 cm apart, overlapping ≥ 40 cm along their length.
* Patterns are not walls: lines that go on at the same spacing beside a pair (hatching, tiles, stair treads)
  leave it out; inside a pair, extra lines (a cavity, insulation) are fine.
* Each line is used once along its length (the nearest partner first); collinear pieces with the same thickness
  are joined; wall ends near another wall's axis meet it (L corners and T junctions).
"""
from __future__ import annotations

import math

MIN_T, MAX_T = 0.06, 0.70          # wall thickness range (m)
MIN_OVERLAP = 0.40                 # the two lines run side by side at least this long (m)
MIN_LEN = 0.30                     # shorter lines are details (m)
ANGLE_TOL = math.radians(1.0)


def _norm(seg):
    x1, y1, x2, y2 = seg
    ang = math.atan2(y2 - y1, x2 - x1) % math.pi
    if ang > math.pi - 1e-9:
        ang = 0.0
    return ang


def _frame(ang):
    return (math.cos(ang), math.sin(ang)), (-math.sin(ang), math.cos(ang))


def _project(seg, u, n):
    """(offset across, start along, end along) of a segment in the frame (u along, n across)."""
    x1, y1, x2, y2 = seg
    s1, s2 = x1 * u[0] + y1 * u[1], x2 * u[0] + y2 * u[1]
    o = ((x1 + x2) / 2) * n[0] + ((y1 + y2) / 2) * n[1]
    return o, min(s1, s2), max(s1, s2)


def _subtract(intervals, a, b):
    out = []
    for c, d in intervals:
        if d <= a or c >= b:
            out.append((c, d))
            continue
        if c < a:
            out.append((c, a))
        if d > b:
            out.append((b, d))
    return out


def find_walls(segments):
    """[(a, b, thickness)] in model metres from drawing segments [(x1, y1, x2, y2)] in model metres."""
    segs = [s for s in segments if math.hypot(s[2] - s[0], s[3] - s[1]) >= MIN_LEN]
    # Group by direction (within ANGLE_TOL), each group in its own frame.
    groups = []
    for s in sorted(segs, key=_norm):
        a = _norm(s)
        if groups and (abs(a - groups[-1][0]) <= ANGLE_TOL):
            groups[-1][1].append(s)
        else:
            groups.append([a, [s]])
    if len(groups) > 1 and abs(groups[0][0] + math.pi - groups[-1][0]) <= ANGLE_TOL:
        groups[0][1] += groups.pop()[1]                           # 0° and 179.5° are the same direction
    walls = []
    for ang, members in groups:
        u, n = _frame(ang)
        lines = [_project(s, u, n) for s in members]
        free = [[(lo, hi)] for _o, lo, hi in lines]
        pairs = []
        for i, (oi, li, hi_) in enumerate(lines):
            for j in range(i + 1, len(lines)):
                oj, lj, hj = lines[j]
                d = abs(oi - oj)
                if not MIN_T <= d <= MAX_T:
                    continue
                lo, hi = max(li, lj), min(hi_, hj)
                if hi - lo < MIN_OVERLAP:
                    continue
                pairs.append((d, i, j, lo, hi))
        pairs.sort()
        for d, i, j, lo, hi in pairs:
            # Patterns (hatching, tiles, treads): the same spacing goes on beside the pair — a wall's faces do not
            # repeat at the wall's own thickness.
            oi, oj = lines[i][0], lines[j][0]
            omin, omax = min(oi, oj), max(oi, oj)
            step = 0.2 * d
            repeated = any(k not in (i, j) and min(h2, hi) - max(l2, lo) > 0.2
                           and (abs(o - (omax + d)) <= step or abs(o - (omin - d)) <= step)
                           for k, (o, l2, h2) in enumerate(lines))
            if repeated:
                continue
            # Each line once along its length: what is still free on both.
            spans = [(max(a, lo), min(b, hi)) for a, b in free[i] if min(b, hi) - max(a, lo) > 0]
            spans = [(max(a, c), min(b, e)) for a, b in spans for c, e in free[j] if min(b, e) - max(a, c) >= MIN_OVERLAP]
            for a, b in spans:
                free[i] = _subtract(free[i], a, b)
                free[j] = _subtract(free[j], a, b)
                mid = (oi + oj) / 2
                walls.append(((a * u[0] + mid * n[0], a * u[1] + mid * n[1]),
                              (b * u[0] + mid * n[0], b * u[1] + mid * n[1]), round(d, 3), ang))
    return _corners(_join(walls))


def _join(walls, gap=0.15):
    """Collinear pieces with the same thickness, end to end (a door gap is kept if wider than ``gap``)."""
    out = []
    for a, b, t, ang in sorted(walls, key=lambda w: (round(w[3], 2), w[2])):
        u, n = _frame(ang)
        merged = False
        for k, (c, d, t2, ang2) in enumerate(out):
            if abs(ang2 - ang) > ANGLE_TOL or abs(t2 - t) > 0.01:
                continue
            if abs((a[0] - c[0]) * n[0] + (a[1] - c[1]) * n[1]) > 0.02:
                continue
            s = sorted([a[0] * u[0] + a[1] * u[1], b[0] * u[0] + b[1] * u[1]])
            r = sorted([c[0] * u[0] + c[1] * u[1], d[0] * u[0] + d[1] * u[1]])
            if s[0] <= r[1] + gap and r[0] <= s[1] + gap:
                lo, hi = min(s[0], r[0]), max(s[1], r[1])
                o = c[0] * n[0] + c[1] * n[1]
                out[k] = ((lo * u[0] + o * n[0], lo * u[1] + o * n[1]), (hi * u[0] + o * n[0], hi * u[1] + o * n[1]), t2, ang2)
                merged = True
                break
        if not merged:
            out.append((a, b, t, ang))
    return out


def _corners(walls):
    """Ends near another wall's axis meet it: L corners (both ends to the crossing) and T junctions."""
    ws = [[list(a), list(b), t] for a, b, t, _ang in walls]
    for i, w in enumerate(ws):
        for e in (0, 1):
            p = w[e]
            best, bd = None, None
            for j, v in enumerate(ws):
                if i == j:
                    continue
                c = _cross(w[0], w[1], v[0], v[1])
                if c is None:
                    continue
                reach = (w[2] + v[2]) * 0.75 + 0.05
                # The crossing must be near this end and on (or just past) the other wall.
                if math.dist(c, p) > reach or not _within(c, v[0], v[1], reach):
                    continue
                if bd is None or math.dist(c, p) < bd:
                    best, bd = c, math.dist(c, p)
            if best is not None:
                w[e] = list(best)
    return [(tuple(a), tuple(b), t) for a, b, t in ws if math.dist(a, b) >= MIN_LEN]


def _cross(a1, a2, b1, b2):
    d = (a1[0] - a2[0]) * (b1[1] - b2[1]) - (a1[1] - a2[1]) * (b1[0] - b2[0])
    if abs(d) < 1e-9:
        return None
    t = ((a1[0] - b1[0]) * (b1[1] - b2[1]) - (a1[1] - b1[1]) * (b1[0] - b2[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


def _within(p, a, b, tol):
    L = math.dist(a, b)
    if L < 1e-9:
        return False
    t = ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / (L * L)
    return -tol / L <= t <= 1 + tol / L
