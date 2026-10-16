"""The plot from the engineer's survey (τοπογραφικό), or drawn by hand.

Inputs:

* **Points** (CSV / TXT from the total station): one point per line, numbers
  separated by spaces, tabs, commas or semicolons — ``X Y Z`` or
  ``id X Y Z`` (a leading label is skipped); Greek decimal commas are read.
* **DXF** (the survey drawing): POINT entities, LWPOLYLINE / POLYLINE /
  LINE vertices with their elevation (contour lines, code 38 or 3D
  vertices), TEXT / MTEXT that are pure numbers (spot heights written next
  to a cross) at their insertion point; the **plot boundary** is the closed
  polyline on a layer named like ΟΡΙΟ / ORIO / OIKOPEDO / BOUNDARY / PLOT,
  else the largest closed polyline.

Placement: survey coordinates (e.g. ΕΓΣΑ87, hundreds of kilometres) are
moved so the plot sits around the building already drawn (or the origin);
the ground floor ±0.00 is set 15 cm above the ground under the building.
The offsets are kept (``geo_origin``, ``altitude_ref``) so absolute values
can always be read back.  The ground surface passes exactly through every
survey point (decimated to ≤ 400) over a best-fit grade plane.
"""
from __future__ import annotations

import math
import re

MAX_POINTS = 400
BOUNDARY_LAYERS = ("ΟΡΙΟ", "ORIO", "OIKOPEDO", "ΟΙΚΟΠΕΔΟ", "BOUNDARY", "PLOT", "ΙΔΙΟΚΤΗΣΙΑ")
FLOOR_ABOVE_GROUND = 0.15


# ---------------------------------------------------------------- readers
def _number(token):
    token = token.strip()
    if re.fullmatch(r"-?\d+,\d+", token):
        token = token.replace(",", ".")
    return float(token)


def parse_points(text):
    """[(x, y, z)] from a points file (X Y Z or label X Y Z per line)."""
    out = []
    for line in str(text).splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "//")):
            continue
        if ";" in line or "\t" in line:
            parts = re.split(r"[;\t]+", line)          # «;» or tab: commas are decimals
        elif len(line.split()) >= 3:
            parts = line.split()                       # spaces: commas are decimals
        else:
            parts = line.split(",")                    # plain CSV
        parts = [p for p in parts if p.strip()]
        nums = []
        for p in parts:
            try:
                nums.append(_number(p))
            except ValueError:
                continue
        if len(nums) >= 4:
            nums = nums[-3:] if abs(nums[0]) < 1e5 and float(nums[0]).is_integer() else nums[:3]
        if len(nums) == 3:
            out.append(tuple(nums))
    return out


def _dxf_pairs(text):
    lines = str(text).splitlines()
    for i in range(0, len(lines) - 1, 2):
        try:
            yield int(lines[i].strip()), lines[i + 1].strip()
        except ValueError:
            continue


def parse_dxf(text):
    """``{"points": [(x, y, z)], "polylines": [(layer, closed, [(x, y, z)])]}`` from an ASCII DXF."""
    points, polylines = [], []
    section, entity, data = None, None, {}
    verts, poly_layer, poly_closed, poly_elev, in_polyline = [], "", False, 0.0, False

    def flush():
        nonlocal verts, in_polyline
        kind = entity
        if kind == "POINT" and 10 in data:
            points.append((data[10], data.get(20, 0.0), data.get(30, 0.0)))
        elif kind == "LINE" and 10 in data:
            z1, z2 = data.get(30, 0.0), data.get(31, 0.0)
            if abs(z1) > 1e-9 or abs(z2) > 1e-9:
                points.extend([(data[10], data[20], z1), (data.get(11, data[10]), data.get(21, data[20]), z2)])
        elif kind in ("TEXT", "MTEXT") and 10 in data:
            txt = re.sub(r"\\[A-Za-z][^;]*;|[{}]", "", str(data.get(1, ""))).strip().replace(",", ".")
            if re.fullmatch(r"[+-]?\d+(\.\d+)?", txt):
                points.append((data[10], data[20], float(txt)))
        elif kind == "LWPOLYLINE" and data.get("_xy"):
            z = data.get(38, 0.0)
            polylines.append((data.get(8, ""), bool(int(data.get(70, 0)) & 1), [(x, y, z) for x, y in data["_xy"]]))
        elif kind == "VERTEX" and in_polyline and 10 in data:
            verts.append((data[10], data.get(20, 0.0), data.get(30, poly_elev)))

    for code, value in _dxf_pairs(text):
        if code == 0:
            if entity is not None:
                flush()
            if value == "SECTION":
                section = "pending"; entity = None; data = {}
                continue
            if value == "ENDSEC":
                section = None; entity = None; data = {}
                continue
            if value == "POLYLINE":
                in_polyline, verts = True, []
            if value == "SEQEND" and in_polyline:
                polylines.append((poly_layer, poly_closed, list(verts)))
                in_polyline, verts = False, []
            entity, data = value, {}
            continue
        if section == "pending" and code == 2:
            section = value
            continue
        if section != "ENTITIES" or entity is None:
            continue
        if code == 8:
            data[8] = value
        elif code in (1,):
            data[1] = value
        elif code in (10, 20, 30, 11, 21, 31, 38, 70):
            try:
                v = float(value)
            except ValueError:
                continue
            if entity == "LWPOLYLINE" and code in (10, 20):
                xy = data.setdefault("_xy", [])
                if code == 10:
                    xy.append([v, 0.0])
                elif xy:
                    xy[-1][1] = v
            else:
                data[code] = v
            if entity == "POLYLINE":
                poly_layer = data.get(8, "")
                poly_closed = bool(int(data.get(70, 0)) & 1)
                poly_elev = data.get(30, 0.0)
    if entity is not None:
        flush()
    # Contours: their vertices are survey points too (only those with an elevation).
    for _layer, _closed, pts in polylines:
        if any(abs(p[2]) > 1e-9 for p in pts):
            points.extend(pts)
    return {"points": points, "polylines": polylines}


def plot_boundary(polylines):
    """The plot outline: a closed polyline on a boundary layer, else the largest closed one."""
    closed = [(layer, [(x, y) for x, y, _z in pts]) for layer, c, pts in polylines if (c or (len(pts) > 3 and pts[0][:2] == pts[-1][:2])) and len(pts) >= 3]
    named = [poly for layer, poly in closed if any(k in str(layer).upper() for k in BOUNDARY_LAYERS)]
    pool = named or [poly for _l, poly in closed]
    return max(pool, key=lambda poly: abs(_area(poly)), default=None)


def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) / 2


# ---------------------------------------------------------------- ground
def _thin(points, limit=MAX_POINTS):
    """Grid-thin to at most ``limit`` points, keeping highs and lows of each cell."""
    if len(points) <= limit:
        return list(points)
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    n = int(math.sqrt(limit / 2)) or 1
    cell = span / n
    cells = {}
    for p in points:
        cells.setdefault((int((p[0] - min(xs)) / cell), int((p[1] - min(ys)) / cell)), []).append(p)
    out = []
    for group in cells.values():
        out.append(min(group, key=lambda p: p[2]))
        if len(group) > 1:
            out.append(max(group, key=lambda p: p[2]))
    return out[:limit]


def _fit_plane(points):
    """z = a + b x + c y (least squares)."""
    n = len(points)
    if n < 3:
        return (points[0][2] if points else 0.0), 0.0, 0.0
    sx = sum(p[0] for p in points); sy = sum(p[1] for p in points); sz = sum(p[2] for p in points)
    sxx = sum(p[0] * p[0] for p in points); syy = sum(p[1] * p[1] for p in points); sxy = sum(p[0] * p[1] for p in points)
    sxz = sum(p[0] * p[2] for p in points); syz = sum(p[1] * p[2] for p in points)
    m = [[n, sx, sy, sz], [sx, sxx, sxy, sxz], [sy, sxy, syy, syz]]
    for i in range(3):                                   # Gauss-Jordan
        piv = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[piv] = m[piv], m[i]
        if abs(m[i][i]) < 1e-12:
            return sz / n, 0.0, 0.0
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                m[r] = [a - f * b for a, b in zip(m[r], m[i])]
    return m[0][3] / m[0][0], m[1][3] / m[1][1], m[2][3] / m[2][2]


def _building_centre(doc):
    xs, ys = [], []
    for e in doc.entities.values():
        if e.kind == "wall":
            p = e.params
            xs += [float(p["x1"]), float(p["x2"])]; ys += [float(p["y1"]), float(p["y2"])]
    return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2) if xs else None


def terrain_from_survey(doc, points, boundary=None, margin=2.0):
    """Terrain params for the survey, placed at the building (local metres, ±0.00 = ground floor)."""
    from archforge.site.terrain import DEFAULT_THICKNESS, terrain_height
    pts = [tuple(map(float, p)) for p in points]
    if len(pts) < 3 and not boundary:
        raise ValueError("Το τοπογραφικό χρειάζεται τουλάχιστον 3 υψομετρικά σημεία ή όριο οικοπέδου")
    ref_xy = boundary or [(p[0], p[1]) for p in pts]
    gx = (min(q[0] for q in ref_xy) + max(q[0] for q in ref_xy)) / 2
    gy = (min(q[1] for q in ref_xy) + max(q[1] for q in ref_xy)) / 2
    centre = _building_centre(doc) or (0.0, 0.0)
    dx, dy = centre[0] - gx, centre[1] - gy
    local = _thin([(x + dx, y + dy, z) for x, y, z in pts])
    bnd = [(x + dx, y + dy) for x, y in boundary] if boundary else None
    xy = (bnd or []) + [(p[0], p[1]) for p in local]
    x0, x1 = min(q[0] for q in xy) - margin, max(q[0] for q in xy) + margin
    y0, y1 = min(q[1] for q in xy) - margin, max(q[1] for q in xy) + margin
    a, b, c = _fit_plane(local) if local else (0.0, 0.0, 0.0)
    params = {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "elevation": a + b * x0 + c * y0,
              "slope_x": max(-100.0, min(100.0, b * 100)), "slope_y": max(-100.0, min(100.0, c * 100)),
              "thickness": DEFAULT_THICKNESS, "points": [list(p) for p in local]}
    # Spacing of the survey → how far each point shapes the ground around it.
    if len(local) >= 2:
        sample = local[:200]
        nn = sorted(min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in sample if q is not p) for p in sample)
        params["blend_radius"] = max(3.0, 2.5 * nn[len(nn) // 2])
    # ±0.00: the ground floor sits 15 cm over the ground under the building.
    ground = terrain_height(params, *centre) if local else 0.0
    shift = ground + FLOOR_ABOVE_GROUND
    params["elevation"] -= shift
    params["points"] = [[x, y, z - shift] for x, y, z in params["points"]]
    params["altitude_ref"] = shift
    params["geo_origin"] = [-dx, -dy]
    if bnd:
        params["boundary"] = [[x, y] for x, y in bnd]
    return params


def contours(params, step=None, cell=None):
    """Contour lines of the ground: ``[(z, [(x1, y1), (x2, y2)])]`` segments (marching squares)."""
    from archforge.site.terrain import terrain_height
    x0, y0, x1, y1 = (float(params[k]) for k in ("x0", "y0", "x1", "y1"))
    cell = cell or max(0.5, max(x1 - x0, y1 - y0) / 60)
    nx, ny = max(1, int((x1 - x0) / cell)), max(1, int((y1 - y0) / cell))
    grid = [[terrain_height(params, x0 + (x1 - x0) * i / nx, y0 + (y1 - y0) * j / ny) for j in range(ny + 1)] for i in range(nx + 1)]
    lo = min(min(r) for r in grid); hi = max(max(r) for r in grid)
    if step is None:
        rng = hi - lo
        step = 0.25 if rng <= 2 else (0.5 if rng <= 5 else (1.0 if rng <= 15 else 2.0))
    out = []
    level = math.ceil(lo / step) * step
    while level < hi - 1e-9:
        for i in range(nx):
            for j in range(ny):
                xa, xb = x0 + (x1 - x0) * i / nx, x0 + (x1 - x0) * (i + 1) / nx
                ya, yb = y0 + (y1 - y0) * j / ny, y0 + (y1 - y0) * (j + 1) / ny
                corners = [((xa, ya), grid[i][j]), ((xb, ya), grid[i + 1][j]), ((xb, yb), grid[i + 1][j + 1]), ((xa, yb), grid[i][j + 1])]
                hits = []
                for k in range(4):
                    (p, za), (q, zb) = corners[k], corners[(k + 1) % 4]
                    if (za < level) != (zb < level):
                        t = (level - za) / (zb - za)
                        hits.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
                if len(hits) >= 2:
                    out.append((round(level, 3), hits[:2]))
                    if len(hits) == 4:
                        out.append((round(level, 3), hits[2:]))
        level += step
    return out


def with_boundary(params, boundary, margin=2.0):
    """``params`` with the plot ``boundary`` (drawn by hand) and an extent that holds it."""
    out = dict(params)
    out["boundary"] = [[float(x), float(y)] for x, y in boundary]
    xs = [p[0] for p in out["boundary"]]; ys = [p[1] for p in out["boundary"]]
    out["x0"] = min(float(out["x0"]), min(xs) - margin); out["x1"] = max(float(out["x1"]), max(xs) + margin)
    out["y0"] = min(float(out["y0"]), min(ys) - margin); out["y1"] = max(float(out["y1"]), max(ys) + margin)
    return out


def read_survey_file(path):
    """``(points, boundary)`` from a .dxf or a points file (.csv / .txt / .xyz)."""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1253", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if str(path).lower().endswith(".dxf"):
        if "SECTION" not in text[:4000]:
            raise ValueError("Το DXF πρέπει να είναι ASCII (αποθήκευση ως DXF κειμένου, όχι binary)")
        data = parse_dxf(text)
        return data["points"], plot_boundary(data["polylines"])
    return parse_points(text), None
