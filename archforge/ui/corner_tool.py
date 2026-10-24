"""Επεξεργασία ▸ Γωνία (G): click two walls, they meet in a corner (handoff 24/10, Revit Trim/Extend to Corner).

Click the first wall, then the second, on the parts that stay: each one goes to where the two lines cross —
longer when it fell short, shorter when it ran past (``CornerWalls`` in architecture/wall_edit.py, one undo).
While the mouse is on the second wall the result shows dashed before the click.  The tool stays on for the
next pair; Esc / right click ends it, another tool ends it too.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen

from archforge.architecture.wall_edit import CornerWalls, plan_corner
from archforge.ui.library_drag import wall_at

ORANGE = QColor(230, 120, 20)
BLUE = QColor(20, 110, 220)
HINT = "Γωνία: κλικ στον 1ο τοίχο, στο κομμάτι που μένει · Esc = τέλος"


class CornerTool:
    def __init__(self, window):
        self.w = window
        self.on = False
        self.first = None           # (wall id, plan point) after the first click
        self.hover = None           # wall under the mouse
        self.preview = None         # plan_corner(...) for first + hover, or None

    @property
    def active(self):
        return self.on

    def start(self):
        if str(self.w.plan_view.controller.tool) != "select":
            self.w._set_active_tool("select")
        self.on, self.first, self.hover, self.preview = True, None, None, None
        self.w.statusBar().showMessage(HINT, 15000)
        self.w.plan_view.redraw()

    def cancel(self):
        had = self.on
        self.on, self.first, self.hover, self.preview = False, None, None, None
        if had:
            self.w.statusBar().showMessage("Γωνία: τέλος", 3000)
            self.w.plan_view.redraw()
        return had

    def pick(self, wid, xy):
        """One click on wall ``wid`` at plan point ``xy``; True when the corner was made."""
        if self.first is None:
            self.first = (wid, xy)
            self.w.statusBar().showMessage("Γωνία: κλικ στον 2ο τοίχο, στο κομμάτι που μένει · Esc = τέλος", 15000)
            return False
        if wid == self.first[0]:
            return False
        command = CornerWalls(self.first[0], self.first[1], wid, xy)
        try:
            self.w.stack.execute(command)
        except ValueError as exc:
            self.w.statusBar().showMessage(f"⚠ {exc}", 8000)
            return False
        self.first, self.preview = None, None
        self.w._redraw_views(all_views=True)
        self.w.refresh_inspector()
        note = " ".join(command.plan.get("warnings", ()))
        self.w.statusBar().showMessage(f"Οι τοίχοι έκαναν γωνία · Ctrl+Z = αναίρεση · επόμενο ζευγάρι: κλικ στον 1ο "
                                       f"τοίχο{' · ' + note if note else ''}", 10000)
        return True

    def handle(self, view, kind, event):
        if not self.on:
            return False
        if str(view.controller.tool) != "select":       # another tool was picked: this one steps aside
            self.cancel()
            return False
        if kind == "key":
            if event.key() == Qt.Key.Key_Escape:
                if self.first is not None:
                    self.first, self.preview = None, None
                    self.w.statusBar().showMessage(HINT, 15000)
                    view.redraw()
                else:
                    self.cancel()
                return True
            return False
        if kind == "context":
            self.cancel()
            return True
        if kind not in ("press", "move", "release", "dclick"):
            return False
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        p = view._scene_to_plane(pos)
        xy = (float(p.a), float(p.b))
        self.hover = wall_at(self.w.doc, *xy)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            if self.hover is None:
                self.w.statusBar().showMessage("Γωνία: κλικ πάνω σε τοίχο", 5000)
            else:
                self.pick(self.hover, xy)
        self.preview = None
        if self.first is not None and self.hover is not None and self.hover != self.first[0]:
            try:
                self.preview = plan_corner(self.w.doc, self.first[0], self.first[1], self.hover, xy)
            except ValueError as exc:
                if kind == "move":
                    self.w.statusBar().showMessage(f"⚠ {exc}", 4000)
        view.redraw()
        return True

    def paint(self, view):
        if not self.on:
            return
        doc = self.w.doc

        def axis(wid, colour, width, dashed=False):
            if wid not in doc.entities:
                return
            q = doc.get(wid).params
            pen = QPen(colour); pen.setCosmetic(True); pen.setWidthF(width)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            view._scene.addLine(float(q["x1"]), float(q["y1"]), float(q["x2"]), float(q["y2"]), pen).setZValue(52)

        if self.hover is not None and (self.first is None or self.hover != self.first[0]):
            axis(self.hover, ORANGE, 2.0)
        if self.first is not None:
            axis(self.first[0], ORANGE, 4.0)
        if self.preview is not None:
            pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(2.5); pen.setStyle(Qt.PenStyle.DashLine)
            for e in self.preview["walls"].values():
                view._scene.addLine(e["x1"], e["y1"], e["x2"], e["y2"], pen).setZValue(53)
            r = 6 / max(1.0, abs(view.transform().m11()))
            x, y = self.preview["corner"]
            solid = QPen(BLUE); solid.setCosmetic(True); solid.setWidthF(1.5)
            view._scene.addRect(x - r, y - r, 2 * r, 2 * r, solid).setZValue(53)


def install(window):
    tool = CornerTool(window)
    window._corner_tool = tool
    window.plan_view.corner_tool = tool
    esc = getattr(window, "_escape_shortcut", None)
    if esc is not None:
        esc.activated.connect(tool.cancel)
    return tool
