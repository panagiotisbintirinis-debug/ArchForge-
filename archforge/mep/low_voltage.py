"""Ασθενή ρεύματα (owner 17/10): data network, TV/SAT and the KNX bus, routed and drawn in 2D and 3D.

* Points: ``electrical_point`` with a type of ``electrical.LOW_VOLTAGE_TYPES`` (rack, RJ45 outlet,
  Wi-Fi access point, TV/SAT outlet) — the same entity, never part of a power circuit.
* Network and TV: a **star** from the rack — one cable per outlet (home run), all of a floor's
  cables in one low-voltage conduit tree chased into the walls like the power conduits but on
  their own run ``LV_RUN_RISE`` above, so the two systems are drawn and counted apart.  A ceiling
  access point is fed like a ceiling light (box on the nearest wall, then the ceiling).
  Other floors: a vertical riser at the rack.
* KNX bus (when the client chose KNX): the bus chain of ``mep.knx`` drawn as its own system.

Cable category and the separation from power cables are the study's (rules ``lv.*``).
"""
from __future__ import annotations

import math

from archforge.core.provenance import DESIGN_DEFAULT, ENGINEER_REVIEW, Rule, register
from archforge.mep.electrical import (LOW_VOLTAGE_TYPES, POINT_TYPES, WALL_RUN_Z, _ceiling, _ceiling_fed, _floor_of,
                                      mount_z)
from archforge.mep.plumbing import _Grid, _grow

LV_RUN_RISE = 0.10          # owner 23/10: low-voltage row above power; DESIGN_DEFAULT, not code clearance
LV_RUN_DROP = -LV_RUN_RISE  # compatibility for integrations using WALL_RUN_Z - LV_RUN_DROP
SYSTEM_OF = {"data_outlet": "network", "wifi_ap": "network", "tv_outlet": "tv"}
SYSTEM_LABELS = {"network": "Δίκτυο δεδομένων", "tv": "TV / SAT", "knx": "Bus KNX"}

register(
    Rule("lv.star", "Δίκτυο δεδομένων και TV σε αστέρα από το rack: ένα καλώδιο ανά πρίζα / σημείο πρόσβασης, κοινή "
         "σωλήνωση ασθενών ανά όροφο, κατακόρυφη στήλη στο rack για άλλους ορόφους", DESIGN_DEFAULT,
         note="Τοπολογία του προγράμματος· ο μελετητής μπορεί να ορίσει άλλη (π.χ. τοπικούς κατανεμητές)."),
    Rule("lv.separation", "Ασθενή σε δική τους σωλήνωση, 10 cm πάνω από τη γραμμή όδευσης της ισχύος", DESIGN_DEFAULT,
         note="Απόσταση/διαχωρισμός από τα καλώδια ισχύος κατά το πρότυπο καλωδίωσης (π.χ. σειρά EN 50174) — δεν "
              "διασταυρώθηκε, προς έλεγχο από τον μελετητή"),
    Rule("lv.cable", "Κατηγορία καλωδίου δικτύου (Cat 6 / 6A / 7 …) και τύπος καλωδίου TV", ENGINEER_REVIEW,
         note="Ρύθμιση στο rack· χωρίς τιμή μετριούνται μόνο μέτρα, όχι κατηγορία"),
    Rule("lv.heights", "Ύψη: πρίζες δικτύου/TV 0,30 m, rack 1,60 m, σημείο πρόσβασης στην οροφή", DESIGN_DEFAULT,
         note="Ίδια με τις προεπιλογές πριζών/πίνακα του προγράμματος· αλλάζουν ανά σημείο"),
)


def lv_points(doc):
    return [e for e in doc.entities.values() if e.kind == "electrical_point" and e.params.get("point_type") in LOW_VOLTAGE_TYPES]


def route_low_voltage(doc):
    """{"rack", "outlets": [...], "runs": [(a, b, system, outlet id)], "boxes", "totals", "knx", "warnings"}."""
    from archforge.mep.electrical_routes import mode_of, run_z, target_cell, device_legs
    pts = lv_points(doc)
    rack = next((e for e in pts if e.params["point_type"] == "network_rack"), None)
    outlets = [e for e in pts if e.params["point_type"] in SYSTEM_OF]
    out = {"rack": rack.id if rack else None, "outlets": [], "runs": [], "boxes": [], "warnings": [],
           "cable": str(rack.params.get("network_cable", "")) if rack else "", "totals": {}}
    if outlets and rack is None:
        out["warnings"].append("Δεν υπάρχει rack δικτύου: βάλτε «Rack δικτύου / κατανεμητής ασθενών» για να χαραχτούν οι γραμμές")
    if rack is not None and outlets:
        rx, ry = float(rack.params["x"]), float(rack.params["y"])
        rack_floor = _floor_of(doc, float(rack.params["z"]))
        by_floor = {}
        for e in outlets:
            by_floor.setdefault((_floor_of(doc, float(e.params["z"])), mode_of(doc, e)), []).append(e)
        for (floor, mode), members in sorted(by_floor.items()):
            z = run_z(doc, floor, mode) + LV_RUN_RISE
            grid = _Grid(doc, floor, [(float(e.params["x"]), float(e.params["y"])) for e in members] + [(rx, ry)])
            grid.mode = "wall" if mode == "wall" else "floor"
            source = grid.cell(rx, ry)
            targets = {e.id: target_cell(grid, e, mode) for e in members}
            paths, _loads, parent = _grow(grid, source, targets)
            seen = set()
            sp = grid.point(source)
            # Riser: from the rack to this floor's run (own floor: rack box up/down to the run).
            rack_z = mount_z(doc, rack.params) if floor == rack_floor else run_z(doc, rack_floor, mode) + LV_RUN_RISE
            riser = abs(z - rack_z)
            systems = {SYSTEM_OF[e.params["point_type"]] for e in members}
            for system in sorted(systems):
                out["runs"].append(((sp[0], sp[1], rack_z), (sp[0], sp[1], z), system, ""))
            by_id = {e.id: e for e in members}
            for tid, path in paths.items():
                e = by_id[tid]
                system = SYSTEM_OF[e.params["point_type"]]
                c, horizontal = path[0], 0.0
                while parent.get(c) is not None:
                    p_ = parent[c]
                    a, b = grid.point(c), grid.point(p_)
                    horizontal += math.dist(a, b)
                    edge = (frozenset((c, p_)), system)
                    if edge not in seen:
                        seen.add(edge)
                        out["runs"].append(((a[0], a[1], z), (b[0], b[1], z), system, tid))
                    c = p_
                bx, by = grid.point(targets[tid])
                legs, box = device_legs(doc, e, mode, (bx, by), z)
                out["boxes"].append((*box[:3], "lv", tid))
                out["runs"] += [(a, b, system, tid) for a, b in legs]
                drop = sum(math.dist(a, b) for a, b in legs)
                out["outlets"].append({"id": tid, "type": e.params["point_type"], "label": POINT_TYPES[e.params["point_type"]][0],
                                       "system": system, "floor": floor, "routing": mode, "x": float(e.params["x"]), "y": float(e.params["y"]),
                                       "cable_m": round(horizontal + drop + riser, 2)})
    out["runs"] = [r for r in out["runs"] if math.dist(r[0], r[1]) > 1e-6]
    for system in ("network", "tv"):
        cables = [o["cable_m"] for o in out["outlets"] if o["system"] == system]
        conduit = sum(math.dist(a, b) for a, b, s, _t in out["runs"] if s == system)
        if cables:
            out["totals"][system] = {"points": len(cables), "cable_m": round(sum(cables), 1), "conduit_m": round(conduit, 1)}
    out["outlets"].sort(key=lambda o: (o["floor"], o["system"], o["label"], o["id"]))
    out["knx"] = _knx(doc)
    for a, b in out["knx"].get("bus_segments", []):
        out["runs"].append((a, b, "knx", ""))
    return out


def _knx(doc):
    from archforge.mep.electrical import electrical_points, route_cables_cached
    from archforge.mep.knx import control_system, knx_summary
    if control_system(doc) != "knx":
        return {}
    points = {e.id: e for e in electrical_points(doc)}
    return knx_summary(doc, route_cables_cached(doc), points)


_CACHE = {"key": None, "value": None}


def route_low_voltage_cached(doc):
    items = []
    for e in doc.entities.values():
        if e.kind == "electrical_point":
            items.append(("e", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
        elif e.kind == "wall":
            items.append(("w", e.id, tuple(round(float(e.params[k]), 6) for k in ("x1", "y1", "x2", "y2", "z", "thickness"))))
        elif e.kind == "drywall_ceiling":
            items.append(("d", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    key = (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())))
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_low_voltage(doc)
    return _CACHE["value"]


def lv_material_rows(doc, meta):
    """Quantities for the material list (no prices): cable metres per system, conduit, outlets, rack."""
    r = route_low_voltage_cached(doc)
    rows = []
    cat = r["cable"] or "κατηγορία από τη μελέτη"
    for system, label in (("network", f"Καλώδιο δικτύου ({cat}) — ένα ανά πρίζα / σημείο πρόσβασης"),
                          ("tv", "Καλώδιο TV / SAT — ένα ανά πρίζα")):
        t = r["totals"].get(system)
        if t:
            rows.append((label, "m", t["cable_m"], meta(f"lv.cable.{system}", "Μέτρα από το rack ως κάθε σημείο, όπως χαράχτηκαν.",
                                                         "ENGINEER_REVIEW")))
            rows.append((f"Σωλήνας ασθενών — {SYSTEM_LABELS[system]}", "m", t["conduit_m"],
                         meta(f"lv.conduit.{system}", "Η σωλήνωση ασθενών, χωριστά από την ισχυρή.")))
    counts = {}
    for e in lv_points(doc):
        counts[e.params["point_type"]] = counts.get(e.params["point_type"], 0) + 1
    for t, n in sorted(counts.items()):
        rows.append((POINT_TYPES[t][0] + " και τοποθέτηση", "τεμ.", n, meta(f"lv.point.{t}", "Σημείο που υπάρχει στο σχέδιο.")))
    return rows
