"""Σχέδια ▸ Σχεδίαση CAD / Σημειώσεις: simple drafting and notes in the plan (architecture/drafting.py).

Clicks in the plan, like the tape (dimension_tool.py): corners and faces of walls, the grid and the points of other
drawings pull the mouse (Shift = no pull); the shape follows the mouse until the last click; one entity, one undo.

* Γραμμή — click, click: a segment; the next one starts where it ended (Esc / right click = end).
* Πολυγραμμή — a click per point; double click or Enter = end; a click on the first point closes it.
* Ορθογώνιο — two opposite corners.   * Κύκλος — centre, then a point on it.   * Τόξο — start, a point on it, end.
* Σημείωση — click where the text goes, type it.   * Σημείωση με βέλος — click what it points at, then the text.

Double click on a note in Επιλογή = change its text (one undo).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPen
from PySide6.QtWidgets import QInputDialog, QMenu

from archforge.architecture import drafting as DR

BLUE = QColor(20, 110, 220)
# mode: (menu text, clicks needed (None = until double click), status hint)
MODES = {
    "line": ("Γραμμή", 2, "κλικ στην αρχή · κλικ στο τέλος · συνεχίζει από εκεί"),
    "polyline": ("Πολυγραμμή", None, "κλικ σε κάθε σημείο · διπλό κλικ / Enter = τέλος · κλικ στο πρώτο = κλειστή"),
    "rect": ("Ορθογώνιο", 2, "κλικ σε μία γωνία · κλικ στην απέναντι"),
    "circle": ("Κύκλος", 2, "κλικ στο κέντρο · κλικ σε σημείο του κύκλου"),
    "arc": ("Τόξο (3 σημεία)", 3, "κλικ στην αρχή · κλικ σε σημείο του τόξου · κλικ στο τέλος"),
    "note": ("Σημείωση", 1, "κλικ εκεί που μπαίνει το κείμενο"),
    "leader": ("Σημείωση με βέλος", 2, "κλικ σε αυτό που δείχνει · κλικ εκεί που μπαίνει το κείμενο"),
}
TOOLTIPS = {
    "line": "Ευθύγραμμα τμήματα στην κάτοψη, το ένα μετά το άλλο. Σχέδιο μόνο: τυπώνεται, δεν χτίζεται.",
    "polyline": "Συνεχής γραμμή από πολλά σημεία· κλικ στο πρώτο σημείο την κλείνει (πολύγωνο).",
    "rect": "Ορθογώνιο από δύο απέναντι γωνίες.",
    "circle": "Κύκλος από το κέντρο και ένα σημείο του.",
    "arc": "Τόξο που περνά από τρία σημεία: αρχή, ένα ενδιάμεσο, τέλος.",
    "note": "Κείμενο στην κάτοψη (τυπώνεται στο PDF και γράφεται στο DXF). Διπλό κλικ = αλλαγή κειμένου.",
    "leader": "Σημείωση με βέλος που δείχνει ένα σημείο (π.χ. «νέα δοκός»).",
}


class DraftTool:
    def __init__(self, window):
        self.w = window
        self.mode = None            # None = off
        self.points = []
        self.cursor = None
        self.snap_kind = ""

    @property
    def active(self):
        return self.mode is not None

    # ------------------------------------------------------------------ start / stop
    def start(self, mode):
        self.mode, self.points, self.cursor = mode, [], None
        label, _n, hint = MODES[mode]
        self.w.statusBar().showMessage(f"{label}: {hint} · Shift = χωρίς έλξη · Esc = τέλος", 20000)
        self.w.plan_view.redraw()

    def cancel(self):
        if self.mode is None:
            return False
        if self.mode == "polyline" and len(self.points) >= 2:
            self._finish_polyline()
        self.mode, self.points, self.cursor = None, [], None
        self.w.plan_view.redraw()
        return True

    @property
    def z(self):
        return float(self.w.doc.work_plane.origin[2])

    def _add(self, entity, message):
        from archforge.core.commands import AddEntity
        try:
            self.w.stack.execute(AddEntity(entity))
        except (ValueError, KeyError) as exc:
            self.w.statusBar().showMessage(f"⚠ {MODES[self.mode][0]}: {exc}", 6000)
            return False
        self.w._redraw_views(all_views=True)
        self.w.statusBar().showMessage(f"{message} · Ctrl+Z = αναίρεση · Esc = τέλος", 8000)
        return True

    # ------------------------------------------------------------------ snapping
    def _xy(self, view, event):
        from archforge.architecture import dimensions as D
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        p = view._scene_to_plane(pos)
        x, y = float(p.a), float(p.b)
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier or not view.controller.snap_enabled:
            return x, y, ""
        tol = min(0.25, max(float(view.controller.snap_tolerance), 9 / max(1.0, abs(view.transform().m11()))))
        best = None
        for e in self.w.doc.entities.values():                    # points of other drawings first
            if e.kind in DR.KINDS and abs(float(e.params.get("level_z", 0.0)) - self.z) <= 1e-5:
                for q in DR.snap_points(e):
                    d = math.dist(q, (x, y))
                    if d <= tol and (best is None or d < best[0]):
                        best = (d, q)
        if self.points and self.mode == "polyline" and math.dist(self.points[0], (x, y)) <= tol:
            return self.points[0][0], self.points[0][1], "close"
        if best is not None:
            return best[1][0], best[1][1], "point"
        return D.tape_snap(self.w.doc, x, y, tol, float(view.controller.grid or 0) or None)

    # ------------------------------------------------------------------ events
    def handle(self, view, kind, event):
        if self.mode is None:
            return self._edit_note(view, kind, event)
        if kind == "key":
            if event.key() == Qt.Key.Key_Escape:
                self.cancel(); return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.mode == "polyline":
                self._finish_polyline(); return True
            return False
        if kind == "context":
            self.cancel(); return True
        if kind == "dclick" and self.mode == "polyline":
            self._finish_polyline(); return True
        if kind not in ("press", "move", "release"):
            return kind == "dclick"
        x, y, self.snap_kind = self._xy(view, event)
        self.cursor = (x, y)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            self._click((x, y))
        view.redraw()
        return True

    def _click(self, pt):
        if self.points and math.dist(self.points[-1], pt) < 1e-4:
            return
        mode = self.mode
        if mode == "polyline" and self.snap_kind == "close" and len(self.points) >= 3:
            self._add(DR.line_entity(self.points, self.z, closed=True), "Κλειστή πολυγραμμή")
            self.points = []
            return
        self.points.append(pt)
        need = MODES[mode][1]
        if need is None or len(self.points) < need:
            return
        pts, self.points = self.points, []
        try:
            if mode == "line":
                if self._add(DR.line_entity(pts, self.z), "Γραμμή"):
                    self.points = [pts[-1]]                           # the next segment starts here
            elif mode == "rect":
                self._add(DR.rectangle_entity(pts[0], pts[1], self.z), "Ορθογώνιο")
            elif mode == "circle":
                self._add(DR.circle_entity(pts[0], pts[1], self.z), "Κύκλος")
            elif mode == "arc":
                self._add(DR.arc_entity(pts[0], pts[1], pts[2], self.z), "Τόξο")
            elif mode in ("note", "leader"):
                text = self._ask_text("")
                if text:
                    at, tip = (pts[-1], pts[0] if mode == "leader" else None)
                    self._add(DR.note_entity(at, text, self.z, leader=tip), "Σημείωση")
        except ValueError as exc:
            self.w.statusBar().showMessage(f"⚠ {MODES[mode][0]}: {exc}", 6000)

    def _finish_polyline(self):
        pts, self.points = self.points, []
        if len(pts) >= 2:
            self._add(DR.line_entity(pts, self.z), "Πολυγραμμή")

    def _ask_text(self, initial):
        text, ok = QInputDialog.getMultiLineText(self.w, "Σημείωση", "Κείμενο της σημείωσης:", initial)
        self.w.plan_view._long_press = None
        return text.strip() if ok else ""

    def _edit_note(self, view, kind, event):
        """Επιλογή: double click on a note → change its text (one undo)."""
        if kind != "dclick" or event.button() != Qt.MouseButton.LeftButton:
            return False
        hit = [view._entity_items.get(i) for i in view.items(event.position().toPoint())]
        eid = next((e for e in hit if e and e in self.w.doc.entities and self.w.doc.get(e).kind == "note"), None)
        if eid is None:
            return False
        from archforge.core.commands import UpdateEntity
        text = self._ask_text(str(self.w.doc.get(eid).params["text"]))
        if text:
            self.w.stack.execute(UpdateEntity(eid, {"text": text}))
            self.w._redraw_views(all_views=True)
            self.w.statusBar().showMessage("Σημείωση: άλλαξε το κείμενο · Ctrl+Z = αναίρεση", 6000)
        return True

    # ------------------------------------------------------------------ live drawing
    def paint(self, view):
        if self.mode is None or self.cursor is None:
            return
        pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(1.5)
        if self.snap_kind:
            r = 6 / max(1.0, abs(view.transform().m11()))
            view._scene.addRect(self.cursor[0] - r, self.cursor[1] - r, 2 * r, 2 * r, pen).setZValue(52)
        pts = self.points + [self.cursor]
        shape = ()
        try:
            if self.mode in ("line", "polyline", "leader") and len(pts) >= 2:
                shape = tuple(pts)
            elif self.mode == "rect" and len(pts) == 2:
                (x0, y0), (x1, y1) = pts
                shape = ((x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0))
            elif self.mode == "circle" and len(pts) == 2:
                shape = DR.arc_points(pts[0][0], pts[0][1], math.dist(*pts), 0.0, 360.0)
            elif self.mode == "arc" and len(pts) == 2:
                shape = tuple(pts)
            elif self.mode == "arc" and len(pts) == 3:
                shape = DR.arc_points(*DR.arc_through(*pts))
        except ValueError:
            shape = tuple(pts)
        for a, b in zip(shape, shape[1:]):
            view._scene.addLine(a[0], a[1], b[0], b[1], pen).setZValue(51)


def menus(window):
    """(Σχεδίαση CAD menu, Σημειώσεις menu)."""
    tool = window._draft_tool
    draw, notes = QMenu("Σχεδίαση CAD", window), QMenu("Σημειώσεις", window)
    window._draft_actions = {}
    for mode in MODES:
        a = QAction(MODES[mode][0], window)
        a.setToolTip(TOOLTIPS[mode]); a.setStatusTip(TOOLTIPS[mode])
        a.triggered.connect(lambda _=False, m=mode: tool.start(m))
        (notes if mode in ("note", "leader") else draw).addAction(a)
        window._draft_actions[mode] = a
    window._main_actions += list(window._draft_actions.values())
    return draw, notes


def install(window):
    """The tool in the plan and its two menus under the old «CAD» menu (main_menus moves them to Σχέδια)."""
    tool = DraftTool(window)
    window._draft_tool = tool
    window.plan_view.drafting_tool = tool
    esc = getattr(window, "_escape_shortcut", None)
    if esc is not None:
        esc.activated.connect(tool.cancel)
    cad = getattr(window, "_cad_menu", None)
    if cad is not None:
        draw, notes = menus(window)
        cad.addSeparator(); cad.addMenu(draw); cad.addMenu(notes)
    return tool
