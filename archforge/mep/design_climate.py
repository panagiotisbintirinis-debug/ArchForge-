"""Θερμοκρασίες σχεδιασμού του έργου: μέσα, έξω χειμώνα / καλοκαίρι, αλλαγές αέρα — όλες αλλάζουν, τίποτα σταθερό.

Ιδιοκτήτης 04/11: «θερμοκρασία σχεδιασμού μετά από έρευνα online πάρε απόφαση… αλλά πάντα περιθώριο να αλλάζουμε
τις θερμοκρασίες, τίποτα fixed». Κριτική v5 (μηχανικός ενεργειακής): η υπόθεση 28/10 «έξω 12 °C» είναι μέση μέρα
χειμώνα, όχι θερμοκρασία σχεδιασμού· υποεκτιμά την ισχύ θέρμανσης.

Απόφαση 04/11 (η έρευνα και τα όριά της, `docs/specs/design_temperatures.md`):

* Η θερμοκρασία σχεδιασμού χειμώνα είναι η «στατιστικά ψυχρή μέρα» της περιοχής (EN 12831-1: external design
  temperature· ελληνικές τιμές: ΤΟΤΕΕ 20701-3, Πίνακας 2.1 «Συνθήκες σχεδιασμού χειμώνα»).
* 05/11: ο ιδιοκτήτης έδωσε το PDF της ΤΟΤΕΕ 20701-3. Έτοιμες επιλογές: οι 30 σταθμοί του Πίνακα 2.1 (DB 1 %) και
  53 πόλεις των Πινάκων 3.4/3.6 με τον κανόνα της §2.1 (``mep/totee_20701_3.py``)· καμία τιμή πόλης δεν επινοείται.
* Προεπιλογή νέου έργου: Αθήνα (Ν. Φιλαδέλφεια), 2,5 °C — ο ψυχρότερος σταθμός της Αθήνας. Κάθε έργο διαλέγει άλλη
  επιλογή ή γράφει δική του τιμή σε **κάθε** πεδίο, με μία αναίρεση· η επιλογή και η πηγή γράφονται δίπλα στο
  αποτέλεσμα. Οι παλιές επιλογές 04/11 (Αθήνα 0 °C, Φλώρινα −9 °C, δευτερεύουσα πηγή) μένουν μόνο για τα έργα που τις
  αποθήκευσαν, σημειωμένες «αντικαταστάθηκε».
"""
from __future__ import annotations

KIND = "design_climate"

# Where each value comes from (05/11: the official table, given by the owner — mep/totee_20701_3.py).
from archforge.mep import totee_20701_3 as _T


def _presets():
    out = {}
    for city, (db1, _db25, _db5) in _T.TABLE_2_1.items():
        out[f"totee:{city}"] = {"label": city, "heat_theta_ext_winter": float(db1),
                                "source": f"{_T.SOURCE}, Πίνακας 2.1, DB 1 %"}
    for city in sorted(_T.ESTIMATE_2_1):
        value, source = _T.winter_design(city)
        out[f"totee:{city}"] = {"label": f"{city} (εκτίμηση §2.1)", "heat_theta_ext_winter": float(value), "source": source}
    # Older choices (04/11): kept so projects that stored them still read them — replaced by the table above.
    _OLD = ("παλιά επιλογή 04/11 από δευτερεύουσα πηγή (oikodomisis.gr) — αντικαταστάθηκε από ΤΟΤΕΕ 20701-3 "
            "(Αθήνα 2,5 / 3,0 °C, Φλώρινα −8 °C)")
    out["athens_b"] = {"label": "Αθήνα · 0 °C (παλιά τιμή 04/11)", "heat_theta_ext_winter": 0.0, "source": _OLD,
                       "superseded": True}
    out["florina_d"] = {"label": "Φλώρινα · −9 °C (παλιά τιμή 04/11)", "heat_theta_ext_winter": -9.0, "source": _OLD,
                        "superseded": True}
    out["owner_2810"] = {"label": "Υπόθεση ιδιοκτήτη 28/10 (μέση μέρα χειμώνα)", "heat_theta_ext_winter": 12.0,
                         "source": "υπόθεση ιδιοκτήτη 28/10 — όχι θερμοκρασία σχεδιασμού"}
    return out


PRESETS = _presets()
# 05/11: the colder of the two Athens stations of Πίνακας 2.1 (the owner: «πάρε απόφαση… τίποτα fixed»).
DEFAULT_PRESET = "totee:Αθήνα (Ν. Φιλαδέλφεια)"
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


def zone(doc):
    """Κλιματική ζώνη ΚΕΝΑΚ of the project (Α–Δ): the one the user set, else the chosen city's (ΤΟΤΕΕ 20701-3
    Πίν. 1.1/1.2), else None — then the limits of Πίνακας 6 are not checked, and that is said."""
    own = dict(entity(doc).params) if entity(doc) is not None else {}
    if own.get("zone"):
        return own["zone"]
    key = preset_of(doc)
    if key.startswith("totee:"):
        return _T.zone_of(key[len("totee:"):])
    return None


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
