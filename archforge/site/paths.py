"""Site paths: roads, sidewalks and garden paths draped on the terrain.

``kind='site_path'`` params: ``x1, y1, x2, y2`` (centre line), ``width``,
``thickness``, ``z`` (storey elevation used off-terrain) and ``style``
('path', 'sidewalk' or 'road'). The strip follows the ground: its top is
``terrain + 0.02 m`` sampled every 0.5 m, so it neither floats nor sinks.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

STYLES = {
    'path': {'width': 1.0, 'thickness': 0.05, 'name': 'Μονοπάτι'},
    'sidewalk': {'width': 1.5, 'thickness': 0.12, 'name': 'Πεζοδρόμιο'},
    'road': {'width': 3.5, 'thickness': 0.10, 'name': 'Δρόμος'},
}
LIFT = 0.02


def path_top(doc, params: Dict, x: float, y: float) -> float:
    from archforge.site.terrain import terrain_height_at
    ground = terrain_height_at(doc, x, y)
    storey = float(params.get('z', 0.0))
    lowest = min([float(v) for v in doc.levels.values()] + [0.0])
    if ground is not None and storey <= lowest + 1e-6:
        return ground + LIFT
    return storey + float(params.get('thickness', 0.05))


def path_outline(params: Dict) -> Tuple[Tuple[float, float], ...]:
    x1, y1, x2, y2 = (float(params[k]) for k in ('x1', 'y1', 'x2', 'y2'))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        raise ValueError('path has zero length')
    hw = float(params['width']) / 2.0
    nx, ny = -(y2 - y1) / L * hw, (x2 - x1) / L * hw
    return ((x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny))


def path_mesh(doc, params: Dict):
    x1, y1, x2, y2 = (float(params[k]) for k in ('x1', 'y1', 'x2', 'y2'))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        raise ValueError('path has zero length')
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    hw = float(params['width']) / 2.0; t = float(params['thickness'])
    n = max(1, int(math.ceil(L / 0.5)))
    verts: List[Tuple[float, float, float]] = []
    left_top, right_top, left_bot, right_bot = [], [], [], []
    for i in range(n + 1):
        s = L * i / n
        cx, cy = x1 + ux * s, y1 + uy * s
        for side, top_list, bot_list in ((1, left_top, left_bot), (-1, right_top, right_bot)):
            px, py = cx - uy * hw * side, cy + ux * hw * side
            z = path_top(doc, params, px, py)
            top_list.append(len(verts)); verts.append((px, py, z))
            bot_list.append(len(verts)); verts.append((px, py, z - t))
    tris: List[Tuple[int, int, int]] = []; roles: List[str] = []

    def quad(a, b, c, d, role):
        tris.extend(((a, b, c), (a, c, d))); roles.extend((role, role))

    for i in range(n):
        quad(right_top[i], right_top[i + 1], left_top[i + 1], left_top[i], 'top')
        quad(right_bot[i], left_bot[i], left_bot[i + 1], right_bot[i + 1], 'bottom')
        quad(left_bot[i], left_top[i], left_top[i + 1], left_bot[i + 1], 'side')
        quad(right_bot[i], right_bot[i + 1], right_top[i + 1], right_top[i], 'side')
    quad(right_bot[0], right_top[0], left_top[0], left_bot[0], 'side')
    quad(right_bot[n], left_bot[n], left_top[n], right_top[n], 'side')
    return tuple(verts), tuple(tris), tuple(roles)
