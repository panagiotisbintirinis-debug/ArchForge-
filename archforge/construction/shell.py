"""The building shell in the units each trade prices by: masonry m², slab concrete m³, plaster m², roof m², joinery pieces.

Owner 15/10: «το σύνολο θα μας δώσει κόστος κατασκευής … πόσα τούβλα, πόσο μπετό, πόσα πλακάκια, τι σωλήνες».
Owner's rule: no values from memory.  So this module measures geometry only:

* **masonry**: wall face area net of openings, per wall type (the bricklayer prices per m²); the number of
  bricks appears only when the user has entered the pieces per m² of the chosen brick (``construction_spec``:
  data sheet of the product) — never a typical figure;
* **slab concrete**: area of each slab × its thickness in the model (m³) — floors, flat roofs, foundations;
* **plaster**: interior faces (the rooms' wall area of the take-off, tiles excluded) and the exterior face of
  the exterior walls, both net of openings (m²);
* **tiled roof**: slope area per tile type (m²); tiles per m² only from the user's data-sheet entry;
* **joinery**: every window and door, by kind, type, finish and size (pieces) — priced per piece.
"""
from __future__ import annotations

import math

from archforge.core.provenance import DESIGN_DEFAULT, MANUFACTURER_DATA, Rule, register

register(
    Rule("shell.geometry", "Τοιχοποιίες m² (όψη μείον ανοίγματα), σκυρόδεμα πλακών m³ (εμβαδόν × πάχος μοντέλου), σοβάδες m², "
         "επιφάνεια κλίσης στέγης m², κουφώματα ανά τεμάχιο", DESIGN_DEFAULT,
         note="Γεωμετρία του σχεδίου· χωρίς φύρα, επικαλύψεις, ενισχύσεις (από τον τεχνίτη/μελέτη)"),
    Rule("shell.pieces_per_m2", "Τεμάχια ανά m² (τούβλα, κεραμίδια)", MANUFACTURER_DATA,
         note="Μόνο αν τα εισαγάγει ο χρήστης από το φύλλο του προϊόντος· αλλιώς η μέτρηση μένει σε m²"),
)


def _meta(code, why, status="DESIGN_DEFAULT"):
    return {"code": code, "why": why, "status": status, "source": "construction/shell.py"}


def _spec(doc):
    e = next((x for x in doc.entities.values() if x.kind == "construction_spec"), None)
    return dict((e.params.get("pieces_per_m2") or {}) if e else {})


def _openings_area(doc, wall_id):
    return sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) for o in doc.entities.values()
               if o.kind in ("door", "window", "opening") and o.parent_id == wall_id)


def masonry_list(doc):
    """m² of wall per wall type (one face, net of openings); bricks only with the user's pieces/m²."""
    from archforge.architecture.wall_types import WALL_TYPES
    per = {}
    for w in doc.entities.values():
        if w.kind != "wall":
            continue
        p = w.params
        kind = str(p.get("wall_type", "generic"))
        if kind.startswith(("drywall", "isotex", "icf")):
            continue                                     # measured by their own lists (Γυψοσανίδες, Isotex, ICF)
        length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
        per[kind] = per.get(kind, 0.0) + max(0.0, length * float(p.get("height", 0.0)) - _openings_area(doc, w.id))
    pieces = _spec(doc)
    rows = []
    for kind, area in sorted(per.items()):
        name = WALL_TYPES.get(kind, (kind,))[0]
        label = "Τοιχοποιία — τύπος δεν ορίστηκε" if kind == "generic" else f"Τοιχοποιία {name}"
        rows.append((label, "m²", round(area, 2), _meta(f"masonry.{kind}", "Εμβαδόν τοίχων αυτού του τύπου από το σχέδιο, "
                                                                          "μείον πόρτες και παράθυρα.")))
        if kind in pieces:
            n = math.ceil(area * float(pieces[kind]))
            rows.append((f"Τεμάχια για {label.lower()} ({float(pieces[kind]):g}/m² από το φύλλο)".replace(".", ","), "τεμ.", n,
                         _meta(f"masonry.{kind}.pieces", "Εμβαδόν × τεμάχια ανά m² που έδωσε ο χρήστης.", "MANUFACTURER_DATA")))
    return rows


def slab_concrete_list(doc):
    """m³ of concrete of the per-room / per-storey slabs in the model: area × thickness."""
    from archforge.ui.project_outline import slab_info
    labels = {"room_floor": "Πλάκες δαπέδου", "room_roof": "Πλάκες οροφής / δώματος", "room_foundation": "Πλάκες θεμελίωσης",
              "room_ceiling": "Πλάκες οροφής"}
    vol, area = {}, {}
    for e in doc.entities.values():
        if e.kind not in labels or (e.kind == "room_roof" and str(e.params.get("roof_type", "flat")) != "flat"):
            continue
        info = slab_info(doc, e)
        if not info["area"] or not info["thickness"]:
            continue
        vol[e.kind] = vol.get(e.kind, 0.0) + float(info["area"]) * float(info["thickness"])
        area[e.kind] = area.get(e.kind, 0.0) + float(info["area"])
    rows = []
    for kind, v in sorted(vol.items()):
        rows.append((f"Σκυρόδεμα — {labels[kind]}", "m³", round(v, 2),
                     _meta(f"concrete.slab.{kind}", f"Εμβαδόν {area[kind]:.2f} m² × πάχος της πλάκας στο μοντέλο.".replace(".", ",", 1))))
    if rows:
        rows.append(("Οπλισμός πλακών — από τη στατική μελέτη", "kg", None,
                     _meta("concrete.slab.rebar", "Από τη στατική μελέτη.", "ENGINEER_REVIEW")))
    return rows


def plaster_list(doc):
    """Interior plaster = the rooms' wall faces of the take-off without tiles; exterior = outer face of exterior walls."""
    from archforge.assistant.understanding import read_drawing
    from archforge.quantities.takeoff import take_off
    rows = []
    try:
        inner = float(take_off(doc)["totals"].get("paint_walls_m2", 0.0))
    except Exception:
        inner = 0.0
    if inner > 0:
        rows.append(("Σοβάς εσωτερικός (τοίχοι χώρων, πλην πλακιδίων)", "m²", round(inner, 2),
                     _meta("plaster.interior", "Οι όψεις των τοίχων κάθε χώρου, μείον ανοίγματα και πλακάκια.")))
    outer = 0.0
    for storey in read_drawing(doc)["storeys"]:
        for wid in storey["exterior_walls"]:
            w = doc.entities.get(wid)
            if w is None or str(w.params.get("wall_type", "generic")).startswith(("drywall", "icf")):
                continue
            p = w.params
            length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
            outer += max(0.0, length * float(p.get("height", 0.0)) - _openings_area(doc, wid))
    if outer > 0:
        rows.append(("Σοβάς εξωτερικός (όψεις)", "m²", round(outer, 2),
                     _meta("plaster.exterior", "Η εξωτερική όψη των εξωτερικών τοίχων, μείον ανοίγματα.")))
    return rows


def roof_list(doc):
    """Tiled roofs: slope area per tile type; tiles only with the user's pieces/m²."""
    from archforge.structure.timber_roof import TILES
    per = {}
    for e in doc.entities.values():
        if e.kind != "pitched_roof":
            continue
        p = e.params
        ov = float(p.get("overhang", 0.0))
        plan = (abs(float(p["x1"]) - float(p["x0"])) + 2 * ov) * (abs(float(p["y1"]) - float(p["y0"])) + 2 * ov)
        tile = str(p.get("tile", "roman"))
        per[tile] = per.get(tile, 0.0) + plan / max(1e-6, math.cos(math.radians(float(p.get("pitch", 0.0)))))
    pieces = _spec(doc)
    rows = []
    for tile, area in sorted(per.items()):
        label = TILES.get(tile, (tile,))[0]
        rows.append((f"Κεραμοσκεπή — {label} (επιφάνεια κλίσης)", "m²", round(area, 2),
                     _meta(f"roof.tiles.{tile}", "Επιφάνεια των κλίσεων της στέγης από το σχέδιο (με την προεξοχή).")))
        if f"tile.{tile}" in pieces:
            n = math.ceil(area * float(pieces[f"tile.{tile}"]))
            rows.append((f"Κεραμίδια {label} ({float(pieces[f'tile.{tile}']):g}/m² από το φύλλο)".replace(".", ","), "τεμ.", n,
                         _meta(f"roof.tiles.{tile}.pieces", "Επιφάνεια × κεραμίδια ανά m² που έδωσε ο χρήστης.",
                               "MANUFACTURER_DATA")))
    return rows


def joinery_list(doc):
    """Windows and doors by kind, type, finish and size — pieces."""
    from archforge.architecture.joinery import FINISHES, TYPES, resolved
    groups = {}
    for e in doc.entities.values():
        if e.kind not in ("window", "door"):
            continue
        r = resolved(e.kind, e.params)
        w, h = float(e.params.get("width", 0.0)), float(e.params.get("height", 0.0))
        t = str(r.get("opening_type", "basic"))
        fin = str(r.get("finish", ""))
        key = (e.kind, t, fin, round(w, 2), round(h, 2))
        groups[key] = groups.get(key, 0) + 1
    rows = []
    for (kind, t, fin, w, h), n in sorted(groups.items()):
        name = TYPES[kind].get(t, t)
        what = "Παράθυρο" if kind == "window" else "Πόρτα"
        finish = FINISHES.get(fin, (fin,))[0] if fin else ""
        rows.append((f"{what} {name}" + (f", {finish}" if finish else "") + f" — {w:.2f}×{h:.2f} m".replace(".", ","), "τεμ.", n,
                     _meta(f"joinery.{kind}.{t}.{fin or 'default'}.{int(round(w * 100))}x{int(round(h * 100))}",
                           "Κουφώματα του σχεδίου με αυτόν τον τύπο και αυτό το μέγεθος.")))
    return rows
