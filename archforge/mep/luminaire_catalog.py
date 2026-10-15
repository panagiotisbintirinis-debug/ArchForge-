"""Luminaire catalogue: data-sheet values applied to a luminaire point in one step.

An entry is MANUFACTURER_DATA only when it names the manufacturer, the product
code and the data sheet (file or URL) its values come from.  Anything else is
a *template*: it fills the fields so the drawing and the board can be worked
on, but the point keeps showing «⚠ όχι φύλλο συγκεκριμένου προϊόντος» until a
real product is chosen (owner's rule 15/10: no values from memory, no fake data).

The three templates below are the owner's 15/10 summary ("typical reference
models", several brands given only as examples) — kept with that status.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from archforge.core.provenance import ENGINEER_REVIEW, MANUFACTURER_DATA, UNVERIFIED, Rule, register

DIMMING = {"onoff": "Χωρίς ρύθμιση (On/Off)", "phase_cut": "Phase-cut / Triac", "dali2": "DALI-2", "0_10v": "0-10 V"}


@dataclass(frozen=True)
class Entry:
    id: str
    label: str
    types: tuple            # point types it applies to
    values: dict            # electrical_point params it sets (power_w or w_per_m, lumen, kelvin, beam_deg …)
    manufacturer: str = ""
    product_code: str = ""
    datasheet: str = ""     # file name or URL of the data sheet
    driver: str = ""        # driver description from the sheet
    extra: dict = field(default_factory=dict)   # CRI, IP, UGR … (shown, not used in calculations)
    source_note: str = ""

    @property
    def status(self):
        return MANUFACTURER_DATA if (self.manufacturer and self.product_code and self.datasheet) else UNVERIFIED


_SUMMARY = "Σύνοψη ιδιοκτήτη 15/10 («τυπικό μοντέλο αναφοράς», μάρκες μόνο ως παράδειγμα) — όχι φύλλο συγκεκριμένου προϊόντος"

ENTRIES = (
    Entry("tpl_strip_cove_14w", "Πρότυπο: ταινία κρυφού φωτισμού 14,4 W/m (IP20, 24 V CV)", ("led_strip",),
          {"w_per_m": 14.4, "lumen": 1650.0, "kelvin": 3000.0, "beam_deg": 120.0},
          driver="24 V DC σταθερής τάσης, SELV", extra={"CRI": "≥ 90", "IP": "20", "Τάση": "24 V DC"}, source_note=_SUMMARY),
    Entry("tpl_strip_outdoor_9w6", "Πρότυπο: στεγανή ταινία 9,6 W/m (IP67, 24 V CV)", ("led_strip",),
          {"w_per_m": 9.6, "lumen": 980.0, "kelvin": 3000.0, "beam_deg": 120.0},
          driver="24 V DC σταθερής τάσης IP67, SELV, Class II, προστασία υπερτάσεων", extra={"CRI": "≥ 85", "IP": "67/68"},
          source_note=_SUMMARY),
    Entry("tpl_downlight_12w_36", "Πρότυπο: χωνευτό downlight 12 W, 36° (UGR < 16)", ("downlight", "spot"),
          {"power_w": 12.0, "lumen": 1100.0, "kelvin": 3000.0, "beam_deg": 36.0},
          driver="Σταθερού ρεύματος 350 mA, εξωτερικό, DALI-2 ή phase-cut, SELV",
          extra={"CRI": "≥ 92, R9 > 50", "UGR": "< 16", "IP": "44 πρόσοψη / 20 σώμα"}, source_note=_SUMMARY),
)

register(
    Rule("lighting.catalog_templates", "Πρότυπα καταλόγου φωτιστικών (ταινία 14,4 W/m, στεγανή 9,6 W/m, downlight 12 W/36°)",
         UNVERIFIED, source=_SUMMARY,
         note="Γίνονται στοιχεία κατασκευαστή μόνο με κατασκευαστή + κωδικό + φύλλο"),
    Rule("lighting.driver_margin", "Τροφοδοτικό ταινίας ≥ ισχύς ταινίας × 1,20", ENGINEER_REVIEW, source=_SUMMARY,
         note="Το περιθώριο το ορίζει το φύλλο του τροφοδοτικού/ταινίας· εδώ μόνο ως ένδειξη"),
    Rule("lighting.dimming_protocol", "Πρωτόκολλο ρύθμισης (On/Off, phase-cut, DALI-2, 0-10 V) ανά φωτιστικό· "
         "μια ομάδα με ροοστάτη πρέπει να έχει ένα πρωτόκολλο", ENGINEER_REVIEW,
         note="Το πρωτόκολλο το δίνει το φύλλο του τροφοδοτικού· ο έλεγχος συμβατότητας ομάδας είναι λογική του προγράμματος"),
)
DRIVER_MARGIN = 1.20


def entries_for(point_type):
    return [e for e in ENTRIES if point_type in e.types]


def entry(entry_id):
    return next(e for e in ENTRIES if e.id == entry_id)


def apply_values(entry_id):
    """Params to write on the point: the entry's values plus ``catalog_id`` (one UpdateEntity)."""
    e = entry(entry_id)
    return {**e.values, "catalog_id": e.id}


def status_of(params):
    """(status, text) of where the point's photometric/electrical values come from."""
    cid = params.get("catalog_id")
    if cid:
        try:
            e = entry(cid)
        except StopIteration:
            return UNVERIFIED, f"άγνωστη εγγραφή καταλόγου {cid}"
        if e.status == MANUFACTURER_DATA:
            return MANUFACTURER_DATA, f"{e.manufacturer} {e.product_code} — φύλλο: {e.datasheet}"
        return UNVERIFIED, f"⚠ {e.label}: όχι φύλλο συγκεκριμένου προϊόντος ({e.source_note})"
    if any(k in params for k in ("lumen", "kelvin", "beam_deg", "w_per_m")) or float(params.get("power_w", 0) or 0) > 0:
        return MANUFACTURER_DATA, "τιμές που εισήγαγε ο χρήστης από το φύλλο"
    return UNVERIFIED, "⚠ δεν έχουν εισαχθεί στοιχεία φύλλου"
