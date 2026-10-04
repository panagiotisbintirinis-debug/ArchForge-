"""Semantic site terrain: a planar-graded ground solid around the building.

The terrain is an authoritative Document entity (``kind='terrain'``):

- ``x0, y0, x1, y1``: plan extent of the site (metres)
- ``elevation``: ground level at (x0, y0); default 0.15 m below Ground
- ``slope_x`` / ``slope_y``: grade in percent along +x / +y
- ``thickness``: depth of the ground solid below its lowest point
- ``points``: optional elevation data ``[[x, y, z], ...]``; the ground
  passes exactly through each point and blends back to the graded plane
  within ``blend_radius`` (default 6 m)

Its top surface is the plane ``elevation + slope_x% * (x - x0) +
slope_y% * (y - y0)``; heights are exact (no sampled noise), so stairs and
other elements can stand on it deterministically.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

DEFAULT_ELEVATION = -0.15
DEFAULT_THICKNESS = 0.50
DEFAULT_MARGIN = 5.0


DEFAULT_BLEND_RADIUS = 6.0


def _plane_height(params: Dict, x: float, y: float) -> float:
    x0 = float(params['x0']); y0 = float(params['y0'])
    return (
        float(params.get('elevation', DEFAULT_ELEVATION))
        + float(params.get('slope_x', 0.0)) / 100.0 * (float(x) - x0)
        + float(params.get('slope_y', 0.0)) / 100.0 * (float(y) - y0)
    )


def terrain_height(params: Dict, x: float, y: float) -> float:
    """Graded plane plus a local, exact correction from elevation points."""
    base = _plane_height(params, x, y)
    points = params.get('points') or ()
    if not points:
        return base
    radius = max(0.5, float(params.get('blend_radius', DEFAULT_BLEND_RADIUS)))
    num = 0.0; den = 1.0 / (radius * radius)
    for px, py, pz in points:
        d = math.hypot(float(x) - float(px), float(y) - float(py))
        if d < 1e-9:
            return float(pz)
        if d >= radius:
            continue
        w = (1.0 - d / radius) ** 2 / (d * d)
        num += w * (float(pz) - _plane_height(params, px, py)); den += w
    return base + num / den


def terrain_contains(params: Dict, x: float, y: float) -> bool:
    return (
        float(params['x0']) <= float(x) <= float(params['x1'])
        and float(params['y0']) <= float(y) <= float(params['y1'])
    )


def terrain_height_at(doc, x: float, y: float):
    """Ground height under (x, y) from the site terrain, or None."""
    for entity in doc.entities.values():
        if entity.kind == 'terrain' and entity.visible and terrain_contains(entity.params, x, y):
            return terrain_height(entity.params, x, y)
    return None


def default_terrain_params(doc, margin: float = DEFAULT_MARGIN) -> Dict:
    """Site around the walls' extent (or 20 x 20 m around the origin)."""
    xs: List[float] = []; ys: List[float] = []
    for entity in doc.entities.values():
        if entity.kind == 'wall':
            p = entity.params
            xs += [float(p['x1']), float(p['x2'])]; ys += [float(p['y1']), float(p['y2'])]
    if xs:
        x0, x1, y0, y1 = min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin
    else:
        x0, x1, y0, y1 = -10.0, 10.0, -10.0, 10.0
    return {
        'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
        'elevation': DEFAULT_ELEVATION, 'slope_x': 0.0, 'slope_y': 0.0,
        'thickness': DEFAULT_THICKNESS,
    }


def terrain_mesh(params: Dict, cell: float | None = None):
    """Closed ground solid: graded top grid, flat bottom, four sides."""
    x0, y0, x1, y1 = (float(params[k]) for k in ('x0', 'y0', 'x1', 'y1'))
    if x1 - x0 <= 1e-6 or y1 - y0 <= 1e-6:
        raise ValueError('terrain extent must be positive')
    if cell is None:
        cell = 0.5 if params.get('points') else 1.0
    nx = max(1, min(120, int(math.ceil((x1 - x0) / cell))))
    ny = max(1, min(120, int(math.ceil((y1 - y0) / cell))))
    lowest = min(
        terrain_height(params, x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny)
        for i in range(nx + 1) for j in range(ny + 1)
    )
    bottom = lowest - max(0.05, float(params.get('thickness', DEFAULT_THICKNESS)))
    verts: List[Tuple[float, float, float]] = []
    index: Dict[Tuple, int] = {}

    def vid(i, j, top):
        key = (i, j, top)
        if key not in index:
            x = x0 + (x1 - x0) * i / nx; y = y0 + (y1 - y0) * j / ny
            index[key] = len(verts)
            verts.append((x, y, terrain_height(params, x, y) if top else bottom))
        return index[key]

    tris: List[Tuple[int, int, int]] = []; roles: List[str] = []

    def quad(a, b, c, d, role):
        tris.extend(((a, b, c), (a, c, d))); roles.extend((role, role))

    for i in range(nx):
        for j in range(ny):
            quad(vid(i, j, True), vid(i + 1, j, True), vid(i + 1, j + 1, True), vid(i, j + 1, True), 'top')
            quad(vid(i, j, False), vid(i, j + 1, False), vid(i + 1, j + 1, False), vid(i + 1, j, False), 'bottom')
    for i in range(nx):  # south (y0) and north (y1)
        quad(vid(i, 0, False), vid(i + 1, 0, False), vid(i + 1, 0, True), vid(i, 0, True), 'side')
        quad(vid(i + 1, ny, False), vid(i, ny, False), vid(i, ny, True), vid(i + 1, ny, True), 'side')
    for j in range(ny):  # west (x0) and east (x1)
        quad(vid(0, j + 1, False), vid(0, j, False), vid(0, j, True), vid(0, j + 1, True), 'side')
        quad(vid(nx, j, False), vid(nx, j + 1, False), vid(nx, j + 1, True), vid(nx, j, True), 'side')
    return tuple(verts), tuple(tris), tuple(roles)
