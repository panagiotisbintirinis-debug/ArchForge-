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
        # The second flight starts from the landing's near edge, back alongside the first.
        local = (
            (0.0, 0.0),
            (p1, 0.0),
            (p1 + landing / 2.0, 0.0),
            (p1 + landing / 2.0, offset),
            (p1, offset),
            (p1 - second * t, offset),
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


# --- walls: a stair is placed in a building, not in empty space (owner 14/10) ----------------------

WALL_CLEARANCE = 0.01


def _seg_seg_distance(a, b, c, d) -> float:
    """Shortest distance between segments ab and cd (0 when they cross)."""
    def cross(o, p, q):
        return (p[0] - o[0]) * (q[1] - o[1]) - (p[1] - o[1]) * (q[0] - o[0])
    d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
    if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 and d2 and d3 and d4:
        return 0.0
    return min(_point_seg_distance(a, c, d), _point_seg_distance(b, c, d),
               _point_seg_distance(c, a, b), _point_seg_distance(d, a, b))


def _point_seg_distance(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 <= 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _spiral_disc(candidate: StairCandidate):
    """Centre and outer radius of a spiral stair (its walking line is a circle round the origin)."""
    return candidate.origin, max(candidate.width * 0.95, 0.85) + candidate.width / 2.0


def stair_walls(doc, lower_z: float, upper_floor_z: float):
    """Walls a stair between the two levels must not cross: those of the storey it starts from and the one it reaches."""
    out = []
    for e in doc.entities.values():
        if e.kind != 'wall':
            continue
        z = float(e.params.get('z', 0.0))
        if abs(z - float(lower_z)) < 1e-3 or abs(z - float(upper_floor_z)) < 1e-3:
            out.append(e)
    return out


def _point_in_convex(p, poly) -> bool:
    from archforge.geometry.regions import point_in_polygon
    return point_in_polygon(p[0], p[1], poly)


def _wall_in_opening(a, b, openings, reach) -> bool:
    """The wall axis ab within ``reach`` of one of the slab opening pieces (or inside it)."""
    seg = (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
    for poly in openings:
        if _apart(seg, _bbox(poly, reach)):
            continue
        if _point_in_convex(a, poly) or _point_in_convex(b, poly):
            return True
        n = len(poly)
        if any(_seg_seg_distance(a, b, poly[i], poly[(i + 1) % n]) < reach for i in range(n)):
            return True
    return False


def stair_wall_conflicts(doc, candidate: StairCandidate, walls=None) -> List[str]:
    """Ids of the walls the stair runs through.

    Walls of the storey it starts from: the walking line closer than half its width + half the wall.
    Walls of the storey it reaches: only where the slab must open (a wall over the low steps, where
    there is headroom, stands on the slab — the upper space is used; owner 14/10).
    """
    walls = stair_walls(doc, candidate.lower_z, candidate.upper_floor_z) if walls is None else walls
    # Walls far from the stair cannot meet it: their boxes fall out first (this runs for every trial position).
    reach = _bbox(stair_footprint(candidate), candidate.width + 0.5)
    walls = [w for w in walls if not _apart(reach, (min(float(w.params['x1']), float(w.params['x2'])),
                                                    min(float(w.params['y1']), float(w.params['y2'])),
                                                    max(float(w.params['x1']), float(w.params['x2'])),
                                                    max(float(w.params['y1']), float(w.params['y2']))))]
    upper = [w for w in walls if abs(float(w.params.get('z', 0.0)) - float(candidate.upper_floor_z)) < 1e-3]
    if upper:
        openings = stair_opening_polygons(candidate)
        upper_hits = [w.id for w in upper
                      if _wall_in_opening((float(w.params['x1']), float(w.params['y1'])),
                                          (float(w.params['x2']), float(w.params['y2'])),
                                          openings, float(w.params.get('thickness', 0.2)) / 2.0 - WALL_CLEARANCE)]
        walls = [w for w in walls if w not in upper]
    else:
        upper_hits = []
    half = candidate.width / 2.0
    hits = list(upper_hits)
    if candidate.layout == 'spiral':
        centre, radius = _spiral_disc(candidate)
        for w in walls:
            p = w.params
            gap = _point_seg_distance(centre, (float(p['x1']), float(p['y1'])), (float(p['x2']), float(p['y2'])))
            if gap < radius + float(p.get('thickness', 0.2)) / 2.0 - WALL_CLEARANCE:
                hits.append(w.id)
        return hits
    path = stair_centerline(candidate)
    for w in walls:
        p = w.params
        a, b = (float(p['x1']), float(p['y1'])), (float(p['x2']), float(p['y2']))
        reach = half + float(p.get('thickness', 0.2)) / 2.0 - WALL_CLEARANCE
        if any(_seg_seg_distance(path[i], path[i + 1], a, b) < reach for i in range(len(path) - 1)):
            hits.append(w.id)
    return hits


# What else a stair must keep clear of on the storey it starts from (driving the house as a user, 23/10: an L
# stair "fitted" in the living room with its landing in the swing of a bedroom door and its flight against the
# kitchen run — only walls were looked at).
DOOR_CLEAR_MAX = 1.0          # m in front of a door, both sides: you walk through it


def stair_obstacles(doc, lower_z: float, upper_floor_z: float):
    """``[(id, polygon)]`` on the storey a stair starts from: the free space each side of every door, the
    footprint of every cabinet / object standing there and of every other stair that starts or arrives there.
    On the storey it reaches (doors, cabinets, stairs starting there) they come as ``(id, polygon, "upper")``:
    the slab opening it comes up through must not land on them."""
    from archforge.architecture.openings import plan_segment
    from archforge.architecture.wall_dims import footprint
    out = []
    lo, hi = float(lower_z) - 0.05, float(upper_floor_z) - 0.05
    for e in doc.entities.values():
        if not e.visible:
            continue
        if e.kind == 'stair':
            try:
                fp = [tuple(q) for q in stair_footprint(candidate_from_params(e.params))]
            except (KeyError, TypeError, ValueError) as exc:
                from archforge.core.notices import not_computed
                not_computed('stair.obstacle', f'Σκάλα: η σκάλα «{e.name or e.id}» δεν ελέγχθηκε για σύγκρουση', e.id, exc)
                continue
            sl, su = float(e.params.get('lower_z', 0.0)), float(e.params.get('upper_floor_z', e.params.get('upper_z', 0.0)))
            if su < float(lower_z) - 0.2 or sl > float(upper_floor_z) + 0.2:
                continue                                     # wholly below / above: cannot meet
            # In 3D: where the two walking surfaces are closer than the headroom (two stairs of one floor crossing,
            # a flight over another's low steps or where you step off it) — a stacked stairwell passes.
            cells = _stair_cells(candidate_from_params(e.params))
            pts = [q for v in cells.values() for q in v]
            out.append((e.id, cells, 'stair3d', (min(q[0] for q in pts), min(q[1] for q in pts),
                                                 max(q[0] for q in pts), max(q[1] for q in pts))))
            continue
        if e.kind == 'door' and e.parent_id in doc.entities:
            w = doc.get(e.parent_id)
            wz = float(w.params.get('z', 0.0))
            where = () if abs(wz - float(lower_z)) <= 1e-3 else (('upper',) if abs(wz - float(upper_floor_z)) <= 1e-3 else None)
            if w.kind != 'wall' or where is None:
                continue
            try:
                (ax, ay), (bx, by) = plan_segment(w.params, e.params)
            except (KeyError, TypeError, ValueError) as exc:
                from archforge.core.notices import not_computed
                not_computed('stair.door', f'Σκάλα: η πόρτα «{e.name or e.id}» δεν ελέγχθηκε για σύγκρουση', e.id, exc)
                continue
            L = hypot(bx - ax, by - ay)
            if L < 1e-6:
                continue
            nx, ny = -(by - ay) / L, (bx - ax) / L
            t = float(w.params.get('thickness', 0.2)) / 2.0
            d = t + min(L, DOOR_CLEAR_MAX)
            out.append((e.id, [(ax + nx * d, ay + ny * d), (bx + nx * d, by + ny * d),
                               (bx - nx * d, by - ny * d), (ax - nx * d, ay - ny * d)]) + where)
        elif e.kind in ('cabinet', 'library_object'):
            f = footprint(e.params)
            z = float(e.params.get('z', lower_z) or 0.0)
            if f is None:
                continue
            if lo <= z < hi:
                where = ()
            elif float(upper_floor_z) - 0.05 <= z < float(upper_floor_z) + 2.0:
                where = ('upper',)                  # standing where the stair arrives
            else:
                continue
            cx, cy, ux, uy, hw, hd = f
            vx, vy = -uy, ux
            out.append((e.id, [(cx + sx * ux * hw + sy * vx * hd, cy + sx * uy * hw + sy * vy * hd)
                               for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]) + where)
    # Driving the house (23/10): an outside stair turned away from the balcony and ended in mid-air at +2,85.
    # Where the storey it reaches has floors, it must arrive on one of them.
    floors = upper_floors(doc, upper_floor_z)
    if floors:
        out.append(('arrival', floors, 'arrive'))
    return out


def upper_floors(doc, z: float):
    """Plan polygons of what you can stand on at storey ``z``: its rooms, its free slabs (balconies, terraces) and
    its storey slabs.  Empty when nothing is drawn there yet."""
    from archforge.architecture.balcony import slab_level
    out = []
    try:
        out += [list(f.polygon) for f in doc.active_room_faces(z=float(z))]
    except (ValueError, KeyError):
        pass
    for e in doc.entities.values():
        p = e.params
        if e.kind == 'floor' and p.get('points') and abs(slab_level(p) - float(z)) < 0.3:
            out.append([tuple(q[:2]) for q in p['points']])
        elif e.kind in ('room_floor', 'room_roof') and p.get('scope') == 'storey' and p.get('polygon') \
                and abs(float(p.get('level_z', 1e9)) - float(z)) < 0.3:
            out.append([tuple(q[:2]) for q in p['polygon']])
    return out


def arrival_point(candidate: StairCandidate) -> Point2:
    """Where you step off the stair: 30 cm past the end of its walking line."""
    path = stair_centerline(candidate)
    (ax, ay), (bx, by) = path[-2], path[-1]
    L = hypot(bx - ax, by - ay) or 1.0
    return bx + (bx - ax) / L * 0.30, by + (by - ay) / L * 0.30


HEADROOM = 2.10            # m of clear height under a flight passing over another stair's opening (practice, προς έλεγχο)


def _arrival_zone(c: StairCandidate):
    """The floor where you step off a stair: its width, 1 m past the end of its walking line."""
    path = stair_centerline(c)
    (ax, ay), (ex, ey) = path[-2], path[-1]
    L = hypot(ex - ax, ey - ay) or 1.0
    dx, dy = (ex - ax) / L, (ey - ay) / L
    nx, ny, h = -dy, dx, c.width / 2.0
    return [(ex + nx * h, ey + ny * h), (ex + dx + nx * h, ey + dy + ny * h),
            (ex + dx - nx * h, ey + dy - ny * h), (ex - nx * h, ey - ny * h)]


CELL = 0.25                # m: the grid the stairs' walking surfaces are compared on
NEAR = 0.12                # m in plan: two samples this close are over each other


def _stair_points(c: StairCandidate, step: float = 0.2):
    """``(x, y, z)`` of a stair's walking surface (flights and landings, edge to edge) and of the floor where you step
    off it (its arrival zone, at its top level)."""
    path = stair_centerline(c)
    lengths = [hypot(path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]) for i in range(len(path) - 1)]
    total = sum(lengths) or 1.0
    rise = float(c.upper_z) - float(c.lower_z)
    half = c.width / 2.0 - WALL_CLEARANCE
    lat = max(1, int(round(2 * half / step)))
    out, walked = [], 0.0
    for (a, b), L in zip(zip(path, path[1:]), lengths):
        if L < 1e-9:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = max(1, int(L / step))
        for k in range(n + 1):
            t = L * k / n
            x, y, z = a[0] + ux * t, a[1] + uy * t, float(c.lower_z) + rise * (walked + t) / total
            for j in range(lat + 1):
                o = -half + 2 * half * j / lat
                out.append((x - uy * o, y + ux * o, z))
        walked += L
    zone = _arrival_zone(c)
    (x0, y0), (x1, y1), _x2, (x3, y3) = zone
    for i in range(6):
        for j in range(lat + 1):
            fu, fv = i / 5, j / lat
            out.append((x0 + (x1 - x0) * fu + (x3 - x0) * fv, y0 + (y1 - y0) * fu + (y3 - y0) * fv, float(c.upper_z)))
    return out


def _stair_cells(c: StairCandidate):
    cells = {}
    for x, y, z in _stair_points(c):
        cells.setdefault((int(x // CELL), int(y // CELL)), []).append((x, y, z))
    return cells


def _stairs_clash(c: StairCandidate, cells) -> bool:
    """The stair's walking surface comes within the headroom of the other's (``_stair_cells``) somewhere."""
    for x, y, z in _stair_points(c):
        i, j = int(x // CELL), int(y // CELL)
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for qx, qy, qz in cells.get((i + di, j + dj), ()):
                    if abs(qz - z) < HEADROOM and abs(qx - x) < NEAR and abs(qy - y) < NEAR:
                        return True
    return False


def _bbox(poly, grow=0.0):
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    return min(xs) - grow, min(ys) - grow, max(xs) + grow, max(ys) + grow


def _apart(a, b) -> bool:
    """Two boxes (``_bbox``) that do not touch: nothing inside them can meet."""
    return a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1]


def _polygons_overlap(a, b) -> bool:
    """Two plan polygons share area (a corner inside the other, or crossing edges)."""
    from archforge.geometry.regions import point_in_polygon
    if _apart(_bbox(a), _bbox(b)):
        return False
    if any(point_in_polygon(q[0], q[1], b) for q in a) or any(point_in_polygon(q[0], q[1], a) for q in b):
        return True
    na, nb = len(a), len(b)
    return any(_seg_seg_distance(a[i], a[(i + 1) % na], b[j], b[(j + 1) % nb]) < 1e-6
               for i in range(na) for j in range(nb))


def stair_obstacle_conflicts(candidate: StairCandidate, obstacles) -> List[str]:
    """Ids of the obstacles (``stair_obstacles``) the stair's flights or landings run into."""
    from archforge.geometry.regions import point_in_polygon
    hits = []
    # Far away obstacles first fall out on their boxes (this runs for every trial position of every mouse move).
    reach = _bbox(stair_footprint(candidate), candidate.width)
    for o in obstacles:
        if len(o) > 2 and o[2] == 'arrive':
            ax, ay = arrival_point(candidate)
            if not any(point_in_polygon(ax, ay, poly) for poly in o[1]):
                hits.append(o[0])
    obstacles = [o for o in obstacles if not (len(o) > 2 and o[2] == 'arrive')]
    for o in [o for o in obstacles if len(o) > 2 and o[2] == 'stair3d']:
        if not _apart(reach, o[3]) and _stairs_clash(candidate, o[1]):
            hits.append(o[0])
    obstacles = [o for o in obstacles if not (len(o) > 2 and o[2] == 'stair3d')]
    near = [o for o in obstacles if not _apart(reach, _bbox(o[1]))]
    upper = [o for o in near if len(o) > 2]
    obstacles = [o[:2] for o in near if len(o) == 2]
    if upper:
        openings = stair_opening_polygons(candidate)
        for oid, poly, _where in upper:
            if any(_polygons_overlap(op, poly) for op in openings):
                hits.append(oid)
    if candidate.layout == 'spiral':
        centre, radius = _spiral_disc(candidate)
        for oid, poly in obstacles:
            n = len(poly)
            if point_in_polygon(centre[0], centre[1], poly) or \
                    any(_point_seg_distance(centre, poly[i], poly[(i + 1) % n]) < radius - WALL_CLEARANCE for i in range(n)):
                hits.append(oid)
        return hits
    path = stair_centerline(candidate)
    half = candidate.width / 2.0 - WALL_CLEARANCE
    for oid, poly in obstacles:
        n = len(poly)
        if any(point_in_polygon(q[0], q[1], poly) for q in path) or any(
                _seg_seg_distance(path[i], path[i + 1], poly[j], poly[(j + 1) % n]) < half
                for i in range(len(path) - 1) for j in range(n)):
            hits.append(oid)
    return hits


def _room_of(doc, point: Point2, z: float):
    from archforge.geometry.regions import point_in_polygon
    for face in doc.active_room_faces(z=z):
        if point_in_polygon(float(point[0]), float(point[1]), face.polygon):
            return face.polygon
    return None


FIT_STEP = 0.10
FIT_REACH = 1.5


def fit_in_walls(doc, candidate: StairCandidate, walls=None, room=None, obstacles=()):
    """The candidate moved as little as possible so that it crosses no wall (nor a door's free space, a cabinet:
    ``stair_obstacles``), staying in the room it starts in.

    Returns ``(candidate, fits)``: the original when it already fits or no position within
    ``FIT_REACH`` does (then ``fits`` is False).
    """
    from dataclasses import replace
    from archforge.geometry.regions import point_in_polygon
    walls = stair_walls(doc, candidate.lower_z, candidate.upper_floor_z) if walls is None else walls
    if not stair_wall_conflicts(doc, candidate, walls) and not stair_obstacle_conflicts(candidate, obstacles):
        return candidate, True
    fp = stair_footprint(candidate)
    # Only walls near the stair can matter while it moves.
    lo_x, lo_y = min(q[0] for q in fp) - FIT_REACH - 1, min(q[1] for q in fp) - FIT_REACH - 1
    hi_x, hi_y = max(q[0] for q in fp) + FIT_REACH + 1, max(q[1] for q in fp) + FIT_REACH + 1
    near = [w for w in walls if not (max(w.params['x1'], w.params['x2']) < lo_x or min(w.params['x1'], w.params['x2']) > hi_x
                                     or max(w.params['y1'], w.params['y2']) < lo_y or min(w.params['y1'], w.params['y2']) > hi_y)]
    ox, oy = candidate.origin
    steps = int(round(FIT_REACH / FIT_STEP))
    shifts = sorted(((i * FIT_STEP, j * FIT_STEP) for i in range(-steps, steps + 1) for j in range(-steps, steps + 1)),
                    key=lambda d: d[0] * d[0] + d[1] * d[1])
    for dx, dy in shifts[1:]:
        if dx * dx + dy * dy > FIT_REACH * FIT_REACH:
            break
        moved = replace(candidate, origin=(ox + dx, oy + dy))
        if room is not None:
            # Stay in the room the human started in: the stair's own outline inside it.
            if not all(point_in_polygon(x, y, room) for x, y in stair_footprint(moved)):
                continue
        if not stair_wall_conflicts(doc, moved, near) and not stair_obstacle_conflicts(moved, obstacles):
            return moved, True
    return candidate, False


def place_among_walls(doc, candidates, click: Point2):
    """``[(candidate, fits)]``: every candidate fitted into the walls, those that fit first (order kept)."""
    if not candidates:
        return []
    walls = stair_walls(doc, candidates[0].lower_z, candidates[0].upper_floor_z)
    if not walls:
        return [(c, True) for c in candidates]
    room = _room_of(doc, click, candidates[0].lower_z)
    obstacles = stair_obstacles(doc, candidates[0].lower_z, candidates[0].upper_floor_z)
    fitted = [fit_in_walls(doc, c, walls, room, obstacles) for c in candidates]
    return [f for f in fitted if f[1]] + [f for f in fitted if not f[1]]


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


def _corridor_rectangle(a: Point2, b: Point2, half_width: float) -> Tuple[Point2, ...]:
    ax, ay = map(float, a)
    bx, by = map(float, b)
    dx, dy = bx - ax, by - ay
    length = hypot(dx, dy)
    if length <= 1e-12:
        return ()
    nx, ny = -dy / length, dx / length
    half = float(half_width)
    return (
        (ax - nx * half, ay - ny * half),
        (bx - nx * half, by - ny * half),
        (bx + nx * half, by + ny * half),
        (ax + nx * half, ay + ny * half),
    )


def _junction_pad(point: Point2, half_width: float) -> Tuple[Point2, ...]:
    x, y = map(float, point)
    half = float(half_width)
    return (
        (x - half, y - half),
        (x + half, y - half),
        (x + half, y + half),
        (x - half, y + half),
    )


def stair_opening_polygons(
    candidate: StairCandidate,
    headroom: float = 2.0,
    underside: float | None = None,
) -> Tuple[Tuple[Point2, ...], ...]:
    """Convex opening pieces following only the upper stair/headroom path.

    The slab stays wherever there is ``headroom`` between the steps and its ``underside``
    (default: the upper storey level) — the upper storey keeps that floor, and the space
    under the stair stays usable (owner 14/10).

    Straight stairs produce one oriented rectangle. L/U stairs produce one
    corridor per remaining flight plus small junction pads so the union follows
    the actual turn instead of cutting one oversized bounding box. Spiral stairs
    are approximated by short oriented corridor pieces around their polyline.
    """
    path = stair_centerline(candidate)
    total_rise = max(1e-9, float(candidate.upper_z) - float(candidate.lower_z))
    slab_underside = float(candidate.upper_floor_z if underside is None else underside)
    start_elevation = max(
        float(candidate.lower_z),
        slab_underside - max(0.1, float(headroom)),
    )
    fraction = (start_elevation - float(candidate.lower_z)) / total_rise
    upper_path = _polyline_tail_from_fraction(path, fraction)
    if len(upper_path) < 2:
        upper_path = path
    if len(upper_path) < 2:
        return ()

    half = float(candidate.width) / 2.0 + 0.05
    pieces = []
    for i in range(len(upper_path) - 1):
        rect = _corridor_rectangle(upper_path[i], upper_path[i + 1], half)
        if rect:
            pieces.append(rect)

    # Fill joints between differently directed corridor rectangles. A square pad
    # is rotation-invariant and avoids tiny uncut wedges at L/U/spiral bends.
    if len(upper_path) > 2:
        for point in upper_path[1:-1]:
            pieces.append(_junction_pad(point, half))

    return tuple(pieces)


def stair_opening_polygon(
    candidate: StairCandidate,
    headroom: float = 2.0,
) -> Tuple[Point2, ...]:
    """Compatibility envelope for callers that still require one polygon.

    Geometry cutting uses :func:`stair_opening_polygons` so turning stairs are
    no longer reduced to this bounding envelope.
    """
    pieces = stair_opening_polygons(candidate, headroom=headroom)
    if not pieces:
        return ()
    if len(pieces) == 1:
        return pieces[0]
    points = [point for polygon in pieces for point in polygon]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (
        (min(xs), min(ys)),
        (max(xs), min(ys)),
        (max(xs), max(ys)),
        (min(xs), max(ys)),
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
        elif entity.kind in ('floor', 'room') and p.get('role') != 'balcony':
            # A balcony slab hangs below its storey's level (top flush with the floor): not a storey.
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
        # No storey above: a stair may still climb to a flat roof terrace
        # (e.g. an external stair to a roof with a pergola).
        return roof_terrace_landing(doc, lower_z, point)
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


def roof_terrace_landing(doc, lower_z: float, point: Point2 | None = None):
    """Landing on top of the nearest flat roof above ``lower_z``, or None.

    Prefers the roof containing ``point``; otherwise the lowest roof above.
    """
    from archforge.architecture.rooms import room_slab_geometry
    roofs = []
    for entity in doc.entities.values():
        if entity.kind != 'room_roof' or entity.params.get('roof_type', 'flat') != 'flat':
            continue
        geom = room_slab_geometry(doc, entity)
        if geom is None:
            continue
        base = float(geom['z'])
        if base <= float(lower_z) + 1e-6:
            continue
        contains = bool(point is not None and _point_in_polygon(point, geom['points']))
        roofs.append((not contains, base, float(geom['thickness'])))
    if not roofs:
        return None
    _, base, thickness = min(roofs)
    return {
        'level_name': 'Ταράτσα',
        'floor_z': base,
        'slab_thickness': thickness,
        'landing_z': base + thickness,
    }


def next_level_above(doc, z: float):
    levels = [
        (float(item['elevation']), str(item['name']))
        for item in discover_building_levels(doc)
        if float(item['elevation']) > float(z) + 1e-6
    ]
    return levels[0] if levels else None


# ---------------------------------------------------------------------------
# Plan symbol (κάτοψη), from the same layout as the 3D steps (geometry/mesh._stair_mesh).

# Greek drafting practice: the plan is cut ~1,10–1,20 m above the floor; the flight
# is broken there with a diagonal zig-zag line, what lies above is dashed.
PLAN_CUT_HEIGHT = 1.10


def _spiral_radii(candidate: StairCandidate) -> Tuple[float, float]:
    w = candidate.width
    return max(0.12, w * 0.20), max(w, 0.85) + w * 0.45


def stair_treads(candidate: StairCandidate):
    """Plan of the steps in world coordinates.

    Returns ``(treads, landings)``: ``treads`` = ``[(index, (s0, e0, e1, s1))]``
    where ``s0-s1`` is the riser (start) edge and ``e0-e1`` its far (nosing of the
    next step) edge; tread ``index`` tops out at ``lower_z + (index + 1) · riser``.
    ``landings`` = ``[(index of the tread before it, polygon)]``. Spiral treads
    carry arc points: ``(s0, *outer arc, e0, e1, *inner arc, s1)``.
    """
    c = candidate
    n, t, w, L = c.tread_count, c.tread_depth, c.width, c.landing_depth
    turn = float(c.turn_direction)
    hw = w / 2.0
    world = lambda pts: tuple(_local_to_world(c, x, y) for x, y in pts)
    if c.layout == 'spiral':
        inner, outer = _spiral_radii(c)
        sweep = turn * 2.0 * pi
        treads = []
        for i in range(n):
            a0, a1 = sweep * i / n, sweep * (i + 1) / n
            arc = [a0 + (a1 - a0) * q / 4 for q in range(5)]
            # s0 (outer start) … e0 (outer end), e1 (inner end) … s1 (inner start).
            outer_arc = [(outer * cos(a), outer * sin(a)) for a in arc]
            inner_back = [(inner * cos(a), inner * sin(a)) for a in reversed(arc)]
            treads.append((i, world(outer_arc + inner_back)))
        return treads, []
    first = max(1, n // 2)
    second = n - first
    p1 = first * t
    local = []
    landings = []
    flight = lambda i: ((i * t, -turn * hw), ((i + 1) * t, -turn * hw), ((i + 1) * t, turn * hw), (i * t, turn * hw))
    if c.layout == 'straight':
        local = [(i, flight(i)) for i in range(n)]
    elif c.layout == 'l':
        local = [(i, flight(i)) for i in range(first)]
        cx = p1 + L / 2.0
        landings.append((first - 1, ((p1, -L / 2.0), (p1 + L, -L / 2.0), (p1 + L, L / 2.0), (p1, L / 2.0))))
        for j in range(second):
            y0, y1 = turn * (L / 2.0 + j * t), turn * (L / 2.0 + (j + 1) * t)
            local.append((first + j, ((cx + hw, y0), (cx + hw, y1), (cx - hw, y1), (cx - hw, y0))))
    elif c.layout == 'u':
        offset = turn * (w + 0.20)
        local = [(i, flight(i)) for i in range(first)]
        lo, hi = min(0.0, offset) - hw, max(0.0, offset) + hw
        landings.append((first - 1, ((p1, lo), (p1 + L, lo), (p1 + L, hi), (p1, hi))))
        for j in range(second):
            x0, x1 = p1 - j * t, p1 - (j + 1) * t
            local.append((first + j, ((x0, offset + turn * hw), (x1, offset + turn * hw), (x1, offset - turn * hw), (x0, offset - turn * hw))))
    else:
        raise ValueError(f'unsupported stair layout: {c.layout}')
    return [(i, world(q)) for i, q in local], [(k, world(q)) for k, q in landings]


def _mid(a: Point2, b: Point2) -> Point2:
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _edges(quad):
    """(start edge, end edge) of a tread: s0-s1 and e0-e1."""
    if len(quad) == 4:
        s0, e0, e1, s1 = quad
    else:
        half = len(quad) // 2
        s0, e0, e1, s1 = quad[0], quad[half - 1], quad[half], quad[-1]
    return (s0, s1), (e0, e1)


def _walking_line(candidate: StairCandidate, treads):
    """Walking line through the middle of every riser, turning in the middle of the
    landings; with the index in it of each tread's start."""
    pts: List[Point2] = []
    starts = []
    L = candidate.landing_depth
    for k, (_i, quad) in enumerate(treads):
        (s0, s1), (e0, e1) = _edges(quad)
        start, end = _mid(s0, s1), _mid(e0, e1)
        if pts and hypot(pts[-1][0] - start[0], pts[-1][1] - start[1]) > 1e-6:
            # A landing: go on along the flight, turn in its middle, come into the next flight.
            prev = pts[-1]
            (ps0, ps1), _pe = _edges(treads[k - 1][1])
            pstart = _mid(ps0, ps1)
            du = (prev[0] - pstart[0], prev[1] - pstart[1])
            dn = hypot(*du) or 1.0
            dv = (end[0] - start[0], end[1] - start[1])
            dm = hypot(*dv) or 1.0
            a = (prev[0] + du[0] / dn * L / 2.0, prev[1] + du[1] / dn * L / 2.0)
            b = (start[0] - dv[0] / dm * L / 2.0, start[1] - dv[1] / dm * L / 2.0)
            pts.append(a)
            if hypot(a[0] - b[0], a[1] - b[1]) > 1e-6:
                pts.append(b)
        if not pts or hypot(pts[-1][0] - start[0], pts[-1][1] - start[1]) > 1e-6:
            pts.append(start)
        starts.append(len(pts) - 1)
        pts.append(end)
    return pts, starts


def _arrow_head(tip: Point2, back: Point2, size: float = 0.18) -> Tuple[Point2, ...]:
    dx, dy = tip[0] - back[0], tip[1] - back[1]
    d = hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    bx, by = tip[0] - ux * size, tip[1] - uy * size
    return ((bx - uy * size * 0.5, by + ux * size * 0.5), tip, (bx + uy * size * 0.5, by - ux * size * 0.5))


def _break_line(quad) -> Tuple[Point2, ...]:
    """Diagonal zig-zag cut line across a tread (riser corner to the opposite far corner)."""
    (s0, _s1), (_e0, e1) = _edges(quad)
    dx, dy = e1[0] - s0[0], e1[1] - s0[1]
    d = hypot(dx, dy) or 1.0
    nx, ny = -dy / d, dx / d
    z = min(0.12, d * 0.12)
    p = lambda u, o: (s0[0] + dx * u + nx * o, s0[1] + dy * u + ny * o)
    # A little past the stair's sides, with the Z break in the middle.
    return (p(-0.10, 0.0), p(0.44, 0.0), p(0.48, z), p(0.52, -z), p(0.56, 0.0), p(1.10, 0.0))


def _strictly_inside(point: Point2, convex, eps: float = 1e-7) -> bool:
    sign = 0.0
    n = len(convex)
    for i in range(n):
        a, b = convex[i], convex[(i + 1) % n]
        cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
        if abs(cross) <= eps * max(1.0, hypot(b[0] - a[0], b[1] - a[1])):
            return False
        if sign == 0.0:
            sign = 1.0 if cross > 0 else -1.0
        elif cross * sign < 0:
            return False
    return True


def _union_outline(polygons) -> List[Tuple[Point2, Point2]]:
    """Boundary segments of a union of convex polygons (edge pieces not inside another piece)."""
    polys = [tuple((float(x), float(y)) for x, y in q) for q in polygons if len(q) >= 3]
    segments = []
    for k, poly in enumerate(polys):
        for a, b in zip(poly, poly[1:] + poly[:1]):
            cuts = [0.0, 1.0]
            rx, ry = b[0] - a[0], b[1] - a[1]
            for m, other in enumerate(polys):
                if m == k:
                    continue
                for c_, d_ in zip(other, other[1:] + other[:1]):
                    sx, sy = d_[0] - c_[0], d_[1] - c_[1]
                    den = rx * sy - ry * sx
                    if abs(den) < 1e-12:
                        continue
                    u = ((c_[0] - a[0]) * sy - (c_[1] - a[1]) * sx) / den
                    v = ((c_[0] - a[0]) * ry - (c_[1] - a[1]) * rx) / den
                    if 0.0 < u < 1.0 and -1e-9 <= v <= 1.0 + 1e-9:
                        cuts.append(u)
            cuts.sort()
            for u0, u1 in zip(cuts, cuts[1:]):
                if u1 - u0 < 1e-9:
                    continue
                um = (u0 + u1) / 2.0
                mid = (a[0] + rx * um, a[1] + ry * um)
                if any(_strictly_inside(mid, other) for m, other in enumerate(polys) if m != k):
                    continue
                seg = ((a[0] + rx * u0, a[1] + ry * u0), (a[0] + rx * u1, a[1] + ry * u1))
                # Shared edges of touching pieces: keep one copy.
                if not any(hypot(seg[0][0] - q[1][0], seg[0][1] - q[1][1]) + hypot(seg[1][0] - q[0][0], seg[1][1] - q[0][1]) < 1e-6
                           or hypot(seg[0][0] - q[0][0], seg[0][1] - q[0][1]) + hypot(seg[1][0] - q[1][0], seg[1][1] - q[1][1]) < 1e-6
                           for q in segments):
                    segments.append(seg)
    return segments


def _dot(p: Point2, radius: float = 0.05) -> Tuple[Point2, ...]:
    m = 12 if radius < 0.2 else 48
    return tuple((p[0] + radius * cos(2 * pi * q / m), p[1] + radius * sin(2 * pi * q / m)) for q in range(m + 1))


def _beyond(a: Point2, b: Point2, distance: float = 0.22) -> Point2:
    """A point past ``b`` on the line a→b (where «ΑΝ» / «ΚΑΤ» goes)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = hypot(dx, dy) or 1.0
    return (b[0] + dx / d * distance, b[1] + dy / d * distance)


def stair_cut_index(candidate: StairCandidate, cut_height: float = PLAN_CUT_HEIGHT) -> int:
    """Number of treads below the plan cut of the lower storey (at least 1, at most all but one)."""
    n = candidate.tread_count
    if n <= 1:
        return n
    return max(1, min(n - 1, int(floor(float(cut_height) / max(1e-9, candidate.riser_height) + 1e-9))))


def stair_plan_symbol(candidate: StairCandidate, view: str = 'lower', numbers: bool = False,
                      cut_height: float = PLAN_CUT_HEIGHT):
    """2D plan symbol of a stair on the storey it starts from (``'lower'``) or reaches (``'upper'``).

    Lower storey: steps up to the cut solid, above it dashed, a diagonal zig-zag
    break line, walking line from a dot on the first riser, arrow and «ΑΝ».
    Upper storey: outline of the slab opening, the steps seen through it (those
    above the lower storey's cut) solid, walking line downwards, arrow and «ΚΑΤ».
    Returns ``(lines, labels)``: ``[(style, points)]`` with style in ``tread /
    hidden / landing / cut / walk / walk-hidden / arrow / opening`` and
    ``[(text, point, kind)]`` with kind ``direction`` or ``number``.
    """
    c = candidate
    treads, landings = stair_treads(c)
    n = len(treads)
    k = stair_cut_index(c, cut_height)
    upper = view == 'upper'
    lines = []
    labels = []
    centre = lambda quad: (sum(q[0] for q in quad) / len(quad), sum(q[1] for q in quad) / len(quad))
    pieces = stair_opening_polygons(c) if upper and c.layout != 'spiral' else ()
    uncovered = lambda poly: any(_point_in_polygon(centre(poly), piece) for piece in pieces)
    if pieces:
        # Seen from above: the steps over the lower storey's cut that the slab opening uncovers.
        while k < n - 1 and not uncovered(treads[k][1]):
            k += 1
    seen_landing = None
    for i, quad in treads:
        closed = tuple(quad) + (quad[0],)
        if not upper:
            lines.append(('tread' if i < k else 'hidden', closed))
        elif i >= k:
            lines.append(('tread', closed))
    for after, poly in landings:
        closed = tuple(poly) + (poly[0],)
        if upper:
            if after >= k - 1 or (pieces and uncovered(poly)):
                lines.append(('landing', closed))
                if after == k - 1 or (after < k and seen_landing is None):
                    seen_landing = after
        else:
            lines.append(('landing' if after < k else 'hidden', closed))
    if c.layout == 'spiral':
        # The newel (κεντρικός στύλος).
        inner, _outer = _spiral_radii(c)
        lines.append(('tread', _dot(c.origin, inner)))
    walk, starts = _walking_line(c, treads)
    cut_at = starts[k] if k < n else len(walk) - 1
    if upper and seen_landing is not None and seen_landing < k:
        cut_at = min(cut_at, starts[seen_landing] + 1)       # the walk down ends on the landing's edge
    if upper:
        if c.layout == 'spiral':
            # Round well around the spiral (the 3D cut approximates it with short pieces).
            lines.append(('opening', _dot(c.origin, _spiral_radii(c)[1] + 0.05)))
        else:
            for a, b in _union_outline(stair_opening_polygons(c)):
                lines.append(('opening', (a, b)))
        part = walk[cut_at:]
        lines.append(('walk', tuple(part)))
        lines.append(('arrow', _arrow_head(part[0], part[1])))
        lines.append(('walk', _dot(part[-1])))
        labels.append(('ΚΑΤ', _beyond(part[-2], part[-1]), 'direction'))
    else:
        if k < n:
            lines.append(('cut', _break_line(treads[k][1])))
        lines.append(('walk', tuple(walk[:cut_at + 1])))
        if cut_at < len(walk) - 1:
            lines.append(('walk-hidden', tuple(walk[cut_at:])))
        lines.append(('arrow', _arrow_head(walk[-1], walk[-2])))
        lines.append(('walk', _dot(walk[0])))
        labels.append(('ΑΝ', _beyond(walk[1], walk[0]), 'direction'))
    if numbers:
        for i, quad in treads:
            if upper and i < k:
                continue
            # Beside the walking line, on the left half of the tread.
            (s0, _s1), (e0, _e1) = _edges(quad)
            labels.append((str(i + 1), _mid(centre(quad), _mid(s0, e0)), 'number'))
    return lines, labels
