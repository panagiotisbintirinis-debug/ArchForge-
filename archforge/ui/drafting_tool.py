"""CAD ▸ Σχεδίαση 2D: γραμμή, πολυγραμμή, ορθογώνιο, πολύγωνο, κύκλος, τόξο, κείμενο στην κάτοψη (06/11).

Κάθε σχήμα = ένα στοιχείο ``drafting`` (``architecture/drafting.py``), μία αναίρεση. Ίδια συμπεριφορά με τη Μεζούρα:

* κλικ = σημείο· οι γωνίες και οι παρειές των τοίχων και τα άκρα / κέντρα των σχεδίων τραβούν το ποντίκι
  (Shift = χωρίς έλξη)· **Ctrl** = ορθή γωνία (0° / 90°) από το προηγούμενο σημείο·
* μετά το πρώτο σημείο: **ψηφία** = μήκος προς το ποντίκι (``3``, ``3,20``, ``320 cm``), **Tab** = γωνία σε μοίρες,
  **Enter** = το σημείο (με κενό πεδίο: τέλος πολυγραμμής / πολυγώνου)·
* Γραμμή: κάθε κλικ μια γραμμή από το προηγούμενο σημείο (συνεχίζει, όπως στο CAD) · Πολυγραμμή / Πολύγωνο: κλικ …,
  Enter / διπλό κλικ = τέλος · Ορθογώνιο: δύο γωνίες · Κύκλος: κέντρο, σημείο της περιφέρειας · Τόξο: αρχή, σημείο
  του τόξου, τέλος · Κείμενο: κλικ → το κείμενο·
* Esc / δεξί κλικ: τέλος της εντολής (μια ανοιχτή πολυγραμμή με ≥ 2 σημεία μπαίνει πρώτα).
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QPen
from PySide6.QtWidgets import QGraphicsTextItem, QMenu

from archforge.architecture import drafting as DR

GREEN = QColor(40, 150, 70)
NEED = {"line": 2, "rectangle": 2, "circle": 2, "arc": 3, "text": 1}
LABELS = {"line": "Γραμμή", "polyline": "Πολυγραμμή", "rectangle": "Ορθογώνιο", "polygon": "Πολύγωνο",
          "circle": "Κύκλος", "arc": "Τόξο (3 σημεία)", "text": "Κείμενο"}
HINTS = {"line": "κλικ στην αρχή · κλικ στα επόμενα σημεία (συνεχίζει)",
         "polyline": "κλικ στα σημεία · Enter / διπλό κλικ = τέλος",
         "rectangle": "κλικ στη μία γωνία · κλικ στην απέναντι",
         "polygon": "κλικ στις κορυφές · Enter / διπλό κλικ = κλείσιμο",
         "circle": "κλικ στο κέντρο · κλικ στην περιφέρεια (ή ακτίνα με το πληκτρολόγιο)",
         "arc": "κλικ στην αρχή · κλικ σε σημείο του τόξου · κλικ στο τέλος",
         "text": "κλικ εκεί που ξεκινά το κείμενο"}
NUMBER_CHARS = set("0123456789.,")
UNIT_CHARS = set("cmμ ")


class DraftingTool:
    def __init__(self, window):
        self.w = window
        self.mode = None            # None = off
        self.points = []
        self.cursor = None
        self.kind = ""
        self.typed = {"length": "", "angle": "", "field": "length"}
        self.style = {"style": "solid", "weight": 0.25, "hatch": "none", "height": DR.DEFAULT_TEXT_HEIGHT}

    @property
    def active(self):
        return self.mode is not None

    # ------------------------------------------------------------ start / stop / place
    def start(self, mode):
        if mode not in LABELS:
            raise ValueError(mode)
        self.mode, self.points, self.cursor = mode, [], None
        self._clear_typed()
        self.w.statusBar().showMessage(f"{LABELS[mode]}: {HINTS[mode]} · Shift = χωρίς έλξη · Ctrl = ορθή · "
                                       "ψηφία = μήκος, Tab = γωνία · Esc = τέλος", 20000)
        self.w.plan_view.redraw()

    def cancel(self):
        had = self.mode is not None
        if had and self.mode == "polyline" and len(self.points) >= 2:
            self.finish()
        self.mode, self.points, self.cursor = None, [], None
        self._clear_typed()
        if had:
            self.w.plan_view.redraw()
        return had

    def _z(self):
        return float(self.w.doc.work_plane.origin[2])

    def add(self, entity):
        """One drafting entity, one undo; True if added."""
        from archforge.core.commands import AddEntity
        try:
            self.w.stack.execute(AddEntity(entity))
        except (ValueError, KeyError) as exc:
            self.w.statusBar().showMessage(f"⚠ {LABELS.get(self.mode, 'Σχέδιο')}: {exc}", 8000)
            return False
        self.w._redraw_views(all_views=True)
        self.w.statusBar().showMessage(f"{DR.describe(entity.params)} · Ctrl+Z = αναίρεση · Esc = τέλος", 8000)
        return True

    def _line_style(self, closed=False):
        out = {"style": self.style["style"], "weight": self.style["weight"]}
        if closed:
            out["hatch"] = self.style["hatch"]
        return out

    def finish(self):
        """Close a polyline / polygon (Enter, double click)."""
        z, pts = self._z(), list(self.points)
        if self.mode == "polyline" and len(pts) >= 2:
            self.add(DR.entity("polyline", z, points=pts, **self._line_style()))
        elif self.mode == "polygon" and len(pts) >= 3:
            self.add(DR.entity("polygon", z, points=pts, **self._line_style(True)))
        else:
            return False
        self.points = []
        return True

    def click(self, x, y):
        """A point of the active command (also for tests and scripts)."""
        z = self._z()
        self.points.append((float(x), float(y)))
        pts, mode = self.points, self.mode
        try:
            if mode == "line" and len(pts) == 2:
                if self.add(DR.entity("line", z, points=pts, **self._line_style())):
                    self.points = [pts[1]]                                    # continues from the end
                else:
                    self.points = [pts[0]]
            elif mode == "rectangle" and len(pts) == 2:
                self.add(DR.rectangle(pts[0], pts[1], z, **self._line_style(True)))
                self.points = []
            elif mode == "circle" and len(pts) == 2:
                self.add(DR.entity("circle", z, cx=pts[0][0], cy=pts[0][1], r=math.dist(*pts), **self._line_style(True)))
                self.points = []
            elif mode == "arc" and len(pts) == 3:
                cx, cy, r, a0, a1 = DR.arc_three_points(*pts)
                self.add(DR.entity("arc", z, cx=cx, cy=cy, r=r, a0=a0, a1=a1, **self._line_style()))
                self.points = []
            elif mode == "text":
                self.points = []
                return self._ask_text(x, y)
        except ValueError as exc:
            self.w.statusBar().showMessage(f"⚠ {LABELS[mode]}: {exc}", 8000)
            self.points = pts[:-1]
        return True

    def _ask_text(self, x, y, text=None):
        if text is None:
            from PySide6.QtWidgets import QInputDialog
            text, ok = QInputDialog.getText(self.w, "Κείμενο", "Κείμενο (ύψος γραμμάτων "
                                            f"{self.style['height'] * 100:.0f} cm):")
            if not ok:
                return False
        if not str(text).strip():
            return False
        return self.add(DR.entity("text", self._z(), x=x, y=y, text=text, height=self.style["height"]))

    # ------------------------------------------------------------ typed length / angle
    def _clear_typed(self):
        self.typed = {"length": "", "angle": "", "field": "length"}

    def typed_point(self):
        """The point the typed length / angle give from the last point (towards the mouse without an angle)."""
        from archforge.core.units import parse_edit_length
        if not self.points or not self.typed["length"].strip():
            return None
        length = parse_edit_length(self.typed["length"], default="m")
        a = self.points[-1]
        if self.typed["angle"].strip():
            ang = math.radians(float(self.typed["angle"].replace(",", ".")))
        elif self.cursor is not None and math.dist(a, self.cursor) > 1e-6:
            ang = math.atan2(self.cursor[1] - a[1], self.cursor[0] - a[0])
        else:
            ang = 0.0
        if self.mode == "circle":
            return a[0] + length, a[1]
        return a[0] + length * math.cos(ang), a[1] + length * math.sin(ang)

    def _key(self, event):
        k, t = event.key(), event.text()
        if k == Qt.Key.Key_Escape:
            if self.typed["length"] or self.typed["angle"]:
                self._clear_typed(); return True
            self.cancel(); return True
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.typed["length"].strip():
                try:
                    q = self.typed_point()
                except ValueError as exc:
                    self.w.statusBar().showMessage(f"⚠ {exc}", 6000)
                    return True
                self._clear_typed()
                if q is not None:
                    self.click(*q)
                return True
            self.finish()
            return True
        if not self.points:
            return False
        if k == Qt.Key.Key_Tab:
            self.typed["field"] = "angle" if self.typed["field"] == "length" else "length"
            return True
        if k == Qt.Key.Key_Backspace:
            f = self.typed["field"]; self.typed[f] = self.typed[f][:-1]; return True
        if t and (t in NUMBER_CHARS or (t in UNIT_CHARS and self.typed["field"] == "length") or (t == "-" and self.typed["field"] == "angle")):
            self.typed[self.typed["field"]] += t
            return True
        return False

    # ------------------------------------------------------------ mouse
    def snap(self, x, y, tolerance):
        """Ends, middles and centres of drawn shapes, then the corners / faces of the walls (the tape's pull)."""
        from archforge.architecture import dimensions as D
        best = None
        z = self._z()
        for e in self.w.doc.entities.values():
            if e.kind != "drafting" or not e.visible or abs(float(e.params.get("level_z", 0.0)) - z) > 1e-5:
                continue
            p = e.params
            cands = []
            if p["shape"] in ("circle", "arc"):
                cands.append((p["cx"], p["cy"]))
            if p["shape"] == "text":
                cands.append((p["x"], p["y"]))
            else:
                pts, closed = DR.outline(p)
                ends = pts if p["shape"] in ("line", "polyline", "polygon") else [pts[0], pts[-1]] if p["shape"] == "arc" else []
                cands += ends
                if p["shape"] in ("line", "polyline", "polygon"):
                    seq = pts + (pts[:1] if closed else [])
                    cands += [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(seq, seq[1:])]
            for q in cands:
                d = math.hypot(q[0] - x, q[1] - y)
                if d <= tolerance and (best is None or d < best[0]):
                    best = (d, q)
        if best is not None:
            return best[1][0], best[1][1], "corner"
        return D.tape_snap(self.w.doc, x, y, tolerance, None)

    def _xy(self, view, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        p = view._scene_to_plane(pos)
        x, y = float(p.a), float(p.b)
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier and self.points:
            a = self.points[-1]
            if abs(x - a[0]) >= abs(y - a[1]):
                y = a[1]
            else:
                x = a[0]
            return x, y, "ortho"
        if mods & Qt.KeyboardModifier.ShiftModifier or not view.controller.snap_enabled:
            return x, y, ""
        tol = max(float(view.controller.snap_tolerance), 9 / max(1.0, abs(view.transform().m11())))
        return self.snap(x, y, min(tol, 0.25))

    def handle(self, view, kind, event):
        if self.mode is None:
            return False
        if kind == "key":
            return self._key(event)
        if kind == "context":
            self.cancel(); return True
        if kind not in ("press", "move", "release", "dclick"):
            return False
        x, y, self.kind = self._xy(view, event)
        self.cursor = (x, y)
        if kind == "dclick" and self.mode in ("polyline", "polygon"):
            if self.points and math.dist(self.points[-1], (x, y)) < 0.01:
                self.points = self.points[:-1] + [self.points[-1]]
            self.finish()
        elif kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            if not self.points or math.dist(self.points[-1], (x, y)) > 0.005:
                self._clear_typed()
                self.click(x, y)
        view.redraw()
        return True

    # ------------------------------------------------------------ preview
    def paint(self, view):
        if self.mode is None:
            return
        pen = QPen(GREEN); pen.setCosmetic(True); pen.setWidthF(1.5)
        scale = max(1.0, abs(view.transform().m11()))
        if self.cursor is not None and self.kind in ("corner", "face"):
            r = 6 / scale
            x, y = self.cursor
            view._scene.addRect(x - r, y - r, 2 * r, 2 * r, pen).setZValue(52)
        if not self.points or self.cursor is None:
            return
        try:
            target = self.typed_point() or self.cursor
        except ValueError:
            target = self.cursor
        pts = self.points + [target]
        lines = []
        if self.mode in ("line", "polyline", "polygon"):
            lines = list(zip(pts, pts[1:]))
            if self.mode == "polygon" and len(pts) >= 3:
                lines.append((pts[-1], pts[0]))
        elif self.mode == "rectangle":
            (x0, y0), (x1, y1) = pts[0], pts[1]
            q = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            lines = list(zip(q, q[1:] + q[:1]))
        elif self.mode == "circle":
            r = math.dist(pts[0], pts[1])
            if r > 1e-6:
                q = DR.arc_points(pts[0][0], pts[0][1], r, 0, 360)
                lines = list(zip(q, q[1:]))
        elif self.mode == "arc":
            if len(pts) == 2:
                lines = [(pts[0], pts[1])]
            else:
                try:
                    q = DR.arc_points(*DR.arc_three_points(*pts))
                    lines = list(zip(q, q[1:]))
                except ValueError:
                    lines = [(pts[0], pts[1]), (pts[1], pts[2])]
        for a, b in lines:
            view._scene.addLine(a[0], a[1], b[0], b[1], pen).setZValue(51)
        a = self.points[-1]
        if self.mode == "circle":
            text = f"r {math.dist(pts[0], target):.2f} m"
        else:
            ang = math.degrees(math.atan2(target[1] - a[1], target[0] - a[0])) % 360
            text = f"{math.dist(a, target):.2f} m · {ang:.1f}°"
        if self.typed["length"] or self.typed["angle"]:
            text += f"   ⌨ μήκος {self.typed['length'] or '—'} · γωνία {self.typed['angle'] or '—'}" \
                    + ("  [Tab]" if self.typed["field"] == "length" else "  [γωνία]")
        item = view._scene.addText("")
        item.setHtml(f'<span style="background-color:#ffffff; color:{GREEN.name()}; font-weight:600">&nbsp;'
                     f'{text.replace(".", ",")}&nbsp;</span>')
        item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        item.setPos(target[0], target[1])
        item.setZValue(53)


# ------------------------------------------------------------------ menu, properties
def set_style(window, **kw):
    tool = window._drafting_tool
    tool.style.update(kw)
    window.statusBar().showMessage("Σχέδιο 2D: γραμμή " + DR.STYLES[tool.style["style"]] + f" {tool.style['weight']:g} mm"
                                   + f" · γέμισμα {DR.HATCHES[tool.style['hatch']]} · κείμενο "
                                   + f"{tool.style['height'] * 100:.0f} cm".replace(".", ","), 6000)


def edit_selected(window, key, value):
    """Line style / pen / hatch / text height of the selected drafting shapes — one undo."""
    from archforge.core.commands import CompositeCommand, UpdateEntity
    doc = window.doc
    cmds = []
    for eid in doc.selection or ():
        e = doc.get(eid)
        if e is None or e.kind != "drafting":
            continue
        if key == "hatch" and e.params["shape"] not in ("polygon", "circle"):
            continue
        if key == "height" and e.params["shape"] != "text":
            continue
        if key in ("style", "weight") and e.params["shape"] == "text":
            continue
        cmds.append(UpdateEntity(eid, {key: value}))
    if cmds:
        window.stack.execute(CompositeCommand(cmds, label="Σχέδιο 2D: ιδιότητες"))
        window._redraw_views(all_views=True)
    return len(cmds)


def menu(window):
    """CAD ▸ Σχεδίαση 2D."""
    m = QMenu("Σχεδίαση 2D", window)
    actions = {}
    for mode, label in LABELS.items():
        a = QAction(label, window)
        a.triggered.connect(lambda _=False, md=mode: window._drafting_tool.start(md))
        m.addAction(a); actions[mode] = a
    m.addSeparator()
    style = m.addMenu("Τύπος γραμμής")
    for k, label in DR.STYLES.items():
        a = style.addAction(label)
        a.triggered.connect(lambda _=False, v=k: (set_style(window, style=v), edit_selected(window, "style", v)))
    weight = m.addMenu("Πάχος γραμμής")
    for v in DR.WEIGHTS:
        a = weight.addAction(f"{v:g} mm".replace(".", ","))
        a.triggered.connect(lambda _=False, v=v: (set_style(window, weight=v), edit_selected(window, "weight", v)))
    hatch = m.addMenu("Γέμισμα (κλειστά σχήματα)")
    for k, label in DR.HATCHES.items():
        a = hatch.addAction(label)
        a.triggered.connect(lambda _=False, v=k: (set_style(window, hatch=v), edit_selected(window, "hatch", v)))
    height = m.addMenu("Ύψος κειμένου")
    for v in (0.10, 0.15, 0.20, 0.25, 0.35, 0.50, 1.0):
        a = height.addAction(f"{v * 100:.0f} cm")
        a.triggered.connect(lambda _=False, v=v: (set_style(window, height=v), edit_selected(window, "height", v)))
    window._main_actions += list(actions.values())
    window._drafting_actions = actions
    return m


def install(window):
    tool = DraftingTool(window)
    window._drafting_tool = tool
    window.plan_view.drafting_tool = tool
    esc = getattr(window, "_escape_shortcut", None)
    if esc is not None:
        esc.activated.connect(tool.cancel)
    return tool
