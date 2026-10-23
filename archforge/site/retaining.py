"""Τοιχίο αντιστήριξης: a wall whose height is the ground's step across it.

Owner 22/10: the site is terraces held by retaining walls.  A person draws the walls and writes the terrace levels
(site/terrain.py ``levels``); the ground steps at each wall, so how high a wall stands is read off the ground on
its two sides: from the lower ground up to the higher one (plus a parapet if asked).  The same function sets the
masterplan's walls when a drawing set is imported.  Plain data, no Qt.
"""
from __future__ import annotations

import math

SIDE = 0.25              # m beyond the wall's face where the ground of each side is read
MIN_HEIGHT = 0.30        # m — a wall that holds no step is still a low wall, not nothing


def sides(doc, wall, samples=3):
    """Ground heights on the two sides of ``wall`` along it: ``(left, right)`` lists (None where no terrain)."""
    from archforge.site.terrain import terrain_height_at
    p = wall.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-6:
        return [], []
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    off = float(p.get("thickness", 0.2)) / 2 + SIDE
    left, right = [], []
    for k in range(samples):
        t = (k + 0.5) / samples
        cx, cy = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        left.append(terrain_height_at(doc, cx - uy * off, cy + ux * off))
        right.append(terrain_height_at(doc, cx + uy * off, cy - ux * off))
    return left, right


def fit(doc, wall, parapet=0.0):
    """``{"z", "height"}`` for ``wall`` from the ground on its two sides, or None (no terrain there)."""
    left, right = sides(doc, wall)
    heights = [h for h in left + right if h is not None]
    if not heights:
        return None
    low, high = min(heights), max(heights)
    return {"z": round(low, 3), "height": round(max(MIN_HEIGHT, high - low + float(parapet)), 3)}


def fit_command(doc, walls, parapet=0.0):
    """One undoable step: every wall of ``walls`` set from the ground; ``(command or None, how many)``."""
    from archforge.core.commands import UpdateEntities
    changes = {}
    for w in walls:
        f = fit(doc, w, parapet)
        if f and (abs(f["z"] - float(w.params.get("z", 0.0))) > 1e-4 or abs(f["height"] - float(w.params["height"])) > 1e-4):
            changes[w.id] = f
    return (UpdateEntities(changes) if changes else None), len(changes)
