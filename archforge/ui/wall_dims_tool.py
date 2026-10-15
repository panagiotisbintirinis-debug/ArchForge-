"""Dimensions on a selected wall, and moving it with a double click (owner 15/10: «εμφανείς διαστάσεις με
επιλογή και δυνατότητα μετακίνησης τοίχου με διπλό κλικ»).

* One wall selected → its length and the clear distances to the walls facing it, in blue, on the plan.
* Double click on a wall → it follows the mouse (no button held) perpendicular to its axis; the walls joined
  to it stretch in the preview and the distances update live; click = place it, Esc / right click = cancel.
* Double click on a distance → type the one you want; the wall moves there.

Every move is the shared ``wall_edit.MoveWall`` (one undo, joined walls / openings / objects follow).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPen

from archforge.architecture.wall_dims import fmt, offset_for, wall_dims

BLUE = QColor(30, 100, 200)
RED = QColor(200, 50, 40)


class WallDimsTool:
    def __init__(self, window):
        self.w = window
        self.moving = None          # {"eid", "start": (x, y), "offset", "problem"}
        self._labels = []           # [(text item, side)] painted this time (side None = length)

    @property
    def doc(self):
        return self.w.doc

    def _selected_wall(self, view):
        sel = [i for i in self.doc.selection if i in self.doc.entities]
        if len(sel) == 1 and self.doc.get(sel[0]).kind == "wall" and str(view.controller.tool) == "select" \
                and view.controller.active is None:
            return sel[0]
        return None

    # ---------------------------------------------------------------- moving
    def start_move(self, eid, x, y):
        self.moving = {"eid": eid, "start": (float(x), float(y)), "offset": 0.0, "problem": None}
        self.doc.select([eid])
        self.w.statusBar().showMessage("Μετακίνηση τοίχου: κούνησε το ποντίκι · κλικ = εδώ · Esc = ακύρωση · "
                                       "διπλό κλικ σε απόσταση = ακριβής τιμή", 15000)

    def _step(self, view):
        if not getattr(self.w, "snap_action", None) or not self.w.snap_action.isChecked():
            return 0.01
        return float(getattr(view, "_grid_step", None) or 0.10)

    def update_move(self, view, x, y, free=False):
        from archforge.architecture.wall_edit import plan_move, wall_normal
        m = self.moving
        nx, ny = wall_normal(self.doc.get(m["eid"]).params)
        d = (x - m["start"][0]) * nx + (y - m["start"][1]) * ny
        step = 0.01 if free else self._step(view)
        m["offset"] = round(d / step) * step
        try:
            m["plan"] = plan_move(self.doc, m["eid"], m["offset"]) if abs(m["offset"]) > 1e-9 else None
            m["problem"] = None
        except ValueError as exc:
            m["plan"], m["problem"] = None, str(exc)

    def commit(self, offset=None):
        from archforge.architecture.wall_edit import MoveWall
        eid = self.moving["eid"] if self.moving else None
        offset = self.moving["offset"] if offset is None and self.moving else offset
        self.moving = None
        if eid is None or offset is None or abs(offset) < 1e-9:
            return False
        try:
            self.w.stack.execute(MoveWall(eid, float(offset)))
        except ValueError as exc:
            self.w.statusBar().showMessage(f"⚠ {exc}", 6000)
            return False
        self.doc.select([eid])
        self.w._redraw_views(all_views=True)
        self.w.refresh_inspector()
        self.w.statusBar().showMessage(f"Ο τοίχος μετακινήθηκε {offset * 100:+.0f} cm · Ctrl+Z = αναίρεση", 6000)
        return True

    def cancel(self):
        had = self.moving is not None
        self.moving = None
        return had

    def type_clear(self, eid, side):
        """Double click on a distance: the value you want → the wall moves there."""
        from PySide6.QtWidgets import QInputDialog
        dims = wall_dims(self.doc, eid)
        now = next((x["clear"] for x in dims["sides"] if x["side"] == side), None)
        if now is None:
            return False
        value, ok = QInputDialog.getDouble(self.w, "Απόσταση από τον απέναντι τοίχο",
                                           "Καθαρή απόσταση (m) — ο τοίχος μετακινείται, οι ενωμένοι τεντώνουν:",
                                           round(now, 2), 0.05, 100.0, 2)
        if not ok:
            return False
        try:
            off = offset_for(self.doc, eid, side, value)
        except ValueError as exc:
            self.w.statusBar().showMessage(f"⚠ {exc}", 6000)
            return False
        self.moving = {"eid": eid, "offset": off}
        return self.commit()

    # ---------------------------------------------------------------- mouse
    def handle(self, view, kind, event):
        if kind == "key":
            if self.moving is not None and event.key() == Qt.Key.Key_Escape:
                self.cancel(); view.redraw()
                self.w.statusBar().showMessage("Μετακίνηση τοίχου: ακυρώθηκε", 4000)
                return True
            return False
        if kind == "context":
            if self.moving is not None:
                self.cancel(); view.redraw()
                return True
            return False
        p = view.mapToScene(event.position().toPoint())
        if self.moving is not None:
            if kind == "move":
                free = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                self.update_move(view, p.x(), p.y(), free)
                view.redraw()
                return True
            if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
                self.update_move(view, p.x(), p.y(), bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                self.commit()
                return True
            return kind in ("release", "dclick")
        if kind != "dclick" or event.button() != Qt.MouseButton.LeftButton or str(view.controller.tool) != "select":
            return False
        # A distance label of the selected wall?
        hit = view.itemAt(event.position().toPoint())
        for item, side in self._labels:
            if hit is item and side is not None:
                eid = self._selected_wall(view)
                if eid:
                    self.type_clear(eid, side)
                    return True
        eid = view._entity_items.get(hit)
        if eid and eid in self.doc.entities and self.doc.get(eid).kind == "wall" and not self.doc.get(eid).locked:
            self.start_move(eid, p.x(), p.y())
            view.selectionChangedByView.emit()
            view.redraw()
            return True
        return False

    # ---------------------------------------------------------------- drawing
    def paint(self, view):
        self._labels = []
        if self.moving is not None and self.moving.get("eid") in self.doc.entities:
            m = self.moving
            plan = m.get("plan") or {}
            ghost = QPen(BLUE if not m.get("problem") else RED); ghost.setWidthF(.03); ghost.setStyle(Qt.PenStyle.DashLine)
            for wid, ends in plan.get("walls", {}).items():
                view._scene.addLine(ends["x1"], ends["y1"], ends["x2"], ends["y2"], ghost).setZValue(48)
            if not plan:
                from archforge.architecture.wall_edit import _ends, wall_normal
                (ax, ay), (bx, by) = _ends(self.doc.get(m["eid"]).params)
                nx, ny = wall_normal(self.doc.get(m["eid"]).params)
                o = m["offset"]
                view._scene.addLine(ax + nx * o, ay + ny * o, bx + nx * o, by + ny * o, ghost).setZValue(48)
            self._paint_dims(view, m["eid"], m["offset"], moving=True)
            if m.get("problem"):
                p = self.doc.get(m["eid"]).params
                self._text(view, "⚠ " + m["problem"], float(p["x1"]), float(p["y1"]), RED)
            return
        eid = self._selected_wall(view)
        if eid:
            self._paint_dims(view, eid, 0.0)

    def _paint_dims(self, view, eid, offset, moving=False):
        dims = wall_dims(self.doc, eid, offset)
        if dims is None:
            return
        pen = QPen(BLUE); pen.setWidthF(.012)
        tick = QPen(BLUE); tick.setWidthF(.02)
        nx, ny = dims["normal"]
        items = [(dims["length"], None, dims["length"]["value"])] + [(s, s["side"], s["clear"]) for s in dims["sides"]]
        for d, side, value in items:
            (ax, ay), (bx, by) = d["a"], d["b"]
            view._scene.addLine(ax, ay, bx, by, pen).setZValue(49)
            # Ticks across the dimension line at both ends.
            import math
            L = math.hypot(bx - ax, by - ay) or 1.0
            tx, ty = -(by - ay) / L * .08, (bx - ax) / L * .08
            for px, py in ((ax, ay), (bx, by)):
                view._scene.addLine(px - tx, py - ty, px + tx, py + ty, tick).setZValue(49)
            item = self._text(view, fmt(value), (ax + bx) / 2, (ay + by) / 2, BLUE, editable=side is not None and not moving)
            self._labels.append((item, side))

    def _text(self, view, text, x, y, color, editable=False):
        from PySide6.QtWidgets import QGraphicsTextItem
        item = view._scene.addText("")
        item.setHtml(f'<span style="background-color:#ffffff; color:{color.name()}; font-weight:600">&nbsp;{text}&nbsp;</span>')
        item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        item.setPos(x, y)
        item.setZValue(50)
        if editable:
            item.setToolTip("Διπλό κλικ: γράψε την απόσταση που θέλεις — ο τοίχος μετακινείται")
            item.setCursor(Qt.CursorShape.PointingHandCursor)
        return item


def install(window):
    tool = WallDimsTool(window)
    window._wall_dims = tool
    window.plan_view.dims_tool = tool
    esc = getattr(window, "_escape_shortcut", None)
    if esc is not None:
        # Esc is the window's «cancel what is in progress»: it ends a wall move too.
        esc.activated.connect(lambda: tool.cancel() and window.plan_view.redraw())
    return tool
