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
import re

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
    # Owner 06/11: «σε πολλούς ορόφους κάθε όροφος πρέπει να έχει υποπίνακα — αυτός είναι κανόνας».
    "subpanel": ("Υποπίνακας ορόφου", "panel", 0, 1.60, "ΥΠ"),
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
        # Measurement queries must not create or migrate persistent room IDs.
        from archforge.architecture.topology import room_faces
        faces = room_faces(doc, z=floor)
    except Exception as exc:
        from archforge.core.notices import not_computed
        not_computed("electrical.room", f"Ηλεκτρολογικά: δεν αναγνωρίστηκαν οι χώροι του ορόφου {floor:+.2f} — τα "
                     "σημεία μένουν χωρίς χώρο", exc=exc)
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


SUBPANEL_RULE = ("κανόνας ιδιοκτήτη 06/11: σε κτίριο με φορτία σε πολλούς ορόφους κάθε όροφος έχει δικό του "
                 "υποπίνακα, τροφοδοτούμενο από τον γενικό πίνακα")


def boards(doc):
    """``{floor z: board entity}``: the main panel on its storey, a «Υποπίνακας ορόφου» on each other storey that has
    one (the first, if two were placed); a storey without one is fed from the main panel — and said."""
    points = electrical_points(doc)
    panel = next((e for e in points if e.params["point_type"] == "panel"), None)
    out = {}
    if panel is not None:
        out[_floor_of(doc, float(panel.params["z"]))] = panel
    for e in sorted((e for e in points if e.params["point_type"] == "subpanel"), key=lambda e: e.id):
        out.setdefault(_floor_of(doc, float(e.params["z"])), e)
    return out


def load_floors(doc):
    """Storeys that have electrical loads (not counting the boards themselves)."""
    return sorted({_floor_of(doc, float(e.params["z"])) for e in electrical_points(doc)
                   if POINT_TYPES[e.params["point_type"]][1] in CIRCUIT_RULES})


def missing_subpanels(doc):
    """Storeys with loads, other than the main panel's, that have no «Υποπίνακας ορόφου» (the rule)."""
    points = electrical_points(doc)
    panel = next((e for e in points if e.params["point_type"] == "panel"), None)
    if panel is None:
        return []
    have = boards(doc)
    floors = load_floors(doc)
    if len(floors) < 2 and (not floors or floors[0] == _floor_of(doc, float(panel.params["z"]))):
        return []
    return [f for f in floors if f not in have]


def subpanel_command(doc):
    """«Υποπίνακες ορόφων (αυτόματα)»: a «Υποπίνακας ορόφου» on every storey with loads that has none, where the riser
    from the main panel reaches it (a wall both storeys share when there is one) — one undo; None when none is missing."""
    from archforge.core.commands import AddEntities
    from archforge.core.model import Entity
    points = electrical_points(doc)
    panel = next((e for e in points if e.params["point_type"] == "panel"), None)
    if panel is None:
        return None
    px, py = float(panel.params["x"]), float(panel.params["y"])
    pf = _floor_of(doc, float(panel.params["z"]))
    new = []
    for floor in missing_subpanels(doc):
        q = _riser(doc, pf, floor, px, py) or (px, py)
        new.append(Entity("electrical_point", {"point_type": "subpanel", "x": float(q[0]), "y": float(q[1]),
                                               "z": float(floor)}, name=f"Υποπίνακας ορόφου {floor:+.2f}".replace(".", ",")))
    return AddEntities(new) if new else None


def feeder_sizing(watts):
    """Breaker and copper section of a sub-board feeder from its storey's installed load (single phase, a design
    default to check: Ib = P / 230, In the next standard rating ≥ Ib, section with Iz ≥ In in method B1)."""
    ib = max(float(watts), 0.0) / VOLTAGE
    rating = next((r for r in (16, 20, 25, 32, 40, 50, 63, 80) if r >= ib), 80)
    section = {16: 2.5, 20: 4.0, 25: 6.0, 32: 6.0, 40: 10.0, 50: 10.0, 63: 16.0, 80: 25.0}[rating]
    return rating, section, round(ib, 1)


def design_circuits(doc, keep_numbers=True):
    """Group points into circuits: ``{"circuits": [...], "switch_links": [...], "report": {...}}``.

    Σ2 (κριτική v5): a point that carries a kept number (``params["circuit"]``, written by ``keep_circuit_numbers``)
    stays in that circuit with that number; only new points are grouped, first into a kept circuit of the same kind
    and room with room left, otherwise into new circuits numbered after the highest kept one.  ``keep_numbers=False``
    groups everything afresh (Επαναρίθμηση).

    Once per project state (bots 07/11: the click, the project tree and the assistant asked for the same circuits —
    three times per luminaire); each caller gets its own copy.
    """
    from archforge.core.state_memo import remembered
    return remembered("design_circuits", doc, (bool(keep_numbers),), lambda: _design_circuits(doc, keep_numbers))


def _design_circuits(doc, keep_numbers=True):
    points = electrical_points(doc)
    panel = next((e for e in points if e.params["point_type"] == "panel"), None)
    out = {"circuits": [], "switch_links": [], "report": {"unassigned": [], "warnings": [], "provenance": PROVENANCE}}
    loads = [e for e in points if POINT_TYPES[e.params["point_type"]][1] in CIRCUIT_RULES]
    if panel is None:
        out["report"]["unassigned"] = [e.id for e in loads]
        if loads:
            out["report"]["warnings"].append("Δεν υπάρχει ηλεκτρικός πίνακας: τα κυκλώματα δεν σχηματίζονται")
        return out
    board_of = boards(doc)
    for floor in missing_subpanels(doc):
        out["report"]["warnings"].append(
            f"Όροφος {floor:+.2f}: χρειάζεται «Υποπίνακας ορόφου» ({SUBPANEL_RULE}) — Εγκαταστάσεις ▸ "
            "Ηλεκτρολογικά ▸ Υποπίνακες ορόφων (αυτόματα)".replace(".", ","))
    by_group = {}
    for e in loads:
        if e.params["point_type"] in DATASHEET_TYPES and point_load_w(e.params) <= 0:
            out["report"]["warnings"].append(
                f"{POINT_TYPES[e.params['point_type']][0]} {e.id[:6]}: εισάγετε ισχύ από το φύλλο του φωτιστικού "
                f"({'W/m' if e.params['point_type'] == 'led_strip' else 'W'}) — μετράει 0 W")
        group = POINT_TYPES[e.params["point_type"]][1]
        floor = _floor_of(doc, float(e.params["z"]))
        room = _room_of(doc, float(e.params["x"]), float(e.params["y"]), floor) or "—"
        board = board_of.get(floor, panel).id                # its storey's sub-board, else the main panel
        by_group.setdefault((group, board), []).append((room, floor, e))
    used = set()
    if keep_numbers:
        for e in loads:
            m = re.match(r"Κ(\d+)$", str(e.params.get("circuit", "")))
            if m:
                used.add(int(m.group(1)))
    number = max(used, default=0)
    claimed = {}                                   # kept number → its group (a number belongs to one group)
    made = []                                      # (number, circuit)
    for group, board_id in [(g, b) for g in GROUP_ORDER for b in sorted({b for (gg, b) in by_group if gg == g})]:
        members = by_group.get((group, board_id), [])
        if not members:
            continue
        label, breaker, cable, limit = CIRCUIT_RULES[group]
        # Same room (and storey) first, then by distance from the panel.
        px, py = float(panel.params["x"]), float(panel.params["y"])
        members.sort(key=lambda m: (m[1], m[0], math.hypot(float(m[2].params["x"]) - px, float(m[2].params["y"]) - py)))
        kept, rest = {}, []
        for room, floor, e in members:
            m = re.match(r"Κ(\d+)$", str(e.params.get("circuit", ""))) if keep_numbers else None
            if m and claimed.setdefault(int(m.group(1)), group) == group:
                kept.setdefault(int(m.group(1)), []).append((room, floor, e))
            else:
                rest.append((room, floor, e))
        if kept:
            # A new point joins a kept circuit of its room while that circuit has room left.
            fresh, rest = rest, []
            for room, floor, e in fresh:
                home = next((k for k, pts in sorted(kept.items()) if limit > 1 and len(pts) < limit
                             and (pts[0][0], pts[0][1]) == (room, floor)), None)
                if home is None:
                    rest.append((room, floor, e))
                else:
                    kept[home].append((room, floor, e))
        chunks, current, current_room = [], [], None
        for room, floor, e in rest:
            # Rooms are not mixed in lighting/socket circuits unless a room is small.
            if current and (len(current) >= limit or (limit > 1 and (room, floor) != current_room and len(current) >= limit // 2)):
                chunks.append(current)
                current = []
            current.append(e)
            current_room = (room, floor)
        if current:
            chunks.append(current)
        if group == "lighting" and not kept and len(chunks) == 1 and len(chunks[0]) >= 2:
            # At least two lighting circuits (owner 15/10): split at the room change nearest the middle.
            only = chunks[0]
            rooms_of = [(r, f) for r, f, e in rest]
            cuts = [k for k in range(1, len(only)) if rooms_of[k] != rooms_of[k - 1]] or [len(only) // 2]
            k = min(cuts, key=lambda c: (abs(c - len(only) / 2), c))
            chunks = [only[:k], only[k:]]
        numbered = [(k, [e for _r, _f, e in pts]) for k, pts in sorted(kept.items())]
        for chunk in chunks:
            number += 1
            numbered.append((number, chunk))
        for num, chunk in numbered:
            watts = sum(point_load_w(e.params) for e in chunk)
            amps = watts / VOLTAGE
            dedicated = limit == 1
            # Shared circuits keep 20 % margin; a dedicated line must carry its appliance.
            ok = amps <= (breaker if dedicated else 0.8 * breaker)
            circuit = {"id": f"Κ{num}", "group": group, "label": label, "breaker_a": breaker, "cable_mm2": cable,
                       "points": [e.id for e in chunk], "load_w": round(watts), "current_a": round(amps, 1), "ok": ok,
                       "board": board_id}
            if not ok:
                fix = "μεγαλύτερη ασφάλεια/διατομή" if dedicated else "χωρίστε το κύκλωμα"
                limit_txt = f"{breaker} A" if dedicated else f"80% της ασφάλειας {breaker} A"
                out["report"]["warnings"].append(f"{circuit['id']} {label}: {amps:.1f} A > {limit_txt} — {fix} "
                                                 "[κανόνας μη επαληθευμένος]")
            made.append((num, circuit))
    out["circuits"] = [c for _n, c in sorted(made, key=lambda t: t[0])]
    # One feeder per sub-board, from the main panel up the riser (sized by its storey's installed load).
    feeders = []
    for k, (floor, sub) in enumerate(sorted((f, b) for f, b in board_of.items() if b.id != panel.id), 1):
        watts = sum(c["load_w"] for c in out["circuits"] if c.get("board") == sub.id)
        rating, section, ib = feeder_sizing(watts)
        feeders.append({"id": f"Τ{k}", "group": "feeder", "label": f"Τροφοδοσία υποπίνακα ορόφου {floor:+.2f}".replace(".", ","),
                        "breaker_a": rating, "cable_mm2": section, "points": [sub.id], "load_w": round(watts),
                        "current_a": ib, "ok": True, "board": panel.id, "feeds": sub.id})
    out["feeders"] = feeders
    out["report"]["numbers_kept"] = bool(used)
    # Switches and dimmers control the lights of their automation group, otherwise of their room (same storey).
    lights = [(e, _room_of(doc, float(e.params["x"]), float(e.params["y"]), _floor_of(doc, float(e.params["z"]))),
               _floor_of(doc, float(e.params["z"]))) for e in points if POINT_TYPES[e.params["point_type"]][1] == "lighting"]
    # Groups that have their own switch/dimmer; their lights leave the room's plain switch.
    grouped = {str(e.params.get("automation_group", "")) for e in points if e.params["point_type"] in SWITCH_TYPES} - {""}
    # Owner 25/10: a switch linked to particular luminaires in Ιδιότητες («controls») controls exactly those; they
    # leave the automatic room/group switching.
    light_ids = {l.id for l, _r, _f in lights}
    linked = {i for e in points if e.params["point_type"] in SWITCH_TYPES for i in e.params.get("controls", ()) if i in light_ids}
    for sw in (e for e in points if e.params["point_type"] in SWITCH_TYPES):
        floor = _floor_of(doc, float(sw.params["z"]))
        room = _room_of(doc, float(sw.params["x"]), float(sw.params["y"]), floor)
        group = str(sw.params.get("automation_group", ""))
        if "controls" in sw.params:
            controlled = [i for i in sw.params["controls"] if i in light_ids]
        elif group:
            controlled = [l.id for l, _r, _f in lights if str(l.params.get("automation_group", "")) == group]
        else:
            controlled = [l.id for l, lroom, lfloor in lights if lfloor == floor and lroom == room and room is not None
                          and str(l.params.get("automation_group", "")) not in grouped and l.id not in linked]
        if not controlled and "controls" not in sw.params:
            near = sorted((math.hypot(float(l.params["x"]) - float(sw.params["x"]), float(l.params["y"]) - float(sw.params["y"])), l.id)
                          for l, _r, lf in lights if lf == floor)
            controlled = [near[0][1]] if near else []
        out["switch_links"].append({"switch": sw.id, "lights": controlled, "dimmer": sw.params["point_type"] == "dimmer",
                                    "group": group})
    _switching_schemes(out, {e.id: e for e in points})
    return out


SCHEMES = {"single": "Απλός", "two_way": "Αλέ-ρετούρ (κομιτατέρ)", "intermediate": "Αντιστροφέας (ενδιάμεσος)"}


def keep_circuit_numbers(doc, renumber=False):
    """One undo: every load point keeps the number of the circuit it is in now («Κράτα την αρίθμηση»); with
    ``renumber`` the circuits are grouped and numbered afresh first («Επαναρίθμηση»).  None when nothing changes."""
    from archforge.core.commands import UpdateEntities
    design = design_circuits(doc, keep_numbers=not renumber)
    number_of = {pid: c["id"] for c in design["circuits"] for pid in c["points"]}
    changes = {}
    for e in electrical_points(doc):
        want = number_of.get(e.id, "")
        if str(e.params.get("circuit", "")) != want and (want or "circuit" in e.params):
            changes[e.id] = {"circuit": want}
    return UpdateEntities(changes) if changes else None


def _switching_schemes(out, points):
    """Several switches for the same luminaires = one multi-way switching: the two ends two-way (αλέ-ρετούρ), the ones
    between intermediate (αντιστροφέας); ``partners`` is the chain the travellers run along (ordered by distance)."""
    links = out["switch_links"]
    by_set = {}
    for link in links:
        link.update(scheme="single", partners=[])
        if link["lights"]:
            by_set.setdefault(frozenset(link["lights"]), []).append(link)
    for same in by_set.values():
        if len(same) < 2:
            continue
        # chain: start at the switch farthest from the others, then nearest neighbour (no crossing back)
        pos = {l["switch"]: (float(points[l["switch"]].params["x"]), float(points[l["switch"]].params["y"])) for l in same}
        start = max(same, key=lambda l: sum(math.dist(pos[l["switch"]], pos[o["switch"]]) for o in same))
        chain, rest = [start], [l for l in same if l is not start]
        while rest:
            nxt = min(rest, key=lambda l: math.dist(pos[chain[-1]["switch"]], pos[l["switch"]]))
            chain.append(nxt); rest.remove(nxt)
        ids = [l["switch"] for l in chain]
        for k, link in enumerate(chain):
            link["scheme"] = "two_way" if k in (0, len(chain) - 1) else "intermediate"
            link["partners"] = ids
        if any(l["dimmer"] for l in chain):
            out["report"]["warnings"].append(
                "Ροοστάτης σε πολλαπλή αφή: χρειάζεται ροοστάτης για αλέ-ρετούρ ή μπουτόν με ρελέ — προς έλεγχο ηλεκτρολόγου")


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
    from archforge.mep.electrical_routes import avoid_frame, layered, run_z, target_cell, device_legs, switch_runs
    design = design_circuits(doc)
    runs, boxes = [], []
    points = {e.id: e for e in electrical_points(doc)}
    panel = next((e for e in points.values() if e.params["point_type"] == "panel"), None)
    if panel is None:
        return {**design, "runs": runs, "boxes": boxes, "switch_runs": []}
    px, py = float(panel.params["x"]), float(panel.params["y"])
    panel_floor = _floor_of(doc, float(panel.params["z"]))
    avoid = avoid_frame(doc)                 # owner 06/11: keep out of columns / beams unless cast-in is allowed
    # Bots 06/11: every new socket re-routed every circuit (~2 s per click in a 450-element house). Each circuit's runs
    # are remembered against what they read — its own points, the building (walls, frame, ceilings, storeys, rooms) and
    # the panel's settings — so a change routes only the circuits it touches.
    geom = _geometry_key(doc)
    panel_key = tuple(sorted((k, str(v)) for k, v in panel.params.items()))
    if len(_CIRCUIT_MEMO) > 4000:
        _CIRCUIT_MEMO.clear()
    main = panel
    for circuit in design["circuits"] + design.get("feeders", []):
        # Each circuit from its own board: its storey's sub-board, or the main panel (feeders: main → sub-board).
        panel = points.get(circuit.get("board")) or main
        px, py = float(panel.params["x"]), float(panel.params["y"])
        panel_floor = _floor_of(doc, float(panel.params["z"]))
        members = [points[i] for i in circuit["points"]]
        ckey = (geom, panel_key, tuple(sorted((k, str(v)) for k, v in panel.params.items())), circuit["id"],
                circuit["group"], tuple((e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))) for e in members))
        hit = _CIRCUIT_MEMO.get(ckey)
        if hit is not None:
            runs.extend(hit[0]); boxes.extend(hit[1])
            if hit[2]:
                design["report"].setdefault("warnings", []).extend(hit[2])
            continue
        n_runs, n_boxes, n_warn = len(runs), len(boxes), len(design["report"].get("warnings", []))
        floor = _floor_of(doc, float(members[0].params["z"]))
        cid, group = circuit["id"], circuit["group"]
        split = {"wall": [], "floor": [], "ceiling": []}
        for e in members:
            split[routing_of(doc, e)].append(e)
        # Another storey than the panel's (owner 29/10: «οι σωληνώσεις στον αέρα — να ακολουθήσει το κτίριο»): from the
        # panel inside its own storey's walls to a riser in a wall both storeys share, up inside it; the storey's runs
        # start at the riser — never at the panel's plan position, which may lie outside that storey.
        riser = None
        if abs(floor - panel_floor) > 1e-4:
            riser = _riser(doc, panel_floor, floor, px, py)
        if riser is not None:
            low_z = run_z(doc, panel_floor, "wall")
            low = _Grid(doc, panel_floor, [(px, py), riser])
            low.mode = "wall"
            lg = None
            if avoid:
                lg, low_z = layered(doc, low, "wall", panel_floor, low_z, [low.cell(px, py), low.cell(*riser)])
            g = lg or low
            start, goal = (g.cell(*riser), g.cell(px, py))
            path = g.route(start, {goal})
            if path is None:
                # Boxed in by the frame (bots 06/11: this raised, and Επιμέτρηση / PDF / Φέρων with it): the storey is
                # still fed — on the plain grid, said as a crossing to agree with the structural engineer.
                design["report"].setdefault("warnings", []).append(
                    f"{cid}: η σύνδεση πίνακα → κατακόρυφη όδευση ορόφου δεν βρίσκει δρόμο έξω από το φέρον — "
                    "περνά από κολόνα / δοκάρι: χιτώνιο με έγκριση στατικού (Λίστες ▸ Χιτώνια / προσωλήνωση)")
                g, lg = low, None
                start, goal = (g.cell(*riser), g.cell(px, py))
                path = g.route(start, {goal})
            chain = [g.point(c) for c in path]
            xyz = [lg.xyz(c) for c in path] if lg else [(*p_, low_z) for p_ in chain]
            for a, b in zip(xyz, xyz[1:]):
                runs.append((a, b, group, cid))
            boxes.extend(_pull_boxes(chain, low_z, cid))
            pp = low.point(low.cell(px, py))
            runs.append(((pp[0], pp[1], mount_z(doc, panel.params)), (pp[0], pp[1], low_z), group, cid))
            rx, ry = low.point(low.cell(*riser))
            from archforge.mep.electrical_routes import routed_z
            top = max(routed_z(doc, floor, mode, avoid) for mode, chosen in split.items() if chosen)
            runs.append(((rx, ry, low_z), (rx, ry, top), group, cid))
        for mode, chosen in split.items():
            if not chosen:
                continue
            z = run_z(doc, floor, mode)
            z_plain = z
            sx, sy = (rx, ry) if riser is not None else (px, py)
            grid = _Grid(doc, floor, [(float(e.params["x"]), float(e.params["y"])) for e in chosen] + [(sx, sy)])
            grid.mode = "wall" if mode == "wall" else "floor"
            grid.doc, grid.floor = doc, floor                   # target_cell keeps a ceiling feed out of the frame
            base_targets = {e.id: target_cell(grid, e, mode) for e in chosen}
            lg = None
            if avoid:
                lg, z = layered(doc, grid, mode, floor, z, [grid.cell(sx, sy), *base_targets.values()])
            g = lg or grid
            source = g.cell(sx, sy)
            # Bots 06/11: a device whose wall run would be inside a beam (wall under the beam) is fed from the floor
            # — before, its leg rose into the concrete where no run could reach it, silently.
            from_floor = {k for k, c in base_targets.items() if lg is not None and lg.two and tuple(c) in lg.core}
            targets = {k: (*c, 1 if k in from_floor else 0) if lg else c for k, c in base_targets.items()}
            paths, _loads, parent = _grow(g, source, targets)
            missing = [k for k in targets if k not in paths and k not in from_floor]
            if missing and lg is not None and lg.two:          # boxed in by the frame on the wall: from the floor
                from_floor |= set(missing)
                targets = {k: (*base_targets[k], 1 if k in from_floor else 0) for k in base_targets}
                paths, _loads, parent = _grow(g, source, targets)
            boxed = [e for e in chosen if e.id not in paths]
            if boxed and lg is not None:
                # Bots 06/11 (a 3-storey frame): avoiding it left dozens of points unconnected. Then the circuit is
                # routed as without avoidance — every point fed — and said once: its crossings need sleeves agreed
                # with the structural engineer (Λίστες ▸ Χιτώνια / προσωλήνωση lists them).
                design["report"].setdefault("warnings", []).append(
                    f"{cid}: {len(boxed)} σημεία δεν φτάνουν παρακάμπτοντας το φέρον — το κύκλωμα περνά από κολόνα / "
                    "δοκάρι: χιτώνια με έγκριση στατικού (Λίστες ▸ Χιτώνια / προσωλήνωση) ή μετακίνηση των σημείων")
                lg, g, z, from_floor = None, grid, z_plain, set()
                source = grid.cell(sx, sy)
                targets = dict(base_targets)
                paths, _loads, parent = _grow(grid, source, targets)
            for e in chosen:
                if e.id not in paths:
                    design["report"].setdefault("warnings", []).append(
                        f"{cid}: «{e.name}» (x {float(e.params['x']):.2f}, y {float(e.params['y']):.2f}) δεν συνδέθηκε")
            at = (lambda c: lg.xyz(c)) if lg else (lambda c: (*grid.point(c), z))
            seen = set()
            for tid, path in paths.items():
                chain = []
                c = path[0]
                chain.append(g.point(c))
                while parent.get(c) is not None:
                    p_ = parent[c]
                    edge = frozenset((c, p_))
                    if edge not in seen:
                        seen.add(edge)
                        runs.append((at(c), at(p_), group, cid))
                    chain.append(g.point(p_))
                    c = p_
                boxes.extend(_pull_boxes(chain, z, cid))
            pp = g.point(source)
            if riser is None:
                runs.append(((pp[0], pp[1], mount_z(doc, panel.params)), (pp[0], pp[1], z), group, cid))
            elif abs(pp[0] - rx) > 1e-6 or abs(pp[1] - ry) > 1e-6:      # the two grids round the riser apart
                runs.append(((rx, ry, z), (pp[0], pp[1], z), group, cid))
            for e in chosen:
                if e.id not in paths:
                    continue                                   # said in the warnings, no leg into the concrete
                if e.id in from_floor:
                    terminal, box = device_legs(doc, e, "floor", g.point(targets[e.id]), lg.z[1])
                else:
                    terminal, box = device_legs(doc, e, mode, g.point(targets[e.id]), z)
                boxes.append((*box, cid))
                runs.extend((a, b, group, cid) for a, b in terminal)
        _CIRCUIT_MEMO[ckey] = (runs[n_runs:], boxes[n_boxes:], list(design["report"].get("warnings", [])[n_warn:]))
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


def _riser(doc, lower, upper, px, py):
    """Plan point of the vertical run between storeys ``lower`` and ``upper``: on a wall of both (stacked walls),
    nearest the panel; else on the upper storey's walls nearest the panel; None without walls up there."""
    def walls_at(z):
        return [w for w in doc.entities.values() if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - z) < 0.05]
    up, down = walls_at(upper), walls_at(lower)
    if not up:
        return None
    candidates = []
    beside = []                 # 10 cm off each face of the wall: a riser box next to it (when beams sit on the walls)
    for w in up:
        p = w.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(L / CELL))
        on = [(x1 + (x2 - x1) * k / steps, y1 + (y2 - y1) * k / steps) for k in range(steps + 1)]
        candidates += on
        if L > 1e-9:
            off = float(p.get("thickness", 0.2)) / 2 + 0.10
            nx, ny = -(y2 - y1) / L * off, (x2 - x1) / L * off
            beside += [(x + sx * nx, y + sx * ny) for x, y in on for sx in (1, -1)]

    def on_lower(q):
        return any(_dist_to_segment(w, *q) <= float(w.params.get("thickness", 0.2)) / 2 + 1e-6 for w in down)
    from archforge.mep.electrical_routes import avoid_frame
    if avoid_frame(doc):                                    # owner 06/11: the vertical run in the brick, not a column
        from archforge.coordination.clash import structure
        # Bots 06/11: a beam too — the riser crosses the slab zone between the storeys, where the beams are; inside
        # one it boxed in a whole storey (its own cell concrete at the run height: no circuit could reach it).
        frame = [b for b in structure(doc) if b.z1 > lower - 1e-6 and b.z0 < upper + 3.5]

        def in_frame(q):
            return any(abs(u) <= b.hu + 0.05 and abs(v) <= b.hv + 0.05 for b in frame for u, v in [b.local(*q)])
        clear = [q for q in candidates if not in_frame(q)]
        candidates = clear or [q for q in beside if not in_frame(q)] or candidates
    stacked = [q for q in candidates if on_lower(q)]
    return min(stacked or candidates, key=lambda q: (math.hypot(q[0] - px, q[1] - py), q))


def _dist_to_segment(w, x, y):
    p = w.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    dx, dy = x2 - x1, y2 - y1
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / ((dx * dx + dy * dy) or 1.0)))
    return math.hypot(x - x1 - t * dx, y - y1 - t * dy)


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


_CIRCUIT_MEMO = {}


def _geometry_key(doc):
    """What a circuit's runs read of the building besides its own points."""
    items = []
    for e in doc.entities.values():
        if e.kind in ("wall", "structural_column", "structural_beam", "drywall_ceiling", "room_floor", "room_roof"):
            items.append((e.kind, e.id, e.visible, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    return hash((tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
                 repr(getattr(doc, "room_data", None)), repr(getattr(doc, "view_layers", None) and None)))


def route_cables_if_cached(doc):
    """The routing already computed for this very model, else None — for readers that must not route on their own
    (the assistant after every change: bots 06/11, 1,2 s per click)."""
    return _CACHE["value"] if _CACHE["key"] is not None and _CACHE["key"] == _route_key(doc) else None


def _route_key(doc):
    items = []
    for e in doc.entities.values():
        if e.kind == "electrical_point":
            items.append(("e", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
        elif e.kind == "wall":
            items.append(("w", e.id, tuple(round(float(e.params[k]), 6) for k in ("x1", "y1", "x2", "y2", "z", "thickness"))))
        elif e.kind == "drywall_ceiling":          # hidden lights sit in its cove
            items.append(("d", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
        elif e.kind in ("structural_column", "structural_beam"):   # the runs go round the frame (06/11)
            items.append(("s", e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    return (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
            tuple(sorted((k, str(v)) for k, v in doc.room_data.items())) if hasattr(doc, "room_data") else ())


def route_cables_cached(doc):
    key = _route_key(doc)
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
    board = params["point_type"] in ("panel", "subpanel")
    s = 0.12 if board else 0.06
    h = 0.4 if board else 0.06
    c = [(x + dx, y + dy, z + dz) for dx in (-s, s) for dy in (-s / 2, s / 2) for dz in (-h / 2, h / 2)]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    tris = [t for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    return c, tris


CABLE_COLORS = {"lighting": "#e0b400", "sockets": "#e07a00", "kitchen_sockets": "#c2410c", "switch": "#9a8f00",
                "cooker": "#7b2fbf", "water_heater": "#7b2fbf", "air_conditioner": "#7b2fbf",
                "washing_machine": "#7b2fbf", "dishwasher": "#7b2fbf",
                # Ασθενή (drawing convention): data, TV, KNX bus.
                "network": "#0e9aa7", "tv": "#6d28d9", "knx": "#2e7d32"}


# -- switches linked from the luminaire's Ιδιότητες (owner 25/10) ---------------------------------------------------
def switches_of(doc, light_id):
    """The switch links (with ``scheme``/``partners``) that control this luminaire."""
    return [l for l in route_cables_cached(doc)["switch_links"] if light_id in l["lights"]]


def link_switch_changes(doc, light_id, switch_id, mode="same"):
    """``{switch id: {"controls": [...]}}`` for a new switch at ``switch_id``.

    ``same``: another place of the luminaire's existing switching (αλέ-ρετούρ, a third place → αντιστροφέας) — the
    new switch takes the lights of the existing one, which keeps them explicitly. ``own``: a switch only for this
    luminaire; it leaves the others. The automatic room switching is frozen into ``controls`` where it is touched,
    so nothing else moves.
    """
    existing = switches_of(doc, light_id)
    changes = {}
    if mode == "same" and existing:
        lights = list(existing[0]["lights"])
        for link in existing:
            if link["lights"] == lights:
                changes[link["switch"]] = {"controls": lights}
        changes[switch_id] = {"controls": lights}
        return changes
    for link in existing:
        changes[link["switch"]] = {"controls": [i for i in link["lights"] if i != light_id]}
    changes[switch_id] = {"controls": [light_id]}
    return changes


def unlink_switch_changes(doc, light_id, switch_id):
    link = next((l for l in switches_of(doc, light_id) if l["switch"] == switch_id), None)
    if link is None:
        return {}
    return {switch_id: {"controls": [i for i in link["lights"] if i != light_id]}}
