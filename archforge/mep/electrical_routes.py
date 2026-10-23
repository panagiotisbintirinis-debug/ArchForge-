"""Owner-selected electrical passage; shared geometry for routing and quantities.

These paths use the application's existing design heights. They do not prove
structural penetrations, installation clearances or compliance.
"""
from __future__ import annotations
import math


def mode_of(doc, e):
    from archforge.mep.electrical import LOW_VOLTAGE_TYPES, WALL_NEAR, _ceiling_fed, _floor_of, _wall_distance
    choice = str(e.params.get('routing', 'auto'))
    if choice in ('wall', 'floor', 'ceiling'):
        return choice
    # Preserve the old automatic wall feed for lights and weak-current points.
    if _ceiling_fed(e) or e.params['point_type'] in LOW_VOLTAGE_TYPES:
        return 'wall'
    floor = _floor_of(doc, float(e.params['z']))
    return 'wall' if _wall_distance(doc, float(e.params['x']), float(e.params['y']), floor) <= WALL_NEAR else 'floor'


def run_z(doc, floor, mode):
    from archforge.mep.electrical import WALL_RUN_Z, FLOOR_RUN_Z, _ceiling
    if mode == 'ceiling':
        return _ceiling(doc, floor)
    # Existing design defaults; no new installation rule is introduced.
    return floor + (WALL_RUN_Z if mode == 'wall' else FLOOR_RUN_Z)


def target_cell(grid, e, mode):
    from archforge.mep.electrical import _ceiling_fed
    xy = (float(e.params['x']), float(e.params['y']))
    if mode != 'ceiling' and _ceiling_fed(e) and (grid.wall or grid.near):
        return min(grid.wall | grid.near, key=lambda c: (c not in grid.wall, math.dist(grid.point(c), xy), c))
    return grid.cell(*xy)


def device_legs(doc, e, mode, anchor, z):
    """Terminal from the chosen run to the actual device, including ceiling feed."""
    from archforge.mep.electrical import FLOOR_BOX_Z, _floor_of, _ceiling_fed, mount_z
    bx, by = anchor
    ex, ey = float(e.params['x']), float(e.params['y'])
    device_z = mount_z(doc, e.params)
    box_z = _floor_of(doc, float(e.params['z'])) + FLOOR_BOX_Z if mode == 'floor' else z
    if e.params.get('routing', 'auto') == 'auto' and not _ceiling_fed(e):
        # Existing automatic terminals stay on the router grid. Adding two tiny
        # snapping jogs here changes bend counts and can demand an extra pipe.
        points = [(bx, by, z), (bx, by, box_z), (bx, by, device_z)]
    elif _ceiling_fed(e) and mode != 'ceiling':
        points = [(bx, by, z), (bx, by, box_z), (bx, by, device_z), (ex, by, device_z), (ex, ey, device_z)]
    else:
        points = [(bx, by, z), (ex, by, z), (ex, ey, z), (ex, ey, box_z), (ex, ey, device_z)]
        bx, by = ex, ey
    legs = [(a, b) for a, b in zip(points, points[1:]) if math.dist(a, b) > 1e-6]
    return legs, (bx, by, box_z, 'floor' if mode == 'floor' else 'junction')


def switch_runs(doc, wiring, points):
    """One switch-leg geometry used by the conduit map and board take-off."""
    from archforge.mep.electrical import WALL_RUN_Z, FLOOR_BOX_Z, _floor_of, _ceiling, mount_z
    from archforge.mep.plumbing import _Grid, _grow
    runs, boxes = [], []
    for link in wiring['switch_links']:
        sw = points.get(link['switch'])
        if sw is None:
            continue
        floor = _floor_of(doc, float(sw.params['z']))
        sx, sy = float(sw.params['x']), float(sw.params['y'])
        members = [points[i] for i in link['lights'] if i in points]
        if sw.params.get('routing', 'auto') == 'auto':
            # Backwards compatibility: the previous conventional switch feed.
            zr, zc = floor + WALL_RUN_Z, _ceiling(doc, floor)
            legs = [((sx, sy, mount_z(doc, sw.params)), (sx, sy, zr)), ((sx, sy, zr), (sx, sy, zc))]
            boxes.append((sx, sy, zr, 'junction', ''))
            for e in members:
                lx, ly = float(e.params['x']), float(e.params['y'])
                legs += [((sx, sy, zc), (lx, sy, zc)), ((lx, sy, zc), (lx, ly, zc))]
        else:
            mode = mode_of(doc, sw); z = run_z(doc, floor, mode)
            grid = _Grid(doc, floor, [(sx, sy)] + [(float(e.params['x']), float(e.params['y'])) for e in members])
            grid.mode = 'wall' if mode == 'wall' else 'floor'
            source = grid.cell(sx, sy); px, py = grid.point(source)
            targets = {e.id: target_cell(grid, e, mode) for e in members}
            paths, _, parent = _grow(grid, source, targets)
            legs = [((sx, sy, mount_z(doc, sw.params)), (sx, sy, z)),
                    ((sx, sy, z), (px, sy, z)), ((px, sy, z), (px, py, z))]
            bz = floor + FLOOR_BOX_Z if mode == 'floor' else z
            boxes.append((sx, sy, bz, 'floor' if mode == 'floor' else 'junction', ''))
            seen = set()
            for path in paths.values():
                c = path[0]
                while parent.get(c) is not None:
                    p = parent[c]; edge = frozenset((c, p))
                    if edge not in seen:
                        a, b = grid.point(c), grid.point(p)
                        legs.append(((*a, z), (*b, z))); seen.add(edge)
                    c = p
            for e in members:
                terminal, box = device_legs(doc, e, mode, grid.point(targets[e.id]), z)
                legs.extend(terminal); boxes.append((*box, ''))
        runs.extend((a, b, sw.id) for a, b in legs if math.dist(a, b) > 1e-6)
    return runs, boxes


def bus_legs(doc, start, e, mode, rise):
    """KNX segment to an explicitly routed destination, using the shared grid."""
    from archforge.mep.electrical import _floor_of, mount_z
    from archforge.mep.plumbing import _Grid
    ex, ey = float(e.params['x']), float(e.params['y'])
    floor = _floor_of(doc, float(e.params['z'])); z = run_z(doc, floor, mode) + rise
    grid = _Grid(doc, floor, [start[:2], (ex, ey)])
    grid.mode = 'wall' if mode == 'wall' else 'floor'
    source, target = grid.cell(*start[:2]), grid.cell(ex, ey)
    path = list(reversed(grid.route(target, {source})))
    xy = [grid.point(c) for c in path]
    pts = [start, (*start[:2], z), (xy[0][0], start[1], z)] + [(*p, z) for p in xy]
    pts += [(ex, xy[-1][1], z), (ex, ey, z), (ex, ey, mount_z(doc, e.params))]
    return [(a, b) for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-6]
