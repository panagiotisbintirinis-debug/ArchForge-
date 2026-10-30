"""«Τοίχος ▾ ▸ Καμπύλος τοίχος»: three clicks in the plan — start, end, a point on the arc — with the arc live under
the cursor (radius, length, pieces), then the walls (architecture/curved_wall.py), one undo.  The tool stays on for
the next arc, which may start where the last one ended; Esc / «✕» ends it.  The wall kind chosen in «Τοίχος ▾»
(glass, a wall type) applies, as for straight walls.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QGraphicsTextItem, QHBoxLayout, QLabel, QPushButton, QSpinBox

BLUE = QColor(30, 110, 200)
STEPS = ("αρχή", "τέλος", "σημείο πάνω στο τόξο")


class CurvedWallTool:
    def __init__(self, window):
        self.window = window
        self.active = False
        self.points = []
        self.cursor = None
        self.pieces = 0                  # 0 = automatic (each piece within 1 cm of the circle)
        self.bar = None

    def start(self):
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
        self.active, self.points, self.cursor = True, [], None
        self._show_bar(); self._status()
        w.plan_view.setFocus(); w.plan_view.redraw()

    def stop(self):
        self.active, self.points, self.cursor = False, [], None
        if self.bar is not None:
            self.bar.hide()
        self.window.statusBar().showMessage("Καμπύλος τοίχος: τέλος", 3000)
        self.window.plan_view.redraw()

    def arc(self, m=None):
        from archforge.architecture.curved_wall import arc_through
        if len(self.points) < 2:
            return None
        try:
            return arc_through(self.points[0], self.points[1], m if m is not None else self.cursor)
        except (ValueError, TypeError):
            return None

    def place(self, a, b, m):
        """The arc's walls — one undo; the new wall ids, or None (and a message)."""
        from archforge.architecture.curved_wall import create_command, info
        w = self.window
        choice = getattr(w.plan_view.controller, 'wall_choice', None)
        try:
            command, walls = create_command(w.doc, a, b, m, self.pieces or None, choice)
            w.stack.execute(command)
        except (ValueError, RuntimeError, PermissionError) as exc:
            w.statusBar().showMessage(str(exc), 7000)
            return None
        w.doc.select([e.id for e in walls])
        w._redraw_views(all_views=True)
        w._refresh_project_tree()
        i = info(w.doc, walls[0])
        w.statusBar().showMessage(
            (f"Καμπύλος τοίχος R {i['r']:.2f} m · μήκος {i['length']:.2f} m · {i['n']} τμήματα (απόκλιση ≤ "
             f"{i['deviation'] * 100:.1f} cm) — ακτίνα/τμήματα στις Ιδιότητες · Ctrl+Z").replace('.', ','), 10000)
        return [e.id for e in walls]

    def _status(self):
        if not self.active:
            return
        text = f"Καμπύλος τοίχος: κλικ {len(self.points) + 1}/3 — {STEPS[len(self.points)]}"
        a = self.arc() if len(self.points) == 2 else None
        if a is not None:
            text += f" · R {a[2]:.2f} m · μήκος {abs(a[2] * a[4]):.2f} m".replace('.', ',')
        self.window.statusBar().showMessage(text + " · Backspace = πίσω · Esc = τέλος")
        if self.bar is not None:
            self.bar.title.setText(f"Καμπύλος τοίχος · {len(self.points) + 1}/3 {STEPS[len(self.points)]}")

    def _show_bar(self):
        view = self.window.plan_view
        if self.bar is None:
            bar = QFrame(view.viewport()); bar.setObjectName("curvedWallBar")
            bar.setStyleSheet("#curvedWallBar { background: rgba(255,255,255,0.96); border: 1px solid #2F6BD6;"
                              " border-radius: 8px; } QPushButton { padding: 3px 8px; }")
            row = QHBoxLayout(bar); row.setContentsMargins(8, 4, 8, 4); row.setSpacing(6)
            bar.title = QLabel(); bar.title.setStyleSheet("font-weight: 600; color: #1e6ec8;")
            bar.pieces = QSpinBox(); bar.pieces.setRange(0, 96); bar.pieces.setSpecialValueText("τμήματα: αυτόματα")
            bar.pieces.setPrefix("τμήματα: "); bar.pieces.setValue(self.pieces)
            bar.pieces.valueChanged.connect(lambda v: setattr(self, 'pieces', int(v)))
            back = QPushButton("↶ Σημείο"); back.clicked.connect(self.undo_point)
            stop = QPushButton("✕ Τέλος"); stop.clicked.connect(self.stop)
            for wdg in (bar.title, bar.pieces, back, stop):
                row.addWidget(wdg)
            for wdg in (back, stop):
                wdg.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.bar = bar
        self.bar.adjustSize(); self.bar.move(12, 12); self.bar.show(); self.bar.raise_()

    def undo_point(self):
        if self.points:
            self.points.pop()
        self._status(); self.window.plan_view.redraw()

    def click(self, x, y):
        self.points.append((float(x), float(y)))
        if len(self.points) == 3:
            a, b, m = self.points
            ids = self.place(a, b, m)
            self.points = [b] if ids else [a, b]      # the next arc may start where this one ended
        if self.active:
            self._status()

    # ------------------------------------------------------------------ plan events
    def _xy(self, view, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        from archforge.core.snapping import best_snap
        p = view._scene_to_plane(pos)
        x, y = float(p.a), float(p.b)
        if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) and view.controller.snap_enabled:
            try:
                sp = best_snap(view.doc, x, y, float(view.controller.snap_tolerance), float(view.controller.grid))
                if sp is not None:
                    return float(sp.x), float(sp.y)
            except Exception:                                   # noqa: BLE001 — snapping is a help, never a stop
                pass
            g = float(view.controller.grid)
            if g > 0:
                x, y = round(x / g) * g, round(y / g) * g
        return x, y

    def handle(self, view, kind, event):
        if not self.active:
            return False
        if kind == "key":
            if event.key() == Qt.Key.Key_Escape:
                self.stop(); return True
            if event.key() == Qt.Key.Key_Backspace:
                self.undo_point(); return True
            return False
        if kind == "context":
            self.stop(); return True
        if kind not in ("press", "move", "release"):
            return kind == "dclick"
        self.cursor = self._xy(view, event)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            self.click(*self.cursor)
        elif kind == "move" and len(self.points) == 2:
            self._status()
        view.redraw()
        return True

    def paint(self, view):
        if not self.active:
            return
        scene = view._scene
        k = 1 / max(1e-6, abs(view.transform().m11()))
        pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(2.0)
        if self.cursor is not None:
            x, y = self.cursor; r = 10 * k
            scene.addLine(x - r, y, x + r, y, pen).setZValue(46); scene.addLine(x, y - r, x, y + r, pen).setZValue(46)
        for px, py in self.points:
            s = 4 * k
            scene.addRect(px - s, py - s, 2 * s, 2 * s, pen).setZValue(47)
        if len(self.points) == 1 and self.cursor is not None:
            (ax, ay), (bx, by) = self.points[0], self.cursor
            dash = QPen(pen); dash.setStyle(Qt.PenStyle.DashLine)
            scene.addLine(ax, ay, bx, by, dash).setZValue(45)
        arc = self.arc() if len(self.points) == 2 else None
        if arc is not None:
            from archforge.architecture.curved_wall import pieces_for, points
            from archforge.architecture.curved_wall import wall_defaults
            n = self.pieces or pieces_for(arc[2], arc[4])
            t = wall_defaults(self.window.doc, getattr(view.controller, 'wall_choice', None))['thickness']
            cx, cy, r, t0, sw = arc
            outer = points(cx, cy, r + t / 2, t0, sw, n); inner = points(cx, cy, max(0.01, r - t / 2), t0, sw, n)
            fill = QColor(BLUE); fill.setAlpha(45)
            scene.addPolygon(QPolygonF([QPointF(*q) for q in outer + inner[::-1]]), pen, fill).setZValue(45)
            label = f"R {r:.2f} m · {abs(r * sw):.2f} m · {n} τμήματα".replace('.', ',')
            item = scene.addText("")
            item.setHtml(f'<span style="background-color:#ffffff; color:{BLUE.name()}; font-weight:600">&nbsp;{label}&nbsp;</span>')
            item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            item.setPos(self.cursor[0] + 10 * k, self.cursor[1]); item.setZValue(48)
        elif len(self.points) == 2:
            (ax, ay), (bx, by) = self.points
            scene.addLine(ax, ay, bx, by, pen).setZValue(45)


def install(window):
    tool = CurvedWallTool(window)
    window._curved_wall_tool = tool
    window.plan_view.curved_wall_tool = tool
    return tool


def inspector_rows(window, entity):
    """Ιδιότητες of a curved wall's piece: the arc as one wall — radius, pieces (rebuilt, one undo), select all."""
    from PySide6.QtWidgets import QDoubleSpinBox
    from archforge.architecture.curved_wall import info
    i = info(window.doc, entity)
    if i is None:
        return
    form = window.form
    form.addRow('Καμπύλος τοίχος', QLabel(
        (f"τόξο {i['sweep_deg']:.0f}° · μήκος {i['length']:.2f} m · {i['n']} ευθύγραμμα τμήματα "
         f"(απόκλιση από τον κύκλο ≤ {i['deviation'] * 100:.1f} cm)").replace('.', ',')))
    radius = QDoubleSpinBox(); radius.setDecimals(2); radius.setRange(0.2, 500.0); radius.setSingleStep(0.1)
    radius.setSuffix(' m'); radius.setValue(i['r'])
    radius.editingFinished.connect(lambda w=radius, c=i['id']: reshape(window, c, r=w.value()))
    form.addRow('Ακτίνα (τα άκρα μένουν)', radius)
    pieces = QSpinBox(); pieces.setRange(2, 96); pieces.setValue(i['n'])
    pieces.editingFinished.connect(lambda w=pieces, c=i['id']: reshape(window, c, n=w.value()))
    form.addRow('Τμήματα', pieces)
    pick = QPushButton(f"Επιλογή όλου του τόξου ({len(i['walls'])} τμήματα)")
    pick.clicked.connect(lambda _=False, ids=i['walls']: (window.doc.select(list(ids)), window._redraw_views(all_views=True)))
    form.addRow(pick)


def reshape(window, curve_id, r=None, n=None):
    from archforge.architecture.curved_wall import info, members, reshape_command
    walls = members(window.doc, curve_id)
    if not walls:
        return False
    old = info(window.doc, walls[0])
    if (r is None or abs(float(r) - old['r']) < 1e-6) and (n is None or int(n) == old['n']):
        return False
    try:
        command, new = reshape_command(window.doc, curve_id, r=r, n=n)
        window.stack.execute(command)
    except (ValueError, RuntimeError, PermissionError) as exc:
        window.statusBar().showMessage(str(exc), 7000)
        return False
    window.doc.select([new[0].id])
    window._redraw_views(all_views=True)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window.refresh_inspector)
    window.statusBar().showMessage("Καμπύλος τοίχος: άλλαξε · Ctrl+Z αναίρεση", 6000)
    return True
