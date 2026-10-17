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
# Presence in this dictionary NEVER means that a part is mandatory.  Quantities
# come only from explicit model entities or selected connection assemblies.
ACCESSORY_TYPES = {
    "isolation_valve": ("Βάνα απομόνωσης", "Επιτρέπει την απομόνωση του επιλεγμένου τμήματος του δικτύου για έλεγχο ή εργασία."),
    "mini_valve": ("Βανάκι σημείου", "Τοπικό εξάρτημα απομόνωσης που έχει επιλεγεί για το συγκεκριμένο σημείο."),
    "angle_stop": ("Γωνιακός διακόπτης", "Γωνιακός διακόπτης που έχει επιλεγεί ρητά για τη συγκεκριμένη τελική σύνδεση."),
    "appliance_valve": ("Βάνα συσκευής", "Βάνα που έχει επιλεγεί ρητά για την απομόνωση της συγκεκριμένης συσκευής."),
    "manifold_valve": ("Βάνα συλλέκτη", "Βάνα που έχει επιλεγεί ρητά για είσοδο ή έξοδο του συγκεκριμένου συλλέκτη."),
    "manifold_connector": ("Ρακόρ / σύνδεσμος συλλέκτη", "Σύνδεσμος που έχει επιλεγεί ρητά μεταξύ συλλέκτη και σωλήνωσης."),
    "manifold_cabinet": ("Πίνακας / ερμάριο υδροληψίας", "Περιέχει και προστατεύει τον επιλεγμένο συλλέκτη και τα συνδεδεμένα εξαρτήματα."),
    "union": ("Ρακόρ", "Αποσπώμενη σύνδεση που έχει επιλεγεί στο συγκεκριμένο σημείο της εγκατάστασης."),
    "adapter": ("Αντάπτορας", "Σύνδεση μεταξύ των επιλεγμένων διαφορετικών άκρων ή συστημάτων."),
    "elbow": ("Γωνία", "Εξάρτημα αλλαγής διεύθυνσης που υπάρχει στη συγκεκριμένη κατασκευαστική λύση."),
    "tee": ("Ταφ", "Εξάρτημα διακλάδωσης που υπάρχει στη συγκεκριμένη κατασκευαστική λύση."),
    "coupling": ("Σύνδεσμος", "Εξάρτημα σύνδεσης δύο τμημάτων σωλήνωσης που έχει δηλωθεί στο μοντέλο."),
    "flexible_connector": ("Εύκαμπτος σύνδεσμος", "Εύκαμπτη σύνδεση που έχει επιλεγεί ρητά μεταξύ εγκατάστασης και συσκευής."),
    "wall_plate": ("Πλάκα / έξοδος τοίχου", "Τερματικό εξάρτημα τοίχου που έχει επιλεγεί για τη συγκεκριμένη σύνδεση."),
    "end_cap": ("Τάπα", "Τάπα που έχει επιλεγεί ρητά για συγκεκριμένο άκρο ή αχρησιμοποίητη έξοδο."),
    "support": ("Στήριγμα σωλήνωσης", "Στήριγμα που έχει δηλωθεί για τη συγκεκριμένη εγκατάσταση."),
    "insulation": ("Μόνωση σωλήνωσης", "Μόνωση που έχει επιλεγεί για συγκεκριμένο μήκος/τμήμα σωλήνωσης."),
    "fixture_connector": ("Εξάρτημα σύνδεσης συσκευής", "Σύνδεση μεταξύ εγκατάστασης και συγκεκριμένης υδραυλικής συσκευής."),
    "tank_connector": ("Σύνδεσμος δοχείου", "Σύνδεσμος που έχει επιλεγεί ρητά για το συγκεκριμένο δοχείο ή θερμοσίφωνα."),
    "solar_connector": ("Σύνδεσμος ηλιακού", "Σύνδεσμος που έχει επιλεγεί ρητά για το συγκεκριμένο ηλιακό σύστημα."),
    "filter": ("Φίλτρο", "Φίλτρο που έχει επιλεγεί ρητά στο συγκεκριμένο σημείο του συστήματος."),
    "pressure_reducer": ("Μειωτής πίεσης", "Εξάρτημα ρύθμισης πίεσης που έχει επιλεγεί ρητά για το έργο."),
    "check_valve": ("Αντεπίστροφη βαλβίδα", "Βαλβίδα μονής κατεύθυνσης που έχει επιλεγεί ρητά για το έργο."),
    "safety_group": ("Ομάδα ασφαλείας", "Συγκρότημα ασφαλείας που έχει επιλεγεί ρητά για το συγκεκριμένο προϊόν/σύστημα."),
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
