"""Electrical layout: points in the Document, circuits and cable runs derived.

The user places the panel, lights, switches, sockets and dedicated appliance
outlets.  Circuits are grouped and routed automatically from those points
with the rules below.  They were first written as "common practice under
ΕΛΟΤ HD 384", a standard that is no longer in force (replaced by ΕΛΟΤ HD
60364, see ``core.provenance``); every rule is registered with its status and
none of them is VERIFIED yet, so none is presented as a requirement:

* Lighting: 10 A breaker, 1.5 mm² cable, at most 10 points per circuit,
  grouped by room.  A switch controls the lights of its room.
* General sockets: 16 A breaker, 2.5 mm², at most 6 sockets per circuit,
  grouped by room; kitchen sockets never share a circuit with other rooms.
* Dedicated lines (one appliance each): cooker/oven 40 A 10 mm² (single
  phase), water heater 20 A 4 mm² (owner's decision 15/10, installer practice),
  air-conditioner, washing machine, dishwasher 16 A 2.5 mm².
* At least two lighting circuits per dwelling (owner 15/10).
* A shared circuit whose design load exceeds 80 % of its breaker, or a
  dedicated line whose appliance exceeds its breaker, is flagged.
* Routes (Greek practice): conduits rise into the walls and run horizontally
  at 2.35 m (above the lintels) with a junction box above every switch and
  socket; points away from walls (kitchen islands) are fed through the floor
  with a box 15 cm above the floor; the choice is automatic per point or set
  by the user ('routing' = wall/floor/ceiling).  Boxes only where needed (owner 18/10):
  a junction box where a conduit turns vertical to a device or the ceiling,
  a pull box at a corner after a long run (≥ 10 m) — none on a straight run —
  and one box per place, shared by every circuit that passes it.  Same
  cheapest-path router as the plumbing.
* All circuits sit behind a 30 mA RCD (noted, not modelled).

Status: pre-design layout for review by an electrical engineer; it is not
a load study, voltage-drop or selectivity calculation.
"""
from __future__ import annotations

import math

from archforge.core.provenance import DESIGN_DEFAULT, ENGINEER_REVIEW, MANUFACTURER_DATA, UNVERIFIED, Rule, register
from archforge.mep.plumbing import CELL, _Grid, _grow, _levels

_HD384 = "Γράφτηκε κατά το ΕΛΟΤ HD 384 (αποσύρθηκε· ισχύει ΕΛΟΤ HD 60364) — να διασταυρωθεί με το ισχύον πρότυπο"
register(
    Rule("electrical.lighting_circuit", "Φωτισμός: ασφάλεια 10 A, καλώδιο 1,5 mm², ως 10 σημεία ανά κύκλωμα, ανά χώρο",
         UNVERIFIED, note=_HD384),
    Rule("electrical.socket_circuit", "Ρευματοδότες: 16 A, 2,5 mm², ως 6 ανά κύκλωμα· κουζίνα ως 4, χωριστά", UNVERIFIED, note=_HD384),
    Rule("electrical.dedicated_lines", "Αποκλειστικές γραμμές: κουζίνα 40 A/10 mm² (μονοφασική), θερμοσίφωνας 20 A/4 mm², "
         "κλιματιστικό/πλυντήρια 16 A/2,5 mm²", ENGINEER_REVIEW,
         source="Απόφαση ιδιοκτήτη 15/10 με βάση την πρακτική εγκαταστάτη (σύνοψη) — αντικατέστησε 32 A/6 mm² και 20 A/2,5 mm²",
         note="Ο θερμοσίφωνας 20 A σε 2,5 mm² δεν περνούσε Ib ≤ In ≤ Iz σε A1 (Iz 19,5 A)· κλιματιστικό/πλυντήρια: " + _HD384),
    Rule("electrical.lighting_min_two", "Τουλάχιστον 2 κυκλώματα φωτισμού ανά κατοικία (όταν υπάρχουν ≥ 2 φωτιστικά)",
         ENGINEER_REVIEW, source="Απόφαση ιδιοκτήτη 15/10 — πρακτική εγκαταστάτη και ΕΛΟΤ HD 60364-3 §314 (κατά σύνοψη)"),
    Rule("electrical.shared_margin", "Κοινό κύκλωμα: προειδοποίηση πάνω από 80 % της ασφάλειας", UNVERIFIED, note=_HD384),
    Rule("electrical.rcd_30ma", "Διαφορικό ≤ 30 mA (συμπληρωματική προστασία): ρευματοδότες ως 32 A, τελικά κυκλώματα "
         "φωτισμού κατοικίας, κινητός εξοπλισμός εξωτερικών χώρων ως 32 A· στο πρόγραμμα όλα τα κυκλώματα (σημειώνεται, "
         "δεν μοντελοποιείται)", ENGINEER_REVIEW,
         source="ΕΛΟΤ HD 60364-4-41 §411.3.3 — κατά τη σύνοψη που έδωσε ο ιδιοκτήτης 15/10",
         note="Δεν έχει διαβαστεί το κείμενο του προτύπου: γίνεται VERIFIED όταν μπει απόσπασμα/σελίδα του ΕΛΟΤ"),
    Rule("electrical.division_314", "Διαίρεση εγκατάστασης: όχι ένας διαφορικός για όλο τον πίνακα· φωτισμός χωριστά από "
         "πρίζες και σε ≥ 2 κυκλώματα/διαφορικούς· βαριά/κρίσιμα φορτία σε δικά τους κυκλώματα", ENGINEER_REVIEW,
         source="ΕΛΟΤ HD 60364-3 §314 (αρχές) — κατά τη σύνοψη του ιδιοκτήτη 15/10",
         note="Η πρακτική εφαρμογή (πλήθος διαφορικών, RCBO) είναι ερμηνεία, όχι κείμενο του προτύπου· απόφαση ηλεκτρολόγου"),
    Rule("electrical.voltage", "Τάση 230 V για τη μετατροπή W → A", UNVERIFIED, note="Ονομαστική τάση δικτύου: να τεκμηριωθεί"),
    Rule("electrical.point_loads", "Ονομαστικά W ανά σημείο (φωτιστικό 60, πρίζα 200, πάγκος 500, κουζίνα 6000, "
         "θερμοσίφωνας 4000, κλιματιστικό 2500, πλυντήρια 2300/2000)", ENGINEER_REVIEW,
         note="Υποθέσεις φορτίου· ο χρήστης τις αλλάζει ανά σημείο (power_w)"),
    Rule("electrical.luminaire_power", "Σποτ/χωνευτό/wall washer: W· ταινία LED: W/m", MANUFACTURER_DATA,
         note="Χωρίς προεπιλογή: 0 W με ⚠ μέχρι να μπει η τιμή του φύλλου"),
    Rule("electrical.routing_heights", "Όδευση: οριζόντια σε τοίχο στα 2,35 m, γραμμή δαπέδου 5 cm, κουτί δαπέδου 15 cm, «κοντά σε τοίχο» = 60 cm",
         DESIGN_DEFAULT, note="Πρακτική τοποθέτησης του προγράμματος, όχι κανονισμός"),
    Rule("electrical.pull_boxes", "Κουτιά μόνο όπου χρειάζονται: διακλάδωσης σε κάθετη έξοδο (κατέβασμα σε σημείο, "
         "ανέβασμα στην οροφή), διέλευσης σε γωνία μετά από μεγάλη διαδρομή (≥ 10 m)· όχι σε ευθεία, ένα ανά θέση",
         DESIGN_DEFAULT, note="Ιδιοκτήτης 18/10: «αλλιώς είναι φθορά υλικού» — πρακτική εγκαταστάτη, προς έλεγχο ηλεκτρολόγου"),
)

PROVENANCE = ("Προμελέτη κυκλωμάτων με κανόνες του προγράμματος ΜΗ ΕΠΑΛΗΘΕΥΜΕΝΟΥΣ (φωτισμός 10A/1,5mm² ≤10 σημεία, "
              "πρίζες 16A/2,5mm² ≤6, αποκλειστικές γραμμές) — είχαν γραφτεί κατά το αποσυρμένο ΕΛΟΤ HD 384· "
              "ισχύει το ΕΛΟΤ HD 60364. Δεν είναι τεχνική απαίτηση· προς έλεγχο από ηλεκτρολόγο μηχανικό")
VOLTAGE = 230.0

# type: label, group, default W, mounting height (m), plan letter
POINT_TYPES = {
    "panel": ("Ηλεκτρικός πίνακας", "panel", 0, 1.60, "ΠΙ"),
    "light": ("Φωτιστικό οροφής", "lighting", 60, None, "Φ"),
    "spot": ("Σποτ (κατευθυνόμενο)", "lighting", 0, None, "Σπ"),
    "downlight": ("Χωνευτό φωτιστικό οροφής", "lighting", 0, None, "Χ"),
    "wall_washer": ("Wall washer (φως σε τοίχο)", "lighting", 0, None, "WW"),
    "led_strip": ("Κρυφός φωτισμός — ταινία LED", "lighting", 0, None, "LED"),
    "wall_light": ("Απλίκα", "lighting", 40, 2.00, "Α"),
    "switch": ("Διακόπτης", "switch", 0, 1.10, "Δ"),
    "dimmer": ("Ροοστάτης (dimmer)", "switch", 0, 1.10, "Δρ"),
    "socket": ("Πρίζα σούκο", "sockets", 200, 0.30, "Ρ"),
    "kitchen_socket": ("Πρίζα πάγκου κουζίνας", "kitchen_sockets", 500, 1.10, "ΡΚ"),
    "cooker": ("Κουζίνα/φούρνος", "cooker", 6000, 0.30, "ΚΦ"),
    "water_heater": ("Θερμοσίφωνας", "water_heater", 4000, 1.80, "ΘΣ"),
    "air_conditioner": ("Κλιματιστικό", "air_conditioner", 2500, 2.20, "ΚΛ"),
    "washing_machine": ("Πλυντήριο ρούχων", "washing_machine", 2300, 0.60, "ΠΡ"),
    "dishwasher": ("Πλυντήριο πιάτων", "dishwasher", 2000, 0.40, "ΠΠ"),
    # Equipment supplies (owner 18/10: heating and the pool on the board) — W from the equipment's data sheet.
    "heating_supply": ("Παροχή θέρμανσης (λέβητας / κέντρο καλωδίωσης)", "heating", 0, 1.50, "ΘΡ"),
    "heat_pump_supply": ("Παροχή αντλίας θερμότητας", "heat_pump", 0, 0.60, "ΑΘ"),
    "pool_supply": ("Παροχή μηχανοστασίου πισίνας", "pool", 0, 1.20, "ΠΣ"),
    # Ασθενή (owner 17/10): same entity, own group — never part of a power circuit (mep/low_voltage.py).
    "network_rack": ("Rack δικτύου / κατανεμητής ασθενών", "low_voltage", 0, 1.60, "RK"),
    "data_outlet": ("Πρίζα δικτύου RJ45", "low_voltage", 0, 0.30, "D"),
    "wifi_ap": ("Σημείο πρόσβασης Wi-Fi (οροφή)", "low_voltage", 0, None, "AP"),
    "tv_outlet": ("Πρίζα TV / SAT", "low_voltage", 0, 0.30, "TV"),
}
# group: label, breaker A, cable mm², max points per circuit (None = dedicated)
CIRCUIT_RULES = {
    "lighting": ("Φωτισμός", 10, 1.5, 10),
    "sockets": ("Ρευματοδότες", 16, 2.5, 6),
    "kitchen_sockets": ("Ρευματοδότες κουζίνας", 16, 2.5, 4),
    "cooker": ("Κουζίνα", 40, 10.0, 1),          # owner 15/10: installer practice (μονοφασική), ENGINEER_REVIEW
    "water_heater": ("Θερμοσίφωνας", 20, 4.0, 1),  # owner 15/10: installer practice, ENGINEER_REVIEW
    "air_conditioner": ("Κλιματιστικό", 16, 2.5, 1),
    "washing_machine": ("Πλυντήριο ρούχων", 16, 2.5, 1),
    "dishwasher": ("Πλυντήριο πιάτων", 16, 2.5, 1),
    # Owner 18/10, installer practice like the cooker / water heater (ENGINEER_REVIEW): the burner / wiring centres of
    # a heating system share one line, a heat pump and the pool's equipment room each have their own.
    "heating": ("Θέρμανση (λέβητας / κέντρα καλωδίωσης)", 10, 1.5, 3),
    "heat_pump": ("Αντλία θερμότητας", 16, 2.5, 1),
    "pool": ("Πισίνα — μηχανοστάσιο (δικός του διαφορικός 30 mA)", 16, 2.5, 1),
}
GROUP_ORDER = tuple(CIRCUIT_RULES)
SWITCH_TYPES = ("switch", "dimmer")
LOW_VOLTAGE_TYPES = ("network_rack", "data_outlet", "wifi_ap", "tv_outlet")
# Luminaires added 15/10 carry no catalogue default (owner's rule: no values from memory) —
# their W (or W/m for a strip) comes from the luminaire's data sheet.
DATASHEET_TYPES = ("spot", "downlight", "wall_washer", "led_strip", "heating_supply", "heat_pump_supply", "pool_supply")


def strip_length(params):
    """Length (m) of an LED strip point (from x, y to x2, y2); 0 for other points."""
    if params.get("point_type") != "led_strip":
        return 0.0
    return math.hypot(float(params.get("x2", params["x"])) - float(params["x"]),
                      float(params.get("y2", params["y"])) - float(params["y"]))


def point_load_w(params):
    """Design load (W): the strip's W/m × length, otherwise the point's power."""
    if params.get("point_type") == "led_strip":
        return float(params.get("w_per_m", 0.0)) * strip_length(params)
    return float(params.get("power_w", POINT_TYPES[params["point_type"]][2]))


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
    if "mount_height" in params:
        return floor + float(params["mount_height"])
    if POINT_TYPES[params["point_type"]][3] is None:
        from archforge.mep.lighting import ceiling_mount_z
        return ceiling_mount_z(doc, params, floor, _ceiling(doc, floor))
    return floor + POINT_TYPES[params["point_type"]][3]


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
            return doc.room_metadata(face.signature).get("name") or f"Χώρος {k + 1}"
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
        if e.params["point_type"] in DATASHEET_TYPES and point_load_w(e.params) <= 0:
            out["report"]["warnings"].append(
                f"{POINT_TYPES[e.params['point_type']][0]} {e.id[:6]}: εισάγετε ισχύ από το φύλλο του φωτιστικού "
                f"({'W/m' if e.params['point_type'] == 'led_strip' else 'W'}) — μετράει 0 W")
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
        if group == "lighting" and len(chunks) == 1 and len(chunks[0]) >= 2:
            # At least two lighting circuits (owner 15/10): split at the room change nearest the middle.
            only = chunks[0]
            rooms_of = [(r, f) for r, f, e in members]
            cuts = [k for k in range(1, len(only)) if rooms_of[k] != rooms_of[k - 1]] or [len(only) // 2]
            k = min(cuts, key=lambda c: (abs(c - len(only) / 2), c))
            chunks = [only[:k], only[k:]]
        for chunk in chunks:
            number += 1
            watts = sum(point_load_w(e.params) for e in chunk)
            amps = watts / VOLTAGE
            dedicated = limit == 1
            # Shared circuits keep 20 % margin; a dedicated line must carry its appliance.
            ok = amps <= (breaker if dedicated else 0.8 * breaker)
            circuit = {"id": f"Κ{number}", "group": group, "label": label, "breaker_a": breaker, "cable_mm2": cable,
                       "points": [e.id for e in chunk], "load_w": round(watts), "current_a": round(amps, 1), "ok": ok}
            if not ok:
                fix = "μεγαλύτερη ασφάλεια/διατομή" if dedicated else "χωρίστε το κύκλωμα"
                limit_txt = f"{breaker} A" if dedicated else f"80% της ασφάλειας {breaker} A"
                out["report"]["warnings"].append(f"{circuit['id']} {label}: {amps:.1f} A > {limit_txt} — {fix} "
                                                 "[κανόνας μη επαληθευμένος]")
            out["circuits"].append(circuit)
    # Switches and dimmers control the lights of their automation group, otherwise of their room (same storey).
    lights = [(e, _room_of(doc, float(e.params["x"]), float(e.params["y"]), _floor_of(doc, float(e.params["z"]))),
               _floor_of(doc, float(e.params["z"]))) for e in points if POINT_TYPES[e.params["point_type"]][1] == "lighting"]
    # Groups that have their own switch/dimmer; their lights leave the room's plain switch.
    grouped = {str(e.params.get("automation_group", "")) for e in points if e.params["point_type"] in SWITCH_TYPES} - {""}
    for sw in (e for e in points if e.params["point_type"] in SWITCH_TYPES):
        floor = _floor_of(doc, float(sw.params["z"]))
        room = _room_of(doc, float(sw.params["x"]), float(sw.params["y"]), floor)
        group = str(sw.params.get("automation_group", ""))
        if group:
            controlled = [l.id for l, _r, _f in lights if str(l.params.get("automation_group", "")) == group]
        else:
            controlled = [l.id for l, lroom, lfloor in lights if lfloor == floor and lroom == room and room is not None
                          and str(l.params.get("automation_group", "")) not in grouped]
        if not controlled:
            near = sorted((math.hypot(float(l.params["x"]) - float(sw.params["x"]), float(l.params["y"]) - float(sw.params["y"])), l.id)
                          for l, _r, lf in lights if lf == floor)
            controlled = [near[0][1]] if near else []
        out["switch_links"].append({"switch": sw.id, "lights": controlled, "dimmer": sw.params["point_type"] == "dimmer",
                                    "group": group})
    return out


def _ceiling_fed(e):
    return POINT_TYPES[e.params["point_type"]][3] is None and "mount_height" not in e.params


WALL_RUN_Z = 2.35          # horizontal conduits above the lintels (Greek practice 2.30-2.40 m)
FLOOR_RUN_Z = 0.05         # existing floor-routing height; DESIGN_DEFAULT, not a verified installation depth
FLOOR_BOX_Z = 0.15         # junction boxes 15 cm above the floor for floor routing
WALL_NEAR = 0.60           # auto: a point within 60 cm of a wall face is fed from the wall
PULL_EVERY = 10.0          # owner 18/10: a pull box only at a corner reached after this long a run (never on a straight)
BOX_MERGE = 0.05           # boxes closer than this are one box (shared by the circuits through it)


def _wall_distance(doc, x, y, floor):
    best = math.inf
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - floor) > 0.05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        best = min(best, math.hypot(x - (x1 + dx * t), y - (y1 + dy * t)) - float(p["thickness"]) / 2)
    return best


def routing_of(doc, e):
    """Effective passage; explicit floor/ceiling/wall choice precedes auto."""
    from archforge.mep.electrical_routes import mode_of
    return mode_of(doc, e)


def _pull_boxes(points_chain, z, cid):
    """Pull boxes along one path (list of xy from the target to the source): only at a corner reached after a
    run of PULL_EVERY or more since the last box — a straight run, however long, needs none (owner 18/10)."""
    boxes, run, prev_dir = [], 0.0, None
    for a, b in zip(points_chain, points_chain[1:]):
        d = (round(b[0] - a[0], 6), round(b[1] - a[1], 6))
        seg = math.hypot(*d)
        if seg < 1e-9:
            continue
        direction = (d[0] / seg, d[1] / seg)
        if prev_dir is not None and direction != prev_dir and run >= PULL_EVERY:
            boxes.append((a[0], a[1], z, "pull", cid))
            run = 0.0
        run += seg
        prev_dir = direction
    return boxes


def _merge_boxes(boxes):
    """One box per place: boxes of the same kind within BOX_MERGE are one, listing every circuit through it."""
    out = []
    for x, y, z, kind, cid in boxes:
        hit = next((k for k, b in enumerate(out) if b[3] == kind and abs(b[2] - z) < 1e-6
                    and math.hypot(b[0] - x, b[1] - y) <= BOX_MERGE), None)
        if hit is None:
            out.append((x, y, z, kind, cid))
        elif cid and cid not in out[hit][4].split(","):
            b = out[hit]
            out[hit] = (b[0], b[1], b[2], b[3], ",".join(filter(None, (b[4], cid))))
    return out


def route_cables(doc):
    """Circuits plus conduit runs ``(a, b, group, circuit)`` and boxes.

    Wall routing: up from the panel into the walls at WALL_RUN_Z, horizontal
    runs inside the walls, a junction box at WALL_RUN_Z above every switch and
    socket, then down to the device.  Ceiling lights are fed from a box on
    the nearest wall through the ceiling slab.  Floor routing (islands, free
    standing points): runs in the screed, junction box FLOOR_BOX_Z above the
    floor at the device. Explicit ceiling passage uses the existing ceiling
    level. Choices change routes and quantities; heights remain design defaults.
    Pull boxes by the stated length/bend rule.
    """
    from archforge.mep.electrical_routes import run_z, target_cell, device_legs, switch_runs
    design = design_circuits(doc)
    runs, boxes = [], []
    points = {e.id: e for e in electrical_points(doc)}
    panel = next((e for e in points.values() if e.params["point_type"] == "panel"), None)
    if panel is None:
        return {**design, "runs": runs, "boxes": boxes, "switch_runs": []}
    px, py = float(panel.params["x"]), float(panel.params["y"])
    for circuit in design["circuits"]:
        members = [points[i] for i in circuit["points"]]
        floor = _floor_of(doc, float(members[0].params["z"]))
        cid, group = circuit["id"], circuit["group"]
        split = {"wall": [], "floor": [], "ceiling": []}
        for e in members:
            split[routing_of(doc, e)].append(e)
        for mode, chosen in split.items():
            if not chosen:
                continue
            z = run_z(doc, floor, mode)
            grid = _Grid(doc, floor, [(float(e.params["x"]), float(e.params["y"])) for e in chosen] + [(px, py)])
            grid.mode = "wall" if mode == "wall" else "floor"
            source = grid.cell(px, py)
            targets = {e.id: target_cell(grid, e, mode) for e in chosen}
            paths, _loads, parent = _grow(grid, source, targets)
            seen = set()
            for tid, path in paths.items():
                chain = []
                c = path[0]
                chain.append(grid.point(c))
                while parent.get(c) is not None:
                    p_ = parent[c]
                    edge = frozenset((c, p_))
                    a, b = grid.point(c), grid.point(p_)
                    if edge not in seen:
                        seen.add(edge)
                        runs.append(((a[0], a[1], z), (b[0], b[1], z), group, cid))
                    chain.append(b)
                    c = p_
                boxes.extend(_pull_boxes(chain, z, cid))
            pp = grid.point(source)
            runs.append(((pp[0], pp[1], mount_z(doc, panel.params)), (pp[0], pp[1], z), group, cid))
            for e in chosen:
                terminal, box = device_legs(doc, e, mode, grid.point(targets[e.id]), z)
                boxes.append((*box, cid))
                runs.extend((a, b, group, cid) for a, b in terminal)
    # The board consumes this same geometry instead of reconstructing switch legs.
    switch_legs, switch_boxes = switch_runs(doc, design, points)
    runs.extend((a, b, "switch", "") for a, b, _sid in switch_legs)
    boxes.extend(switch_boxes)
    runs = [r for r in runs if math.dist(r[0], r[1]) > 1e-6]
    boxes = _merge_boxes(boxes)
    design["report"]["conduits"] = conduit_summary(runs, design["circuits"])
    design["report"]["cable_m"] = round(sum(math.dist(a, b) for a, b, _g, _c in runs), 1)
    design["report"]["boxes"] = {k: sum(1 for b in boxes if b[3] == k) for k in ("junction", "floor", "pull")}
    return {**design, "runs": runs, "boxes": boxes, "switch_runs": switch_legs}


def conduit_summary(runs, circuits):
    """What runs through each conduit: the circuits sharing a stretch, their conductors (L, N, PE each) and
    sections.  ``[{"a", "b", "circuits": [...], "conductors": n, "mm2": {mm²: n}}]`` merged along straight stretches
    with the same circuits, busiest first (owner 18/10: «πόσα καλώδια περνάνε από μέσα;»)."""
    by_id = {c["id"]: c for c in circuits}
    edges = {}
    for a, b, _g, cid in runs:
        if not cid:
            continue
        key = tuple(sorted((tuple(round(v, 3) for v in a), tuple(round(v, 3) for v in b))))
        edges.setdefault(key, set()).add(cid)
    out = []
    for (a, b), cids in edges.items():
        mm2 = {}
        for cid in cids:
            s = float(by_id[cid]["cable_mm2"]) if cid in by_id else 1.5
            mm2[s] = mm2.get(s, 0) + 3
        out.append({"a": a, "b": b, "circuits": sorted(cids, key=lambda c: (len(c), c)), "conductors": 3 * len(cids), "mm2": mm2})
    # Merge consecutive collinear pieces carrying the same circuits (a 20 cm grid makes many short ones).
    merged = []
    for seg in sorted(out, key=lambda s: (tuple(s["circuits"]), s["a"], s["b"])):
        last = merged[-1] if merged else None
        if last and last["circuits"] == seg["circuits"] and last["b"] == seg["a"] and \
                _collinear(last["a"], last["b"], seg["b"]):
            last["b"] = seg["b"]
        else:
            merged.append(dict(seg))
    merged.sort(key=lambda s: (-s["conductors"], s["a"]))
    return merged


def _collinear(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - b[i] for i in range(3)]
    cross = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    return max(abs(x) for x in cross) < 1e-9


_CACHE = {"key": None, "value": None}


def route_cables_cached(doc):
    items = []
    for e in doc.entities.values():
        if e.kind == "electrical_point":
            items.append(("e", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
        elif e.kind == "wall":
            items.append(("w", e.id, tuple(round(float(e.params[k]), 6) for k in ("x1", "y1", "x2", "y2", "z", "thickness"))))
        elif e.kind == "drywall_ceiling":          # hidden lights sit in its cove
            items.append(("d", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    key = (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
           tuple(sorted((k, str(v)) for k, v in doc.room_data.items())) if hasattr(doc, "room_data") else ())
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_cables(doc)
    return _CACHE["value"]


def point_marker_mesh(doc, params):
    """Small box at the point's mounting position (selectable in 3D)."""
    x, y = float(params["x"]), float(params["y"])
    z = mount_z(doc, params)
    if params["point_type"] == "led_strip" and strip_length(params) > 1e-6:
        # The strip itself: a 1 cm × 2 cm bar along its line.
        x2, y2 = float(params["x2"]), float(params["y2"])
        L = strip_length(params)
        ux, uy = (x2 - x) / L, (y2 - y) / L
        nx, ny = -uy * 0.01, ux * 0.01
        c = [(px + sx * nx, py + sx * ny, z + dz) for px, py in ((x, y), (x2, y2)) for sx in (-1, 1) for dz in (0.0, 0.01)]
        quads = [(0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3), (0, 1, 3, 2), (4, 6, 7, 5)]
        return c, [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    s = 0.12 if params["point_type"] == "panel" else 0.06
    h = 0.4 if params["point_type"] == "panel" else 0.06
    c = [(x + dx, y + dy, z + dz) for dx in (-s, s) for dy in (-s / 2, s / 2) for dz in (-h / 2, h / 2)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    return c, tris


CABLE_COLORS = {"lighting": "#e0b400", "sockets": "#e07a00", "kitchen_sockets": "#c2410c", "switch": "#9a8f00",
                "cooker": "#7b2fbf", "water_heater": "#7b2fbf", "air_conditioner": "#7b2fbf",
                "washing_machine": "#7b2fbf", "dishwasher": "#7b2fbf",
                # Ασθενή (drawing convention): data, TV, KNX bus.
                "network": "#0e9aa7", "tv": "#6d28d9", "knx": "#2e7d32"}
