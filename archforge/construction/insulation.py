"""Insulation of every surface of the building: thermal and waterproofing, all in view (owner 15/10).

Owner: «πρέπει να υπάρχει καρτέλα για μονώσεις από τις επιφάνειες — είτε πλάκας είτε δαπέδου, κεραμοσκεπής —
τι μόνωση, υγρασίας, θερμο· ιδανικά πρέπει να φαίνονται όλα».

``surfaces(doc)`` reads the model: flat roofs / roof slabs, floors on the ground, tiled roofs (slope area),
exterior walls (net of openings), plasterboard ceilings, floors of wet rooms.  For each it gives the area
and the thermal insulation and waterproofing **as chosen**: from the element itself where it has a build-up
(tiled roof insulation, wall type layers, ceiling wool) or from the project's specification per category
(``insulation_spec`` entity: one choice per category, undoable).  Nothing is filled in by the program:
an unchosen layer is shown «— επιλέξτε», no thickness, λ or U-value comes from memory (owner's rule).
Area = geometry of the drawing; the material, thickness and system are the designer's / engineer's choice.
"""
from __future__ import annotations

import math

from archforge.core.provenance import DESIGN_DEFAULT, ENGINEER_REVIEW, Rule, register

CATEGORIES = {
    "flat_roof": "Δώμα / πλάκα οροφής σε επαφή με εξωτερικό αέρα",
    "pitched_roof": "Κεραμοσκεπή (επιφάνεια κλίσης)",
    "ground_floor": "Δάπεδο σε επαφή με το έδαφος",
    "exterior_wall": "Εξωτερικοί τοίχοι (καθαρά, χωρίς ανοίγματα)",
    "ceiling": "Ψευδοροφή γυψοσανίδας",
    "wet_floor": "Δάπεδο υγρού χώρου (μπάνιο / WC / κουζίνα)",
}
# Names only (materials are chosen; their λ / thickness come from the product's data sheet).
THERMAL = {"xps": "Εξηλασμένη πολυστερίνη (XPS)", "eps": "Διογκωμένη πολυστερίνη (EPS)", "graphite_eps": "EPS γραφίτη",
           "rockwool": "Πετροβάμβακας", "glasswool": "Υαλοβάμβακας", "pir": "Πολυϊσοκυανουρικό (PIR)",
           "none": "Χωρίς θερμομόνωση"}
WATERPROOFING = {"bitumen": "Ασφαλτική μεμβράνη", "liquid_pu": "Επαλειφόμενη πολυουρεθανική",
                 "cementitious": "Επαλειφόμενη τσιμεντοειδής", "tpo_pvc": "Συνθετική μεμβράνη (TPO/PVC/EPDM)",
                 "underlay": "Μεμβράνη κάτω από τα κεραμίδια (διαπνέουσα)", "none": "Χωρίς στεγάνωση"}
# Where waterproofing is part of the surface's job (the system itself is chosen).
NEEDS_WATERPROOFING = ("flat_roof", "pitched_roof", "ground_floor", "wet_floor")

register(
    Rule("insulation.areas", "Εμβαδά μονώσεων από το σχέδιο: δώματα, δάπεδα σε έδαφος, κλίση κεραμοσκεπής "
         "(κάτοψη / cos κλίσης), εξωτερικοί τοίχοι μείον ανοίγματα, ψευδοροφές, υγροί χώροι", DESIGN_DEFAULT,
         note="Γεωμετρία· χωρίς επικαλύψεις/φύρα (η φύρα από το φύλλο του προϊόντος)"),
    Rule("insulation.choice", "Υλικό, πάχος και σύστημα στεγάνωσης ανά επιφάνεια: επιλογή του μελετητή", ENGINEER_REVIEW,
         note="Καμία τιμή λ / U / πάχους από το πρόγραμμα· ενεργειακή μελέτη (ΚΕΝΑΚ) από μηχανικό"),
)


def spec_entity(doc):
    return next((e for e in doc.entities.values() if e.kind == "insulation_spec"), None)


def spec(doc):
    """``{category: {"thermal": key|None, "thickness": m|None, "waterproofing": key|None}}`` as chosen."""
    e = spec_entity(doc)
    raw = dict((e.params.get("categories") or {}) if e else {})
    return {c: {"thermal": (raw.get(c) or {}).get("thermal"), "thickness": (raw.get(c) or {}).get("thickness"),
                "waterproofing": (raw.get(c) or {}).get("waterproofing")} for c in CATEGORIES}


def _poly_area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2.0


def _entry(category, element, label, storey, area, thermal=None, thickness=None, waterproofing=None, source="spec"):
    return {"category": category, "element": element, "label": label, "storey": storey, "area": round(area, 2),
            "thermal": thermal, "thickness": thickness, "waterproofing": waterproofing, "source": source}


def surfaces(doc):
    """Every insulated / waterproofed surface of the model, with what it has (or «not chosen»)."""
    from archforge.assistant.understanding import read_drawing
    from archforge.ui.project_outline import _level_label, slab_info
    chosen = spec(doc)
    out = []

    def from_spec(entry):
        c = chosen[entry["category"]]
        if entry["thermal"] is None and c["thermal"]:
            entry.update(thermal=c["thermal"], thickness=c["thickness"])
        if entry["waterproofing"] is None and c["waterproofing"]:
            entry["waterproofing"] = c["waterproofing"]
        return entry

    levels = sorted({0.0, *[float(v) for v in doc.levels.values()]})
    lowest = levels[0] if levels else 0.0
    for e in doc.entities.values():
        p = e.params
        if e.kind == "room_roof" and str(p.get("roof_type", "flat")) == "flat":
            info = slab_info(doc, e)
            if info["area"]:
                out.append(from_spec(_entry("flat_roof", e.id, f"Δώμα — {info['where'] or ''}".strip(" —"), info["where"], info["area"])))
        elif e.kind in ("room_floor", "room_foundation"):
            from archforge.ui.project_outline import _slab_face
            found = None if p.get("scope") == "storey" else _slab_face(doc, e)
            z = float(found[1]) if found else float(p.get("level_z", 0.0))
            info = slab_info(doc, e)
            if info["area"] and (e.kind == "room_foundation" or abs(z - lowest) < 1e-3):
                out.append(from_spec(_entry("ground_floor", e.id, f"Δάπεδο σε έδαφος — {info['where'] or ''}".strip(" —"),
                                            info["where"], info["area"])))
        elif e.kind == "pitched_roof":
            ov = float(p.get("overhang", 0.0))
            plan = (abs(float(p["x1"]) - float(p["x0"])) + 2 * ov) * (abs(float(p["y1"]) - float(p["y0"])) + 2 * ov)
            area = plan / max(1e-6, math.cos(math.radians(float(p.get("pitch", 0.0)))))
            kind = str(p.get("insulation", "")) or None
            out.append(from_spec(_entry("pitched_roof", e.id, e.name or "Κεραμοσκεπή", None, area,
                                        thermal=None if kind in (None, "none") else kind,
                                        thickness=float(p["insulation_thickness"]) if kind not in (None, "none") and
                                        "insulation_thickness" in p else None, source="element" if kind else "spec")))
        elif e.kind == "drywall_ceiling":
            from archforge.construction.drywall import outline
            poly = outline(doc, e)
            if poly:
                wool = float(p.get("insulation", 0.0))
                out.append(from_spec(_entry("ceiling", e.id, e.name or "Ψευδοροφή", None, _poly_area(poly),
                                            thermal="rockwool" if wool > 0 else None, thickness=wool or None,
                                            source="element" if wool > 0 else "spec")))
    # Exterior walls, net of their openings; the wall type's own insulation layer counts as chosen.
    from archforge.architecture.wall_types import layers
    for storey in read_drawing(doc)["storeys"]:
        name = _level_label(storey["name"]) if storey.get("name") else None
        for wid in storey["exterior_walls"]:
            w = doc.entities.get(wid)
            if w is None:
                continue
            p = w.params
            length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
            gross = length * float(p.get("height", 0.0))
            holes = sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) for o in doc.entities.values()
                        if o.kind in ("door", "window", "opening") and o.parent_id == wid)
            ins = [l for l in layers(p.get("wall_type", "generic"), doc) if l[4]]
            entry = _entry("exterior_wall", wid, f"Τοίχος {length:.2f} m".replace(".", ","), name, max(0.0, gross - holes))
            if ins:
                entry.update(thermal=ins[0][0], thickness=sum(l[1] for l in ins), source="element")
            out.append(from_spec(entry))
        from archforge.assistant.understanding import _use_from_text
        for room in storey.get("rooms", ()):
            meta = doc.room_metadata(room["signature"]) if hasattr(doc, "room_metadata") else {}
            use = _use_from_text(meta.get("use")) or _use_from_text(room.get("name"))
            if use in ("bathroom", "wc", "kitchen") and room.get("polygon"):
                out.append(from_spec(_entry("wet_floor", None, f"{room.get('name') or 'Υγρός χώρος'}", name,
                                            _poly_area(room["polygon"]))))
    return out


def thermal_label(key):
    return THERMAL.get(key, key) if key else None


def quantity_rows(doc):
    """Rows for the price lists: m² per category × material × thickness, and per waterproofing system."""
    totals, wp = {}, {}
    for s in surfaces(doc):
        key = (s["category"], s["thermal"], s["thickness"])
        totals[key] = totals.get(key, 0.0) + s["area"]
        if s["category"] in NEEDS_WATERPROOFING:
            k = (s["category"], s["waterproofing"])
            wp[k] = wp.get(k, 0.0) + s["area"]
    rows = []
    for (cat, mat, t), area in sorted(totals.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2] or 0)):
        if mat in ("none",):
            continue
        if mat is None:
            desc = f"Θερμομόνωση — {CATEGORIES[cat]} (δεν επιλέχθηκε υλικό)"
            code = f"insulation.thermal.{cat}.unset"
        else:
            desc = f"Θερμομόνωση {thermal_label(mat)}" + (f" {t * 100:g} cm" if t else "") + f" — {CATEGORIES[cat]}"
            code = f"insulation.thermal.{cat}.{mat}" + (f".{round(t * 1000)}mm" if t else "")
        rows.append((desc.replace(".", ",") if t else desc, "m²", round(area, 2),
                     {"code": code, "why": "Εμβαδόν της επιφάνειας από το σχέδιο· υλικό/πάχος όπως επιλέχθηκαν.",
                      "status": "ENGINEER_REVIEW", "source": "construction/insulation.py"}))
    for (cat, system), area in sorted(wp.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        if system == "none":
            continue
        desc = (f"Στεγάνωση {WATERPROOFING.get(system, system)} — {CATEGORIES[cat]}" if system
                else f"Στεγάνωση — {CATEGORIES[cat]} (δεν επιλέχθηκε σύστημα)")
        rows.append((desc, "m²", round(area, 2),
                     {"code": f"waterproofing.{cat}.{system or 'unset'}", "why": "Επιφάνεια που χρειάζεται προστασία από νερό/υγρασία.",
                      "status": "ENGINEER_REVIEW", "source": "construction/insulation.py"}))
    return rows
