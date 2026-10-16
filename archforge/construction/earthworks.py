"""Earthworks (χωματουργικά) from whatever the design gives (owner 15/10: «ανάλογα τις πληροφορίες που δίνονται
στην κατασκευή, αυτό θα αντλεί στοιχεία»).

Measured in m³ of excavation, geometry only, from what exists in the model:

* **basement** — the rooms of every storey below ±0.00, out to the outer face of its walls: plan area ×
  (ground − basement floor level);
* **foundation** — pads (B×B), tie beams (width × length) and strip footings (B × length) of the up-to-date
  structural design, each from the ground down to its bottom (``foundation.levels``) — outside a basement only.

Ground: the site terrain under the point when one is drawn, otherwise ±0.00 — and the report says which.
Not included, and said so: working space / slopes of the pit, bulking of the removed soil, backfill,
soil type — the contractor's / engineer's figures.  Nothing is measured that the design does not give.
"""
from __future__ import annotations

from archforge.core.provenance import DESIGN_DEFAULT, Rule, register

register(
    Rule("earthworks.geometry", "Εκσκαφή m³: υπόγειο (κάτοψη × βάθος από το έδαφος) και θεμέλια της στατικής επίλυσης "
         "(πέδιλα, συνδετήριες, πεδιλοδοκοί ως τον πάτο τους)", DESIGN_DEFAULT,
         note="Γεωμετρία· χωρίς χώρο εργασίας/πρανή, αφράτευση, επιχώσεις — από τον εργολάβο/μηχανικό"),
)


def _meta(code, why):
    return {"code": code, "why": why, "status": "DESIGN_DEFAULT", "source": "construction/earthworks.py"}


def _ground(doc, x, y):
    from archforge.site.terrain import terrain_height_at
    h = terrain_height_at(doc, x, y)
    return (float(h), True) if h is not None else (0.0, False)


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2.0


def _inside(poly, x, y):
    inside = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def earthworks(doc):
    """``{"rows": [...], "basis": [...], "missing": [...]}`` — rows for the price lists, and what was / was not used."""
    from archforge.assistant.understanding import read_drawing
    rows, basis, missing = [], [], []
    terrain_used = False
    basement_polys = []
    total_basement = 0.0
    for storey in read_drawing(doc)["storeys"]:
        z = float(storey["z"])
        if z >= -1e-6:
            continue
        for room in storey["rooms"]:
            poly = room["polygon"]
            cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
            g, from_terrain = _ground(doc, cx, cy)
            terrain_used |= from_terrain
            depth = g - z
            if depth > 0:
                # The pit reaches the outer face of the basement walls (room outlines run on the wall axes).
                half = max((float(w.params["thickness"]) / 2 for w in doc.entities.values()
                            if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - z) < 0.05), default=0.0)
                try:
                    from archforge.geometry.regions import offset_loop
                    ccw = poly if sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                                      for i in range(len(poly))) > 0 else poly[::-1]
                    outer = [tuple(q) for q in offset_loop(ccw, [half] * len(ccw))]
                    poly = outer if _area(outer) >= _area(poly) else poly
                except Exception:
                    pass
                total_basement += _area(poly) * depth
                basement_polys.append((poly, z))
    if total_basement:
        rows.append(("Εκσκαφή υπογείου", "m³", round(total_basement, 2),
                     _meta("earthworks.basement", "Κάτοψη των χώρων του υπογείου × βάθος από το έδαφος ως τη στάθμη του δαπέδου.")))
    foundation = 0.0
    try:
        from archforge.structure.analysis import fresh_result
        from archforge.structure.foundation import TIE_B, TIE_H, levels
        r = fresh_result(doc)
    except Exception:
        r = None
    fd = (r or {}).get("foundation") if r and not r.get("error") else None
    if fd:
        def depth_at(x, y, bottom):
            for poly, zb in basement_polys:
                if _inside(poly, x, y):
                    return max(0.0, zb - bottom)            # under the basement floor: from its level
            g, _t = _ground(doc, x, y)
            return max(0.0, g - bottom)
        for f in fd.get("footings", ()):
            _top, bottom = levels(f)
            foundation += float(f["B_m"]) ** 2 * depth_at(f["x"], f["y"], bottom) if "B_m" in f else 0.0
        for t in fd.get("ties", ()):
            mx, my = (t["a"][0] + t["b"][0]) / 2, (t["a"][1] + t["b"][1]) / 2
            bottom = float(t.get("z", 0.0)) - TIE_H
            foundation += float(t["length_m"]) * TIE_B * depth_at(mx, my, bottom)
        for s_ in fd.get("strips", ()):
            mx, my = (s_["a"][0] + s_["b"][0]) / 2, (s_["a"][1] + s_["b"][1]) / 2
            bottom = float(s_.get("z", 0.0)) - float(s_["H_m"])
            foundation += float(s_["length_m"]) * float(s_["B_m"]) * depth_at(mx, my, bottom)
    elif any(e.kind == "structural_column" for e in doc.entities.values()):
        missing.append("θεμέλια: δεν υπάρχει ενημερωμένη στατική επίλυση (Φέρων ▸ Επίλυση) — η εκσκαφή τους δεν μετρήθηκε")
    else:
        missing.append("θεμέλια: δεν υπάρχει φέρων οργανισμός στο σχέδιο")
    if foundation > 0:
        rows.append(("Εκσκαφή θεμελίων (πέδιλα, συνδετήριες, πεδιλοδοκοί)", "m³", round(foundation, 2),
                     _meta("earthworks.foundation", "Αποτύπωμα κάθε θεμελίου × βάθος από το έδαφος ως τον πάτο του.")))
    if rows:
        total = sum(r_[2] for r_ in rows)
        rows.append(("Φόρτωση και μεταφορά προϊόντων εκσκαφής (όγκος εκσκαφής, χωρίς αφράτευση)", "m³", round(total, 2),
                     _meta("earthworks.removal", "Ο όγκος που βγαίνει από την εκσκαφή· η αφράτευση από τον εργολάβο.")))
    basis.append("έδαφος από το τοπογραφικό/έδαφος του σχεδίου" if terrain_used
                 else "έδαφος στο ±0,00 (δεν δόθηκε έδαφος στη θέση της εκσκαφής)")
    if not total_basement:
        missing.append("υπόγειο: δεν υπάρχει όροφος κάτω από το ±0,00 με χώρους")
    return {"rows": rows, "basis": basis, "missing": missing}


def earthworks_list(doc):
    return earthworks(doc)["rows"]
