"""Semantic plumbing components and drag/drop snap targets.

This catalogue defines what a component *is* and where it may be attached. It
contains no mandatory quantities, dimensions, prices or regulatory claims.
Those belong to a selected product/assembly or an engineer-reviewed rule.

The catalogue names are cross-checked against current manufacturer product
families (Uponor, Geberit, Caleffi, Watts).  That verification supports the
existence/category of a component only; it does NOT make the component
mandatory in any particular installation.
"""
from __future__ import annotations

import math

from archforge.mep.plumbing import route_plumbing_cached

# Source families used only to document semantic catalogue provenance.
# Detailed product dimensions/compatibility must come from the selected product
# data sheet, not from this module.
CATALOGUE_SOURCES = {
    "uponor_fittings": "Uponor product catalogue — plumbing fittings / valves / manifolds / mounting parts",
    "geberit_valves": "Geberit piping catalogue — pipe valve fittings / shut-off and manifold units",
    "caleffi_domestic": "Caleffi General Product Guide — components for domestic water systems",
    "watts_appliance": "Watts plumbing catalogue — appliance / washing-machine valves and fittings",
}

# key -> (Greek label, allowed host kinds, owner-facing purpose)
# Presence in this dictionary means only that the component is available to be
# selected/modelled. It does not imply a required quantity or engineering rule.
COMPONENTS = {
    # Isolation / service valves
    "angle_stop": ("Γωνιακός διακόπτης", ("point",), "Τοπικό εξάρτημα απομόνωσης σε σύνδεση συσκευής."),
    "straight_stop": ("Ευθύς διακόπτης", ("point",), "Ευθύ εξάρτημα τοπικής απομόνωσης που έχει επιλεγεί για τη σύνδεση."),
    "appliance_valve": ("Βάνα συσκευής", ("point",), "Βάνα απομόνωσης που έχει επιλεγεί για συγκεκριμένη συσκευή."),
    "washing_machine_valve": ("Βάνα πλυντηρίου", ("point",), "Βάνα σύνδεσης/απομόνωσης που έχει επιλεγεί για πλυντήριο."),
    "ball_valve": ("Σφαιρική βάνα", ("point", "pipe", "manifold"), "Σφαιρική βάνα που έχει επιλεγεί για απομόνωση τμήματος."),
    "isolation_valve": ("Βάνα απομόνωσης", ("point", "pipe", "manifold"), "Απομονώνει το επιλεγμένο τμήμα της εγκατάστασης."),
    "manifold_valve": ("Βάνα συλλέκτη", ("manifold",), "Βάνα που έχει επιλεγεί για είσοδο ή έξοδο συλλέκτη."),

    # General fittings
    "union": ("Ρακόρ", ("point", "pipe", "manifold"), "Αποσπώμενη σύνδεση στο επιλεγμένο σημείο."),
    "adapter": ("Αντάπτορας", ("point", "pipe", "manifold"), "Σύνδεση μεταξύ ρητά επιλεγμένων διαφορετικών άκρων."),
    "male_thread_adapter": ("Αντάπτορας αρσενικού σπειρώματος", ("point", "pipe", "manifold"), "Μετάβαση σε αρσενικό σπείρωμα του επιλεγμένου συστήματος."),
    "female_thread_adapter": ("Αντάπτορας θηλυκού σπειρώματος", ("point", "pipe", "manifold"), "Μετάβαση σε θηλυκό σπείρωμα του επιλεγμένου συστήματος."),
    "swivel_adapter": ("Περιστρεφόμενο ρακόρ / αντάπτορας", ("point", "pipe", "manifold"), "Αποσπώμενη περιστρεφόμενη σύνδεση που έχει επιλεγεί."),
    "coupling": ("Σύνδεσμος", ("pipe",), "Σύνδεσμος δύο τμημάτων σωλήνωσης όταν έχει επιλεγεί κατασκευαστικά."),
    "slip_coupling": ("Επισκευαστικός / ολισθαίνων σύνδεσμος", ("pipe",), "Ολισθαίνων σύνδεσμος που έχει επιλεγεί για ένωση ή επισκευή."),
    "reducer": ("Συστολή / μειωτικό", ("pipe", "point", "manifold"), "Μετάβαση μεταξύ δύο επιλεγμένων διαμέτρων."),
    "nipple": ("Μαστός / νίπελ", ("point", "pipe", "manifold"), "Κοντό σπειρωτό στοιχείο σύνδεσης που έχει επιλεγεί."),
    "elbow": ("Γωνία", ("pipe",), "Εξάρτημα αλλαγής διεύθυνσης όταν υπάρχει στην επιλεγμένη λύση."),
    "elbow_adapter": ("Γωνιακός αντάπτορας", ("point", "pipe"), "Γωνιακή μετάβαση προς διαφορετικό άκρο ή σπείρωμα."),
    "wall_plate_elbow": ("Γωνία στήριξης / έξοδος τοίχου", ("point",), "Σταθερό γωνιακό τερματικό σύνδεσης στον τοίχο."),
    "tee": ("Ταφ", ("pipe",), "Εξάρτημα διακλάδωσης όταν υπάρχει στην επιλεγμένη λύση."),
    "reducing_tee": ("Μειωτικό ταφ", ("pipe",), "Διακλάδωση με διαφορετική επιλεγμένη διάμετρο κλάδου."),
    "end_cap": ("Τάπα", ("pipe", "manifold"), "Τάπα σε ρητά επιλεγμένο άκρο ή αχρησιμοποίητη έξοδο."),
    "plug": ("Βιδωτή τάπα", ("point", "pipe", "manifold"), "Σπειρωτή τάπα που έχει επιλεγεί για συγκεκριμένο στόμιο."),

    # Fixture / appliance terminal connections
    "flex_connector": ("Εύκαμπτος σύνδεσμος", ("point",), "Εύκαμπτη τελική σύνδεση που έχει επιλεγεί για τη συσκευή."),
    "wall_outlet": ("Έξοδος τοίχου", ("point",), "Τερματικό σύνδεσης εγκατάστασης προς τη συσκευή."),
    "fixture_connector": ("Σύνδεσμος είδους υγιεινής", ("point",), "Σύνδεση μεταξύ εγκατάστασης και συγκεκριμένου είδους υγιεινής."),
    "cistern_connector": ("Σύνδεσμος καζανακίου", ("point",), "Σύνδεση παροχής προς καζανάκι που έχει επιλεγεί ρητά."),
    "appliance_hose_connector": ("Σύνδεσμος σωλήνα συσκευής", ("point",), "Σύνδεση για εύκαμπτο σωλήνα πλυντηρίου ή άλλης συσκευής."),

    # Manifold / cabinet assembly
    "manifold_connector": ("Ρακόρ / σύνδεσμος συλλέκτη", ("manifold",), "Σύνδεσμος μεταξύ συλλέκτη και σωλήνωσης."),
    "manifold_adapter": ("Αντάπτορας συλλέκτη", ("manifold",), "Αντάπτορας εισόδου ή εξόδου συλλέκτη που έχει επιλεγεί."),
    "manifold_end_cap": ("Τάπα άκρου συλλέκτη", ("manifold",), "Τερματική τάπα συλλέκτη που έχει επιλεγεί."),
    "manifold_cabinet": ("Ερμάριο συλλέκτη", ("manifold",), "Ερμάριο/πίνακας που περιέχει τον επιλεγμένο συλλέκτη."),
    "manifold_mount": ("Στήριγμα συλλέκτη", ("manifold",), "Στήριγμα ή βάση που έχει επιλεγεί για τον συλλέκτη."),

    # Mounting / rough-in
    "mounting_plate": ("Πλάκα στήριξης", ("point",), "Πλάκα στήριξης για τερματικά/εξόδους που έχει επιλεγεί."),
    "mounting_angle": ("Γωνία στήριξης", ("point",), "Γωνιακό εξάρτημα στήριξης που έχει επιλεγεί."),
    "mounting_rail": ("Ράγα στήριξης", ("point", "manifold"), "Ράγα στήριξης για επιλεγμένα υδραυλικά στοιχεία."),
    "rough_in_box": ("Κουτί προεγκατάστασης", ("point",), "Κουτί/βάση προεγκατάστασης για τελική σύνδεση."),
    "cover_plate": ("Πλάκα κάλυψης", ("point", "manifold"), "Πλάκα κάλυψης επιλεγμένου εντοιχισμένου στοιχείου."),
    "support": ("Στήριγμα σωλήνωσης", ("pipe",), "Στήριγμα σωλήνωσης που έχει δηλωθεί στο έργο."),
    "insulation": ("Μόνωση σωλήνωσης", ("pipe",), "Μόνωση που έχει επιλεγεί για συγκεκριμένο τμήμα σωλήνωσης."),

    # Protection / control components
    "filter": ("Φίλτρο / σίτα", ("pipe", "point"), "Φίλτρο ή σίτα που έχει επιλεγεί για το έργο."),
    "strainer": ("Φίλτρο τύπου strainer", ("pipe",), "Φίλτρο σωματιδίων που έχει επιλεγεί στη γραμμή."),
    "check_valve": ("Αντεπίστροφη βαλβίδα", ("pipe", "point"), "Βαλβίδα μονής κατεύθυνσης που έχει επιλεγεί ρητά."),
    "pressure_reducer": ("Μειωτής πίεσης", ("pipe",), "Συσκευή μείωσης/ρύθμισης πίεσης που έχει επιλεγεί."),
    "water_hammer_arrester": ("Αντικρουστικό υδραυλικού πλήγματος", ("pipe", "point"), "Εξάρτημα απόσβεσης υδραυλικού πλήγματος που έχει επιλεγεί."),
    "thermostatic_mixing_valve": ("Θερμοστατική βαλβίδα ανάμιξης", ("pipe", "point"), "Βαλβίδα ανάμιξης θερμού/κρύου νερού που έχει επιλεγεί."),
    "safety_valve": ("Βαλβίδα ασφαλείας", ("point", "pipe"), "Βαλβίδα ασφαλείας μόνο όταν ανήκει στην επιλεγμένη λύση/συσκευή."),
    "safety_group": ("Ομάδα ασφαλείας", ("point",), "Συγκρότημα ασφαλείας μόνο όταν προβλέπεται από επιλεγμένη λύση/προϊόν."),
    "expansion_vessel": ("Δοχείο διαστολής", ("point", "pipe"), "Δοχείο διαστολής που έχει επιλεγεί για το συγκεκριμένο σύστημα."),

    # Water heater / solar connections
    "tank_connector": ("Σύνδεσμος δοχείου / θερμοσίφωνα", ("point",), "Σύνδεση προς επιλεγμένο δοχείο ή θερμοσίφωνα."),
    "solar_connector": ("Σύνδεσμος ηλιακού", ("point",), "Σύνδεση προς επιλεγμένο ηλιακό σύστημα."),
    "fill_drain_cock": ("Κρουνός πλήρωσης / εκκένωσης", ("point", "pipe"), "Κρουνός πλήρωσης ή αποστράγγισης που έχει επιλεγεί στο σύστημα."),
    "pressure_gauge": ("Μανόμετρο", ("point", "pipe"), "Όργανο ένδειξης πίεσης που έχει επιλεγεί."),
    "thermometer": ("Θερμόμετρο", ("point", "pipe"), "Όργανο ένδειξης θερμοκρασίας που έχει επιλεγεί."),
    "flow_meter": ("Παροχόμετρο", ("point", "pipe"), "Όργανο ένδειξης/ρύθμισης παροχής που έχει επιλεγεί."),
}


def component_label(key: str) -> str:
    return COMPONENTS.get(str(key), (str(key), (), ""))[0]


def component_actions():
    """Library rows: label + action tuple. No product claims are encoded."""
    return [(label, ("plumbing_component", key)) for key, (label, _hosts, _why) in COMPONENTS.items()]


def _point_distance(x, y, px, py):
    return math.hypot(float(x) - float(px), float(y) - float(py))


def _segment_projection(x, y, a, b):
    ax, ay = float(a[0]), float(a[1]); bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    den = dx * dx + dy * dy
    t = 0.0 if den <= 1e-12 else max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / den))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(x - qx, y - qy), (qx, qy, float(a[2]) + t * (float(b[2]) - float(a[2])))


def snap_target(doc, component_type: str, x: float, y: float, reach: float = 0.35):
    """Nearest valid plumbing host around plan point; returns a serializable dict.

    Derived pipes/manifolds have no authoritative entity id, so the target stores
    their semantic network/location. This is attachment metadata, not a new
    engineering rule.
    """
    spec = COMPONENTS.get(str(component_type))
    if spec is None:
        return None
    allowed = set(spec[1])
    candidates = []

    if "point" in allowed:
        for e in doc.entities.values():
            if e.kind != "plumbing_point":
                continue
            p = e.params
            d = _point_distance(x, y, p.get("x", 0), p.get("y", 0))
            if d <= reach:
                candidates.append((d, {
                    "host_kind": "point", "host_id": str(e.id),
                    "x": float(p.get("x", 0)), "y": float(p.get("y", 0)), "z": float(p.get("z", 0)),
                    "point_type": str(p.get("point_type", "")),
                }))

    routed = route_plumbing_cached(doc)
    if "manifold" in allowed:
        for index, m in enumerate(routed.get("manifolds", ())):
            d = _point_distance(x, y, m["x"], m["y"])
            if d <= reach:
                candidates.append((d, {
                    "host_kind": "manifold", "host_id": "",
                    "manifold_index": index, "network": str(m.get("system", "")),
                    "outlets": len(m.get("outlets", ())),
                    "x": float(m["x"]), "y": float(m["y"]), "z": float(m["z"]),
                }))

    if "pipe" in allowed:
        for network in ("cold", "hot"):
            for index, (a, b, dia) in enumerate(routed.get(network, ())):
                d, q = _segment_projection(float(x), float(y), a, b)
                if d <= reach:
                    candidates.append((d, {
                        "host_kind": "pipe", "host_id": "",
                        "network": network, "segment_index": index, "diameter": int(dia),
                        "x": q[0], "y": q[1], "z": q[2],
                    }))

    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def accessory_params(component_type: str, target: dict) -> dict:
    """Authoritative plumbing_accessory params for one drag/drop placement."""
    key = str(component_type)
    label, _hosts, why = COMPONENTS[key]
    return {
        "accessory_type": key,
        "quantity": 1.0,
        "unit": "pcs",
        "x": float(target["x"]), "y": float(target["y"]), "z": float(target["z"]),
        "host_kind": str(target["host_kind"]),
        "host_id": str(target.get("host_id", "")),
        "network": str(target.get("network", "")),
        "diameter": target.get("diameter"),
        "manifold_index": target.get("manifold_index"),
        "segment_index": target.get("segment_index"),
        "source_kind": "professional_selection",
        "rule_status": "MODEL_SELECTED",
        "selection_basis": "visual_drag_drop",
        "owner_explanation": why,
        "display_label": label,
    }
