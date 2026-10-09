"""Section drawing (τομή) on screen and the mouse workflow around it.

* Προβολή ▾ → «Τομή» (or the Προβολή menu): drag the cut line across the plan; a red dash-dot
  ghost shows the line, the arrows (where the section looks) and its length.  Esc cancels.
* Releasing adds one ``section_line`` (one undo) and opens the «Τομή Α-Α» tab: cut walls/slabs
  hatched with a heavy outline, the building behind in elevation, the storey levels.
* Clicking the line in the plan selects it (Delete removes it); the Properties offer «Άνοιγμα
  τομής», «Αντιστροφή» (look the other way) and «Στο 3D» (clipping plane on the line).

The drawing itself is ``output/section_cut.py`` (plain data); this module only paints it.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout,
                               QLabel, QPushButton, QVBoxLayout, QWidget)

from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity

INK = QColor(25, 28, 34)
CUT_FILL = {"concrete": (QColor(120, 124, 130), Qt.BrushStyle.SolidPattern),
            "masonry": (QColor(40, 40, 40), Qt.BrushStyle.BDiagPattern),
            "roof": (QColor(140, 70, 35), Qt.BrushStyle.FDiagPattern),
            "joinery": (QColor(255, 255, 255), Qt.BrushStyle.SolidPattern),
            "other": (QColor(90, 90, 90), Qt.BrushStyle.Dense6Pattern)}


class _Drawing(QGraphicsItem):
    """The whole section in one item, painted in order: elevation behind (far → near), then the cut."""

    def __init__(self, data):
        super().__init__()
        self.data = data
        u0, z0, u1, z1 = data["bounds"]
        self._rect = QRectF(u0 - 1.0, z0 - 1.0, (u1 - u0) + 2.0, (z1 - z0) + 2.0)

    def boundingRect(self):
        return self._rect

    def paint(self, painter, _option, _widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        edge = QPen(QColor(70, 74, 82)); edge.setCosmetic(True); edge.setWidthF(0.8)
        for f in self.data["faces"]:
            color = QColor(*f["fill"])
            seam = QPen(color); seam.setCosmetic(True); seam.setWidthF(1.0)
            painter.setPen(seam); painter.setBrush(color)
            painter.drawPolygon(QPolygonF([QPointF(u, z) for u, z in f["points"]]))
            if f["edges"]:
                painter.setPen(edge)
                for (a, b) in f["edges"]:
                    painter.drawLine(QPointF(*a), QPointF(*b))
        heavy = QPen(INK); heavy.setCosmetic(True); heavy.setWidthF(2.4)
        for cut in self.data["cuts"]:
            path = QPainterPath(); path.setFillRule(Qt.FillRule.OddEvenFill)
            for loop in cut["loops"]:
                path.moveTo(QPointF(*loop[0]))
                for q in loop[1:]:
                    path.lineTo(QPointF(*q))
                path.closeSubpath()
            color, pattern = CUT_FILL.get(cut["style"], CUT_FILL["other"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255)); painter.drawPath(path)          # paper under the hatch
            hatch = QBrush(color, pattern)
            hatch.setTransform(painter.worldTransform().inverted()[0])                # hatch keeps its screen size
            painter.setBrush(hatch); painter.drawPath(path)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(heavy if cut["style"] != "joinery" else edge); painter.drawPath(path)
            for chain in cut["chains"]:
                painter.drawPolyline(QPolygonF([QPointF(*q) for q in chain]))


class SectionView(QGraphicsView):
    """2D section on a ``section_line`` entity, refreshed from the Document whenever shown."""

    def __init__(self, window, parent=None):
        self._scene = QGraphicsScene()
        super().__init__(self._scene, parent)
        self.window = window
        self.entity_id = None
        self.data = None
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setBackgroundBrush(QColor(255, 255, 255))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(60.0, -60.0)

    def wheelEvent(self, event):
        f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(f, f)

    def show_section(self, eid, fit=True):
        from archforge.output.section_cut import cut_section
        doc = self.window.doc
        self.entity_id = eid
        if eid not in doc.entities:
            self._scene.clear(); self.data = None
            return None
        cache = getattr(getattr(self.window, "pbr_view", None), "_evaluation_cache", None)
        evaluation = cache.sync(doc) if cache is not None else None
        self.data = cut_section(doc, doc.get(eid).params, evaluation)
        self._scene.clear()
        self._scene.addItem(_Drawing(self.data))
        self._draw_levels()
        if fit:
            u0, z0, u1, z1 = self.data["bounds"]
            self.fitInView(QRectF(u0 - 4.5, z0 - 1.0, (u1 - u0) + 9.5, (z1 - z0) + 2.0), Qt.AspectRatioMode.KeepAspectRatio)
        return self.data

    def _text(self, text, u, z, color=INK, bold=False, align=(0.0, 0.5)):
        t = self._scene.addText(text)
        t.setDefaultTextColor(color)
        if bold:
            f = t.font(); f.setBold(True); t.setFont(f)
        t.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        r = t.boundingRect()
        t.setPos(u, z)
        from PySide6.QtGui import QTransform
        t.setTransform(QTransform.fromTranslate(-align[0] * r.width(), -align[1] * r.height()))
        return t

    def _draw_levels(self):
        """Level marks at the left: ▽ ±0,00 / +3,00 with the storey name, a thin line across."""
        u0, z0, u1, z1 = self.data["bounds"]
        pen = QPen(QColor(30, 90, 170)); pen.setCosmetic(True); pen.setWidthF(1.0); pen.setStyle(Qt.PenStyle.DashLine)
        x = u0 - 0.8
        for z, mark, name in self.data["levels"]:
            if z > z1 + 0.5:
                continue
            self._scene.addLine(x, z, u1 + 0.4, z, pen).setZValue(5)
            tri = QPolygonF([QPointF(x, z), QPointF(x - 0.14, z + 0.2), QPointF(x + 0.14, z + 0.2)])
            outline = QPen(QColor(30, 90, 170)); outline.setCosmetic(True); outline.setWidthF(1.2)
            self._scene.addPolygon(tri, outline, QBrush(QColor(255, 255, 255))).setZValue(6)
            self._text(f"{mark}  {name}", x - 0.2, z + 0.25, QColor(30, 90, 170), True, (1.0, 1.0))
        top = max((max(q[1] for q in loop) for c in self.data["cuts"] for loop in c["loops"]), default=None)
        if top is not None and all(abs(top - z) > 0.3 for z, _m, _n in self.data["levels"]):
            self._text(f"{top:+.2f}".replace(".", ",") + "  ανώτατο σημείο", u1 + 0.4, top, QColor(30, 90, 170), False, (0.0, 0.5))


class SectionPanel(QWidget):
    """Central tab: title, the drawing and its few buttons."""

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 4, 6, 4)
        bar = QHBoxLayout()
        self.title = QLabel("Τομή")
        f = self.title.font(); f.setBold(True); f.setPointSizeF(f.pointSizeF() * 1.15); self.title.setFont(f)
        bar.addWidget(self.title, 1)
        for text, tip, run in (("Αντιστροφή", "Κοίτα από την άλλη πλευρά της γραμμής", lambda: flip_section(window, self.view.entity_id)),
                               ("Στο 3D", "Η ίδια τομή στο 3D, με επίπεδο αποκοπής στη γραμμή", lambda: section_in_3d(window, self.view.entity_id)),
                               ("Όλη η τομή", "Προσαρμογή στην οθόνη", lambda: self.refresh(fit=True))):
            b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(lambda _=False, r=run: r()); bar.addWidget(b)
        lay.addLayout(bar)
        self.view = SectionView(window, self)
        lay.addWidget(self.view, 1)
        self.hint = QLabel("Κομμένα: σκυρόδεμα γκρι, τοιχοποιία με διαγράμμιση, στέγη καφέ · πίσω από την τομή: όψη · "
                           "ρόδα = ζουμ, σύρσιμο = μετακίνηση")
        self.hint.setStyleSheet("color:#5B6778;")
        lay.addWidget(self.hint)

    def refresh(self, fit=False):
        eid = self.view.entity_id
        doc = self.window.doc
        if eid not in doc.entities:
            self.title.setText("Τομή — η γραμμή τομής διαγράφηκε")
            self.view.show_section(eid)
            return
        self.title.setText(f"{doc.get(eid).name} — όψη προς τα βέλη της γραμμής")
        self.view.show_section(eid, fit=fit)


# --- workflow (main window) -----------------------------------------------------------------------

def create_section(window, x1, y1, x2, y2):
    """Mouse released after the drag: one section line (one undo), then its drawing."""
    import math
    from archforge.output.section_cut import next_section_name
    if math.hypot(x2 - x1, y2 - y1) < 0.3:
        window.statusBar().showMessage("Τομή: σύρε μια γραμμή κατά μήκος του κτιρίου (τουλάχιστον 30 cm)", 6000)
        return None
    entity = Entity("section_line", {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2), "flip": 0},
                    name=next_section_name(window.doc))
    window.stack.execute(AddEntity(entity))
    window.doc.select([entity.id])
    window.plan_view.controller.set_tool("select")
    window.refresh_inspector()
    window._redraw_views(all_views=True) if hasattr(window, "_redraw_views") else window.redraw()
    open_section(window, entity.id)
    window.statusBar().showMessage(f"{entity.name}: κοιτάς προς τα βέλη · «Αντιστροφή» για την άλλη πλευρά · "
                                   "«Στο 3D» για το επίπεδο αποκοπής · Ctrl+Z αναιρεί", 10000)
    return entity


def open_section(window, eid):
    """Show (or bring forward) the section tab for ``eid``."""
    tabs = getattr(window, "_central_tabs", None)
    panel = getattr(window, "_section_panel", None)
    if panel is None:
        panel = window._section_panel = SectionPanel(window)
        if tabs is not None:
            tabs.addTab(panel, "Τομή")
            tabs.currentChanged.connect(lambda _i, p=panel: tabs.currentWidget() is p and p.refresh())
    panel.view.entity_id = eid
    if tabs is not None:
        if tabs.indexOf(panel) < 0:
            tabs.addTab(panel, "Τομή")
        tabs.setTabText(tabs.indexOf(panel), window.doc.get(eid).name)
        if tabs.currentWidget() is panel:
            panel.refresh(fit=True)
        else:
            tabs.setCurrentWidget(panel)
            panel.refresh(fit=True)
    else:
        panel.refresh(fit=True)
    return panel


def flip_section(window, eid):
    if eid not in window.doc.entities:
        return
    window.stack.execute(UpdateEntity(eid, {"flip": 0 if int(window.doc.get(eid).params.get("flip", 0)) else 1}))
    window._redraw_views(all_views=True) if hasattr(window, "_redraw_views") else window.redraw()
    panel = getattr(window, "_section_panel", None)
    if panel is not None and panel.view.entity_id == eid:
        panel.refresh(fit=True)


def section_in_3d(window, eid):
    """The same cut in 3D: clipping plane on the line, camera square to it, looking where the arrows point."""
    from archforge.output.section_cut import frame
    if eid not in window.doc.entities:
        return
    (ox, oy), (ux, uy), (nx, ny), length = frame(window.doc.get(eid).params)
    mx, my = ox + ux * length / 2, oy + uy * length / 2
    window._show_3d_view()
    window.pbr_view.set_view_line("section", mx, my, mx + nx, my + ny, z=float(window.doc.work_plane.origin[2]))
    window.statusBar().showMessage(f"{window.doc.get(eid).name} στο 3D — ρόδα = μετακίνηση της τομής μπρος/πίσω", 8000)


def add_rows(window, eid):
    """Properties of a section line: length, buttons."""
    import math
    p = window.doc.get(eid).params
    window.form.addRow("Μήκος γραμμής", QLabel(f"{math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1']):.2f} m".replace(".", ",")))
    for text, run in (("Άνοιγμα τομής", lambda: open_section(window, eid)),
                      ("Αντιστροφή κατεύθυνσης", lambda: flip_section(window, eid)),
                      ("Τομή στο 3D", lambda: section_in_3d(window, eid))):
        b = QPushButton(text); b.clicked.connect(lambda _=False, r=run: r()); window.form.addRow(b)
