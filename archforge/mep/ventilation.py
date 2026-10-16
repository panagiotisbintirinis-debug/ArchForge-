"""Extract ventilation: points in the Document, ducts derived from them.

The user places the kitchen hood and the bathroom / WC extract fans.  The
ducts to the outside are DERIVED on demand, like the pipes: moving a point,
a wall or changing the outlet re-routes at once.

Rules (stated so a mechanical engineer can check them):

* Kitchen hood: extract duct Ø125 for up to 450 m³/h, Ø150 above that
  (default 400 m³/h, typical for a domestic hood).  Bathroom fan Ø100 at
  90 m³/h, WC fan Ø100 at 60 m³/h (intermittent rates of the DIN 18017-3
  order of magnitude).
* The duct rises from the device to the duct level, 10 cm under the ceiling
  (inside a bulkhead / suspended ceiling, above the wall cabinets), then runs
  STRAIGHT in plan to the nearest exterior wall, where it ends in a wall
  grille.  Straight runs: as few bends as possible, as for any duct.
* A wall hood and an island hood follow the same rule: an island hood simply
  rises from the middle of the room into the ceiling first.
* Outlet per point (``outlet``): 'wall' (through the nearest exterior wall),
  'roof' (vertical through the roof, cap 50 cm above the roof surface) or
  'auto': wall, unless the horizontal run would exceed the length limit and
  the roof is reachable (the point is on the top storey) - then roof.
* An exterior wall is a wall with open space on one side: a ray from the
  middle of one face, along its normal, meets no other wall of the storey.
* Length limits (rule of thumb, check the manufacturer's data): horizontal
  duct ≤ 6 m for a hood, ≤ 4 m for a small fan.  Longer runs are flagged,
  not refused.  Air velocity in the duct is reported.

Status: pre-design layout for review by a mechanical engineer; it is not a
pressure-drop or fan-selection calculation.
"""
from __future__ import annotations

import math

from archforge.mep.plumbing import _levels, pipe_mesh

PROVENANCE = ("Προμελέτη απαγωγής: απορροφητήρας Ø125 (≤450 m³/h, αλλιώς Ø150), ανεμιστήρες μπάνιου/WC Ø100 "
              "(τάξη μεγέθους DIN 18017-3), ευθεία όδευση στον πλησιέστερο εξωτερικό τοίχο ή από τη στέγη — "
              "όχι υπολογισμός πτώσης πίεσης, προς έλεγχο από μηχανολόγο και με τα στοιχεία του κατασκευαστή")

# type: label, default airflow m³/h, device height above floor (m), max horizontal duct (m), plan letter
POINT_TYPES = {
    "hood": ("Απορροφητήρας κουζίνας", 400.0, 2.10, 6.0, "ΑΠ"),
    "bath_fan": ("Ανεμιστήρας απαγωγής μπάνιου", 90.0, 2.20, 4.0, "ΕΞ"),
    "wc_fan": ("Ανεμιστήρας απαγωγής WC", 60.0, 2.20, 4.0, "ΕΞ"),
}
OUTLETS = ("auto", "wall", "roof")
UNDER_CEILING = 0.10       # duct axis under the ceiling
ROOF_CAP = 0.50            # cap height above the roof surface
GRILLE_OUT = 0.05          # grille projection outside the wall face
STOREY_HEIGHT = 3.0        # assumed when there is neither a storey above nor walls


def ventilation_points(doc):
    return [e for e in doc.entities.values() if e.kind == "ventilation_point"]


def duct_diameter(point_type, airflow):
    if point_type == "hood":
        return 125 if airflow <= 450.0 else 150
    return 100


def airflow_of(params):
    value = params.get("airflow")
    return float(value) if value not in (None, "") and float(value) > 0 else POINT_TYPES[params["point_type"]][1]


def _floor_of(doc, z):
    below = [lz for lz in _levels(doc) if lz <= z + 1e-4]
    return below[-1] if below else _levels(doc)[0]


def _ceiling(doc, floor):
    """Underside of the ceiling: the slab of the storey above, else the top of the walls."""
    above = [lz for lz in _levels(doc) if lz > floor + 1e-4]
    if above:
        return above[0] - 0.20
    heights = [float(w.params.get("height", 0.0)) for w in _walls(doc, floor)]
    return floor + (max(heights) if heights else STOREY_HEIGHT - 0.20)


def _is_top_storey(doc, floor):
    return not [lz for lz in _levels(doc) if lz > floor + 1e-4]


def _walls(doc, floor):
    return [e for e in doc.entities.values()
            if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - floor) < 0.05]


def _ray_hits(walls, skip, ox, oy, dx, dy):
    for w in walls:
        if w.id == skip:
            continue
        p = w.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        ex, ey = x2 - x1, y2 - y1
        den = dx * ey - dy * ex
        if abs(den) < 1e-12:
            continue
        t = ((x1 - ox) * ey - (y1 - oy) * ex) / den
        s = ((x1 - ox) * dy - (y1 - oy) * dx) / den
        if t > 1e-6 and -1e-6 <= s <= 1 + 1e-6:
            return True
    return False


def exterior_walls(doc, floor):
    """``[(wall, outward_normal)]``: walls of the storey with open space on one side."""
    walls = _walls(doc, floor)
    out = []
    for w in walls:
        p = w.params
        x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 1e-9:
            continue
        nx, ny = -(y2 - y1) / length, (x2 - x1) / length
        sides = []
        for sign in (1.0, -1.0):
            # Sample a few points along the wall so a short partition meeting it
            # in the middle does not hide the open side.
            free = any(not _ray_hits(walls, w.id, x1 + (x2 - x1) * f + sign * nx * (t / 2 + 0.01),
                                     y1 + (y2 - y1) * f + sign * ny * (t / 2 + 0.01), sign * nx, sign * ny)
                       for f in (0.25, 0.5, 0.75))
            if free:
                sides.append(sign)
        if len(sides) == 1:
            out.append((w, (sides[0] * nx, sides[0] * ny)))
    return out


def _nearest_exit(doc, x, y, floor):
    """Closest exterior wall point: ``(wall, inner_xy, outer_xy, distance)`` or None."""
    best = None
    for w, (nx, ny) in exterior_walls(doc, floor):
        p = w.params
        x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        # Keep the grille clear of the wall ends (corners).
        margin = min(0.15, math.sqrt(L2) / 2) / math.sqrt(L2)
        s = max(margin, min(1.0 - margin, ((x - x1) * dx + (y - y1) * dy) / L2))
        cx, cy = x1 + dx * s, y1 + dy * s
        if (x - cx) * nx + (y - cy) * ny > 0:
            continue                       # the point is outside this wall
        inner = (cx - nx * t / 2, cy - ny * t / 2)
        outer = (cx + nx * (t / 2 + GRILLE_OUT), cy + ny * (t / 2 + GRILLE_OUT))
        d = math.hypot(x - inner[0], y - inner[1])
        if best is None or (d, w.id) < (best[3], best[0].id):
            best = (w, inner, outer, d)
    return best


def _roof_top(doc, x, y, floor):
    """Height of the roof surface above (x, y), else the top of the storey."""
    best = None
    for e in doc.entities.values():
        if e.kind != "pitched_roof":
            continue
        from archforge.structure.timber_roof import height_at, planes
        for plane in planes(e.params):
            poly = plane[0]
            inside = False
            for i in range(len(poly)):
                (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
                if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
                    inside = not inside
            if inside:
                h = height_at(e.params, plane, x, y)
                best = h if best is None else max(best, h)
    if best is None:
        best = _ceiling(doc, floor) + 0.30                 # through a flat roof slab
    return best


def outlet_of(doc, e):
    """'wall' or 'roof' for one point: explicit choice, else the length rule decides."""
    p = e.params
    choice = str(p.get("outlet", "auto"))
    floor = _floor_of(doc, float(p["z"]))
    exit_ = _nearest_exit(doc, float(p["x"]), float(p["y"]), floor)
    if choice in ("wall", "roof"):
        return choice if choice == "roof" or exit_ is not None else "roof"
    limit = POINT_TYPES[p["point_type"]][3]
    if exit_ is None or (exit_[3] > limit and _is_top_storey(doc, floor)):
        return "roof"
    return "wall"


def _crossings(walls, skip, a, b):
    n = 0
    for w in walls:
        if w.id == skip:
            continue
        p = w.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        d1 = (b[0] - a[0]) * (y1 - a[1]) - (b[1] - a[1]) * (x1 - a[0])
        d2 = (b[0] - a[0]) * (y2 - a[1]) - (b[1] - a[1]) * (x2 - a[0])
        d3 = (x2 - x1) * (a[1] - y1) - (y2 - y1) * (a[0] - x1)
        d4 = (x2 - x1) * (b[1] - y1) - (y2 - y1) * (b[0] - x1)
        if d1 * d2 < 0 and d3 * d4 < 0:
            n += 1
    return n


def route_ventilation(doc):
    """Derived ducts: ``{"ducts": [...], "terminals": [...], "report": {...}}``.

    Each duct is ``(start_xyz, end_xyz, diameter_mm, point_id)``; each terminal
    is a dict with position, kind ('wall' grille or 'roof' cap), Ø and point.
    """
    result = {"ducts": [], "terminals": [], "report": {"points": {}, "warnings": [], "duct_m": 0.0,
                                                       "provenance": PROVENANCE}}
    for e in sorted(ventilation_points(doc), key=lambda q: q.id):
        p = e.params
        label = e.name or POINT_TYPES[p["point_type"]][0]
        x, y = float(p["x"]), float(p["y"])
        floor = _floor_of(doc, float(p["z"]))
        flow = airflow_of(p)
        dia = duct_diameter(p["point_type"], flow)
        device = floor + POINT_TYPES[p["point_type"]][2]
        duct_z = max(device, _ceiling(doc, floor) - UNDER_CEILING)
        outlet = outlet_of(doc, e)
        ducts = []
        horizontal = 0.0
        bends = 0
        crossings = 0
        if outlet == "wall":
            wall, inner, outer, dist = _nearest_exit(doc, x, y, floor)
            if duct_z > device + 1e-6:
                ducts.append(((x, y, device), (x, y, duct_z)))
                bends += 1
            ducts.append(((x, y, duct_z), (inner[0], inner[1], duct_z)))
            ducts.append(((inner[0], inner[1], duct_z), (outer[0], outer[1], duct_z)))
            horizontal = dist
            crossings = _crossings(_walls(doc, floor), wall.id, (x, y), inner)
            result["terminals"].append({"x": outer[0], "y": outer[1], "z": duct_z, "kind": "wall",
                                        "diameter": dia, "point": e.id, "wall": wall.id})
        else:
            top = _roof_top(doc, x, y, floor) + ROOF_CAP
            ducts.append(((x, y, device), (x, y, top)))
            result["terminals"].append({"x": x, "y": y, "z": top, "kind": "roof", "diameter": dia, "point": e.id,
                                        "wall": None})
            if not _is_top_storey(doc, floor):
                result["report"]["warnings"].append(f"{label}: κατακόρυφος αγωγός μέσα από τους ορόφους (φρεάτιο)")
        ducts = [(a, b) for a, b in ducts if math.dist(a, b) > 1e-6]
        result["ducts"] += [(a, b, dia, e.id) for a, b in ducts]
        length = sum(math.dist(a, b) for a, b in ducts)
        area = math.pi * (dia / 2000.0) ** 2
        velocity = flow / 3600.0 / area
        limit = POINT_TYPES[p["point_type"]][3]
        if outlet == "wall" and horizontal > limit:
            result["report"]["warnings"].append(
                f"{label}: οριζόντιος αγωγός {horizontal:.1f} m > {limit:g} m — έλεγχος ανεμιστήρα/κατασκευαστή")
        if crossings:
            result["report"]["warnings"].append(f"{label}: διάτρηση {crossings} εσωτερικού τοίχου")
        result["report"]["points"][e.id] = {
            "label": label, "outlet": outlet, "diameter": dia, "airflow": flow, "length_m": round(length, 2),
            "horizontal_m": round(horizontal, 2), "bends": bends, "wall_crossings": crossings,
            "velocity_ms": round(velocity, 1)}
    result["report"]["duct_m"] = round(sum(math.dist(a, b) for a, b, _d, _i in result["ducts"]), 2)
    return result


_CACHE = {"key": None, "value": None}


def route_ventilation_cached(doc):
    """route_ventilation() reused while walls, roofs and points are unchanged."""
    items = []
    for e in doc.entities.values():
        if e.kind in ("ventilation_point", "wall", "pitched_roof"):
            items.append((e.kind, e.id, tuple(sorted((k, str(v)) for k, v in e.params.items())), e.name))
    key = (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())))
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_ventilation(doc)
    return _CACHE["value"]


def point_marker_mesh(doc, params):
    """Device body at its height: hood canopy or flat fan box (selectable in 3D)."""
    x, y = float(params["x"]), float(params["y"])
    floor = _floor_of(doc, float(params["z"]))
    top = floor + POINT_TYPES[params["point_type"]][2]
    if params["point_type"] == "hood":
        sx, sy, z0 = 0.30, 0.25, top - 0.55
    else:
        sx, sy, z0 = 0.10, 0.10, top - 0.08
    return _box(x, y, (z0 + top) / 2, sx, sy, (top - z0) / 2)


_BOX_QUADS = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))


def _box(x, y, z, sx, sy, sz):
    verts = [(x + dx, y + dy, z + dz) for dx in (-sx, sx) for dy in (-sy, sy) for dz in (-sz, sz)]
    return verts, [t for a, b, c, d in _BOX_QUADS for t in ((a, b, c), (a, c, d))]


def duct_meshes(route):
    """One mesh for all ducts (true Ø) and one for the terminals (grilles / caps)."""
    meshes = ([], []), ([], [])
    parts = [(0, pipe_mesh(a, b, dia, sides=12)) for a, b, dia, _pid in route["ducts"]]
    for term in route["terminals"]:
        x, y, z, dia = term["x"], term["y"], term["z"], term["diameter"]
        if term["kind"] == "roof":
            parts.append((1, pipe_mesh((x, y, z), (x, y, z + 0.12), dia + 120, sides=12)))
        else:
            half = dia / 2000.0 + 0.03
            parts.append((1, _box(x, y, z, half, half, half)))
    for k, (v, t) in parts:
        verts, tris = meshes[k]
        base = len(verts)
        verts += [list(map(float, q)) for q in v]
        tris += [[base + i for i in tri] for tri in t]
    return meshes
