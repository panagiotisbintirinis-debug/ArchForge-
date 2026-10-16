"""Sun position for the 3D Scene (render state, not design data).

Plan axes: +y is north, +x is east. Angles in degrees; ``azimuth`` is
measured clockwise from north. Default latitude 38° N (Greece).
"""
from __future__ import annotations

import math
from typing import Tuple

DEFAULT_LATITUDE = 38.0
# Mid-month day-of-year, for month 1..12.
_MID_MONTH_DAY = (17, 47, 75, 105, 135, 162, 198, 228, 258, 288, 318, 344)


def sun_position(hour: float, month: int = 6, latitude: float = DEFAULT_LATITUDE) -> Tuple[float, float]:
    """(elevation, azimuth) of the sun at solar time ``hour`` in ``month``."""
    if not 1 <= int(month) <= 12:
        raise ValueError('month must be 1..12')
    day = _MID_MONTH_DAY[int(month) - 1]
    decl = math.radians(23.44 * math.sin(math.radians(360.0 / 365.0 * (284 + day))))
    lat = math.radians(float(latitude))
    h = math.radians(15.0 * (float(hour) - 12.0))
    sin_el = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(h)
    el = math.asin(max(-1.0, min(1.0, sin_el)))
    az = math.atan2(math.sin(h), math.cos(h) * math.sin(lat) - math.tan(decl) * math.cos(lat))
    return math.degrees(el), (math.degrees(az) + 180.0) % 360.0


def sun_direction(elevation: float, azimuth: float) -> Tuple[float, float, float]:
    """Unit vector from the scene towards the sun (x east, y north, z up)."""
    el, az = math.radians(elevation), math.radians(azimuth)
    return (math.cos(el) * math.sin(az), math.cos(el) * math.cos(az), math.sin(el))
