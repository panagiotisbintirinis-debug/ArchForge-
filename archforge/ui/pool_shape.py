"""Πισίνα ▸ «Σχεδίασε το σχήμα»: the pool's outline drawn by clicks in the plan, each corner sharp or curved (an L
with a round-ended spa, a kidney …) — owner 22–23/10: what the PDF import does must be a tool of the program.

Owner 30/10: «το μενού της πισίνας … αναφέρει σχεδίασε την πισίνα, καμπύλες κτλ αλλά δεν σου εμφανίζει σχεδιαστικό
μέσα». So the tool shows itself: the plan comes to the front with a bar on it (Γωνία / Καμπύλη, ακτίνα, ↶ σημείο,
Τέλος, Άκυρο), the existing shape dashed underneath, the new one live under the cursor with its curves, the length of
the edge being drawn and the area.

Click the corners (grid / Shift as everywhere); R switches Γωνία ⇄ Καμπύλη for the next corners, the radius applies
to the last curved corner and the next ones; Backspace takes the last corner back; close on the first corner, double
click, Enter or «Τέλος»; Esc cancels.  One undo.  ``start(None)`` draws a **new** pool (Έδαφος ▸ «Πισίνα με
σχεδίαση σχήματος»).  site/pool.with_outline is the same function the drawing-set import uses for the water it reads.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QDoubleSpinBox, QFrame, QGraphicsTextItem, QHBoxLayout, QLabel,
                               QPushButton)

BLUE = QColor(30, 110, 200)
NEW = "new"                      # pool_id while a new pool is being drawn


class PoolShapeTool:
    def __init__(self, window):
        self.window = window
        self.pool_id = None
        self.points, self.radii = [], []
        self.cursor = None
        self.curve = False
        self.radius = 1.0
        self.bar = None

    # ------------------------------------------------------------------ start / end
    def start(self, pool_id=None):
        """Draw the shape of pool ``pool_id``, or a new pool (None): the plan in front, the bar on it."""
        w = self.window
        from archforge.ui.material_brush import end as _end_brush
        _end_brush(w, quiet=True)
        central = getattr(w, '_central_tabs', None)
        simultaneous = getattr(w, '_simultaneous_action', None)
        if central is not None and not (simultaneous is not None and simultaneous.isChecked()):
            central.setCurrentIndex(0)
        w.view = w.plan_view
        w.plan_view.controller.cancel()
        w.plan_view.controller.set_tool('select')
        self.pool_id = pool_id if pool_id is not None else NEW
        self.points, self.radii, self.cursor = [], [], None
        self._show_bar()
        self._status()
        w.plan_view.setFocus()
        w.plan_view.redraw()

    def cancel(self):
        self.pool_id = None
        self.points, self.radii, self.cursor = [], [], None
        self._hide_bar()
        self.window.statusBar().showMessage("Σχήμα πισίνας: ακυρώθηκε", 4000)
        self.window.plan_view.redraw()

    def apply(self, points, radius=0.0):
        """The pool's shape from plan ``points``, corners rounded by ``radius`` (one number, or one per corner) —
        one undo; False (and a message) if not."""
        from archforge.core.commands import UpdateEntity
        from archforge.site.pool import with_outline
        doc = self.window.doc
        if self.pool_id not in doc.entities:
            return False
        try:
            changes = with_outline(doc.get(self.pool_id).params, points, radius)
            self.window.stack.execute(UpdateEntity(self.pool_id, changes))
        except (ValueError, RuntimeError, PermissionError) as exc:
            self.window.statusBar().showMessage(f"Σχήμα πισίνας: {exc}", 8000)
            return False
        self.window._redraw_views(all_views=True)
        self.window.refresh_inspector()
        from archforge.site.pool import area
        self.window.statusBar().showMessage(
            f"Σχήμα πισίνας: {area(doc.get(self.pool_id).params):.1f} m² · Ctrl+Z αναίρεση".replace(".", ","), 8000)
        return True

    def create(self, points, radius=0.0):
        """A new pool with the shape at ``points`` (its equipment room beside it, as Έδαφος ▸ Πισίνα) — one undo."""
        from archforge.site.pool import DEFAULTS, with_outline
        xs, ys = [float(q[0]) for q in points], [float(q[1]) for q in points]
        p = {**DEFAULTS, 'x': (min(xs) + max(xs)) / 2, 'y': (min(ys) + max(ys)) / 2}
        try:
            changes = with_outline(p, points, radius)
        except ValueError as exc:
            self.window.statusBar().showMessage(f"Πισίνα: {exc}", 8000)
            return None
        x, y = changes.pop('x'), changes.pop('y')
        pool = self.window._place_pool(x, y, **changes)
        if pool is not None:
            self.window.doc.select([pool.id])
            self.window.refresh_inspector()
        return pool

    def _finish(self):
        points, radii = list(self.points), list(self.radii)
        target = self.pool_id
        self.points, self.radii, self.cursor = [], [], None
        self.pool_id = None
        self._hide_bar()
        if len(points) >= 3:
            if target == NEW:
                self.create(points, radii)
            else:
                self.pool_id = target
                self.apply(points, radii)
                self.pool_id = None
        else:
            self.window.statusBar().showMessage("Σχήμα πισίνας: χρειάζονται τουλάχιστον 3 γωνίες — τίποτα δεν άλλαξε", 6000)
        self.window.plan_view.redraw()

    # ------------------------------------------------------------------ editing while drawing
    def add_point(self, x, y):
        if not self.points or math.dist(self.points[-1], (x, y)) > 1e-6:
            self.points.append((float(x), float(y)))
            self.radii.append(float(self.radius) if self.curve else 0.0)
        self._status()

    def undo_point(self):
        if self.points:
            self.points.pop(); self.radii.pop()
        self._status()
        self.window.plan_view.redraw()

    def set_curve(self, on):
        self.curve = bool(on)
        if self.bar is not None:
            self.bar.curve_button.setChecked(self.curve); self.bar.corner_button.setChecked(not self.curve)
            self.bar.radius_box.setEnabled(self.curve)
        self._status()

    def set_radius(self, r):
        self.radius = max(0.05, float(r))
        if self.radii and self.radii[-1] > 0:
            self.radii[-1] = self.radius              # the curved corner just clicked follows the box
        self.window.plan_view.redraw()

    def _status(self):
        if self.pool_id is None:
            return
        what = "Νέα πισίνα" if self.pool_id == NEW else "Σχήμα πισίνας"
        mode = f"Καμπύλη R {self.radius:.2f} m".replace(".", ",") if self.curve else "Γωνία"
        self.window.statusBar().showMessage(
            f"{what}: κλικ στις γωνίες ({len(self.points)}) · τώρα {mode} — R αλλάζει · Backspace = πίσω ένα σημείο · "
            "κλικ στην πρώτη / διπλό κλικ / Enter = τέλος · Esc = άκυρο")
        if self.bar is not None:
            self.bar.title.setText(f"{what} · {len(self.points)} γωνίες")

    # ------------------------------------------------------------------ the bar on the plan
    def _show_bar(self):
        view = self.window.plan_view
        if self.bar is None:
            bar = QFrame(view.viewport()); bar.setObjectName("poolShapeBar")
            bar.setStyleSheet("#poolShapeBar { background: rgba(255,255,255,0.96); border: 1px solid #2F6BD6;"
                              " border-radius: 8px; } QPushButton { padding: 3px 8px; }"
                              " QPushButton:checked { background: #2F6BD6; color: white; }")
            row = QHBoxLayout(bar); row.setContentsMargins(8, 4, 8, 4); row.setSpacing(6)
            bar.title = QLabel(); bar.title.setStyleSheet("font-weight: 600; color: #1e6ec8;")
            bar.corner_button = QPushButton("⌐ Γωνία"); bar.curve_button = QPushButton("◠ Καμπύλη")
            group = QButtonGroup(bar); group.setExclusive(True)
            for b in (bar.corner_button, bar.curve_button):
                b.setCheckable(True); group.addButton(b)
            bar.corner_button.clicked.connect(lambda: self.set_curve(False))
            bar.curve_button.clicked.connect(lambda: self.set_curve(True))
            bar.radius_box = QDoubleSpinBox(); bar.radius_box.setRange(0.05, 10.0); bar.radius_box.setSingleStep(0.05)
            bar.radius_box.setDecimals(2); bar.radius_box.setSuffix(" m"); bar.radius_box.setPrefix("R ")
            bar.radius_box.valueChanged.connect(self.set_radius)
            back = QPushButton("↶ Σημείο"); back.clicked.connect(self.undo_point)
            done = QPushButton("✓ Τέλος"); done.clicked.connect(self._finish)
            stop = QPushButton("✕ Άκυρο"); stop.clicked.connect(self.cancel)
            for wdg in (bar.title, bar.corner_button, bar.curve_button, bar.radius_box, back, done, stop):
                row.addWidget(wdg)
            for wdg in (bar.corner_button, bar.curve_button, bar.radius_box, back, done, stop):
                wdg.setFocusPolicy(Qt.FocusPolicy.ClickFocus if wdg is bar.radius_box else Qt.FocusPolicy.NoFocus)
            self.bar = bar
        self.bar.radius_box.blockSignals(True); self.bar.radius_box.setValue(self.radius)
        self.bar.radius_box.blockSignals(False)
        self.set_curve(self.curve)
        self.bar.adjustSize(); self.bar.move(12, 12); self.bar.show(); self.bar.raise_()

    def _hide_bar(self):
        if self.bar is not None:
            self.bar.hide()

    # ------------------------------------------------------------------ mouse / keys in the plan
    def _xy(self, view, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        p = view._scene_to_plane(pos)
        x, y = float(p.a), float(p.b)
        if view.controller.snap_enabled and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            g = float(view.controller.grid)
            if g > 0:
                x, y = round(x / g) * g, round(y / g) * g
        return x, y

    def handle(self, view, kind, event):
        if self.pool_id is None:
            return False
        if kind == "key":
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.cancel(); return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._finish(); return True
            if key == Qt.Key.Key_Backspace:
                self.undo_point(); return True
            if key == Qt.Key.Key_R:
                self.set_curve(not self.curve); return True
            return False
        if kind == "dclick":
            self._finish(); return True
        if kind == "context":
            self._finish(); return True               # right click = done, as for walls
        if kind not in ("press", "move", "release"):
            return False
        x, y = self._xy(view, event)
        self.cursor = (x, y)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            tol = 9 / max(1.0, abs(view.transform().m11()))
            if len(self.points) >= 3 and math.dist(self.points[0], (x, y)) <= tol:
                self._finish()
            else:
                self.add_point(x, y)
        view.redraw()
        return True

    def preview(self):
        """The plan outline as it would be now (corners clicked + the cursor), curves included."""
        from archforge.site.pool import fillet
        pts = list(self.points) + ([self.cursor] if self.cursor else [])
        radii = list(self.radii) + ([self.radius if self.curve else 0.0] if self.cursor else [])
        if len(pts) < 3:
            return pts
        return fillet(pts, radii)

    def paint(self, view):
        if self.pool_id is None:
            return
        scene = view._scene
        if self.pool_id in self.window.doc.entities:
            from archforge.site.pool import rim
            old = QPen(QColor(120, 120, 120)); old.setCosmetic(True); old.setWidthF(1.2); old.setStyle(Qt.PenStyle.DashLine)
            scene.addPolygon(QPolygonF([QPointF(*q) for q in rim(self.window.doc.get(self.pool_id).params)]), old).setZValue(44)
        k = 1 / max(1e-6, abs(view.transform().m11()))
        pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(2.0)
        if self.cursor is not None:
            x, y = self.cursor
            r = 5 * k
            scene.addLine(x - 2 * r, y, x + 2 * r, y, pen).setZValue(46)
            scene.addLine(x, y - 2 * r, x, y + 2 * r, pen).setZValue(46)
        if not self.points:
            return
        shape = self.preview()
        if len(shape) >= 3:
            fill = QColor(BLUE); fill.setAlpha(40)
            scene.addPolygon(QPolygonF([QPointF(*q) for q in shape]), pen, QBrush(fill)).setZValue(45)
        else:
            for a, b in zip(shape, shape[1:]):
                scene.addLine(a[0], a[1], b[0], b[1], pen).setZValue(45)
        dot = QPen(BLUE); dot.setCosmetic(True); dot.setWidthF(1.5)
        for (px, py), rr in zip(self.points, self.radii):
            s = 4 * k
            if rr > 0:
                scene.addEllipse(px - s, py - s, 2 * s, 2 * s, dot, QBrush(QColor("white"))).setZValue(47)
            else:
                scene.addRect(px - s, py - s, 2 * s, 2 * s, dot, QBrush(QColor("white"))).setZValue(47)
        if self.cursor is not None:
            last = self.points[-1]
            text = f"{math.dist(last, self.cursor):.2f} m".replace(".", ",")
            if len(shape) >= 3:
                a = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(shape, shape[1:] + shape[:1]))) / 2
                text += f" · {a:.1f} m²".replace(".", ",")
            item = scene.addText("")
            item.setHtml(f'<span style="background-color:#ffffff; color:{BLUE.name()}; font-weight:600">&nbsp;{text}&nbsp;</span>')
            item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            item.setPos(self.cursor[0] + 8 * k, self.cursor[1])
            item.setZValue(48)


def install(window):
    tool = PoolShapeTool(window)
    window._pool_shape_tool = tool
    window.plan_view.pool_tool = tool
    return tool
