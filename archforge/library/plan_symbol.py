"""2D plan symbol for a library mesh: the outline of its top-down silhouette.

The mesh is projected onto the floor plane and rasterised; the boundary of
the covered cells is traced into closed loops (outer outline and holes, e.g.
the opening of a ring or the gap between chair legs seen from above) and
simplified.  The symbol is derived from the same geometry as the 3D view, so
plan and 3D cannot disagree about the footprint.
"""
import math

GRID = 160          # cells along the longer side of the footprint
SIMPLIFY = 1.6      # Douglas-Peucker tolerance, in cells (removes raster stair-steps)
MIN_LINE = 10       # inner lines shorter than this many cells are noise
STEP = 0.05         # height jump (m) between neighbouring cells drawn as an inner line


def _raster(triangles, lo, cell, nx, ny):
    """Top-down height map: highest surface point over each cell centre."""
    grid = [[None] * nx for _ in range(ny)]   # top height per cell, None = empty
    for a, b, c in triangles:
        (x0, y0), (x1, y1), (x2, y2) = ((p[0], p[1]) for p in (a, b, c))
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-18:
            continue
        i0 = max(0, int((min(x0, x1, x2) - lo[0]) / cell))
        i1 = min(nx - 1, int((max(x0, x1, x2) - lo[0]) / cell))
        j0 = max(0, int((min(y0, y1, y2) - lo[1]) / cell))
        j1 = min(ny - 1, int((max(y0, y1, y2) - lo[1]) / cell))
        for j in range(j0, j1 + 1):
            py = lo[1] + (j + 0.5) * cell
            row = grid[j]
            for i in range(i0, i1 + 1):
                px = lo[0] + (i + 0.5) * cell
                w0 = (x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)
                w1 = (x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)
                w2 = (x0 - px) * (y1 - py) - (x1 - px) * (y0 - py)
                if (w0 >= 0 and w1 >= 0 and w2 >= 0) or (w0 <= 0 and w1 <= 0 and w2 <= 0):
                    z = (w0 * a[2] + w1 * b[2] + w2 * c[2]) / (w0 + w1 + w2)
                    if row[i] is None or z > row[i]:
                        row[i] = z
        # Thin parts (legs, rods) narrower than a cell still mark their cell.
        for x, y, z in (a, b, c):
            i = min(nx - 1, max(0, int((x - lo[0]) / cell)))
            j = min(ny - 1, max(0, int((y - lo[1]) / cell)))
            if grid[j][i] is None or z > grid[j][i]:
                grid[j][i] = z
    return grid


def _boundary_loops(grid, nx, ny):
    """Directed boundary edges of filled cells (filled on the left), chained into loops."""
    def filled(i, j):
        return 0 <= i < nx and 0 <= j < ny and grid[j][i] is not None
    nxt = {}
    for j in range(ny):
        for i in range(nx):
            if grid[j][i] is None:
                continue
            if not filled(i, j - 1):
                nxt.setdefault((i, j), []).append((i + 1, j))
            if not filled(i + 1, j):
                nxt.setdefault((i + 1, j), []).append((i + 1, j + 1))
            if not filled(i, j + 1):
                nxt.setdefault((i + 1, j + 1), []).append((i, j + 1))
            if not filled(i - 1, j):
                nxt.setdefault((i, j + 1), []).append((i, j))
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, p = [start], start
        while True:
            outs = nxt.get(p)
            if not outs:
                break
            q = outs.pop()
            if not outs:
                del nxt[p]
            if q == start:
                break
            loop.append(q)
            p = q
        if len(loop) >= 4:
            loops.append(loop)
    return loops


def _simplify(points, tol):
    if len(points) < 3:
        return points
    (ax, ay), (bx, by) = points[0], points[-1]
    dx, dy = bx - ax, by - ay
    norm = math.hypot(dx, dy)
    best, index = -1.0, 0
    for k in range(1, len(points) - 1):
        px, py = points[k]
        d = abs(dy * (px - ax) - dx * (py - ay)) / norm if norm > 1e-12 else math.hypot(px - ax, py - ay)
        if d > best:
            best, index = d, k
    if best <= tol:
        return [points[0], points[-1]]
    left = _simplify(points[:index + 1], tol)
    return left[:-1] + _simplify(points[index:], tol)


def _area(loop):
    return 0.5 * sum(loop[k][0] * loop[k - 1][1] - loop[k - 1][0] * loop[k][1] for k in range(len(loop)))


def _step_lines(grid, nx, ny, step):
    """Cell edges where the top height jumps by more than ``step``, chained into polylines."""
    segs = []
    for j in range(ny):
        for i in range(nx):
            z = grid[j][i]
            if z is None:
                continue
            if i + 1 < nx and grid[j][i + 1] is not None and abs(grid[j][i + 1] - z) > step:
                segs.append(((i + 1, j), (i + 1, j + 1)))
            if j + 1 < ny and grid[j + 1][i] is not None and abs(grid[j + 1][i] - z) > step:
                segs.append(((i, j + 1), (i + 1, j + 1)))
    adj = {}
    for a, b in segs:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    lines, used = [], set()
    for a, b in segs:
        if (a, b) in used:
            continue
        used.add((a, b)); used.add((b, a))
        line = [a, b]
        for end in (1, 0):
            while True:
                tip = line[-1] if end else line[0]
                nxt = [q for q in adj[tip] if (tip, q) not in used]
                if len(adj[tip]) != 2 or not nxt:
                    break
                q = nxt[0]
                used.add((tip, q)); used.add((q, tip))
                if end:
                    line.append(q)
                else:
                    line.insert(0, q)
        if len(line) >= MIN_LINE:   # ignore ledges and stair-step fragments
            lines.append(line)
    return lines


def plan_symbol(vertices, triangles, grid=GRID, step=STEP):
    """Plan symbol: ``{"outline": [closed loops], "lines": [open polylines]}`` in metres."""
    loops, lines, to_m = _trace(vertices, triangles, grid, step)
    return {"outline": loops, "lines": [[to_m(p) for p in _simplify(l, SIMPLIFY)] for l in lines]}


def plan_outline(vertices, triangles, grid=GRID):
    """Closed outline loops only (see :func:`plan_symbol`)."""
    return _trace(vertices, triangles, grid, None)[0]


def _trace(vertices, triangles, grid, step):
    tris = [tuple(vertices[i] for i in t) for t in triangles]
    xs = [v[0] for v in vertices]
    ys = [v[1] for v in vertices]
    lo = (min(xs), min(ys))
    span = max(max(xs) - lo[0], max(ys) - lo[1], 1e-6)
    cell = span / grid
    nx = max(1, int(math.ceil((max(xs) - lo[0]) / cell)) + 1)
    ny = max(1, int(math.ceil((max(ys) - lo[1]) / cell)) + 1)
    raster = _raster(tris, lo, cell, nx, ny)

    def to_m(p):
        return (lo[0] + p[0] * cell, lo[1] + p[1] * cell)
    loops = []
    for loop in _boundary_loops(raster, nx, ny):
        # Split the closed loop at its farthest point so DP keeps both halves.
        far = max(range(len(loop)), key=lambda k: (loop[k][0] - loop[0][0]) ** 2 + (loop[k][1] - loop[0][1]) ** 2)
        simple = _simplify(loop[:far + 1], SIMPLIFY)[:-1] + _simplify(loop[far:] + [loop[0]], SIMPLIFY)[:-1]
        if len(simple) >= 3 and abs(_area(simple)) >= 2.0:  # drop specks under ~2 cells
            loops.append([to_m(q) for q in simple])
    loops.sort(key=lambda l: -abs(_area(l)))
    lines = _step_lines(raster, nx, ny, step) if step is not None else []
    return loops, lines, to_m
