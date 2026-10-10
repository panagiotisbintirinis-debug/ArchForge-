"""«Γραμμή ντουλαπιών» in the plan: point at a wall, see the run, apply it with one undo.

Mouse only: hover a wall face (it lights up with its length), double click
= the whole face, or click two points on it = the stretch between them.
The run shows as a ghost (cabinets, fillers in orange, worktop, sink and
hob) until «Εφαρμογή» (Enter).  Right click on the ghost: sink here / hob
here / wall units / cornice / corner type.  Delete or Esc throws the ghost
away.  After applying, a click on a cabinet and its mouse menu (or the
Ιδιότητες) change its width: the run re-flows and the filler follows.

Only UI state lives here; the Document changes through
``kitchen.cabinet_run`` commands on the window's CommandStack.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

TOOL = "layout_cabinet_run"
HINT = ("Γραμμή ντουλαπιών: διπλό κλικ σε τοίχο = όλος ο τοίχος · ή κλικ σε δύο σημεία του τοίχου = το κομμάτι ανάμεσα · "
        "Enter = Εφαρμογή · δεξί κλικ = επιλογές · Esc = τέλος")


def _label(view, text, x, y, color, bold=True):
    from PySide6.QtWidgets import QGraphicsTextItem
    item = view._scene.addText(text)
    item.setDefaultTextColor(color)
    if bold:
        f = item.font(); f.setBold(True); item.setFont(f)
    item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
    item.setPos(x, y)
    item.setZValue(60)
    return item


class CabinetRunTool:
    def __init__(self, window):
        self.w = window
        self.active = False
        self.first = None          # (x, y) of the first click on the face
        self.pick = None           # (x0, y0, x1, y1) of the proposal
        self.cursor = None         # (run, s, (x, y), runs)
        self.proposal = None
        self.options = {"wall_units": True, "cornice": False, "corner": "blind",
                        "worktop_material": "marble_thassos", "front_material": ""}

    @property
    def doc(self):
        return self.w.doc

    def status(self, text, ms=12000):
        self.w.statusBar().showMessage(text, ms)

    # ---------------------------------------------------------------- state
    def start(self):
        self.active = True
        self._reset()
        self.w._start_site_tool(TOOL, HINT)
        self._sync_panel()
        self.w.plan_view.redraw()

    def _reset(self):
        self.first, self.pick, self.proposal = None, None, None
        self.options.pop("sink_xy", None)
        self.options.pop("hob_xy", None)

    def propose(self, x0, y0, x1=None, y1=None):
        from archforge.kitchen.cabinet_run import plan_run
        self.pick = (x0, y0, x1, y1)
        self.proposal = plan_run(self.doc, x0, y0, x1, y1, self.options)
        if not self.proposal.entities:
            self.status("⚠ " + " · ".join(self.proposal.problems))
            self.proposal = None
        else:
            warn = (" · ⚠ " + " · ".join(self.proposal.problems)) if self.proposal.problems else ""
            self.status(f"{self.proposal.label}: {self.proposal.notes[0]}{warn} — Enter = Εφαρμογή · "
                        "δεξί κλικ = νεροχύτης/εστία εδώ, κρεμαστά, κορνίζα · Delete = σβήσιμο", 20000)
        self._sync_panel()
        self.w.plan_view.redraw()
        return self.proposal

    def again(self):
        if self.pick is not None:
            return self.propose(*self.pick)
        return None

    def set_option(self, key, value):
        self.options[key] = value
        if self.proposal is not None:
            self.again()
        else:
            # Nothing being proposed: the choice applies to the selected run (one undo).
            self.apply_to_selected(key, value)

    def place_here(self, role, xy):
        """«Νεροχύτης εδώ» / «Εστία εδώ» at a plan point (on the ghost)."""
        if self.proposal is None or xy is None:
            return None
        self.options[role + "_xy"] = [float(xy[0]), float(xy[1])]
        self.options[role] = True
        return self.again()

    def apply(self):
        if self.proposal is None:
            self.status("Δεν υπάρχει πρόταση — διπλό κλικ σε τοίχο ή δύο κλικ πάνω του")
            return None
        proposal = self.proposal
        self.w.stack.execute(proposal.command())
        self.doc.select([e.id for e in proposal.entities if e.params.get("run_id") == proposal.run_id])
        self._reset()
        self._refresh()
        n = sum(1 for e in proposal.entities if e.params.get("run_id") == proposal.run_id)
        self.status(f"✓ {proposal.label}: {n} κομμάτια — επιλεγμένα όλα · δεξί κλικ σε ντουλάπι = άλλο πλάτος · "
                    "Ctrl+Z = αναίρεση · συνέχισε σε άλλον τοίχο ή Esc", 20000)
        return proposal

    def discard(self):
        if self.proposal is None and self.first is None:
            return False
        self._reset()
        self._sync_panel()
        self.w.plan_view.redraw()
        self.status("Η πρόταση σβήστηκε — διάλεξε άλλον τοίχο · Esc = τέλος", 8000)
        return True

    def cancel(self):
        had = self.discard()
        self.active = False
        if str(self.w.plan_view.controller.tool) == TOOL:
            self.w.plan_view.controller.set_tool("select")
        self._sync_panel()
        return had

    def _refresh(self):
        self.w._redraw_views(all_views=True)
        for name in ("_refresh_project_tree", "refresh_inspector", "_schedule_assistant_refresh"):
            fn = getattr(self.w, name, None)
            if fn is not None:
                fn()
        self._sync_panel()

    # ---------------------------------------------------------------- applied runs
    def selected_run(self):
        for eid in self.doc.selection:
            e = self.doc.entities.get(eid)
            if e is not None and e.params.get("run_id"):
                return e.params["run_id"]
        return None

    def set_width(self, entity_id, width):
        from archforge.kitchen.cabinet_run import fmt_cm, reflow_width
        try:
            command = reflow_width(self.doc, entity_id, float(width))
        except ValueError as exc:
            self.status(f"⚠ {exc}")
            return None
        self.w.stack.execute(command)
        if entity_id in self.doc.entities:
            self.doc.select([entity_id])
        self._refresh()
        self.status(f"✓ Πλάτος {fmt_cm(float(width))} cm — η γραμμή προσαρμόστηκε, το συμπλήρωμα ακολουθεί · Ctrl+Z = αναίρεση")
        return command

    def apply_to_selected(self, key, value):
        from archforge.kitchen.cabinet_run import set_run_option
        rid = self.selected_run()
        if rid is None or key not in ("cornice", "worktop_material", "front_material", "wall_units", "corner"):
            return None
        if key in ("wall_units", "corner"):
            return None                         # these shape the run: they apply to the next one
        command = set_run_option(self.doc, rid, key, value)
        if command is not None:
            self.w.stack.execute(command)
            self._refresh()
            self.status("✓ Η γραμμή άλλαξε — Ctrl+Z = αναίρεση", 6000)
        return command

    def delete_run(self, run_id=None):
        from archforge.kitchen.cabinet_run import delete_run_command
        rid = run_id or self.selected_run()
        command = delete_run_command(self.doc, rid) if rid else None
        if command is None:
            self.status("Επίλεξε ένα ντουλάπι της γραμμής")
            return None
        self.w.stack.execute(command)
        self.doc.select([])
        self._refresh()
        self.status("Η γραμμή ντουλαπιών σβήστηκε (ένα undo)", 8000)
        return command

    # ---------------------------------------------------------------- mouse
    def handle(self, view, kind, event):
        from archforge.kitchen.cabinet_run import runs_at, snap
        if kind == "key":
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.apply()
                return True
            if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                return self.discard()
            if key == Qt.Key.Key_Escape:
                if not self.discard():
                    self.cancel()
                    self.w._set_active_tool("select")
                return True
            return False
        if kind == "context":
            return False                          # the mouse menu (marking_entries) opens
        p = view.mapToScene(event.position().toPoint())
        x, y = p.x(), p.y()
        if kind == "move":
            runs, _room = runs_at(self.doc, x, y)
            hit = snap(runs, x, y) if runs else None
            self.cursor = (hit[0], hit[1], hit[2], runs) if hit else None
            view.redraw()
            return True
        if kind == "release":
            return True
        if kind == "dclick":
            self.first = None
            self.propose(x, y)
            return True
        if kind != "press" or event.button() != Qt.MouseButton.LeftButton:
            return False
        runs, _room = runs_at(self.doc, x, y)
        hit = snap(runs, x, y) if runs else None
        if hit is None:
            self.status("Κλικ πάνω στην παρειά ενός τοίχου (μέσα στον χώρο)")
            return True
        if self.first is None:
            self.first = (x, y)
            self.proposal = None
            self.status("Αρχή — κλικ στο τέλος του κομματιού πάνω στον ίδιο τοίχο · διπλό κλικ = όλος ο τοίχος")
        else:
            x0, y0 = self.first
            self.first = None
            if math.hypot(x - x0, y - y0) < 0.30:
                self.propose(x0, y0)
            else:
                self.propose(x0, y0, x, y)
        self._sync_panel()
        view.redraw()
        return True

    # ---------------------------------------------------------------- drawing
    def paint(self, view):
        from archforge.kitchen.cabinet_run import fmt_m
        if str(view.controller.tool) == TOOL and self.cursor is not None and self.proposal is None:
            i, s, (cx, cy), runs = self.cursor
            r = runs[i]
            orange = QColor(230, 120, 20)
            pen = QPen(orange); pen.setWidthF(.07)
            a, b = r.point(0.0, 0.04), r.point(r.length, 0.04)
            if self.first is not None:
                from archforge.kitchen.cabinet_run import snap as _snap
                h0 = _snap(runs, *self.first)
                if h0 and h0[0] == i:
                    a, b = r.point(min(h0[1], s), 0.04), r.point(max(h0[1], s), 0.04)
            view._scene.addLine(a[0], a[1], b[0], b[1], pen).setZValue(45)
            mx, my = (a[0] + b[0]) / 2 + r.n[0] * 0.5, (a[1] + b[1]) / 2 + r.n[1] * 0.5
            _label(view, fmt_m(math.hypot(b[0] - a[0], b[1] - a[1])), mx, my, orange)
            dot = QPen(orange); dot.setWidthF(.02)
            view._scene.addEllipse(cx - .09, cy - .09, .18, .18, dot, QBrush(orange)).setZValue(46)
        if self.first is not None:
            x, y = self.first
            pen = QPen(QColor(230, 120, 20)); pen.setWidthF(.02)
            view._scene.addEllipse(x - .1, y - .1, .2, .2, pen, QBrush(QColor(230, 120, 20))).setZValue(46)
        if self.proposal is not None:
            self._paint_ghost(view)

    def _paint_ghost(self, view):
        from archforge.kitchen.cabinet_run import plan_primitives, proposal_ghost
        fills = {"base": QColor(70, 170, 110, 70), "wall": QColor(0, 0, 0, 0),
                 "filler-base": QColor(240, 150, 40, 170), "filler-wall": QColor(240, 150, 40, 90)}
        for kind, pts, closed in proposal_ghost(self.proposal):
            if len(pts) < 2:
                continue
            pen = QPen(QColor(200, 110, 20) if kind.startswith("filler") else QColor(30, 120, 70))
            pen.setWidthF(.012 if kind in ("front", "wall", "filler-wall") else .02)
            if kind in ("wall", "filler-wall"):
                pen.setStyle(Qt.PenStyle.DashLine)
            if closed:
                item = view._scene.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]), pen,
                                              QBrush(fills.get(kind, QColor(0, 0, 0, 0))))
            else:
                path = QPainterPath(QPointF(*pts[0]))
                for q in pts[1:]:
                    path.lineTo(QPointF(*q))
                item = view._scene.addPath(path, pen)
            item.setZValue(35)
        fake = SimpleNamespace(entities={e.id: e for e in self.proposal.entities}, work_plane=self.doc.work_plane)
        for role, pts, closed in plan_primitives(fake):
            pen = QPen(QColor(20, 90, 50)); pen.setWidthF(.016 if role == "worktop" else .009)
            if role == "hood":
                pen.setStyle(Qt.PenStyle.DashLine)
            path = QPainterPath(QPointF(*pts[0]))
            for q in list(pts[1:]) + ([pts[0]] if closed else []):
                path.lineTo(QPointF(*q))
            view._scene.addPath(path, pen).setZValue(36)
        # The label sits in front of the run, inside the room.
        seg = self.proposal.segments[0] if self.proposal.segments else None
        if seg is not None:
            from archforge.kitchen.cabinet_run import frame_point
            frame, lo, hi, _layer = seg
            x, y = frame_point(frame, (lo + hi) / 2, 1.1)
            text = self.proposal.label + ("  ⚠" if self.proposal.problems else "") + "  —  Enter = Εφαρμογή · δεξί κλικ = επιλογές"
            _label(view, text, x - 1.4, y, QColor(20, 90, 50))

    # ---------------------------------------------------------------- panel
    def build_panel(self, parent):
        from archforge.kitchen.cabinet_run import CORNERS, FRONT_MATERIALS, WORKTOP_MATERIALS
        from archforge.rendering.materials import MATERIAL_PRESETS
        box = QGroupBox("Γραμμή ντουλαπιών", parent)
        lay = QVBoxLayout(box)
        start = QPushButton("Γραμμή ντουλαπιών σε τοίχο…", box)
        start.setToolTip("Διπλό κλικ σε τοίχο = γέμισμα όλου του τοίχου· δύο κλικ = κομμάτι του")
        start.clicked.connect(self.start)
        lay.addWidget(start)
        row = QHBoxLayout()
        self.wall_units = QCheckBox("Κρεμαστά", box); self.wall_units.setChecked(True)
        self.wall_units.toggled.connect(lambda v: self.set_option("wall_units", bool(v)))
        self.cornice = QCheckBox("Κορνίζα", box)
        self.cornice.toggled.connect(lambda v: self.set_option("cornice", bool(v)))
        self.corner = QComboBox(box)
        for k, t in CORNERS.items():
            self.corner.addItem(t, k)
        self.corner.currentIndexChanged.connect(lambda _i: self.set_option("corner", self.corner.currentData()))
        for wdg in (self.wall_units, self.cornice, self.corner):
            row.addWidget(wdg)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Πάγκος", box))
        self.worktop = QComboBox(box)
        for k in WORKTOP_MATERIALS:
            self.worktop.addItem(MATERIAL_PRESETS[k]["name"], k)
        self.worktop.currentIndexChanged.connect(lambda _i: self.set_option("worktop_material", self.worktop.currentData()))
        row.addWidget(self.worktop)
        row.addWidget(QLabel("Προσόψεις", box))
        self.fronts = QComboBox(box)
        for k in FRONT_MATERIALS:
            self.fronts.addItem(MATERIAL_PRESETS[k]["name"] if k else "Λευκές (βασικές)", k)
        self.fronts.currentIndexChanged.connect(lambda _i: self.set_option("front_material", self.fronts.currentData()))
        row.addWidget(self.fronts)
        lay.addLayout(row)
        self.info = QLabel(HINT, box)
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        row = QHBoxLayout()
        self.apply_button = QPushButton("✓ Εφαρμογή γραμμής", box); self.apply_button.clicked.connect(self.apply)
        self.discard_button = QPushButton("Σβήσε πρόταση", box); self.discard_button.clicked.connect(self.discard)
        delete = QPushButton("Σβήσε όλη τη γραμμή", box); delete.clicked.connect(lambda: self.delete_run())
        for b in (self.apply_button, self.discard_button, delete):
            row.addWidget(b)
        lay.addLayout(row)
        self.box = box
        self._sync_panel()
        return box

    def _sync_panel(self):
        if not hasattr(self, "info"):
            return
        p = self.proposal
        self.apply_button.setEnabled(p is not None)
        self.discard_button.setEnabled(p is not None or self.first is not None)
        if p is None:
            self.info.setText(HINT)
            return
        lines = [f"<b>{p.label}</b>"] + [f"⚠ {t}" for t in p.problems] + [f"• {t}" for t in p.notes[:5]]
        from archforge.kitchen.cabinet_run import SOURCE
        lines.append(f"<i>{SOURCE}</i>")
        self.info.setText("<br>".join(lines))


# ---------------------------------------------------------------- mouse menu
def marking_entries(window):
    from archforge.ui.marking_menu import _e
    t = window._cabinet_run
    o = t.options
    entries = [_e("mm:krun:apply", "✓ Εφαρμογή")]
    if t.proposal is not None:
        entries += [_e("mm:krun:sink_here", "Νεροχύτης εδώ"), _e("mm:krun:hob_here", "Εστία εδώ")]
    entries += [_e("mm:krun:wall_units", "Κρεμαστά", checked=bool(o.get("wall_units"))),
                _e("mm:krun:cornice", "Κορνίζα", checked=bool(o.get("cornice"))),
                _e("mm:krun:corner_blind", "Γωνία: τυφλό", checked=o.get("corner") == "blind"),
                _e("mm:krun:corner_L", "Γωνία: Γ 90×90", checked=o.get("corner") == "L"),
                _e("mm:krun:discard", "✕ Σβήσε πρόταση", danger=True),
                _e("mm:krun:end", "Τέλος", "panel")]
    center = t.proposal.label if t.proposal is not None else "Γραμμή ντουλαπιών"
    return {"center": center, "entries": entries, "wheel": None}


def entity_entries(window, entity):
    """Mouse-menu entries for a cabinet of a run: its width (standard), delete the whole run."""
    from archforge.kitchen.cabinet_run import STANDARD_WIDTHS
    from archforge.ui.marking_menu import _e
    p = entity.params
    out = []
    if p.get("cabinet_type") not in ("filler", "corner", "corner_blind"):
        w = float(p["width"])
        out += [_e(f"mm:krun:width_{int(round(v * 100))}", f"Πλάτος {v * 100:.0f} cm", "panel", checked=abs(v - w) < 1e-6)
                for v in STANDARD_WIDTHS]
    out.append(_e("mm:krun:delete_run", "Διαγραφή όλης της γραμμής", "panel", danger=True))
    return out


def run(window, arg, entity_id=None, plan_xy=None):
    t = window._cabinet_run
    if arg == "start":
        t.start()
    elif arg == "apply":
        t.apply()
    elif arg in ("sink_here", "hob_here"):
        t.place_here(arg.split("_")[0], plan_xy)
    elif arg in ("wall_units", "cornice"):
        t.set_option(arg, not bool(t.options.get(arg)))
    elif arg.startswith("corner_"):
        t.set_option("corner", arg[len("corner_"):])
    elif arg == "discard":
        t.discard()
    elif arg == "end":
        t.cancel()
        window._set_active_tool("select")
    elif arg.startswith("width_") and entity_id:
        t.set_width(entity_id, int(arg[len("width_"):]) / 100.0)
    elif arg == "delete_run" and entity_id in window.doc.entities:
        t.delete_run(window.doc.get(entity_id).params.get("run_id"))


def install_cabinet_run(window):
    """Panel in the Βοηθός dock, an entry in the Κουζίνα menu; the plan overlay goes through LayoutAssist."""
    from PySide6.QtGui import QAction
    tool = CabinetRunTool(window)
    window._cabinet_run = tool
    dock = getattr(window, "_assistant_dock", None)
    if dock is not None and dock.widget() is not None and dock.widget().layout() is not None:
        dock.widget().layout().insertWidget(2, tool.build_panel(dock.widget()))
    menus = getattr(window, "_mockup_menus", {}) or {}
    menu = menus.get("Κουζίνα")
    if menu is not None:
        menu.addSeparator()
        for text, fn in (("Γραμμή ντουλαπιών σε τοίχο…", tool.start),
                         ("Σβήσε όλη τη γραμμή ντουλαπιών", lambda: tool.delete_run())):
            action = QAction(text, window)
            action.triggered.connect(lambda _=False, f=fn: f())
            menu.addAction(action)
    return tool
