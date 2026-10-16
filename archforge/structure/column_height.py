"""How tall a hand-placed column is: it follows the walls it stands on.

A column placed on a storey rises to the top of the walls it touches (a sloped
wall top is read at the column's position along the wall).  Away from walls it
takes the height of the storey's walls; a level above counts only when it is
at that wall top (a split level half way up the walls is not where the column
stops).  Without walls on the storey: the next level above, else 2.70 m.
"""
from __future__ import annotations

import math

STOREY_TOL = 0.05      # walls whose base is this close to the column base belong to its storey
REACH = 0.35           # beyond the wall face: a column this close still stands on the wall
LEVEL_TOL = 0.05       # a level this close to the column top is the column's top level
FALLBACK = 2.70


def _wall_top_at(p, x, y, reach):
    """Top z of a wall at (x, y) or None if the point is not on/at the wall."""
    ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-9:
        return None
    ux, uy = (bx - ax) / L, (by - ay) / L
    s = (x - ax) * ux + (y - ay) * uy
    if s < -reach or s > L + reach:
        return None
    if abs(-(x - ax) * uy + (y - ay) * ux) > float(p.get("thickness", 0.2)) / 2 + reach:
        return None
    h = float(p.get("height", FALLBACK))
    h0, h1 = float(p.get("start_height", h)), float(p.get("end_height", h))
    t = min(1.0, max(0.0, s / L))
    return float(p.get("z", 0.0)) + h0 + (h1 - h0) * t


def _storey_walls(doc, z):
    return [e for e in doc.entities.values()
            if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < STOREY_TOL]


def _level_at(doc, top):
    for name, lz in sorted(doc.levels.items(), key=lambda kv: float(kv[1])):
        if abs(float(lz) - top) < LEVEL_TOL:
            return str(name)
    return "Unassigned"


def column_span(doc, x, y, z, *, width=0.25, depth=0.25):
    """``(height, top_level)`` of a column at plan (x, y) with its base at z."""
    z = float(z)
    walls = _storey_walls(doc, z)
    reach = max(float(width), float(depth)) / 2 + REACH
    tops = [t for t in (_wall_top_at(w.params, float(x), float(y), reach) for w in walls) if t is not None]
    if not tops:
        tops = [_wall_top_at(w.params, float(w.params["x1"]), float(w.params["y1"]), 0.0) for w in walls]
        tops += [_wall_top_at(w.params, float(w.params["x2"]), float(w.params["y2"]), 0.0) for w in walls]
        tops = [t for t in tops if t is not None]
    if tops:
        top = max(tops)
    else:
        above = sorted(float(v) for v in doc.levels.values() if float(v) > z + 0.5)
        top = above[0] if above else z + FALLBACK
    return max(0.05, top - z), _level_at(doc, top)
