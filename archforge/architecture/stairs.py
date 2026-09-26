from __future__ import annotations

from dataclasses import dataclass
from math import atan2, ceil, cos, degrees, floor, hypot, pi, radians, sin
from typing import Dict, Iterable, List, Sequence, Tuple

Point2 = Tuple[float, float]


@dataclass(frozen=True)
class StairCandidate:
    layout: str
    origin: Point2
    angle_deg: float
    lower_z: float
    upper_z: float
    width: float
    riser_count: int
    riser_height: float
    tread_depth: float
    landing_depth: float
    turn_direction: int
    score: float
    suggestions: Tuple[str, ...] = ()

    @property
    def tread_count(self) -> int:
        return max(1, self.riser_count - 1)

    @property
    def floor_height(self) -> float:
        return self.upper_z - self.lower_z

    def to_params(self) -> Dict[str, object]:
        return {
            'x': float(self.origin[0]),
            'y': float(self.origin[1]),
            'lower_z': float(self.lower_z),
            'upper_z': float(self.upper_z),
            'layout': str(self.layout),
            'angle_deg': float(self.angle_deg),
            'width': float(self.width),
            'riser_count': int(self.riser_count),
            'riser_height': float(self.riser_height),
            'tread_depth': float(self.tread_depth),
            'landing_depth': float(self.landing_depth),
            'turn_direction': int(self.turn_direction),
            'opening_margin': 0.05,
        }


def _riser_solution(
    floor_height: float,
    preferred_riser: float = 0.17,
    min_riser: float = 0.15,
    max_riser: float = 0.19,
) -> Tuple[int, float, Tuple[str, ...]]:
    h = float(floor_height)
    if h <= 0:
        raise ValueError('stair upper level must be above lower level')
    target = max(2, int(round(h / float(preferred_riser))))
    candidates = []
    for n in range(max(2, target - 4), target + 5):
        r = h / n
        penalty = abs(r - preferred_riser)
        if min_riser <= r <= max_riser:
            penalty *= 0.2
        candidates.append((penalty, n, r))
    _, count, riser = min(candidates)
    notes = []
    if not (min_riser <= riser <= max_riser):
        notes.append(
            f'Riser {riser:.3f} m falls outside preferred {min_riser:.2f}-{max_riser:.2f} m range'
        )
    return count, riser, tuple(notes)


def _preferred_tread(riser: float, preferred_tread: float = 0.29) -> Tuple[float, Tuple[str, ...]]:
    # 0.28-0.30 m is the user's preferred human-design range.
    tread = min(0.30, max(0.28, float(preferred_tread)))
    notes = []
    comfort = 2.0 * float(riser) + tread
    if comfort < 0.60:
        notes.append('Increase tread or riser slightly for a more comfortable proportion')
    elif comfort > 0.66:
        notes.append('Reduce tread or riser slightly for a more compact proportion')
    return tread, tuple(notes)


def _layout_score(layout: str, available_run: float, required_run: float) -> float:
    shortage = max(0.0, required_run - max(0.0, available_run))
    excess = max(0.0, available_run - required_run)
    compact_bias = {'straight': 0.0, 'l': 0.10, 'u': 0.18, 'spiral': 0.28}.get(layout, 0.5)
    return shortage * 10.0 + excess * 0.03 + compact_bias


def solve_stair_candidates(
    lower_z: float,
    upper_z: float,
    origin: Point2,
    pointer: Point2,
    *,
    width: float = 1.0,
    preferred_riser: float = 0.17,
    preferred_tread: float = 0.29,
    landing_depth: float | None = None,
) -> Tuple[StairCandidate, ...]:
    """Generate ranked live stair alternatives from one placement drag.

    Pointer direction controls orientation. Pointer distance is treated as the
    currently available straight run, so candidates react continuously as the
    user moves the mouse.
    """
    ox, oy = map(float, origin)
    px, py = map(float, pointer)
    dx, dy = px - ox, py - oy
    available = hypot(dx, dy)
    angle = degrees(atan2(dy, dx)) if available > 1e-9 else 0.0
    width = float(width)
    if width <= 0:
        raise ValueError('stair width must be positive')

    risers, riser, riser_notes = _riser_solution(
        float(upper_z) - float(lower_z),
        preferred_riser=preferred_riser,
    )
    tread, tread_notes = _preferred_tread(riser, preferred_tread)
    treads = max(1, risers - 1)
    landing = max(width, float(landing_depth if landing_depth is not None else width))

    straight_run = treads * tread
    first = max(1, treads // 2)
    second = treads - first
    l_run = max(first * tread, second * tread) + landing
    u_run = max(first, second) * tread + landing
    spiral_radius = max(width * 0.95, 0.85)
    spiral_run_equivalent = 2.0 * spiral_radius

    base_notes = tuple(riser_notes) + tuple(tread_notes)
    layouts = (
        ('straight', straight_run, 1),
        ('l', l_run, 1),
        ('l', l_run, -1),
        ('u', u_run, 1),
        ('u', u_run, -1),
        ('spiral', spiral_run_equivalent, 1),
        ('spiral', spiral_run_equivalent, -1),
    )
    result = []
    for layout, required, turn in layouts:
        notes = list(base_notes)
        if available > 1e-6 and required > available:
            notes.append(
                f'{layout.upper()} needs about {required:.2f} m; current pointer run is {available:.2f} m'
            )
            if layout == 'straight':
                notes.append('Try L/U/spiral, add one riser, or allow a longer run')
        result.append(
            StairCandidate(
                layout=layout,
                origin=(ox, oy),
                angle_deg=angle,
                lower_z=float(lower_z),
                upper_z=float(upper_z),
                width=width,
                riser_count=risers,
                riser_height=riser,
                tread_depth=tread,
                landing_depth=landing,
                turn_direction=turn,
                score=_layout_score(layout, available, required),
                suggestions=tuple(notes),
            )
        )
    return tuple(sorted(result, key=lambda c: (c.score, c.layout, -c.turn_direction)))


def candidate_from_params(params) -> StairCandidate:
    return StairCandidate(
        layout=str(params['layout']),
        origin=(float(params['x']), float(params['y'])),
        angle_deg=float(params['angle_deg']),
        lower_z=float(params['lower_z']),
        upper_z=float(params['upper_z']),
        width=float(params['width']),
        riser_count=int(params['riser_count']),
        riser_height=float(params['riser_height']),
        tread_depth=float(params['tread_depth']),
        landing_depth=float(params.get('landing_depth', params['width'])),
        turn_direction=1 if int(params.get('turn_direction', 1)) >= 0 else -1,
        score=0.0,
        suggestions=(),
    )


def _local_to_world(candidate: StairCandidate, x: float, y: float) -> Point2:
    a = radians(candidate.angle_deg)
    c, s = cos(a), sin(a)
    ox, oy = candidate.origin
    return (ox + c * x - s * y, oy + s * x + c * y)


def stair_centerline(candidate: StairCandidate) -> Tuple[Point2, ...]:
    n = candidate.tread_count
    t = candidate.tread_depth
    w = candidate.width
    landing = candidate.landing_depth
    turn = float(candidate.turn_direction)

    if candidate.layout == 'straight':
        local = ((0.0, 0.0), (n * t, 0.0))
    elif candidate.layout == 'l':
        first = max(1, n // 2)
        second = n - first
        p1 = first * t
        local = (
            (0.0, 0.0),
            (p1, 0.0),
            (p1 + landing / 2.0, 0.0),
            (p1 + landing / 2.0, turn * (second * t + landing / 2.0)),
        )
    elif candidate.layout == 'u':
        first = max(1, n // 2)
        second = n - first
        p1 = first * t
        offset = turn * (w + 0.20)
        local = (
            (0.0, 0.0),
            (p1, 0.0),
            (p1 + landing, 0.0),
            (p1 + landing, offset),
            (p1 + landing - second * t, offset),
        )
    elif candidate.layout == 'spiral':
        radius = max(w * 0.95, 0.85)
        points = []
        sweep = turn * 2.0 * pi
        for i in range(max(12, n + 1)):
            u = i / max(1, max(12, n + 1) - 1)
            a = sweep * u
            points.append((radius * cos(a), radius * sin(a)))
        local = tuple(points)
    else:
        raise ValueError(f'unsupported stair layout: {candidate.layout}')

    return tuple(_local_to_world(candidate, x, y) for x, y in local)


def stair_footprint(candidate: StairCandidate, margin: float = 0.0) -> Tuple[Point2, ...]:
    """Return a conservative footprint polygon for plan display/opening envelope."""
    path = stair_centerline(candidate)
    xs = [p[0] for p in path]
    ys = [p[1] for p in path]
    half = candidate.width / 2.0 + float(margin)
    return (
        (min(xs) - half, min(ys) - half),
        (max(xs) + half, min(ys) - half),
        (max(xs) + half, max(ys) + half),
        (min(xs) - half, max(ys) + half),
    )


def stair_opening_polygon(candidate: StairCandidate) -> Tuple[Point2, ...]:
    # First implementation uses a conservative safe opening envelope.
    # Later headroom analysis can trim the lower-flight area while preserving clearance.
    return stair_footprint(candidate, margin=0.05)


def next_level_above(doc, z: float):
    levels = sorted((float(value), str(name)) for name, value in doc.levels.items() if float(value) > float(z) + 1e-6)
    return levels[0] if levels else None
