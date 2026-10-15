"""Installer practice for dwelling circuits, as given by the owner (15/10), compared with the program's rules.

The owner's summary says these are "established practice of the Greek market"
alongside ΕΛΟΤ HD 60364 (sizing by Iz, installation method, voltage drop,
Ib ≤ In ≤ Iz) — so they are ENGINEER_REVIEW, not VERIFIED.  Their use here is
to show where the program's circuit rules (``electrical.CIRCUIT_RULES``)
disagree with them, so the owner / an electrician can decide.  Nothing is
changed automatically.
"""
from __future__ import annotations

from archforge.core.provenance import ENGINEER_REVIEW, UNVERIFIED, Rule, register

SOURCE = "Σύνοψη ιδιοκτήτη 15/10 «Κανόνες κυκλωμάτων κατοικίας (πρακτική εγκαταστάτη)» — όχι κείμενο προτύπου"

# group: (mm² options, breaker A options, max points (low, high) or None, note)
PRACTICE = {
    "lighting": ((1.5,), (10,), (10, 12), "τουλάχιστον 2 ανεξάρτητα κυκλώματα φωτισμού ανά κατοικία"),
    "sockets": ((2.5,), (16,), (6, 8), "οι πρίζες πάγκου κουζίνας σε χωριστή γραμμή"),
    "kitchen_sockets": ((2.5,), (16,), (3, 4), ""),
    "cooker": ((10.0,), (40,), None, "μονοφασική· τριφασική 5×2,5 ή 5×4 με 3×16 ή 3×20 A"),
    "water_heater": ((4.0,), (20,), None, "αντίσταση ως 4 kW, διπολικός διακόπτης απομόνωσης"),
    "washing_machine": ((2.5,), (16,), None, ""),
    "dishwasher": ((2.5,), (16,), None, ""),
    "air_conditioner": ((2.5, 4.0), (16, 20), None, "≤ 12.000 BTU: 2,5/16 A· 18–24.000 BTU κατά Imax κατασκευαστή"),
}
# cable section -> highest breaker (A) in the same summary
MAX_BREAKER = {1.5: 10, 2.5: 16, 4.0: 20, 10.0: 40}

register(
    Rule("practice.circuits", "Πρακτική εγκαταστάτη για κυκλώματα κατοικίας (διατομή, ασφάλεια, σημεία ανά χρήση)",
         ENGINEER_REVIEW, source=SOURCE, note="Χρησιμοποιείται μόνο για να δείξει διαφωνίες με τους κανόνες του προγράμματος"),
    Rule("practice.section_breaker", "Διατομή → μέγιστη ασφάλεια: 1,5→10 A, 2,5→16 A, 4→20 A, 10→40 A",
         ENGINEER_REVIEW, source=SOURCE, note="Κατά HD 60364 η επιλογή γίνεται με Ib ≤ In ≤ Iz για τη μέθοδο εγκατάστασης"),
    Rule("practice.voltage_drop_4", "Πτώση τάσης ≤ 4 %", ENGINEER_REVIEW, source=SOURCE,
         note="Η σύνοψη αναφέρει 4 %· να διασταυρωθεί με ΕΛΟΤ HD 60364-5-52 (δεν υπολογίζεται ακόμη)"),
    Rule("standards.keee_replaced", "Ο ΚΕΗΕ αντικαταστάθηκε από το ΕΛΟΤ HD 384 με την ΥΑ Φ.7.5/1816/88/2004 (ΦΕΚ 470/Β/2004)· "
         "σήμερα ισχύει το ΕΛΟΤ HD 60364", UNVERIFIED,
         source="Συμφωνούν: dsanet.gr/Epikairothta/Nomothesia/4654_2021.PDF · tuv-nord.com (Electrical Installations) · "
                "ΣΕΒ kokkinos_parousiasi_final.pdf",
         note="Δευτερογενείς πηγές· γίνεται VERIFIED όταν διαβαστεί το ΦΕΚ 470/Β/2004"),
)


def conflicts():
    """Where the program's circuit rules differ from the installer practice: [(group, text)]."""
    from archforge.mep.electrical import CIRCUIT_RULES
    out = []
    for group, (label, breaker, cable, limit) in CIRCUIT_RULES.items():
        if group not in PRACTICE:
            continue
        sections, breakers, points, _note = PRACTICE[group]
        if cable not in sections or breaker not in breakers:
            out.append((group, f"{label}: πρόγραμμα {breaker} A / {cable:g} mm² — πρακτική "
                               f"{' ή '.join(f'{b} A' for b in breakers)} / {' ή '.join(f'{s:g} mm²' for s in sections)}"))
        top = MAX_BREAKER.get(cable)
        if top is not None and breaker > top:
            out.append((group, f"{label}: {breaker} A σε {cable:g} mm² — η ίδια πρακτική δίνει ως {top} A για {cable:g} mm²"))
        if points and limit > 1 and not points[0] <= limit <= points[1]:
            out.append((group, f"{label}: πρόγραμμα ως {limit} σημεία — πρακτική {points[0]}–{points[1]}"))
    return [(g, t.replace("2.5", "2,5").replace("1.5", "1,5")) for g, t in out]


def lighting_circuit_count_conflict(design):
    """The practice asks for at least 2 lighting circuits per dwelling."""
    n = sum(1 for c in design["circuits"] if c["group"] == "lighting")
    if n == 1:
        return "Φωτισμός: 1 κύκλωμα — η πρακτική ζητά τουλάχιστον 2 ανά κατοικία"
    return None
