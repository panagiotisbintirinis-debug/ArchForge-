"""Θερμοκρασίες σχεδιασμού του έργου: μέσα, έξω χειμώνα / καλοκαίρι, αλλαγές αέρα — όλες αλλάζουν, τίποτα σταθερό.

Ιδιοκτήτης 04/11: «θερμοκρασία σχεδιασμού μετά από έρευνα online πάρε απόφαση… αλλά πάντα περιθώριο να αλλάζουμε
τις θερμοκρασίες, τίποτα fixed». Κριτική v5 (μηχανικός ενεργειακής): η υπόθεση 28/10 «έξω 12 °C» είναι μέση μέρα
χειμώνα, όχι θερμοκρασία σχεδιασμού· υποεκτιμά την ισχύ θέρμανσης.

Απόφαση 04/11 (η έρευνα και τα όριά της, `docs/specs/design_temperatures.md`):

* Η θερμοκρασία σχεδιασμού χειμώνα είναι η «στατιστικά ψυχρή μέρα» της περιοχής (EN 12831-1: external design
  temperature· ελληνικές τιμές: ΤΟΤΕΕ 20701-3, Πίνακας 2.1 «Συνθήκες σχεδιασμού χειμώνα»).
* Ο επίσημος πίνακας δεν ήταν προσβάσιμος από το περιβάλλον εργασίας. Οι έτοιμες τιμές είναι **μόνο** όσες βρέθηκαν με
  πηγή, σημειωμένες «προς επαλήθευση»· καμία τιμή πόλης δεν επινοείται.
* Προεπιλογή νέου έργου: Αθήνα · ζώνη Β, 0 °C (η πιο κοινή περίπτωση των έργων). Κάθε έργο διαλέγει άλλη επιλογή ή
  γράφει δική του τιμή σε **κάθε** πεδίο, με μία αναίρεση· η επιλογή και η πηγή γράφονται δίπλα στο αποτέλεσμα.
"""
from __future__ import annotations

KIND = "design_climate"

# Where each value comes from. VERIFY = secondary source, to be checked against ΤΟΤΕΕ 20701-3 Πίνακας 2.1.
_SECONDARY = ("δευτερεύουσα πηγή: οδηγός μελέτης θερμικών απωλειών EN 12831, oikodomisis.gr — "
              "προς επαλήθευση με ΤΟΤΕΕ 20701-3, Πίνακας 2.1")
PRESETS = {
    "athens_b": {"label": "Αθήνα · ζώνη Β ΚΕΝΑΚ", "heat_theta_ext_winter": 0.0, "source": _SECONDARY},
    "florina_d": {"label": "Φλώρινα · ζώνη Δ ΚΕΝΑΚ", "heat_theta_ext_winter": -9.0, "source": _SECONDARY},
    "owner_2810": {"label": "Υπόθεση ιδιοκτήτη 28/10 (μέση μέρα χειμώνα)", "heat_theta_ext_winter": 12.0,
                   "source": "υπόθεση ιδιοκτήτη 28/10 — όχι θερμοκρασία σχεδιασμού"},
}
DEFAULT_PRESET = "athens_b"
CUSTOM = "custom"
CUSTOM_LABEL = "Δική μου τιμή"

# The values every project starts with (each one changes per project).
FIELDS = {
    "heat_theta_int": (20.0, "°C", "Θερμοκρασία μέσα (άνεση)", "υπόθεση ιδιοκτήτη 28/10"),
    "heat_theta_ext_winter": (PRESETS[DEFAULT_PRESET]["heat_theta_ext_winter"], "°C",
                              "Θερμοκρασία σχεδιασμού έξω, χειμώνας", PRESETS[DEFAULT_PRESET]["source"]),
    "heat_theta_ext_summer": (28.0, "°C", "Θερμοκρασία έξω, καλοκαίρι", "υπόθεση ιδιοκτήτη 28/10"),
    "heat_air_changes": (0.5, "1/h", "Αλλαγές αέρα την ώρα", "υπόθεση ιδιοκτήτη 28/10"),
}


def entity(doc):
    return next((e for e in doc.entities.values() if e.kind == KIND), None)


def values(doc):
    """``{field: value}``: the project's own values, else (older projects) those on the heat source, else defaults."""
    from archforge.mep.heating_layout import source_of
    own = dict(entity(doc).params) if entity(doc) is not None else {}
    src = source_of(doc)
    older = dict(src.params) if src is not None else {}
    out = {}
    for key, (default, *_rest) in FIELDS.items():
        v = own.get(key, older.get(key, default))
        out[key] = float(v)
    return out


def preset_of(doc):
    """The key of the chosen preset, or ``CUSTOM`` when the winter value is the user's own."""
    own = dict(entity(doc).params) if entity(doc) is not None else {}
    key = own.get("preset")
    winter = values(doc)["heat_theta_ext_winter"]
    if key in PRESETS and abs(PRESETS[key]["heat_theta_ext_winter"] - winter) < 1e-9:
        return key
    if key is None and abs(PRESETS[DEFAULT_PRESET]["heat_theta_ext_winter"] - winter) < 1e-9:
        return DEFAULT_PRESET
    return CUSTOM


def source_text(doc):
    """One line: where the winter design temperature comes from."""
    key = preset_of(doc)
    if key == CUSTOM:
        return "δική σας τιμή για το έργο"
    return f"{PRESETS[key]['label']} — {PRESETS[key]['source']}"


def set_command(doc, changes):
    """One undoable change of the project's design values (``changes``: some of FIELDS, and/or ``preset``)."""
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    changes = dict(changes)
    if changes.get("preset") in PRESETS and "heat_theta_ext_winter" not in changes:
        changes["heat_theta_ext_winter"] = PRESETS[changes["preset"]]["heat_theta_ext_winter"]
    for key in FIELDS:
        if key in changes:
            changes[key] = float(changes[key])
    e = entity(doc)
    if e is None:
        return AddEntity(Entity(KIND, changes, name="Θερμοκρασίες σχεδιασμού"))
    return UpdateEntity(e.id, changes)
