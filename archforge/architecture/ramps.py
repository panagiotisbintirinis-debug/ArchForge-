from __future__ import annotations

from dataclasses import dataclass
from math import atan2, degrees, hypot, radians, cos, sin
from typing import Dict, Tuple

from archforge.architecture.stairs import upper_floor_landing

Point2 = Tuple[float, float]


@dataclass(frozen=True)
class RampCandidate:
    origin: Point2
    angle_deg: float
    lower_z: float
    upper_z: float
    upper_floor_z: float
    upper_slab_thickness: float
    width: float
    slope_pct: float
    run_length: float
    thickness: float
    score: float

    @property
    def rise(self) -> float:
        return self.upper_z - self.lower_z

    def to_params(self) -> Dict[str, float]:
        return {
            'x': float(self.origin[0]),
            'y': float(self.origin[1]),
            'lower_z': float(self.lower_z),
            'upper_z': float(self.upper_z),
            'upper_floor_z': float(self.upper_floor_z),
            'upper_slab_thickness': float(self.upper_slab_thickness),
            'angle_deg': float(self.angle_deg),
            'width': float(self.width),
            'slope_pct': float(self.slope_pct),
            'run_length': float(self.run_length),
            'thickness': float(self.thickness),
            'opening_margin': 0.05,
        }


def solve_ramp_candidates(
    doc,
    lower_z: float,
    origin: Point2,
    pointer: Point2,
    *,
    width: float = 1.20,
    thickness: float = 0.15,
    slope_presets=(5.0, 6.0, 8.0, 10.0, 12.0, 15.0),
):
    landing = upper_floor_landing(doc, float(lower_z), origin)
    if landing is None:
        raise ValueError('Create or infer an upper floor before placing a ramp')

    ox, oy = map(float, origin)
    px, py = map(float, pointer)
    dx, dy = px - ox, py - oy
    available = hypot(dx, dy)
    angle = degrees(atan2(dy, dx)) if available > 1e-9 else 0.0

    upper_floor_z = float(landing['floor_z'])
    slab_thickness = float(landing['slab_thickness'])
    upper_z = float(landing['landing_z'])
    rise = upper_z - float(lower_z)
    if rise <= 0:
        raise ValueError('ramp upper landing must be above lower level')

    out = []
    for slope in slope_presets:
        slope = float(slope)
        if slope <= 0:
            continue
        run = rise / (slope / 100.0)
        # Pointer distance ranks the available presets without changing the exact
        # engineering relationship rise/run=slope.
        score = abs(run - available)
        out.append(
            RampCandidate(
                origin=(ox, oy),
                angle_deg=angle,
                lower_z=float(lower_z),
                upper_z=upper_z,
                upper_floor_z=upper_floor_z,
                upper_slab_thickness=slab_thickness,
                width=float(width),
                slope_pct=slope,
                run_length=run,
                thickness=float(thickness),
                score=score,
            )
        )
    if not out:
        raise ValueError('no ramp slope presets available')
    return tuple(sorted(out, key=lambda candidate: (candidate.score, candidate.slope_pct)))


def candidate_from_params(params):
    return RampCandidate(
        origin=(float(params['x']), float(params['y'])),
        angle_deg=float(params['angle_deg']),
        lower_z=float(params['lower_z']),
        upper_z=float(params['upper_z']),
        upper_floor_z=float(params.get('upper_floor_z', params['upper_z'])),
        upper_slab_thickness=float(params.get('upper_slab_thickness', 0.0)),
        width=float(params['width']),
        slope_pct=float(params['slope_pct']),
        run_length=float(params['run_length']),
        thickness=float(params.get('thickness', 0.15)),
        score=0.0,
    )


def ramp_footprint(candidate: RampCandidate, margin: float = 0.0):
    half = candidate.width / 2.0 + float(margin)
    run = candidate.run_length
    a = radians(candidate.angle_deg)
    ux, uy = cos(a), sin(a)
    vx, vy = -uy, ux
    ox, oy = candidate.origin

    def point(along, across):
        return (
            ox + ux * along + vx * across,
            oy + uy * along + vy * across,
        )

    return (
        point(0.0, -half),
        point(run, -half),
        point(run, half),
        point(0.0, half),
    )


def ramp_opening_polygon(candidate: RampCandidate):
    return ramp_footprint(candidate, margin=0.05)
