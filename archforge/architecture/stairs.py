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
    upper_floor_z: float
    upper_slab_thickness: float
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
            'upper_floor_z': float(self.upper_floor_z),
            'upper_slab_thickness': float(self.upper_slab_thickness),
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
    upper_floor_z: float | None = None,
    upper_slab_thickness: float = 0.0,
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

    upper_floor_z = float(upper_z if upper_floor_z is None else upper_floor_z)
    upper_slab_thickness = max(0.0, float(upper_slab_thickness))
    landing_z = float(upper_floor_z) + upper_slab_thickness
    risers, riser, riser_notes = _riser_solution(
        landing_z - float(lower_z),
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
                upper_z=landing_z,
                upper_floor_z=upper_floor_z,
                upper_slab_thickness=upper_slab_thickness,
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
        upper_floor_z=float(params.get('upper_floor_z', params['upper_z'])),
        upper_slab_thickness=float(params.get('upper_slab_thickness', 0.0)),
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


def _polyline_tail_from_fraction(path: Sequence[Point2], fraction: float) -> Tuple[Point2, ...]:
    pts = tuple((float(x), float(y)) for x, y in path)
    if len(pts) < 2:
        return pts
    fraction = max(0.0, min(1.0, float(fraction)))
    lengths = [
        hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
        for i in range(len(pts) - 1)
    ]
    total = sum(lengths)
    if total <= 1e-12:
        return pts
    target = total * fraction
    walked = 0.0
    for i, seg_len in enumerate(lengths):
        if walked + seg_len + 1e-12 < target:
            walked += seg_len
            continue
        u = 0.0 if seg_len <= 1e-12 else (target - walked) / seg_len
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        start = (ax + (bx - ax) * u, ay + (by - ay) * u)
        return (start,) + pts[i + 1:]
    return (pts[-1],)


def stair_opening_polygon(
    candidate: StairCandidate,
    headroom: float = 2.0,
) -> Tuple[Point2, ...]:
    """Opening envelope for the upper part of the stair that needs headroom.

    The previous implementation used the complete stair footprint, so a stair
    beginning outside a room could prevent *any* slab opening. Here the opening
    begins where the tread elevation enters the required headroom zone below the
    upper slab and follows only the remaining upper path.
    """
    path = stair_centerline(candidate)
    total_rise = max(1e-9, float(candidate.upper_z) - float(candidate.lower_z))
    slab_underside = float(candidate.upper_floor_z)
    start_elevation = max(
        float(candidate.lower_z),
        slab_underside - max(0.1, float(headroom)),
    )
    fraction = (start_elevation - float(candidate.lower_z)) / total_rise
    upper_path = _polyline_tail_from_fraction(path, fraction)
    if not upper_path:
        upper_path = path

    xs = [p[0] for p in upper_path]
    ys = [p[1] for p in upper_path]
    half = float(candidate.width) / 2.0 + 0.05
    return (
        (min(xs) - half, min(ys) - half),
        (max(xs) + half, min(ys) - half),
        (max(xs) + half, max(ys) + half),
        (min(xs) - half, max(ys) + half),
    )


def _point_in_polygon(point: Point2, polygon: Sequence[Point2]) -> bool:
    x, y = map(float, point)
    inside = False
    pts = [(float(px), float(py)) for px, py in polygon]
    if len(pts) < 3:
        return False
    j = len(pts) - 1
    for i, (xi, yi) in enumerate(pts):
        xj, yj = pts[j]
        if (yi > y) != (yj > y):
            at_x = xj + (y - yj) * (xi - xj) / (yi - yj)
            if x < at_x:
                inside = not inside
        j = i
    return inside


def discover_building_levels(doc, tolerance: float = 1e-5):
    """Merge declared levels with elevations already present in building geometry.

    This also acts as a compatibility bridge for older ArchForge projects that
    contain second-storey walls/slabs but predate the explicit Floor registry.
    """
    explicit = [
        (float(value), str(name), False)
        for name, value in doc.levels.items()
    ]
    candidates = list(explicit)

    from archforge.architecture.rooms import room_slab_geometry
    for entity in doc.entities.values():
        p = entity.params
        if entity.kind == 'wall':
            candidates.append((float(p.get('z', 0.0)), '', True))
        elif entity.kind == 'pod':
            candidates.append((float(p.get('floor_level', 0.0)), '', True))
        elif entity.kind in ('floor', 'room'):
            candidates.append((float(p.get('z', 0.0)), '', True))
        elif entity.kind == 'room_floor':
            geom = room_slab_geometry(doc, entity)
            if geom is not None:
                candidates.append((float(geom['z']), '', True))

    merged = []
    for elevation, name, inferred in sorted(candidates, key=lambda item: item[0]):
        existing = next(
            (item for item in merged if abs(item['elevation'] - elevation) <= tolerance),
            None,
        )
        if existing is None:
            merged.append({
                'elevation': elevation,
                'name': name,
                'inferred': inferred,
            })
        elif name and existing['inferred']:
            existing['name'] = name
            existing['inferred'] = False

    used_names = {item['name'] for item in merged if item['name']}
    floor_number = 2
    for item in merged:
        if item['name']:
            continue
        while f'Floor {floor_number}' in used_names:
            floor_number += 1
        item['name'] = f'Floor {floor_number}'
        used_names.add(item['name'])
        floor_number += 1

    return tuple(merged)


def upper_floor_landing(doc, lower_z: float, point: Point2 | None = None):
    """Resolve next level plus the actual room-floor slab thickness.

    The level elevation identifies the slab base; landing_z is its top surface.
    If multiple room floors exist, prefer the slab containing the placement point.
    """
    next_level = next_level_above(doc, lower_z)
    if next_level is None:
        return None
    level_z, level_name = next_level

    from archforge.architecture.rooms import room_slab_geometry
    matches = []
    for entity in doc.entities.values():
        if entity.kind == 'room_floor':
            geom = room_slab_geometry(doc, entity)
            if geom is None:
                continue
            slab_z = float(geom['z'])
            slab_points = geom['points']
            slab_thickness = float(geom['thickness'])
        elif entity.kind == 'floor':
            slab_z = float(entity.params['z'])
            slab_points = entity.params['points']
            slab_thickness = float(entity.params['thickness'])
        else:
            continue
        if abs(slab_z - float(level_z)) > 1e-5:
            continue
        contains = bool(point is not None and _point_in_polygon(point, slab_points))
        matches.append((contains, slab_thickness, entity.id))

    if matches:
        containing = [item for item in matches if item[0]]
        pool = containing if containing else matches
        # If several room slabs share the level, choose the thickest safe landing
        # unless the placement point identifies its exact host slab.
        thickness = max(item[1] for item in pool)
    else:
        thickness = 0.0

    return {
        'level_name': str(level_name),
        'floor_z': float(level_z),
        'slab_thickness': float(thickness),
        'landing_z': float(level_z) + float(thickness),
    }


def next_level_above(doc, z: float):
    levels = [
        (float(item['elevation']), str(item['name']))
        for item in discover_building_levels(doc)
        if float(item['elevation']) > float(z) + 1e-6
    ]
    return levels[0] if levels else None
