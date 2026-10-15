"""Electrical board analysis derived from the routed circuits (``route_cables``).

Three things the owner asked for (2026-10-14/15), each with its rule written
here so an electrical engineer can check it:

1. **Conductors per circuit** — phase L, neutral N, protective earth PE and the
   switch returns, with the cross-section of each (0.75 … 10 mm² copper).
2. **Metres per wall and per cross-section** (prefabricated houses: which
   cables pass through which wall, how many metres) from the conduit runs.
3. **Board analysis** — breaker per circuit, main switch, 30 mA RCDs, phase
   balance on a three-phase supply, installed power, demand (diversity) and
   the supply it needs, voltage drop to the farthest point of each circuit.

Settings live on the panel point (shared commands, undo, save/load):
``supply`` ('auto' or ΔΕΔΔΗΕ supply '1'…'5'), ``demand_factor`` (0 = method
below, otherwise the factor the engineer sets) and ``waste_pct`` (purchase
allowance on cable metres, a user setting).

Status: pre-design for review by an electrical engineer — not a full
study (no short-circuit/selectivity/earthing-resistance calculation).
"""
from __future__ import annotations

import heapq
import math

from archforge.mep.electrical import (VOLTAGE, WALL_NEAR, WALL_RUN_Z, _ceiling, _floor_of,
                                      electrical_points, mount_z, route_cables_cached)
from archforge.mep.plumbing import CELL

PROVENANCE = ("Ελάχιστες διατομές: ΕΛΟΤ HD 60364-5-52 (πρώην HD 384.5.52) Πίν. 52.2 — 1,5 mm² Cu για κυκλώματα "
              "ισχύος/φωτισμού, 0,75 mm² μόνο εύκαμπτα καλώδια συσκευών/φωτιστικών· "
              "Iz: HD 60364-5-52 Πίν. B.52.4, μέθοδος B1 (αγωγοί σε σωλήνα σε τοίχο), PVC 70 °C, 30 °C· "
              "χρώματα HD 308· πτώση τάσης: HD 60364-5-52 Παράρτ. G (3 % φωτισμός, 5 % λοιπά, ρ = 0,0225 Ω·mm²/m)· "
              "30 mA: HD 60364-4-41 §411.3.3. Προμελέτη, προς έλεγχο από ηλεκτρολόγο μηχανικό")

# Cross-sections (mm² Cu): use, Iz for 2 / 3 loaded conductors (A), method B1, PVC.
SECTIONS = {
    0.75: ("Εύκαμπτο κορδόνι φωτιστικού/συσκευής (όχι σταθερή εγκατάσταση)", None, None),
    1.5: ("Φωτισμός, επιστροφές διακοπτών", 17.5, 15.5),
    2.5: ("Ρευματοδότες, αποκλειστικές γραμμές έως 20 A", 24.0, 21.0),
    4.0: ("Γραμμές έως 25 A", 32.0, 28.0),
    6.0: ("Κουζίνα 32 A", 41.0, 36.0),
    10.0: ("Γραμμή τροφοδοσίας πίνακα έως 50 A", 57.0, 50.0),
    16.0: ("Γραμμή τροφοδοσίας πίνακα έως 63 A", 76.0, 68.0),
}
FIXED_MIN_MM2 = 1.5
COLORS = {"L": "καφέ", "N": "μπλε", "PE": "πρασινοκίτρινο", "R": "μαύρο (επιστροφή)"}
CONDUCTOR_LABELS = {"L": "Φάση", "N": "Ουδέτερος", "PE": "Γείωση", "R": "Επιστροφή"}

# ΔΕΔΔΗΕ standard low-voltage supplies for dwellings: number -> (label, phases, kVA, fuse A).
SUPPLIES = {
    "1": ("Παροχή Νο 1 — μονοφασική 8 kVA", 1, 8.0, 40),
    "2": ("Παροχή Νο 2 — μονοφασική 12 kVA", 1, 12.0, 63),
    "3": ("Παροχή Νο 3 — τριφασική 15 kVA", 3, 15.0, 25),
    "4": ("Παροχή Νο 4 — τριφασική 25 kVA", 3, 25.0, 40),
    "5": ("Παροχή Νο 5 — τριφασική 35 kVA", 3, 35.0, 50),
}
SUPPLY_PROVENANCE = "Τυποποιημένες παροχές ΔΕΔΔΗΕ Νο 1–5 — επιβεβαιώστε με τον ισχύοντα πίνακα του ΔΕΔΔΗΕ"
DEMAND_PROVENANCE = ("Ταυτοχρονισμός: IET On-Site Guide (BS 7671) Πίν. A1 για κατοικίες — βρετανική μέθοδος, ενδεικτική· "
                     "ο ηλεκτρολόγος μπορεί να ορίσει δικό του συντελεστή στον πίνακα")
DROP_LIMITS = {"lighting": 3.0}            # % (HD 60364-5-52 Annex G, supply from the public LV network)
DROP_OTHER = 5.0
RHO = 0.0225                               # Ω·mm²/m, copper at operating temperature (Annex G)
DEFAULT_WASTE_PCT = 10.0


def settings(doc):
    """Board settings from the panel point (defaults when absent)."""
    panel = next((e for e in electrical_points(doc) if e.params["point_type"] == "panel"), None)
    p = panel.params if panel is not None else {}
    return {"panel": panel.id if panel is not None else None, "supply": str(p.get("supply", "auto")),
            "demand_factor": float(p.get("demand_factor", 0.0)), "waste_pct": float(p.get("waste_pct", DEFAULT_WASTE_PCT))}


def conductors(circuit):
    """Conductors of a circuit's line: [(code, label, colour, mm²)] — L, N, PE at the circuit section."""
    s = float(circuit["cable_mm2"])
    return [(c, CONDUCTOR_LABELS[c], COLORS[c], s) for c in ("L", "N", "PE")]


SWITCH_LEG = [("L", CONDUCTOR_LABELS["L"], COLORS["L"], 1.5), ("R", CONDUCTOR_LABELS["R"], COLORS["R"], 1.5)]


# --- where each run lies --------------------------------------------------------------------------------------

def _walls_by_floor(doc):
    out = {}
    for e in doc.entities.values():
        if e.kind == "wall":
            out.setdefault(round(float(e.params.get("z", 0.0)), 3), []).append(e)
    return out


def _dist_to_wall(w, x, y):
    p = w.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
    return math.hypot(x - (x1 + dx * t), y - (y1 + dy * t))


def _wall_at(walls, a, b, reach):
    """Wall whose body (plus ``reach`` from its face) contains the segment a-b in plan, or None."""
    best, best_d = None, math.inf
    for w in walls:
        tol = float(w.params["thickness"]) / 2 + reach
        da, db = _dist_to_wall(w, a[0], a[1]), _dist_to_wall(w, b[0], b[1])
        if da <= tol and db <= tol and max(da, db) < best_d:
            best, best_d = w, max(da, db)
    return best


def _facing(nx, ny):
    return ("Α", "ΒΑ", "Β", "ΒΔ", "Δ", "ΝΔ", "Ν", "ΝΑ")[int(round(math.degrees(math.atan2(ny, nx)) / 45.0)) % 8]


def wall_label(doc, w, number):
    """«Τ3 Κουζίνα | Σαλόνι · 4,00 m» or «Τ1 εξωτ. Ν · Σαλόνι · 8,00 m»."""
    from archforge.mep.electrical import _room_of
    p = w.params
    x1, y1, x2, y2, t = (float(p[k]) for k in ("x1", "y1", "x2", "y2", "thickness"))
    length = math.hypot(x2 - x1, y2 - y1)
    nx, ny = (-(y2 - y1) / length, (x2 - x1) / length) if length > 1e-9 else (0.0, 0.0)
    floor = float(p.get("z", 0.0))
    d = t / 2 + 0.15
    sides = [_room_of(doc, (x1 + x2) / 2 + s * nx * d, (y1 + y2) / 2 + s * ny * d, floor) for s in (1, -1)]
    named = [s for s in sides if s]
    if len(named) == 1:
        out = (nx, ny) if sides[0] is None else (-nx, -ny)
        where = f"εξωτ. {_facing(*out)} · {named[0]}"
    elif named:
        where = " | ".join(dict.fromkeys(named))
    else:
        where = "ελεύθερος"
    return f"Τ{number} {where} · {length:.2f} m".replace(f"{length:.2f}", f"{length:.2f}".replace(".", ","))


def _location(doc, walls, floor, a, b):
    """('wall', wall id) / ('ceiling', None) / ('floor', None) / ('free', None) for one run."""
    zc = _ceiling(doc, floor)
    horizontal = abs(a[2] - b[2]) < 1e-9
    if horizontal and (abs(a[2] - zc) < 1e-6 or a[2] > floor + WALL_RUN_Z + 1e-6):
        return ("ceiling", None)                     # under the slab or in a plasterboard ceiling
    if horizontal and a[2] < floor + 0.10:
        return ("floor", None)
    if not horizontal and max(a[2], b[2]) <= floor + 0.16 + 1e-9:
        return ("floor", None)                       # up from the screed into a floor box
    # Runs follow the router's wall band (2 cells); a device's drop sits on the face of the wall it is fed from.
    w = _wall_at(walls, a, b, 2 * CELL + 1e-6 if horizontal else WALL_NEAR)
    if w is not None:
        return ("wall", w.id)
    if not horizontal and min(a[2], b[2]) >= floor + WALL_RUN_Z - 1e-6:
        return ("ceiling", None)                     # through the slab to a ceiling light
    if not horizontal and min(a[2], b[2]) <= floor + 0.16:
        return ("floor", None)                       # rise from a floor box into an island/free-standing unit
    return ("free", None)


LOCATION_LABELS = {"ceiling": "Οροφή (μέσα/κάτω από την πλάκα)", "floor": "Δάπεδο (κονίαμα) και άνοδοι σε νησίδες",
                   "free": "Εκτός τοίχου (ελέγξτε τη διαδρομή)"}


# --- board analysis -------------------------------------------------------------------------------------------

def _demand(circuits, factor):
    """Diversified demand current (A) on a single-phase basis."""
    amps = lambda c: float(c["load_w"]) / VOLTAGE
    if factor > 0:
        return sum(amps(c) for c in circuits) * factor, f"συντελεστής {factor:.2f} (ορισμένος από τον χρήστη)"
    lighting = sum(amps(c) for c in circuits if c["group"] == "lighting") * 0.66
    sockets = sorted((float(c["breaker_a"]) for c in circuits if c["group"] in ("sockets", "kitchen_sockets")), reverse=True)
    socket_d = (sockets[0] + 0.4 * sum(sockets[1:])) if sockets else 0.0
    cooker = sum(min(amps(c), 10.0) + 0.3 * max(0.0, amps(c) - 10.0) for c in circuits if c["group"] == "cooker")
    heaters = sum(amps(c) for c in circuits if c["group"] == "water_heater")
    fixed = sum(amps(c) for c in circuits if c["group"] in ("air_conditioner", "washing_machine", "dishwasher"))
    fixed_d = min(fixed, 10.0) + 0.5 * max(0.0, fixed - 10.0)
    method = ("φωτισμός 66 % · πρίζες 100 % της ασφάλειας του μεγαλύτερου κυκλώματος + 40 % των άλλων "
              "(με την ασφάλεια, όχι με τα ονομαστικά W ανά πρίζα) · κουζίνα 10 A + 30 % του υπολοίπου · "
              "θερμοσίφωνες 100 % · σταθερές συσκευές 100 % ως 10 A + 50 % του υπολοίπου")
    return lighting + socket_d + cooker + heaters + fixed_d, method


def _farthest(runs, start, targets):
    """Longest shortest-path length (m) from ``start`` to any of ``targets`` over the run graph."""
    key = lambda p: (round(p[0], 4), round(p[1], 4), round(p[2], 4))
    adj = {}
    for a, b in runs:
        ka, kb = key(a), key(b)
        d = math.dist(a, b)
        adj.setdefault(ka, []).append((kb, d))
        adj.setdefault(kb, []).append((ka, d))
    dist = {key(start): 0.0}
    heap = [(0.0, key(start))]
    while heap:
        d, n = heapq.heappop(heap)
        if d > dist.get(n, math.inf):
            continue
        for m, w in adj.get(n, ()):
            if d + w < dist.get(m, math.inf):
                dist[m] = d + w
                heapq.heappush(heap, (d + w, m))
    found = [dist[key(t)] for t in targets if key(t) in dist]
    if found:
        return max(found)
    return sum(math.dist(a, b) for a, b in runs)          # disconnected: whole length (upper bound)


def analyse(doc):
    """Everything the «Πίνακας» tab shows. Pure function of the Document."""
    wiring = route_cables_cached(doc)
    conf = settings(doc)
    points = {e.id: e for e in electrical_points(doc)}
    circuits = wiring["circuits"]
    warnings = list(wiring["report"]["warnings"])
    by_id = {c["id"]: c for c in circuits}
    # Switch legs belong to the lighting circuit of their lights.
    light_circuit = {pid: c["id"] for c in circuits if c["group"] == "lighting" for pid in c["points"]}
    switch_circuit = {}
    for link in wiring["switch_links"]:
        switch_circuit[link["switch"]] = next((light_circuit[l] for l in link["lights"] if l in light_circuit), "")

    walls_by_floor = _walls_by_floor(doc)
    numbers = {}
    for floor in sorted(walls_by_floor):
        for w in walls_by_floor[floor]:
            numbers[w.id] = len(numbers) + 1
    per_location, per_circuit_runs = {}, {}
    totals = {}
    switch_runs = _switch_runs(doc, wiring, points)
    tagged = [(a, b, cid, conductors(by_id[cid]) if cid in by_id else SWITCH_LEG, "line")
              for a, b, _g, cid in wiring["runs"] if cid]
    tagged += [(a, b, switch_circuit.get(sid, ""), SWITCH_LEG, "switch") for a, b, sid in switch_runs]
    for a, b, cid, wires, kind in tagged:
        floor = _floor_of(doc, min(a[2], b[2]))
        walls = walls_by_floor.get(round(floor, 3), [])
        where, wid = _location(doc, walls, floor, a, b)
        loc = wid if where == "wall" else f"{where}@{floor:g}"
        length = math.dist(a, b)
        entry = per_location.setdefault(loc, {"kind": where, "wall": wid, "floor": floor, "conduit_m": 0.0,
                                              "by_section": {}, "circuits": set()})
        entry["conduit_m"] += length
        entry["circuits"].add(cid or "—")
        for _code, _label, _colour, s in wires:
            entry["by_section"][s] = entry["by_section"].get(s, 0.0) + length
            totals[s] = totals.get(s, 0.0) + length
        if kind == "line":
            per_circuit_runs.setdefault(cid, []).append((a, b))
        per_circuit_runs.setdefault(("all", cid), []).append((a, b, wires))
    walls_out = []
    for loc, entry in per_location.items():
        if entry["kind"] == "wall":
            label = wall_label(doc, doc.get(entry["wall"]), numbers[entry["wall"]])
        else:
            label = LOCATION_LABELS[entry["kind"]]
        walls_out.append({"location": loc, "kind": entry["kind"], "wall": entry["wall"], "floor": entry["floor"],
                          "label": label, "conduit_m": round(entry["conduit_m"], 2),
                          "by_section": {s: round(m, 2) for s, m in sorted(entry["by_section"].items())},
                          "circuits": sorted(entry["circuits"], key=_natural)})
    order = {"wall": 0, "ceiling": 1, "floor": 2, "free": 3}
    walls_out.sort(key=lambda r: (r["floor"], order[r["kind"]], numbers.get(r["wall"], 0)))
    if any(r["kind"] == "free" for r in walls_out):
        warnings.append("Τμήματα καλωδίων εκτός τοίχων (βλ. «Εκτός τοίχου»): ελέγξτε τη διαδρομή")

    waste = max(0.0, conf["waste_pct"])
    purchase = [{"mm2": s, "use": SECTIONS[s][0], "metres": round(m, 1), "with_waste": round(m * (1 + waste / 100.0), 1)}
                for s, m in sorted(totals.items())]

    panel = points.get(conf["panel"]) if conf["panel"] else None
    rows = []
    for c in circuits:
        sec = float(c["cable_mm2"])
        iz = SECTIONS.get(sec, (None, None, None))[1]
        own = per_circuit_runs.get(c["id"], [])
        targets = [(float(points[p].params["x"]), float(points[p].params["y"]), mount_z(doc, points[p].params))
                   for p in c["points"]]
        start = None
        if panel is not None and own:
            pz = mount_z(doc, panel.params)
            start = min((pt for ab in own for pt in ab), key=lambda q: (abs(q[2] - pz), math.hypot(q[0] - float(panel.params["x"]), q[1] - float(panel.params["y"]))))
        far = _farthest(own, start, targets) if start is not None else 0.0
        amps = float(c["load_w"]) / VOLTAGE
        drop = 200.0 * RHO * far * amps / (sec * VOLTAGE) if sec > 0 else 0.0
        limit = DROP_LIMITS.get(c["group"], DROP_OTHER)
        all_runs = per_circuit_runs.get(("all", c["id"]), [])
        metres = {}
        for a, b, wires in all_runs:
            for _code, _l, _col, s in wires:
                metres[s] = metres.get(s, 0.0) + math.dist(a, b)
        row = {"id": c["id"], "label": c["label"], "group": c["group"], "breaker_a": c["breaker_a"], "mm2": sec,
               "iz_a": iz, "points": len(c["points"]), "point_ids": list(c["points"]), "load_w": c["load_w"],
               "current_a": c["current_a"], "conductors": conductors(c), "switch_leg": c["group"] == "lighting",
               "conduit_m": round(sum(math.dist(a, b) for a, b in own), 1),
               "wire_m": {s: round(m, 1) for s, m in sorted(metres.items())},
               "farthest_m": round(far, 1), "drop_pct": round(drop, 2), "drop_limit_pct": limit,
               "rooms": _rooms(doc, [points[p] for p in c["points"]]), "ok": bool(c["ok"]), "notes": []}
        if not c["ok"]:
            row["notes"].append("υπερφόρτιση")
        if iz is not None and c["breaker_a"] > iz:
            row["ok"] = False
            row["notes"].append(f"ασφάλεια {c['breaker_a']} A > Iz {iz:g} A")
            warnings.append(f"{c['id']} {c['label']}: ασφάλεια {c['breaker_a']} A > Iz {iz:g} A του {sec:g} mm²")
        if drop > limit:
            row["ok"] = False
            row["notes"].append(f"πτώση τάσης {drop:.1f} % > {limit:g} %")
            warnings.append(f"{c['id']} {c['label']}: πτώση τάσης {drop:.1f} % > {limit:g} % (μεγαλύτερη διατομή ή κοντύτερη διαδρομή)")
        rows.append(row)

    board = _board(circuits, rows, conf, warnings) if circuits else None
    return {"circuits": rows, "walls": walls_out, "purchase": purchase, "waste_pct": waste, "board": board,
            "warnings": warnings, "provenance": PROVENANCE, "circuit_provenance": wiring["report"]["provenance"],
            "boxes": wiring["report"].get("boxes", {}), "settings": conf}


def _board(circuits, rows, conf, warnings):
    installed = sum(float(c["load_w"]) for c in circuits)
    demand_a, method = _demand(circuits, conf["demand_factor"])
    demand_kva = demand_a * VOLTAGE / 1000.0
    if conf["supply"] in SUPPLIES:
        key = conf["supply"]
        chosen_by = "επιλογή χρήστη"
    else:
        key = next((k for k, s in SUPPLIES.items() if s[2] >= demand_kva), "5")
        chosen_by = "η μικρότερη που καλύπτει τη ζήτηση"
    label, phases, kva, fuse = SUPPLIES[key]
    if demand_kva > kva:
        warnings.append(f"Ζήτηση {demand_kva:.1f} kVA > {label}: χρειάζεται μεγαλύτερη παροχή")
    phase_of, phase_w = {}, {"L1": 0.0, "L2": 0.0, "L3": 0.0}
    if phases == 3:
        for c in sorted(circuits, key=lambda c: (-float(c["load_w"]), c["id"])):
            ph = min(phase_w, key=lambda k: (phase_w[k], k))
            phase_of[c["id"]] = ph
            phase_w[ph] += float(c["load_w"])
    else:
        phase_of = {c["id"]: "L1" for c in circuits}
        phase_w = {"L1": installed}
    for r in rows:
        r["phase"] = phase_of[r["id"]]
    imbalance = 0.0
    if phases == 3 and installed > 0:
        mean = installed / 3.0
        imbalance = 100.0 * (max(phase_w.values()) - min(phase_w.values())) / mean
    feeder = next((s for s, v in SECTIONS.items() if v[1] is not None and (v[1] if phases == 1 else v[2]) >= fuse), max(SECTIONS))
    rcd_a = 40 if fuse <= 40 else 63
    rcd_count = 2 if len(circuits) >= 6 else 1
    poles = "2P" if phases == 1 else "4P"
    groups = [rows[i::rcd_count] for i in range(rcd_count)]
    rcds = [{"label": f"Διαφορικός Δ{k + 1} {poles} {rcd_a} A / 30 mA τύπου A", "circuits": [r["id"] for r in g]}
            for k, g in enumerate(groups)]
    return {"installed_w": round(installed), "demand_a": round(demand_a, 1), "demand_kva": round(demand_kva, 1),
            "demand_method": method, "demand_provenance": DEMAND_PROVENANCE, "supply": key, "supply_label": label,
            "supply_chosen_by": chosen_by, "supply_provenance": SUPPLY_PROVENANCE, "phases": phases, "supply_kva": kva,
            "fuse_a": fuse, "main_switch": f"Γενικός διακόπτης {poles} {fuse} A",
            "feeder": f"Γραμμή τροφοδοσίας {'3' if phases == 1 else '5'}×{feeder:g} mm² (Iz ≥ {fuse} A)",
            "rcds": rcds, "rcd_note": ("Δύο διαφορικοί ώστε μια διαρροή να μη σβήνει όλο το σπίτι (HD 60364-3 §314) — πρόταση"
                                       if rcd_count == 2 else "Ένας διαφορικός για όλα τα κυκλώματα"),
            "phase_w": {k: round(v) for k, v in phase_w.items()}, "imbalance_pct": round(imbalance, 1),
            "breakers": [f"{r['id']} 1P+N {r['breaker_a']} A" for r in rows]}


def _rooms(doc, pts):
    from archforge.mep.electrical import _room_of
    names = []
    for e in pts:
        floor = _floor_of(doc, float(e.params["z"]))
        name = _room_of(doc, float(e.params["x"]), float(e.params["y"]), floor) or "—"
        if name not in names:
            names.append(name)
    return names


def _switch_runs(doc, wiring, points):
    """Switch-leg runs keyed by switch id (route_cables leaves them without a circuit id)."""
    out = []
    for link in wiring["switch_links"]:
        sw = points.get(link["switch"])
        if sw is None:
            continue
        floor = _floor_of(doc, float(sw.params["z"]))
        zr, zc = floor + WALL_RUN_Z, _ceiling(doc, floor)
        sx, sy = float(sw.params["x"]), float(sw.params["y"])
        legs = [((sx, sy, mount_z(doc, sw.params)), (sx, sy, zr)), ((sx, sy, zr), (sx, sy, zc))]
        for lid in link["lights"]:
            lx, ly = float(points[lid].params["x"]), float(points[lid].params["y"])
            legs += [((sx, sy, zc), (lx, sy, zc)), ((lx, sy, zc), (lx, ly, zc))]
        out += [(a, b, sw.id) for a, b in legs if math.dist(a, b) > 1e-6]
    return out


def _natural(text):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(text))]


def board_csv(result):
    """Semicolon CSV (opens in Excel with Greek locale) of circuits, walls and purchase list."""
    def num(v):
        return f"{v:g}".replace(".", ",") if isinstance(v, (int, float)) else str(v)
    lines = ["Κυκλώματα", "Κύκλωμα;Περιγραφή;Φάση;Ασφάλεια A;Διατομή mm²;Αγωγοί;Σημεία;Χώροι;Φορτίο W;Ρεύμα A;"
             "Μήκος σωλήνα m;Πτώση τάσης %;Έλεγχος"]
    for r in result["circuits"]:
        wires = " + ".join(f"{code} {num(s)}" for code, _l, _c, s in r["conductors"])
        if r["switch_leg"]:
            wires += " · επιστροφές 1,5"
        lines.append(";".join([r["id"], r["label"], r.get("phase", ""), num(r["breaker_a"]), num(r["mm2"]), wires,
                               num(r["points"]), ", ".join(r["rooms"]), num(r["load_w"]), num(r["current_a"]),
                               num(r["conduit_m"]), num(r["drop_pct"]), "OK" if r["ok"] else "⚠ " + ", ".join(r["notes"])]))
    sections = sorted({s for w in result["walls"] for s in w["by_section"]})
    lines += ["", "Μέτρα ανά τοίχο", "Θέση;Κυκλώματα;Σωλήνας m;" + ";".join(f"{num(s)} mm² m" for s in sections)]
    for w in result["walls"]:
        lines.append(";".join([w["label"], " ".join(w["circuits"]), num(w["conduit_m"])]
                              + [num(w["by_section"].get(s, 0)) for s in sections]))
    lines += ["", f"Αγορά (φύρα {num(result['waste_pct'])} %)", "Διατομή mm²;Χρήση;Μέτρα;Με φύρα"]
    lines += [";".join([num(p["mm2"]), p["use"], num(p["metres"]), num(p["with_waste"])]) for p in result["purchase"]]
    b = result["board"]
    if b:
        lines += ["", "Πίνακας", f"Εγκατεστημένη ισχύς W;{num(b['installed_w'])}", f"Ζήτηση kVA;{num(b['demand_kva'])}",
                  f"Παροχή;{b['supply_label']}", f"Γενικός;{b['main_switch']}", f"Τροφοδοσία;{b['feeder']}"]
        lines += [f"Διαφορικός;{d['label']};{' '.join(d['circuits'])}" for d in b["rcds"]]
    lines += ["", result["provenance"], result["circuit_provenance"]]
    return "\n".join(lines) + "\n"
