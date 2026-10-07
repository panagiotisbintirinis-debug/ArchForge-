"""Isotex wood-cement formwork blocks: catalogue, wall types and the piece count.

An alternative way to build: Isotex blocks (cement-bonded wood fibre, H
form) are laid dry, staggered by half a block, and filled with concrete
every few courses; the result is a reinforced concrete wall in a permanent
formwork, with (HDIII) or without (HB) a graphite EPS (BASF Neopor®) insert.

Rules for the take-off (stated so they can be checked):

* Every block shows a 50 × 25 cm face: 8 blocks per m² of wall.
* Wall area per wall: axis length × height, less its doors / windows /
  openings.  Pieces = ⌈net area × 8 × (1 + waste)⌉, waste 3 % (cuts at
  corners, ends and jambs come out of whole blocks).
* Courses = ⌈height / 0.25⌉; the blocks cut at the jambs are two per course
  an opening spans (listed, already inside the total).
* Concrete fill = net area × the block's l/m² from its data sheet.  A block
  added later without a data sheet value would be estimated from the core
  thickness × 0.79 (the ratio of HB 25/16 and HB 30/19: 126 l / 16 cm and
  151 l / 19 cm) and marked as an estimate; every block in the catalogue
  below carries its data sheet value.
* Reinforcement (vertical and horizontal bars), lintels over openings and
  the ring beam belong to the structural design and are not counted here.

Values locked 2026-10-07 from Isotex's data sheets and product pages
(``DATA_SHEETS``; ETA 08/0023): concrete l/m², blocks kg/m², core and U as
published.  To be confirmed against the current data sheet of the block
ordered.  Pre-design take-off, for review.
"""
from __future__ import annotations

import math

BLOCK_LENGTH, BLOCK_HEIGHT = 0.50, 0.25
BLOCKS_PER_M2 = 1.0 / (BLOCK_LENGTH * BLOCK_HEIGHT)      # 8
WASTE = 0.03
CORE_FILL_RATIO = 0.79                                   # l/m² per mm of core ÷ 10, from HB 25/16 and HB 30/19
SOURCE = "Isotex, τεχνικά φυλλάδια τεμαχίων / ETA 08/0023 (τιμές κλειδωμένες 2026-10-07)"
PROVENANCE = ("Αναγωγή τεμαχίων Isotex: 8 τεμ./m² (όψη 50×25), καθαρό εμβαδόν τοίχων (άξονας × ύψος − ανοίγματα), "
              f"φύρα {WASTE:.0%}, σκυρόδεμα l/m² από το φυλλάδιο του τεμαχίου — οπλισμός, πρέκια και σενάζ στη στατική μελέτη. "
              "Τιμές από δημοσιευμένα στοιχεία Isotex: επιβεβαίωση με το τρέχον φυλλάδιο — προς έλεγχο μηχανικού")

# code: label, total thickness, graphite EPS insert, concrete core, concrete l/m² (None = estimate), blocks kg/m², U W/m²K
BLOCKS = {
    "HB 25/16": ("Isotex HB 25/16 (χωρίς μόνωση)", 0.25, 0.00, 0.16, 126.0, 80.0, 0.79),
    "HB 30/19": ("Isotex HB 30/19 (χωρίς μόνωση)", 0.30, 0.00, 0.19, 151.0, 85.0, 0.68),
    "HDIII 30/7": ("Isotex HDIII 30/7 (μόνωση γραφίτη 7 cm)", 0.30, 0.07, 0.15, 130.0, 80.0, 0.34),
    "HDIII 30/10": ("Isotex HDIII 30/10 (μόνωση γραφίτη 10 cm)", 0.30, 0.10, 0.12, 104.0, 80.0, 0.23),
    "HDIII 38/14": ("Isotex HDIII 38/14 (μόνωση γραφίτη 14 cm)", 0.38, 0.14, 0.15, 130.0, 88.0, 0.21),
}
_SITE = "https://www.blocchiisotex.com"
DATA_SHEETS = {   # where each locked value was read
    "HB 25/16": "https://en.blocchiisotex.com/products/formwork-block-hb-25-16/",
    "HB 30/19": _SITE + "/prodotti/blocco-cassero-hb-3019/",
    "HDIII 30/7": _SITE + "/prodotti/blocco-cassero-hdiii-30-7-grafite/",
    "HDIII 30/10": "https://en.blocchiisotex.com/products/hdiii-30-10-wood-cement-formwork-block-with-neopor-bmbcert-insulation-insert-from-basf/",
    "HDIII 38/14": _SITE + "/wp-content/uploads/2024/02/SK-Tecnica-sito-Blocco-Isotex-HDIII-38.14-gr.pdf",
}
WALL_TYPE_PREFIX = "isotex_"


def wall_type_of(code):
    return WALL_TYPE_PREFIX + code.lower().replace(" ", "_").replace("/", "_")


def code_of_wall_type(wall_type):
    for code in BLOCKS:
        if wall_type_of(code) == str(wall_type):
            return code
    return None


def wall_type_layers():
    """Wall assemblies for ``architecture.wall_types``: wood-cement shells, graphite EPS, concrete core."""
    out = {}
    for code, (label, total, eps, core, _l, _kg, _u) in BLOCKS.items():
        shell = round((total - eps - core) / 2, 4)
        layers = [("Ξυλότσιμεντο Isotex", shell, 0.11, "#b9a98c", False)]
        if eps > 0:
            layers.append(("EPS γραφίτη (Neopor®)", eps, 0.031, "#6f7780", True))
        layers += [("Σκυρόδεμα πλήρωσης", core, 2.30, "#a3a3a0", False), ("Ξυλότσιμεντο Isotex", shell, 0.11, "#b9a98c", False)]
        out[wall_type_of(code)] = (label, layers)
    return out


def concrete_per_m2(code):
    """(l/m², estimated?) for a block."""
    _label, _t, _eps, core, litres, _kg, _u = BLOCKS[code]
    if litres is not None:
        return litres, False
    return round(core * 1000 * CORE_FILL_RATIO, 1), True


def _wall_openings(doc, wall):
    out = []
    for e in doc.entities.values():
        if e.kind in ("door", "window", "opening") and e.parent_id == wall.id:
            p = e.params
            sill = float(p.get("sill", 0.0)) if e.kind == "window" else float(p.get("bottom", 0.0) or 0.0)
            out.append((float(p.get("width", 0.0)), float(p.get("height", 0.0)), sill))
    return out


def count_wall(doc, wall):
    """Pieces and concrete for one Isotex wall, or None when the wall is not Isotex."""
    code = code_of_wall_type(wall.params.get("wall_type"))
    if code is None:
        return None
    p = wall.params
    length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
    height = float(p["height"])
    openings = _wall_openings(doc, wall)
    gross = length * height
    holes = sum(w * h for w, h, _s in openings)
    net = max(0.0, gross - holes)
    courses = math.ceil(height / BLOCK_HEIGHT - 1e-9)
    jamb_cuts = sum(2 * math.ceil(min(h, height) / BLOCK_HEIGHT - 1e-9) for _w, h, _s in openings)
    litres, estimated = concrete_per_m2(code)
    kg = BLOCKS[code][5]
    return {"wall": wall.id, "name": wall.name or wall.id[:6], "z": round(float(p.get("z", 0.0)), 2), "code": code,
            "length_m": round(length, 2), "height_m": round(height, 2), "courses": courses,
            "gross_m2": round(gross, 2), "openings_m2": round(holes, 2), "net_m2": round(net, 2),
            "blocks": math.ceil(net * BLOCKS_PER_M2 * (1 + WASTE) - 1e-9), "jamb_cuts": jamb_cuts,
            "concrete_m3": round(net * litres / 1000, 2), "concrete_estimated": estimated,
            "blocks_kg": round(net * kg) if kg else None}


def take_off_isotex(doc):
    """``{"walls": [...], "by_code": {code: {...}}, "by_storey": {z: {...}}, "totals": {...}, "provenance"}``."""
    walls = [r for e in sorted(doc.entities.values(), key=lambda e: (float(e.params.get("z", 0.0)), e.id))
             if e.kind == "wall" and str(e.params.get("phase", "new")) != "demolish"
             for r in [count_wall(doc, e)] if r is not None]
    by_code, by_storey = {}, {}
    for r in walls:
        for bucket, key in ((by_code, r["code"]), (by_storey, r["z"])):
            b = bucket.setdefault(key, {"walls": 0, "net_m2": 0.0, "blocks": 0, "concrete_m3": 0.0, "jamb_cuts": 0})
            b["walls"] += 1
            b["net_m2"] = round(b["net_m2"] + r["net_m2"], 2)
            b["blocks"] += r["blocks"]
            b["concrete_m3"] = round(b["concrete_m3"] + r["concrete_m3"], 2)
            b["jamb_cuts"] += r["jamb_cuts"]
    totals = {"walls": len(walls), "net_m2": round(sum(r["net_m2"] for r in walls), 2),
              "blocks": sum(r["blocks"] for r in walls), "concrete_m3": round(sum(r["concrete_m3"] for r in walls), 2),
              "pallet_note": "παλέτες/συσκευασία: από τον προμηθευτή"}
    return {"walls": walls, "by_code": by_code, "by_storey": by_storey, "totals": totals,
            "estimated": sorted({r["code"] for r in walls if r["concrete_estimated"]}), "provenance": PROVENANCE,
            "source": SOURCE}


def isotex_html(result):
    if not result["walls"]:
        return ("<h2>Τεμάχια Isotex</h2><p>Δεν υπάρχουν τοίχοι Isotex. Διάλεξε Isotex στα Στοιχεία έργου "
                "(εξωτερικοί ή εσωτερικοί τοίχοι) ή στον τύπο ενός τοίχου.</p>")
    rows = "".join(
        f"<tr><td>{r['name']}</td><td>+{r['z']:.2f}</td><td>{r['code']}</td><td>{r['length_m']}</td><td>{r['height_m']}</td>"
        f"<td>{r['courses']}</td><td>{r['openings_m2']}</td><td>{r['net_m2']}</td><td><b>{r['blocks']}</b></td>"
        f"<td>{r['jamb_cuts']}</td><td>{r['concrete_m3']}{' *' if r['concrete_estimated'] else ''}</td></tr>"
        for r in result["walls"])
    codes = "".join(f"<tr><td>{c}</td><td>{BLOCKS[c][0]}</td><td>{v['net_m2']}</td><td><b>{v['blocks']}</b></td>"
                    f"<td>{v['concrete_m3']}</td></tr>" for c, v in result["by_code"].items())
    t = result["totals"]
    note = (f"<p>* σκυρόδεμα κατ' εκτίμηση (πυρήνας × {CORE_FILL_RATIO}) για: {', '.join(result['estimated'])} — "
            "συμπλήρωσε από το φυλλάδιο.</p>") if result["estimated"] else ""
    return ("<h2>Τεμάχια Isotex — αναγωγή</h2>"
            "<h3>Ανά τεμάχιο</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Κωδικός</th><th>Τεμάχιο</th>"
            "<th>Καθαρό m²</th><th>Τεμάχια</th><th>Σκυρόδεμα m³</th></tr>" + codes +
            f"<tr><td><b>Σύνολο</b></td><td></td><td><b>{t['net_m2']}</b></td><td><b>{t['blocks']}</b></td>"
            f"<td><b>{t['concrete_m3']}</b></td></tr></table>"
            "<h3>Ανά τοίχο</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Τοίχος</th><th>Στάθμη</th><th>Κωδικός</th>"
            "<th>Μήκος</th><th>Ύψος</th><th>Σειρές</th><th>Ανοίγματα m²</th><th>Καθαρό m²</th><th>Τεμάχια</th>"
            "<th>Κομμένα σε λαμπάδες</th><th>Σκυρόδεμα m³</th></tr>" + rows + "</table>" + note +
            f"<p><i>{PROVENANCE}<br>Πηγή: {SOURCE}</i></p>")
