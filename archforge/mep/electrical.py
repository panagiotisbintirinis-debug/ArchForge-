"""Electrical layout: points in the Document, circuits and cable runs derived.

The user places the panel, lights, switches, sockets and dedicated appliance
outlets.  Circuits are grouped and routed automatically from those points
using common Greek practice for dwellings (ΕΛΟΤ HD 384 conventions as
commonly applied); every rule is written here so an electrical engineer can
check it:

* Lighting: 10 A breaker, 1.5 mm² cable, at most 10 points per circuit,
  grouped by room.  A switch controls the lights of its room.
* General sockets: 16 A breaker, 2.5 mm², at most 6 sockets per circuit,
  grouped by room; kitchen sockets never share a circuit with other rooms.
* Dedicated lines (one appliance each): cooker/oven 32 A 6 mm², water heater
  20 A 2.5 mm², air-conditioner, washing machine, dishwasher 16 A 2.5 mm².
* A shared circuit whose design load exceeds 80 % of its breaker, or a
  dedicated line whose appliance exceeds its breaker, is flagged.
* Routes: lights and switches via the ceiling, sockets along the walls at
  30 cm, using the same cheapest-path router as the plumbing.
* All circuits sit behind a 30 mA RCD (noted, not modelled).

Status: pre-design layout for review by an electrical engineer; it is not
a load study, voltage-drop or selectivity calculation.
"""
from __future__ import annotations

import math

from archforge.mep.plumbing import CELL, _Grid, _grow, _levels

PROVENANCE = ("Προμελέτη κυκλωμάτων με κανόνες ΕΛΟΤ HD 384 όπως εφαρμόζονται συνήθως σε κατοικίες "
              "(φωτισμός 10A/1,5mm² ≤10 σημεία, πρίζες 16A/2,5mm² ≤6, αποκλειστικές γραμμές) — "
              "όχι μελέτη φορτίων/πτώσης τάσης, προς έλεγχο από ηλεκτρολόγο μηχανικό")
VOLTAGE = 230.0

# type: label, group, default W, mounting height (m), plan letter
POINT_TYPES = {
    "panel": ("Ηλεκτρικός πίνακας", "panel", 0, 1.60, "ΠΙ"),
    "light": ("Φωτιστικό οροφής", "lighting", 60, None, "Φ"),
    "wall_light": ("Απλίκα", "lighting", 40, 2.00, "Α"),
    "switch": ("Διακόπτης", "switch", 0, 1.10, "Δ"),
    "socket": ("Πρίζα σούκο", "sockets", 200, 0.30, "Ρ"),
    "kitchen_socket": ("Πρίζα πάγκου κουζίνας", "kitchen_sockets", 500, 1.10, "ΡΚ"),
    "cooker": ("Κουζίνα/φούρνος", "cooker", 6000, 0.30, "ΚΦ"),
    "water_heater": ("Θερμοσίφωνας", "water_heater", 4000, 1.80, "ΘΣ"),
    "air_conditioner": ("Κλιματιστικό", "air_conditioner", 2500, 2.20, "ΚΛ"),
    "washing_machine": ("Πλυντήριο ρούχων", "washing_machine", 2300, 0.60, "ΠΡ"),
    "dishwasher": ("Πλυντήριο πιάτων", "dishwasher", 2000, 0.40, "ΠΠ"),
}
# group: label, breaker A, cable mm², max points per circuit (None = dedicated)
CIRCUIT_RULES = {
    "lighting": ("Φωτισμός", 10, 1.5, 10),
    "sockets": ("Ρευματοδότες", 16, 2.5, 6),
    "kitchen_sockets": ("Ρευματοδότες κουζίνας", 16, 2.5, 4),
    "cooker": ("Κουζίνα", 32, 6.0, 1),
    "water_heater": ("Θερμοσίφωνας", 20, 2.5, 1),
    "air_conditioner": ("Κλιματιστικό", 16, 2.5, 1),
    "washing_machine": ("Πλυντήριο ρούχων", 16, 2.5, 1),
    "dishwasher": ("Πλυντήριο πιάτων", 16, 2.5, 1),
}
GROUP_ORDER = tuple(CIRCUIT_RULES)


def electrical_points(doc):
    return [e for e in doc.entities.values() if e.kind == "electrical_point"]


def _floor_of(doc, z):
    below = [lz for lz in _levels(doc) if lz <= z + 1e-4]
    return below[-1] if below else _levels(doc)[0]


def _ceiling(doc, floor):
    above = [lz for lz in _levels(doc) if lz > floor + 1e-4]
    return (above[0] if above else floor + 3.0) - 0.20     # under the slab


def mount_z(doc, params):
    floor = _floor_of(doc, float(params["z"]))
    h = POINT_TYPES[params["point_type"]][3]
    return _ceiling(doc, floor) if h is None else floor + h


def _room_of(doc, x, y, floor):
    try:
        faces = doc.active_room_faces(z=floor)
    except Exception:
        return None
    for k, face in enumerate(faces):
        poly = face.polygon
        inside = False
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
        if inside:
            return doc.room_metadata(face.signature).get("name") or f"Room {k + 1}"
    return None


def design_circuits(doc):
    """Group points into circuits: ``{"circuits": [...], "switch_links": [...], "report": {...}}``."""
    points = electrical_points(doc)
    panel = next((e for e in points if e.params["point_type"] == "panel"), None)
    out = {"circuits": [], "switch_links": [], "report": {"unassigned": [], "warnings": [], "provenance": PROVENANCE}}
    loads = [e for e in points if POINT_TYPES[e.params["point_type"]][1] in CIRCUIT_RULES]
    if panel is None:
        out["report"]["unassigned"] = [e.id for e in loads]
        if loads:
            out["report"]["warnings"].append("Δεν υπάρχει ηλεκτρικός πίνακας: τα κυκλώματα δεν σχηματίζονται")
        return out
    by_group = {}
    for e in loads:
        group = POINT_TYPES[e.params["point_type"]][1]
        floor = _floor_of(doc, float(e.params["z"]))
        room = _room_of(doc, float(e.params["x"]), float(e.params["y"]), floor) or "—"
        by_group.setdefault(group, []).append((room, floor, e))
    number = 0
    for group in GROUP_ORDER:
        members = by_group.get(group, [])
        if not members:
            continue
        label, breaker, cable, limit = CIRCUIT_RULES[group]
        # Same room (and storey) first, then by distance from the panel.
        px, py = float(panel.params["x"]), float(panel.params["y"])
        members.sort(key=lambda m: (m[1], m[0], math.hypot(float(m[2].params["x"]) - px, float(m[2].params["y"]) - py)))
        chunks, current, current_room = [], [], None
        for room, floor, e in members:
            # Rooms are not mixed in lighting/socket circuits unless a room is small.
            if current and (len(current) >= limit or (limit > 1 and (room, floor) != current_room and len(current) >= limit // 2)):
                chunks.append(current)
                current = []
            current.append(e)
            current_room = (room, floor)
        if current:
            chunks.append(current)
        for chunk in chunks:
            number += 1
            watts = sum(float(e.params.get("power_w", POINT_TYPES[e.params["point_type"]][2])) for e in chunk)
            amps = watts / VOLTAGE
            dedicated = limit == 1
            # Shared circuits keep 20 % margin; a dedicated line must carry its appliance.
            ok = amps <= (breaker if dedicated else 0.8 * breaker)
            circuit = {"id": f"Κ{number}", "group": group, "label": label, "breaker_a": breaker, "cable_mm2": cable,
                       "points": [e.id for e in chunk], "load_w": round(watts), "current_a": round(amps, 1), "ok": ok}
            if not ok:
                fix = "μεγαλύτερη ασφάλεια/διατομή" if dedicated else "χωρίστε το κύκλωμα"
                limit_txt = f"{breaker} A" if dedicated else f"80% της ασφάλειας {breaker} A"
                out["report"]["warnings"].append(f"{circuit['id']} {label}: {amps:.1f} A > {limit_txt} — {fix}")
            out["circuits"].append(circuit)
    # Switches control the lights of their room (same storey).
    lights = [(e, _room_of(doc, float(e.params["x"]), float(e.params["y"]), _floor_of(doc, float(e.params["z"]))),
               _floor_of(doc, float(e.params["z"]))) for e in points if POINT_TYPES[e.params["point_type"]][1] == "lighting"]
    for sw in (e for e in points if e.params["point_type"] == "switch"):
        floor = _floor_of(doc, float(sw.params["z"]))
        room = _room_of(doc, float(sw.params["x"]), float(sw.params["y"]), floor)
        controlled = [l.id for l, lroom, lfloor in lights if lfloor == floor and lroom == room and room is not None]
        if not controlled:
            near = sorted((math.hypot(float(l.params["x"]) - float(sw.params["x"]), float(l.params["y"]) - float(sw.params["y"])), l.id)
                          for l, _r, lf in lights if lf == floor)
            controlled = [near[0][1]] if near else []
        out["switch_links"].append({"switch": sw.id, "lights": controlled})
    return out


def route_cables(doc):
    """Circuits plus cable runs ``(a, b, group)`` from the panel to each point."""
    design = design_circuits(doc)
    runs = []
    points = {e.id: e for e in electrical_points(doc)}
    panel = next((e for e in points.values() if e.params["point_type"] == "panel"), None)
    if panel is None:
        return {**design, "runs": runs}
    for circuit in design["circuits"]:
        members = [points[i] for i in circuit["points"]]
        floor = _floor_of(doc, float(members[0].params["z"]))
        overhead = circuit["group"] == "lighting"
        z = _ceiling(doc, floor) if overhead else floor + 0.30
        pts = [(float(e.params["x"]), float(e.params["y"])) for e in members + [panel]]
        grid = _Grid(doc, floor, pts)
        source = grid.cell(float(panel.params["x"]), float(panel.params["y"]))
        targets = {e.id: grid.cell(float(e.params["x"]), float(e.params["y"])) for e in members}
        paths, _loads, parent = _grow(grid, source, targets)
        seen = set()
        for path in paths.values():
            c = path[0]
            while parent.get(c) is not None:
                p = parent[c]
                edge = frozenset((c, p))
                if edge in seen:
                    break
                seen.add(edge)
                a, b = grid.point(c), grid.point(p)
                runs.append(((a[0], a[1], z), (b[0], b[1], z), circuit["group"], circuit["id"]))
                c = p
        # Panel riser to the run level and drops to each point's mounting height.
        pp = grid.point(source)
        runs.append(((pp[0], pp[1], mount_z(doc, panel.params)), (pp[0], pp[1], z), circuit["group"], circuit["id"]))
        for e in members:
            c = grid.point(grid.cell(float(e.params["x"]), float(e.params["y"])))
            runs.append(((c[0], c[1], z), (c[0], c[1], mount_z(doc, e.params)), circuit["group"], circuit["id"]))
    # Switch legs: switch to its lights through the ceiling.
    for link in design["switch_links"]:
        sw = points[link["switch"]]
        floor = _floor_of(doc, float(sw.params["z"]))
        zc = _ceiling(doc, floor)
        sx, sy = float(sw.params["x"]), float(sw.params["y"])
        runs.append(((sx, sy, mount_z(doc, sw.params)), (sx, sy, zc), "switch", ""))
        for lid in link["lights"]:
            lx, ly = float(points[lid].params["x"]), float(points[lid].params["y"])
            runs.append(((sx, sy, zc), (lx, sy, zc), "switch", ""))
            runs.append(((lx, sy, zc), (lx, ly, zc), "switch", ""))
    runs = [r for r in runs if math.dist(r[0], r[1]) > 1e-6]
    total = sum(math.dist(a, b) for a, b, _g, _c in runs)
    design["report"]["cable_m"] = round(total, 1)
    return {**design, "runs": runs}


_CACHE = {"key": None, "value": None}


def route_cables_cached(doc):
    items = []
    for e in doc.entities.values():
        if e.kind == "electrical_point":
            items.append(("e", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
        elif e.kind == "wall":
            items.append(("w", e.id, tuple(round(float(e.params[k]), 6) for k in ("x1", "y1", "x2", "y2", "z", "thickness"))))
    key = (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
           tuple(sorted((k, str(v)) for k, v in doc.room_data.items())) if hasattr(doc, "room_data") else ())
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_cables(doc)
    return _CACHE["value"]


def point_marker_mesh(doc, params):
    """Small box at the point's mounting position (selectable in 3D)."""
    x, y = float(params["x"]), float(params["y"])
    z = mount_z(doc, params)
    s = 0.12 if params["point_type"] == "panel" else 0.06
    h = 0.4 if params["point_type"] == "panel" else 0.06
    c = [(x + dx, y + dy, z + dz) for dx in (-s, s) for dy in (-s / 2, s / 2) for dz in (-h / 2, h / 2)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    return c, tris


CABLE_COLORS = {"lighting": "#e0b400", "sockets": "#e07a00", "kitchen_sockets": "#c2410c", "switch": "#9a8f00",
                "cooker": "#7b2fbf", "water_heater": "#7b2fbf", "air_conditioner": "#7b2fbf",
                "washing_machine": "#7b2fbf", "dishwasher": "#7b2fbf"}
