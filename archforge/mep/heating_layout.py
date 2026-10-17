"""Heating layout: supply and return pipes, manifolds and underfloor loops, derived from the heating points.

The owner chooses the system on the heat source (``heating_system``):

* ``radiators`` (καλοριφέρ): a radiator per room; each gets a thermostatic valve on the supply, a lockshield on the
  return and an air vent.
* ``fan_coil``: a fan coil per room, connected like a radiator (valve set + condensate is the installer's).
* ``underfloor`` (ενδοδαπέδια): one loop per heated room from the storey's manifold; the loop is laid at the spacing
  the owner/engineer declares on the source (``loop_spacing``) — none is assumed.

Distribution (``distribution`` on the source): ``manifold`` (συλλέκτης per storey, one supply + one return home run
per circuit) or ``two_pipe`` (δισωλήνιο with branches; radiators / fan coils only).  Underfloor is always manifold.

Every manifold shows its parts: supply and return bars, a flow meter (υδρονομέας) per outlet on the supply, a
valve per outlet on the return (actuator for the room thermostat), ball valves on the feed, air vent and drain cock
at the ends; an underfloor manifold fed by a boiler also gets a mixing group (circulator + mixing valve).

Pipe sizes: the owner's trade rule (17/10), as for the water supply — by the kind of emitter, not a hydraulic
calculation: radiators Ø18 per circuit, underfloor loops Ø16, fan coils Ø20; the mains to the manifolds Ø20
(fan coils Ø26).  PEX-Al-PEX.  What is DERIVED here is geometry: routes, lengths, counts.  No heat load, emitter
output, flow, pump or balancing is computed (``heating_rules``: ENGINEER_REVIEW).
"""
from __future__ import annotations

import math

SYSTEMS = {"radiators": "Καλοριφέρ (θερμαντικά σώματα)", "underfloor": "Ενδοδαπέδια", "fan_coil": "Fan coil"}
DISTRIBUTIONS = {"manifold": "Συλλέκτες ανά όροφο", "two_pipe": "Δισωλήνιο με κλάδους"}
# Owner's trade rule 17/10: (Ø per circuit, Ø of the mains) in mm, PEX-Al-PEX.
PIPE_SIZES = {"radiators": (18, 20), "underfloor": (16, 20), "fan_coil": (20, 26)}
SIZE_RULE = "Κανόνας ιδιοκτήτη 17/10: καλοριφέρ Φ18, ενδοδαπέδια Φ16, fan coil Φ20· προς συλλέκτες Φ20 (fan coil Φ26)"
DEFAULT_SYSTEM, DEFAULT_DISTRIBUTION = "radiators", "manifold"
SOURCES = ("boiler", "heat_pump", "heat_source")
EMITTERS = ("radiator", "fan_coil")
# Connection height of the pipes at each point, above its floor (m) — where the pipe leaves the screed.
CONNECTION = {"radiator": 0.15, "fan_coil": 0.15, "manifold": 0.55, "boiler": 1.00, "heat_pump": 0.30, "heat_source": 0.50}
RETURN_OFFSET = 0.06        # plan offset of the return so both pipes stay visible
HOME_RUN_GAP = 0.05         # side by side home runs from a manifold
OUTLET_PITCH = 0.05         # manifold outlet spacing (m), drawing/3D only
LOOP_INSET = 0.15           # loops stay this far from the walls (edge strip + wall)
# Rooms that get no emitter / loop of their own.
UNHEATED_USES = ("Κλιμακοστάσιο", "Λεβητοστάσιο", "Γκαράζ", "Αποθήκη", "Πισίνα", "Αυλή", "Αίθριο")
PROVENANCE = ("Χάραξη προσαγωγής/επιστροφής από τις θέσεις των σημείων (συλλέκτες ή δισωλήνιο), βρόχοι ενδοδαπέδιας "
              "στο βήμα που δηλώθηκε — μήκη και τεμάχια από τη γεωμετρία, διατομές από κανόνα ιδιοκτήτη ανά είδος "
              "εκπομπής· θερμικά φορτία, ισχύς σωμάτων, παροχές, υδραυλικός υπολογισμός, κυκλοφορητής και "
              "εξισορρόπηση ΔΕΝ υπολογίζονται: μηχανολόγος (ENGINEER_REVIEW)")


def heating_points(doc):
    return [e for e in doc.entities.values() if e.kind == "heating_point"]


def source_of(doc):
    return next((e for e in heating_points(doc) if e.params.get("point_type") in SOURCES), None)


def system_of(doc):
    src = source_of(doc)
    value = str(src.params.get("heating_system", DEFAULT_SYSTEM)) if src is not None else DEFAULT_SYSTEM
    return value if value in SYSTEMS else DEFAULT_SYSTEM


def distribution_of(doc):
    if system_of(doc) == "underfloor":
        return "manifold"
    src = source_of(doc)
    value = str(src.params.get("distribution", DEFAULT_DISTRIBUTION)) if src is not None else DEFAULT_DISTRIBUTION
    return value if value in DISTRIBUTIONS else DEFAULT_DISTRIBUTION


def loop_spacing(doc):
    """Declared underfloor loop spacing (m), or None when nobody has declared it."""
    src = source_of(doc)
    value = src.params.get("loop_spacing") if src is not None else None
    return float(value) if value else None


def _room_use(doc, face):
    meta = doc.room_metadata(face.signature)
    return str(meta.get("use") or meta.get("name") or "")


def heated_rooms(doc, floor):
    """Room faces of the storey that are heated (not open to the sky, not stairs / storage / boiler room)."""
    try:
        faces = doc.active_room_faces(z=floor)
    except Exception:                                         # noqa: BLE001 - a storey without closed rooms
        return []
    return [f for f in faces if not any(_room_use(doc, f).startswith(u) for u in UNHEATED_USES)]


def _inside(poly, x, y):
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _face_of(faces, x, y):
    return next((f for f in faces if _inside(f.polygon, x, y)), None)


# ----------------------------------------------------------------------------------------------- placement
def emitter_positions(doc, floor, kind="radiator"):
    """Where a radiator / fan coil goes in each heated room of the storey without one: under its widest window
    (inside, against the wall), else at the middle of the room's longest wall.  ``[(x, y, rotation_deg, room)]``."""
    from archforge.assistant.understanding import _opening_sides
    faces = heated_rooms(doc, floor)
    have = {id(f) for f in faces for e in heating_points(doc)
            if e.params.get("point_type") in EMITTERS and abs(float(e.params.get("z", 0.0)) - floor) < 0.5
            and _inside(f.polygon, float(e.params["x"]), float(e.params["y"]))}
    windows = [w for w in doc.entities.values() if w.kind == "window" and w.parent_id in doc.entities
               and abs(float(doc.get(w.parent_id).params.get("z", 0.0)) - floor) < 0.05]
    out = []
    for f in faces:
        if id(f) in have:
            continue
        best = None
        for w in windows:
            for side in _opening_sides(doc, w):
                if _inside(f.polygon, *side):
                    width = float(w.params.get("width", 1.0))
                    if best is None or width > best[0]:
                        best = (width, side, doc.get(w.parent_id))
        if best is not None:
            (x, y), wall = best[1], best[2]
        else:
            poly = f.polygon
            edges = [(poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))]
            a, b = max(edges, key=lambda ab: math.dist(*ab))
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            L = math.dist(a, b) or 1.0
            nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
            if not _inside(poly, mx + nx * 0.2, my + ny * 0.2):
                nx, ny = -nx, -ny
            x, y, wall = mx + nx * 0.2, my + ny * 0.2, None
        if wall is not None:
            p = wall.params
            ang = math.degrees(math.atan2(float(p["y2"]) - float(p["y1"]), float(p["x2"]) - float(p["x1"])))
            # Against the wall face: wall side point + 5 cm into the room (the radiator's depth is 10 cm).
            wx, wy = _wall_foot(p, x, y)
            d = math.hypot(x - wx, y - wy) or 1.0
            x, y = wx + (x - wx) / d * (float(p["thickness"]) / 2 + 0.08), wy + (y - wy) / d * (float(p["thickness"]) / 2 + 0.08)
        else:
            ang = 0.0
        out.append((round(x, 3), round(y, 3), round(ang, 1), _room_use(doc, f)))
    return out


def _wall_foot(p, x, y):
    ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1.0
    t = max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
    return ax + (bx - ax) * t, ay + (by - ay) * t


# ----------------------------------------------------------------------------------------------- loops
def loop_path(polygon, start, spacing):
    """Serpentine loop inside ``polygon`` at ``spacing``, beginning and ending at the side nearest ``start``.

    Runs parallel to the room's longer side, inset LOOP_INSET from the walls; the last run comes back along the
    edge to the start, so supply and return both meet the manifold's home runs.  ``[(x, y)]``."""
    xs = [p[0] for p in polygon]; ys = [p[1] for p in polygon]
    x0, x1, y0, y1 = min(xs) + LOOP_INSET, max(xs) - LOOP_INSET, min(ys) + LOOP_INSET, max(ys) - LOOP_INSET
    if x1 - x0 < spacing or y1 - y0 < spacing:
        return []
    along_x = (x1 - x0) >= (y1 - y0)
    # Lines across the short side, starting from the side nearest the entry.
    lo, hi = (y0, y1) if along_x else (x0, x1)
    n = int((hi - lo) / spacing) + 1
    pos = [lo + k * spacing for k in range(n)]
    if abs((start[1] if along_x else start[0]) - hi) < abs((start[1] if along_x else start[0]) - lo):
        pos = pos[::-1]
    a, b = (x0, x1) if along_x else (y0, y1)
    if abs((start[0] if along_x else start[1]) - b) < abs((start[0] if along_x else start[1]) - a):
        a, b = b, a
    pts = []
    for k, c in enumerate(pos):
        run = [(a, c), (b, c)] if k % 2 == 0 else [(b, c), (a, c)]
        # Clip to the polygon (an L room): keep the part inside.
        run = [q for q in run if _inside(polygon, *(q if along_x else (q[1], q[0])))] or []
        if len(run) == 2:
            pts += run
    if len(pts) < 2:
        return []
    # Back to the start along the entry side (a run ends far when the count is odd): supply and return both
    # leave the room at its entry, next to each other.
    if pts[-1][0] != a:
        pts.append((a, pts[-1][1]))
    pts.append((a, pos[0]))
    return [q if along_x else (q[1], q[0]) for q in pts]


# ----------------------------------------------------------------------------------------------- routing
def route_heating(doc):
    """Derived network: ``{"supply", "return": [(a, b, Ø mm)], "loops": [...], "manifolds": [...], "report": {...}}``."""
    from archforge.mep.plumbing import SCREED, _floor_of, _Grid, _grow, _segments, _simplify
    system, dist = system_of(doc), distribution_of(doc)
    report = {"system": system, "system_label": SYSTEMS[system], "distribution": dist,
              "distribution_label": DISTRIBUTIONS[dist], "supply_m": 0.0, "return_m": 0.0, "loop_m": 0.0,
              "loop_area_m2": 0.0, "circuits": 0, "unserved": [], "warnings": [], "auto": [], "provenance": PROVENANCE,
              "size_rule": SIZE_RULE, "length_by_dn": {}}
    result = {"supply": [], "return": [], "loops": [], "manifolds": [], "emitters": [], "report": report}
    pts = heating_points(doc)
    src = source_of(doc)
    emitters = [e for e in pts if e.params.get("point_type") in EMITTERS]
    if system in ("radiators", "fan_coil") and not emitters:
        return result
    if src is None:
        report["unserved"] = [e.name or e.params["point_type"] for e in emitters] or ["χωρίς πηγή θέρμανσης"]
        return result
    sx, sy, sz = (float(src.params[k]) for k in ("x", "y", "z"))
    sfloor = _floor_of(doc, sz)
    spacing = loop_spacing(doc)
    circuit_dn, main_dn = PIPE_SIZES[system]
    if system == "underfloor" and spacing is None:
        report["warnings"].append("Ενδοδαπέδια: δεν έχει δηλωθεί βήμα βρόχων (Ιδιότητες πηγής ▸ Βήμα βρόχων) — "
                                  "οι βρόχοι δεν χαράζονται ούτε μετρώνται")
    # Storeys served: those with emitters, or (underfloor) every storey with heated rooms.
    if system == "underfloor":
        levels = sorted({float(v) for v in doc.levels.values()} | {sfloor})
        floors = [z for z in levels if heated_rooms(doc, z)]
    else:
        floors = sorted({_floor_of(doc, float(e.params["z"])) for e in emitters})
    placed_manifolds = [e for e in pts if e.params.get("point_type") == "manifold"]
    for floor in floors:
        z = floor + SCREED
        rooms = heated_rooms(doc, floor)
        members = [e for e in emitters if _floor_of(doc, float(e.params["z"])) == floor]
        # Circuits of this storey: (id, xy of its connection, kind, label, loop polygon or None)
        circuits = []
        shift = {}                     # circuit id → plan shift of its own home run (side by side from the manifold)
        if system == "underfloor":
            for f in rooms:
                circuits.append((f"loop:{f.signature}", None, "loop", _room_use(doc, f) or "Χώρος", f.polygon))
        else:
            for e in members:
                circuits.append((e.id, (float(e.params["x"]), float(e.params["y"])), e.params["point_type"],
                                 e.name or e.params["point_type"], None))
        if not circuits:
            continue
        root = (sx, sy)
        anchor = [root] + [c[1] for c in circuits if c[1]] + [q for c in circuits if c[4] for q in c[4]]
        grid = _Grid(doc, floor, anchor)
        root_cell = grid.cell(*root)
        if dist == "manifold":
            here = [m for m in placed_manifolds if _floor_of(doc, float(m.params["z"])) == floor]
            if here:
                mans = [(m.id, float(m.params["x"]), float(m.params["y"]), False) for m in here]
            else:
                # One manifold for the storey, on the wall nearest the middle of its circuits (auto).
                cs = [c[1] or _centroid(c[4]) for c in circuits]
                cx, cy = sum(q[0] for q in cs) / len(cs), sum(q[1] for q in cs) / len(cs)
                mx, my = _manifold_spot(doc, floor, cx, cy, rooms)
                mans = [(f"auto:{floor}", mx, my, True)]
                report["auto"].append(f"Συλλέκτης θέρμανσης (αυτόματα) +{floor:.2f}: ({mx:.2f}, {my:.2f})")
            groups = {m[0]: [] for m in mans}
            for c in circuits:
                q = c[1] or _centroid(c[4])
                m = min(mans, key=lambda m: math.dist((m[1], m[2]), q))
                groups[m[0]].append(c)
            feeds = {}
            for mid, mx, my, auto in mans:
                group = groups[mid]
                if not group:
                    continue
                mcell = grid.cell(mx, my)
                feeds[mid] = mcell
                outlets = []
                for k, (cid, xy, kind, label, poly) in enumerate(sorted(group, key=lambda c: c[3])):
                    slot = (k - (len(group) - 1) / 2) * HOME_RUN_GAP
                    shift[cid] = slot
                    target = xy
                    if poly is not None:
                        # The loop starts on the room side nearest the manifold, inset from the wall.
                        target = _entry_point(poly, (mx, my))
                    path = _simplify([grid.point(c_) for c_ in grid.route(grid.cell(*target), {mcell})])
                    for system_key, off in (("supply", 0.0), ("return", RETURN_OFFSET)):
                        d = slot + off
                        for a, b in zip(path, path[1:]):
                            result[system_key].append(((a[0] + d, a[1] + d, z), (b[0] + d, b[1] + d, z), circuit_dn))
                        # Last stretch from the grid node to the point itself.
                        g = path[0]
                        if math.dist(g, target) > 1e-6:
                            result[system_key].append(((target[0] + d, target[1] + d, z), (g[0] + d, g[1] + d, z), circuit_dn))
                        # Into the manifold bar (each outlet on its own spot).
                        e_ = path[-1]
                        bar = (mx + d, my + d)
                        if math.dist(e_, (mx, my)) > 1e-6:
                            result[system_key].append(((e_[0] + d, e_[1] + d, z), (bar[0], bar[1], z), circuit_dn))
                    if poly is not None and spacing:
                        loop = loop_path(poly, target, spacing)
                        if loop:
                            length = sum(math.dist(a, b) for a, b in zip(loop, loop[1:]))
                            area = _area(poly)
                            result["loops"].append({"room": label, "points": loop, "z": z, "length_m": round(length, 2),
                                                    "area_m2": round(area, 2), "manifold": mid, "entry": target,
                                                    "perimeter_m": round(sum(math.dist(poly[i], poly[(i + 1) % len(poly)])
                                                                             for i in range(len(poly))), 2)})
                            report["loop_m"] += length
                            report["loop_area_m2"] += area
                    outlets.append({"circuit": cid, "kind": kind, "label": label})
                # The collector bar under the manifold joins its outlets (side by side) and its feed.
                span = (len(group) - 1) / 2 * HOME_RUN_GAP
                for system_key, off in (("supply", 0.0), ("return", RETURN_OFFSET)):
                    if span > 0:
                        result[system_key].append(((mx + off - span, my + off - span, z), (mx + off + span, my + off + span, z), main_dn))
                result["manifolds"].append({"id": mid, "x": mx, "y": my, "z": floor, "auto": auto, "outlets": outlets,
                                            "underfloor": system == "underfloor",
                                            "mixing": system == "underfloor" and src.params.get("point_type") != "heat_pump"})
                report["circuits"] += len(outlets)
            # Mains: source (or its riser on this storey) → each manifold.
            if feeds:
                paths, loads, parent = _grow(grid, root_cell, feeds)
                for system_key, off in (("supply", 0.0), ("return", RETURN_OFFSET)):
                    result[system_key] += _segments(grid, paths, loads, parent, z, off, (main_dn, main_dn, main_dn))
                    for mid, mx, my, _a in mans:
                        if mid in feeds:
                            g = grid.point(feeds[mid])
                            if math.dist(g, (mx, my)) > 1e-6:
                                result[system_key].append(((g[0] + off, g[1] + off, z), (mx + off, my + off, z), main_dn))
                            # Up from the screed into the manifold cabinet.
                            result[system_key].append(((mx + off, my + off, z), (mx + off, my + off, floor + CONNECTION["manifold"]), main_dn))
        else:
            cell_of = {c[0]: grid.cell(*c[1]) for c in circuits}
            paths, loads, parent = _grow(grid, root_cell, cell_of)
            for system_key, off in (("supply", 0.0), ("return", RETURN_OFFSET)):
                # Two-pipe: Ø of a circuit on a branch to one emitter, the mains' Ø where it serves more.
                result[system_key] += _segments(grid, paths, loads, parent, z, off, (circuit_dn, main_dn, main_dn))
                for cid, xy, *_r in circuits:
                    g = grid.point(cell_of[cid])
                    if math.dist(g, xy) > 1e-6:
                        result[system_key].append(((g[0] + off, g[1] + off, z), (xy[0] + off, xy[1] + off, z), circuit_dn))
            report["circuits"] += len(circuits)
        # Up from the screed to each emitter's valves.
        for cid, xy, kind, label, poly in circuits:
            if xy is None:
                continue
            for system_key, off in (("supply", 0.0), ("return", RETURN_OFFSET)):
                d = shift.get(cid, 0.0) + off
                result[system_key].append(((xy[0] + d, xy[1] + d, z), (xy[0] + d, xy[1] + d, floor + CONNECTION[kind]), circuit_dn))
            result["emitters"].append({"id": cid, "kind": kind, "label": label, "floor": floor})
        # The source: down from its connection to the screed on its own storey, a riser to the others.
        for system_key, off in (("supply", 0.0), ("return", RETURN_OFFSET)):
            rc = grid.point(root_cell)
            if math.dist(rc, root) > 1e-6:
                result[system_key].append(((root[0] + off, root[1] + off, z), (rc[0] + off, rc[1] + off, z), main_dn))
            if floor == sfloor:
                top = sz + CONNECTION.get(src.params["point_type"], 0.5)
                result[system_key].append(((root[0] + off, root[1] + off, top), (root[0] + off, root[1] + off, z), main_dn))
            else:
                result[system_key].append(((root[0] + off, root[1] + off, sfloor + SCREED), (root[0] + off, root[1] + off, z), main_dn))
    for key in ("supply", "return"):
        report[f"{key}_m"] = round(sum(math.dist(a, b) for a, b, _d in result[key]), 2)
        for a, b, dn in result[key]:
            report["length_by_dn"][dn] = round(report["length_by_dn"].get(dn, 0.0) + math.dist(a, b), 2)
    report["loop_m"] = round(report["loop_m"], 2)
    if report["loop_m"]:
        report["length_by_dn"][circuit_dn] = round(report["length_by_dn"].get(circuit_dn, 0.0) + report["loop_m"], 2)
    report["loop_area_m2"] = round(report["loop_area_m2"], 2)
    return result


def _manifold_spot(doc, floor, x, y, rooms, into=0.15):
    """On the face of the wall nearest (x, y), on the side of a heated room (never inside the wall)."""
    best = None
    for w in doc.entities.values():
        if w.kind != "wall" or abs(float(w.params.get("z", 0.0)) - floor) > 0.05:
            continue
        p = w.params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-9:
            continue
        t = max(0.1, min(0.9, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / (L * L)))
        fx, fy = ax + (bx - ax) * t, ay + (by - ay) * t
        nx, ny = -(by - ay) / L, (bx - ax) / L
        off = float(p["thickness"]) / 2 + into
        for sgn in (1, -1):
            q = (fx + nx * off * sgn, fy + ny * off * sgn)
            if any(_inside(f.polygon, *q) for f in rooms):
                d = math.hypot(x - q[0], y - q[1])
                if best is None or d < best[0]:
                    best = (d, q)
    return best[1] if best else (x, y)


def _centroid(poly):
    return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def _entry_point(poly, toward):
    """Inside the room, LOOP_INSET from the wall, at the point nearest ``toward`` (the manifold)."""
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    x = min(max(toward[0], min(xs) + LOOP_INSET), max(xs) - LOOP_INSET)
    y = min(max(toward[1], min(ys) + LOOP_INSET), max(ys) - LOOP_INSET)
    return (round(x, 3), round(y, 3))


_CACHE = {"key": None, "value": None}


def route_heating_cached(doc):
    items = []
    for e in doc.entities.values():
        if e.kind in ("heating_point", "wall", "window"):
            items.append((e.kind, e.id, e.parent_id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    key = (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
           tuple(sorted((k, str(v)) for k, v in getattr(doc, "room_data", {}).items())))
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_heating(doc)
    return _CACHE["value"]


# ----------------------------------------------------------------------------------------------- fittings / BOM
def fittings(route):
    """Counts of the parts the layout implies (each one a quote line): ``{code: (label, count, why)}``."""
    out = {}

    def add(code, label, n, why):
        if n:
            prev = out.get(code, (label, 0, why))
            out[code] = (label, prev[1] + n, why)
    for m in route["manifolds"]:
        n = len(m["outlets"])
        add(f"heating.manifold.{n}", f"Συλλέκτης θέρμανσης {n} κυκλωμάτων (προσαγωγή + επιστροφή)", 1, "ένας ανά όροφο / ομάδα κυκλωμάτων")
        add("heating.fitting.flow_meter" if m["underfloor"] else "heating.fitting.supply_valve",
            "Υδρονομέας (ρυθμιστής παροχής) στην προσαγωγή" if m["underfloor"] else "Διακόπτης προσαγωγής κυκλώματος",
            n, "ένας ανά κύκλωμα του συλλέκτη")
        add("heating.fitting.return_valve", "Βάνα επιστροφής κυκλώματος (με θέση για θερμοηλεκτρική κεφαλή)", n,
            "μία ανά κύκλωμα του συλλέκτη")
        add("heating.fitting.ball_valve", "Σφαιρική βάνα στην είσοδο του συλλέκτη", 2, "προσαγωγή και επιστροφή")
        add("heating.fitting.air_vent", "Αυτόματο εξαεριστικό", 2, "στα άκρα των δύο σωλήνων του συλλέκτη")
        add("heating.fitting.drain_cock", "Κρουνός εκκένωσης", 2, "στα άκρα των δύο σωλήνων του συλλέκτη")
        add("heating.manifold.cabinet", "Ερμάριο συλλέκτη (χωνευτό)", 1, "ένα ανά συλλέκτη")
        if m["mixing"]:
            add("heating.fitting.mixing_group", "Ομάδα ανάμιξης (κυκλοφορητής + τρίοδη) ενδοδαπέδιας", 1,
                "ενδοδαπέδια με λέβητα: χαμηλότερη θερμοκρασία νερού — επιλογή από μηχανολόγο")
    for e in route["emitters"]:
        if e["kind"] == "radiator":
            add("heating.fitting.radiator_valve", "Θερμοστατικός διακόπτης σώματος (προσαγωγή)", 1, "ένας ανά σώμα")
            add("heating.fitting.lockshield", "Διακόπτης επιστροφής σώματος (ταπώ)", 1, "ένας ανά σώμα")
            add("heating.fitting.radiator_vent", "Εξαεριστικό σώματος", 1, "ένα ανά σώμα")
        elif e["kind"] == "fan_coil":
            add("heating.fitting.fan_coil_valves", "Σετ βανών fan coil (προσαγωγή + επιστροφή)", 1, "ένα ανά fan coil")
    if route["loops"]:
        rooms = len(route["loops"])
        out["heating.underfloor.board"] = ("Μονωτική πλάκα συστήματος ενδοδαπέδιας (m²)", round(route["report"]["loop_area_m2"], 2),
                                           f"εμβαδό {rooms} χώρων με βρόχο")
        out["heating.underfloor.edge_strip"] = ("Περιμετρική ταινία διαστολής (m)",
                                                round(sum(l["perimeter_m"] for l in route["loops"]), 2), "περίμετρος των χώρων με βρόχο")
    return out


# ----------------------------------------------------------------------------------------------- drawing
# Plan size (length along the wall, depth) and height of each point (m) — drawing / 3D only, never sizing.
BODY = {"radiator": (0.80, 0.10, 0.60, 0.15), "fan_coil": (1.00, 0.22, 0.60, 0.10), "boiler": (0.45, 0.35, 0.75, 1.00),
        "heat_pump": (0.95, 0.40, 0.75, 0.00), "heat_source": (0.50, 0.40, 0.80, 0.30), "manifold": (0.40, 0.10, 0.45, 0.45),
        "thermostat": (0.08, 0.03, 0.08, 1.50)}


def footprint(params):
    """Plan rectangle of the point, turned by its ``rotation`` (degrees)."""
    t = params["point_type"]
    L, D, _h, _z0 = BODY[t]
    L = float(params.get("length", L)) if t in EMITTERS else L
    x, y = float(params["x"]), float(params["y"])
    r = math.radians(float(params.get("rotation", 0.0)))
    c, s = math.cos(r), math.sin(r)
    return [(x + u * c - v * s, y + u * s + v * c) for u, v in ((-L / 2, -D / 2), (L / 2, -D / 2), (L / 2, D / 2), (-L / 2, D / 2))]


def point_mesh(params):
    """Body of the point as a box (radiator panel, boiler, manifold cabinet …): ``(verts, tris)``."""
    t = params["point_type"]
    _L, _D, h, z0 = BODY[t]
    z = float(params["z"]) + z0
    ring = footprint(params)
    verts = [(x, y, z) for x, y in ring] + [(x, y, z + h) for x, y in ring]
    tris = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7)]
    for i in range(4):
        j = (i + 1) % 4
        tris += [(i, j, 4 + j), (i, 4 + j, 4 + i)]
    return verts, tris


def manifold_parts(m, supply_dn=20):
    """3D parts of a manifold: the two bars, a flow meter / valve per outlet on the supply, a valve per outlet on
    the return, ball valves on the feed.  ``[(verts, tris)]``."""
    from archforge.mep.plumbing import pipe_mesh
    n = len(m["outlets"])
    w = 0.15 + OUTLET_PITCH * n
    x, y, z = m["x"], m["y"], m["z"] + CONNECTION["manifold"]
    parts = []
    for zz in (z + 0.10, z):                           # supply above, return below
        parts.append(pipe_mesh((x - w / 2, y, zz), (x + w / 2, y, zz), max(supply_dn, 26) + 6, sides=10))
        parts.append(pipe_mesh((x - w / 2 - 0.06, y, zz), (x - w / 2, y, zz), 40, sides=6))     # ball valve
    for k in range(n):
        px = x - w / 2 + 0.075 + OUTLET_PITCH * k
        parts.append(pipe_mesh((px, y, z + 0.10), (px, y, z + 0.20), 26 if m["underfloor"] else 18, sides=8))  # flow meter
        parts.append(pipe_mesh((px, y, z), (px, y, z - 0.06), 22, sides=6))                     # return valve
    return parts


def against_wall(doc, floor, x, y, depth):
    """A click near a wall puts the radiator / fan coil / manifold against its face, turned along it:
    ``(x, y, rotation_deg)``; far from any wall the click stays as it is."""
    best = None
    for w in doc.entities.values():
        if w.kind != "wall" or abs(float(w.params.get("z", 0.0)) - floor) > 0.05:
            continue
        p = w.params
        fx, fy = _wall_foot(p, x, y)
        d = math.hypot(x - fx, y - fy)
        if d < 0.6 and (best is None or d < best[0]):
            best = (d, p, fx, fy)
    if best is None:
        return x, y, 0.0
    d, p, fx, fy = best
    ang = math.degrees(math.atan2(float(p["y2"]) - float(p["y1"]), float(p["x2"]) - float(p["x1"])))
    if d < 1e-6:
        return x, y, ang
    off = float(p["thickness"]) / 2 + depth / 2 + 0.03
    return fx + (x - fx) / d * off, fy + (y - fy) / d * off, ang
