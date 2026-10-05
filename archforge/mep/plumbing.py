"""Water supply layout: plumbing points in the Document, pipes derived from them.

The user places points (cold-water supply, solar or electric water heater,
fixtures).  Cold and hot pipe networks are DERIVED on demand, like wall
geometry: moving a point re-routes instantly and nothing has to be redrawn.

Routing rules (stated so an engineer can check them):

* Pipes run in the floor screed of the fixture's storey (z = floor + 5 cm)
  on a 20 cm grid, preferring runs along walls, avoiding crossings through
  walls (penalised, not forbidden: a wall bottom can be drilled) and turns.
* Each network is a tree grown from its source: fixtures are connected one
  by one, nearest first, to the closest point of the existing tree.
* A heater above the storey (solar on the roof) drops a vertical riser at
  its plan position; it also needs a cold feed, so it joins the cold tree.
* At each fixture the pipe rises vertically to the fixture's usual
  connection height.
* Diameters follow common PEX practice: Ø20 on runs that feed two or more
  outlets, Ø16 on single-outlet branches.  Not a hydraulic calculation.

Status: pre-design layout for review by a mechanical engineer.
"""
from __future__ import annotations

import heapq
import math

PROVENANCE = ("Προμελέτη διάταξης: κανόνες χάραξης & τυπικές διατομές PEX (Ø20 κοινά τμήματα, "
              "Ø16 διακλαδώσεις) — όχι υδραυλικός υπολογισμός, προς έλεγχο από μηχανολόγο")

# type: label, needs cold, needs hot, connection height (m), plan letter
POINT_TYPES = {
    "water_supply": ("Παροχή κρύου νερού", False, False, 0.30, "Π"),
    "solar_heater": ("Ηλιακός θερμοσίφωνας", True, False, 0.0, "Η"),
    "water_heater": ("Ηλεκτρικός θερμοσίφωνας", True, False, 1.60, "Θ"),
    "basin": ("Νιπτήρας", True, True, 0.55, "Ν"),
    "wc": ("Λεκάνη WC", True, False, 0.15, "W"),
    "shower": ("Ντουζιέρα", True, True, 1.05, "Ντ"),
    "bathtub": ("Μπανιέρα", True, True, 0.70, "Μ"),
    "kitchen_sink": ("Νεροχύτης κουζίνας", True, True, 0.55, "Κ"),
    "dishwasher": ("Πλυντήριο πιάτων", True, False, 0.45, "ΠΠ"),
    "washing_machine": ("Πλυντήριο ρούχων", True, False, 0.80, "ΠΡ"),
}
SOURCES = ("water_supply", "solar_heater", "water_heater")
CELL = 0.20
SCREED = 0.05
HOT_OFFSET = 0.05   # plan offset of the hot pipe so both remain visible
WALL_COST, NEAR_WALL_COST, FREE_COST, TURN_COST = 6.0, 0.8, 1.0, 0.4


def _levels(doc):
    return sorted({float(v) for v in doc.levels.values()} | {0.0})


def _floor_of(doc, z):
    below = [lz for lz in _levels(doc) if lz <= z + 1e-4]
    return below[-1] if below else _levels(doc)[0]


def plumbing_points(doc):
    return [e for e in doc.entities.values() if e.kind == "plumbing_point"]


class _Grid:
    def __init__(self, doc, floor_z, pts):
        walls = [e for e in doc.entities.values()
                 if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - floor_z) < 0.05]
        xs = [p[0] for p in pts] + [float(w.params[k]) for w in walls for k in ("x1", "x2")]
        ys = [p[1] for p in pts] + [float(w.params[k]) for w in walls for k in ("y1", "y2")]
        self.x0, self.y0 = min(xs) - 1.0, min(ys) - 1.0
        self.nx = int(math.ceil((max(xs) + 1.0 - self.x0) / CELL)) + 1
        self.ny = int(math.ceil((max(ys) + 1.0 - self.y0) / CELL)) + 1
        self.wall = set()
        for w in walls:
            p = w.params
            x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
            length = math.hypot(x2 - x1, y2 - y1)
            if length < 1e-9:
                continue
            steps = int(length / (CELL / 2)) + 1
            for s in range(steps + 1):
                cx, cy = x1 + (x2 - x1) * s / steps, y1 + (y2 - y1) * s / steps
                for dt in (-t / 2, 0.0, t / 2):
                    nx, ny = -(y2 - y1) / length * dt, (x2 - x1) / length * dt
                    self.wall.add(self.cell(cx + nx, cy + ny))
        self.near = {(i + di, j + dj) for i, j in self.wall for di in (-2, -1, 0, 1, 2) for dj in (-2, -1, 0, 1, 2)} - self.wall

    def cell(self, x, y):
        return (int(round((x - self.x0) / CELL)), int(round((y - self.y0) / CELL)))

    def point(self, c):
        return (self.x0 + c[0] * CELL, self.y0 + c[1] * CELL)

    def cost(self, c):
        if c in self.wall:
            return WALL_COST
        return NEAR_WALL_COST if c in self.near else FREE_COST

    def route(self, start, tree):
        """Cheapest 4-connected path from ``start`` to any cell of ``tree``."""
        if start in tree:
            return [start]
        best = {(start, None): 0.0}
        heap = [(0.0, start, None)]
        parent = {}
        while heap:
            d, c, came = heapq.heappop(heap)
            if c in tree:
                path = [c]
                key = (c, came)
                while key in parent:
                    key = parent[key]
                    path.append(key[0])
                return path[::-1]
            if d > best.get((c, came), math.inf):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (c[0] + dx, c[1] + dy)
                if not (0 <= n[0] < self.nx and 0 <= n[1] < self.ny):
                    continue
                nd = d + self.cost(n) + (TURN_COST if came not in (None, (dx, dy)) else 0.0)
                if nd < best.get((n, (dx, dy)), math.inf):
                    best[(n, (dx, dy))] = nd
                    parent[(n, (dx, dy))] = (c, came)
                    heapq.heappush(heap, (nd, n, (dx, dy)))
        return [start]


def _simplify(points):
    out = [points[0]]
    for k in range(1, len(points) - 1):
        a, b, c = out[-1], points[k], points[k + 1]
        if abs((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])) > 1e-9:
            out.append(b)
    if len(points) > 1:
        out.append(points[-1])
    return out


def _grow(grid, source_cell, targets):
    """Grow a tree from ``source_cell``; returns {target_id: path cells} and edge loads."""
    tree = {source_cell}
    paths, loads = {}, {}
    remaining = dict(targets)
    while remaining:
        tid, cell = min(remaining.items(),
                        key=lambda kv: min(abs(kv[1][0] - t[0]) + abs(kv[1][1] - t[1]) for t in tree))
        path = grid.route(cell, tree)          # fixture -> tree
        paths[tid] = path
        tree.update(path)
        del remaining[tid]
    # Edge loads: walk each fixture back to the source along the union tree.
    adj = {}
    for path in paths.values():
        for a, b in zip(path, path[1:]):
            adj.setdefault(a, set()).add(b)
            adj.setdefault(b, set()).add(a)
    parent = {source_cell: None}
    queue = [source_cell]
    while queue:
        c = queue.pop()
        for n in adj.get(c, ()):
            if n not in parent:
                parent[n] = c
                queue.append(n)
    for tid, path in paths.items():
        c = path[0]
        while parent.get(c) is not None:
            edge = frozenset((c, parent[c]))
            loads[edge] = loads.get(edge, 0) + 1
            c = parent[c]
    return paths, loads, parent


def _segments(grid, paths, loads, parent, z, offset=0.0):
    """Tree edges as straight runs ``(a, b, diameter_mm)``: one run per straight
    stretch of equal diameter, each edge emitted once."""
    seen = set()
    runs = []
    for path in paths.values():
        chain = []                 # consecutive (cell, parent, dia) in walking order
        c = path[0]
        while parent.get(c) is not None:
            p = parent[c]
            edge = frozenset((c, p))
            if edge in seen:
                break
            seen.add(edge)
            chain.append((c, p, 20 if loads.get(edge, 1) >= 2 else 16))
            c = p
        k = 0
        while k < len(chain):
            a, b, dia = chain[k]
            direction = (b[0] - a[0], b[1] - a[1])
            j = k
            while j + 1 < len(chain) and chain[j + 1][2] == dia and \
                    (chain[j + 1][1][0] - chain[j + 1][0][0], chain[j + 1][1][1] - chain[j + 1][0][1]) == direction:
                j += 1
            runs.append((a, chain[j][1], dia))
            k = j + 1
    out = []
    for a, b, dia in runs:
        pa, pb = grid.point(a), grid.point(b)
        ox = oy = 0.0
        if offset:
            dx, dy = pb[0] - pa[0], pb[1] - pa[1]
            n = math.hypot(dx, dy) or 1.0
            ox, oy = -dy / n * offset, dx / n * offset
        out.append(((pa[0] + ox, pa[1] + oy, z), (pb[0] + ox, pb[1] + oy, z), dia))
    return out


def route_plumbing(doc):
    """Derived networks: ``{"cold": [...], "hot": [...], "report": {...}}``.

    Each pipe is ``(start_xyz, end_xyz, diameter_mm)``.
    """
    points = plumbing_points(doc)
    result = {"cold": [], "hot": [], "report": {"cold_m": 0.0, "hot_m": 0.0, "unserved": [], "provenance": PROVENANCE}}
    if not points:
        return result
    supplies = [e for e in points if e.params["point_type"] == "water_supply"]
    heaters = [e for e in points if e.params["point_type"] in ("solar_heater", "water_heater")]
    fixtures = [e for e in points if e.params["point_type"] not in SOURCES]
    by_floor = {}
    for e in fixtures + heaters:
        floor = _floor_of(doc, float(e.params["z"]))
        by_floor.setdefault(floor, []).append(e)
    for floor, members in by_floor.items():
        z = floor + SCREED
        pts = [(float(e.params["x"]), float(e.params["y"])) for e in members + supplies + heaters]
        grid = _Grid(doc, floor, pts)
        for system, source_list in (("cold", supplies), ("hot", heaters)):
            needs = [e for e in members if POINT_TYPES[e.params["point_type"]][1 if system == "cold" else 2]]
            if not needs:
                continue
            if not source_list:
                result["report"]["unserved"] += [f"{e.name or POINT_TYPES[e.params['point_type']][0]}: χωρίς {'παροχή' if system == 'cold' else 'θερμοσίφωνα'}"
                                                for e in needs]
                continue
            src = source_list[0]
            sx, sy, sz = (float(src.params[k]) for k in ("x", "y", "z"))
            source_cell = grid.cell(sx, sy)
            targets = {e.id: grid.cell(float(e.params["x"]), float(e.params["y"])) for e in needs if e.id != src.id}
            paths, loads, parent = _grow(grid, source_cell, targets)
            offset = HOT_OFFSET if system == "hot" else 0.0
            pipes = _segments(grid, paths, loads, parent, z, offset)
            # Riser from the source to the screed (e.g. solar heater on the roof)
            sxy = grid.point(source_cell)
            src_conn = sz + POINT_TYPES[src.params["point_type"]][3]
            if abs(src_conn - z) > 1e-6:
                pipes.append(((sxy[0] + offset, sxy[1], src_conn), (sxy[0] + offset, sxy[1], z), 20))
            # Drop-ups to each fixture's connection height
            for e in needs:
                if e.id == src.id:
                    continue
                c = grid.point(grid.cell(float(e.params["x"]), float(e.params["y"])))
                top = float(e.params["z"]) + POINT_TYPES[e.params["point_type"]][3]
                if top > z + 1e-6:
                    pipes.append(((c[0] + offset, c[1], z), (c[0] + offset, c[1], top), 16))
            result[system] += pipes
    for system in ("cold", "hot"):
        result["report"][f"{system}_m"] = round(sum(math.dist(a, b) for a, b, _d in result[system]), 2)
    return result


def pipe_mesh(a, b, diameter_mm, sides=8):
    """Closed prism along a->b (render only)."""
    r = diameter_mm / 2000.0
    ax, ay, az = a
    bx, by, bz = b
    d = (bx - ax, by - ay, bz - az)
    length = math.sqrt(sum(c * c for c in d))
    if length < 1e-9:
        return [], []
    u = tuple(c / length for c in d)
    helper = (0.0, 0.0, 1.0) if abs(u[2]) < 0.9 else (1.0, 0.0, 0.0)
    v = (u[1] * helper[2] - u[2] * helper[1], u[2] * helper[0] - u[0] * helper[2], u[0] * helper[1] - u[1] * helper[0])
    vn = math.sqrt(sum(c * c for c in v))
    v = tuple(c / vn for c in v)
    w = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    verts = []
    for base in (a, b):
        for k in range(sides):
            t = 2 * math.pi * k / sides
            verts.append(tuple(base[i] + r * (math.cos(t) * v[i] + math.sin(t) * w[i]) for i in range(3)))
    verts += [a, b]
    tris = []
    for k in range(sides):
        n = (k + 1) % sides
        tris += [(k, n, sides + n), (k, sides + n, sides + k), (2 * sides, n, k), (2 * sides + 1, sides + k, sides + n)]
    return verts, tris


_CACHE = {"key": None, "value": None}


def _signature(doc):
    items = []
    for e in doc.entities.values():
        if e.kind == "plumbing_point":
            items.append(("p", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
        elif e.kind == "wall":
            items.append(("w", e.id, tuple(round(float(e.params[k]), 6) for k in ("x1", "y1", "x2", "y2", "z", "thickness"))))
    return (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())))


def route_plumbing_cached(doc):
    """route_plumbing() reused while walls and points are unchanged (live redraws)."""
    key = _signature(doc)
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_plumbing(doc)
    return _CACHE["value"]


def point_marker_mesh(params):
    """Small vertical marker at the point's connection height (selectable in 3D)."""
    x, y, z = (float(params[k]) for k in ("x", "y", "z"))
    top = z + max(POINT_TYPES[params["point_type"]][3], 0.12)
    verts, tris = pipe_mesh((x, y, z), (x, y, top), 80, sides=10)
    return verts, tris
