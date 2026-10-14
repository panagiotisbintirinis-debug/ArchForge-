"""Balcony: a slab drawn outside (or over) the walls of a storey, with a railing on its free sides.

Owner (2026-10-14): «πλήρες διώροφο … μπαλκόνια».  The slab is the existing free-outline
``floor`` entity (top at the storey level); the railing is the existing ``railing`` entity
along the sides that are not against a wall of the same storey — open when the balcony
leans on the house, closed when it stands free.  Both are added as one undo by the caller.
"""
from __future__ import annotations

import math

from archforge.core.model import Entity

THICKNESS = 0.18          # cantilever slab, typical 16–20 cm (προς στατικό έλεγχο)
MIN_SIDE = 0.40
WALL_REACH = 0.05         # a side within half a wall thickness + this of the wall's axis leans on it


def slab_level(params):
    """Storey level of a free ``floor`` slab: a balcony hangs below it (top flush), others sit on it."""
    z = float(params.get('z', 0.0))
    return z + float(params.get('thickness', 0.0)) if params.get('role') == 'balcony' else z


def _area(points):
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1]
                   for i in range(len(points)))) / 2


def _distance_to_segment(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _storey_walls(doc, level_z):
    return [e.params for e in doc.entities.values()
            if e.kind == 'wall' and abs(float(e.params.get('z', 0.0)) - level_z) < 1e-3]


def _on_a_wall(p, walls):
    return any(_distance_to_segment(p, (float(w['x1']), float(w['y1'])), (float(w['x2']), float(w['y2'])))
               <= float(w.get('thickness', 0.2)) / 2 + WALL_REACH for w in walls)


def _against_wall(a, b, walls):
    """Every point of the side touches some wall (a wall split by an inner wall is two walls)."""
    n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.25) + 1)
    return all(_on_a_wall((a[0] + (b[0] - a[0]) * k / (n - 1), a[1] + (b[1] - a[1]) * k / (n - 1)), walls)
               for k in range(n))


def railing_runs(points, walls):
    """Free sides of the outline as railing polylines: ``[(points, closed)]``."""
    n = len(points)
    free = [not _against_wall(points[i], points[(i + 1) % n], walls) for i in range(n)]
    if all(free):
        return [(list(points), True)]
    start = next(i for i in range(n) if not free[i])     # walk from just after a side against a wall
    runs, run = [], None
    for k in range(1, n + 1):
        i = (start + k) % n
        if free[i]:
            run = run or [points[i]]
            run.append(points[(i + 1) % n])
        elif run:
            runs.append((run, False)); run = None
    if run:
        runs.append((run, False))
    return runs


def balcony_entities(doc, points, level_z, railing_type='balusters', thickness=THICKNESS):
    """``[floor slab, railing…]`` for a balcony outline on the storey at ``level_z``."""
    from archforge.architecture.railings import TYPES, default_params
    pts = [(round(float(q[0]), 4), round(float(q[1]), 4)) for q in points]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    if len(pts) < 3 or max(xs) - min(xs) < MIN_SIDE or max(ys) - min(ys) < MIN_SIDE or _area(pts) < MIN_SIDE ** 2:
        raise ValueError(f'Το μπαλκόνι χρειάζεται περίγραμμα τουλάχιστον {MIN_SIDE:.2f} × {MIN_SIDE:.2f} m')
    level_z = float(level_z)
    slab = Entity('floor', {'points': [list(q) for q in pts], 'z': level_z - thickness, 'thickness': float(thickness),
                         'role': 'balcony'},
                  name='Μπαλκόνι')
    out = [slab]
    for run, closed in railing_runs(pts, _storey_walls(doc, level_z)):
        out.append(Entity('railing', default_params(railing_type, [list(q) for q in run], z=level_z, closed=int(closed)),
                          name=f"{TYPES[railing_type]['label']} μπαλκονιού"))
    return out
