"""PDF output: cover, a scaled plan per storey with dimensions, the take-off and the client quote.

Drawn with Qt (QPdfWriter + QPainter) as vectors on A4 landscape, so it
prints sharp at any size.  Plans:

* the drawing itself is the plan view's: the storey's plan frame (core/plan_scene.build_plan_frame) painted
  with the same styles (core/plan_style.py) — walls, joinery, stairs, furniture, rooms, dimensions, MEP; what
  the plan view hides or switches off is not printed (owner 28/10: one drawing, the PDF only translates it);
  only the working aids of the screen (previews, guides, pick lines, cameras, the storey below) are left out;
* scale: the largest of 1:20 / 1:50 / 1:100 / 1:200 / 1:500 that fits the
  sheet, stated in the title block and as a scale bar; line widths are the
  plan's at 1:100 (0.035 m → 0.35 mm) whatever the scale.

Everything comes from the same Document the program draws from; nothing is
typed twice.
"""
from __future__ import annotations

import datetime
import math

from PySide6.QtCore import QMarginsF, QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QPageLayout, QPageSize, QPainter, QPainterPath, QPdfWriter, QPen,
                           QPolygonF)

SCALES = (20, 50, 100, 200, 500)
PAGE_W, PAGE_H = 297.0, 210.0          # A4 landscape (mm)
FONT = "Arial"
INK = QColor(25, 25, 25)
POCHE = QColor(70, 70, 70)
DIM = QColor(40, 70, 120)
ACCENT = QColor(176, 106, 48)


class Sheet:
    """Millimetre drawing helpers on a QPainter of a QPdfWriter page."""

    def __init__(self, painter, dpmm):
        self.p, self.k = painter, dpmm

    def pt(self, x, y):
        return QPointF(x * self.k, y * self.k)

    def pen(self, color=INK, width_mm=.25, style=Qt.PenStyle.SolidLine):
        pen = QPen(color); pen.setWidthF(max(.5, width_mm * self.k)); pen.setStyle(style)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap); pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        self.p.setPen(pen)

    def line(self, x1, y1, x2, y2, color=INK, width=.25, style=Qt.PenStyle.SolidLine):
        self.pen(color, width, style); self.p.drawLine(self.pt(x1, y1), self.pt(x2, y2))

    def rect(self, x, y, w, h, color=INK, width=.25, fill=None):
        self.pen(color, width); self.p.setBrush(QBrush(fill) if fill is not None else Qt.BrushStyle.NoBrush)
        self.p.drawRect(QRectF(x * self.k, y * self.k, w * self.k, h * self.k))
        self.p.setBrush(Qt.BrushStyle.NoBrush)

    def poly(self, pts, color=INK, width=.25, fill=None):
        self.pen(color, width); self.p.setBrush(QBrush(fill) if fill is not None else Qt.BrushStyle.NoBrush)
        self.p.drawPolygon(QPolygonF([self.pt(x, y) for x, y in pts]))
        self.p.setBrush(Qt.BrushStyle.NoBrush)

    def text(self, x, y, s, size=9, bold=False, align="left", color=INK, w=120, angle=0.0, italic=False):
        f = QFont(FONT); f.setPointSizeF(size); f.setBold(bold); f.setItalic(italic)
        self.p.setFont(f); self.p.setPen(color)
        flags = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
                 "right": Qt.AlignmentFlag.AlignRight}[align] | Qt.AlignmentFlag.AlignVCenter
        h = size * .55 * max(1, str(s).count("\n") + 1) + 2
        x0 = x - (w / 2 if align == "center" else (w if align == "right" else 0))
        self.p.save()
        self.p.translate(self.pt(x, y)); self.p.rotate(angle); self.p.translate(-self.pt(x, y))
        self.p.drawText(QRectF(x0 * self.k, (y - h / 2) * self.k, w * self.k, h * self.k), int(flags), str(s))
        self.p.restore()


# ---------------------------------------------------------------- plan geometry (metres)
def _storey_walls(doc, z):
    """The storey's walls as the plan view shows them: hidden ones are left off the PDF too."""
    return [e for e in doc.entities.values() if e.kind == "wall" and e.visible and abs(float(e.params.get("z", 0.0)) - z) < .05
            and str(e.params.get("phase", "new")) != "demolish"]


def _on_segment_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(ax + dx * t - px, ay + dy * t - py)


def wall_pieces(doc, wall, walls):
    """Solid parts of a wall (polygons, m) between its openings; ends extended into the walls they meet."""
    p = wall.params
    ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-6:
        return [], []
    ux, uy = (bx - ax) / L, (by - ay) / L
    nx, ny = -uy, ux
    t = float(p.get("thickness", .2))

    def joined(x, y):
        return any(o.id != wall.id and _on_segment_dist(x, y, *(float(o.params[k]) for k in ("x1", "y1", "x2", "y2"))) < .01
                   for o in walls)
    s0 = -t / 2 if joined(ax, ay) else 0.0
    s1 = L + t / 2 if joined(bx, by) else L
    holes = []
    for e in doc.entities.values():
        if e.kind in ("door", "window", "opening") and e.parent_id == wall.id:
            c, w = float(e.params.get("offset", 0.0)), float(e.params.get("width", 0.0))
            holes.append((max(0.0, c - w / 2), min(L, c + w / 2), e))
    holes.sort(key=lambda h: h[0])
    pieces, cur = [], s0
    for u0, u1, _e in holes:
        if u0 > cur + 1e-6:
            pieces.append((cur, u0))
        cur = max(cur, u1)
    if s1 > cur + 1e-6:
        pieces.append((cur, s1))

    def quad(a, b):
        return [(ax + ux * a + nx * t / 2, ay + uy * a + ny * t / 2), (ax + ux * b + nx * t / 2, ay + uy * b + ny * t / 2),
                (ax + ux * b - nx * t / 2, ay + uy * b - ny * t / 2), (ax + ux * a - nx * t / 2, ay + uy * a - ny * t / 2)]
    frame = {"a": (ax, ay), "u": (ux, uy), "n": (nx, ny), "t": t, "L": L}
    return [quad(a, b) for a, b in pieces], [(u0, u1, e, frame) for u0, u1, e in holes]


def net_room(doc, room, z):
    """(net area m², width, depth) of a room inside its walls (as the take-off measures it)."""
    from archforge.quantities.takeoff import _area, net_polygon
    net = net_polygon(doc, room["polygon"], z)
    xs = [q[0] for q in net]; ys = [q[1] for q in net]
    return abs(_area(net)), max(xs) - min(xs), max(ys) - min(ys)


# ---------------------------------------------------------------- pages
def _title_block(sh, title, scale, sheet_no, project, date):
    x, y, w, h = 197.0, 178.0, 90.0, 24.0
    sh.rect(x, y, w, h, width=.35)
    sh.line(x, y + 9, x + w, y + 9, width=.2)
    sh.line(x + 58, y + 9, x + 58, y + h, width=.2)
    sh.text(x + 3, y + 4.5, project or "Έργο", size=10, bold=True, w=w - 6)
    sh.text(x + 3, y + 13.5, title, size=9, bold=True, w=55)
    sh.text(x + 3, y + 19.5, f"Κλίμακα 1:{scale}" if scale else "", size=8, w=55)
    sh.text(x + 61, y + 13.5, date, size=8, w=28)
    sh.text(x + 61, y + 19.5, f"Φύλλο {sheet_no}", size=8, w=28)
    sh.text(x + w - 2, y - 2.5, "ArchForge — προμελέτη", size=6.5, align="right", color=QColor(120, 120, 120), w=80, italic=True)


def _scale_bar(sh, x, y, scale):
    step = {20: .5, 50: 1, 100: 1, 200: 2, 500: 5}[scale]
    for i in range(5):
        x0 = x + i * step * 1000 / scale
        sh.rect(x0, y, step * 1000 / scale, 1.6, width=.15, fill=INK if i % 2 == 0 else QColor(255, 255, 255))
    sh.text(x, y + 4, "0", size=6.5, align="center", w=10)
    sh.text(x + 5 * step * 1000 / scale, y + 4, f"{5 * step:g} m", size=6.5, align="center", w=16)


def _north(sh, x, y):
    sh.poly([(x, y - 6), (x + 2.6, y + 3), (x, y + 1.5), (x - 2.6, y + 3)], width=.2, fill=INK)
    sh.text(x, y - 8.5, "Β", size=8, bold=True, align="center", w=10)


def _dimension(sh, P1, P2, off_dir, off_mm, value, to_mm):
    """Dimension between world points P1, P2 drawn ``off_mm`` out along ``off_dir`` (world unit vector)."""
    (x1, y1), (x2, y2) = to_mm(*P1), to_mm(*P2)
    ox, oy = off_dir[0], -off_dir[1]                     # paper y points down
    d1 = (x1 + ox * off_mm, y1 + oy * off_mm); d2 = (x2 + ox * off_mm, y2 + oy * off_mm)
    sh.line(x1 + ox * 1.0, y1 + oy * 1.0, d1[0] + ox * 1.2, d1[1] + oy * 1.2, color=DIM, width=.13)
    sh.line(x2 + ox * 1.0, y2 + oy * 1.0, d2[0] + ox * 1.2, d2[1] + oy * 1.2, color=DIM, width=.13)
    sh.line(*d1, *d2, color=DIM, width=.18)
    L = math.hypot(d2[0] - d1[0], d2[1] - d1[1]) or 1.0
    ux, uy = (d2[0] - d1[0]) / L, (d2[1] - d1[1]) / L
    for (dx, dy) in (d1, d2):                             # architectural ticks
        sh.line(dx - (ux + uy) * 1.0, dy - (uy - ux) * 1.0, dx + (ux + uy) * 1.0, dy + (uy - ux) * 1.0, color=DIM, width=.3)
    ang = math.degrees(math.atan2(uy, ux))
    if ang > 90.001 or ang < -89.999:
        ang += 180
    mx, my = (d1[0] + d2[0]) / 2 + ox * 1.9, (d1[1] + d2[1]) / 2 + oy * 1.9
    sh.text(mx, my, f"{value:.2f}", size=7, align="center", color=DIM, w=30, angle=ang)


LEVEL_NAMES = {"Ground": "Ισόγειο", "XY": "Ισόγειο", "Basement": "Υπόγειο", "Roof": "Δώμα"}


def level_name(name):
    import re
    m = re.match(r"Floor (\d+)$", str(name))
    return f"{int(m.group(1)) - 1}ος όροφος" if m else LEVEL_NAMES.get(str(name), str(name))


def plan_frame(doc, z):
    """The plan view's drawing of storey ``z`` as printed: its frame with nothing selected, without the screen aids.

    ``[(primitive, entity kind)]`` in the plan view's stacking order."""
    from archforge.core.model import WorkPlane
    from archforge.core.plan_scene import build_plan_frame
    from archforge.core.plan_style import label_style, printable, style
    old, selection = doc.work_plane, doc.selection
    try:
        doc.work_plane = WorkPlane(name=old.name, origin=(old.origin[0], old.origin[1], float(z)), u=old.u, v=old.v)
        doc.selection = []
        frame = build_plan_frame(doc)
    finally:
        doc.work_plane, doc.selection = old, selection
    out = []
    for prim in frame.primitives:
        e = doc.entities.get(prim.entity_id) if prim.entity_id else None
        kind = e.kind if e is not None else None
        if printable(prim, kind):
            out.append((prim, kind))
    # Stable sort by the plan view's z: what lies on top on screen lies on top on paper.
    zs = [label_style(q).z if q.kind == "label" else style(q, k).z for q, k in out]
    return [item for _z, _i, item in sorted(zip(zs, range(len(out)), out), key=lambda t: (t[0], t[1]))]


LABEL_PT = 6.5          # pt of a plan label on paper (× its style's scale)


def _paint_label(sh, prim, at, s):
    from PySide6.QtGui import QFontMetricsF
    meta = dict(prim.meta)
    text = str(meta.get("text", ""))
    if not text:
        return
    f = QFont(FONT); f.setPointSizeF(LABEL_PT * s.text_scale); f.setBold(s.bold)
    sh.p.setFont(f)
    color = QColor(*s.text_color); color.setAlphaF(color.alphaF() * s.opacity); sh.p.setPen(color)
    lines = text.split("\n")
    fm = QFontMetricsF(f, sh.p.device())
    w = max(fm.horizontalAdvance(t) for t in lines); h = fm.height() * len(lines)
    x, y = sh.pt(*at).x(), sh.pt(*at).y()
    sh.p.save()
    sh.p.translate(x, y)
    if prim.role == "dimension-label":
        # Along its dimension line, just above it (as in the plan view).
        sh.p.rotate(-float(meta.get("angle", 0.0)))
        rect = QRectF(-w / 2, -h - fm.descent() * .3, w, h)
    else:
        hx, vy = meta.get("align") or (0.0, 0.0)
        rect = QRectF(-hx * w, -vy * h, w, h)
    sh.p.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), text)
    sh.p.restore()


def paint_plan(sh, items, to_mm):
    """Paint the plan frame ``items`` (``plan_frame``) on the sheet: each primitive with its plan-view style."""
    from archforge.core.plan_style import label_style, style
    from archforge.output.plan_qt import qbrush, qpen
    for prim, kind in items:
        if prim.kind == "label":
            _paint_label(sh, prim, to_mm(*prim.points[0]), label_style(prim))
            continue
        s = style(prim, kind)
        pen = qpen(s, max(.05, s.width * 10.0) * sh.k)       # the plan's metres at 1:100 → paper mm
        if s.opacity != 1.0:
            c = pen.color(); c.setAlphaF(c.alphaF() * s.opacity); pen.setColor(c)
        sh.p.setPen(pen)
        brush = qbrush(s)
        if s.opacity != 1.0 and s.fill is not None:
            c = QColor(*s.fill); c.setAlphaF(c.alphaF() * s.opacity); brush = QBrush(c)
        meta = dict(prim.meta)
        if prim.kind == "polygon" and meta.get("islands"):
            path = QPainterPath(); path.setFillRule(Qt.FillRule.OddEvenFill)
            for outer, holes in meta["islands"]:
                for loop in (outer,) + tuple(holes):
                    path.moveTo(sh.pt(*to_mm(*loop[0])))
                    for q in loop[1:]:
                        path.lineTo(sh.pt(*to_mm(*q)))
                    path.closeSubpath()
            sh.p.setBrush(brush); sh.p.drawPath(path)
        elif prim.kind == "polygon":
            sh.p.setBrush(brush); sh.p.drawPolygon(QPolygonF([sh.pt(*to_mm(*q)) for q in prim.points]))
        elif prim.kind in ("line", "polyline") and len(prim.points) >= 2:
            path = QPainterPath(sh.pt(*to_mm(*prim.points[0])))
            for q in prim.points[1:]:
                path.lineTo(sh.pt(*to_mm(*q)))
            sh.p.setBrush(Qt.BrushStyle.NoBrush); sh.p.drawPath(path)
        elif prim.kind == "ellipse":
            cx, cy = to_mm(*prim.points[0])
            k = abs(to_mm(1.0, 0.0)[0] - to_mm(0.0, 0.0)[0])
            sh.p.setBrush(brush)
            sh.p.drawEllipse(sh.pt(cx, cy), prim.radius_x * k * sh.k, prim.radius_y * k * sh.k)
        sh.p.setBrush(Qt.BrushStyle.NoBrush)


def _plan_page(sh, doc, storey, sheet_no, project, date):
    z = float(storey["z"])
    items = plan_frame(doc, z)
    pts = [q for prim, _k in items for q in prim.points] or [(0.0, 0.0)]
    xs = [float(q[0]) for q in pts]; ys = [float(q[1]) for q in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    margin = 0.6                                          # m around the drawing (its dimensions are in it)
    box_w, box_h = 268.0, 150.0
    scale = next((s for s in SCALES if (x1 - x0 + 2 * margin) * 1000 / s <= box_w and (y1 - y0 + 2 * margin) * 1000 / s <= box_h), SCALES[-1])
    k = 1000.0 / scale
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = 12 + box_w / 2, 14 + box_h / 2

    def to_mm(x, y):
        return ox + (x - cx) * k, oy - (y - cy) * k
    sh.text(12, 8, f"Κάτοψη — {level_name(storey['name'])} (+{z:.2f})", size=13, bold=True, w=200)
    paint_plan(sh, items, to_mm)
    _north(sh, 275, 30)
    _scale_bar(sh, 14, 190, scale)
    _title_block(sh, f"Κάτοψη {level_name(storey['name'])}", scale, sheet_no, project, date)
    return scale


def _table(sh, x, y, cols, rows, row_h=6.2, header=True, size=8):
    """cols: [(title, width_mm, align)] → draws rows from y; returns the y after the last row."""
    if header:
        sh.rect(x, y, sum(c[1] for c in cols), row_h, width=.2, fill=QColor(236, 231, 222))
        cx = x
        for title, w, align in cols:
            sh.text(cx + (2 if align == "left" else (w / 2 if align == "center" else w - 2)), y + row_h / 2, title,
                    size=size, bold=True, align=align, w=w - 3)
            cx += w
        y += row_h
    for row in rows:
        bold = isinstance(row, dict)
        cells = row["cells"] if bold else row
        cx = x
        for (title, w, align), v in zip(cols, cells):
            sh.text(cx + (2 if align == "left" else (w / 2 if align == "center" else w - 2)), y + row_h / 2, v,
                    size=size, bold=bold and row.get("bold", True), align=align, w=w - 3)
            cx += w
        sh.line(x, y + row_h, x + sum(c[1] for c in cols), y + row_h, color=QColor(210, 205, 196), width=.12)
        y += row_h
    return y


def _cover(sh, doc, project, client, date, storeys):
    from archforge.project.brief import INTERIOR_WALLS, PROJECT_TYPES, WALL_SYSTEMS, get_brief
    sh.rect(0, 0, PAGE_W, 46, width=.01, fill=QColor(34, 30, 27))
    sh.text(20, 20, "ArchForge", size=26, bold=True, color=QColor(246, 238, 227), w=150)
    sh.text(20, 33, "From dream to dream home", size=11, color=QColor(233, 180, 108), w=150, italic=True)
    sh.text(20, 66, project or "Έργο", size=22, bold=True, w=250)
    if client:
        sh.text(20, 78, f"Πελάτης: {client}", size=12, w=250)
    sh.text(20, 88, f"Ημερομηνία: {date}", size=10, w=250, color=QColor(90, 90, 90))
    brief = get_brief(doc)
    y = 104
    if brief:
        lines = [f"Έργο: {PROJECT_TYPES[brief['project_type']]}",
                 f"Τοίχοι: {brief.get('wall_system_text') or WALL_SYSTEMS[brief['wall_system']][0]}",
                 f"Εσωτερικοί τοίχοι: {brief.get('interior_walls_text') or INTERIOR_WALLS[brief['interior_walls']][0]}"]
        for s in lines:
            sh.text(20, y, s, size=10, w=250); y += 6.5
    y += 4
    total = 0.0
    for s in storeys:
        area = sum(net_room(doc, r, float(s["z"]))[0] for r in s["rooms"])
        total += area
        sh.text(20, y, f"{level_name(s['name'])} (+{float(s['z']):.2f}) — {len(s['rooms'])} χώροι, {area:.2f} m² καθαρά", size=10, w=250); y += 6.5
    if storeys:
        sh.text(20, y + 2, f"Σύνολο: {total:.2f} m²", size=10, bold=True, w=250)
    sh.text(20, 196, "Περιεχόμενα: κατόψεις ανά όροφο με διαστάσεις · ξυλότυποι · επιμέτρηση ανά χώρο · προσφορά", size=8.5,
            color=QColor(110, 110, 110), w=260)


def export_pdf(doc, path, project=None, client=None, include=("cover", "plans", "formwork", "takeoff", "quote"), only=None):
    """Write the PDF; returns ``{"pages": n, "path": path, "scales": [...]}``."""
    from archforge.assistant.understanding import read_drawing
    from archforge.quantities.quote import money, quote
    from archforge.quantities.takeoff import take_off
    q = quote(doc, only)
    project = project or q["project"] or "Έργο"
    client = client if client is not None else q["client"]
    date = datetime.date.today().strftime("%d/%m/%Y")
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
    writer.setTitle(f"{project} — ArchForge"); writer.setCreator("ArchForge")
    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    sh = Sheet(painter, 300 / 25.4)
    pages, scales = 0, []

    def new_page():
        nonlocal pages
        if pages:
            writer.newPage()
        pages += 1
    storeys = [s for s in read_drawing(doc)["storeys"] if s["walls"]]
    if "cover" in include:
        new_page(); _cover(sh, doc, project, client, date, storeys)
    if "plans" in include:
        for s in storeys:
            new_page(); scales.append(_plan_page(sh, doc, s, pages, project, date))
    if "formwork" in include:
        from archforge.output.formwork import draw_formwork
        scales += draw_formwork(sh, doc, new_page, project, date, lambda: pages)
    if "takeoff" in include:
        t = take_off(doc)
        cols = [("Όροφος", 26, "left"), ("Χώρος", 40, "left"), ("Δάπεδο m²", 24, "right"), ("Τοίχοι m²", 24, "right"),
                ("Βαφή τοίχων", 25, "right"), ("Βαφή οροφής", 25, "right"), ("Πλακ. δαπέδου", 26, "right"),
                ("Πλακ. τοίχου", 25, "right"), ("Ξύλινο δάπ.", 23, "right"), ("Σοβατεπί m", 22, "right")]
        keys = ("floor_m2", "walls_m2", "paint_walls_m2", "paint_ceiling_m2", "floor_tiles_m2", "wall_tiles_m2", "wood_floor_m2", "skirting_m")
        rows = [[level_name(r["storey"]), r["name"]] + [f"{r[k_]:.2f}" for k_ in keys] for r in t["rooms"]]
        rows.append({"cells": ["Σύνολο", ""] + [f"{t['totals'][k_]:.2f}" for k_ in keys]})
        per = 24
        for i in range(0, max(1, len(rows)), per):
            new_page()
            sh.text(12, 12, "Επιμέτρηση εργασιών ανά χώρο", size=13, bold=True, w=200)
            sh.text(12, 19, "Καθαρές επιφάνειες (εσωτερικό περίγραμμα, πλην ανοιγμάτων)", size=8, color=QColor(110, 110, 110), w=200)
            _table(sh, 12, 26, cols, rows[i:i + per])
            _title_block(sh, "Επιμέτρηση", None, pages, project, date)
    if "quote" in include:
        cols = [("Είδος / εργασία", 150, "left"), ("Μον.", 16, "center"), ("Ποσότητα", 26, "right"),
                ("Τιμή μονάδας", 32, "right"), ("Σύνολο", 34, "right")]
        rows = []
        for (title, items), trade in zip(q["sections"], q["by_trade"]):
            rows.append({"cells": [title, "", "", "", ""]})
            for it in items:
                qty = "" if it["quantity"] is None else f"{float(it['quantity']):.2f}".rstrip("0").rstrip(".").replace(".", ",")
                rows.append([it["description"], it["unit"], qty, money(it["price"]) if it["price"] is not None else "—",
                             money(it["amount"]) if it["amount"] is not None else "—"])
            # Each trade's own total: materials + labour, and how many of its items still have no price.
            rows.append({"cells": [f"Σύνολο «{title.split(' — ')[0]}»: υλικά {money(trade['material'])} · εργασία {money(trade['labour'])}"
                                   + (f" · {trade['missing']} χωρίς τιμή" if trade["missing"] else ""), "", "", "", money(trade["subtotal"])]})
        per, first = 22, True
        chunks = [rows[i:i + per] for i in range(0, len(rows), per)] or [[]]
        for n, chunk in enumerate(chunks):
            new_page()
            sh.text(12, 12, "Προσφορά", size=16, bold=True, w=120)
            sh.text(285, 10, project, size=10, bold=True, align="right", w=160)
            if q["client"]:
                sh.text(285, 16, f"Προς: {q['client']}", size=9, align="right", w=160)
            sh.text(285, 21.5, date, size=8.5, align="right", w=160, color=QColor(100, 100, 100))
            y = _table(sh, 12, 28, cols, chunk)
            if n == len(chunks) - 1:
                y += 4
                for label, v, bold in (("Υλικά", q.get("material"), False), ("Εργασία", q.get("labour"), False),
                                       ("Μερικό σύνολο", q["subtotal"], False), (f"ΦΠΑ {q['vat']:g}%", q["vat_amount"], False),
                                       ("Σύνολο", q["total"], True)):
                    sh.text(220, y + 3, label, size=10 if bold else 9, bold=bold, align="right", w=60)
                    sh.text(270, y + 3, money(v), size=10 if bold else 9, bold=bold, align="right", w=40)
                    y += 6.5
                notes = [f"Ισχύς προσφοράς: {q['validity_days']} ημέρες."]
                if q["missing"]:
                    notes.append("1 είδος χωρίς τιμή δεν περιλαμβάνεται στο σύνολο." if q["missing"] == 1 else
                                 f"{q['missing']} είδη χωρίς τιμή δεν περιλαμβάνονται στο σύνολο.")
                if q["notes"]:
                    notes.append(q["notes"])
                for s in notes:
                    sh.text(12, y + 3, s, size=8.5, w=200, color=QColor(80, 80, 80)); y += 5.5
                sh.line(200, 192, 280, 192, width=.2)
                sh.text(240, 196, "Υπογραφή / σφραγίδα", size=8, align="center", w=80, color=QColor(110, 110, 110))
    painter.end()
    return {"pages": pages, "path": str(path), "scales": scales}
