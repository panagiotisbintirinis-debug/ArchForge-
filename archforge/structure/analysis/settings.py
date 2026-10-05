"""Building data for the structural analysis, stored in the Document.

One ``structural_design`` entity holds the building type and the design
basis; it is edited through UpdateEntity like anything else (undo, save).
Without it the defaults below apply (Greek dwelling, RC frame).
"""
from __future__ import annotations

SYSTEMS = {"reinforced_concrete": "Πλαίσια οπλισμένου σκυροδέματος", "steel": "Μεταλλικά πλαίσια ροπής"}
# occupancy: label, q floors (kN/m²), ψ2 — EN 1991-1-1 Πίν. 6.2 (συνιστώμενες) & EN 1990 Πίν. A1.1
OCCUPANCIES = {"residential": ("Κατοικία (κατ. A)", 2.0, 0.3), "office": ("Γραφεία (κατ. B)", 3.0, 0.3),
               "retail": ("Καταστήματα (κατ. D1)", 4.0, 0.6), "assembly": ("Συνάθροιση κοινού (κατ. C3)", 5.0, 0.6)}
ROOF_ACCESS = {"accessible": ("Δώμα βατό", 2.0), "non_accessible": ("Δώμα μη βατό (κατ. H)", 0.4)}
ZONES = {"1": 0.16, "2": 0.24, "3": 0.36}           # ag,R / g — Greek NA to EN 1998-1
SOILS = ("A", "B", "C", "D", "E")
IMPORTANCE = {"1": 0.8, "2": 1.0, "3": 1.2, "4": 1.4}

DEFAULTS = {"system": "reinforced_concrete", "occupancy": "residential", "roof_access": "accessible",
            "seismic_zone": "1", "soil": "B", "importance": "2", "concrete": "C25/30", "steel_grade": "S275",
            "slab_thickness": 0.18, "finishes": 1.5, "partitions": 1.0, "roof_finishes": 2.0,
            "soil_pressure": 200.0}


def design_entity(doc):
    return next((e for e in doc.entities.values() if e.kind == "structural_design"), None)


def get_settings(doc):
    s = dict(DEFAULTS)
    e = design_entity(doc)
    if e is not None:
        s.update({k: v for k, v in e.params.items() if k in DEFAULTS})
    else:
        # The building type follows the members the user drew.
        kinds = [str(m.params.get("construction")) for m in doc.entities.values()
                 if m.kind in ("structural_column", "structural_beam")]
        if kinds and kinds.count("steel") > len(kinds) / 2:
            s["system"] = "steel"
    s["seismic_zone"], s["importance"] = str(s["seismic_zone"]), str(s["importance"])
    return s
