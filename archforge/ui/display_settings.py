from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

ColorRGB = Tuple[int, int, int]


@dataclass(frozen=True)
class ViewportDisplaySettings:
    """View-only 3D display palette; never part of authoritative Document state."""

    background: ColorRGB = (222, 226, 232)
    grid: ColorRGB = (187, 193, 201)
    selected: ColorRGB = (72, 145, 225)
    wall: ColorRGB = (184, 195, 207)
    floor: ColorRGB = (166, 184, 171)
    surface: ColorRGB = (176, 186, 201)
