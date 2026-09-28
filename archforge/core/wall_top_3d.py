from __future__ import annotations

import math
from typing import Mapping, Tuple

Vec3 = Tuple[float, float, float]


def wall_top_endpoint_world(params: Mapping[str, object], endpoint: str) -> Vec3:
    """Return the semantic wall-top endpoint in world coordinates.

    Endpoint identity follows the wall's stored start/end direction; no global-axis
    classification or snapping is involved.
    """
    if endpoint not in ('start', 'end'):
        raise ValueError("endpoint must be 'start' or 'end'")
    legacy = float(params['height'])
    if endpoint == 'start':
        x, y = float(params['x1']), float(params['y1'])
        height = float(params.get('start_height', legacy))
    else:
        x, y = float(params['x2']), float(params['y2'])
        height = float(params.get('end_height', legacy))
    z = float(params['z']) + height
    if not all(math.isfinite(v) for v in (x, y, z)):
        raise ValueError('wall top endpoint must be finite')
    return x, y, z


def vertical_height_from_ray(
    base_z: float,
    endpoint_xy: Tuple[float, float],
    ray_origin: Vec3,
    ray_direction: Vec3,
) -> float:
    """Map a perspective pointer ray to height on an endpoint's vertical edit line.

    This is the closest-points solution between the camera ray and the semantic
    endpoint's world-Z line.  It keeps the endpoint fixed in host-local XY while
    allowing direct 3D height editing independent of wall rotation.
    """
    ox, oy, oz = (float(v) for v in ray_origin)
    dx, dy, dz = (float(v) for v in ray_direction)
    px, py = (float(v) for v in endpoint_xy)
    base_z = float(base_z)
    if not all(math.isfinite(v) for v in (ox, oy, oz, dx, dy, dz, px, py, base_z)):
        raise ValueError('3D wall-top drag inputs must be finite')
    norm = math.sqrt(dx * dx + dy * dy + dz * dz)
    if norm <= 1e-12:
        raise ValueError('ray direction must be non-zero')
    dx, dy, dz = dx / norm, dy / norm, dz / norm

    # Ray r(t)=o+t*d, vertical edit line l(s)=(px,py,base_z+s).
    # Eliminating s from the closest-points equations leaves the XY projection.
    denom = dx * dx + dy * dy
    if denom <= 1e-12:
        raise ValueError('camera ray is parallel to the vertical edit line')
    t = ((px - ox) * dx + (py - oy) * dy) / denom
    top_z = oz + t * dz
    height = top_z - base_z
    if not math.isfinite(height) or height <= 0.0:
        raise ValueError('wall top must remain above base')
    return height
