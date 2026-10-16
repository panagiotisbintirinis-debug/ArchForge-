"""Site plants (trees / shrubs) standing on the terrain.

``kind='plant'`` params: ``x, y`` (plan position), ``z`` (storey elevation
used when no terrain is under the plant), ``height`` (overall, m),
``canopy`` (crown diameter, m) and ``species`` ('tree' or 'shrub').
The mesh is a simple stylised trunk + low-poly crown; surface roles
'trunk' / 'canopy' carry the bark / foliage materials.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

SPECIES = {
    'tree': {'height': 4.0, 'canopy': 3.0},
    'shrub': {'height': 1.0, 'canopy': 1.2},
}


def plant_base_z(doc, params: Dict) -> float:
    from archforge.site.terrain import terrain_height_at
    ground = terrain_height_at(doc, float(params['x']), float(params['y']))
    storey = float(params.get('z', 0.0))
    # On the lowest storey a plant stands on the terrain; elsewhere (roof
    # terrace, balcony) on its own storey elevation.
    lowest = min([float(v) for v in doc.levels.values()] + [0.0])
    if ground is not None and storey <= lowest + 1e-6:
        return ground
    return storey


def plant_mesh(params: Dict, base_z: float):
    x, y = float(params['x']), float(params['y'])
    height = float(params['height']); canopy = float(params['canopy'])
    shrub = str(params.get('species', 'tree')) == 'shrub'
    radius = canopy / 2.0
    trunk_h = 0.05 * height if shrub else max(0.3, height - canopy * 0.85)
    trunk_w = max(0.06, min(0.4, height * 0.035))
    verts: List[Tuple[float, float, float]] = []
    tris: List[Tuple[int, int, int]] = []
    roles: List[str] = []

    def v(px, py, pz):
        verts.append((px, py, pz)); return len(verts) - 1

    # Trunk: closed square prism.
    hw = trunk_w / 2.0
    ring = [(x - hw, y - hw), (x + hw, y - hw), (x + hw, y + hw), (x - hw, y + hw)]
    lo = [v(px, py, base_z) for px, py in ring]
    hi = [v(px, py, base_z + trunk_h) for px, py in ring]
    for i in range(4):
        j = (i + 1) % 4
        tris += [(lo[i], lo[j], hi[j]), (lo[i], hi[j], hi[i])]; roles += ['trunk', 'trunk']
    tris += [(lo[0], lo[2], lo[1]), (lo[0], lo[3], lo[2]), (hi[0], hi[1], hi[2]), (hi[0], hi[2], hi[3])]
    roles += ['trunk'] * 4

    # Crown: closed UV ellipsoid sitting on the trunk.
    rz = (height - trunk_h) / 2.0 if not shrub else height / 2.0
    cz = base_z + (trunk_h + rz if not shrub else rz)
    seg, rings = 10, 6
    top = v(x, y, cz + rz); bottom = v(x, y, cz - rz)
    grid = []
    for r in range(1, rings):
        phi = math.pi * r / rings
        row = []
        for s in range(seg):
            th = 2 * math.pi * s / seg
            row.append(v(x + radius * math.sin(phi) * math.cos(th),
                         y + radius * math.sin(phi) * math.sin(th),
                         cz + rz * math.cos(phi)))
        grid.append(row)
    for s in range(seg):
        t = (s + 1) % seg
        tris.append((top, grid[0][s], grid[0][t])); roles.append('canopy')
        tris.append((bottom, grid[-1][t], grid[-1][s])); roles.append('canopy')
        for r in range(len(grid) - 1):
            a, b, c, d = grid[r][s], grid[r][t], grid[r + 1][t], grid[r + 1][s]
            tris += [(a, d, c), (a, c, b)]; roles += ['canopy', 'canopy']
    return tuple(verts), tuple(tris), tuple(roles)
