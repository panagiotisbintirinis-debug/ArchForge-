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
    floor = _floor_of(doc, float(e.params['z']))
    near_wall = _wall_distance(doc, float(e.params['x']), float(e.params['y']), floor) <= WALL_NEAR
    if distribution(doc) == 'ceiling' and (near_wall or _ceiling_fed(e)):
        # Distribution from the ceiling (owner 06/11: «σε άλλες χώρες… διανομή από το ταβάνι»): the runs in / under the
        # slab, each point fed down from above; a point in the middle of a room keeps its floor feed.
        return 'ceiling'
    # Preserve the old automatic wall feed for lights and weak-current points.
    if _ceiling_fed(e) or e.params['point_type'] in LOW_VOLTAGE_TYPES:
        return 'wall'
    return 'wall' if near_wall else 'floor'


DISTRIBUTIONS = {'walls': 'Διανομή στους τοίχους (οριζόντια στα 2,35 m)', 'ceiling': 'Διανομή από το ταβάνι'}


def avoid_frame(doc):
    """True unless the project allows conduits cast in the concrete (electrical_board settings, «Προσωλήνωση»)."""
    from archforge.mep.electrical_board import panel_value
    return not int(panel_value(doc, 'cast_in_concrete', 0))


def layered(doc, grid, mode, floor, z, free=()):
    """The grid that keeps out of the frame for a run of ``mode`` at ``z`` (``(grid, z)``): walls → two layers (brick +
    floor); floor → the screed round the columns; ceiling → a false ceiling under the lowest beam, round the columns."""
    from archforge.mep.electrical import FLOOR_RUN_Z
    if mode == 'wall':
        return LayeredGrid(grid, doc, z, floor + FLOOR_RUN_Z, free), z
    if mode == 'ceiling':
        z = false_ceiling_z(doc, floor)
    return LayeredGrid(grid, doc, z, None, free), z


def distribution(doc):
    """The project's way of distributing the circuits (electrical_board.settings, on the panel)."""
    from archforge.mep.electrical_board import panel_value
    return str(panel_value(doc, 'distribution', 'walls'))


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
        pool = grid.wall | grid.near
        if avoid_frame(grid.doc) if getattr(grid, 'doc', None) is not None else False:
            pool = pool - frame_cells(grid, grid.doc, run_z(grid.doc, grid.floor, 'wall'), 0.0) or pool
        return min(pool, key=lambda c: (c not in grid.wall, math.dist(grid.point(c), xy), c))
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
        floor = _floor_of(doc, float(e.params['z']))
        zc = min(device_z, false_ceiling_z(doc, floor)) if avoid_frame(doc) else device_z
        points = [(bx, by, z), (bx, by, box_z), (bx, by, zc), (ex, by, zc), (ex, ey, zc), (ex, ey, device_z)]
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
            if avoid_frame(doc):
                zc = min(zc, false_ceiling_z(doc, floor))          # in the false ceiling, under the beams
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
    runs.extend(traveller_runs(doc, wiring, points))
    return runs, boxes


TRAVELLER = 'traveller:'


def traveller_runs(doc, wiring, points):
    """Multi-way switching (αλέ-ρετούρ / αντιστροφέας): the two travellers between consecutive switches of a chain,
    at the horizontal wall-run height — ``(a, b, 'traveller:<switch id>')`` (DESIGN_DEFAULT path, not a survey)."""
    from archforge.mep.electrical import WALL_RUN_Z, _floor_of, mount_z
    runs, done = [], set()
    for link in wiring['switch_links']:
        chain = link.get('partners') or []
        for a, b in zip(chain, chain[1:]):
            if (a, b) in done or a not in points or b not in points:
                continue
            done.add((a, b))
            pa, pb = points[a].params, points[b].params
            ax, ay, bx, by = float(pa['x']), float(pa['y']), float(pb['x']), float(pb['y'])
            za = _floor_of(doc, float(pa['z'])) + WALL_RUN_Z
            zb = _floor_of(doc, float(pb['z'])) + WALL_RUN_Z
            path = [(ax, ay, mount_z(doc, pa)), (ax, ay, za), (bx, ay, za), (bx, by, za), (bx, by, zb),
                    (bx, by, mount_z(doc, pb))]
            runs.extend((p, q, TRAVELLER + a) for p, q in zip(path, path[1:]) if math.dist(p, q) > 1e-6)
    return runs


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


# ------------------------------------------------------------------ avoiding the frame (owner 06/11)
# «Η διέλευση … μέσα από φέροντα στοιχεία πρέπει να αποφεύγεται… Στην τοιχοποιία η σωλήνωση περνάει αποκλειστικά μέσα
# από το τούβλο· στο σημείο συνάντησης με το μπετόν η διαδρομή στρίβει… Στο δάπεδο απόσταση 10–20 cm από τη βάση της
# κολόνας… Οριζόντια διανομή στην ψευδοροφή… Χιτώνιο μόνο αν η διέλευση είναι απολύτως απαραίτητη, εγκεκριμένο».
COLUMN_CLEARANCE = 0.15    # m around a column in the floor (the owner's 10–20 cm: the middle), DESIGN_DEFAULT
FALSE_CEILING_GAP = 0.05   # m under the lowest beam for the false-ceiling runs, DESIGN_DEFAULT


def frame_cells(grid, doc, z, pad):
    """Cells of the plan whose centre lies in a column / beam that spans height ``z``, grown by ``pad`` (m)."""
    from archforge.coordination.clash import structure
    from archforge.mep.plumbing import CELL
    # The grid lives for one routing of an unchanged model: the same (z, pad) is asked ~80 times (bots 06/11:
    # 1,5 s of every change in a two-storey house) — computed once per grid.
    memo = grid.__dict__.setdefault('_frame_cells', {})
    key = (round(float(z), 6), round(float(pad), 6))
    if key in memo:
        return set(memo[key])
    boxes = grid.__dict__.get('_frame_boxes')
    if boxes is None:
        boxes = grid.__dict__['_frame_boxes'] = list(structure(doc))
    cells = set()
    for box in boxes:
        if not (box.z0 - 1e-6 <= z <= box.z1 + 1e-6):
            continue
        r = math.hypot(box.hu, box.hv) + pad + CELL
        i0, j0 = grid.cell(box.cx - r, box.cy - r)
        i1, j1 = grid.cell(box.cx + r, box.cy + r)
        for i in range(i0, i1 + 1):
            for j in range(j0, j1 + 1):
                u, v = box.local(*grid.point((i, j)))
                if abs(u) <= box.hu + pad and abs(v) <= box.hv + pad:
                    cells.add((i, j))
    memo[key] = frozenset(cells)
    return cells


def false_ceiling_z(doc, floor):
    """Height of the runs in a false ceiling: under the lowest beam of the storey (else under the slab)."""
    from archforge.coordination.clash import structure
    from archforge.mep.electrical import _ceiling
    top = _ceiling(doc, floor)
    bottoms = [b.z0 for b in structure(doc) if b.kind == "structural_beam" and floor < b.z0 < top + 0.3]
    return min([top] + [z - FALSE_CEILING_GAP for z in bottoms])


class LayeredGrid:
    """The router's grid in two layers that keep out of the frame: 0 = the wall run (brick only, at ``z_run``),
    1 = the floor (anywhere but a column and its clearance, at ``z_floor``). A run meeting a column in a wall turns
    down inside the brick, goes round the column in the floor and comes back up. Cells are (i, j, layer)."""

    def __init__(self, base, doc, z_run, z_floor=None, free=()):
        from archforge.mep.plumbing import CELL, FREE_COST, NEAR_WALL_COST, TURN_COST, WALL_COST
        self.two = z_floor is not None
        self.base, self.z = base, (z_run, z_floor if self.two else z_run)
        keep = {tuple(c[:2]) for c in free}                                     # the panel / riser / points themselves
        if self.two:      # wall run: the member and the band in front of it; floor: the column and its clearance
            self.blocked = (frame_cells(base, doc, z_run, 2 * CELL + CELL / 2) - keep,
                            frame_cells(base, doc, z_floor, COLUMN_CLEARANCE) - keep)
        else:             # one layer (floor screed or false ceiling): the column and its clearance
            self.blocked = (frame_cells(base, doc, z_run, COLUMN_CLEARANCE) - keep, set())
        # The concrete itself (no band, nothing kept): never a vertical drop through it.
        self.core = frame_cells(base, doc, z_run, 0.0) | (frame_cells(base, doc, z_floor, 0.0) if self.two else set())
        self.turn = TURN_COST
        self.vertical = abs(self.z[0] - self.z[1]) / CELL                      # a drop costs its length in cells
        self.costs = (WALL_COST, NEAR_WALL_COST, FREE_COST)
        self.wall, self.near = base.wall, base.near
        self.nx, self.ny = base.nx, base.ny

    def cell(self, x, y, layer=0):
        return (*self.base.cell(x, y), layer)

    def point(self, c):
        return self.base.point(c[:2])

    def xyz(self, c):
        x, y = self.base.point(c[:2])
        return (x, y, self.z[c[2]])

    def cost(self, c):
        ij, layer = c[:2], c[2]
        if ij in self.blocked[layer]:
            return math.inf
        if layer == 0 and self.two:
            return 0.8 if ij in self.wall else (1.5 if ij in self.near else 40.0)   # as base mode «wall»
        wall_cost, near_cost, free_cost = self.costs
        return wall_cost if ij in self.wall else (near_cost if ij in self.near else free_cost)

    def route(self, start, tree):
        import heapq
        if start in tree:
            return [start]
        best = {(start, None): 0.0}
        heap = [(0.0, start, None)]
        parent = {}
        while heap:
            d, c, came = heapq.heappop(heap)
            if c in tree:
                path, key = [c], (c, came)
                while key in parent:
                    key = parent[key]
                    path.append(key[0])
                return path[::-1]
            if d > best.get((c, came), math.inf):
                continue
            steps = [((c[0] + dx, c[1] + dy, c[2]), (dx, dy)) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if self.two and c[:2] in self.wall and c[:2] not in self.core and c[:2] not in self.blocked[0] \
                    and c[:2] not in self.blocked[1]:
                steps.append(((c[0], c[1], 1 - c[2]), (0, 0)))                # down / up inside the brick
            for n, move in steps:
                if not (0 <= n[0] < self.nx and 0 <= n[1] < self.ny):
                    continue
                step = self.vertical if move == (0, 0) else self.cost(n)
                if step == math.inf:
                    continue
                nd = d + step + (self.turn if came not in (None, move) else 0.0)
                if nd < best.get((n, move), math.inf):
                    best[(n, move)] = nd
                    parent[(n, move)] = (c, came)
                    heapq.heappush(heap, (nd, n, move))
        return [start]
