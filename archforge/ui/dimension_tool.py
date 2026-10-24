"""CAD ▸ Διαστάσεις: the tape (Μεζούρα) and the automatic dimensions, exterior / interior (owner 23/10).

* Μεζούρα: click the first point, click the second (corners and faces of the walls pull the mouse; Shift = no
  pull), move the mouse to where the dimension line goes, click — one ``dimension`` entity, one undo.  Enter
  places it on the points, Esc / right click cancels.  While measuring, the length and Δx / Δy follow the mouse.
* Αυτόματες διαστάσεις: one ``auto_dimensions`` entity per storey; its chains are read from the walls each time
  (architecture/dimensions.py), so moving a wall or a window moves its numbers.  The PDF prints the same ones.

Clicking a dimension selects it (an automatic one selects the storey's set): Delete removes it, Ctrl+Z brings it
back.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPen
from PySide6.QtWidgets import QGraphicsTextItem, QMenu

from archforge.architecture import dimensions as D

BLUE = QColor(20, 110, 220)


class TapeTool:
    def __init__(self, window):
        self.w = window
        self.points = None          # None = off; [] … [a, b] while measuring
        self.cursor = None
        self.kind = ""

    @property
    def active(self):
        return self.points is not None

    def start(self):
        self.points, self.cursor, self.kind = [], None, ""
        self.w.statusBar().showMessage("Μεζούρα: κλικ στο πρώτο σημείο · κλικ στο δεύτερο · κλικ εκεί που μπαίνει η "
                                       "γραμμή (Enter = πάνω στα σημεία) · Shift = χωρίς έλξη · Esc = τέλος", 15000)
        self.w.plan_view.redraw()

    def cancel(self):
        had = self.points is not None
        self.points, self.cursor = None, None
        if had:
            self.w.plan_view.redraw()
        return had

    def place(self, a, b, offset=0.0):
        """Add the measured dimension (one undo); True if it was added."""
        from archforge.core.commands import AddEntity
        doc = self.w.doc
        try:
            entity = D.tape_entity(a, b, float(doc.work_plane.origin[2]), offset)
            self.w.stack.execute(AddEntity(entity))
        except (ValueError, KeyError) as exc:
            self.w.statusBar().showMessage(f"Μεζούρα: {exc}", 6000)
            return False
        self.w._redraw_views(all_views=True)
        self.w.statusBar().showMessage(f"Διάσταση {D.fmt(math.dist(a, b))} m · επόμενη: κλικ στο πρώτο σημείο · "
                                       "Esc = τέλος · Ctrl+Z = αναίρεση", 8000)
        return True

    def _xy(self, view, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        p = view._scene_to_plane(pos)
        x, y = float(p.a), float(p.b)
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier or not view.controller.snap_enabled:
            return x, y, ""
        if len(self.points or ()) == 2:
            return x, y, ""                                   # placing the line: wherever the mouse is
        tol = max(float(view.controller.snap_tolerance), 9 / max(1.0, abs(view.transform().m11())))
        return D.tape_snap(self.w.doc, x, y, min(tol, 0.25), float(view.controller.grid or 0) or None)

    def handle(self, view, kind, event):
        if self.points is None:
            return self._type_dimension(view, kind, event)
        return self._measure(view, kind, event)

    LABEL_PX = 14                      # a click this close to a dimension's number types it

    def _type_dimension(self, view, kind, event):
        """Επιλογή: one click on a dimension's number → type the value; the wall at its end follows (D.drive)."""
        if kind != "press" or event.button() != Qt.MouseButton.LeftButton or str(view.controller.tool) != "select":
            return False
        doc = self.w.doc
        if not any(e.kind in ("dimension", "auto_dimensions") for e in doc.entities.values()):
            return False
        z = float(doc.work_plane.origin[2])
        pos = event.position()
        best = None
        for d in D.storey_dimensions(doc, z):
            at = D.drawing(d)["text_at"]
            q = view.mapFromScene(at[0], at[1])
            gap = math.hypot(q.x() - pos.x(), q.y() - pos.y())
            if gap <= self.LABEL_PX and (best is None or gap < best[0]):
                best = (gap, d)
        if best is None:
            return False
        d = best[1]
        from PySide6.QtWidgets import QInputDialog
        value, ok = QInputDialog.getDouble(self.w, "Διάσταση", "Μήκος (m) — ο τοίχος στην άκρη της ακολουθεί:",
                                           round(float(d["value"]), 3), 0.01, 1000.0, 3)
        view._long_press = None
        if not ok:
            return True
        try:
            wid, command = D.drive(doc, z, d, value)
            self.w.stack.execute(command)
        except ValueError as exc:
            self.w.statusBar().showMessage(f"⚠ Διάσταση: {exc}", 8000)
            return True
        doc.select([wid])
        self.w._redraw_views(all_views=True)
        self.w.refresh_inspector()
        self.w.statusBar().showMessage(f"Διάσταση {D.fmt(value)} · ο τοίχος ακολούθησε · Ctrl+Z = αναίρεση", 6000)
        return True

    def _measure(self, view, kind, event):
        if kind == "key":
            if event.key() == Qt.Key.Key_Escape:
                self.cancel(); return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and len(self.points) == 2:
                a, b = self.points
                self.points = []
                self.place(a, b, 0.0)
                return True
            return False
        if kind == "context":
            self.cancel(); return True
        if kind not in ("press", "move", "release", "dclick"):
            return False
        x, y, self.kind = self._xy(view, event)
        self.cursor = (x, y)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            if len(self.points) < 2:
                if not self.points or math.dist(self.points[-1], (x, y)) > 0.01:
                    self.points.append((x, y))
            else:
                a, b = self.points
                self.points = []
                self.place(a, b, D.tape_offset(a, b, x, y))
        view.redraw()
        return True

    def paint(self, view):
        if self.points is None:
            return
        pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(1.5)
        if self.cursor is not None and self.kind in ("corner", "face"):
            r = 6 / max(1.0, abs(view.transform().m11()))
            x, y = self.cursor
            view._scene.addRect(x - r, y - r, 2 * r, 2 * r, pen).setZValue(52)
        if not self.points or self.cursor is None:
            return
        if len(self.points) == 1:
            a, b, off = self.points[0], self.cursor, 0.0
        else:
            (a, b), off = self.points, D.tape_offset(self.points[0], self.points[1], *self.cursor)
        if math.dist(a, b) < 0.01:
            return
        g = D.drawing(D.manual(D.tape_entity(a, b, 0.0, off)))
        for (p, q) in [g["line"]] + g["extensions"] + g["ticks"]:
            view._scene.addLine(p[0], p[1], q[0], q[1], pen).setZValue(51)
        dx, dy = b[0] - a[0], b[1] - a[1]
        text = f"{D.fmt(math.hypot(dx, dy))} m   Δx {D.fmt(abs(dx))} · Δy {D.fmt(abs(dy))}"
        item = view._scene.addText("")
        item.setHtml(f'<span style="background-color:#ffffff; color:{BLUE.name()}; font-weight:600">&nbsp;{text}&nbsp;</span>')
        item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        item.setPos(self.cursor[0], self.cursor[1])
        item.setZValue(53)


def toggle_auto(window, exterior=None, interior=None):
    """Αυτόματες διαστάσεις on / off for the active storey — one undo."""
    doc = window.doc
    z = float(doc.work_plane.origin[2])
    window.stack.execute(D.set_auto(doc, z, exterior=exterior, interior=interior))
    window._redraw_views(all_views=True)
    s = D.settings(doc, z)
    parts = [w for w, on in (("εξωτερικές", s.params.get("exterior")), ("εσωτερικές", s.params.get("interior"))) if on]
    window.statusBar().showMessage(("Διαστάσεις: " + " και ".join(parts) if parts else "Διαστάσεις: καμία αυτόματη")
                                   + " · Ctrl+Z = αναίρεση", 6000)


def menu(window):
    """CAD ▸ Διαστάσεις."""
    m = QMenu("Διαστάσεις", window)
    tape = QAction("Μεζούρα (μέτρηση με 2 κλικ)", window)
    tape.triggered.connect(lambda: window._tape_tool.start())
    ext = QAction("Αυτόματες διαστάσεις: εξωτερικές", window); ext.setCheckable(True)
    inn = QAction("Αυτόματες διαστάσεις: εσωτερικές (καθαρά χώρων)", window); inn.setCheckable(True)
    ext.triggered.connect(lambda on: toggle_auto(window, exterior=on))
    inn.triggered.connect(lambda on: toggle_auto(window, interior=on))

    def refresh():
        s = D.settings(window.doc, float(window.doc.work_plane.origin[2]))
        ext.setChecked(bool(s and int(s.params.get("exterior", 0))))
        inn.setChecked(bool(s and int(s.params.get("interior", 0))))
    m.aboutToShow.connect(refresh)
    for a in (tape, None, ext, inn):
        m.addSeparator() if a is None else m.addAction(a)
    window._main_actions += [tape, ext, inn]
    window._dimension_actions = {"tape": tape, "exterior": ext, "interior": inn}
    return m


def install(window):
    tool = TapeTool(window)
    window._tape_tool = tool
    window.plan_view.tape_tool = tool
    esc = getattr(window, "_escape_shortcut", None)
    if esc is not None:
        esc.activated.connect(tool.cancel)
    return tool
