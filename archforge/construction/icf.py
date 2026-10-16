"""ICF (insulated concrete forms): catalogue, wall types and the piece count.

An alternative way to build, like Isotex: hollow blocks of expanded
polystyrene (EPS on both faces, joined by moulded / plastic webs) are laid
dry, staggered, and filled with concrete; the result is a reinforced
concrete wall (load-bearing: no columns) with its insulation on both faces.
Generic types, no brand: «ICF EPS 2×7,5 — πυρήνας 15».

Rules for the take-off (stated so they can be checked):

* Straight block face 1.20 × 0.40 m (the usual European size): 2.08 blocks
  per m² of wall.  Courses = ⌈height / 0.40⌉ (the top course is cut).
* 90° corner blocks (≈ 0.80 + 0.40 m legs, 0.40 m high): one per corner per
  course; a corner is a point where exactly two ICF walls of the storey meet
  at 60°–120°.  Each corner block stands in for about one straight block
  (1.20 m of outer face), so straights = ⌈(net area / 0.48 − corner blocks)
  × (1 + waste)⌉, waste 5 % (cuts at ends, jambs and the top course).  A
  T-junction is built with cut straight blocks (no special piece).
* Closures (end caps / bucks): the perimeter of every door / window /
  opening plus the height of every free wall end, in metres.
* Ties / webs are part of the block (nothing separate to count); the
  alignment bracing is counted in metres of wall (hired, per supplier).
* Concrete fill = net area × the type's l/m²: from a published data sheet
  where one is quoted (``DATA``), else the core × 0.94 (the ratio of the
  published 150 / 200 mm cores: 140 l / 15 cm, 190 l / 20 cm) marked as an
  estimate.
* Reinforcement (vertical and horizontal bars), lintels and ring beams
  belong to the structural design and are not counted here.

Pre-design take-off: to be confirmed with the data sheet of the block ordered.
"""
from __future__ import annotations

import math

BLOCK_LENGTH, BLOCK_HEIGHT = 1.20, 0.40
BLOCKS_PER_M2 = 1.0 / (BLOCK_LENGTH * BLOCK_HEIGHT)      # 2.083
CORNER_LEGS = (0.80, 0.40)
WASTE = 0.05
CORE_FILL_RATIO = 0.94                                   # l/m² per mm of core ÷ 10, from the 150 / 200 mm cores
CORNER_ANGLE = (60.0, 120.0)
JOIN_TOLERANCE = 0.05
SOURCE = ("Δημοσιευμένα στοιχεία κατασκευαστών ICF (τεμάχιο 1200×400 mm, EPS 65–100 mm ανά όψη, πυρήνας 150/200 mm, "
          "γωνιακό ≈800×400 mm — icf-structures.co.uk «ICF Blocks»· σκυρόδεμα 0,14 / 0,19 m³/m² για πυρήνα 150 / 200 mm — "
          "althermicf.com «ICF Block Specification»)")
PROVENANCE = ("Αναγωγή ICF: τεμάχιο 120×40 (2,08 τεμ./m²), καθαρό εμβαδόν τοίχων (άξονας × ύψος − ανοίγματα), γωνιακά ανά γωνία × σειρές, "
              f"φύρα {WASTE:.0%}, κλεισίματα = περίμετρος ανοιγμάτων + ελεύθερα άκρα, σκυρόδεμα l/m² ανά τύπο — "
              "οπλισμός, πρέκια και σενάζ στη στατική μελέτη. Επιβεβαίωση με το φυλλάδιο του τεμαχίου — προς έλεγχο μηχανικού")
WALL_TYPE_PREFIX = "icf_"

# code: label, EPS per face (m), concrete core (m), concrete l/m² (None = estimate from the core)
BLOCKS = {
    "15/65": ("ICF EPS 2×6,5 — πυρήνας 15", 0.065, 0.15, None),
    "15/75": ("ICF EPS 2×7,5 — πυρήνας 15", 0.075, 0.15, 140.0),
    "20/75": ("ICF EPS 2×7,5 — πυρήνας 20", 0.075, 0.20, 190.0),
    "20/100": ("ICF EPS 2×10 — πυρήνας 20", 0.10, 0.20, None),
    "25/65": ("ICF EPS 2×6,5 — πυρήνας 25", 0.065, 0.25, None),
}
DATA = {   # where a quoted value was read (published as 0.014 / 0.019 m³/m², i.e. 140 / 190 l/m²)
    "15/75": "https://www.althermicf.com/resources/copy-of-technical",
    "20/75": "https://www.althermicf.com/resources/copy-of-technical",
}


def wall_type_of(code):
    return WALL_TYPE_PREFIX + code.replace("/", "_")


def code_of_wall_type(wall_type):
    for code in BLOCKS:
        if wall_type_of(code) == str(wall_type):
            return code
    return None


def thickness(code):
    _label, eps, core, _l = BLOCKS[code]
    return round(2 * eps + core, 4)


def wall_type_layers():
    """Wall assemblies for ``architecture.wall_types``: EPS, concrete core, EPS."""
    out = {}
    for code, (label, eps, core, _l) in BLOCKS.items():
        e = ("EPS καλουπιού ICF", eps, 0.036, "#e9eef0", True)
        out[wall_type_of(code)] = (label, [e, ("Σκυρόδεμα πυρήνα ICF", core, 2.30, "#a3a3a0", False), e])
    return out


def concrete_per_m2(code):
    """(l/m², estimated?) for a block type."""
    _label, _eps, core, litres = BLOCKS[code]
    if litres is not None:
        return litres, False
    return round(core * 1000 * CORE_FILL_RATIO, 1), True


def _length(p):
    return math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))


def _icf_walls(doc):
    return [e for e in sorted(doc.entities.values(), key=lambda e: (float(e.params.get("z", 0.0)), e.id))
            if e.kind == "wall" and str(e.params.get("phase", "new")) != "demolish"
            and code_of_wall_type(e.params.get("wall_type")) is not None]


def joints(doc, walls=None):
    """``{wall id: {"corners": n, "free_ends": n}}``: corners counted once (on the first wall), free ends per wall."""
    walls = _icf_walls(doc) if walls is None else walls
    ends = {}
    for w in walls:
        p = w.params
        z = round(float(p.get("z", 0.0)), 2)
        for i, (x, y) in enumerate(((float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"])))):
            key = (z, round(x / JOIN_TOLERANCE), round(y / JOIN_TOLERANCE))
            ends.setdefault(key, []).append((w, i))
    out = {w.id: {"corners": 0, "free_ends": 0} for w in walls}
    # every other wall end (of any wall) closes the end: an ICF wall against a brick wall is not free
    ids = {w.id for w in walls}
    others = {(round(float(e.params.get("z", 0.0)), 2), round(float(e.params[k]) / JOIN_TOLERANCE), round(float(e.params[k2]) / JOIN_TOLERANCE))
              for e in doc.entities.values() if e.kind == "wall" and e.id not in ids
              for k, k2 in (("x1", "y1"), ("x2", "y2"))}
    for key, at in ends.items():
        if len(at) == 1:
            if key not in others:
                out[at[0][0].id]["free_ends"] += 1
            continue
        if len(at) != 2:
            continue
        (a, ia), (b, ib) = at
        da = _direction(a.params, ia)
        db = _direction(b.params, ib)
        angle = math.degrees(math.acos(max(-1.0, min(1.0, da[0] * db[0] + da[1] * db[1]))))
        if CORNER_ANGLE[0] <= angle <= CORNER_ANGLE[1]:
            out[a.id]["corners"] += 1
    return out


def _direction(p, end):
    """Unit vector from the shared end into the wall."""
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    d = ((x2 - x1) / L, (y2 - y1) / L)
    return d if end == 0 else (-d[0], -d[1])


def count_wall(doc, wall, joint=None):
    """Pieces and concrete for one ICF wall, or None when the wall is not ICF."""
    from archforge.construction.isotex import _wall_openings
    code = code_of_wall_type(wall.params.get("wall_type"))
    if code is None:
        return None
    joint = joint or joints(doc).get(wall.id, {"corners": 0, "free_ends": 0})
    p = wall.params
    length, height = _length(p), float(p["height"])
    openings = _wall_openings(doc, wall)
    gross = length * height
    holes = sum(w * h for w, h, _s in openings)
    net = max(0.0, gross - holes)
    courses = math.ceil(height / BLOCK_HEIGHT - 1e-9)
    corner_blocks = joint["corners"] * courses
    closures = sum(2 * (w + min(h, height)) for w, h, _s in openings) + joint["free_ends"] * height
    litres, estimated = concrete_per_m2(code)
    straight = max(0, math.ceil((net * BLOCKS_PER_M2 - corner_blocks) * (1 + WASTE) - 1e-9))
    return {"wall": wall.id, "name": wall.name or wall.id[:6], "z": round(float(p.get("z", 0.0)), 2), "code": code,
            "length_m": round(length, 2), "height_m": round(height, 2), "courses": courses,
            "gross_m2": round(gross, 2), "openings_m2": round(holes, 2), "net_m2": round(net, 2),
            "blocks": straight, "corners": joint["corners"], "corner_blocks": corner_blocks,
            "free_ends": joint["free_ends"], "closures_m": round(closures, 2),
            "concrete_m3": round(net * litres / 1000, 2), "concrete_estimated": estimated}


def take_off_icf(doc):
    """``{"walls": [...], "by_code": {...}, "by_storey": {...}, "totals": {...}, "estimated", "provenance", "source"}``."""
    icf = _icf_walls(doc)
    js = joints(doc, icf)
    walls = [count_wall(doc, w, js[w.id]) for w in icf]
    by_code, by_storey = {}, {}
    keys = ("net_m2", "blocks", "corner_blocks", "closures_m", "concrete_m3", "length_m")
    for r in walls:
        for bucket, key in ((by_code, r["code"]), (by_storey, r["z"])):
            b = bucket.setdefault(key, {"walls": 0, **{k: 0 for k in keys}})
            b["walls"] += 1
            for k in keys:
                b[k] = round(b[k] + r[k], 2)
    totals = {"walls": len(walls), **{k: round(sum(r[k] for r in walls), 2) for k in keys}}
    return {"walls": walls, "by_code": by_code, "by_storey": by_storey, "totals": totals,
            "estimated": sorted({r["code"] for r in walls if r["concrete_estimated"]}), "provenance": PROVENANCE,
            "source": SOURCE}


def icf_list(doc):
    r = take_off_icf(doc)
    if not r["walls"]:
        return []
    rows = []
    for c, v in r["by_code"].items():
        rows += [(f"Τεμάχιο {BLOCKS[c][0]} — ευθύ 120×40×{thickness(c) * 100:.0f} cm", "τεμ.", int(v["blocks"])),
                 (f"Τεμάχιο {BLOCKS[c][0]} — γωνιακό 90°", "τεμ.", int(v["corner_blocks"]))]
    t = r["totals"]
    rows += [("Κλεισίματα ανοιγμάτων / άκρων (τελικά τεμάχια ή ξυλότυπος)", "m", t["closures_m"]),
             ("Σκυρόδεμα πλήρωσης πυρήνα" + (" (μέρος κατ' εκτίμηση)" if r["estimated"] else ""), "m³", t["concrete_m3"]),
             ("Οπλισμός τοιχωμάτων (κατακόρυφος/οριζόντιος) — από τη στατική μελέτη", "kg", None),
             ("Πρέκια / σενάζ — από τη στατική μελέτη", "m", None),
             ("Σύστημα ευθυγράμμισης / αντιστήριξης (ενοικίαση)", "m", t["length_m"]),
             ("Εργασία τοποθέτησης τεμαχίων ICF", "m²", t["net_m2"]),
             ("Εργασία σκυροδέτησης πλήρωσης", "m³", t["concrete_m3"])]
    return [row for row in rows if row[2] is None or row[2]]


def icf_html(result):
    if not result["walls"]:
        return ("<h2>Τεμάχια ICF</h2><p>Δεν υπάρχουν τοίχοι ICF. Διάλεξε ICF στα Στοιχεία έργου "
                "(εξωτερικοί τοίχοι) ή στον τύπο ενός τοίχου.</p>")
    rows = "".join(
        f"<tr><td>{r['name']}</td><td>+{r['z']:.2f}</td><td>{BLOCKS[r['code']][0]}</td><td>{r['length_m']}</td><td>{r['height_m']}</td>"
        f"<td>{r['courses']}</td><td>{r['openings_m2']}</td><td>{r['net_m2']}</td><td><b>{r['blocks']}</b></td>"
        f"<td>{r['corner_blocks']}</td><td>{r['closures_m']}</td><td>{r['concrete_m3']}{' *' if r['concrete_estimated'] else ''}</td></tr>"
        for r in result["walls"])
    codes = "".join(f"<tr><td>{BLOCKS[c][0]}</td><td>{v['net_m2']}</td><td><b>{int(v['blocks'])}</b></td>"
                    f"<td>{int(v['corner_blocks'])}</td><td>{v['concrete_m3']}</td></tr>" for c, v in result["by_code"].items())
    storeys = "".join(f"<tr><td>+{z:.2f}</td><td>{v['net_m2']}</td><td>{int(v['blocks'])}</td><td>{int(v['corner_blocks'])}</td>"
                      f"<td>{v['concrete_m3']}</td></tr>" for z, v in sorted(result["by_storey"].items()))
    t = result["totals"]
    note = (f"<p>* σκυρόδεμα κατ' εκτίμηση (πυρήνας × {CORE_FILL_RATIO}) για: "
            f"{', '.join(BLOCKS[c][0] for c in result['estimated'])} — συμπλήρωσε από το φυλλάδιο.</p>") if result["estimated"] else ""
    head = "<th>Καθαρό m²</th><th>Ευθέα</th><th>Γωνιακά</th><th>Σκυρόδεμα m³</th></tr>"
    return ("<h2>Τεμάχια ICF — αναγωγή</h2>"
            "<h3>Ανά τύπο</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Τύπος</th>" + head + codes +
            f"<tr><td><b>Σύνολο</b></td><td><b>{t['net_m2']}</b></td><td><b>{int(t['blocks'])}</b></td>"
            f"<td><b>{int(t['corner_blocks'])}</b></td><td><b>{t['concrete_m3']}</b></td></tr></table>"
            "<h3>Ανά όροφο</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Στάθμη</th>" + head + storeys + "</table>"
            "<h3>Ανά τοίχο</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Τοίχος</th><th>Στάθμη</th><th>Τύπος</th>"
            "<th>Μήκος</th><th>Ύψος</th><th>Σειρές</th><th>Ανοίγματα m²</th><th>Καθαρό m²</th><th>Ευθέα</th>"
            "<th>Γωνιακά</th><th>Κλεισίματα m</th><th>Σκυρόδεμα m³</th></tr>" + rows + "</table>" + note +
            f"<p>Κλεισίματα: {t['closures_m']} m · ευθυγράμμιση/αντιστήριξη: {t['length_m']} m τοίχου · "
            "σύνδεσμοι (webs) ενσωματωμένοι στο τεμάχιο.</p>"
            f"<p><i>{PROVENANCE}<br>Πηγή: {SOURCE}</i></p>")
