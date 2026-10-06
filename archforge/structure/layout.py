"""Proposed load-bearing frame from the walls: columns and beams where they are needed.

Drawn after the walls and rooms, the frame follows them (rules stated so a
structural engineer can check them):

* A structural grid, as in usual RC dwelling studies: axes on the exterior
  walls, and where a bay would exceed 6 m an axis on the strongest wall
  inside it (longest, nearest the middle) — or a free axis — so slab and
  beam spans and the load each column takes stay balanced; axes closer
  than 2 m are not doubled.  Columns at the axis crossings inside the
  building where they meet a wall (never free in a room: there the axis'
  beam spans façade to façade), never in a door or window
  (slid to its side); columns closer than 1.2 m become one; wall pieces
  under 40 cm and plasterboard partitions are not structure.
* Beams on the axes from column to column, their top on the slab level
  (the storey above, or the top of the walls on the last storey).
* Typical starting sections — RC: columns 40/40, beams 25/50; steel: HEB200
  columns, IPE300 beams.  The structural analysis then checks them and the
  assistant proposes changes where needed.
* Every storey gets its own columns at the same plan positions (continuous
  columns).  Columns already drawn within 30 cm are kept, not duplicated.

Status: pre-design layout for review by a structural engineer.
"""
from __future__ import annotations

import math

MAX_SPAN = 6.0
MERGE = 1.2           # columns closer than this become one (the stronger reason wins)
MIN_WALL = 0.40       # shorter wall pieces are drawing leftovers, not structure
LIGHT_TYPES = ("drywall_100", "drywall_double_125")   # partitions on the slab: no frame under them
SNAP = 0.05
EXISTING = 0.30
OPENING_CLEAR = 0.15


def _key(x, y):
    return (round(x / SNAP) * SNAP, round(y / SNAP) * SNAP)


def _walls(doc, z):
    """Walls of the storey that the frame follows: not tiny leftovers, not light (plasterboard) partitions."""
    out = []
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - z) >= 0.05:
            continue
        p = e.params
        if math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"])) < MIN_WALL:
            continue
        if str(p.get("wall_type", "")) in LIGHT_TYPES and not p.get("load_bearing"):
            continue
        out.append(e)
    return out


RANK = {"γωνία εξωτερικών τοίχων": 0, "γωνία/συνάντηση τοίχων": 1, "άκρο εξωτερικού τοίχου": 2}


def _merge(points):
    """Columns closer than MERGE become one: the exterior corner first, then junctions, then ends."""
    kept = {}
    for k, reason in sorted(points.items(), key=lambda kv: (RANK.get(kv[1], 3), kv[0])):
        if all(math.hypot(k[0] - q[0], k[1] - q[1]) >= MERGE for q in kept):
            kept[k] = reason
    return kept


def _storeys(doc):
    return sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"})


def _level_name(doc, z):
    return next((str(n) for n, lz in doc.levels.items() if abs(float(lz) - z) < 1e-4), doc.active_level_name())


def _top_of(doc, z, walls):
    above = sorted(float(v) for v in doc.levels.values() if float(v) > z + 0.5)
    if above:
        return above[0]
    return z + max(float(w.params.get("height", 2.7)) for w in walls)


def _openings(doc, wall):
    """(start, end) along the wall axis of its doors and windows, widened by a clearance."""
    out = []
    for e in doc.entities.values():
        if e.kind in ("door", "window", "opening") and e.parent_id == wall.id:
            c, half = float(e.params.get("offset", 0.0)), float(e.params.get("width", 0.0)) / 2
            out.append((c - half - OPENING_CLEAR, c + half + OPENING_CLEAR))
    return out


def _free_of_openings(s, openings, length):
    for a, b in openings:
        if a < s < b:
            s = a if (s - a) <= (b - s) else b
    return max(0.0, min(length, s))


# ---------------------------------------------------------------- structural grid
GRID_SPAN = 6.0        # largest bay (m): slab and beam spans stay within usual RC dwelling sizes
MIN_BAY = 2.0          # no axis closer than this to another (no double columns)
AXIS_TOL = 0.30        # walls within this of an axis are on it


def _direction(w):
    p = w.params
    dx, dy = float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"])
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return None, 0.0
    if abs(dx) / L < 0.03:
        return "x", L                 # runs along y: lies on an x = const axis
    if abs(dy) / L < 0.03:
        return "y", L
    return None, L


def _candidates(walls, exterior, axis):
    """Axis positions offered by the walls (weight: length, exterior ×3), merged within AXIS_TOL."""
    raw = []
    for w in walls:
        d, L = _direction(w)
        if d != axis:
            continue
        p = w.params
        pos = (float(p["x1"]) + float(p["x2"])) / 2 if axis == "x" else (float(p["y1"]) + float(p["y2"])) / 2
        raw.append([pos, L * (3.0 if w.id in exterior else 1.0), w.id in exterior])
    raw.sort()
    merged = []
    for pos, wt, ext in raw:
        if merged and abs(pos - merged[-1][0]) <= AXIS_TOL:
            m = merged[-1]
            m[0] = (m[0] * m[1] + pos * wt) / (m[1] + wt); m[1] += wt; m[2] = m[2] or ext
        else:
            merged.append([pos, wt, ext])
    return merged


def grid_axes(walls, exterior, axis):
    """The structural axes along one direction: exterior walls, then the strongest walls that keep bays ≤ GRID_SPAN."""
    cands = _candidates(walls, exterior, axis)
    if not cands:
        return []
    chosen = sorted({c[0] for c in cands if c[2]} | {cands[0][0], cands[-1][0]})
    # Drop exterior axes closer than MIN_BAY (a jog in the facade): keep the heavier one.
    weight = {c[0]: c[1] for c in cands}
    pruned = []
    for a in chosen:
        if pruned and a - pruned[-1] < MIN_BAY:
            if weight.get(a, 0) > weight.get(pruned[-1], 0):
                pruned[-1] = a
            continue
        pruned.append(a)
    chosen = pruned
    for _ in range(40):
        gaps = [(b - a, a, b) for a, b in zip(chosen, chosen[1:]) if b - a > GRID_SPAN + 1e-6]
        if not gaps:
            break
        _g, a, b = max(gaps)
        mid = (a + b) / 2
        inside = [c for c in cands if a + MIN_BAY <= c[0] <= b - MIN_BAY]
        if inside:
            # A wall carries the new axis: the longest, preferring the middle of the bay.
            best = max(inside, key=lambda c: c[1] * (1.0 - .6 * abs(c[0] - mid) / (b - a)))
            pos = best[0]
        else:
            pos = mid                                     # no wall there: a free axis in the middle
        chosen = sorted(chosen + [pos])
    return chosen


def _inside_building(doc, z, walls, x, y):
    """On a wall (within its thickness) or inside a room of the storey."""
    from archforge.assistant.understanding import inside
    for w in walls:
        p = w.params
        ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        if L2 < 1e-12:
            continue
        t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
        if math.hypot(ax + (bx - ax) * t - x, ay + (by - ay) * t - y) <= float(p["thickness"]) / 2 + SNAP:
            return "wall"
    for f in doc.active_room_faces(z=z):
        if inside(f.polygon, x, y):
            return "room"
    return None


def _wall_at(walls, x, y):
    for w in walls:
        p = w.params
        ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-9:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        s = (x - ax) * ux + (y - ay) * uy
        if -SNAP <= s <= L + SNAP and abs(-(x - ax) * uy + (y - ay) * ux) <= float(p["thickness"]) / 2 + SNAP:
            return w, s, (ax, ay, ux, uy, L)
    return None


def column_points(doc, z):
    """Plan points of the columns a storey needs: ``{(x, y): reason}`` on a structural grid.

    Axes in x and y from the exterior walls and, where a bay would exceed GRID_SPAN, from the
    strongest interior wall in it (or a free axis): the slab loads spread evenly and every slab
    span stays within ~6 m.  Columns where axes cross inside a wall (never free in a room), slid
    out of doors and windows; walls off the grid (diagonal) keep columns at their ends.
    """
    from archforge.mep.ventilation import exterior_walls
    walls = _walls(doc, z)
    if not walls:
        return {}
    exterior = {w.id for w, _n in exterior_walls(doc, z)}
    xs, ys = grid_axes(walls, exterior, "x"), grid_axes(walls, exterior, "y")
    points = {}
    for x in xs:
        for y in ys:
            where = _inside_building(doc, z, walls, x, y)
            if where is None:
                continue
            hit = _wall_at(walls, x, y)
            if hit is not None:
                w, s, (ax, ay, ux, uy, L) = hit
                s = _free_of_openings(s, _openings(doc, w), L)
                px, py = ax + ux * s, ay + uy * s
                ext = w.id in exterior
                points[_key(px, py)] = "γωνία εξωτερικών τοίχων" if ext and (x in (xs[0], xs[-1]) or y in (ys[0], ys[-1])) \
                    else ("φέρων άξονας σε τοίχο" if not ext else "φέρων άξονας στην πρόσοψη")
            # In the middle of a room: no column — the axis' beam spans façade to façade.
    # Walls off the grid (diagonal): columns at their ends.
    for w in walls:
        d, L = _direction(w)
        if d is None and L > 0 and w.id in exterior:
            p = w.params
            for x, y in ((float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))):
                points.setdefault(_key(x, y), "άκρο λοξού τοίχου")
    return _merge(points)


def flush_with_facade(x, y, size, outer):
    """Move a column whose section is thicker than the exterior wall inwards, so its outer face is the
    wall's outer face: nothing hangs outside the building (at a corner, inwards both ways)."""
    dx = dy = 0.0
    for w, (nx, ny) in outer:
        p = w.params
        ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-9:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        s = (x - ax) * ux + (y - ay) * uy
        t = float(p.get("thickness", .2))
        if not (-t <= s <= L + t) or abs(-(x - ax) * uy + (y - ay) * ux) > t / 2 + SNAP:
            continue
        half = (size[1] if abs(nx) > abs(ny) else size[0]) / 2   # the column's half-size across this wall
        shift = max(0.0, half - t / 2)
        if abs(nx) > abs(ny) and abs(dx) < 1e-9:
            dx = -nx * shift
        elif abs(ny) >= abs(nx) and abs(dy) < 1e-9:
            dy = -ny * shift
    return round(x + dx, 4), round(y + dy, 4)


def grid_beams(doc, z, points):
    """Beams on the grid axes between consecutive columns (inside the building)."""
    walls = _walls(doc, z)
    pts = list(points)
    out = []
    for axis in ("x", "y"):
        lines = {}
        for x, y in pts:
            lines.setdefault(round(x if axis == "x" else y, 2), []).append((x, y))
        for _pos, line in lines.items():
            line.sort(key=lambda q: q[1] if axis == "x" else q[0])
            for a, b in zip(line, line[1:]):
                if math.dist(a, b) < 0.3:
                    continue
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if _inside_building(doc, z, walls, *mid):
                    out.append((a, b))
    # Diagonal exterior walls: a beam along each, end to end.
    from archforge.mep.ventilation import exterior_walls
    for w, _n in exterior_walls(doc, z):
        if _direction(w)[0] is None and w in walls:
            p = w.params
            out.append(((float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))))
    return out


def propose_frame(doc, settings=None):
    """New column and beam entities for every storey (existing columns are kept): ``(entities, report)``."""
    from archforge.core.model import Entity
    from archforge.project.brief import load_bearing_walls
    from archforge.structure.analysis.settings import get_settings
    if load_bearing_walls(doc):
        # Stone / solid masonry: the walls carry the loads — no columns; the slabs are designed instead.
        return [], {"storeys": [], "columns": 0, "beams": 0, "load_bearing": True}
    settings = settings or get_settings(doc)
    steel = settings["system"] == "steel"
    construction = "steel" if steel else "reinforced_concrete"
    col_size, beam_size = ((0.20, 0.20), (0.15, 0.30)) if steel else ((0.40, 0.40), (0.25, 0.50))
    existing_cols = [e for e in doc.entities.values() if e.kind == "structural_column"]
    existing_beams = [e for e in doc.entities.values() if e.kind == "structural_beam"]
    entities, report = [], {"storeys": [], "columns": 0, "beams": 0}
    # Top down: what does each storey carry? Its own grid, plus every column of the storeys above
    # that stands over it — a column is never left without one under it down to the foundation.
    per_storey, carried = {}, {}
    for z in reversed(_storeys(doc)):
        walls = _walls(doc, z)
        pts = column_points(doc, z)
        for q, why in carried.items():
            if all(math.hypot(q[0] - p[0], q[1] - p[1]) >= MERGE for p in pts) and _inside_building(doc, z, walls, *q):
                pts[q] = "στηρίζει κολόνα του ορόφου από πάνω"
        per_storey[z] = pts
        carried = {**carried, **pts}
    for z in _storeys(doc):
        walls = _walls(doc, z)
        top = _top_of(doc, z, walls)
        level = _level_name(doc, z)
        pts = per_storey[z]
        new_cols = 0
        from archforge.mep.ventilation import exterior_walls
        outer = exterior_walls(doc, z)
        for (x, y), reason in sorted(pts.items()):
            x, y = flush_with_facade(x, y, col_size, outer)
            if any(abs(float(c.params["z"]) - z) < 0.05 and math.hypot(float(c.params["x"]) - x, float(c.params["y"]) - y) <= EXISTING
                   for c in existing_cols):
                continue
            params = {"x": x, "y": y, "z": z, "width": col_size[0], "depth": col_size[1], "height": top - z,
                      "rotation": 0.0, "role": "structural", "construction": construction, "section": "rectangular",
                      "base_level": level, "top_level": "Unassigned"}
            if steel:
                params["profile"] = "HEB200"
            entities.append(Entity("structural_column", params, name="Κολόνα"))
            new_cols += 1
        # Beams on the grid axes, column to column.
        all_pts = dict(pts)
        for c in existing_cols:
            if abs(float(c.params["z"]) - z) < 0.05:
                all_pts.setdefault((float(c.params["x"]), float(c.params["y"])), "υπάρχουσα")
        new_beams = 0
        for (x1, y1), (x2, y2) in grid_beams(doc, z, all_pts):
            if any(abs(float(e.params["z"]) + float(e.params["height"]) - top) < 0.05 and
                   math.hypot((float(e.params["x1"]) + float(e.params["x2"])) / 2 - (x1 + x2) / 2,
                              (float(e.params["y1"]) + float(e.params["y2"])) / 2 - (y1 + y2) / 2) < 0.3
                   for e in existing_beams):
                continue
            params = {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "z": top - beam_size[1], "width": beam_size[0],
                      "height": beam_size[1], "role": "structural", "construction": construction,
                      "section": "rectangular", "level": level}
            if steel:
                params["profile"] = "IPE300"
            entities.append(Entity("structural_beam", params, name="Δοκός"))
            new_beams += 1
        report["storeys"].append({"z": z, "level": level, "columns": new_cols, "beams": new_beams})
        report["columns"] += new_cols
        report["beams"] += new_beams
    return entities, report
