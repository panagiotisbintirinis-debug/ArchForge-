"""Electrical board analysis derived from the routed circuits (``route_cables``).

Three things the owner asked for (2026-10-14/15), each with its rule written
here so an electrical engineer can check it:

1. **Conductors per circuit** — phase L, neutral N, protective earth PE and the
   switch returns, with the cross-section of each (0.75 … 10 mm² copper).
2. **Metres per wall and per cross-section** (prefabricated houses: which
   cables pass through which wall, how many metres) from the conduit runs.
3. **Board** — breaker per circuit, installed power (sum of the points),
   phase balance on a three-phase supply, the length to the farthest point
   of each circuit; demand and supply only from the values the user enters.

Owner's rule (2026-10-15, AGENTS.md): no value from memory.  Everything here is
geometry or arithmetic on the drawing and on the user's entries; every rule is
registered in ``core.provenance`` with its status and only VERIFIED ones may be
shown as requirements.

Settings live on the panel point (shared commands, undo, save/load), 0 = not
entered: ``supply_kva``, ``supply_phases`` (1/3), ``supply_fuse_a`` (from the
ΔΕΔΔΗΕ connection), ``demand_factor`` (from the study), ``waste_pct``.

Status: pre-design for review by an electrical engineer — not a full
study (no short-circuit/selectivity/earthing-resistance calculation).
"""
from __future__ import annotations

import heapq
import math

from archforge.mep.electrical import (WALL_NEAR, WALL_RUN_Z, _ceiling, _floor_of,
                                      electrical_points, mount_z, route_cables_cached)
from archforge.core.provenance import DESIGN_DEFAULT, ENGINEER_REVIEW, Rule, register
from archforge.mep.plumbing import CELL

PROVENANCE = ("Κανόνας ιδιοκτήτη 15/10: καμία τιμή από μνήμη. Εδώ υπολογίζονται μόνο γεωμετρία (μέτρα, θέσεις) "
              "και αθροίσματα από τα στοιχεία του σχεδίου και ό,τι εισάγει ο χρήστης· οι κανόνες κυκλωμάτων "
              "(ασφάλειες/διατομές/σημεία ανά κύκλωμα) είναι του mep/electrical.py και περιμένουν επαλήθευση "
              "(βλ. «Κατάσταση κανόνων»). Προμελέτη, προς έλεγχο από ηλεκτρολόγο μηχανικό")

register(
    Rule("board.iz", "Ικανότητα φόρτισης Iz ανά διατομή — δεν ελέγχεται ασφάλεια ≤ Iz", ENGINEER_REVIEW,
         note="ΕΛΟΤ HD 60364-5-52 Πίνακες B.52.x: να εισαχθούν από το πρότυπο"),
    Rule("board.voltage_drop", "Πτώση τάσης — δεν υπολογίζεται· δίνεται μόνο το μήκος ως το πιο μακρινό σημείο", ENGINEER_REVIEW,
         note="ΕΛΟΤ HD 60364-5-52 Παράρτ. G: όρια και ειδική αντίσταση από το πρότυπο"),
    Rule("board.supply", "Παροχή ΔΕΔΔΗΕ: kVA, φάσεις, ασφάλεια όπως τα εισάγει ο χρήστης", ENGINEER_REVIEW,
         note="Από την αίτηση/σύμβαση σύνδεσης· η αρίθμηση «Νο 1–5» από μνήμη ήταν λάθος (ΔΕΔΔΗΕ: Νο 03, Νο 05 …)"),
    Rule("board.demand_factor", "Συντελεστής ταυτοχρονισμού της μελέτης", ENGINEER_REVIEW),
    Rule("board.rcd_layout", "Πλήθος/ονομαστικό ρεύμα διαφορικών, γραμμή τροφοδοσίας", ENGINEER_REVIEW),
    Rule("board.phase_balance", "Κατανομή φάσεων: το μεγαλύτερο φορτίο στην πιο ελαφριά φάση", DESIGN_DEFAULT,
         note="Αλγόριθμος του προγράμματος· ο ηλεκτρολόγος ορίζει την τελική κατανομή"),
    Rule("board.waste", "Φύρα αγοράς καλωδίων", DESIGN_DEFAULT, note="Ρύθμιση χρήστη, 0 % αν δεν οριστεί"),
)


def unverified_lines():
    """Every rule the board relies on that is not VERIFIED, as «[κατάσταση] κανόνας — σημείωση»."""
    from archforge.core.provenance import STATUS_LABELS, rules
    out = []
    for r in rules("electrical.") + rules("board.") + rules("lighting."):
        if not r.is_requirement:
            out.append(f"[{STATUS_LABELS[r.status]}] {r.statement}" + (f" — {r.note}" if r.note else ""))
    return out


CONDUCTOR_LABELS = {"L": "Φάση", "N": "Ουδέτερος", "PE": "Γείωση", "R": "Επιστροφή διακόπτη"}


def settings(doc):
    """Board settings from the panel point; 0 = not entered (no hidden defaults)."""
    panel = next((e for e in electrical_points(doc) if e.params["point_type"] == "panel"), None)
    p = panel.params if panel is not None else {}
    return {"panel": panel.id if panel is not None else None, "supply_kva": float(p.get("supply_kva", 0.0)),
            "supply_phases": int(p.get("supply_phases", 0)), "supply_fuse_a": float(p.get("supply_fuse_a", 0.0)),
            "demand_factor": float(p.get("demand_factor", 0.0)), "waste_pct": float(p.get("waste_pct", 0.0))}


def conductors(circuit):
    """Conductors of a circuit's line: [(code, label, mm²)] — L, N, PE at the circuit's section."""
    s = float(circuit["cable_mm2"])
    return [(c, CONDUCTOR_LABELS[c], s) for c in ("L", "N", "PE")]


def switch_leg(section):
    """Switch leg of a lighting circuit: phase to the switch and its return, at the circuit's section."""
    return [("L", CONDUCTOR_LABELS["L"], section), ("R", CONDUCTOR_LABELS["R"], section)]


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
    tagged = [(a, b, cid, conductors(by_id[cid]), "line") for a, b, _g, cid in wiring["runs"] if cid in by_id]
    for a, b, sid in switch_runs:
        cid = switch_circuit.get(sid, "")
        if cid in by_id:
            tagged.append((a, b, cid, switch_leg(float(by_id[cid]["cable_mm2"])), "switch"))
        else:
            warnings.append(f"Διακόπτης {sid[:6]} χωρίς κύκλωμα φωτισμού: τα σκέλη του δεν μετρήθηκαν")
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
        for _code, _label, s in wires:
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
    purchase = [{"mm2": s, "metres": round(m, 1), "with_waste": round(m * (1 + waste / 100.0), 1)}
                for s, m in sorted(totals.items())]

    panel = points.get(conf["panel"]) if conf["panel"] else None
    rows = []
    for c in circuits:
        sec = float(c["cable_mm2"])
        own = per_circuit_runs.get(c["id"], [])
        targets = [(float(points[p].params["x"]), float(points[p].params["y"]), mount_z(doc, points[p].params))
                   for p in c["points"]]
        start = None
        if panel is not None and own:
            pz = mount_z(doc, panel.params)
            start = min((pt for ab in own for pt in ab), key=lambda q: (abs(q[2] - pz), math.hypot(q[0] - float(panel.params["x"]), q[1] - float(panel.params["y"]))))
        far = _farthest(own, start, targets) if start is not None else 0.0
        all_runs = per_circuit_runs.get(("all", c["id"]), [])
        metres = {}
        for a, b, wires in all_runs:
            for _code, _l, s in wires:
                metres[s] = metres.get(s, 0.0) + math.dist(a, b)
        row = {"id": c["id"], "label": c["label"], "group": c["group"], "breaker_a": c["breaker_a"], "mm2": sec,
               "points": len(c["points"]), "point_ids": list(c["points"]), "load_w": c["load_w"],
               "current_a": c["current_a"], "conductors": conductors(c), "switch_leg": c["group"] == "lighting",
               "conduit_m": round(sum(math.dist(a, b) for a, b in own), 1),
               "wire_m": {s: round(m, 1) for s, m in sorted(metres.items())},
               "farthest_m": round(far, 1),
               "rooms": _rooms(doc, [points[p] for p in c["points"]]), "ok": bool(c["ok"]), "notes": []}
        if not c["ok"]:
            row["notes"].append("υπερφόρτιση")
        rows.append(row)

    board = _board(circuits, rows, conf, warnings) if circuits else None
    return {"circuits": rows, "walls": walls_out, "purchase": purchase, "waste_pct": waste, "board": board,
            "warnings": warnings, "provenance": PROVENANCE, "unverified": unverified_lines(), "circuit_provenance": wiring["report"]["provenance"],
            "boxes": wiring["report"].get("boxes", {}), "settings": conf}


def _board(circuits, rows, conf, warnings):
    """Installed power (sum of the points' loads), demand and supply only from the user's entries."""
    installed = sum(float(c["load_w"]) for c in circuits)
    factor, kva, phases, fuse = conf["demand_factor"], conf["supply_kva"], conf["supply_phases"], conf["supply_fuse_a"]
    demand_kva = installed * factor / 1000.0 if factor > 0 else None      # kVA ≈ kW: no power factor assumed
    missing = [name for name, value in (("συντελεστής ταυτοχρονισμού", factor), ("παροχή kVA", kva),
                                        ("φάσεις", phases), ("ασφάλεια παροχής", fuse)) if not value]
    if demand_kva is not None and kva and demand_kva > kva:
        warnings.append(f"Ζήτηση {demand_kva:.1f} kVA > παροχή {kva:g} kVA (με τον συντελεστή {factor:.2f} της μελέτης)")
    phase_w = {"L1": installed}
    phase_of = {c["id"]: "L1" for c in circuits} if phases == 1 else {c["id"]: "" for c in circuits}
    imbalance = None
    if phases == 3:
        phase_w = {"L1": 0.0, "L2": 0.0, "L3": 0.0}
        for c in sorted(circuits, key=lambda c: (-float(c["load_w"]), c["id"])):
            ph = min(phase_w, key=lambda k: (phase_w[k], k))      # largest load to the lightest phase
            phase_of[c["id"]] = ph
            phase_w[ph] += float(c["load_w"])
        if installed > 0:
            imbalance = 100.0 * (max(phase_w.values()) - min(phase_w.values())) / (installed / 3.0)
    for r in rows:
        r["phase"] = phase_of[r["id"]]
    return {"installed_w": round(installed), "demand_kva": None if demand_kva is None else round(demand_kva, 1),
            "demand_factor": factor or None, "supply_kva": kva or None, "phases": phases or None, "fuse_a": fuse or None,
            "main_switch": (f"Γενικός διακόπτης {'2P' if phases == 1 else '4P'} {fuse:g} A" if fuse and phases else None),
            "missing": missing, "phase_w": {k: round(v) for k, v in phase_w.items()},
            "imbalance_pct": None if imbalance is None else round(imbalance, 1),
            "breakers": [f"{r['id']} {r['breaker_a']} A" for r in rows]}


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
        if v is None:
            return "— (δεν εισήχθη)"
        return f"{v:g}".replace(".", ",") if isinstance(v, (int, float)) else str(v)
    lines = ["Κυκλώματα", "Κύκλωμα;Περιγραφή;Φάση;Ασφάλεια A;Διατομή mm²;Αγωγοί;Σημεία;Χώροι;Φορτίο W;Ρεύμα A;"
             "Μήκος σωλήνα m;Ως το πιο μακρινό σημείο m;Έλεγχος"]
    for r in result["circuits"]:
        wires = " + ".join(f"{code} {num(s)}" for code, _l, s in r["conductors"])
        if r["switch_leg"]:
            wires += f" · σκέλη διακοπτών L + επιστροφή {num(r['mm2'])}"
        lines.append(";".join([r["id"], r["label"], r.get("phase", ""), num(r["breaker_a"]), num(r["mm2"]), wires,
                               num(r["points"]), ", ".join(r["rooms"]), num(r["load_w"]), num(r["current_a"]),
                               num(r["conduit_m"]), num(r["farthest_m"]), "OK" if r["ok"] else "⚠ " + ", ".join(r["notes"])]))
    sections = sorted({s for w in result["walls"] for s in w["by_section"]})
    lines += ["", "Μέτρα ανά τοίχο", "Θέση;Κυκλώματα;Σωλήνας m;" + ";".join(f"{num(s)} mm² m" for s in sections)]
    for w in result["walls"]:
        lines.append(";".join([w["label"], " ".join(w["circuits"]), num(w["conduit_m"])]
                              + [num(w["by_section"].get(s, 0)) for s in sections]))
    lines += ["", f"Αγορά (φύρα {num(result['waste_pct'])} %, ρύθμιση χρήστη)", "Διατομή mm²;Μέτρα;Με φύρα"]
    lines += [";".join([num(p["mm2"]), num(p["metres"]), num(p["with_waste"])]) for p in result["purchase"]]
    b = result["board"]
    if b:
        lines += ["", "Πίνακας", f"Εγκατεστημένη ισχύς (άθροισμα σημείων) W;{num(b['installed_w'])}",
                  f"Συντελεστής ταυτοχρονισμού (μελέτη);{num(b['demand_factor'])}", f"Ζήτηση kVA;{num(b['demand_kva'])}",
                  f"Παροχή kVA;{num(b['supply_kva'])}", f"Φάσεις;{num(b['phases'])}", f"Ασφάλεια παροχής A;{num(b['fuse_a'])}"]
    lines += ["", "Κατάσταση κανόνων (μόνο τα επαληθευμένα είναι τεχνική απαίτηση)"] + list(result["unverified"])
    lines += ["", result["provenance"], result["circuit_provenance"]]
    return "\n".join(lines) + "\n"
