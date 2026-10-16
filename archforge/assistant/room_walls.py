"""The inside faces of a room's walls, as the assistant lays things out along them.

A room of the reading has its outline on the wall axes; things stand on the
inside faces.  Each edge of the outline becomes a *run*: the face segment
(axis moved inwards by half the wall thickness, cut at the neighbouring
faces), its direction ``u`` and inward normal ``n``, and the doors / windows
on it as intervals ``s`` measured from the run start.  Runs follow the room
counter-clockwise, so the room is on the left of ``u`` and the corner at the
end of run ``i`` is the start of run ``i + 1``.

Guide lines drawn by the user are made of points snapped to the runs
(corners pull harder); ``legs_from_points`` turns them into intervals per
run, walking round the corners in between.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

FACE_SNAP = 0.40      # a click this close to a face lands on it
CORNER_SNAP = 0.25    # ... and this close to a corner, on the corner
DOOR_MARGIN = 0.05    # nothing stands closer than this to a door opening


@dataclass
class Opening:
    kind: str            # 'door' | 'window'
    s0: float
    s1: float
    sill: float          # above the floor (0 for doors)
    top: float
    entity_id: str
    width: float


@dataclass
class Run:
    index: int
    a: Tuple[float, float]
    b: Tuple[float, float]
    u: Tuple[float, float]
    n: Tuple[float, float]
    length: float
    thickness: float
    wall_ids: Tuple[str, ...]
    openings: List[Opening] = field(default_factory=list)

    def point(self, s, depth=0.0):
        """Plan point ``s`` along the face and ``depth`` into the room."""
        return (self.a[0] + self.u[0] * s + self.n[0] * depth, self.a[1] + self.u[1] * s + self.n[1] * depth)

    @property
    def rotation(self):
        """Rotation (degrees) of a cabinet / fixture whose back is on this face."""
        return math.degrees(math.atan2(self.n[0], -self.n[1])) % 360.0

    def doors(self):
        return [o for o in self.openings if o.kind == "door"]

    def windows(self):
        return [o for o in self.openings if o.kind == "window"]


def _signed_area(poly):
    return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly))) / 2.0


def _merge_collinear(poly):
    out = list(poly)
    changed = True
    while changed and len(out) > 3:
        changed = False
        for i in range(len(out)):
            p0, p1, p2 = out[i - 1], out[i], out[(i + 1) % len(out)]
            ax, ay, bx, by = p1[0] - p0[0], p1[1] - p0[1], p2[0] - p1[0], p2[1] - p1[1]
            la, lb = math.hypot(ax, ay), math.hypot(bx, by)
            if la < 1e-6 or lb < 1e-6 or abs(ax * by - ay * bx) / (la * lb) < 1e-4 and ax * bx + ay * by > 0:
                del out[i]
                changed = True
                break
    return out


def _walls_on_edge(doc, p, q, z):
    """Walls of the storey lying on the outline edge p→q: ``[(entity, thickness)]``."""
    ex, ey = q[0] - p[0], q[1] - p[1]
    L = math.hypot(ex, ey)
    ux, uy = ex / L, ey / L
    out = []
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - z) > 0.05:
            continue
        w = e.params
        x1, y1, x2, y2 = (float(w[k]) for k in ("x1", "y1", "x2", "y2"))
        wl = math.hypot(x2 - x1, y2 - y1)
        if wl < 1e-6 or abs((x2 - x1) / wl * uy - (y2 - y1) / wl * ux) > 1e-3:
            continue
        if abs((x1 - p[0]) * -uy + (y1 - p[1]) * ux) > 0.03:
            continue
        t1, t2 = sorted(((x1 - p[0]) * ux + (y1 - p[1]) * uy, (x2 - p[0]) * ux + (y2 - p[1]) * uy))
        if min(t2, L) - max(t1, 0.0) > 0.05:
            out.append((e, float(w.get("thickness", 0.2))))
    return out


def _intersect(p, d, q, e):
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-9:
        return None
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * t, p[1] + d[1] * t)


def room_runs(doc, room, z=None) -> List[Run]:
    """Inside-face runs of ``room`` (a room of the reading), counter-clockwise."""
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    poly = [(float(x), float(y)) for x, y in room["polygon"]]
    if _signed_area(poly) < 0:
        poly = poly[::-1]
    poly = _merge_collinear(poly)
    n = len(poly)
    edges = []
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        u = ((q[0] - p[0]) / L, (q[1] - p[1]) / L)
        nrm = (-u[1], u[0])
        walls = _walls_on_edge(doc, p, q, level)
        t = max((th for _e, th in walls), default=0.0)
        edges.append((p, u, nrm, t, tuple(e.id for e, _t in walls)))
    corners = []
    for i in range(n):
        p0, u0, n0, t0, _w = edges[i - 1]
        p1, u1, n1, t1, _w = edges[i]
        a = (p0[0] + n0[0] * t0 / 2, p0[1] + n0[1] * t0 / 2)
        b = (p1[0] + n1[0] * t1 / 2, p1[1] + n1[1] * t1 / 2)
        corners.append(_intersect(a, u0, b, u1) or b)
    runs = []
    for i in range(n):
        p, u, nrm, t, wall_ids = edges[i]
        a, b = corners[i], corners[(i + 1) % n]
        length = (b[0] - a[0]) * u[0] + (b[1] - a[1]) * u[1]
        run = Run(i, a, b, u, nrm, max(0.0, length), t, wall_ids)
        run.openings = _openings(doc, run)
        runs.append(run)
    return runs


def _openings(doc, run):
    out = []
    for e in doc.entities.values():
        if e.kind not in ("door", "window") or e.parent_id not in run.wall_ids:
            continue
        host = doc.get(e.parent_id).params
        x1, y1, x2, y2 = (float(host[k]) for k in ("x1", "y1", "x2", "y2"))
        wl = math.hypot(x2 - x1, y2 - y1)
        if wl < 1e-9:
            continue
        c = float(e.params.get("offset", 0.0))
        cx, cy = x1 + (x2 - x1) / wl * c, y1 + (y2 - y1) / wl * c
        s = (cx - run.a[0]) * run.u[0] + (cy - run.a[1]) * run.u[1]
        w = float(e.params.get("width", 0.9))
        if s + w / 2 < 0 or s - w / 2 > run.length:
            continue
        sill = 0.0 if e.kind == "door" else float(e.params.get("sill", 0.9))
        out.append(Opening(e.kind, s - w / 2, s + w / 2, sill, sill + float(e.params.get("height", 2.1 if e.kind == "door" else 1.4)),
                           e.id, w))
    return sorted(out, key=lambda o: o.s0)


def inner_polygon(runs):
    return [r.a for r in runs]


# ------------------------------------------------------------------ guide lines
def snap_point(runs, x, y, tolerance=FACE_SNAP):
    """``(run index, s, (px, py))`` of the face point under (x, y), or None."""
    best = None
    for r in runs:
        if r.length < 0.05 or r.thickness <= 0:
            continue
        s = (x - r.a[0]) * r.u[0] + (y - r.a[1]) * r.u[1]
        s = max(0.0, min(r.length, s))
        px, py = r.point(s)
        d = math.hypot(x - px, y - py)
        if d <= tolerance and (best is None or d < best[0]):
            best = (d, r.index, s)
    if best is None:
        return None
    _d, i, s = best
    r = runs[i]
    # Corners pull harder: the end of one run is the start of the next.
    if s <= CORNER_SNAP:
        s = 0.0
    elif r.length - s <= CORNER_SNAP:
        s = r.length
    return i, s, r.point(s)


def legs_from_points(runs, points):
    """Intervals ``[(run, lo, hi)]`` covered by a guide line through snapped points ``[(run, s)]``.

    Between points on different runs the line follows the faces round the
    corners, the shorter way.  Legs come in counter-clockwise order.
    """
    n = len(runs)
    cover = {}

    def add(i, lo, hi):
        lo, hi = max(0.0, min(lo, hi)), min(runs[i].length, max(lo, hi))
        if i in cover:
            cover[i] = (min(cover[i][0], lo), max(cover[i][1], hi))
        else:
            cover[i] = (lo, hi)
    pts = list(points)
    if len(pts) == 1:
        add(pts[0][0], pts[0][1], pts[0][1])
    for (i, si), (j, sj) in zip(pts, pts[1:]):
        if i == j:
            add(i, si, sj)
            continue
        # A point on a corner belongs to both runs that meet there.
        if si >= runs[i].length - 1e-6 and (i + 1) % n == j:
            add(j, 0.0, sj); add(i, si, si)
            continue
        if si <= 1e-6 and (i - 1) % n == j:
            add(j, sj, runs[j].length); add(i, si, si)
            continue
        forward = (j - i) % n
        backward = (i - j) % n
        if forward <= backward:
            add(i, si, runs[i].length)
            k = (i + 1) % n
            while k != j:
                add(k, 0.0, runs[k].length)
                k = (k + 1) % n
            add(j, 0.0, sj)
        else:
            add(i, 0.0, si)
            k = (i - 1) % n
            while k != j:
                add(k, 0.0, runs[k].length)
                k = (k - 1) % n
            add(j, sj, runs[j].length)
    legs = [(i, lo, hi) for i, (lo, hi) in cover.items() if hi - lo > 0.05]
    return order_legs(runs, legs)


def order_legs(runs, legs):
    """Legs in counter-clockwise order along the chain (the start is the run whose predecessor is not used)."""
    n = len(runs)
    used = {i for i, _lo, _hi in legs}
    if not used:
        return []
    start = next((i for i in sorted(used) if (i - 1) % n not in used), min(used))
    by = {i: (i, lo, hi) for i, lo, hi in legs}
    out, k = [], start
    for _ in range(n):
        if k in by:
            out.append(by[k])
        k = (k + 1) % n
    return out


def is_corner(runs, i, j):
    """Run ``j`` follows run ``i`` at a convex, square corner."""
    a, b = runs[i], runs[j]
    if (i + 1) % len(runs) != j:
        return False
    cross = a.u[0] * b.u[1] - a.u[1] * b.u[0]
    return cross > 0.99


def fmt_m(v):
    """Metres the Greek way: 2,40 m."""
    return f"{v:.2f}".replace(".", ",") + " m"
