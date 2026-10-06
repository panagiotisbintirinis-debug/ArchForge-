"""PDF output: cover, a scaled plan per storey with dimensions, the take-off and the client quote.

Drawn with Qt (QPdfWriter + QPainter) as vectors on A4 landscape, so it
prints sharp at any size.  Plans:

* scale: the largest of 1:20 / 1:50 / 1:100 / 1:200 / 1:500 that fits the
  sheet (with room for the dimensions), stated in the title block and as a
  scale bar;
* walls filled (poché), cut by their doors (leaf + swing), windows (glass
  lines) and openings; columns black; stairs and fitted furniture as thin
  lines; every room with its name, area and inner size;
* dimensions: every exterior wall on its outer face (its length with the
  corners) and the overall width / depth of the storey.

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
    return [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < .05
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


def _extras(doc, z):
    """Stairs, ramps, fitted furniture and fixtures of the storey, as plan primitives (thin lines)."""
    from archforge.core.model import WorkPlane
    from archforge.core.plan_scene import build_plan_frame
    keep = {"stair", "ramp", "cabinet", "library_object", "component", "kitchen_run", "plumbing_point"}
    old = doc.work_plane
    try:
        doc.work_plane = WorkPlane(name=old.name, origin=(old.origin[0], old.origin[1], z), u=old.u, v=old.v)
        frame = build_plan_frame(doc)
    finally:
        doc.work_plane = old
    out = []
    for prim in frame.primitives:
        e = doc.entities.get(prim.entity_id) if prim.entity_id else None
        if e is not None and e.kind in keep and prim.kind in ("polygon", "polyline", "line") and len(prim.points) >= 2:
            out.append((prim.kind, [tuple(map(float, q)) for q in prim.points]))
    return out


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


def _plan_page(sh, doc, storey, sheet_no, project, date):
    from archforge.assistant.understanding import centroid
    from archforge.mep.ventilation import exterior_walls
    z = float(storey["z"])
    walls = _storey_walls(doc, z)
    pieces, holes = [], []
    for w in walls:
        pc, hl = wall_pieces(doc, w, walls)
        pieces += pc; holes += hl
    xs = [q[0] for poly in pieces for q in poly] or [0.0]
    ys = [q[1] for poly in pieces for q in poly] or [0.0]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    margin = 2.2                                          # m for the dimension chains
    box_w, box_h = 268.0, 150.0
    scale = next((s for s in SCALES if (x1 - x0 + 2 * margin) * 1000 / s <= box_w and (y1 - y0 + 2 * margin) * 1000 / s <= box_h), SCALES[-1])
    k = 1000.0 / scale
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = 12 + box_w / 2, 14 + box_h / 2

    def to_mm(x, y):
        return ox + (x - cx) * k, oy - (y - cy) * k
    sh.text(12, 8, f"Κάτοψη — {level_name(storey['name'])} (+{z:.2f})", size=13, bold=True, w=200)
    # Rooms: light fill and labels.
    for r in storey["rooms"]:
        sh.poly([to_mm(*q) for q in r["polygon"]], color=QColor(255, 255, 255, 0), width=.01, fill=QColor(247, 243, 236))
    for kind, pts in _extras(doc, z):
        mm = [to_mm(*q) for q in pts]
        if kind == "polygon":
            sh.poly(mm, color=QColor(90, 90, 90), width=.15)
        else:
            for a, b in zip(mm, mm[1:]):
                sh.line(*a, *b, color=QColor(90, 90, 90), width=.15)
    # Walls (poché).
    for poly in pieces:
        sh.poly([to_mm(*q) for q in poly], color=INK, width=.3, fill=POCHE)
    # Openings.
    outward = {w.id: n for w, n in exterior_walls(doc, z)}
    for u0, u1, e, f in holes:
        (axx, ayy), (ux, uy), (nx, ny), t = f["a"], f["u"], f["n"], f["t"]
        P = lambda u, s: to_mm(axx + ux * u + nx * s, ayy + uy * u + ny * s)
        if e.kind == "window":
            for s in (t / 2, -t / 2, 0.0):
                sh.line(*P(u0, s), *P(u1, s), width=.18 if s else .12)
            sh.line(*P(u0, t / 2), *P(u0, -t / 2), width=.25); sh.line(*P(u1, t / 2), *P(u1, -t / 2), width=.25)
        elif e.kind == "door":
            w = u1 - u0
            # Swing into the building: away from the outside of an exterior wall.
            out = outward.get(e.parent_id)
            sgn = -1.0 if out is None or (out[0] * nx + out[1] * ny) > 0 else 1.0
            P_ = P
            P = lambda u, s_, P_=P_: P_(u, sgn * -s_)
            hinge, leaf = P(u0, -t / 2), P(u0, -t / 2 - w)
            sh.line(*hinge, *leaf, width=.3)
            path = QPainterPath(); steps = 18
            for i in range(steps + 1):
                a = math.pi / 2 * i / steps
                q = P(u0 + w * math.sin(a), -t / 2 - w * math.cos(a))
                (path.moveTo if i == 0 else path.lineTo)(sh.pt(*q))
            sh.pen(INK, .13); sh.p.drawPath(path)
            sh.line(*P(u0, t / 2), *P(u0, -t / 2), width=.25); sh.line(*P(u1, t / 2), *P(u1, -t / 2), width=.25)
            P = P_
        else:
            for s in (t / 2, -t / 2):
                sh.line(*P(u0, s), *P(u1, s), width=.13, style=Qt.PenStyle.DashLine)
    # Columns.
    for cid in storey.get("columns", ()):
        c = doc.get(cid).params
        w2, d2 = float(c.get("width", .3)) / 2, float(c.get("depth", .3)) / 2
        x, y = float(c["x"]), float(c["y"])
        sh.poly([to_mm(x - w2, y - d2), to_mm(x + w2, y - d2), to_mm(x + w2, y + d2), to_mm(x - w2, y + d2)], width=.2, fill=INK)
    # Room labels.
    for r in storey["rooms"]:
        mx, my = to_mm(*centroid(r["polygon"]))
        a, rw, rd = net_room(doc, r, z)
        sh.text(mx, my - 2.6, r["name"], size=8.5, bold=True, align="center", w=50)
        sh.text(mx, my + 1.2, f"{a:.2f} m²", size=7.5, align="center", w=50)
        sh.text(mx, my + 4.6, f"{rw:.2f} × {rd:.2f}", size=6.5, align="center", w=50,
                color=QColor(110, 110, 110))
    # Dimensions: exterior walls on their outer face, then the overall size.
    for w, (nx, ny) in exterior_walls(doc, z):
        p = w.params
        ax, ay, bx, by = (float(p[k_]) for k_ in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < .3:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        t = float(p.get("thickness", .2))
        e0 = t / 2 if any(_on_segment_dist(ax, ay, *(float(o.params[k_]) for k_ in ("x1", "y1", "x2", "y2"))) < .01 for o in walls if o.id != w.id) else 0
        e1 = t / 2 if any(_on_segment_dist(bx, by, *(float(o.params[k_]) for k_ in ("x1", "y1", "x2", "y2"))) < .01 for o in walls if o.id != w.id) else 0
        face = lambda u: (ax + ux * u + nx * t / 2, ay + uy * u + ny * t / 2)
        # Chain: corner, every opening's jambs, corner — then the whole wall further out.
        stops = [-e0] + sorted(v for u0, u1, e, _f in holes if e.parent_id == w.id for v in (u0, u1)) + [L + e1]
        if len(stops) > 2:
            for a_, b_ in zip(stops, stops[1:]):
                if b_ - a_ > .05:
                    _dimension(sh, face(a_), face(b_), (nx, ny), 6.0, b_ - a_, to_mm)
            _dimension(sh, face(-e0), face(L + e1), (nx, ny), 12.0, L + e0 + e1, to_mm)
        else:
            _dimension(sh, face(-e0), face(L + e1), (nx, ny), 6.0, L + e0 + e1, to_mm)
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
    sh.text(20, 196, "Περιεχόμενα: κατόψεις ανά όροφο με διαστάσεις · επιμέτρηση ανά χώρο · προσφορά", size=8.5,
            color=QColor(110, 110, 110), w=260)


def export_pdf(doc, path, project=None, client=None, include=("cover", "plans", "takeoff", "quote")):
    """Write the PDF; returns ``{"pages": n, "path": path, "scales": [...]}``."""
    from archforge.assistant.understanding import read_drawing
    from archforge.quantities.quote import money, quote
    from archforge.quantities.takeoff import take_off
    q = quote(doc)
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
        for title, items in q["sections"]:
            rows.append({"cells": [title, "", "", "", ""]})
            for it in items:
                qty = "" if it["quantity"] is None else f"{float(it['quantity']):.2f}".rstrip("0").rstrip(".").replace(".", ",")
                rows.append([it["description"], it["unit"], qty, money(it["price"]) if it["price"] is not None else "—",
                             money(it["amount"]) if it["amount"] is not None else "—"])
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
                for label, v, bold in (("Μερικό σύνολο", q["subtotal"], False), (f"ΦΠΑ {q['vat']:g}%", q["vat_amount"], False),
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
