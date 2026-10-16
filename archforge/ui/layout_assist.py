"""«Κουζίνα εδώ… / Μπάνιο εδώ…» in the plan: guide lines, ghost preview, one-undo apply.

The mouse does everything: click inside a room for an automatic proposal,
or click points on its walls (they snap to the faces and the corners, with
the length of every leg written next to it) and double click / Enter /
right click to finish the guide line.  The proposal shows as a ghost until
«Εφαρμογή» (Enter); «Επόμενη παραλλαγή» (Tab) cycles the alternatives;
Delete or Esc throws it away to try another place.  After applying, the
pieces are ordinary cabinets / fixtures: selected all together (Delete
removes the whole layout, Ctrl+Z undoes it), then each one can be dragged
on its own and clicks onto the wall and its neighbour.

This module only keeps UI state (draft points, the ghost); the Document
changes through the shared commands of ``assistant.room_layout``.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGraphicsTextItem, QGroupBox, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout)

TOOLS = {"kitchen": "layout_kitchen", "bath": "layout_bath"}
HINT = {
    "kitchen": "Κουζίνα: κλικ μέσα στον χώρο = αυτόματη πρόταση · ή κλικ πάνω στους τοίχους (αρχή, γωνίες, τέλος) "
               "και διπλό κλικ / Enter = τέλος γραμμής · Esc = ακύρωση",
    "bath": "Μπάνιο: κλικ μέσα στον χώρο = αυτόματη πρόταση · ή γραμμή πάνω στον τοίχο των υδραυλικών "
            "και διπλό κλικ / Enter · Esc = ακύρωση",
}


def _label(view, text, x, y, color=QColor(30, 30, 30), bold=False):
    item = view._scene.addText(text)
    item.setDefaultTextColor(color)
    if bold:
        f = item.font(); f.setBold(True); item.setFont(f)
    item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    item.setPos(x, y)
    item.setZValue(60)
    return item


class LayoutAssist:
    def __init__(self, window):
        self.w = window
        self.mode = None
        self.room = None
        self.runs = []
        self.points = []           # [(run, s)] of the guide line being drawn
        self.cursor = None         # snapped cursor (run, s, (x, y)) or None
        self.proposal = None
        self.legs = None
        self.variant = 0
        self.options = {"kitchen": {"shape": "auto", "dishwasher": True, "fridge": True}, "bath": {"wet": "shower"}}
        self._press = None
        self._dragging = False
        self.last_layout = None

    # ---------------------------------------------------------------- state
    @property
    def doc(self):
        return self.w.doc

    def status(self, text, ms=9000):
        self.w.statusBar().showMessage(text, ms)

    def start(self, kind, xy=None):
        """Start «Κουζίνα εδώ» / «Μπάνιο εδώ» (from the panel, the menu or the mouse menu at ``xy``)."""
        self.mode = kind
        self._reset()
        self.w._start_site_tool(TOOLS[kind], HINT[kind])
        dock = getattr(self.w, "_assistant_dock", None)
        if dock is not None:
            dock.show(); dock.raise_()
        if xy is not None:
            self.propose_at(*xy)
        self._sync_panel()
        self.w.plan_view.redraw()

    def _reset(self):
        self.points, self.cursor, self.proposal, self.legs, self.variant = [], None, None, None, 0

    def _room(self, x, y):
        from archforge.assistant.room_walls import room_runs
        from archforge.assistant.suggestions import room_at
        room = room_at(self.doc, x, y)
        if room is None:
            return None
        if self.room is None or room["signature"] != self.room["signature"]:
            self.room, self.runs, self.points = room, room_runs(self.doc, room), []
        return room

    def propose_at(self, x, y):
        if self._room(x, y) is None:
            self.status("Κλικ μέσα σε κλειστό χώρο (σχεδίασε πρώτα τους τοίχους)")
            return None
        self.legs, self.variant = None, 0
        return self.propose()

    def propose(self):
        from archforge.assistant.room_layout import plan
        if self.room is None or self.mode is None:
            return None
        self.proposal = plan(self.doc, self.mode, self.room, legs=self.legs, options=self.options[self.mode],
                             variant=self.variant)
        self.variant = self.proposal.variant
        problems = " · ⚠ " + " · ".join(self.proposal.problems) if self.proposal.problems else ""
        self.status(f"{self.proposal.label}{problems} — Enter/✓ Εφαρμογή · Tab επόμενη παραλλαγή · Delete σβήσιμο", 15000)
        self._sync_panel()
        self.w.plan_view.redraw()
        return self.proposal

    def finish_line(self):
        from archforge.assistant.room_walls import legs_from_points
        if not self.points:
            return None
        legs = legs_from_points(self.runs, self.points)
        self.points, self.cursor = [], None
        if not legs:
            self.status("Η γραμμή είναι πολύ κοντή — κλικ σε αρχή και τέλος πάνω στον τοίχο")
            self.w.plan_view.redraw()
            return None
        self.legs, self.variant = legs, 0
        return self.propose()

    def next_variant(self):
        if self.proposal is None:
            return None
        self.variant = self.proposal.variant + 1
        return self.propose()

    def set_option(self, key, value):
        kind = "bath" if key == "wet" else "kitchen"
        self.options[kind][key] = value
        if self.proposal is not None and self.mode == kind:
            self.variant = 0
            self.propose()

    def apply(self):
        """«Εφαρμογή»: one AddEntities (one undo); the new pieces stay selected."""
        from archforge.assistant.room_layout import apply_command
        if self.proposal is None or not self.proposal.entities:
            self.status("Δεν υπάρχει πρόταση — κλικ μέσα σε χώρο ή γραμμή στον τοίχο")
            return None
        proposal = self.proposal
        self.w.stack.execute(apply_command(proposal))
        ids = [e.id for e in proposal.entities if e.kind in ("cabinet", "library_object")]
        self.doc.select(ids)
        self.last_layout = proposal.layout_id
        self._reset()
        self.mode = None
        self.w._set_active_tool("select")
        self._refresh()
        counts = proposal.summary()
        self.status(f"✓ {proposal.label.split(' · ')[0]}: {counts.get('cabinet', 0)} ντουλάπια, {counts.get('library_object', 0)} "
                    "συσκευές/είδη — επιλεγμένα όλα: Delete = σβήσιμο όλης · Ctrl+Z = αναίρεση · σύρε ένα κομμάτι για μετακίνηση", 15000)
        return proposal

    def discard(self):
        """Delete / Esc on a ghost or a guide line: throw it away (nothing was in the Document)."""
        if self.proposal is None and not self.points:
            return False
        self._reset()
        self._sync_panel()
        self.w.plan_view.redraw()
        if self.mode:
            self.status("Η πρόταση σβήστηκε — κλικ σε άλλο σημείο για νέα δοκιμή · Esc = τέλος", 8000)
        return True

    def cancel(self):
        had = self.discard()
        if self.mode and str(self.w.plan_view.controller.tool).startswith("layout_"):
            self.mode = None
            self.w.plan_view.controller.set_tool("select")
        self._sync_panel()
        return had

    def delete_layout(self, layout_id=None):
        from archforge.assistant.room_layout import delete_command
        lid = layout_id or self._selected_layout()
        command = delete_command(self.doc, lid) if lid else None
        if command is None:
            self.status("Δεν βρέθηκε διάταξη του Βοηθού στην επιλογή")
            return None
        self.w.stack.execute(command)
        self.doc.select([])
        self._refresh()
        self.status("Η διάταξη σβήστηκε (ένα undo) — «Κουζίνα/Μπάνιο εδώ…» για νέα δοκιμή", 8000)
        return command

    def refit(self, layout_id=None):
        from archforge.assistant.room_layout import refit
        lid = layout_id or self._selected_layout() or self.last_layout
        command, proposal = refit(self.doc, lid) if lid else (None, None)
        if command is None:
            self.status("Επίλεξε ένα κομμάτι της διάταξης (ντουλάπι ή είδος) για αναπροσαρμογή")
            return None
        self.w.stack.execute(command)
        self.doc.select([e.id for e in proposal.entities if e.kind in ("cabinet", "library_object")])
        self._refresh()
        self.status(f"✓ Αναπροσαρμογή: {proposal.label.split(' · ')[0]} για τον νέο χώρο — Ctrl+Z = αναίρεση", 10000)
        return proposal

    def _selected_layout(self):
        from archforge.assistant.room_layout import layout_of
        for eid in self.doc.selection:
            lid = layout_of(self.doc, eid)
            if lid:
                return lid
        return None

    def _refresh(self):
        self.w._redraw_views(all_views=True)
        for name in ("_refresh_project_tree", "refresh_inspector", "_schedule_assistant_refresh"):
            fn = getattr(self.w, name, None)
            if fn is not None:
                fn()
        self._sync_panel()

    # ---------------------------------------------------------------- mouse (PlanView overlay)
    def handle(self, view, kind, event):
        tool = str(view.controller.tool)
        run_tool = getattr(self.w, "_cabinet_run", None)
        if run_tool is not None and tool == "layout_cabinet_run":
            return run_tool.handle(view, kind, event)          # «Γραμμή ντουλαπιών» (ui/cabinet_run_tool.py)
        if tool.startswith("layout_"):
            return self._layout_event(view, kind, event)
        if kind == "press" and tool == "select":
            from archforge.assistant.fixture_snap import snappable
            eid = view._entity_items.get(view.itemAt(event.position().toPoint()))
            if eid and eid in self.doc.entities and snappable(self.doc, self.doc.get(eid)):
                p = view.mapToScene(event.position().toPoint())
                self._press = (eid, p.x(), p.y())
            else:
                self._press = None
            return False
        if kind == "move" and self._press and getattr(view, "_mouse_down", False) and tool == "select":
            eid, x0, y0 = self._press
            p = view.mapToScene(event.position().toPoint())
            if math.hypot(p.x() - x0, p.y() - y0) < 0.08:
                return False
            # Dragging a cabinet / fixture: the shared move transaction (snaps onto the wall / neighbour).
            from archforge.core.viewport import PointerEvent
            self._press = None
            self.doc.select([eid])
            view.controller.set_tool("move")
            view.controller.set_target(eid, None)
            try:
                view.controller.pointer_down(PointerEvent(x0, y0))
            except (ValueError, RuntimeError, KeyError):
                view.controller.set_tool("select")
                return False
            view._mouse_down = True
            self._dragging = True
            return False
        if kind == "release":
            self._press = None
            if self._dragging:
                self._dragging = False
                ev = view._scene_to_plane(event.position().toPoint())
                ev.shift = ev.ctrl = False
                try:
                    view.controller.pointer_up(ev)
                except ValueError as exc:
                    view.controller.cancel()
                    self.status(str(exc))
                view._mouse_down = False
                view.controller.set_tool("select")
                view.redraw()
                view.selectionChangedByView.emit()
                self._refresh()
                self.status("Μετακινήθηκε — κούμπωσε στον τοίχο / στο διπλανό · Ctrl+Z = αναίρεση", 6000)
                return True
        return False

    def _layout_event(self, view, kind, event):
        from archforge.assistant.room_walls import snap_point
        if kind == "key":
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                (self.finish_line if self.points else self.apply)()
                return True
            if key == Qt.Key.Key_Tab:
                self.next_variant()
                return True
            if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                return self.discard()
            return False
        if kind == "context":
            if self.points:
                self.finish_line()
                return True
            return False
        p = view.mapToScene(event.position().toPoint())
        x, y = p.x(), p.y()
        if kind == "move":
            if self.mode and self._room(x, y) is not None:
                self.cursor = snap_point(self.runs, x, y)
            else:
                self.cursor = None
            view.redraw()
            return True
        if kind == "dclick":
            self.finish_line()
            return True
        if kind == "release":
            return True
        if kind != "press":
            return False
        if self.mode is None:
            self.mode = "bath" if str(view.controller.tool) == "layout_bath" else "kitchen"
        before = self.room["signature"] if self.room else None
        if self._room(x, y) is None:
            self.status("Κλικ μέσα σε κλειστό χώρο (σχεδίασε πρώτα τους τοίχους)")
            return True
        if before is not None and before != self.room["signature"]:
            self.proposal = None
        hit = snap_point(self.runs, x, y)
        if hit is None:
            if self.points:
                self.status("Η γραμμή πατά στους τοίχους: κλικ κοντά σε τοίχο · διπλό κλικ / Enter = τέλος")
                return True
            self.propose_at(x, y)
            return True
        i, s, _xy = hit
        if not self.points or self.points[-1] != (i, s):
            self.points.append((i, s))
        self.proposal = None
        n = len(self.points)
        self.status(("Αρχή γραμμής — κλικ στη γωνία ή στο τέλος της" if n == 1 else
                     f"{n} σημεία — συνέχισε, ή διπλό κλικ / Enter / δεξί κλικ = τέλος γραμμής") + " · Esc = ακύρωση")
        self._sync_panel()
        view.redraw()
        return True

    # ---------------------------------------------------------------- drawing
    def paint(self, view):
        from archforge.assistant.room_walls import fmt_m, legs_from_points
        tool = str(view.controller.tool)
        run_tool = getattr(self.w, "_cabinet_run", None)
        if run_tool is not None:
            run_tool.paint(view)
            if tool == "layout_cabinet_run":
                return
        if self.proposal is not None:
            self._paint_ghost(view)
        if not tool.startswith("layout_") or not self.runs:
            return
        pts = list(self.points)
        if self.cursor is not None and pts:
            pts.append((self.cursor[0], self.cursor[1]))
        if pts:
            orange = QColor(230, 120, 20)
            pen = QPen(orange); pen.setWidthF(.06); pen.setStyle(Qt.PenStyle.DashLine)
            for i, lo, hi in legs_from_points(self.runs, pts):
                r = self.runs[i]
                a, b = r.point(lo, 0.04), r.point(hi, 0.04)
                view._scene.addLine(a[0], a[1], b[0], b[1], pen).setZValue(45)
                mx, my = r.point((lo + hi) / 2, 0.45)
                _label(view, fmt_m(hi - lo), mx, my, orange, bold=True)
            dot = QPen(orange); dot.setWidthF(.02)
            for i, s in self.points:
                x, y = self.runs[i].point(s, 0.04)
                view._scene.addEllipse(x - .08, y - .08, .16, .16, dot, QBrush(orange)).setZValue(46)
        if self.cursor is not None:
            x, y = self.cursor[2]
            pen = QPen(QColor(230, 120, 20)); pen.setWidthF(.025)
            view._scene.addEllipse(x - .11, y - .11, .22, .22, pen).setZValue(46)

    def _paint_ghost(self, view):
        from archforge.assistant.room_layout import ghost
        fills = {"base": QColor(70, 170, 110, 70), "wall": QColor(0, 0, 0, 0), "object": QColor(60, 130, 210, 60),
                 "point": QColor(31, 90, 160, 200)}
        for kind, pts, closed in ghost(self.proposal):
            if len(pts) < 2:
                continue
            pen = QPen(QColor(30, 120, 70) if kind in ("base", "wall", "front") else QColor(40, 90, 160))
            pen.setWidthF(.02 if kind in ("base", "object") else .012)
            if kind == "wall":
                pen.setStyle(Qt.PenStyle.DashLine)
            if closed:
                item = view._scene.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]), pen, QBrush(fills.get(kind, QColor(0, 0, 0, 0))))
            else:
                path = QPainterPath(QPointF(*pts[0]))
                for q in pts[1:]:
                    path.lineTo(QPointF(*q))
                item = view._scene.addPath(path, pen)
            item.setZValue(35)
        if self.room is not None:
            cx, cy = self.room["centroid"]
            text = self.proposal.label + ("  ⚠" if self.proposal.problems else "") + "  —  Enter = Εφαρμογή · Tab = επόμενη · Delete = σβήσιμο"
            _label(view, text, cx - 1.2, cy + 0.3, QColor(20, 90, 50), bold=True)

    # ---------------------------------------------------------------- panel
    def build_panel(self, parent):
        box = QGroupBox("Κουζίνα / Μπάνιο εδώ", parent)
        lay = QVBoxLayout(box)
        row = QHBoxLayout()
        kitchen = QPushButton("Κουζίνα εδώ…", box); kitchen.clicked.connect(lambda: self.start("kitchen"))
        bath = QPushButton("Μπάνιο εδώ…", box); bath.clicked.connect(lambda: self.start("bath"))
        row.addWidget(kitchen); row.addWidget(bath)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Σχήμα", box))
        from archforge.assistant.kitchen_layout import SHAPES
        self.shape = QComboBox(box)
        for key, text in SHAPES.items():
            self.shape.addItem(text, key)
        self.shape.currentIndexChanged.connect(lambda _i: self.set_option("shape", self.shape.currentData()))
        row.addWidget(self.shape)
        self.dishwasher = QCheckBox("Πλυντ. πιάτων", box); self.dishwasher.setChecked(True)
        self.dishwasher.toggled.connect(lambda v: self.set_option("dishwasher", bool(v)))
        row.addWidget(self.dishwasher)
        self.wet = QComboBox(box)
        self.wet.addItem("με ντουζιέρα", "shower"); self.wet.addItem("με μπανιέρα", "bathtub")
        self.wet.currentIndexChanged.connect(lambda _i: self.set_option("wet", self.wet.currentData()))
        row.addWidget(self.wet)
        lay.addLayout(row)
        self.info = QLabel("Κλικ σε «Κουζίνα εδώ…» ή «Μπάνιο εδώ…», μετά κλικ στον χώρο ή γραμμή στους τοίχους.", box)
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        self.apply_button = QPushButton("✓ Εφαρμογή διάταξης", box); self.apply_button.clicked.connect(self.apply)
        self.next_button = QPushButton("Επόμενη παραλλαγή", box); self.next_button.clicked.connect(self.next_variant)
        self.discard_button = QPushButton("Σβήσε πρόταση", box); self.discard_button.clicked.connect(self.discard)
        for b in (self.apply_button, self.next_button, self.discard_button):
            row.addWidget(b)
        lay.addLayout(row)
        row = QHBoxLayout()
        refit = QPushButton("Αναπροσαρμογή διάταξης", box); refit.clicked.connect(lambda: self.refit())
        delete = QPushButton("Σβήσε όλη τη διάταξη", box); delete.clicked.connect(lambda: self.delete_layout())
        row.addWidget(refit); row.addWidget(delete)
        lay.addLayout(row)
        self.box = box
        self._sync_panel()
        return box

    def _sync_panel(self):
        if not hasattr(self, "info"):
            return
        p = self.proposal
        has = p is not None and bool(p.entities)
        for b in (self.apply_button, self.next_button, self.discard_button):
            b.setEnabled(has or (b is self.discard_button and bool(self.points)))
        if p is None:
            self.info.setText(HINT[self.mode] if self.mode else
                              "Κλικ σε «Κουζίνα εδώ…» ή «Μπάνιο εδώ…», μετά κλικ στον χώρο ή γραμμή στους τοίχους.")
            return
        lines = [f"<b>{p.label}</b>"] + [f"⚠ {t}" for t in p.problems] + [f"• {t}" for t in p.notes[:4]]
        lines.append(f"<i>{p.source}</i>")
        self.info.setText("<br>".join(lines))


# ---------------------------------------------------------------- mouse menu
def marking_entries(window):
    """The mouse menu while «Κουζίνα/Μπάνιο εδώ» is active."""
    from archforge.ui.marking_menu import _e
    a = window._layout_assist
    entries = [_e("mm:layout:apply", "✓ Εφαρμογή")]
    if a.points:
        entries = [_e("mm:layout:finish", "✓ Τέλος γραμμής")]
    entries.append(_e("mm:layout:next", "↻ Επόμενη παραλλαγή"))
    if a.mode == "bath":
        wet = a.options["bath"]["wet"]
        entries += [_e("mm:layout:wet_shower", "Ντουζιέρα", checked=wet == "shower"),
                    _e("mm:layout:wet_bathtub", "Μπανιέρα", checked=wet == "bathtub")]
    else:
        shape = a.options["kitchen"]["shape"]
        entries += [_e(f"mm:layout:shape_{k}", t, checked=k == shape) for k, t in (("I", "Ι"), ("L", "Γ"), ("U", "Π"), ("auto", "Αυτόματο"))]
    entries.append(_e("mm:layout:discard", "✕ Σβήσε πρόταση", danger=True))
    entries.append(_e("mm:layout:end", "Τέλος", "panel"))
    center = a.proposal.label if a.proposal is not None else ("Κουζίνα εδώ" if a.mode != "bath" else "Μπάνιο εδώ")
    return {"center": center, "entries": entries, "wheel": None}


def run(window, arg, entity_id=None, plan_xy=None):
    a = window._layout_assist
    if arg in ("kitchen", "bath"):
        a.start(arg, plan_xy)
    elif arg == "apply":
        a.apply()
    elif arg == "finish":
        a.finish_line()
    elif arg == "next":
        a.next_variant()
    elif arg == "discard":
        a.discard()
    elif arg == "end":
        a.cancel()
    elif arg.startswith("shape_"):
        a.set_option("shape", arg[len("shape_"):])
        if a.proposal is None and a.room is not None and not a.points:
            a.propose()
    elif arg.startswith("wet_"):
        a.set_option("wet", arg[len("wet_"):])
        if a.proposal is None and a.room is not None and not a.points:
            a.propose()
    elif arg == "refit":
        a.refit(window.doc.get(entity_id).params.get("layout_id") if entity_id in window.doc.entities else None)
    elif arg == "delete_all":
        a.delete_layout(window.doc.get(entity_id).params.get("layout_id") if entity_id in window.doc.entities else None)


def install_layout_assist(window):
    """Panel in the Βοηθός dock, entries in the Κουζίνα menu, the plan overlay."""
    from PySide6.QtGui import QAction
    assist = LayoutAssist(window)
    window._layout_assist = assist
    window.plan_view.overlay_tool = assist
    dock = getattr(window, "_assistant_dock", None)
    if dock is not None and dock.widget() is not None and dock.widget().layout() is not None:
        dock.widget().layout().insertWidget(1, assist.build_panel(dock.widget()))
    menus = getattr(window, "_mockup_menus", {}) or {}
    menu = menus.get("Κουζίνα")
    if menu is not None:
        for text, fn in (("Κουζίνα εδώ (Βοηθός)…", lambda: assist.start("kitchen")),
                         ("Μπάνιο εδώ (Βοηθός)…", lambda: assist.start("bath")),
                         (None, None),
                         ("Αναπροσαρμογή διάταξης", lambda: assist.refit()),
                         ("Σβήσε όλη τη διάταξη", lambda: assist.delete_layout())):
            if text is None:
                menu.addSeparator()
                continue
            action = QAction(text, window)
            action.triggered.connect(lambda _=False, f=fn: f())
            menu.addAction(action)
    return assist
