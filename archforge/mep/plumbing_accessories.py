"""Explicit plumbing accessories for model quantities and quotes.

Accessories are first-class BOM items. This module never infers hidden parts
from custom or trade habits. A valve, cabinet, fitting, insulation item or
connector is counted only when it exists as a ``plumbing_accessory`` entity or
is emitted by an explicitly selected, sourced connection assembly.

This makes the quote explainable to both the professional and the owner while
respecting ArchForge's NO UNSOURCED ENGINEERING CONSTANTS rule.
"""
from __future__ import annotations

from collections import defaultdict

from archforge.mep.trade_costing import QuantityLine

# Semantic catalogue only: labels/purpose, not required quantities or prices.
# Presence in this dictionary NEVER means that a part is mandatory. Quantities
# come only from explicit model entities or selected connection assemblies.
ACCESSORY_TYPES = {
    "isolation_valve": ("Βάνα απομόνωσης", "Επιτρέπει την απομόνωση του επιλεγμένου τμήματος του δικτύου για έλεγχο ή εργασία."),
    "mini_valve": ("Βανάκι σημείου", "Τοπικό εξάρτημα απομόνωσης που έχει επιλεγεί για το συγκεκριμένο σημείο."),
    "angle_stop": ("Γωνιακός διακόπτης", "Γωνιακός διακόπτης που έχει επιλεγεί ρητά για τη συγκεκριμένη τελική σύνδεση."),
    "straight_stop": ("Ευθύς διακόπτης", "Ευθύς διακόπτης που έχει επιλεγεί ρητά για τη συγκεκριμένη τελική σύνδεση."),
    "appliance_valve": ("Βάνα συσκευής", "Βάνα που έχει επιλεγεί ρητά για την απομόνωση της συγκεκριμένης συσκευής."),
    "washing_machine_valve": ("Βάνα πλυντηρίου", "Βάνα σύνδεσης/απομόνωσης που έχει επιλεγεί για πλυντήριο."),
    "ball_valve": ("Σφαιρική βάνα", "Σφαιρική βάνα που έχει επιλεγεί ρητά για απομόνωση τμήματος."),
    "manifold_valve": ("Βάνα συλλέκτη", "Βάνα που έχει επιλεγεί ρητά για είσοδο ή έξοδο του συγκεκριμένου συλλέκτη."),
    "manifold_connector": ("Ρακόρ / σύνδεσμος συλλέκτη", "Σύνδεσμος που έχει επιλεγεί ρητά μεταξύ συλλέκτη και σωλήνωσης."),
    "manifold_adapter": ("Αντάπτορας συλλέκτη", "Αντάπτορας εισόδου ή εξόδου συλλέκτη που έχει επιλεγεί."),
    "manifold_end_cap": ("Τάπα άκρου συλλέκτη", "Τερματική τάπα συλλέκτη που έχει επιλεγεί."),
    "manifold_cabinet": ("Πίνακας / ερμάριο υδροληψίας", "Περιέχει και προστατεύει τον επιλεγμένο συλλέκτη και τα συνδεδεμένα εξαρτήματα."),
    "manifold_mount": ("Στήριγμα συλλέκτη", "Στήριγμα ή βάση που έχει επιλεγεί για τον συλλέκτη."),
    "union": ("Ρακόρ", "Αποσπώμενη σύνδεση που έχει επιλεγεί στο συγκεκριμένο σημείο της εγκατάστασης."),
    "adapter": ("Αντάπτορας", "Σύνδεση μεταξύ των επιλεγμένων διαφορετικών άκρων ή συστημάτων."),
    "male_thread_adapter": ("Αντάπτορας αρσενικού σπειρώματος", "Μετάβαση σε αρσενικό σπείρωμα του επιλεγμένου συστήματος."),
    "female_thread_adapter": ("Αντάπτορας θηλυκού σπειρώματος", "Μετάβαση σε θηλυκό σπείρωμα του επιλεγμένου συστήματος."),
    "swivel_adapter": ("Περιστρεφόμενο ρακόρ / αντάπτορας", "Αποσπώμενη περιστρεφόμενη σύνδεση που έχει επιλεγεί."),
    "coupling": ("Σύνδεσμος", "Εξάρτημα σύνδεσης δύο τμημάτων σωλήνωσης που έχει δηλωθεί στο μοντέλο."),
    "slip_coupling": ("Επισκευαστικός / ολισθαίνων σύνδεσμος", "Ολισθαίνων σύνδεσμος που έχει επιλεγεί για ένωση ή επισκευή."),
    "reducer": ("Συστολή / μειωτικό", "Μετάβαση μεταξύ δύο επιλεγμένων διαμέτρων."),
    "nipple": ("Μαστός / νίπελ", "Κοντό σπειρωτό στοιχείο σύνδεσης που έχει επιλεγεί."),
    "elbow": ("Γωνία", "Εξάρτημα αλλαγής διεύθυνσης που υπάρχει στη συγκεκριμένη κατασκευαστική λύση."),
    "elbow_adapter": ("Γωνιακός αντάπτορας", "Γωνιακή μετάβαση προς διαφορετικό άκρο ή σπείρωμα."),
    "wall_plate_elbow": ("Γωνία στήριξης / έξοδος τοίχου", "Σταθερό γωνιακό τερματικό σύνδεσης στον τοίχο."),
    "tee": ("Ταφ", "Εξάρτημα διακλάδωσης που υπάρχει στη συγκεκριμένη κατασκευαστική λύση."),
    "reducing_tee": ("Μειωτικό ταφ", "Διακλάδωση με διαφορετική επιλεγμένη διάμετρο κλάδου."),
    "end_cap": ("Τάπα", "Τάπα που έχει επιλεγεί ρητά για συγκεκριμένο άκρο ή αχρησιμοποίητη έξοδο."),
    "plug": ("Βιδωτή τάπα", "Σπειρωτή τάπα που έχει επιλεγεί για συγκεκριμένο στόμιο."),
    "flex_connector": ("Εύκαμπτος σύνδεσμος", "Εύκαμπτη σύνδεση που έχει επιλεγεί ρητά μεταξύ εγκατάστασης και συσκευής."),
    "flexible_connector": ("Εύκαμπτος σύνδεσμος", "Εύκαμπτη σύνδεση που έχει επιλεγεί ρητά μεταξύ εγκατάστασης και συσκευής."),
    "wall_outlet": ("Έξοδος τοίχου", "Τερματικό σύνδεσης εγκατάστασης προς τη συσκευή."),
    "wall_plate": ("Πλάκα / έξοδος τοίχου", "Τερματικό εξάρτημα τοίχου που έχει επιλεγεί για τη συγκεκριμένη σύνδεση."),
    "fixture_connector": ("Σύνδεσμος είδους υγιεινής", "Σύνδεση μεταξύ εγκατάστασης και συγκεκριμένου είδους υγιεινής."),
    "cistern_connector": ("Σύνδεσμος καζανακίου", "Σύνδεση παροχής προς καζανάκι που έχει επιλεγεί ρητά."),
    "appliance_hose_connector": ("Σύνδεσμος σωλήνα συσκευής", "Σύνδεση για εύκαμπτο σωλήνα πλυντηρίου ή άλλης συσκευής."),
    "mounting_plate": ("Πλάκα στήριξης", "Πλάκα στήριξης για τερματικά/εξόδους που έχει επιλεγεί."),
    "mounting_angle": ("Γωνία στήριξης", "Γωνιακό εξάρτημα στήριξης που έχει επιλεγεί."),
    "mounting_rail": ("Ράγα στήριξης", "Ράγα στήριξης για επιλεγμένα υδραυλικά στοιχεία."),
    "rough_in_box": ("Κουτί προεγκατάστασης", "Κουτί/βάση προεγκατάστασης για τελική σύνδεση."),
    "cover_plate": ("Πλάκα κάλυψης", "Πλάκα κάλυψης επιλεγμένου εντοιχισμένου στοιχείου."),
    "support": ("Στήριγμα σωλήνωσης", "Στήριγμα που έχει δηλωθεί για τη συγκεκριμένη εγκατάσταση."),
    "insulation": ("Μόνωση σωλήνωσης", "Μόνωση που έχει επιλεγεί για συγκεκριμένο μήκος/τμήμα σωλήνωσης."),
    "filter": ("Φίλτρο", "Φίλτρο που έχει επιλεγεί ρητά στο συγκεκριμένο σημείο του συστήματος."),
    "strainer": ("Φίλτρο τύπου strainer", "Φίλτρο σωματιδίων που έχει επιλεγεί στη γραμμή."),
    "pressure_reducer": ("Μειωτής πίεσης", "Εξάρτημα ρύθμισης πίεσης που έχει επιλεγεί ρητά για το έργο."),
    "check_valve": ("Αντεπίστροφη βαλβίδα", "Βαλβίδα μονής κατεύθυνσης που έχει επιλεγεί ρητά για το έργο."),
    "water_hammer_arrester": ("Αντικρουστικό υδραυλικού πλήγματος", "Εξάρτημα απόσβεσης υδραυλικού πλήγματος που έχει επιλεγεί."),
    "thermostatic_mixing_valve": ("Θερμοστατική βαλβίδα ανάμιξης", "Βαλβίδα ανάμιξης θερμού/κρύου νερού που έχει επιλεγεί."),
    "safety_valve": ("Βαλβίδα ασφαλείας", "Βαλβίδα ασφαλείας μόνο όταν ανήκει στην επιλεγμένη λύση/συσκευή."),
    "safety_group": ("Ομάδα ασφαλείας", "Συγκρότημα ασφαλείας που έχει επιλεγεί ρητά για το συγκεκριμένο προϊόν/σύστημα."),
    "expansion_vessel": ("Δοχείο διαστολής", "Δοχείο διαστολής που έχει επιλεγεί για το συγκεκριμένο σύστημα."),
    "tank_connector": ("Σύνδεσμος δοχείου / θερμοσίφωνα", "Σύνδεσμος που έχει επιλεγεί ρητά για το συγκεκριμένο δοχείο ή θερμοσίφωνα."),
    "solar_connector": ("Σύνδεσμος ηλιακού", "Σύνδεσμος που έχει επιλεγεί ρητά για το συγκεκριμένο ηλιακό σύστημα."),
    "fill_drain_cock": ("Κρουνός πλήρωσης / εκκένωσης", "Κρουνός πλήρωσης ή αποστράγγισης που έχει επιλεγεί στο σύστημα."),
    "pressure_gauge": ("Μανόμετρο", "Όργανο ένδειξης πίεσης που έχει επιλεγεί."),
    "thermometer": ("Θερμόμετρο", "Όργανο ένδειξης θερμοκρασίας που έχει επιλεγεί."),
    "flow_meter": ("Παροχόμετρο", "Όργανο ένδειξης/ρύθμισης παροχής που έχει επιλεγεί."),
}


def plumbing_accessories(doc):
    return [e for e in doc.entities.values() if e.kind == "plumbing_accessory"]


def accessory_quantities(doc) -> list[QuantityLine]:
    """Count only explicit accessories already present in the authoritative model."""
    grouped: dict[tuple[str, str, str, str], float] = defaultdict(float)
    metadata: dict[tuple[str, str, str, str], dict] = {}

    for entity in plumbing_accessories(doc):
        p = entity.params
        accessory_type = str(p.get("accessory_type", "unspecified"))
        unit = str(p.get("unit", "pcs"))
        manufacturer = str(p.get("manufacturer", ""))
        product_ref = str(p.get("product_ref", ""))
        qty = float(p.get("quantity", 1.0))
        if qty < 0:
            raise ValueError("plumbing accessory quantity must be >= 0")
        key = (accessory_type, unit, manufacturer, product_ref)
        grouped[key] += qty
        metadata[key] = dict(p)

    lines: list[QuantityLine] = []
    for key, qty in sorted(grouped.items()):
        accessory_type, unit, manufacturer, product_ref = key
        label, why = ACCESSORY_TYPES.get(
            accessory_type,
            (accessory_type, "Παρελκόμενο που έχει δηλωθεί ρητά στο έργο."),
        )
        meta = metadata[key]
        suffix = ""
        if manufacturer or product_ref:
            suffix = " — " + " / ".join(x for x in (manufacturer, product_ref) if x)
        source_kind = str(meta.get("source_kind", "model"))
        rule_source = str(meta.get("rule_source", ""))
        rule_status = str(meta.get("rule_status", "MODEL_SELECTED"))
        selection_basis = str(meta.get("selection_basis", source_kind))
        code_tail = accessory_type
        if product_ref:
            code_tail += "." + product_ref.replace(" ", "_")
        lines.append(QuantityLine(
            code=f"plumbing.accessory.{code_tail}",
            description=label + suffix,
            category="Παρελκόμενα",
            quantity=round(qty, 3),
            unit=unit,
            trade="plumbing",
            source="plumbing_accessory",
            owner_explanation=why,
            rule_status=rule_status,
            rule_source=rule_source,
            selection_basis=selection_basis,
        ))
    return lines
