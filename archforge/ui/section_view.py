"""Section drawing (τομή) on screen and the mouse workflow around it.

* Προβολή ▾ → «Τομή» (or the Προβολή menu): drag the cut line across the plan; a red dash-dot
  ghost shows the line, the arrows (where the section looks) and its length.  Esc cancels.
* Releasing adds one ``section_line`` (one undo) and opens the «Τομή Α-Α» tab: cut walls/slabs
  hatched with a heavy outline, the building behind in elevation, the storey levels.
* Clicking the line in the plan selects it (Delete removes it); the Properties offer «Άνοιγμα
  τομής», «Αντιστροφή» (look the other way) and «Στο 3D» (clipping plane on the line).
* «Υπόβαθρο τομής…»: the engineer's section (PDF / DXF) under this section, placed with two
  clicks (its ±0,00 on ours), calibrated on a known height; the level under the mouse is shown
  in the status bar to read storey heights, slabs, ground and pool off it.

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
            "soil": (QColor(145, 100, 55), Qt.BrushStyle.BDiagPattern),
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
        from archforge.ui.view_zoom import zoom_about
        zoom_about(self, event)

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
        backdrop = self._draw_underlays()
        self._scene.addItem(_Drawing(self.data))
        self._draw_levels()
        self._draw_terrain_marks()
        self._draw_pools()
        if fit:
            u0, z0, u1, z1 = self.data["bounds"]
            rect = QRectF(u0 - 4.5, z0 - 1.0, (u1 - u0) + 9.5, (z1 - z0) + 2.0)
            for item in backdrop:
                rect = rect.united(item.sceneBoundingRect())
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
        return self.data

    def _draw_underlays(self):
        """The engineer's section under ours (faint, behind, never selectable)."""
        from archforge.project.underlay import section_underlays
        from archforge.ui.plan_view import add_underlay_item
        return [add_underlay_item(self._scene, e.params)
                for e in section_underlays(self.window.doc, self.entity_id) if e.visible]

    # --- clicks for placing / calibrating the section underlay (ui/underlay_tools.py) -----------------

    def _picking(self):
        state = getattr(self.window, "_underlay_calibration", None)
        if not state or state["id"] not in self.window.doc.entities:
            return None
        return state if self.window.doc.get(state["id"]).params.get("section_id") == self.entity_id else None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._picking():
            from archforge.ui.underlay_tools import calibration_click
            q = self.mapToScene(event.position().toPoint())
            calibration_click(self.window, q.x(), q.y())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self.data is None or event.buttons() != Qt.MouseButton.NoButton:
            return
        q = self.mapToScene(event.position().toPoint())
        self.setCursor(Qt.CursorShape.CrossCursor if self._picking() else Qt.CursorShape.OpenHandCursor)
        if not self._picking():
            self.window.statusBar().showMessage(level_readout(q.x(), q.y()), 4000)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self._picking():
            self.window._underlay_calibration = None
            self.window.statusBar().showMessage("Ακυρώθηκε", 3000)
            return
        super().keyPressEvent(event)

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
        top = max((max(q[1] for q in loop) for c in self.data["cuts"] if c['kind'] != 'terrain' for loop in c["loops"]), default=None)
        if top is not None and all(abs(top - z) > 0.3 for z, _m, _n in self.data["levels"]):
            self._text(f"{top:+.2f}".replace(".", ",") + "  ανώτατο σημείο", u1 + 0.4, top, QColor(30, 90, 170), False, (0.0, 0.5))

    def _draw_pools(self):
        """A pool the line crosses: its concrete cut (walls, sloping floor), the water, and its levels — rim, water,
        bottom at each end — relative to ±0,00 and absolute (section_cut.pool_cuts)."""
        blue = QColor(30, 110, 200)
        concrete = QPen(QColor(40, 40, 40)); concrete.setCosmetic(True); concrete.setWidthF(1.6)
        for c in self.data.get("pools", ()):
            u0, u1, rim, water, t, f = c["u0"], c["u1"], c["rim"], c["water"], c["wall"], c["floor"]
            bottom = c["bottom"]
            shell = ([QPointF(u0 - t, rim), QPointF(u0, rim)] + [QPointF(u, z) for u, z in bottom] +
                     [QPointF(u1, rim), QPointF(u1 + t, rim), QPointF(u1 + t, bottom[-1][1] - f)] +
                     [QPointF(u, z - f) for u, z in reversed(bottom)] + [QPointF(u0 - t, bottom[0][1] - f)])
            # The ground goes on under the basin (the 3D cuts the terrain through for the hole; a section must not).
            low = min(self.data["bounds"][1], min(z for _u, z in bottom) - f - 0.5)
            soil = [QPointF(u0 - t, bottom[0][1] - f)] + [QPointF(u, z - f) for u, z in bottom] + \
                   [QPointF(u1 + t, bottom[-1][1] - f), QPointF(u1 + t, low), QPointF(u0 - t, low)]
            hatch = QBrush(QColor(125, 75, 25), Qt.BrushStyle.BDiagPattern)
            self._scene.addPolygon(QPolygonF(soil), QPen(Qt.PenStyle.NoPen), hatch).setZValue(7)
            self._scene.addPolygon(QPolygonF(shell), concrete, QBrush(QColor(190, 190, 190))).setZValue(8)
            wet = [QPointF(u0, water), QPointF(u1, water)] + [QPointF(u, z) for u, z in reversed(bottom)]
            self._scene.addPolygon(QPolygonF(wet), QPen(Qt.PenStyle.NoPen), QBrush(QColor(110, 180, 230, 170))).setZValue(9)
            ref = c.get("altitude_ref", 0.0)

            def both(z):
                rel = "±0,00" if abs(z) < 5e-3 else f"{z:+.2f}".replace(".", ",")
                return rel + (f" (+{z + ref:.2f})".replace(".", ",") if ref else "")
            self._text(f"χείλος {both(rim)}", u1 + t + 0.15, rim + 0.15, blue, True, (0.0, 1.0))
            self._text(f"νερό {both(water)}", u1 + t + 0.15, water - 0.05, blue, False, (0.0, 0.0))
            self._text(f"πυθμένας {both(bottom[0][1])}", u0 + 0.15, bottom[0][1] + 0.1, blue, False, (0.0, 1.0))
            if abs(bottom[-1][1] - bottom[0][1]) > 0.01:
                self._text(f"πυθμένας {both(bottom[-1][1])}", u1 - 0.15, bottom[-1][1] + 0.1, blue, False, (1.0, 1.0))
            self._text(c["name"], (u0 + u1) / 2, water + 0.6, blue, True, (0.5, 1.0))

    def _draw_terrain_marks(self):
        from archforge.ui.terrain_tools import mark
        color = QColor(125, 75, 25)
        pen = QPen(color); pen.setCosmetic(True); pen.setWidthF(1.4)
        for u, z in self.data.get('terrain_marks', ()):
            tri = QPolygonF([QPointF(u,z), QPointF(u-.12,z+.18), QPointF(u+.12,z+.18)])
            self._scene.addPolygon(tri, pen, QBrush(QColor('white'))).setZValue(7)
            self._text(mark(z), u+.15, z+.3, color, True, (0.,1.))


def level_readout(u, z):
    """Status-bar text for the point under the mouse in a section: «Υψόμετρο +3,20 · 4,15 m κατά μήκος της τομής»."""
    mark = "±0,00" if abs(z) < 5e-3 else f"{z:+.2f}".replace(".", ",")
    return f"Υψόμετρο {mark} · " + f"{u:.2f}".replace(".", ",") + " m κατά μήκος της τομής"


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
                               ("Υπόβαθρο τομής…", "Η τομή του μηχανικού (PDF / DXF) κάτω από αυτή — "
                                "τοποθέτηση με 2 κλικ, μετά διαβάζεις υψόμετρα με το ποντίκι", lambda: import_section_underlay(window, self.view.entity_id)),
                               ("Αυτόματη θέση", "Το υπόβαθρο τομής στη θέση και τη φορά του, από την πισίνα / τους τοίχους "
                                "του μοντέλου πάνω στη γραμμή (το ίδιο με το Σύνολο σχεδίων)", lambda: auto_place_section(window, self.view.entity_id)),
                               ("Όλη η τομή", "Προσαρμογή στην οθόνη", lambda: self.refresh(fit=True))):
            b = QPushButton(text); b.setToolTip(tip); b.clicked.connect(lambda _=False, r=run: r()); bar.addWidget(b)
        lay.addLayout(bar)
        self.view = SectionView(window, self)
        lay.addWidget(self.view, 1)
        self.hint = QLabel("Κομμένα: σκυρόδεμα γκρι, τοιχοποιία με διαγράμμιση, έδαφος καφέ με υψόμετρα · πίσω από την τομή: όψη · "
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


def section_sheet(params):
    """The section underlay as a drawing-set sheet (lines and water in metres, the underlay's own frame)."""
    from archforge.project import drawing_set as D
    k = float(params["m_per_unit"])
    if params.get("source") == "pdf":
        return D.read_sheet(params["path"], int(params.get("page", 0)), scale=k / D.PT_M)
    u0, v0 = float(params.get("u0", 0.0)), float(params.get("v0", 0.0))
    segs = [((a - u0) * k, (b - v0) * k, (c - u0) * k, (d - v0) * k) for a, b, c, d in params.get("segments", ())]
    return D.Sheet(str(params.get("path", "")), kind="section", scale=k / D.PT_M, segments=segs)


def auto_place_section(window, eid):
    """«Αυτόματη θέση»: the engineer's section under section ``eid`` placed and turned by the model on its line
    (project/section_fit.py — the pool's water, else the walls); the drawing is checked against the model.
    One undo.  Returns the fit or None."""
    from archforge.core.commands import CompositeCommand
    from archforge.project import section_fit as F
    from archforge.project.underlay import section_underlays
    doc = window.doc
    if eid not in doc.entities:
        return None
    under = [u for u in section_underlays(doc, eid) if u.visible]
    if not under:
        window.statusBar().showMessage("Αυτόματη θέση: βάλε πρώτα την τομή του μηχανικού («Υπόβαθρο τομής…»)", 7000)
        return None
    u = under[-1]
    p = doc.get(eid).params
    line = ((float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"])))
    found = F.fit(section_sheet(u.params), doc, line)
    name = doc.get(eid).name
    if found is None:
        window.statusBar().showMessage(F.report(None, name), 9000)
        return None
    window.stack.execute(CompositeCommand([UpdateEntity(eid, {"flip": found["flip"]}),
                                           UpdateEntity(u.id, {"x": found["x"], "y": found["y"]})], "Αυτόματη θέση τομής"))
    window._redraw_views(all_views=True) if hasattr(window, "_redraw_views") else None
    panel = getattr(window, "_section_panel", None)
    if panel is not None:
        panel.refresh(fit=True)
    window.statusBar().showMessage(F.report(found, name) + " · Ctrl+Z αναίρεση", 15000)
    return found


def pool_section(window, pool_id, margin=3.0):
    """Πισίνα ▸ «Τομή πισίνας»: a section line along the pool through its middle, 3 m beyond each end — its levels
    in the section tab (rim, water, bottom)."""
    import math
    from archforge.site.pool import param
    if pool_id not in window.doc.entities:
        return None
    p = window.doc.get(pool_id).params
    a = math.radians(param(p, "rotation"))
    h = param(p, "length") / 2 + margin
    cx, cy = float(p["x"]), float(p["y"])
    return create_section(window, cx - math.cos(a) * h, cy - math.sin(a) * h, cx + math.cos(a) * h, cy + math.sin(a) * h)


def import_section_underlay(window, eid, **kwargs):
    """The engineer's section (PDF / DXF) under section ``eid`` — then two clicks place it."""
    if eid not in window.doc.entities:
        return None
    from archforge.ui.underlay_tools import import_drawing
    return import_drawing(window, section_id=eid, **kwargs)


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
