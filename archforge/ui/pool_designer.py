"""Σχεδιασμός πισίνας (ιδιοκτήτης 07/11): «η σχεδίαση πρέπει να γίνεται στον ίδιο τον πίνακα σχεδιασμού της πισίνας
και μετά να τοποθετείται στο 3D … συγχρόνως μια μινιατούρα του 3D, τη στιγμή που το σχεδιάζουμε να φαίνεται στη
μινιατούρα ο σχεδιασμός, για να έχουμε ρεφερένς της σύνδεσης στον χώρο».

Ένα παράθυρο, πρώτα σχεδιάζεις και μετά τοποθετείς:

* **Σχήμα** (αριστερά): ορθογώνιο με διαστάσεις, ελεύθερο (κλικ στις γωνίες, γωνία / καμπύλη R ανά γωνία, όπως το
  «Σχήμα πισίνας» της κάτοψης) ή **από κλειστή γραμμή του σχεδίου 2D** (πολύγωνο, κύκλος, κλειστή πολυγραμμή).
  Μήκη πλευρών πάνω στο σχήμα.
* **Τομή** (δεξιά): κατά μήκος — χείλος, νερό, πυθμένας με την κλίση του, τοιχώματα, πλάκα, στέψη — ζωντανά.
* **Μινιατούρα 3D** (κάτω δεξιά): το κτίριο (τοίχοι όλων των ορόφων) και η πισίνα στη θέση της, αξονομετρικά·
  κλικ / σύρσιμο εκεί τη μετακινεί.  Σύνολα: νερό, σκυρόδεμα, εκσκαφή, εμβαδόν.
* **Τοποθέτηση**: «με κλικ στην κάτοψη» (ακολουθεί το ποντίκι, R / + / − περιστροφή, κλικ = εδώ, Esc άκυρο) ή «στη
  θέση της μινιατούρας».  Μία αναίρεση, με το μηχανοστάσιο και την παροχή του (``MainWindow._place_pool``).
* Υπάρχουσα πισίνα (Ιδιότητες ▸ Σχεδιασμός πισίνας): ίδιο παράθυρο, «Εφαρμογή» = μία αναίρεση (``UpdateEntity``).

Όλη η γεωμετρία είναι του ``site/pool.py`` (``with_outline``, ``fillet``, ``depth_at``, ``analyse``) — η ίδια που
χρησιμοποιούν η κάτοψη, το 3D, η τομή και η εισαγωγή σχεδίων.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QLabel, QPushButton, QRadioButton, QVBoxLayout, QWidget)

BLUE = QColor(20, 120, 170)
WATER = QColor(90, 175, 220)
CONCRETE = QColor(170, 170, 165)
EDIT_KEYS = ("length", "width", "depth_shallow", "depth_deep", "rotation", "pool_type", "wall", "floor", "coping",
             "outline", "x", "y")


def _gr(v, d=2):
    return f"{v:.{d}f}".replace(".", ",")


def closed_drawings(doc):
    """``[(id, label, plan points)]``: the closed shapes of the 2D drawing (polygon, circle, polyline back at its start)."""
    from archforge.architecture.drafting import SHAPES, outline
    out = []
    for e in doc.entities.values():
        if e.kind != "drafting" or not e.visible:
            continue
        try:
            pts, closed = outline(e.params)
        except Exception:                                   # noqa: BLE001 — a text / odd shape is just not offered
            continue
        if not closed and len(pts) >= 4 and math.dist(pts[0], pts[-1]) < 1e-3:
            pts, closed = pts[:-1], True
        if closed and len(pts) >= 3:
            label = e.name or SHAPES.get(e.params.get("shape"), "σχήμα")
            out.append((e.id, f"{label} · {len(pts)} σημεία", [(float(x), float(y)) for x, y, *_ in pts]))
    return out


def default_spot(doc, length):
    """Where a new pool starts: 3 m east of the building's walls (the site's middle when there are none)."""
    xs, ys = [], []
    for e in doc.entities.values():
        if e.kind == "wall" and e.visible:
            p = e.params
            xs += [float(p["x1"]), float(p["x2"])]; ys += [float(p["y1"]), float(p["y2"])]
    if not xs:
        return 0.0, 0.0
    return max(xs) + 3.0 + float(length) / 2, (min(ys) + max(ys)) / 2


# ------------------------------------------------------------------------------------------------ shape editor
class ShapeEditor(QWidget):
    """The pool's inside edge in its own axes (u along the length): shows the shape with its side lengths; in
    «ελεύθερο» mode clicks put the corners (each sharp or curved), the first corner / double click closes it."""
    changed = Signal()
    closed = Signal(list, list)                 # corners (u, v), radii

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 300)
        self.setMouseTracking(True)
        self.shape = []                          # the pool's outline (u, v), as the pool has it
        self.drawing = False
        self.points, self.radii, self.cursor = [], [], None
        self.curve, self.radius = False, 0.5
        self.grid = 0.05

    # view transform: fit the shape (or the corners drawn so far) with a margin
    def _fit(self):
        pts = list(self.shape) + list(self.points) + ([self.cursor] if self.cursor else [])
        if not pts:
            pts = [(-4, -2), (4, 2)]
        u0, u1 = min(p[0] for p in pts) - 1.0, max(p[0] for p in pts) + 1.0
        v0, v1 = min(p[1] for p in pts) - 1.0, max(p[1] for p in pts) + 1.0
        if self.drawing:                         # room to draw: at least 12 × 8 m
            cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
            u0, u1 = min(u0, cu - 6), max(u1, cu + 6); v0, v1 = min(v0, cv - 4), max(v1, cv + 4)
        k = min((self.width() - 20) / (u1 - u0), (self.height() - 20) / (v1 - v0))
        return k, (u0 + u1) / 2, (v0 + v1) / 2

    def to_screen(self, u, v):
        k, cu, cv = self._view
        return QPointF(self.width() / 2 + (u - cu) * k, self.height() / 2 - (v - cv) * k)

    def to_local(self, pos):
        k, cu, cv = self._view
        u = cu + (pos.x() - self.width() / 2) / k
        v = cv - (pos.y() - self.height() / 2) / k
        g = self.grid
        return (round(u / g) * g, round(v / g) * g)

    def start_drawing(self):
        self.drawing, self.points, self.radii, self.cursor = True, [], [], None
        self._view = self._fit()
        self.update()

    def stop_drawing(self):
        self.drawing, self.points, self.radii, self.cursor = False, [], [], None
        self.update()

    def undo_point(self):
        if self.points:
            self.points.pop(); self.radii.pop(); self.update()

    def finish(self):
        if len(self.points) >= 3:
            pts, radii = list(self.points), list(self.radii)
            self.stop_drawing()
            self.closed.emit(pts, radii)
            return True
        return False

    def mousePressEvent(self, ev):
        if not self.drawing:
            return
        if ev.button() == Qt.MouseButton.RightButton:
            self.finish(); return
        if ev.button() != Qt.MouseButton.LeftButton:
            return
        q = self.to_local(ev.position())
        if len(self.points) >= 3 and math.dist(q, self.points[0]) < 8 / self._view[0]:
            self.finish(); return
        if not self.points or math.dist(self.points[-1], q) > 1e-6:
            self.points.append(q); self.radii.append(self.radius if self.curve else 0.0)
        self.update(); self.changed.emit()

    def mouseDoubleClickEvent(self, ev):
        if self.drawing:
            self.finish()

    def mouseMoveEvent(self, ev):
        if self.drawing:
            self.cursor = self.to_local(ev.position()); self.update()

    def paintEvent(self, ev):
        from archforge.site.pool import fillet
        if not self.drawing:
            self._view = self._fit()
        k = self._view[0]
        pa = QPainter(self); pa.setRenderHint(QPainter.RenderHint.Antialiasing)
        pa.fillRect(self.rect(), QColor(250, 251, 252))
        grid = QPen(QColor(232, 235, 238)); pa.setPen(grid)
        step = 1.0 if k > 12 else 2.0
        k_, cu, cv = self._view
        u = math.floor((cu - self.width() / 2 / k) / step) * step
        while u < cu + self.width() / 2 / k:
            a = self.to_screen(u, 0); pa.drawLine(int(a.x()), 0, int(a.x()), self.height()); u += step
        v = math.floor((cv - self.height() / 2 / k) / step) * step
        while v < cv + self.height() / 2 / k:
            a = self.to_screen(0, v); pa.drawLine(0, int(a.y()), self.width(), int(a.y())); v += step
        f = QFont(); f.setPointSize(8); pa.setFont(f)
        shape = self.shape
        if self.drawing:
            pts = list(self.points) + ([self.cursor] if self.cursor else [])
            radii = list(self.radii) + ([self.radius if self.curve else 0.0] if self.cursor else [])
            shape = fillet(pts, radii) if len(pts) >= 3 else pts
            if self.shape:                          # the old shape, dashed, under the new one
                old = QPen(QColor(150, 150, 150)); old.setStyle(Qt.PenStyle.DashLine); pa.setPen(old)
                pa.setBrush(Qt.BrushStyle.NoBrush)
                pa.drawPolygon(QPolygonF([self.to_screen(*q) for q in self.shape]))
        if len(shape) >= 3:
            fill = QColor(WATER); fill.setAlpha(110)
            pa.setPen(QPen(BLUE, 2)); pa.setBrush(QBrush(fill))
            pa.drawPolygon(QPolygonF([self.to_screen(*q) for q in shape]))
        elif len(shape) == 2:
            pa.setPen(QPen(BLUE, 2)); pa.drawLine(self.to_screen(*shape[0]), self.to_screen(*shape[1]))
        # side lengths (the corners as drawn: arcs are many short sides, so only the long ones are labelled)
        corners = list(self.points) if self.drawing else shape
        n = len(corners)
        pa.setPen(QColor(40, 60, 80))
        for i in range(n if (n >= 3 and not self.drawing) else max(0, n - 1)):
            a, b = corners[i], corners[(i + 1) % n]
            L = math.dist(a, b)
            if L < 0.6:
                continue
            m = self.to_screen((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            pa.drawText(QRectF(m.x() - 40, m.y() - 16, 80, 14), Qt.AlignmentFlag.AlignCenter, f"{_gr(L)} m")
        if self.drawing:
            for (pu, pv), r in zip(self.points, self.radii):
                s = self.to_screen(pu, pv)
                pa.setPen(QPen(BLUE, 1.5)); pa.setBrush(QBrush(QColor("white")))
                (pa.drawEllipse if r > 0 else pa.drawRect)(QRectF(s.x() - 4, s.y() - 4, 8, 8))
            if self.cursor and self.points:
                pa.setPen(QColor(20, 90, 140))
                c = self.to_screen(*self.cursor)
                pa.drawText(QPointF(c.x() + 10, c.y() - 6), f"{_gr(math.dist(self.points[-1], self.cursor))} m")
        pa.end()


# ------------------------------------------------------------------------------------------------ section
class SectionView(QWidget):
    """Longitudinal section of the basin through its middle: rim, water, the sloping floor, walls, slab, coping."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(360, 170)
        self.params = {}

    def paintEvent(self, ev):
        from archforge.site.pool import WATER_DROP, depth_at, outline, param
        pa = QPainter(self); pa.setRenderHint(QPainter.RenderHint.Antialiasing)
        pa.fillRect(self.rect(), QColor(250, 251, 252))
        p = self.params
        if not p:
            pa.end(); return
        loc = outline(p)
        u0, u1 = min(q[0] for q in loc), max(q[0] for q in loc)
        t, tf, cop = param(p, "wall"), param(p, "floor"), param(p, "coping")
        dmax = max(param(p, "depth_shallow"), param(p, "depth_deep")) + tf
        span_u = (u1 - u0) + 2 * (t + cop) + 1.0
        k = min((self.width() - 30) / span_u, (self.height() - 40) / (dmax + 0.6))
        ox = self.width() / 2 - (u0 + u1) / 2 * k
        oy = 22.0

        def at(u, z):                               # z: 0 at the rim, negative down
            return QPointF(ox + u * k, oy - z * k)
        ground = QPen(QColor(120, 100, 70), 1.5)
        pa.setPen(ground)
        pa.drawLine(at(u0 - t - cop - 0.5, 0), at(u0 - t - cop, 0)); pa.drawLine(at(u1 + t + cop, 0), at(u1 + t + cop + 0.5, 0))
        n = 24
        floor_top = [at(u0 + (u1 - u0) * i / n, -depth_at(p, u0 + (u1 - u0) * i / n)) for i in range(n + 1)]
        floor_bot = [at(u0 + (u1 - u0) * i / n - (t if i == 0 else -t if i == n else 0), -depth_at(p, u0 + (u1 - u0) * i / n) - tf)
                     for i in range(n + 1)]
        body = QPolygonF([at(u0 - t, 0), at(u0, 0)] + floor_top + [at(u1, 0), at(u1 + t, 0)] + floor_bot[::-1])
        pa.setPen(QPen(QColor(90, 90, 90), 1)); pa.setBrush(QBrush(CONCRETE, Qt.BrushStyle.BDiagPattern))
        pa.drawPolygon(body)
        drop = WATER_DROP.get(param(p, "pool_type"), 0.10)
        water = QPolygonF([at(u0, -drop)] + floor_top + [at(u1, -drop)])
        wf = QColor(WATER); wf.setAlpha(150)
        pa.setPen(QPen(BLUE, 1)); pa.setBrush(QBrush(wf)); pa.drawPolygon(water)
        pa.setBrush(QBrush(QColor(210, 205, 195))); pa.setPen(QPen(QColor(110, 110, 110), 1))
        for a, b in ((u0 - t - cop + t, u0), (u1, u1 + cop)):
            pa.drawRect(QRectF(at(a - (t if a < u0 else 0), 0.04), at(b + (t if b > u1 else 0), 0)))
        f = QFont(); f.setPointSize(8); pa.setFont(f); pa.setPen(QColor(30, 50, 70))
        pa.drawText(at(u0 + 0.1, -param(p, "depth_shallow") / 2), f"{_gr(param(p, 'depth_shallow'))} m")
        pa.drawText(at(u1 - 0.9, -param(p, "depth_deep") / 2), f"{_gr(param(p, 'depth_deep'))} m")
        pa.drawText(QRectF(0, 2, self.width(), 16), Qt.AlignmentFlag.AlignCenter,
                    f"Τομή κατά μήκος · {_gr(u1 - u0)} m · πυθμένας {_gr(param(p, 'depth_shallow'))} → "
                    f"{_gr(param(p, 'depth_deep'))} m · νερό {_gr(drop * 100, 0)} cm κάτω από το χείλος")
        pa.end()


# ------------------------------------------------------------------------------------------------ 3D miniature
class Miniature(QWidget):
    """The building (every storey's walls as solids) and the pool where it would go, axonometric — for the owner's
    «ρεφερένς της σύνδεσης στον χώρο».  Click / drag moves the pool there (at its rim level)."""
    moved = Signal(float, float)
    C30, S30 = math.cos(math.radians(30)), math.sin(math.radians(30))

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setMinimumSize(360, 230)
        self.params = {}
        self.walls = [e.params for e in doc.entities.values() if e.kind == "wall" and e.visible]
        self.others = [e.params for e in doc.entities.values() if e.kind == "pool" and e.visible]
        self._t = (1.0, 0.0, 0.0)

    def _iso(self, x, y, z):
        return ((x - y) * self.C30, (x + y) * self.S30 - z)

    def _fit(self, pts):
        xs = [self._iso(*q)[0] for q in pts]; ys = [self._iso(*q)[1] for q in pts]
        k = min((self.width() - 20) / max(1.0, max(xs) - min(xs)), (self.height() - 20) / max(1.0, max(ys) - min(ys)))
        return k, (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2

    def _scr(self, x, y, z):
        k, cx, cy = self._t
        sx, sy = self._iso(x, y, z)
        return QPointF(self.width() / 2 + (sx - cx) * k, self.height() / 2 + (sy - cy) * k)

    def _ground(self, pos, z):
        """Screen → plan at height z (inverse of the projection)."""
        k, cx, cy = self._t
        sx = (pos.x() - self.width() / 2) / k + cx
        sy = (pos.y() - self.height() / 2) / k + cy
        a = sx / self.C30                          # x − y
        b = (sy + z) / self.S30                    # x + y
        return ((a + b) / 2, (b - a) / 2)

    def mousePressEvent(self, ev):
        self._move(ev)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton:
            self._move(ev)

    def _move(self, ev):
        if not self.params:
            return
        x, y = self._ground(ev.position(), float(self.params.get("z", 0.0)))
        self.moved.emit(round(x, 2), round(y, 2))

    def paintEvent(self, ev):
        from archforge.site.pool import depth_at, rim, to_local
        pa = QPainter(self); pa.setRenderHint(QPainter.RenderHint.Antialiasing)
        pa.fillRect(self.rect(), QColor(236, 242, 236))
        p = self.params
        pool_rim = rim(p) if p else []
        z = float(p.get("z", 0.0)) if p else 0.0
        pts = [(float(w["x1"]), float(w["y1"]), float(w.get("z", 0.0)) + float(w["height"])) for w in self.walls]
        pts += [(float(w["x2"]), float(w["y2"]), float(w.get("z", 0.0))) for w in self.walls]
        pts += [(x, y, z - 2.0) for x, y in pool_rim] + [(x, y, z) for x, y in pool_rim]
        if not pts:
            pa.end(); return
        # the frame follows the building, and the pool only when it leaves it (no jump while dragging inside)
        self._t = self._fit(pts)
        # Seen from the +x +y side, above: the screen's lower edge is nearer.  Painter's order: far (small x + y)
        # first; the pool (a hole in the ground) as one block at its place in that order.
        faces = []                                   # (depth, polygon, fill)
        for w in self.walls:
            x1, y1, x2, y2 = float(w["x1"]), float(w["y1"]), float(w["x2"]), float(w["y2"])
            z0 = float(w.get("z", 0.0)); z1 = z0 + float(w["height"]); t = float(w["thickness"]) / 2
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 1e-6:
                continue
            nx, ny = -(y2 - y1) / L * t, (x2 - x1) / L * t
            c = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
            if sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(c, c[1:] + c[:1])) < 0:
                c.reverse()                          # counter-clockwise: the outward normal of a→b is (dy, −dx)
            for i in range(4):
                a, b = c[i], c[(i + 1) % 4]
                ox, oy = b[1] - a[1], -(b[0] - a[0])
                if ox + oy <= 1e-9:
                    continue                         # faces away from the viewer
                shade = 205 if abs(ox) > abs(oy) else 178
                poly = [(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)]
                faces.append(((a[0] + a[1] + b[0] + b[1]) / 2 + z0 * 0.001, poly, QColor(shade, shade, shade - 8)))
            top = [(q[0], q[1], z1) for q in c]
            faces.append((sum(q[0] + q[1] for q in c) / 2 + 0.002 + z1 * 0.001, top, QColor(226, 223, 216)))
        for q in self.others:                        # the project's other pools, grey, flat
            r = rim(q); zq = float(q.get("z", 0.0))
            faces.append((sum(a + b for a, b in r) / len(r) - 100, [(a, b, zq) for a, b in r], QColor(170, 190, 200)))
        faces.sort(key=lambda f: f[0])
        block = []
        if p:
            floor = [(x, y, z - depth_at(p, to_local(p, x, y)[0])) for x, y in pool_rim]
            n = len(pool_rim)
            stone = rim(p, max(0.05, float(p.get("coping", 0.30))))
            block.append(([(x, y, z) for x, y in stone], QColor(215, 205, 185)))
            block.append(([(x, y, z) for x, y in pool_rim], QColor(55, 100, 130)))
            for i in range(n):                       # the far inner walls show inside the hole
                a, b = pool_rim[i], pool_rim[(i + 1) % n]
                ox, oy = b[1] - a[1], -(b[0] - a[0])  # rim is counter-clockwise: (ox, oy) points out of the water
                if ox + oy < 0:
                    block.append(([(a[0], a[1], z), (b[0], b[1], z), floor[(i + 1) % n], floor[i]], QColor(125, 190, 220)))
            block.append(([(x, y, z - 0.10) for x, y in pool_rim], QColor(90, 175, 220, 170)))
            key = sum(a + b for a, b in pool_rim) / n - 0.5
        drawn = False
        for d, poly, fill in faces:
            if block and not drawn and d > key:
                for bp, bf in block:
                    pa.setPen(QPen(QColor(90, 110, 120), 0.6)); pa.setBrush(QBrush(bf))
                    pa.drawPolygon(QPolygonF([self._scr(*q) for q in bp]))
                drawn = True
            pa.setPen(QPen(QColor(110, 110, 110), 0.6)); pa.setBrush(QBrush(fill))
            pa.drawPolygon(QPolygonF([self._scr(*q) for q in poly]))
        if block and not drawn:
            for bp, bf in block:
                pa.setPen(QPen(QColor(90, 110, 120), 0.6)); pa.setBrush(QBrush(bf))
                pa.drawPolygon(QPolygonF([self._scr(*q) for q in bp]))
        if p:
            pa.setPen(QPen(BLUE, 2)); pa.setBrush(Qt.BrushStyle.NoBrush)
            pa.drawPolygon(QPolygonF([self._scr(x, y, z) for x, y in pool_rim]))
        f = QFont(); f.setPointSize(8); pa.setFont(f); pa.setPen(QColor(50, 60, 60))
        pa.drawText(QRectF(6, self.height() - 18, self.width() - 12, 16), Qt.AlignmentFlag.AlignLeft,
                    "Μινιατούρα 3D · κλικ / σύρσιμο = μετακίνηση της πισίνας")
        pa.end()


# ------------------------------------------------------------------------------------------------ the dialog
class PoolDesigner(QDialog):
    def __init__(self, window, pool_id=None):
        super().__init__(window)
        from archforge.site.pool import DEFAULTS, POOL_TYPES
        self.window, self.doc, self.pool_id = window, window.doc, pool_id
        self.setWindowTitle("Σχεδιασμός πισίνας" + (" — " + (self.doc.get(pool_id).name or "Πισίνα") if pool_id else ""))
        if pool_id:
            self.params = dict(self.doc.get(pool_id).params)
        else:
            z = float(self.doc.work_plane.origin[2])
            x, y = default_spot(self.doc, DEFAULTS["length"])
            self.params = {**DEFAULTS, "x": x, "y": y, "z": z, "outline": []}
        self.result_pool = None
        grid = QGridLayout(self)
        # ---- left: shape
        shape_box = QGroupBox("Σχήμα (κάτοψη της λεκάνης)"); sl = QVBoxLayout(shape_box)
        modes = QHBoxLayout(); self.mode = QButtonGroup(self)
        for i, text in enumerate(("Ορθογώνιο", "Ελεύθερο (κλικ στις γωνίες)", "Από σχέδιο 2D")):
            b = QRadioButton(text); self.mode.addButton(b, i); modes.addWidget(b)
        sl.addLayout(modes)
        self.editor = ShapeEditor(); sl.addWidget(self.editor, 1)
        tools = QHBoxLayout()
        self.curve = QCheckBox("Καμπύλη γωνία, R"); self.radius = QDoubleSpinBox(); self.radius.setRange(0.05, 10.0)
        self.radius.setSingleStep(0.1); self.radius.setValue(0.5); self.radius.setSuffix(" m")
        self.undo_point = QPushButton("↶ Σημείο"); self.close_shape = QPushButton("✓ Κλείσιμο σχήματος")
        self.redraw_shape = QPushButton("Νέο σχήμα")
        for w in (self.curve, self.radius, self.undo_point, self.close_shape, self.redraw_shape):
            tools.addWidget(w)
        sl.addLayout(tools)
        self.drawings = QComboBox(); sl.addWidget(self.drawings)
        self.shape_note = QLabel(); self.shape_note.setWordWrap(True); sl.addWidget(self.shape_note)
        grid.addWidget(shape_box, 0, 0, 2, 1)
        # ---- right top: dimensions and section
        dims = QGroupBox("Διαστάσεις και τομή"); form = QFormLayout(dims)
        self.boxes = {}
        for key, label, lo, hi, step, suffix in (("length", "Μήκος", 1.0, 50.0, 0.1, " m"), ("width", "Πλάτος", 1.0, 30.0, 0.1, " m"),
                                                 ("depth_shallow", "Βάθος στην αρχή (ρηχό)", 0.3, 4.0, 0.05, " m"),
                                                 ("depth_deep", "Βάθος στο τέλος (βαθύ)", 0.3, 5.0, 0.05, " m"),
                                                 ("wall", "Πάχος τοιχώματος", 0.10, 0.60, 0.01, " m"),
                                                 ("floor", "Πάχος πυθμένα", 0.10, 0.60, 0.01, " m"),
                                                 ("coping", "Στέψη (πλάτος)", 0.0, 1.0, 0.01, " m"),
                                                 ("rotation", "Στροφή", -180.0, 180.0, 5.0, "°")):
            b = QDoubleSpinBox(); b.setRange(lo, hi); b.setSingleStep(step); b.setDecimals(2 if suffix == " m" else 0)
            b.setSuffix(suffix); form.addRow(label, b); self.boxes[key] = b
        self.kind = QComboBox()
        for value, text in POOL_TYPES.items():
            self.kind.addItem(text, value)
        form.addRow("Τύπος", self.kind)
        self.section = SectionView(); form.addRow(self.section)
        grid.addWidget(dims, 0, 1)
        # ---- right bottom: miniature and totals
        mini_box = QGroupBox("Στον χώρο"); ml = QVBoxLayout(mini_box)
        self.mini = Miniature(self.doc); ml.addWidget(self.mini, 1)
        self.totals = QLabel(); self.totals.setWordWrap(True); ml.addWidget(self.totals)
        grid.addWidget(mini_box, 1, 1)
        # ---- buttons
        row = QHBoxLayout()
        if pool_id:
            self.apply_button = QPushButton("Εφαρμογή"); self.apply_button.setDefault(True); row.addWidget(self.apply_button)
            self.apply_button.clicked.connect(self.apply_to_pool)
        else:
            self.place_click = QPushButton("Τοποθέτηση με κλικ στην κάτοψη…"); self.place_click.setDefault(True)
            self.place_here = QPushButton("Τοποθέτηση στη θέση της μινιατούρας")
            row.addWidget(self.place_click); row.addWidget(self.place_here)
            self.place_click.clicked.connect(self.place_by_click)
            self.place_here.clicked.connect(self.place_at_miniature)
        cancel = QPushButton("Άκυρο"); cancel.clicked.connect(self.reject); row.addStretch(1); row.addWidget(cancel)
        grid.addLayout(row, 2, 0, 1, 2)
        grid.setColumnStretch(0, 1); grid.setColumnStretch(1, 1)
        # ---- state → widgets, then wiring
        self._loading = True
        for key, b in self.boxes.items():
            from archforge.site.pool import param
            b.setValue(float(param(self.params, key)))
        self.kind.setCurrentIndex(max(0, self.kind.findData(self.params.get("pool_type", "skimmer"))))
        self._fill_drawings()
        self.mode.button(1 if self.params.get("outline") else 0).setChecked(True)
        self._loading = False
        for key, b in self.boxes.items():
            b.valueChanged.connect(lambda v, key=key: self._set(key, float(v)))
        self.kind.currentIndexChanged.connect(lambda _i: self._set("pool_type", self.kind.currentData()))
        self.mode.idClicked.connect(self._mode_changed)
        self.curve.toggled.connect(lambda on: setattr(self.editor, "curve", bool(on)))
        self.radius.valueChanged.connect(lambda v: setattr(self.editor, "radius", float(v)))
        self.undo_point.clicked.connect(self.editor.undo_point)
        self.close_shape.clicked.connect(self._close_clicked)
        self.redraw_shape.clicked.connect(self.editor.start_drawing)
        self.editor.closed.connect(self._shape_drawn)
        self.drawings.activated.connect(lambda _i: self._from_drawing())
        self.mini.moved.connect(self._moved)
        self._mode_changed(self.mode.checkedId(), start=False)
        self.resize(1080, 720)
        self.refresh()

    # ---------------------------------------------------------------- state
    def _fill_drawings(self):
        self.drawings.clear()
        self._closed = closed_drawings(self.doc)
        if not self._closed:
            self.drawings.addItem("(δεν υπάρχει κλειστή γραμμή στο σχέδιο 2D)", None)
        for eid, label, _pts in self._closed:
            self.drawings.addItem(label, eid)

    def _set(self, key, value):
        if self._loading:
            return
        self.params[key] = value
        self.refresh()

    def _moved(self, x, y):
        self.params["x"], self.params["y"] = float(x), float(y)
        self.refresh()

    def _mode_changed(self, mode, start=True):
        rect = mode == 0
        for key in ("length", "width"):
            self.boxes[key].setEnabled(True)
        for w in (self.curve, self.radius, self.undo_point, self.close_shape, self.redraw_shape):
            w.setVisible(mode == 1)
        self.drawings.setVisible(mode == 2)
        if rect:
            self.editor.stop_drawing()
            if self.params.get("outline"):
                self.params["outline"] = []
                self.refresh()
        elif mode == 1 and start:
            self.editor.start_drawing()
        elif mode == 2 and start:
            self._from_drawing()
        self._note()

    def _note(self):
        mode = self.mode.checkedId()
        if mode == 1 and self.editor.drawing:
            text = ("Κλικ στις γωνίες· «Καμπύλη γωνία» για στρογγυλή γωνία με ακτίνα R· κλικ στην πρώτη γωνία, διπλό κλικ, "
                    "δεξί κλικ ή «Κλείσιμο» = τέλος.  Το μήκος / πλάτος μετά τεντώνουν το σχήμα.")
        elif mode == 2:
            text = ("Διάλεξε κλειστή γραμμή του σχεδίου 2D (πολύγωνο, κύκλο, κλειστή πολυγραμμή): η πισίνα παίρνει το "
                    "σχήμα και τη θέση της.")
        elif mode == 1:
            text = "Σχεδιασμένο σχήμα · «Νέο σχήμα» για να το ξανασχεδιάσεις."
        else:
            text = "Ορθογώνια λεκάνη: μήκος × πλάτος στα δεξιά."
        self.shape_note.setText(text)

    def _close_clicked(self):
        if not self.editor.finish():
            self.window.statusBar().showMessage("Σχεδιασμός πισίνας: χρειάζονται τουλάχιστον 3 γωνίες", 5000)

    def _apply_shape(self, plan_points, radii=0.0):
        from archforge.site.pool import with_outline
        try:
            changes = with_outline(self.params, plan_points, radii)
        except ValueError as exc:
            self.shape_note.setText(f"⚠ {exc}")
            return False
        self.params.update(changes)
        self._loading = True
        for key in ("length", "width"):
            self.boxes[key].setValue(float(self.params[key]))
        self._loading = False
        self.refresh()
        return True

    def _shape_drawn(self, local_pts, radii):
        from archforge.site.pool import to_world
        world = [to_world(self.params, u, v) for u, v in local_pts]
        if self._apply_shape(world, radii):
            self._note()

    def _from_drawing(self):
        eid = self.drawings.currentData()
        pts = next((p for i, _l, p in self._closed if i == eid), None)
        if pts:
            if self._apply_shape(pts):
                self.shape_note.setText(f"Σχήμα από το σχέδιο 2D: «{self.drawings.currentText()}» — η πισίνα στη θέση του.")

    def refresh(self):
        from archforge.core.model import Entity
        from archforge.site.pool import analyse, area, outline
        p = self.params
        self.editor.shape = outline(p)
        self.editor.update()
        self.section.params = p; self.section.update()
        self.mini.params = p; self.mini.update()
        try:
            a = analyse(self.doc, Entity("pool", p, id=self.pool_id or "designer"))
            self.totals.setText(f"Εμβαδόν νερού {_gr(area(p), 1)} m² · νερό {_gr(a['volume_m3'], 1)} m³ · "
                                f"σκυρόδεμα {_gr(a['concrete_m3'], 1)} m³ · εκσκαφή {_gr(a.get('excavation_m3', 0.0), 1)} m³ · "
                                f"κέντρο ({_gr(float(p['x']))}, {_gr(float(p['y']))})")
        except Exception as exc:                                # noqa: BLE001 — said, not hidden
            self.totals.setText(f"⚠ {exc}")

    def changes(self):
        """What differs from the pool as it is (``EDIT_KEYS``)."""
        old = self.doc.get(self.pool_id).params if self.pool_id else {}
        return {k: self.params[k] for k in EDIT_KEYS if k in self.params and old.get(k) != self.params[k]}

    # ---------------------------------------------------------------- results
    def apply_to_pool(self):
        from archforge.core.commands import UpdateEntity
        ch = self.changes()
        if ch:
            self.window.stack.execute(UpdateEntity(self.pool_id, ch))
            self.window._redraw_views(all_views=True)
            self.window.refresh_inspector()
        self.window.statusBar().showMessage("Σχεδιασμός πισίνας: " + ("εφαρμόστηκε · Ctrl+Z αναίρεση" if ch else "καμία αλλαγή"), 6000)
        self.accept()

    def _new_params(self):
        return {k: v for k, v in self.params.items() if k not in ("x", "y")}

    def place_at_miniature(self):
        pool = self.window._place_pool(float(self.params["x"]), float(self.params["y"]), **self._new_params())
        self.result_pool = pool
        if pool is not None:
            self.doc.select([pool.id]); self.window.refresh_inspector()
        self.accept()

    def place_by_click(self):
        tool = getattr(self.window, "_pool_place_tool", None) or install(self.window)
        self.accept()
        tool.start(self._new_params())


# ------------------------------------------------------------------------------------------------ placing in plan
class PoolPlaceTool:
    """The designed pool follows the mouse in the plan: R / + turn it 15°, − back; click puts it there (one undo,
    with its equipment room); Esc cancels."""

    def __init__(self, window):
        self.window = window
        self.params = None
        self.cursor = None

    def start(self, params):
        self.params = dict(params)
        self.cursor = None
        w = self.window
        central = getattr(w, '_central_tabs', None)
        simultaneous = getattr(w, '_simultaneous_action', None)
        if central is not None and not (simultaneous is not None and simultaneous.isChecked()):
            central.setCurrentIndex(0)                       # the plan in front (as the shape tool)
        w.view = w.plan_view
        w.plan_view.controller.cancel()
        w.plan_view.controller.set_tool('select')
        w.plan_view.setFocus()
        self._status()

    def _status(self):
        from archforge.site.pool import param
        self.window.statusBar().showMessage(
            f"Πισίνα {_gr(param(self.params, 'length'))} × {_gr(param(self.params, 'width'))} m: κλικ στην κάτοψη για "
            f"τη θέση της · στροφή {param(self.params, 'rotation'):.0f}° (R / + / −) · Esc = άκυρο")

    def cancel(self):
        self.params = None
        self.window.statusBar().showMessage("Τοποθέτηση πισίνας: ακυρώθηκε", 4000)
        self.window.plan_view.redraw()

    def place(self, x, y):
        params, self.params = self.params, None
        pool = self.window._place_pool(float(x), float(y), **params)
        if pool is not None:
            self.window.doc.select([pool.id]); self.window.refresh_inspector()
        self.window.plan_view.redraw()
        return pool

    def turn(self, deg):
        self.params["rotation"] = ((float(self.params.get("rotation", 0.0)) + deg + 180) % 360) - 180
        self._status(); self.window.plan_view.redraw()

    def handle(self, view, kind, event):
        if self.params is None:
            return False
        if kind == "key":
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.cancel(); return True
            if key in (Qt.Key.Key_R, Qt.Key.Key_Plus, Qt.Key.Key_Equal):
                self.turn(15); return True
            if key == Qt.Key.Key_Minus:
                self.turn(-15); return True
            return False
        if kind not in ("press", "move", "release"):
            return kind in ("dclick", "context")
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        q = view._scene_to_plane(pos)
        x, y = float(q.a), float(q.b)
        if view.controller.snap_enabled and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            g = float(view.controller.grid)
            if g > 0:
                x, y = round(x / g) * g, round(y / g) * g
        self.cursor = (x, y)
        if kind == "press" and event.button() == Qt.MouseButton.LeftButton:
            view._long_press = None
            self.place(x, y)
            return True
        view.redraw()
        return True

    def paint(self, view):
        if self.params is None or self.cursor is None:
            return
        from archforge.site.pool import rim
        p = {**self.params, "x": self.cursor[0], "y": self.cursor[1]}
        pen = QPen(BLUE); pen.setCosmetic(True); pen.setWidthF(2.0)
        fill = QColor(WATER); fill.setAlpha(90)
        view._scene.addPolygon(QPolygonF([QPointF(*q) for q in rim(p)]), pen, QBrush(fill)).setZValue(45)
        stone = QPen(QColor(150, 140, 120)); stone.setCosmetic(True); stone.setStyle(Qt.PenStyle.DashLine)
        view._scene.addPolygon(QPolygonF([QPointF(*q) for q in rim(p, max(0.05, float(p.get('coping', 0.3))))]), stone).setZValue(45)


def install(window):
    tool = PoolPlaceTool(window)
    window._pool_place_tool = tool
    window.plan_view.pool_place_tool = tool
    return tool


def open_designer(window, pool_id=None):
    """Έδαφος ▸ Πισίνα… (new) / Ιδιότητες ▸ Σχεδιασμός πισίνας… (existing)."""
    if getattr(window, "_pool_place_tool", None) is None:
        install(window)
    d = PoolDesigner(window, pool_id)
    window._pool_designer = d
    d.exec() if not getattr(window, "_no_modal_dialogs", False) else d.show()
    return d
