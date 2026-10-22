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


def _gap(wa, wb):
    """(gap start, gap end, merged wall) when wa and wb lie on one axis with a gap between them, else None."""
    (a1, a2, ta), (b1, b2, tb) = wa, wb
    if abs(ta - tb) > THICK_TOL or math.dist(a1, a2) < 1e-6 or math.dist(b1, b2) < 1e-6:
        return None
    (ux, uy), _ = _dir(a1, a2)
    (vx, vy), _ = _dir(b1, b2)
    if abs(ux * vy - uy * vx) > math.sin(ANGLE_TOL):
        return None
    nx, ny = -uy, ux
    if abs((b1[0] - a1[0]) * nx + (b1[1] - a1[1]) * ny) > AXIS_TOL or abs((b2[0] - a1[0]) * nx + (b2[1] - a1[1]) * ny) > AXIS_TOL:
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
    walls, openings, missing = place_openings(find_walls(segs), [placed(o) for o in T.openings(sheet.texts)])
    return {"walls": walls, "openings": openings, "missing": missing, "rooms": [placed(r) for r in T.rooms(sheet.texts)],
            "levels": [placed(l) for l in T.levels(sheet.texts)]}
