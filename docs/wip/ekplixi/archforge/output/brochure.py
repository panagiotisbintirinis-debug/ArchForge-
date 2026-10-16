"""Φυλλάδιο ακινήτου για μεσίτες (PDF): κάτοψη πώλησης ανά όροφο, πίνακας εμβαδών, χαρακτηριστικά.

A listing sheet, not a technical drawing: rooms filled in soft colours by use,
walls as solid poché, doors / windows simple, furniture as light lines, each
room with its name and net m², north arrow and scale bar — no dimension
chains.  Every number comes from the Document through the rules written in
``AREA_RULES`` (shown on the sheet as a footnote); nothing is typed twice.

Integration (για τον lead — μενού «Αρχείο → Φυλλάδιο ακινήτου (PDF)…»)::

    from archforge.output.brochure import export_brochure
    result = export_brochure(window.doc, path, title=None, notes=None)
    # → {"pages": n, "path": str}; title=None παίρνει το «Έργο» της προσφοράς.

``property_areas(doc)`` is the pure table data (per storey and total: net,
gross, balconies, semi-open, terraces, counts) and can be shown elsewhere
(e.g. a dialog) without drawing anything.  Needs a QApplication (Qt fonts).
"""
from __future__ import annotations

import datetime
import math
import re
import unicodedata

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter,
                           QPolygonF)

from archforge.output.pdf import FONT, Sheet, _extras, _north, _on_segment_dist, _storey_walls, level_name, net_room, \
    wall_pieces

PAGE_W, PAGE_H = 210.0, 297.0           # A4 portrait (mm)
MARGIN = 14.0
DARK = QColor(38, 34, 31)
CREAM = QColor(246, 238, 227)
ACCENT = QColor(196, 132, 70)
TEXT = QColor(48, 44, 40)
MUTED = QColor(118, 112, 104)
RULE = QColor(214, 207, 196)
POCHE = QColor(52, 50, 50)
GLASS = QColor(96, 140, 176)
FURNITURE = QColor(168, 162, 154)
BROCHURE_SCALES = (50, 75, 100, 125, 150, 200, 250, 300, 400, 500)
FOOTER = "ArchForge — From dream to dream home"

# Uses of rooms: label and soft fill colour (listing-sheet palette).
CATEGORIES = {
    "living": ("Καθιστικό", QColor(246, 230, 200)),
    "kitchen": ("Κουζίνα", QColor(250, 215, 190)),
    "bedroom": ("Υπνοδωμάτιο", QColor(212, 228, 245)),
    "bathroom": ("Μπάνιο", QColor(200, 236, 232)),
    "wc": ("WC", QColor(214, 238, 236)),
    "office": ("Γραφείο", QColor(242, 236, 196)),
    "corridor": ("Διάδρομος / χολ", QColor(236, 233, 228)),
    "storage": ("Βοηθητικός χώρος", QColor(230, 224, 238)),
    "balcony": ("Μπαλκόνι / βεράντα", QColor(222, 237, 210)),
    "semi_open": ("Ημιυπαίθριος", QColor(232, 240, 214)),
    "terrace": ("Ταράτσα", QColor(214, 233, 200)),
    "other": ("Χώρος", QColor(243, 240, 234)),
}
OPEN_CATEGORIES = ("balcony", "semi_open", "terrace")      # outdoor / semi-open: not in net or gross

# Keywords of room names (lower case, accents removed), checked in this order.
_KEYWORDS = (
    ("bathroom", ("μπανι", "λουτρ", "bath", "ντουζ", "shower")),
    ("wc", ("wc", "w.c", "τουαλετ", "toilet")),
    ("kitchen", ("κουζιν", "kitchen")),
    ("bedroom", ("υπνοδωμ", "κρεβατοκαμ", "bedroom", "master", "παιδικ", "ξενων", "κοιτων", "υπνου")),
    ("semi_open", ("ημιυπαιθρ", "στεγασμεν", "loggia", "λοτζια", "porch")),
    ("balcony", ("μπαλκον", "εξωστ", "βεραντ", "balcon", "veranda")),
    ("terrace", ("ταρατσ", "δωμα", "terrace")),
    ("office", ("γραφει", "office", "study")),
    ("living", ("σαλον", "καθιστικ", "living", "τραπεζαρ", "dining", "lounge")),
    ("storage", ("αποθηκ", "λεβητ", "πλυσταρ", "laundry", "storage", "utility", "γκαραζ", "garage", "closet",
                 "wardrobe", "ντουλαπ")),
    ("corridor", ("διαδρομ", "χολ", "hall", "εισοδ", "entrance", "κλιμακ", "corridor", "stair")),
)
_FURNITURE_HINTS = (("bedroom", ("bed", "κρεβατ")), ("living", ("sofa", "καναπ", "couch")))

AREA_RULES = (
    "Καθαρό: εμβαδό δαπέδου μέσα στις παρειές των τοίχων (όπως η επιμέτρηση ανά χώρο).",
    "Μικτό: κλειστοί χώροι μαζί με τους τοίχους τους, έως τις εξωτερικές παρειές των εξωτερικών τοίχων.",
    "Μπαλκόνια / βεράντες / ημιυπαίθριοι: χώροι με αυτό το όνομα, καθαρό εμβαδό — εκτός καθαρού και μικτού.",
    "Ταράτσες: ακάλυπτο μέρος της επίπεδης πλάκας χώρου του κάτω ορόφου, στη στάθμη του ορόφου από πάνω.",
    "Ενδεικτικά — όχι επίσημη επιμέτρηση· τα επίσημα εμβαδά δίνει ο μηχανικός (προς έλεγχο μηχανικού).",
)


def _plain(text):
    s = unicodedata.normalize("NFD", str(text or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _category_from_text(text):
    t = _plain(text)
    if not t:
        return None
    found = [cat for cat, words in _KEYWORDS if any(w in t for w in words)]
    if "kitchen" in found and "living" in found:
        return "living"                                     # «σαλόνι – κουζίνα»: open plan, a living room
    return found[0] if found else None


def _default_name(name):
    return re.fullmatch(r"(Room|Χώρος)\s*\d+", str(name or "").strip()) is not None


def room_category(doc, room):
    """(category, source) of a reading room: by its name / use, else by its fixtures and furniture."""
    meta = doc.room_metadata(room["signature"]) if room.get("signature") else {}
    for text in (meta.get("use"), None if _default_name(room["name"]) else room["name"]):
        cat = _category_from_text(text)
        if cat:
            return cat, "όνομα/χρήση"
    if room.get("use") in ("bathroom", "wc", "kitchen"):
        return room["use"], "εξοπλισμός"
    for eid in room.get("contents", ()):
        e = doc.entities.get(eid)
        if e is None or e.kind not in ("library_object", "box", "component"):
            continue
        t = _plain(" ".join([str(e.name or ""), str(e.params.get("asset", "")), str(e.params.get("name", ""))]))
        for cat, words in _FURNITURE_HINTS:
            if any(w in t for w in words):
                return cat, "έπιπλα"
    return "other", None


def _display_name(room, category, index):
    if not _default_name(room["name"]):
        return str(room["name"])
    return CATEGORIES[category][0] if category != "other" else f"Χώρος {index}"


# ---------------------------------------------------------------- polygon helpers (metres)
def _shoelace(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2.0


def _inside(poly, x, y):
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _path_of(polys):
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    for poly in polys:
        sub = QPainterPath()
        sub.addPolygon(QPolygonF([QPointF(float(x), float(y)) for x, y in poly]))
        sub.closeSubpath()
        path = path.united(sub)
    return path


def _path_area(path):
    """Area of a (united) path: outer loops add, holes (nested an odd number of times) subtract."""
    loops = [[(p.x(), p.y()) for p in poly] for poly in path.simplified().toSubpathPolygons()]
    loops = [lp[:-1] if len(lp) > 1 and lp[0] == lp[-1] else lp for lp in loops]
    loops = [lp for lp in loops if len(lp) >= 3 and abs(_shoelace(lp)) > 1e-9]
    total = 0.0
    for i, lp in enumerate(loops):
        (ax, ay), (bx, by) = lp[0], lp[1]
        L = math.hypot(bx - ax, by - ay) or 1.0
        mx, my, nx, ny = (ax + bx) / 2, (ay + by) / 2, -(by - ay) / L * 1e-4, (bx - ax) / L * 1e-4
        probe = (mx + nx, my + ny) if _inside(lp, mx + nx, my + ny) else (mx - nx, my - ny)
        depth = sum(1 for j, other in enumerate(loops) if j != i and _inside(other, *probe))
        total += abs(_shoelace(lp)) * (1 if depth % 2 == 0 else -1)
    return total


def _wall_quad(wall, walls):
    """Whole wall (no openings) as a quad, ends extended into the walls they meet."""
    p = wall.params
    ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-6:
        return None
    ux, uy = (bx - ax) / L, (by - ay) / L
    nx, ny = -uy, ux
    t = float(p.get("thickness", .2))

    def joined(x, y):
        return any(o.id != wall.id and _on_segment_dist(x, y, *(float(o.params[k]) for k in ("x1", "y1", "x2", "y2"))) < .01
                   for o in walls)
    a = -t / 2 if joined(ax, ay) else 0.0
    b = L + t / 2 if joined(bx, by) else L
    return [(ax + ux * a + nx * t / 2, ay + uy * a + ny * t / 2), (ax + ux * b + nx * t / 2, ay + uy * b + ny * t / 2),
            (ax + ux * b - nx * t / 2, ay + uy * b - ny * t / 2), (ax + ux * a - nx * t / 2, ay + uy * a - ny * t / 2)]


def _wall_bounds_closed_room(wall, closed_polys):
    p = wall.params
    ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(bx - ax, by - ay) or 1.0
    nx, ny = -(by - ay) / L, (bx - ax) / L
    d = float(p.get("thickness", .2)) / 2 + .03
    for f in (.25, .5, .75):
        mx, my = ax + (bx - ax) * f, ay + (by - ay) * f
        if any(_inside(poly, mx + s * nx * d, my + s * ny * d) for poly in closed_polys for s in (1, -1)):
            return True
    return False


# ---------------------------------------------------------------- the survey (pure data)
def _flat_roofs(doc):
    """[(base_z, parts)] of every flat room roof: its slab outline, only the part open to the sky."""
    from archforge.architecture.roof_need import room_face_of
    from archforge.architecture.rooms import room_slab_geometry
    out = []
    for e in doc.entities.values():
        if e.kind != "room_roof" or str(e.params.get("roof_type", "flat")) != "flat":
            continue
        try:
            found = room_face_of(doc, e)
            geo = room_slab_geometry(doc, e)
        except Exception:
            continue
        if found is None or geo is None:
            continue
        parts = geo.get("parts") or [geo["points"]]
        out.append((float(found[1]), [[(float(q[0]), float(q[1])) for q in part] for part in parts]))
    return out


def _survey(doc):
    from archforge.assistant.understanding import read_drawing
    reading = read_drawing(doc)
    storeys = [s for s in reading["storeys"] if s["walls"]]
    zs = [float(s["z"]) for s in storeys]
    flat = _flat_roofs(doc)
    out, geo = [], []
    index = 0
    for k, s in enumerate(storeys):
        z = float(s["z"])
        walls = _storey_walls(doc, z)
        rooms, closed_polys = [], []
        for r in s["rooms"]:
            index += 1
            cat, source = room_category(doc, r)
            net = net_room(doc, r, z)[0]
            rooms.append({"name": _display_name(r, cat, index), "category": cat, "category_source": source,
                          "net_m2": round(net, 2), "polygon": r["polygon"], "signature": r["signature"]})
            if cat not in OPEN_CATEGORIES:
                closed_polys.append(r["polygon"])
        shell = [q for w in walls if _wall_bounds_closed_room(w, closed_polys) for q in [_wall_quad(w, walls)] if q]
        gross = _path_area(_path_of(closed_polys + shell)) if closed_polys else 0.0
        # Terraces: open flat roofs of the storeys below, at this storey's level (reached from here).
        below = zs[k - 1] if k else None
        terraces = [part for bz, parts in flat if below is not None and abs(bz - below) < .05 for part in parts]
        row = {"name": level_name(s["name"]), "level": s["name"], "z": z, "rooms": [
                   {k_: v for k_, v in r.items() if k_ not in ("polygon", "signature")} for r in rooms],
               "net_m2": round(sum(r["net_m2"] for r in rooms if r["category"] not in OPEN_CATEGORIES), 2),
               "gross_m2": round(gross, 2),
               "balcony_m2": round(sum(r["net_m2"] for r in rooms if r["category"] == "balcony"), 2),
               "semi_open_m2": round(sum(r["net_m2"] for r in rooms if r["category"] == "semi_open"), 2),
               "terrace_m2": round(sum(r["net_m2"] for r in rooms if r["category"] == "terrace")
                                   + sum(abs(_shoelace(p)) for p in terraces), 2),
               "bedrooms": sum(1 for r in rooms if r["category"] == "bedroom"),
               "bathrooms": sum(1 for r in rooms if r["category"] == "bathroom"),
               "wcs": sum(1 for r in rooms if r["category"] == "wc"),
               "kitchens": sum(1 for r in rooms if r["category"] == "kitchen")}
        out.append(row)
        geo.append({"storey": s, "rooms": rooms, "terraces": terraces, "walls": walls})
    top = zs[-1] if zs else None
    roof_deck = sum(abs(_shoelace(p)) for bz, parts in flat if top is not None and abs(bz - top) < .05 for p in parts)
    pitched = any(e.kind == "pitched_roof" for e in doc.entities.values())
    roof = ("mixed" if pitched and roof_deck > 0 else "tiled" if pitched else "flat" if roof_deck > 0 else None)
    keys = ("net_m2", "gross_m2", "balcony_m2", "semi_open_m2", "terrace_m2")
    totals = {k_: round(sum(r[k_] for r in out), 2) for k_ in keys}
    totals.update({k_: sum(r[k_] for r in out) for k_ in ("bedrooms", "bathrooms", "wcs", "kitchens")})
    totals["storeys"] = len(out)
    areas = {"storeys": out, "totals": totals, "roof_deck_m2": round(roof_deck, 2), "roof": roof, "rules": AREA_RULES}
    return areas, geo


def property_areas(doc):
    """Πίνακας εμβαδών: ``{"storeys": [row], "totals": {...}, "roof_deck_m2", "roof", "rules"}``.

    Each row: name, z, rooms [{name, category, category_source, net_m2}], net_m2, gross_m2,
    balcony_m2, semi_open_m2, terrace_m2, bedrooms, bathrooms, wcs, kitchens.  ``roof_deck_m2`` is the
    flat roof (δώμα) of the top storey; ``roof`` is 'tiled' / 'flat' / 'mixed' / None.
    """
    return _survey(doc)[0]


def _m2(v, digits=1):
    return f"{v:,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def features(doc, areas):
    """«Χαρακτηριστικά»: short lines, each derived from the model (nothing assumed)."""
    from archforge.project.brief import FLOOR_SYSTEMS, INTERIOR_WALLS, PROJECT_TYPES, WALL_SYSTEMS, get_brief
    t = areas["totals"]
    lines = []
    names = ", ".join(r["name"] for r in areas["storeys"])
    lines.append(f"{t['storeys']} {'όροφος' if t['storeys'] == 1 else 'όροφοι'}" + (f" ({names})" if names else ""))
    if t["bedrooms"]:
        lines.append(f"{t['bedrooms']} {'υπνοδωμάτιο' if t['bedrooms'] == 1 else 'υπνοδωμάτια'}")
    baths = []
    if t["bathrooms"]:
        baths.append(f"{t['bathrooms']} {'μπάνιο' if t['bathrooms'] == 1 else 'μπάνια'}")
    if t["wcs"]:
        baths.append(f"{t['wcs']} WC")
    if baths:
        lines.append(" · ".join(baths))
    kitchens = [r for s in areas["storeys"] for r in s["rooms"] if r["category"] == "kitchen"]
    if kitchens:
        lines.append("Κουζίνα " + _m2(sum(r["net_m2"] for r in kitchens)) + " m²")
    outdoor = [("Ταράτσες", t["terrace_m2"]), ("Μπαλκόνια / βεράντες", t["balcony_m2"]), ("Ημιυπαίθριοι", t["semi_open_m2"])]
    for label, v in outdoor:
        if v > 0:
            lines.append(f"{label} {_m2(v)} m²")
    roof = {"tiled": "Στέγη: κεραμοσκεπή", "flat": f"Στέγη: δώμα (ταράτσα κτιρίου {_m2(areas['roof_deck_m2'])} m²)",
            "mixed": f"Στέγη: κεραμοσκεπή και δώμα {_m2(areas['roof_deck_m2'])} m²"}.get(areas["roof"])
    if roof:
        lines.append(roof)
    brief = get_brief(doc)
    if brief:
        lines.append(f"Κατασκευή: {PROJECT_TYPES.get(brief['project_type'], '—')}")
        ws = brief.get("wall_system_text") or WALL_SYSTEMS.get(brief["wall_system"], ("—",))[0]
        lines.append(f"Τοιχοποιία: {ws}")
        iw = brief.get("interior_walls_text") or INTERIOR_WALLS.get(brief["interior_walls"], ("—",))[0]
        lines.append(f"Εσωτερικοί τοίχοι: {iw}")
        lines.append(f"Πατώματα: {FLOOR_SYSTEMS.get(brief['floor_system'], '—')}")
    counts = {}
    for e in doc.entities.values():
        counts[e.kind] = counts.get(e.kind, 0) + 1
    types = [str(e.params.get("point_type", "")) for e in doc.entities.values()
             if e.kind in ("plumbing_point", "electrical_point")]
    heat_words = ("καλοριφ", "radiator", "fancoil", "fan coil", "ενδοδαπ", "underfloor", "αντλια θερμ", "heat pump",
                  "λεβητ", "boiler", "θερμανσ", "heating")
    heating = sorted({str(e.name or e.kind) for e in doc.entities.values()
                      if e.kind in ("mep_terminal", "mechanical_part", "library_object", "component")
                      and any(w in _plain(f"{e.name} {e.params}") for w in heat_words)})
    if heating:
        lines.append("Θέρμανση: " + ", ".join(heating[:3]))
    if types.count("air_conditioner"):
        lines.append(f"Κλιματιστικά: {types.count('air_conditioner')}")
    if "solar_heater" in types:
        lines.append("Ηλιακός θερμοσίφωνας")
    mep = []
    if counts.get("plumbing_point"):
        mep.append("ύδρευση")
    if counts.get("drainage_point"):
        mep.append("αποχέτευση")
    if counts.get("electrical_point"):
        mep.append("ηλεκτρολογικά")
    if counts.get("ventilation_point"):
        mep.append("αερισμός")
    if mep:
        lines.append("Η/Μ μελετημένα: " + ", ".join(mep) + " (προς έλεγχο μηχανικού)")
    if counts.get("structural_column") or counts.get("structural_beam"):
        lines.append("Στατική προμελέτη φέροντα (προς έλεγχο μηχανικού)")
    return lines


# ---------------------------------------------------------------- drawing
def _text_w(sh, s, size, bold=False):
    f = QFont(FONT); f.setPointSizeF(size); f.setBold(bold)
    return QFontMetricsF(f, sh.p.device()).horizontalAdvance(str(s)) / sh.k


def _label_point(poly):
    """A point well inside the polygon (largest clearance on a grid) and that clearance (m)."""
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    best, clear = None, -1.0
    n = 24
    for i in range(1, n):
        for j in range(1, n):
            x = min(xs) + (max(xs) - min(xs)) * i / n
            y = min(ys) + (max(ys) - min(ys)) * j / n
            if not _inside(poly, x, y):
                continue
            d = min(_on_segment_dist(x, y, *poly[m], *poly[(m + 1) % len(poly)]) for m in range(len(poly)))
            # Prefer the middle: a small pull towards the bounding-box centre.
            d -= .02 * math.hypot(x - (min(xs) + max(xs)) / 2, y - (min(ys) + max(ys)) / 2)
            if d > clear:
                best, clear = (x, y), d
    if best is None:
        best, clear = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), 0.0
    return best, max(clear, 0.0)


def _storey_bounds(doc, g):
    xs, ys = [], []
    for w in g["walls"]:
        q = _wall_quad(w, g["walls"])
        if q:
            xs += [p[0] for p in q]; ys += [p[1] for p in q]
    for part in g["terraces"]:
        xs += [p[0] for p in part]; ys += [p[1] for p in part]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 1.0, 1.0)


def _pick_scale(bounds, box_w, box_h, pad=1.2):
    for s in BROCHURE_SCALES:
        k = 1000.0 / s
        if all((x1 - x0 + 2 * pad) * k <= box_w and (y1 - y0 + 2 * pad) * k <= box_h for x0, y0, x1, y1 in bounds):
            return s
    return BROCHURE_SCALES[-1]


def _scale_bar(sh, x, y, scale):
    k = 1000.0 / scale
    step = 1 if scale <= 150 else (2 if scale <= 300 else 5)
    for i in range(5):
        sh.rect(x + i * step * k, y, step * k, 1.4, color=POCHE, width=.12, fill=POCHE if i % 2 == 0 else QColor(255, 255, 255))
    for i in (0, 5):
        sh.text(x + i * step * k, y + 3.6, "0" if i == 0 else f"{5 * step} m", size=6.5, align="center", color=MUTED, w=14)
    sh.text(x + 5 * step * k + 9, y + .7, f"1:{scale} (Α4)", size=6.5, color=MUTED, w=30)


def _draw_plan(sh, doc, g, box, scale):
    """Marketing plan of one storey centred in ``box`` (x, y, w, h mm)."""
    from archforge.mep.ventilation import exterior_walls
    z = float(g["storey"]["z"])
    x0, y0, x1, y1 = _storey_bounds(doc, g)
    k = 1000.0 / scale
    bx, by, bw, bh = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = bx + bw / 2, by + bh / 2

    def to_mm(x, y):
        return ox + (x - cx) * k, oy - (y - cy) * k
    # Terraces below the storey (open roofs of the storey underneath).
    for part in g["terraces"]:
        sh.poly([to_mm(*q) for q in part], color=QColor(150, 178, 128), width=.25, fill=CATEGORIES["terrace"][1])
    # Rooms: soft fills by use.
    for r in g["rooms"]:
        sh.poly([to_mm(*q) for q in r["polygon"]], color=QColor(255, 255, 255, 0), width=.01, fill=CATEGORIES[r["category"]][1])
    for kind, pts in _extras(doc, z):
        mm = [to_mm(*q) for q in pts]
        if kind == "polygon":
            sh.poly(mm, color=FURNITURE, width=.12)
        else:
            for a, b in zip(mm, mm[1:]):
                sh.line(*a, *b, color=FURNITURE, width=.12)
    pieces, holes = [], []
    for w in g["walls"]:
        pc, hl = wall_pieces(doc, w, g["walls"])
        pieces += pc; holes += hl
    for poly in pieces:
        sh.poly([to_mm(*q) for q in poly], color=POCHE, width=.05, fill=POCHE)
    outward = {w.id: n for w, n in exterior_walls(doc, z)}
    for u0, u1, e, f in holes:
        (axx, ayy), (ux, uy), (nx, ny), t = f["a"], f["u"], f["n"], f["t"]

        def P(u, s):
            return to_mm(axx + ux * u + nx * s, ayy + uy * u + ny * s)
        if e.kind == "window":
            sh.poly([P(u0, t / 2), P(u1, t / 2), P(u1, -t / 2), P(u0, -t / 2)], color=POCHE, width=.12,
                    fill=QColor(255, 255, 255))
            sh.line(*P(u0, 0.0), *P(u1, 0.0), color=GLASS, width=.3)
        elif e.kind == "door":
            w_ = u1 - u0
            out = outward.get(e.parent_id)
            sgn = -1.0 if out is None or (out[0] * nx + out[1] * ny) > 0 else 1.0
            Q = lambda u, s_: P(u, sgn * -s_)      # noqa: E731 — swing into the building
            sh.line(*Q(u0, -t / 2), *Q(u0, -t / 2 - w_), color=TEXT, width=.25)
            path = QPainterPath()
            for i in range(19):
                a = math.pi / 2 * i / 18
                q = Q(u0 + w_ * math.sin(a), -t / 2 - w_ * math.cos(a))
                (path.moveTo if i == 0 else path.lineTo)(sh.pt(*q))
            sh.pen(QColor(150, 144, 136), .12); sh.p.drawPath(path)
    for cid in g["storey"].get("columns", ()):
        c = doc.get(cid).params
        w2, d2 = float(c.get("width", .3)) / 2, float(c.get("depth", .3)) / 2
        x, y = float(c["x"]), float(c["y"])
        sh.poly([to_mm(x - w2, y - d2), to_mm(x + w2, y - d2), to_mm(x + w2, y + d2), to_mm(x - w2, y + d2)],
                color=POCHE, width=.05, fill=POCHE)
    # Labels: name and net m², sized to fit the room.
    labels = [(r["name"], r["net_m2"], r["polygon"]) for r in g["rooms"]]
    labels += [("Ταράτσα", abs(_shoelace(p)), p) for p in g["terraces"]]
    for name, a, poly in labels:
        (lx, ly), clear = _label_point(poly)
        mx, my = to_mm(lx, ly)
        room_w = 2 * clear * k - 1.5
        size = 9.0
        while size > 5.0 and max(_text_w(sh, name.upper(), size * .82, True), _text_w(sh, f"{_m2(a)} m²", size)) > room_w:
            size -= .5
        sh.text(mx, my - size * .27, name.upper(), size=size * .82, bold=True, align="center", color=TEXT, w=max(room_w, 30))
        sh.text(mx, my + size * .33, f"{_m2(a)} m²", size=size, align="center", color=MUTED, w=max(room_w, 30))
    return to_mm


def _legend(sh, x, y, cats, max_w):
    cx = x
    for cat in cats:
        label = CATEGORIES[cat][0]
        w = 5 + _text_w(sh, label, 7) + 6
        if cx + w > x + max_w:
            cx, y = x, y + 5.5
        sh.rect(cx, y - 1.6, 3.2, 3.2, color=RULE, width=.12, fill=CATEGORIES[cat][1])
        sh.text(cx + 4.6, y, label, size=7, color=TEXT, w=w)
        cx += w
    return y


def _footer(sh, page, pages):
    sh.line(MARGIN, PAGE_H - 13, PAGE_W - MARGIN, PAGE_H - 13, color=RULE, width=.2)
    sh.text(MARGIN, PAGE_H - 9, FOOTER, size=7.5, color=MUTED, w=120, italic=True)
    sh.text(PAGE_W - MARGIN, PAGE_H - 9, f"{page} / {pages}", size=7.5, align="right", color=MUTED, w=30)


def _header(sh, title, subtitle, small=False):
    h = 24.0 if small else 42.0
    sh.rect(0, 0, PAGE_W, h, color=DARK, width=.01, fill=DARK)
    sh.rect(0, h, PAGE_W, 1.2, color=ACCENT, width=.01, fill=ACCENT)
    if small:
        sh.text(MARGIN, 10, title, size=14, bold=True, color=CREAM, w=150)
        sh.text(MARGIN, 17, subtitle, size=8.5, color=QColor(233, 190, 140), w=180)
    else:
        sh.text(MARGIN, 10, "ΠΑΡΟΥΣΙΑΣΗ ΑΚΙΝΗΤΟΥ", size=7.5, bold=True, color=QColor(233, 190, 140), w=120)
        sh.text(MARGIN, 21, title, size=22, bold=True, color=CREAM, w=PAGE_W - 2 * MARGIN)
        sh.text(MARGIN, 32, subtitle, size=10, color=QColor(226, 214, 198), w=PAGE_W - 2 * MARGIN)
    return h + 1.2


def _tiles(sh, y, tiles):
    n = len(tiles)
    gap = 3.0
    w = (PAGE_W - 2 * MARGIN - gap * (n - 1)) / n
    for i, (value, caption) in enumerate(tiles):
        x = MARGIN + i * (w + gap)
        sh.rect(x, y, w, 17, color=RULE, width=.15, fill=QColor(250, 247, 242))
        sh.text(x + w / 2, y + 7, value, size=14, bold=True, align="center", color=TEXT, w=w - 2)
        sh.text(x + w / 2, y + 13.2, caption, size=6.8, align="center", color=MUTED, w=w - 2)
    return y + 17


def _plan_section(sh, doc, row, g, top, bottom, scale):
    sh.text(MARGIN, top + 3, f"Κάτοψη — {row['name']}", size=13, bold=True, color=TEXT, w=120)
    info = [f"καθαρό {_m2(row['net_m2'])} m²", f"μικτό {_m2(row['gross_m2'])} m²"]
    if row["terrace_m2"]:
        info.append(f"ταράτσα {_m2(row['terrace_m2'])} m²")
    if row["balcony_m2"] + row["semi_open_m2"]:
        info.append(f"μπαλκόνια {_m2(row['balcony_m2'] + row['semi_open_m2'])} m²")
    sh.text(PAGE_W - MARGIN, top + 3, " · ".join(info), size=8.5, align="right", color=MUTED, w=120)
    sh.line(MARGIN, top + 7, PAGE_W - MARGIN, top + 7, color=RULE, width=.2)
    legend_y = bottom - 4
    box = (MARGIN, top + 10, PAGE_W - 2 * MARGIN, legend_y - 8 - (top + 10))
    _draw_plan(sh, doc, g, box, scale)
    _north(sh, PAGE_W - MARGIN - 5, top + 20)
    cats = [c for c in CATEGORIES if any(r["category"] == c for r in g["rooms"]) or (c == "terrace" and g["terraces"])]
    _legend(sh, MARGIN, legend_y, cats, PAGE_W - 2 * MARGIN - 60)
    _scale_bar(sh, PAGE_W - MARGIN - 50, legend_y - 1.4, scale)


def _table(sh, x, y, cols, rows, row_h=7.0, size=8.5):
    total_w = sum(c[1] for c in cols)
    sh.rect(x, y, total_w, row_h, color=DARK, width=.01, fill=DARK)
    cx = x
    for title, w, align in cols:
        sh.text(cx + (2 if align == "left" else (w / 2 if align == "center" else w - 2)), y + row_h / 2, title,
                size=size - .5, bold=True, align=align, color=CREAM, w=w - 3)
        cx += w
    y += row_h
    for i, row in enumerate(rows):
        bold = isinstance(row, dict)
        cells = row["cells"] if bold else row
        if bold:
            sh.rect(x, y, total_w, row_h, color=RULE, width=.01, fill=QColor(240, 232, 220))
        elif i % 2:
            sh.rect(x, y, total_w, row_h, color=QColor(250, 247, 242), width=.01, fill=QColor(250, 247, 242))
        cx = x
        for (title, w, align), v in zip(cols, cells):
            sh.text(cx + (2 if align == "left" else (w / 2 if align == "center" else w - 2)), y + row_h / 2, v,
                    size=size, bold=bold, align=align, color=TEXT, w=w - 3)
            cx += w
        y += row_h
    sh.line(x, y, x + total_w, y, color=DARK, width=.3)
    return y


def _summary_page(sh, doc, areas, notes):
    y = _header(sh, "Πίνακας εμβαδών", "Ανά όροφο και συνολικά · ενδεικτικά, από το μοντέλο", small=True) + 10
    cols = [("Όροφος", 34, "left"), ("Καθαρό m²", 24, "right"), ("Μικτό m²", 24, "right"),
            ("Μπαλκόνια / βεράντες", 30, "right"), ("Ημιυπαίθριοι", 24, "right"), ("Ταράτσες", 22, "right"),
            ("Υπνοδ.", 12, "center"), ("Μπάνια / WC", 12, "center")]
    scale_w = (PAGE_W - 2 * MARGIN) / sum(c[1] for c in cols)
    cols = [(t, w * scale_w, a) for t, w, a in cols]
    num = lambda v: _m2(v, 2) if v else "—"      # noqa: E731
    rows = [[r["name"], num(r["net_m2"]), num(r["gross_m2"]), num(r["balcony_m2"]), num(r["semi_open_m2"]),
             num(r["terrace_m2"]), str(r["bedrooms"] or "—"), f"{r['bathrooms']} / {r['wcs']}"] for r in areas["storeys"]]
    t = areas["totals"]
    rows.append({"cells": ["Σύνολο", num(t["net_m2"]), num(t["gross_m2"]), num(t["balcony_m2"]), num(t["semi_open_m2"]),
                           num(t["terrace_m2"]), str(t["bedrooms"] or "—"), f"{t['bathrooms']} / {t['wcs']}"]})
    y = _table(sh, MARGIN, y, cols, rows)
    if areas["roof_deck_m2"]:
        y += 5
        sh.text(MARGIN, y, f"Δώμα (επίπεδη στέγη τελευταίου ορόφου): {_m2(areas['roof_deck_m2'], 2)} m² — εκτός των παραπάνω.",
                size=8, color=TEXT, w=PAGE_W - 2 * MARGIN)
    y += 6
    for rule in AREA_RULES:
        sh.text(MARGIN, y, rule, size=6.8, color=MUTED, w=PAGE_W - 2 * MARGIN, italic=True); y += 4.0
    # Rooms per storey (small two-column list).
    y += 5
    sh.text(MARGIN, y, "Χώροι", size=13, bold=True, color=TEXT, w=100); y += 4
    sh.line(MARGIN, y, PAGE_W - MARGIN, y, color=RULE, width=.2); y += 5
    col_w = (PAGE_W - 2 * MARGIN - 8) / 2
    entries = []
    for r in areas["storeys"]:
        entries.append((r["name"], None, None))
        for room in r["rooms"]:
            entries.append((room["name"], room["net_m2"], room["category"]))
    per_col = math.ceil(len(entries) / 2)
    y_rooms = y
    for i, (name, a, cat) in enumerate(entries):
        col, row = divmod(i, per_col)
        x = MARGIN + col * (col_w + 8)
        yy = y_rooms + row * 5.2
        if a is None:
            sh.text(x, yy, name, size=8.5, bold=True, color=ACCENT, w=col_w)
        else:
            sh.rect(x + 1, yy - 1.4, 2.8, 2.8, color=RULE, width=.1, fill=CATEGORIES[cat][1])
            sh.text(x + 6, yy, name, size=8, color=TEXT, w=col_w - 30)
            sh.text(x + col_w, yy, f"{_m2(a, 2)} m²", size=8, align="right", color=MUTED, w=30)
    y = y_rooms + per_col * 5.2 + 6
    # Features.
    sh.text(MARGIN, y, "Χαρακτηριστικά", size=13, bold=True, color=TEXT, w=100); y += 4
    sh.line(MARGIN, y, PAGE_W - MARGIN, y, color=RULE, width=.2); y += 5
    feats = features(doc, areas)
    per_col = math.ceil(len(feats) / 2)
    for i, s in enumerate(feats):
        col, row = divmod(i, per_col)
        x = MARGIN + col * (col_w + 8)
        yy = y + row * 5.6
        sh.rect(x + 1.2, yy - .9, 1.8, 1.8, color=ACCENT, width=.01, fill=ACCENT)
        sh.text(x + 5.5, yy, s, size=8.3, color=TEXT, w=col_w - 6)
    y += per_col * 5.6 + 4
    if notes:
        lines = [ln for ln in str(notes).splitlines() if ln.strip()] or [str(notes)]
        wrapped = []
        for ln in lines:
            words, cur = ln.split(), ""
            for wd in words:
                if _text_w(sh, (cur + " " + wd).strip(), 8.5) > PAGE_W - 2 * MARGIN - 10:
                    wrapped.append(cur); cur = wd
                else:
                    cur = (cur + " " + wd).strip()
            wrapped.append(cur)
        h = 9 + 4.6 * len(wrapped)
        sh.rect(MARGIN, y, PAGE_W - 2 * MARGIN, h, color=RULE, width=.15, fill=QColor(250, 247, 242))
        sh.rect(MARGIN, y, 1.2, h, color=ACCENT, width=.01, fill=ACCENT)
        sh.text(MARGIN + 5, y + 4.5, "Σημειώσεις", size=9, bold=True, color=TEXT, w=100)
        for i, ln in enumerate(wrapped):
            sh.text(MARGIN + 5, y + 9.5 + i * 4.6, ln, size=8.5, color=TEXT, w=PAGE_W - 2 * MARGIN - 10)


def export_brochure(doc, path, title=None, notes=None):
    """Write the property brochure PDF; returns ``{"pages": n, "path": str}``."""
    from archforge.quantities.quote import settings
    areas, geo = _survey(doc)
    s = settings(doc)
    title = title or s["project"] or "Κατοικία"
    t = areas["totals"]
    bits = [f"Μικτό {_m2(t['gross_m2'])} m²"]
    if t["bedrooms"]:
        bits.append(f"{t['bedrooms']} {'υπνοδωμάτιο' if t['bedrooms'] == 1 else 'υπνοδωμάτια'}")
    if t["bathrooms"] + t["wcs"]:
        bits.append(f"{t['bathrooms'] + t['wcs']} {'μπάνιο/WC' if t['bathrooms'] + t['wcs'] == 1 else 'μπάνια/WC'}")
    outdoor = t["terrace_m2"] + t["balcony_m2"] + t["semi_open_m2"]
    if outdoor:
        bits.append(f"εξωτερικοί χώροι {_m2(outdoor)} m²")
    subtitle = " · ".join(bits)

    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Portrait, QMarginsF(0, 0, 0, 0)))
    writer.setTitle(f"{title} — ArchForge"); writer.setCreator("ArchForge")
    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    sh = Sheet(painter, 300 / 25.4)
    pages = max(1, len(geo)) + 1
    plan_w = PAGE_W - 2 * MARGIN
    first_top = 42 + 1.2 + 6 + 17 + 8                      # header, tiles, gap
    plan_h = (PAGE_H - 22) - first_top - 22                 # section title, legend
    scale = _pick_scale([_storey_bounds(doc, g) for g in geo], plan_w, plan_h) if geo else 100
    date = datetime.date.today().strftime("%d/%m/%Y")
    page = 1
    y = _header(sh, title, subtitle)
    sh.text(PAGE_W - MARGIN, 10, date, size=7.5, align="right", color=QColor(200, 188, 172), w=40)
    tiles = [(_m2(t["gross_m2"]) + " m²", "Μικτό εμβαδό"), (_m2(t["net_m2"]) + " m²", "Καθαρό εμβαδό"),
             (str(t["bedrooms"]), "Υπνοδωμάτια"), (f"{t['bathrooms']} / {t['wcs']}", "Μπάνια / WC"),
             (str(t["storeys"]), "Όροφοι" if t["storeys"] != 1 else "Όροφος")]
    y = _tiles(sh, y + 6, tiles) + 8
    if geo:
        _plan_section(sh, doc, areas["storeys"][0], geo[0], y, PAGE_H - 20, scale)
    else:
        sh.text(PAGE_W / 2, PAGE_H / 2, "Δεν υπάρχουν τοίχοι στο έργο ακόμα.", size=12, align="center", color=MUTED, w=150)
    _footer(sh, page, pages)
    for row, g in zip(areas["storeys"][1:], geo[1:]):
        writer.newPage(); page += 1
        top = _header(sh, title, subtitle, small=True) + 8
        _plan_section(sh, doc, row, g, top, PAGE_H - 20, scale)
        _footer(sh, page, pages)
    writer.newPage(); page += 1
    _summary_page(sh, doc, areas, notes)
    _footer(sh, page, pages)
    painter.end()
    return {"pages": page, "path": str(path)}
