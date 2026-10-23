"""Πισίνα ▸ «Σχεδίασε το σχήμα»: the pool's outline drawn by clicks in the plan, corners rounded (an L with a
round-ended spa, a kidney …) — owner 22–23/10: what the PDF import does must be a tool of the program.

Click the corners (grid / Shift as everywhere), close on the first corner, double click or Enter; then the
rounding radius (0 = sharp corners).  One undo; site/pool.with_outline is the same function the drawing-set
import uses for the water it reads.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPen, QPolygonF
from PySide6.QtWidgets import QInputDialog

BLUE = QColor(30, 110, 200)


class PoolShapeTool:
    def __init__(self, window):
        self.window = window
        self.pool_id = None
        self.points = []
        self.cursor = None

    def start(self, pool_id):
        self.pool_id = pool_id
        self.points, self.cursor = [], None
        self.window.statusBar().showMessage(
            "Σχήμα πισίνας: κλικ στις γωνίες · κλικ στην πρώτη / διπλό κλικ / Enter κλείσιμο · μετά ακτίνα στρογγυλέματος "
            "(0 = γωνίες) · Esc ακύρωση", 12000)
        self.window.plan_view.redraw()

    def cancel(self):
        self.pool_id = None
        self.points, self.cursor = [], None
        self.window.plan_view.redraw()

    def apply(self, points, radius=0.0):
        """The pool's shape from plan ``points`` with rounded corners — one undo; False (and a message) if not."""
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

    def _finish(self):
        points = list(self.points)
        self.points, self.cursor = [], None
        if len(points) >= 3:
            r, ok = QInputDialog.getDouble(self.window, "Σχήμα πισίνας",
                                           "Στρογγύλεμα γωνιών — ακτίνα (m), 0 = γωνίες:", 0.0, 0.0, 10.0, 2)
            if ok:
                self.apply(points, r)
        self.pool_id = None
        self.window.plan_view.redraw()

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
            if event.key() == Qt.Key.Key_Escape:
                self.cancel(); return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._finish(); return True
            return False
        if kind == "dclick":
            self._finish(); return True
        if kind not in ("press", "move", "release"):
            return False
        x, y = self._xy(view, event)
        self.cursor = (x, y)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            tol = 9 / max(1.0, abs(view.transform().m11()))
            if len(self.points) >= 3 and math.dist(self.points[0], (x, y)) <= tol:
                self._finish()
            elif not self.points or math.dist(self.points[-1], (x, y)) > 1e-6:
                self.points.append((x, y))
        view.redraw()
        return True

    def paint(self, view):
        if self.pool_id is None or not self.points:
            return
        pts = self.points + ([self.cursor] if self.cursor else [])
        pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(2.0)
        poly = QPolygonF([QPointF(*q) for q in pts])
        item = view._scene.addPolygon(poly, pen)
        item.setZValue(45)


def install(window):
    tool = PoolShapeTool(window)
    window._pool_shape_tool = tool
    window.plan_view.pool_tool = tool
    return tool
