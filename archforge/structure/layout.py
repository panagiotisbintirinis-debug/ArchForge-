"""Proposed load-bearing frame from the walls: columns and beams where they are needed.

Drawn after the walls and rooms, the frame follows them (rules stated so a
structural engineer can check them):

* Columns at every wall corner and junction (L, T, cross) and at the free
  ends of exterior walls; along longer walls, extra columns so that no clear
  distance between columns exceeds ``MAX_SPAN`` (6.0 m, usual for RC
  dwellings).  Never inside a door or window: a column that would fall in
  an opening moves to the nearer side of it.
* Beams along every wall from column to column, their top on the slab level
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
SNAP = 0.05
EXISTING = 0.30
OPENING_CLEAR = 0.15


def _key(x, y):
    return (round(x / SNAP) * SNAP, round(y / SNAP) * SNAP)


def _walls(doc, z):
    return [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 0.05]


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


def column_points(doc, z):
    """Plan points of the columns a storey needs: ``{(x, y): reason}``."""
    from archforge.mep.ventilation import exterior_walls
    walls = _walls(doc, z)
    if not walls:
        return {}
    exterior = {w.id for w, _n in exterior_walls(doc, z)}
    ends = {}
    for w in walls:
        p = w.params
        for x, y in ((float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))):
            ends.setdefault(_key(x, y), []).append(w.id)
    points = {}
    # Junctions: an end shared by two walls, or an end lying on another wall (T).
    for k, ids in ends.items():
        on_other = []
        for w in walls:
            if w.id in ids:
                continue
            p = w.params
            ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
            L2 = (bx - ax) ** 2 + (by - ay) ** 2
            if L2 < 1e-12:
                continue
            t = ((k[0] - ax) * (bx - ax) + (k[1] - ay) * (by - ay)) / L2
            if 0.0 < t < 1.0 and math.hypot(ax + (bx - ax) * t - k[0], ay + (by - ay) * t - k[1]) <= float(p["thickness"]) / 2 + SNAP:
                on_other.append(w.id)
        if len(ids) >= 2 or on_other:
            points[k] = "γωνία/συνάντηση τοίχων"
        elif any(i in exterior for i in ids):
            points[k] = "άκρο εξωτερικού τοίχου"
    # Long walls: intermediate columns, never inside an opening.
    for w in walls:
        p = w.params
        ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
        length = math.hypot(bx - ax, by - ay)
        if length < 1e-9:
            continue
        ux, uy = (bx - ax) / length, (by - ay) / length
        on_wall = sorted({0.0, length} | {round((k[0] - ax) * ux + (k[1] - ay) * uy, 3) for k in points
                                          if abs(-(k[0] - ax) * uy + (k[1] - ay) * ux) <= float(p["thickness"]) / 2 + SNAP
                                          and -SNAP <= (k[0] - ax) * ux + (k[1] - ay) * uy <= length + SNAP})
        openings = _openings(doc, w)
        for a, b in zip(on_wall, on_wall[1:]):
            n = math.ceil((b - a) / MAX_SPAN - 1e-9)
            for i in range(1, n):
                s = _free_of_openings(a + (b - a) * i / n, openings, length)
                points[_key(ax + ux * s, ay + uy * s)] = "ενδιάμεση (άνοιγμα ≤ 6 m)"
    return points


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
    for z in _storeys(doc):
        walls = _walls(doc, z)
        top = _top_of(doc, z, walls)
        level = _level_name(doc, z)
        pts = column_points(doc, z)
        new_cols = 0
        for (x, y), reason in sorted(pts.items()):
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
        # Beams along the walls, column to column.
        all_pts = list(pts) + [(float(c.params["x"]), float(c.params["y"])) for c in existing_cols
                               if abs(float(c.params["z"]) - z) < 0.05]
        new_beams = 0
        for w in walls:
            p = w.params
            ax, ay, bx, by = (float(p[c]) for c in ("x1", "y1", "x2", "y2"))
            length = math.hypot(bx - ax, by - ay)
            if length < 1e-9:
                continue
            ux, uy = (bx - ax) / length, (by - ay) / length
            on = sorted({round((x - ax) * ux + (y - ay) * uy, 3) for x, y in all_pts
                         if abs(-(x - ax) * uy + (y - ay) * ux) <= float(p["thickness"]) / 2 + SNAP
                         and -SNAP <= (x - ax) * ux + (y - ay) * uy <= length + SNAP})
            for a, b in zip(on, on[1:]):
                if b - a < 0.3:
                    continue
                x1, y1, x2, y2 = ax + ux * a, ay + uy * a, ax + ux * b, ay + uy * b
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
