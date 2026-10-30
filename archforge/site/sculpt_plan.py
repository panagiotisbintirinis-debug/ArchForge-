"""What Γλυπτική did, shown in the plan (owner 29/10: «στο 2Δ … την παραμόρφωση με νούμερα και σχεδιαστικά αχνές
γραμμές», «η ρύθμιση σχέδιο … και του βάθους που εφαρμόζει»).

- Ground strokes (``terrain.params['strokes']``): faint contour lines of the sculpted ground around them (every
  ``step`` m) and, at each stroke's centre, its height / depth («+0.80 m», «−0.40 m»).
- Wall sculpt (surface modifiers): a faint circle of the brush's reach and the amount pushed out / in.
Pure geometry for the plan (``core/plan_scene.py`` draws it); reads the same height field as 3D and sections.
"""
from __future__ import annotations

import math

SIGN = {"pull": 1.0, "inflate": 1.0, "crease": 1.0, "push": -1.0, "recess": -1.0}


def contour_step(strokes):
    peak = max((abs(float(s.get("dz", 0.0))) for s in strokes), default=0.0)
    return 0.1 if peak <= 0.6 else 0.25 if peak <= 2.5 else 0.5


def stroke_contours(params, cell=None):
    """``[(level, ((x, y), (x, y)))]``: contour segments of the terrain over the strokes' area (marching squares)."""
    from archforge.site.terrain import stroke_extent, terrain_height
    strokes = params.get("strokes") or ()
    box = stroke_extent(params)
    if box is None:
        return []
    x0, y0, x1, y1 = box
    # Only where there is ground: a stroke near the site's edge is cut by it, as in 3D.
    x0, y0 = max(x0, float(params["x0"])), max(y0, float(params["y0"]))
    x1, y1 = min(x1, float(params["x1"])), min(y1, float(params["y1"]))
    if x1 <= x0 or y1 <= y0:
        return []
    step = contour_step(strokes)
    if cell is None:
        cell = max(0.05, min(0.25, min(float(s["radius"]) for s in strokes) / 6.0))
    nx = max(2, min(200, int(math.ceil((x1 - x0) / cell))))
    ny = max(2, min(200, int(math.ceil((y1 - y0) / cell))))
    xs = [x0 + (x1 - x0) * i / nx for i in range(nx + 1)]
    ys = [y0 + (y1 - y0) * j / ny for j in range(ny + 1)]
    h = [[terrain_height(params, x, y) for x in xs] for y in ys]
    lo = min(min(r) for r in h); hi = max(max(r) for r in h)
    out = []
    level = math.ceil(lo / step) * step
    while level <= hi + 1e-9:
        for j in range(ny):
            for i in range(nx):
                corners = ((xs[i], ys[j], h[j][i]), (xs[i + 1], ys[j], h[j][i + 1]),
                           (xs[i + 1], ys[j + 1], h[j + 1][i + 1]), (xs[i], ys[j + 1], h[j + 1][i]))
                cuts = []
                for k in range(4):
                    (ax, ay, az), (bx, by, bz) = corners[k], corners[(k + 1) % 4]
                    if (az - level) * (bz - level) < 0:
                        t = (level - az) / (bz - az)
                        cuts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
                if len(cuts) == 2:
                    out.append((round(level, 4), (cuts[0], cuts[1])))
                elif len(cuts) == 4:
                    out += [(round(level, 4), (cuts[0], cuts[1])), (round(level, 4), (cuts[2], cuts[3]))]
        level += step
    return out


def stroke_labels(params):
    """``[((x, y), "+0.80 m", radius)]`` for each ground stroke."""
    return [((float(s["x"]), float(s["y"])), f"{float(s.get('dz', 0.0)):+.2f} m", float(s["radius"]))
            for s in params.get("strokes") or ()]


def wall_sculpt_marks(doc, wall_id):
    """``[((x, y), text, radius)]`` for each enabled sculpt modifier on the wall."""
    out = []
    for modifier in doc.surface_modifiers.values():
        if str(modifier.target.owner_id) != str(wall_id) or not modifier.enabled:
            continue
        region = modifier.target.subregion or {}
        hint = region.get("world_hint") or region.get("world_center")
        if not hint:
            continue
        op = str(modifier.operation)
        amount = float((modifier.params or {}).get("amount", 0.0))
        text = f"{SIGN[op] * amount:+.2f} m" if op in SIGN else f"λείανση {amount:.2f}"
        out.append(((float(hint[0]), float(hint[1])), text, float(region.get("radius", 0.0))))
    return out


def circle(center, radius, n=36):
    cx, cy = center
    return tuple((cx + radius * math.cos(2 * math.pi * k / n), cy + radius * math.sin(2 * math.pi * k / n)) for k in range(n + 1))
