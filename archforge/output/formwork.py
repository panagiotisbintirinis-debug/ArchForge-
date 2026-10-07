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

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter

from archforge.output.pdf import (DIM, INK, SCALES, Sheet, _dimension, _north, _scale_bar, _table, _title_block,
                                  level_name, wall_pieces, _storey_walls)

MEMBER_INK = QColor(20, 20, 20)
SLAB_INK = QColor(30, 90, 160)
FAINT = QColor(200, 200, 200)
MAX_ROWS = 30


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


def slab_label_point(polygon, beams):
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
            placed.append((slab_label_point(r["polygon"], frame["beams"]), p))
    placed.sort(key=lambda item: (-round(item[0][1], 1), round(item[0][0], 1)))   # reading order, like Κ/Δ
    for point, p in placed:
        mx, my = to_mm(*point)
        sh.text(mx, my - 3.2, f"Π{n}", size=9, bold=True, align="center", color=SLAB_INK, w=30)
        sh.text(mx, my + 0.6, f"h={float(p['h']) * 100:.0f}", size=7, align="center", color=SLAB_INK, w=30)
        L = 9.0
        horizontal = p["short_dir"] == "x"
        if horizontal or "δύο" in p["kind"]:
            sh.line(mx - L, my + 7.0, mx + L, my + 7.0, color=SLAB_INK, width=.2)
            for s_ in (-1, 1):
                sh.line(mx + s_ * L, my + 7.0, mx + s_ * (L - 1.4), my + 6.3, color=SLAB_INK, width=.2)
                sh.line(mx + s_ * L, my + 7.0, mx + s_ * (L - 1.4), my + 7.7, color=SLAB_INK, width=.2)
        if not horizontal or "δύο" in p["kind"]:
            sh.line(mx, my + 7.0 - 3.6, mx, my + 7.0 + 3.6, color=SLAB_INK, width=.2)
            for s_ in (-1, 1):
                ye = my + 7.0 + s_ * 3.6
                sh.line(mx, ye, mx - .7, ye - s_ * 1.4, color=SLAB_INK, width=.2)
                sh.line(mx, ye, mx + .7, ye - s_ * 1.4, color=SLAB_INK, width=.2)
        n += 1
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
    y = 176 - 4.2 * len(notes)
    for t in notes:
        sh.text(202, y, t, size=6.5, w=85, color=QColor(80, 80, 80)); y += 4.2
    _north(sh, 190, 30)
    _scale_bar(sh, 14, 190, scale)
    _title_block(sh, f"Ξυλότυπος οροφής {level_genitive(storey['name'])}", scale, sheet_no, project, date)
    return scale, n, rest


def draw_formwork(sh, doc, new_page, project, date, page_no):
    """All ξυλότυπος pages through ``new_page()``; returns the scales used."""
    scales, slab_no = [], 1
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
