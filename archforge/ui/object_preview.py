"""Οπτική προεπισκόπηση του Object Modifier: 3D με QPainter, λαβές μεγέθους, επιλογή τμήματος.

Απλό QWidget (χωρίς OpenGL/WebEngine: δουλεύει ίδια σε Windows, χωρίς
κάρτα γραφικών και headless).  Το πλέγμα βγαίνει από τις ίδιες συναρτήσεις
με το έργο (``library_object_mesh`` / ``cabinet_mesh``) στις παραμέτρους της
οντότητας, γωνίες σκιασμένες με σταθερό φως, ζωγραφισμένες από πίσω προς
τα εμπρός.

* Σύρσιμο στο κενό: περιστροφή της θέας (δεν αλλάζει το έργο).
* Λαβές Π / Β / Υ (πλάτος, βάθος, ύψος) με ετικέτες σε cm: σύρσιμο = νέο
  μέγεθος ζωντανά στην προεπισκόπηση· στο άφημα ``sizeCommitted`` → ο
  διάλογος κάνει ΕΝΑ UpdateEntity (ένα undo ανά κίνηση).  Με κλειδωμένες
  αναλογίες αλλάζουν και οι τρεις μαζί.
* Κλικ σε τμήμα → ``partPicked(ρόλος)`` για την παλέτα υλικών δίπλα.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

ROLE_COLORS = {"carcass": "#e8e2d6", "front": "#d6cdbd", "shelf": "#efe9dd", "handle": "#9aa0a6", "plinth": "#5a5a5a",
               "worktop": "#8a8178", "rail": "#b0b4b8", "glass": "#bcd6e0", "mechanism": "#9aa0a6"}
HANDLE_COLORS = {"width": QColor(210, 60, 50), "depth": QColor(40, 150, 70), "height": QColor(30, 100, 210)}
HANDLE_NAMES = {"width": "Π", "depth": "Β", "height": "Υ"}
MIN_SIZE = 0.05


class ObjectPreview(QWidget):
    sizeCommitted = Signal(dict)     # {'width': m, ...} στο άφημα μιας λαβής
    partPicked = Signal(str)         # ρόλος τμήματος κάτω από το κλικ

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 300)
        self.setMouseTracking(True)
        self.kind = None
        self.params = {}
        self.yaw = -35.0
        self.pitch = 25.0
        self.lock = True
        self.selected_role = None
        self._mesh = ((), (), ())
        self._colors = []
        self._press = None
        self._drag_handle = None
        self._pending = None          # μέγεθος κατά το σύρσιμο (δεν έχει μπει στο έργο ακόμη)
        self._screen_tris = []
        self._handles = {}

    # -------------------------------------------------------------- data
    def set_entity(self, entity):
        self.kind = entity.kind
        self.params = dict(entity.params)
        self.lock = bool(self.params.get("uniform", 1.0)) if self.kind == "library_object" else False
        self._pending = None
        self._rebuild()

    def sizes(self):
        p = self._pending or self.params
        return {k: float(p.get(k, 0.0)) for k in ("width", "depth", "height")}

    def _local_params(self):
        p = dict(self.params, x=0.0, y=0.0, z=0.0, rotation=0.0)
        if self._pending:
            p.update(self._pending)
        return p

    def _rebuild(self):
        p = self._local_params()
        try:
            if self.kind == "cabinet":
                from archforge.kitchen.cabinets import cabinet_mesh
                verts, tris, roles = cabinet_mesh(p)
            elif self.kind == "library_object":
                from archforge.library.objects import library_object_mesh, triangle_part_indices
                verts, tris, _roles = library_object_mesh(p)
                idx = triangle_part_indices(p)
                roles = tuple(f"part{i}" for i in idx) if idx is not None and len(idx) == len(tris) else ("body",) * len(tris)
            else:
                verts, tris, roles = (), (), ()
        except (KeyError, ValueError, TypeError):
            verts, tris, roles = (), (), ()
        self._mesh = (verts, tris, roles)
        self._colors = self._role_colors(p, roles)
        self.update()

    def _role_colors(self, p, roles):
        from archforge.rendering.materials import MATERIAL_PRESETS
        overrides = p.get("surface_materials") or {}
        whole = p.get("material_id")
        palette = {}
        if self.kind == "library_object":
            from archforge.library.objects import asset_parts
            palette = {role: color for role, color, _n in asset_parts(p)}
        out = []
        for role in roles:
            mid = overrides.get(role) or whole
            color = MATERIAL_PRESETS.get(mid, {}).get("color") if mid else None
            out.append(QColor(color or palette.get(role) or ROLE_COLORS.get(role, "#c8c4bc")))
        return out

    # ------------------------------------------------------------ camera
    def _basis(self):
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        right = (math.cos(yaw), math.sin(yaw), 0.0)
        fwd = (-math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), -math.sin(pitch))
        up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2], right[0] * fwd[1] - right[1] * fwd[0])
        return right, up, fwd

    def _scale_center(self):
        w, d, h = (max(MIN_SIZE, v) for v in self.sizes().values())
        size = math.sqrt(w * w + d * d + h * h)
        return min(self.width(), self.height()) * 0.62 / max(size, 1e-6), (0.0, 0.0, h / 2)

    def project(self, q):
        right, up, fwd = self._basis()
        k, c = self._scale_center()
        x, y, z = q[0] - c[0], q[1] - c[1], q[2] - c[2]
        sx = self.width() / 2 + k * (x * right[0] + y * right[1] + z * right[2])
        sy = self.height() / 2 + 20 - k * (x * up[0] + y * up[1] + z * up[2])
        depth = x * fwd[0] + y * fwd[1] + z * fwd[2]
        return sx, sy, depth

    def handle_points(self):
        """Θέσεις λαβών στην οθόνη: {'width': (x, y), ...} και η κατεύθυνση κάθε άξονα ανά μέτρο."""
        s = self.sizes()
        w, d, h = s["width"], s["depth"], s["height"]
        anchors = {"width": ((w / 2, 0.0, h / 2), (1.0, 0.0, 0.0)),
                   "depth": ((0.0, -d / 2, h / 2), (0.0, -1.0, 0.0)),
                   "height": ((0.0, 0.0, h), (0.0, 0.0, 1.0))}
        out = {}
        for key, (q, axis) in anchors.items():
            ax, ay, _ = self.project(q)
            bx, by, _ = self.project((q[0] + axis[0], q[1] + axis[1], q[2] + axis[2]))
            out[key] = ((ax, ay), (bx - ax, by - ay))
        return out

    # ------------------------------------------------------------- paint
    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(246, 246, 243))
        verts, tris, roles = self._mesh
        pts = [self.project(v) for v in verts]
        right, up, fwd = self._basis()
        light = (0.35, -0.55, 0.76)
        faces = []
        for i, (a, b, c) in enumerate(tris):
            va, vb, vc = verts[a], verts[b], verts[c]
            ux, uy, uz = vb[0] - va[0], vb[1] - va[1], vb[2] - va[2]
            wx, wy, wz = vc[0] - va[0], vc[1] - va[1], vc[2] - va[2]
            nx, ny, nz = uy * wz - uz * wy, uz * wx - ux * wz, ux * wy - uy * wx
            n = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            nx, ny, nz = nx / n, ny / n, nz / n
            shade = 0.55 + 0.45 * abs(nx * light[0] + ny * light[1] + nz * light[2])
            depth = (pts[a][2] + pts[b][2] + pts[c][2]) / 3
            faces.append((depth, i, shade))
        faces.sort(reverse=True)          # μακρινά πρώτα
        self._screen_tris = []
        for depth, i, shade in faces:
            a, b, c = tris[i]
            poly = QPolygonF([QPointF(pts[a][0], pts[a][1]), QPointF(pts[b][0], pts[b][1]), QPointF(pts[c][0], pts[c][1])])
            base = self._colors[i] if i < len(self._colors) else QColor(200, 200, 200)
            color = QColor(int(base.red() * shade), int(base.green() * shade), int(base.blue() * shade))
            chosen = self.selected_role is not None and roles[i] == self.selected_role
            if chosen:
                color = QColor(min(255, color.red() + 40), min(255, color.green() + 20), max(0, color.blue() - 30))
            painter.setPen(QPen(color, 0.6))
            painter.setBrush(QBrush(color))
            painter.drawPolygon(poly)
            self._screen_tris.append((poly, roles[i]))
        self._screen_tris.reverse()        # κοντινά πρώτα για το κλικ
        # Λαβές μεγέθους με ετικέτες σε cm.
        s = self.sizes()
        font = QFont(self.font())
        font.setBold(True)
        painter.setFont(font)
        self._handles = {}
        for key, ((hx, hy), (dx, dy)) in self.handle_points().items():
            L = math.hypot(dx, dy) or 1.0
            ex, ey = hx + dx / L * 26, hy + dy / L * 26
            pen = QPen(HANDLE_COLORS[key], 2.2)
            painter.setPen(pen)
            painter.drawLine(QPointF(hx, hy), QPointF(ex, ey))
            painter.setBrush(QBrush(QColor(255, 255, 255)))
            r = 8 if self._drag_handle != key else 10
            painter.drawEllipse(QPointF(ex, ey), r, r)
            painter.drawText(QPointF(ex - 4, ey + 4), HANDLE_NAMES[key])
            painter.drawText(QPointF(ex + 12, ey + 4), f"{s[key] * 100:.0f} cm")
            self._handles[key] = (ex, ey)
        painter.setPen(QPen(QColor(90, 90, 90)))
        font.setBold(False)
        painter.setFont(font)
        hint = "Σύρε λαβή Π/Β/Υ = μέγεθος · σύρε στο κενό = περιστροφή θέας · κλικ σε τμήμα = υλικό"
        if self.lock:
            hint = "🔒 αναλογίες κλειδωμένες · " + hint
        painter.drawText(self.rect().adjusted(8, 0, -8, -6), Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap, hint)
        painter.end()

    # ------------------------------------------------------------- mouse
    def handle_at(self, x, y):
        for key, (hx, hy) in self._handles.items():
            if math.hypot(x - hx, y - hy) <= 12:
                return key
        return None

    def part_at(self, x, y):
        p = QPointF(x, y)
        for poly, role in self._screen_tris:
            if poly.containsPoint(p, Qt.FillRule.OddEvenFill):
                return role
        return None

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        self._press = (pos.x(), pos.y(), self.yaw, self.pitch, self.sizes())
        self._drag_handle = self.handle_at(pos.x(), pos.y())
        self._moved = False

    def mouseMoveEvent(self, event):
        if self._press is None:
            return
        pos = event.position()
        x0, y0, yaw0, pitch0, size0 = self._press
        dx, dy = pos.x() - x0, pos.y() - y0
        if abs(dx) + abs(dy) > 3:
            self._moved = True
        if self._drag_handle:
            self.drag_handle_to(self._drag_handle, dx, dy, size0)
        else:
            self.yaw = yaw0 - dx * 0.5
            self.pitch = max(-10.0, min(85.0, pitch0 + dy * 0.4))
            self.update()

    def drag_handle_to(self, key, dx, dy, size0=None):
        """Σύρσιμο λαβής κατά (dx, dy) pixel από το πάτημα: νέο μέγεθος (μόνο στην προεπισκόπηση)."""
        size0 = dict(size0 or self.sizes())
        (_h, (ax, ay)) = self.handle_points()[key]
        per_m = ax * ax + ay * ay
        if per_m < 1e-9:
            return
        along = (dx * ax + dy * ay) / per_m             # μέτρα κατά τον άξονα
        grow = along * (1.0 if key == "height" else 2.0)    # πλάτος/βάθος: συμμετρικά γύρω από το κέντρο
        value = max(MIN_SIZE, round((size0[key] + grow) * 100.0) / 100.0)     # βήμα 1 cm
        if self.lock and size0[key] > 0:
            factor = value / size0[key]
            self._pending = {k: max(MIN_SIZE, v * factor) for k, v in size0.items()}
        else:
            self._pending = dict(size0, **{key: value})
        self._rebuild()

    def mouseReleaseEvent(self, event):
        if self._press is None:
            return
        handle, moved = self._drag_handle, self._moved
        self._press = None
        self._drag_handle = None
        if handle and self._pending:
            changes = {k: v for k, v in self._pending.items() if abs(v - float(self.params.get(k, 0.0))) > 1e-6}
            self.params.update(self._pending)
            self._pending = None
            if changes:
                self.sizeCommitted.emit(changes)
            self.update()
            return
        if not moved:
            role = self.part_at(event.position().x(), event.position().y())
            if role:
                self.selected_role = role
                self.partPicked.emit(role)
                self.update()
