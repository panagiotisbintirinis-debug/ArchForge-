"""Formwork sheet (ξυλότυπος): one A4 landscape page per storey slab.

For each storey that carries a frame it draws the slab over that storey seen
from above, the way the site reads it:

* columns of the storey filled black with their mark and section
  («Κ3 40/40» — the same mark as in the Properties and the analysis);
* beams whose top is the slab, outlined, with mark and section along them
  («Δ5 25/50»);
* slab panels (one per room, from the slab pre-design) as «Π1 h=20» with
  the bearing direction: one arrow for one-way, a cross for two-way;
* the storey's walls faint, for orientation;
* chained dimensions between column axes along the top and the left side,
  and the overall length;
* a member table (mark, section, length / height, material) and the notes
  (concrete, steel, «προς έλεγχο στατικού μηχανικού»).

Everything is read from the Document; nothing is typed twice.
"""
from __future__ import annotations

import datetime
import math

from PySide6.QtCore import QMarginsF, QRectF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter

from archforge.output.pdf import (DIM, INK, SCALES, Sheet, _dimension, _north, _scale_bar, _table, _title_block,
                                  level_name, wall_pieces, _storey_walls)

MEMBER_INK = QColor(20, 20, 20)
SLAB_INK = QColor(30, 90, 160)
FAINT = QColor(200, 200, 200)
MAX_ROWS = 30
BAND_INK = QColor(200, 90, 20)


def _section(e):
    p = e.params
    if p.get("profile"):
        return str(p["profile"])
    if e.kind == "structural_column":
        return f"{float(p['width']) * 100:.0f}/{float(p['depth']) * 100:.0f}"
    return f"{float(p['width']) * 100:.0f}/{float(p['height']) * 100:.0f}"


MATERIALS = {"reinforced_concrete": "Ο/Σ", "steel": "Χάλυβας", "timber": "Ξύλο", "aluminium": "Αλουμίνιο", "generic": "—"}


def storey_frames(doc):
    """``[{"storey", "z", "top", "columns", "beams", "slabs"}]`` for each storey with columns or beams."""
    from archforge.assistant.understanding import read_drawing
    from archforge.structure.marks import reading_key
    storeys = [s for s in read_drawing(doc)["storeys"] if s["walls"]]
    levels = sorted({float(z) for z in doc.levels.values()} | {float(s["z"]) for s in storeys})
    try:
        from archforge.structure.slabs import design_slabs
        slabs = design_slabs(doc)["panels"]
    except Exception:                                    # slab pre-design is optional on the sheet
        slabs = []
    out = []
    for s in storeys:
        z = float(s["z"])
        above = [v for v in levels if v > z + 1.0]
        top = above[0] if above else None
        cols = [e for e in doc.entities.values() if e.kind == "structural_column" and abs(float(e.params["z"]) - z) < 0.05
                and str(e.params.get("role", "structural")) == "structural" and str(e.params.get("phase", "new")) != "demolish"]
        if top is None:
            top = max([float(c.params["z"]) + float(c.params["height"]) for c in cols], default=z + 3.0)
        beams = [e for e in doc.entities.values() if e.kind == "structural_beam"
                 and str(e.params.get("role", "structural")) == "structural" and str(e.params.get("phase", "new")) != "demolish"
                 and z + 1.0 < float(e.params["z"]) + float(e.params["height"]) <= top + 0.10]
        if not cols and not beams:
            continue
        out.append({"storey": s, "z": z, "top": top, "columns": sorted(cols, key=reading_key),
                    "beams": sorted(beams, key=reading_key),
                    "slabs": [p for p in slabs if p["storey"] == s["name"]]})
    return out


def level_genitive(name):
    """«ισογείου», «1ου ορόφου», «υπογείου» — for «Ξυλότυπος οροφής …»."""
    import re
    m = re.match(r"Floor (\d+)$", str(name))
    if m:
        return f"{int(m.group(1)) - 1}ου ορόφου"
    return {"Ground": "ισογείου", "XY": "ισογείου", "Basement": "υπογείου", "Roof": "δώματος"}.get(str(name), str(name))


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1.0)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def slab_label_point(polygon, beams, holes=()):
    """Where «Π1 h=20» reads clearly: the point of the panel farthest from every beam axis."""
    xs = [p[0] for p in polygon]; ys = [p[1] for p in polygon]
    from archforge.assistant.understanding import centroid
    best, score = centroid(polygon), -1.0
    lines = [tuple(float(b.params[k]) for k in ("x1", "y1", "x2", "y2")) for b in beams]
    for i in range(1, 8):
        for j in range(1, 8):
            x = min(xs) + (max(xs) - min(xs)) * i / 8; y = min(ys) + (max(ys) - min(ys)) * j / 8
            d = min((_seg_dist(x, y, *ln) for ln in lines), default=1e9)
            d = min(d, x - min(xs), max(xs) - x, y - min(ys), max(ys) - y)
            for hx0, hy0, hx1, hy1 in holes:                 # keep clear of stair wells
                d = min(d, math.hypot(max(hx0 - x, 0, x - hx1), max(hy0 - y, 0, y - hy1)))
            if d > score + 1e-9:
                best, score = (x, y), d
    return best


def _axes(values, tol=0.05):
    out = []
    for v in sorted(values):
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


def formwork_page(sh, doc, frame, sheet_no, project, date, slab_start=1):
    """Draw one ξυλότυπος page; returns ``(scale, next slab number, member rows not shown)``."""
    from archforge.structure.analysis.settings import get_settings
    storey, z, top = frame["storey"], frame["z"], frame["top"]
    walls = _storey_walls(doc, z)
    pieces = []
    for w in walls:
        pieces += wall_pieces(doc, w, walls)[0]
    pts = [q for poly in pieces for q in poly]
    for c in frame["columns"]:
        pts.append((float(c.params["x"]), float(c.params["y"])))
    for b in frame["beams"]:
        pts += [(float(b.params["x1"]), float(b.params["y1"])), (float(b.params["x2"]), float(b.params["y2"]))]
    xs = [q[0] for q in pts] or [0.0]; ys = [q[1] for q in pts] or [0.0]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    margin = 2.6
    box_w, box_h = 186.0, 150.0
    scale = next((s for s in SCALES if (x1 - x0 + 2 * margin) * 1000 / s <= box_w and (y1 - y0 + 2 * margin) * 1000 / s <= box_h), SCALES[-1])
    k = 1000.0 / scale
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = 10 + box_w / 2, 16 + box_h / 2

    def to_mm(x, y):
        return ox + (x - cx) * k, oy - (y - cy) * k
    title = f"Ξυλότυπος οροφής {level_genitive(storey['name'])} (+{top:.2f})"
    sh.text(12, 8, title, size=13, bold=True, w=220)
    # Walls: faint, for orientation only.
    for poly in pieces:
        sh.poly([to_mm(*q) for q in poly], color=FAINT, width=.12, fill=QColor(242, 242, 242))
    # Slab panels: mark, thickness, bearing direction.
    n = slab_start
    rooms = {r["signature"]: r for r in storey["rooms"]}
    placed = []
    for p in frame["slabs"]:
        r = rooms.get(p["signature"])
        if r is not None:
            placed.append((slab_label_point(r["polygon"], frame["beams"], [o["box"] for o in p.get("openings", ())]), p))
    placed.sort(key=lambda item: (-round(item[0][1], 1), round(item[0][0], 1)))   # reading order, like Κ/Δ
    for point, p in placed:
        mx, my = to_mm(*point)
        sh.text(mx, my - 5.5, p.get("mark") or f"Πλ{n}", size=9, bold=True, align="center", color=SLAB_INK, w=30)
        sh.text(mx, my - 2.2, f"h={float(p['h']) * 100:.0f}", size=7, align="center", color=SLAB_INK, w=30)
        L = 9.0
        horizontal = p["short_dir"] == "x"
        if horizontal or "δύο" in p["kind"]:
            sh.line(mx - L, my + 3.0, mx + L, my + 3.0, color=SLAB_INK, width=.2)
            for s_ in (-1, 1):
                sh.line(mx + s_ * L, my + 3.0, mx + s_ * (L - 1.4), my + 2.3, color=SLAB_INK, width=.2)
                sh.line(mx + s_ * L, my + 3.0, mx + s_ * (L - 1.4), my + 3.7, color=SLAB_INK, width=.2)
        if not horizontal or "δύο" in p["kind"]:
            sh.line(mx, my + 3.0 - 3.6, mx, my + 3.0 + 3.6, color=SLAB_INK, width=.2)
            for s_ in (-1, 1):
                ye = my + 3.0 + s_ * 3.6
                sh.line(mx, ye, mx - .7, ye - s_ * 1.4, color=SLAB_INK, width=.2)
                sh.line(mx, ye, mx + .7, ye - s_ * 1.4, color=SLAB_INK, width=.2)
        # Reinforcement of the panel: bottom both ways, top over the supports.
        other = "y" if p["short_dir"] == "x" else "x"
        sh.text(mx, my + 8.0, f"κάτω {p['bottom_short']} ({p['short_dir']}) / {p['bottom_long']} ({other})", size=5.8,
                align="center", color=SLAB_INK, w=50)
        if p.get("top_support") and p["top_support"] != "—":
            sh.text(mx, my + 10.4, f"άνω στηρίξεις {p['top_support']}", size=5.8, align="center", color=SLAB_INK, w=50)
        n += 1
    # Stair wells: the opening crossed out, the reinforcement bands along its free edges.
    for p in frame["slabs"]:
        for o in p.get("openings", ()):
            x0_, y0_, x1_, y1_ = o["box"]
            box = [to_mm(x0_, y0_), to_mm(x1_, y0_), to_mm(x1_, y1_), to_mm(x0_, y1_)]
            sh.poly(box, color=MEMBER_INK, width=.3, fill=QColor(255, 255, 255))
            sh.line(*box[0], *box[2], width=.15); sh.line(*box[1], *box[3], width=.15)
            for b in o["bands"]:
                w_ = b["width_m"]
                strip = {"y0": (x0_, y0_ - w_, x1_, y0_), "y1": (x0_, y1_, x1_, y1_ + w_),
                         "x0": (x0_ - w_, y0_, x0_, y1_), "x1": (x1_, y0_, x1_ + w_, y1_)}[b["side"]]
                a_, b_ = to_mm(strip[0], strip[3]), to_mm(strip[2], strip[1])
                sh.pen(BAND_INK, .2, Qt.PenStyle.DashLine)
                sh.p.drawRect(QRectF(sh.pt(*a_), sh.pt(*b_)))
                mx_, my_ = (a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2
                sh.text(mx_, my_, f"{b['bottom']}", size=5.2, bold=True, align="center", color=BAND_INK, w=14,
                        angle=0 if b["along"] == "x" else -90)
            (tx, ty) = to_mm(x0_, y1_ + (0.45 if any(b["side"] == "y1" for b in o["bands"]) else 0.0))
            sh.text(tx, ty - 2.2, f"Οπή σκάλας {o['size'][0]:.2f}×{o['size'][1]:.2f}" + (" ⚠" if o["warning"] else ""),
                    size=6, bold=True, color=BAND_INK if not o["warning"] else QColor(190, 30, 30), w=50)
    # Beams: outline and «Δ5 25/50» along them.
    for b in frame["beams"]:
        p = b.params
        ax, ay, bx, by = (float(p[k_]) for k_ in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        h2 = float(p["width"]) / 2
        quad = [(ax + nx * h2, ay + ny * h2), (bx + nx * h2, by + ny * h2), (bx - nx * h2, by - ny * h2), (ax - nx * h2, ay - ny * h2)]
        sh.poly([to_mm(*q) for q in quad], color=MEMBER_INK, width=.3, fill=QColor(255, 255, 255))
        (mx, my) = to_mm((ax + bx) / 2 + nx * (h2 + .18), (ay + by) / 2 + ny * (h2 + .18))
        ang = -math.degrees(math.atan2(uy, ux))
        if ang > 90.001 or ang < -89.999:
            ang += 180
        sh.text(mx, my, f"{b.name} {_section(b)}", size=6.5, bold=True, align="center", w=40, angle=ang)
    # Columns: filled, «Κ3 40/40» at the corner.
    for c in frame["columns"]:
        p = c.params
        w2, d2 = float(p["width"]) / 2, float(p["depth"]) / 2
        x, y = float(p["x"]), float(p["y"])
        rot = math.radians(float(p.get("rotation", 0.0)))
        cs, sn = math.cos(rot), math.sin(rot)
        corners = [(x + u * cs - v * sn, y + u * sn + v * cs) for u, v in ((-w2, -d2), (w2, -d2), (w2, d2), (-w2, d2))]
        sh.poly([to_mm(*q) for q in corners], color=MEMBER_INK, width=.25, fill=MEMBER_INK)
        tx, ty = to_mm(x + w2, y + d2)
        sh.text(tx + .8, ty - 2.2, f"{c.name}", size=7, bold=True, w=20)
        sh.text(tx + .8, ty + .4, _section(c), size=6, w=20, color=QColor(70, 70, 70))
    # Axis dimensions between columns: along the top and the left.
    col_xy = [(float(c.params["x"]), float(c.params["y"])) for c in frame["columns"]]
    if len(col_xy) >= 2:
        ax_ = _axes([q[0] for q in col_xy]); ay_ = _axes([q[1] for q in col_xy])
        ytop, xleft = y1 + 0.2, x0 - 0.2
        for a_, b_ in zip(ax_, ax_[1:]):
            _dimension(sh, (a_, ytop), (b_, ytop), (0, 1), 6.0, b_ - a_, to_mm)
        if len(ax_) > 2:
            _dimension(sh, (ax_[0], ytop), (ax_[-1], ytop), (0, 1), 12.0, ax_[-1] - ax_[0], to_mm)
        for a_, b_ in zip(ay_, ay_[1:]):
            _dimension(sh, (xleft, a_), (xleft, b_), (-1, 0), 6.0, b_ - a_, to_mm)
        if len(ay_) > 2:
            _dimension(sh, (xleft, ay_[0]), (xleft, ay_[-1]), (-1, 0), 12.0, ay_[-1] - ay_[0], to_mm)
    # Member table and notes on the right.
    rows = [[c.name, _section(c), f"{float(c.params['height']):.2f}", MATERIALS.get(str(c.params.get("construction")), "—")]
            for c in frame["columns"]]
    rows += [[b.name, _section(b), f"{math.hypot(float(b.params['x2']) - float(b.params['x1']), float(b.params['y2']) - float(b.params['y1'])):.2f}",
              MATERIALS.get(str(b.params.get("construction")), "—")] for b in frame["beams"]]
    cols = [("Μέλος", 14, "left"), ("Διατομή", 20, "center"), ("L/H m", 16, "right"), ("Υλικό", 20, "left")]
    shown, rest = rows[:MAX_ROWS], rows[MAX_ROWS:]
    _table(sh, 202, 16, cols, shown, row_h=4.4, size=6.5)
    s = get_settings(doc)
    notes = [f"Σκυρόδεμα {s['concrete']} · χάλυβας B500C", f"Πλάκες h={float(s['slab_thickness']) * 100:.0f} cm (προδιάσταση)",
             "Διαστάσεις σε m, μεταξύ αξόνων κολονών", "Προμελέτη — προς έλεγχο στατικού μηχανικού"]
    if rest:
        notes.insert(0, f"+{len(rest)} μέλη στον πίνακα της επόμενης σελίδας")
    ops = [o for p in frame["slabs"] for o in p.get("openings", ())]
    if ops:
        notes.insert(0, "Οπές σκάλας: ζώνες ενίσχυσης 40 cm (πορτοκαλί), ίδιος οπλισμός κάτω και άνω, "
                        "συνδ. Ø8/20, 2Ø12 διαγώνια στις γωνίες, lb=40Ø")
        notes[1:1] = [f"⚠ {o['warning']}" for o in ops if o["warning"]]
    import textwrap
    lines = [ln for t in notes for ln in textwrap.wrap(t, 58)]
    y = 176 - 3.4 * len(lines)
    for t in lines:
        sh.text(202, y, t, size=6, w=85, color=QColor(190, 30, 30) if t.startswith("⚠") else QColor(80, 80, 80)); y += 3.4
    _north(sh, 190, 30)
    _scale_bar(sh, 14, 190, scale)
    _title_block(sh, f"Ξυλότυπος οροφής {level_genitive(storey['name'])}", scale, sheet_no, project, date)
    return scale, n, rest


def foundation_of(doc):
    """The foundation (footings, tie beams) from the structural analysis, or None."""
    if not any(e.kind == "structural_column" for e in doc.entities.values()):
        return None
    try:
        from archforge.structure.analysis import analyze_cached
        fd = (analyze_cached(doc) or {}).get("foundation")
    except Exception:
        return None
    return fd if fd and fd.get("footings") else None


def foundation_page(sh, doc, fd, sheet_no, project, date):
    """Ξυλότυπος θεμελίωσης: footings B×B with their mesh, tie beams with bars and stirrups, the columns on them."""
    from archforge.structure.foundation import TIE_B, PROVENANCE
    fts, ties = fd["footings"], fd["ties"]
    pts = []
    for f in fts:
        B = float(f["B_m"]) / 2
        pts += [(f["x"] - B, f["y"] - B), (f["x"] + B, f["y"] + B)]
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    margin = 2.6
    box_w, box_h = 186.0, 150.0
    scale = next((s for s in SCALES if (x1 - x0 + 2 * margin) * 1000 / s <= box_w and (y1 - y0 + 2 * margin) * 1000 / s <= box_h), SCALES[-1])
    k = 1000.0 / scale
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = 10 + box_w / 2, 16 + box_h / 2

    def to_mm(x, y):
        return ox + (x - cx) * k, oy - (y - cy) * k
    sh.text(12, 8, "Ξυλότυπος θεμελίωσης (πέδιλα και συνδετήριες δοκοί)", size=13, bold=True, w=230)
    # Tie beams first (under the footings' labels).
    for t in ties:
        (ax, ay), (bx, by) = t["a"], t["b"]
        L = math.hypot(bx - ax, by - ay) or 1.0
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy * TIE_B / 2, ux * TIE_B / 2
        quad = [(ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)]
        sh.poly([to_mm(*q) for q in quad], color=MEMBER_INK, width=.25, fill=QColor(235, 235, 235))
        # Label below / left of the tie: the footing labels sit above-right of each footing.
        sx, sy = -uy, ux
        if sy > 1e-9 or (abs(sy) <= 1e-9 and sx > 0):
            sx, sy = -sx, -sy
        mx, my = to_mm((ax + bx) / 2 + sx * (TIE_B / 2 + .2), (ay + by) / 2 + sy * (TIE_B / 2 + .2))
        ang = -math.degrees(math.atan2(uy, ux))
        if ang > 90.001 or ang < -89.999:
            ang += 180
        sh.text(mx, my, f"{t['name']} {t['section']} · {t['bars']} · Ø8/20".replace("Ø8/20", t["stirrups"]), size=5.8, bold=True,
                align="center", w=50, angle=ang)
    # Footings: B×B outline, mesh drawn as a few bars, the column on top.
    for f in fts:
        B = float(f["B_m"]) / 2
        corners = [(f["x"] - B, f["y"] - B), (f["x"] + B, f["y"] - B), (f["x"] + B, f["y"] + B), (f["x"] - B, f["y"] + B)]
        sh.poly([to_mm(*q) for q in corners], color=MEMBER_INK, width=.35, fill=QColor(255, 255, 255))
        for i in range(1, 4):                                  # a hint of the bottom mesh
            t_ = -B + 2 * B * i / 4
            sh.line(*to_mm(f["x"] - B + .05, f["y"] + t_), *to_mm(f["x"] + B - .05, f["y"] + t_), color=BAND_INK, width=.1)
            sh.line(*to_mm(f["x"] + t_, f["y"] - B + .05), *to_mm(f["x"] + t_, f["y"] + B - .05), color=BAND_INK, width=.1)
        c = float(f.get("column_m", 0.3)) / 2
        sh.poly([to_mm(f["x"] - c, f["y"] - c), to_mm(f["x"] + c, f["y"] - c), to_mm(f["x"] + c, f["y"] + c),
                 to_mm(f["x"] - c, f["y"] + c)], width=.2, fill=MEMBER_INK)
        tx, ty = to_mm(f["x"] + B, f["y"] + B)
        sh.text(tx + .8, ty - 2.2, f"{f['name']} ({f.get('column', '')})", size=6.5, bold=True, w=30)
        sh.text(tx + .8, ty + .4, f"{f['B_m']:.2f}×{f['B_m']:.2f} h{f['h_m']:.2f}", size=5.6, w=30, color=QColor(70, 70, 70))
        sh.text(tx + .8, ty + 2.8, f"σχάρα {f['mesh']}", size=5.6, w=30, color=BAND_INK)
    # Axis dimensions between footings.
    ax_ = _axes([f["x"] for f in fts]); ay_ = _axes([f["y"] for f in fts])
    for a_, b_ in zip(ax_, ax_[1:]):
        _dimension(sh, (a_, y1 + .1), (b_, y1 + .1), (0, 1), 6.0, b_ - a_, to_mm)
    for a_, b_ in zip(ay_, ay_[1:]):
        _dimension(sh, (x0 - .1, a_), (x0 - .1, b_), (-1, 0), 6.0, b_ - a_, to_mm)
    rows = [[f["name"], f"{f['B_m']:.2f}×{f['B_m']:.2f}×{f['h_m']:.2f}", f["mesh"] + " ×2", f"{f['concrete_m3']:.2f}"] for f in fts]
    rows += [[t["name"], t["section"], f"{t['bars']} + {t['stirrups']}", f"{t['concrete_m3']:.2f}"] for t in ties]
    cols = [("Στοιχείο", 14, "left"), ("Διαστάσεις", 24, "center"), ("Οπλισμός", 26, "left"), ("m³", 10, "right")]
    _table(sh, 202, 16, cols, rows[:MAX_ROWS], row_h=4.4, size=6.2)
    import textwrap
    notes = [f"Σκυρόδεμα θεμελίωσης: {fd['concrete_m3']} m³", "Πέδιλα: κάτω σχάρα και στις δύο διευθύνσεις, επικάλυψη 5 cm",
             "Συνδετήριες: άνω/κάτω οπλισμός συμμετρικός, συνδ. κλειστοί", PROVENANCE]
    if len(rows) > MAX_ROWS:
        notes.insert(0, f"+{len(rows) - MAX_ROWS} στοιχεία εκτός πίνακα")
    lines = [ln for t in notes for ln in textwrap.wrap(t, 58)]
    y = 176 - 3.4 * len(lines)
    for t in lines:
        sh.text(202, y, t, size=6, w=85, color=QColor(80, 80, 80)); y += 3.4
    _north(sh, 190, 30)
    _scale_bar(sh, 14, 190, scale)
    _title_block(sh, "Ξυλότυπος θεμελίωσης", scale, sheet_no, project, date)
    return scale


def draw_formwork(sh, doc, new_page, project, date, page_no):
    """All ξυλότυπος pages through ``new_page()`` (foundation first); returns the scales used."""
    scales, slab_no = [], 1
    fd = foundation_of(doc)
    if fd:
        new_page()
        scales.append(foundation_page(sh, doc, fd, page_no(), project, date))
    for frame in storey_frames(doc):
        new_page()
        scale, slab_no, rest = formwork_page(sh, doc, frame, page_no(), project, date, slab_no)
        scales.append(scale)
        cols = [("Μέλος", 30, "left"), ("Διατομή", 40, "center"), ("L/H m", 30, "right"), ("Υλικό", 40, "left")]
        while rest:
            new_page()
            sh.text(12, 12, f"Ξυλότυπος {level_name(frame['storey']['name'])} — πίνακας μελών (συνέχεια)", size=12, bold=True, w=220)
            _table(sh, 12, 22, cols, rest[:34], row_h=4.6, size=7)
            rest = rest[34:]
            _title_block(sh, "Πίνακας μελών", None, page_no(), project, date)
    return scales


def export_formwork_pdf(doc, path, project=None):
    """Only the ξυλότυπος sheets; returns ``{"pages", "path", "scales"}``."""
    from archforge.quantities.quote import quote
    project = project or quote(doc)["project"] or "Έργο"
    date = datetime.date.today().strftime("%d/%m/%Y")
    if not storey_frames(doc):
        raise ValueError("Δεν υπάρχουν κολόνες ή δοκοί — Δομικά → «Πρόταση φέροντος οργανισμού» πρώτα")
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
    writer.setTitle(f"{project} — Ξυλότυπος"); writer.setCreator("ArchForge")
    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    sh = Sheet(painter, 300 / 25.4)
    pages = 0

    def new_page():
        nonlocal pages
        if pages:
            writer.newPage()
        pages += 1
    scales = draw_formwork(sh, doc, new_page, project, date, lambda: pages)
    painter.end()
    return {"pages": pages, "path": str(path), "scales": scales}
