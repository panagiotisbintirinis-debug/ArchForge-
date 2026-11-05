"""Θερμικά στοιχεία κουφώματος — από τον κατασκευαστή, ένα σημείο για τη λίστα, τη θερμική εικόνα και τις απώλειες.

Ιδιοκτήτης 05/11: «να συνδέεται με τη λίστα των κουφωμάτων· αλλάζει το κούφωμα, αλλάζει και η θερμική απεικόνιση…
κάθε κούφωμα πρέπει να έχει εκτός από τομές και διαστάσεις και θερμικά στοιχεία — θα πάρω στοιχεία από τις εταιρείες».

Στοιχεία (όλα προαιρετικά, κανένα δεν μαντεύεται):

* ``u_value`` Uw δηλωμένο από τον κατασκευαστή (W/m²K) — αν δοθεί, ισχύει αυτό.
* ``uf`` Uf πλαισίου, ``ug`` Ug υαλοπίνακα (W/m²K), ``psi_g`` ψg αποστάτη (W/mK), ``frame_width`` ορατό πλάτος
  πλαισίου (m). Με όλα αυτά και χωρίς δηλωμένο Uw, το Uw υπολογίζεται κατά EN ISO 10077-1:
  Uw = (Ag·Ug + Af·Uf + lg·ψg) / (Ag + Af), Ag = (b − 2·bf)(h − 2·bf), lg = 2·((b − 2·bf) + (h − 2·bf)).
* ``g_value`` ηλιακός συντελεστής υαλοπίνακα (0…1), ``maker`` κατασκευαστής / σειρά / έγγραφο.

Χωρίς τίποτα από αυτά ισχύει το Uw κουφωμάτων του έργου (``heat_load.assumptions``), ή «δεν υπολογίστηκε».
"""
from __future__ import annotations

import math

# key: (label, unit, lo, hi) — the ranges only catch typing errors, they are not product limits.
NUMBERS = {
    "u_value": ("Uw δηλωμένο", "W/m²K", 0.3, 7.0),
    "uf": ("Uf πλαισίου", "W/m²K", 0.3, 8.0),
    "ug": ("Ug υαλοπίνακα", "W/m²K", 0.2, 6.0),
    "psi_g": ("ψg αποστάτη", "W/mK", 0.0, 0.3),
    "frame_width": ("πλάτος πλαισίου", "m", 0.02, 0.3),
    "g_value": ("g υαλοπίνακα", "", 0.05, 0.95),
}
TEXTS = {"maker": "Κατασκευαστής / σειρά / έγγραφο"}

# Τυπικά εύρη από το «Τεχνικό έντυπο: Στοιχεία κουφωμάτων & θερμική αγωγιμότητα (λ)» που έστειλε ο ιδιοκτήτης 05/11.
# Χωρίς αναφορά προτύπου ή κατασκευαστή → UNVERIFIED: χρησιμεύουν ΜΟΝΟ ως έλεγχος («το Uf που γράψατε είναι έξω από
# το συνηθισμένο για αυτό το πλαίσιο»), ποτέ ως τιμή του κουφώματος. key: (label, λ W/mK or (min, max), (U min, max)).
RANGES_SOURCE = "τεχνικό έντυπο κουφωμάτων του ιδιοκτήτη (05/11), τυπικά εύρη χωρίς πηγή προτύπου"
RANGES_STATUS = "UNVERIFIED"
FRAME_TYPES = {
    "alu_plain": ("Αλουμίνιο χωρίς θερμοδιακοπή", 160.0, (4.0, 7.0)),
    "alu_break": ("Αλουμίνιο με θερμοδιακοπή (πολυαμίδιο)", 0.30, (1.4, 2.8)),
    "upvc": ("Συνθετικό (uPVC)", 0.17, (1.0, 1.8)),
    "wood": ("Ξύλο (μαλακή / σκληρή ξυλεία)", (0.13, 0.18), (1.2, 2.0)),
}
GLAZING_TYPES = {
    "double_lowe_argon": ("Διπλός ενεργειακός (Low-E + αργό)", 0.016, (1.0, 1.4)),
}
CHOICES = {"frame_material": ("Υλικό πλαισίου", FRAME_TYPES, "uf"),
           "glazing": ("Υαλοπίνακας", GLAZING_TYPES, "ug")}


def range_notes(params):
    """«Uf 3,5 έξω από το συνηθισμένο 1,0–1,8 για uPVC» — one note per value outside the sheet's typical range."""
    notes = []
    for key, (_label, table, u_key) in CHOICES.items():
        choice = params.get(key)
        if choice not in table or params.get(u_key) in (None, ""):
            continue
        name, _lam, (lo, hi) = table[choice]
        v = float(params[u_key])
        if not lo <= v <= hi:
            notes.append(f"{'Uf' if u_key == 'uf' else 'Ug'} {v:g} έξω από το συνηθισμένο {lo:g}–{hi:g} για "
                         f"«{name}» — ελέγξτε το φύλλο του κατασκευαστή".replace(".", ","))
    return notes
SOURCE_DECLARED = "του κουφώματος, δηλωμένο από τον κατασκευαστή"
SOURCE_10077 = "του κουφώματος, EN ISO 10077-1 από Uf, Ug, ψg, πλαίσιο"
SOURCE_PROJECT = "του έργου"


def uw_10077(width, height, frame_width, uf, ug, psi_g):
    """Uw of one door / window, EN ISO 10077-1 (one glazed field framed all round)."""
    w, h, bf = float(width), float(height), float(frame_width)
    gw, gh = w - 2 * bf, h - 2 * bf
    if gw <= 0 or gh <= 0:
        raise ValueError(f"πλαίσιο {bf * 100:.1f} cm: δεν μένει τζάμι σε {w:.2f} × {h:.2f} m")
    ag, a = gw * gh, w * h
    return (ag * float(ug) + (a - ag) * float(uf) + 2 * (gw + gh) * float(psi_g)) / a


def has_parts(params):
    return all(params.get(k) not in (None, "") for k in ("uf", "ug", "psi_g", "frame_width"))


def uw(doc, opening):
    """``(Uw, source)`` of a door / window, or ``(None, None)`` — the one answer of the list, the image and the loads."""
    p = opening.params
    if p.get("u_value"):
        return float(p["u_value"]), SOURCE_DECLARED
    if has_parts(p):
        try:
            return uw_10077(p.get("width", 1.0), p.get("height", 1.0), p["frame_width"], p["uf"], p["ug"],
                            p["psi_g"]), SOURCE_10077
        except ValueError:
            pass
    from archforge.mep.heat_load import assumptions
    project = assumptions(doc)["heat_u_openings"]
    return (float(project), SOURCE_PROJECT) if project else (None, None)


def parse(key, text):
    """A typed value (comma or dot; empty = remove) checked against ``NUMBERS``; ``frame_width`` is typed in cm."""
    if key in TEXTS:
        return str(text or "").strip() or None
    if key in CHOICES:
        t = str(text or "").strip()
        if t in ("", "—"):
            return None
        table = CHOICES[key][1]
        for k, (label, _lam, _rng) in table.items():
            if t == k or t.casefold() == label.casefold():
                return k
        raise ValueError(f"{CHOICES[key][0]} «{t}»: διαλέξτε από τη λίστα")
    if key not in NUMBERS:
        raise KeyError(key)
    t = str(text or "").strip().replace(",", ".")
    if t in ("", "—"):
        return None
    v = float(t)
    if key == "frame_width":
        v /= 100.0
    label, unit, lo, hi = NUMBERS[key]
    if not math.isfinite(v) or not lo <= v <= hi:
        shown = f"{v * 100:g} cm" if key == "frame_width" else f"{t} {unit}".strip()
        raise ValueError(f"{label} {shown}: έξω από τα λογικά όρια — ελέγξτε το φύλλο του κατασκευαστή")
    return v


def set_command(doc, eid, key, text):
    """One undoable change of one thermal datum of a door / window."""
    from archforge.core.commands import UpdateEntity
    e = doc.get(eid)
    if e is None or e.kind not in ("door", "window"):
        raise ValueError("θερμικά στοιχεία έχουν μόνο πόρτες και παράθυρα")
    value = parse(key, text)
    if key == "frame_width" and value is not None:
        uw_10077(e.params.get("width", 1.0), e.params.get("height", 1.0), value, 1.0, 1.0, 0.0)   # glass must remain
    return UpdateEntity(eid, {key: value})
