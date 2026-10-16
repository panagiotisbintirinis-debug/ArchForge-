"""Σύρσιμο από τη Βιβλιοθήκη στην κάτοψη και στο 3D («στο χέρι»).

Πατάς σε ένα φύλλο του δέντρου της Βιβλιοθήκης και σέρνεις: πάνω στην
κάτοψη (ή στο 3D) εμφανίζεται φάντασμα στο πραγματικό μέγεθος που ακολουθεί
τον κέρσορα και κουμπώνει με την πλάτη στην παρειά του τοίχου όπου έχει
νόημα (έπιπλα, ντουλάπια, είδη υγιεινής)· ροδέλα = 15°, R = 90°, Shift =
χωρίς κούμπωμα, Esc = ακύρωση.  Το άφημα είναι ΜΙΑ εντολή (ένα undo) μέσα
από τις ίδιες διαδρομές με το διπλό κλικ (AddEntity, τα εργαλεία πόρτας/
ντουλαπιού/κολόνας, τα σημεία Η/Μ).  Υλικό που αφήνεται πάνω σε τοίχο ή
αντικείμενο εφαρμόζεται στην πλευρά/στο τμήμα κάτω από τον κέρσορα.

Το ίδιο ``LibraryCarry`` εξυπηρετεί και το κλασικό drag & drop με QMimeData
(``MIME``), ώστε ένα σύρσιμο από άλλο σημείο να δουλεύει το ίδιο.
"""
from __future__ import annotations

import json
import math

from PySide6.QtCore import QEvent, QMimeData, QObject, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QGraphicsTextItem

MIME = 'application/x-archforge-library'
TURN_STEP = 15.0          # ροδέλα
WALL_REACH = 0.45         # πόσο κοντά στον τοίχο κουμπώνει η πλάτη (m)


def mime_for(action):
    data = QMimeData()
    data.setData(MIME, json.dumps(list(action)).encode('utf-8'))
    data.setText(str(action[-1]))
    return data


def action_from_mime(mime):
    if mime is None or not mime.hasFormat(MIME):
        return None
    try:
        return tuple(json.loads(bytes(mime.data(MIME)).decode('utf-8')))
    except (ValueError, TypeError):
        return None


def droppable(action):
    return bool(action) and action[0] in ('asset', 'cabinet', 'opening', 'railing', 'material', 'tool', 'structural')


class LibraryCarry:
    """Ένα στοιχείο της Βιβλιοθήκης «στο χέρι»: φάντασμα, κούμπωμα, στροφή, άφημα."""

    def __init__(self, window, action):
        self.window = window
        self.action = tuple(action)
        self.kind = self.action[0]
        self.turn = 0.0
        self.xy = None
        self.free = False
        self.ghost = None          # {'poly': [...], 'front': (a, b), 'line': (a, b), 'ok': bool, 'params': {...}}
        self.message = ''
        self._ctl = None
        self.record = None
        if self.kind == 'asset':
            from archforge.library.assets import load_asset
            self.record = load_asset(str(self.action[1])) or {}
        if self.kind in ('cabinet', 'opening', 'structural'):
            self._ctl = self._controller()

    # ------------------------------------------------------------ helpers
    @property
    def doc(self):
        return self.window.doc

    @property
    def z(self):
        return float(self.doc.work_plane.origin[2])

    @property
    def name(self):
        a = self.action
        if self.kind == 'asset':
            return str(self.record.get('name') or 'Αντικείμενο')
        if self.kind == 'cabinet':
            return str(a[1])
        if self.kind == 'opening':
            from archforge.architecture.joinery import preset
            return preset(a[1])['name']
        if self.kind == 'railing':
            from archforge.architecture.railings import TYPES
            return TYPES[a[1]]['label']
        if self.kind == 'material':
            from archforge.rendering.materials import MATERIAL_PRESETS
            return MATERIAL_PRESETS.get(a[1], {}).get('name', 'Υλικό')
        if self.kind == 'structural':
            return 'Κολόνα' if a[1] == 'structural_column' else 'Δοκός'
        return str(a[-1])

    def _controller(self):
        """Ιδιωτικός PointerController: οι ίδιες συναλλαγές με τα εργαλεία (μία εντολή στο άφημα)."""
        from archforge.core.viewport import PointerController
        ctl = PointerController(self.doc, self.window.stack)
        a = self.action
        if self.kind == 'cabinet':
            definition = dict(getattr(self.window, '_kitchen_defs', {}).get(a[1]) or {})
            if not definition:
                return None
            ctl.set_tool('component')
            ctl.set_component_definition(definition)
        elif self.kind == 'opening':
            from archforge.architecture.joinery import preset
            pr = preset(a[1])
            ctl.set_tool(pr['kind'])
            ctl.opening_preset = pr
        elif self.kind == 'structural':
            ctl.set_tool(a[1])
            ctl.structural_preset = dict(a[2])
        return ctl

    def _press(self, x, y):
        from archforge.core.viewport import PointerEvent
        ev = PointerEvent(float(x), float(y))
        ev.shift = self.free
        ev.ctrl = False
        if self.kind == 'cabinet' and self._ctl.component_definition is not None:
            self._ctl.component_definition['rotation'] = self.turn
        self._ctl.cancel()
        return self._ctl.pointer_down(ev), ev

    # ---------------------------------------------------------------- live
    def move(self, x, y, free=False):
        """Το φάντασμα στο (x, y) της κάτοψης· free = χωρίς κούμπωμα (Shift)."""
        self.xy = (float(x), float(y))
        self.free = bool(free)
        self.message = ''
        try:
            self.ghost = self._ghost(*self.xy)
        except (ValueError, KeyError, RuntimeError) as exc:
            self.ghost = None
            self.message = str(exc)
        return self.ghost

    def turn_by(self, degrees):
        self.turn = (self.turn + float(degrees)) % 360.0
        if self.xy is not None:
            self.move(*self.xy, free=self.free)

    def _asset_params(self, x, y):
        w, d, h = (float(v) for v in self.record.get('size', (0.6, 0.6, 0.8)))
        p = {'x': x, 'y': y, 'z': self.z, 'rotation': self.turn, 'width': w, 'depth': d, 'height': h,
             'uniform': 1.0, 'asset': str(self.action[1])}
        if self.free:
            return p, None
        snapped = None
        if abs(self.turn) < 1e-9:
            # Πλάτη στην παρειά του κοντινού τοίχου, μέτωπο προς τον χώρο του κέρσορα.
            from archforge.kitchen.cabinets import wall_aligned
            aligned = wall_aligned(self.doc, x, y, d, tolerance=WALL_REACH + d / 2, z=self.z)
            if aligned is not None:
                p['x'], p['y'], p['rotation'] = aligned
                snapped = 'wall'
        from archforge.assistant.fixture_snap import snap_correction
        from archforge.core.model import Entity
        probe = Entity('library_object', dict(p), name=self.name)
        found = snap_correction(self.doc, probe.id, p, entity=probe)
        if found is not None:
            p['x'] += found[0]
            p['y'] += found[1]
            snapped = found[2]
        return p, snapped

    def _ghost(self, x, y):
        if self.kind == 'asset':
            from archforge.library.objects import footprint
            p, snapped = self._asset_params(x, y)
            poly = footprint(p)
            return {'poly': poly, 'front': (poly[0], poly[1]), 'ok': True, 'params': p, 'snapped': snapped}
        if self.kind in ('cabinet', 'structural') and self._ctl is not None:
            if self.kind == 'structural' and self.action[1] != 'structural_column':
                return {'cross': (x, y), 'ok': True}
            preview, _ev = self._press(x, y)
            g = dict(preview.geometry or {})
            ok = g.get('fits') is not False
            if {'x', 'y', 'width', 'depth'} <= set(g):
                from archforge.library.objects import footprint
                poly = footprint(g)
                problem = getattr(self._ctl.active, 'problem', None)
                if problem:
                    self.message = f'⚠ Δεν χωράει: {problem}'
                return {'poly': poly, 'front': (poly[0], poly[1]), 'ok': ok, 'params': g}
            return {'cross': (x, y), 'ok': ok}
        if self.kind == 'opening' and self._ctl is not None:
            preview, _ev = self._press(x, y)
            g = preview.geometry or {}
            if not {'x1', 'y1', 'x2', 'y2'} <= set(g):
                raise ValueError('άφησε το κούφωμα πάνω σε τοίχο')
            return {'line': ((g['x1'], g['y1']), (g['x2'], g['y2'])), 'ok': True}
        if self.kind == 'railing':
            a = math.radians(self.turn)
            dx, dy = math.cos(a), math.sin(a)
            return {'line': ((x - dx, y - dy), (x + dx, y + dy)), 'ok': True}
        if self.kind == 'tool':
            return {'cross': (x, y), 'ok': True}
        return None     # υλικό: χωρίς φάντασμα, μετρά τι είναι κάτω από τον κέρσορα

    def label(self):
        if self.message:
            return f'{self.name}: {self.message}'
        g = self.ghost or {}
        if self.kind == 'material':
            return f'Υλικό «{self.name}»: άφησέ το πάνω σε τοίχο (πλευρά) ή αντικείμενο (τμήμα) · Esc = ακύρωση'
        text = self.name
        p = g.get('params') or {}
        if 'width' in p and 'depth' in p:
            text += f"  {float(p['width']) * 100:.0f}×{float(p['depth']) * 100:.0f} cm · {float(p.get('rotation', 0.0)) % 360:.0f}°"
        if g.get('snapped') == 'wall':
            text += ' · πλάτη στον τοίχο'
        return text + ' — άφησε για τοποθέτηση · ροδέλα 15° / R 90° · Shift ελεύθερα · Esc ακύρωση'

    # ---------------------------------------------------------------- drop
    def drop(self, x, y, target=None):
        """Τοποθέτηση/εφαρμογή — ΜΙΑ εντολή.  ``target`` = (entity_id, ρόλος) κάτω από τον κέρσορα."""
        w = self.window
        self.move(x, y, free=self.free)
        done = None
        try:
            done = self._commit(float(x), float(y), target)
        except (ValueError, KeyError, RuntimeError) as exc:
            w.statusBar().showMessage(f'{self.name}: {exc}', 6000)
            return None
        finally:
            if self._ctl is not None:
                self._ctl.cancel()
        if done:
            ids = [i for i in (done if isinstance(done, (list, tuple)) else [done]) if isinstance(i, str) and i in w.doc.entities]
            if ids and self.kind != 'material':
                w.doc.select(ids)
            w._redraw_views(all_views=True)
            if hasattr(w, 'refresh_inspector'):
                w.refresh_inspector()
            if self.kind != 'material':
                w.statusBar().showMessage(f'{self.name}: τοποθετήθηκε — σύρε για μετακίνηση, λαβή ⟳ για περιστροφή, Delete για διαγραφή · Ctrl+Z = αναίρεση', 6000)
        return done

    def _commit(self, x, y, target):
        from archforge.core.commands import AddEntity, UpdateEntity
        from archforge.core.model import Entity
        w = self.window
        if self.kind == 'asset':
            p = dict((self.ghost or {}).get('params') or self._asset_params(x, y)[0])
            obj = Entity('library_object', p, name=self.name)
            w.stack.execute(AddEntity(obj))
            return obj.id
        if self.kind in ('cabinet', 'opening') or (self.kind == 'structural' and self.action[1] == 'structural_column'):
            if self._ctl is None:
                raise ValueError('δεν βρέθηκε ο ορισμός')
            _preview, ev = self._press(x, y)
            result = self._ctl.pointer_up(ev)
            return result.entity_id
        if self.kind == 'structural':
            return w._start_structural_preset(self.action[1], self.action[2])
        if self.kind == 'railing':
            g = self.ghost or self._ghost(x, y)
            before = set(w.doc.entities)
            w._place_railing(f'railing_{self.action[1]}', [list(q) for q in g['line']], False)
            return [i for i in w.doc.entities if i not in before]
        if self.kind == 'tool':
            before = set(w.doc.entities)
            w._place_site_point(self.action[1], x, y)
            return [i for i in w.doc.entities if i not in before] or True
        if self.kind == 'material':
            if not target or target[0] not in w.doc.entities:
                raise ValueError('άφησε το υλικό πάνω σε τοίχο ή αντικείμενο')
            eid, role = target
            changes = material_changes(w.doc, eid, str(self.action[1]), role, (x, y))
            w.stack.execute(UpdateEntity(eid, changes))
            e = w.doc.get(eid)
            where = {'exterior': 'πλευρά Α', 'interior': 'πλευρά Β'}.get(role, role or 'όλο')
            w.statusBar().showMessage(f'{self.name} → {e.name or e.kind} ({where}) · Ctrl+Z = αναίρεση', 5000)
            return [eid]
        return None

    # --------------------------------------------------------------- paint
    def paint(self, view):
        """Φάντασμα στην κάτοψη (QGraphicsScene της PlanView)."""
        g = self.ghost
        scene = view._scene
        ok = g is None or g.get('ok', True)
        color = QColor(40, 150, 70) if ok else QColor(210, 40, 40)
        pen = QPen(color)
        pen.setWidthF(.03)
        pen.setStyle(Qt.PenStyle.DashLine)
        fill = QBrush(QColor(color.red(), color.green(), color.blue(), 45))
        anchor = self.xy
        if g and g.get('poly'):
            poly = g['poly']
            scene.addPolygon(QPolygonF([QPointF(*q) for q in poly]), pen, fill).setZValue(60)
            (ax, ay), (bx, by) = g['front']
            front = QPen(color)
            front.setWidthF(.05)
            scene.addLine(ax, ay, bx, by, front).setZValue(61)       # μέτωπο
            if self.kind == 'asset':
                # Το σύμβολο κάτοψης του αντικειμένου μέσα στο φάντασμα (ίδια πηγή με την κάτοψη).
                from PySide6.QtGui import QPainterPath
                from archforge.library.objects import plan_symbol_world
                thin = QPen(color.darker(120))
                thin.setWidthF(.012)
                for closed, line in plan_symbol_world(g['params']):
                    if len(line) < 2:
                        continue
                    path = QPainterPath(QPointF(*line[0]))
                    for q in line[1:]:
                        path.lineTo(QPointF(*q))
                    if closed:
                        path.closeSubpath()
                    scene.addPath(path, thin).setZValue(61)
            anchor = (max(q[0] for q in poly), max(q[1] for q in poly))
        elif g and g.get('line'):
            (ax, ay), (bx, by) = g['line']
            thick = QPen(color)
            thick.setWidthF(.08)
            scene.addLine(ax, ay, bx, by, thick).setZValue(60)
        elif g and g.get('cross'):
            cx, cy = g['cross']
            scene.addEllipse(cx - .15, cy - .15, .3, .3, pen, fill).setZValue(60)
        if anchor is None:
            return
        text = scene.addText(self.label().split(' — ')[0])
        text.setDefaultTextColor(color.darker(130))
        font = text.font()
        font.setBold(True)
        text.setFont(font)
        text.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        text.setPos(anchor[0] + .1, anchor[1] + .1)
        text.setZValue(62)

    def ghost_box(self):
        """Το φάντασμα για το 3D: κουτί {x, y, z, w, d, h, r, ok} ή None."""
        g = self.ghost or {}
        p = g.get('params') or {}
        if {'x', 'y', 'width', 'depth'} <= set(p):
            return {'x': float(p['x']), 'y': float(p['y']), 'z': float(p.get('z', self.z)),
                    'w': float(p['width']), 'd': float(p['depth']), 'h': float(p.get('height', .8)),
                    'r': float(p.get('rotation', 0.0)), 'ok': bool(g.get('ok', True))}
        if g.get('line'):
            (ax, ay), (bx, by) = g['line']
            return {'x': (ax + bx) / 2, 'y': (ay + by) / 2, 'z': self.z, 'w': math.hypot(bx - ax, by - ay), 'd': .08,
                    'h': 1.0 if self.kind == 'railing' else 2.1, 'r': math.degrees(math.atan2(by - ay, bx - ax)), 'ok': True}
        if g.get('cross'):
            cx, cy = g['cross']
            return {'x': cx, 'y': cy, 'z': self.z, 'w': .3, 'd': .3, 'h': .3, 'r': 0.0, 'ok': bool(g.get('ok', True))}
        return None


def wall_at(doc, x, y):
    """Τοίχος του ορόφου κάτω από το (x, y) (μέσα στο πάχος του, +5 cm), ή None."""
    z = float(doc.work_plane.origin[2])
    best = None
    for e in doc.entities.values():
        if e.kind != 'wall' or abs(float(e.params.get('z', 0.0)) - z) > .05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ('x1', 'y1', 'x2', 'y2'))
        L2 = (x2 - x1) ** 2 + (y2 - y1) ** 2
        if L2 < 1e-12:
            continue
        t = max(0.0, min(1.0, ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / L2))
        d = math.hypot(x - x1 - t * (x2 - x1), y - y1 - t * (y2 - y1))
        if d <= float(p.get('thickness', .2)) / 2 + .05 and (best is None or d < best[0]):
            best = (d, e.id)
    return best[1] if best else None


def wall_side(doc, wall_id, x, y):
    """'exterior' (πλευρά Α, +n) ή 'interior' (πλευρά Β) για το σημείο (x, y)."""
    p = doc.get(wall_id).params
    x1, y1, x2, y2 = (float(p[k]) for k in ('x1', 'y1', 'x2', 'y2'))
    return 'exterior' if (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1) >= 0 else 'interior'


def material_changes(doc, eid, material_id, role=None, xy=None):
    """Αλλαγές για υλικό που αφέθηκε πάνω σε ``eid``: πλευρά τοίχου ή τμήμα αντικειμένου."""
    from archforge.rendering.materials import MATERIAL_PRESETS
    if material_id not in MATERIAL_PRESETS:
        raise KeyError(material_id)
    e = doc.get(eid)
    surface_map = dict(e.params.get('surface_materials') or {})
    if e.kind == 'wall':
        side = role if role in ('exterior', 'interior') else (wall_side(doc, eid, *xy) if xy else 'exterior')
        surface_map[side] = material_id
        return {'surface_materials': surface_map}
    if e.kind in ('library_object', 'cabinet', 'door', 'window') and role and role not in ('body', 'placeholder', 'marker'):
        surface_map[role] = material_id
        return {'surface_materials': surface_map}
    changes = {'material_id': material_id}
    if e.kind in ('library_object', 'cabinet'):
        changes['surface_materials'] = {}
    return changes


# ------------------------------------------------------------------ tree
class _TreeCarry(QObject):
    """Πάτημα + σύρσιμο σε φύλλο της Βιβλιοθήκης → LibraryCarry πάνω από την κάτοψη ή το 3D."""

    def __init__(self, window, tree):
        super().__init__(tree)
        self.window = window
        self.tree = tree
        self.press = None
        self.carry = None
        tree.viewport().installEventFilter(self)
        tree.installEventFilter(self)

    def _target(self, global_pos):
        w = self.window
        under = QApplication.widgetAt(global_pos)
        plan = getattr(w, 'plan_view', None)
        pbr = getattr(w, 'pbr_view', None)
        if plan is not None and under is not None and (under is plan.viewport() or plan.isAncestorOf(under)):
            return plan
        if pbr is not None and under is not None and (under is pbr or pbr.isAncestorOf(under)):
            return pbr
        return None

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            item = self.tree.itemAt(event.position().toPoint())
            action = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
            self.press = (event.position().toPoint(), tuple(action)) if action and droppable(action) else None
            return False
        if t == QEvent.Type.MouseMove and self.press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if self.carry is None:
                if (event.position().toPoint() - self.press[0]).manhattanLength() < QApplication.startDragDistance():
                    return False
                self.carry = LibraryCarry(self.window, self.press[1])
                self.tree.setCursor(Qt.CursorShape.DragCopyCursor)
            self._hover(event.globalPosition().toPoint(), bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            return True
        if t == QEvent.Type.MouseButtonRelease and self.carry is not None:
            carry, self.carry, self.press = self.carry, None, None
            self.tree.unsetCursor()
            view = self._target(event.globalPosition().toPoint())
            if view is not None:
                view.carry_drop(carry, view.mapFromGlobal(event.globalPosition().toPoint()))
            else:
                self._clear(carry)
                self.window.statusBar().showMessage('Σύρσιμο ακυρώθηκε — άφησε το στοιχείο πάνω στην κάτοψη ή στο 3D', 4000)
            return True
        if t == QEvent.Type.MouseButtonRelease:
            self.press = None
        if self.carry is not None and t == QEvent.Type.Wheel:
            self.carry.turn_by(TURN_STEP if event.angleDelta().y() > 0 else -TURN_STEP)
            self._hover(event.globalPosition().toPoint(), self.carry.free)
            return True
        if self.carry is not None and t == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                carry, self.carry, self.press = self.carry, None, None
                self.tree.unsetCursor()
                self._clear(carry)
                self.window.statusBar().showMessage('Σύρσιμο ακυρώθηκε', 3000)
                return True
            if event.key() == Qt.Key.Key_R:
                self.carry.turn_by(90.0)
                from PySide6.QtGui import QCursor
                self._hover(QCursor.pos(), self.carry.free)
                return True
        return False

    def _hover(self, global_pos, free):
        view = self._target(global_pos)
        for other in (getattr(self.window, 'plan_view', None), getattr(self.window, 'pbr_view', None)):
            if other is not None and other is not view and getattr(other, 'carry', None) is self.carry:
                other.carry_leave()
        if view is None:
            self.window.statusBar().showMessage(self.carry.name + ': σύρε το πάνω στην κάτοψη ή στο 3D')
            return
        self.carry.free = free
        view.carry_move(self.carry, view.mapFromGlobal(global_pos))

    def _clear(self, carry):
        for view in (getattr(self.window, 'plan_view', None), getattr(self.window, 'pbr_view', None)):
            if view is not None and getattr(view, 'carry', None) is carry:
                view.carry_leave()


def install_tree_carry(window, tree):
    tree.setToolTip('Διπλό κλικ: τοποθέτηση · ή σύρε το στοιχείο πάνω στην κάτοψη / στο 3D')
    window._library_tree_carry = _TreeCarry(window, tree)
    return window._library_tree_carry


# ------------------------------------------------------------- 3D (JS)
def js_3d():
    """Βοηθοί για το 3D: σημείο/αντικείμενο κάτω από τον κέρσορα και φάντασμα κουτί."""
    from archforge.core.object_ops import ROTATABLE_KINDS, USER_PLACED_KINDS
    move = sorted(set(USER_PLACED_KINDS) | {'stair', 'ramp', 'wall', 'box', 'pod', 'floor', 'room', 'mechanical_part'})
    rot = sorted(set(ROTATABLE_KINDS) | {'stair', 'ramp', 'wall', 'box', 'pod'})
    return ('const MOVABLE_3D = ' + json.dumps(move) + ';\nconst ROTATABLE_3D = ' + json.dumps(rot) + ';\n' + r'''
window.afDropPick = function(cx, cy) {
  const rect = renderer.domElement.getBoundingClientRect();
  const ev = {clientX: rect.left + Number(cx), clientY: rect.top + Number(cy)};
  const p = pointOnHorizontalPlane(ev, workPlaneZ);
  const out = {x: p ? Number(p.x) : null, y: p ? Number(p.y) : null, id: "", kind: "", role: ""};
  const hit = pickForSelection(ev);
  if (hit) {
    out.id = hit.object.userData.entityId || "";
    out.kind = hit.object.userData.kind || "";
    const part = String(hit.object.userData.renderPart || "");
    const roles = hit.object.userData.surfaceRoles || [];
    out.role = part.indexOf(":") > 0 ? part.split(":").pop() : String(roles[hit.faceIndex] || "");
    out.hx = Number(hit.point.x); out.hy = Number(hit.point.y);
  }
  return JSON.stringify(out);
};
let afGhost = null;
window.afDropGhost = function(g) {
  if (afGhost) { scene.remove(afGhost); afGhost.geometry.dispose(); afGhost.material.dispose(); afGhost = null; }
  if (!g) return;
  const geo = new THREE.BoxGeometry(Number(g.w), Number(g.d), Number(g.h));
  const mat = new THREE.MeshBasicMaterial({color: g.ok ? 0x2a9a50 : 0xd23030, transparent: true, opacity: 0.38, depthWrite: false});
  afGhost = new THREE.Mesh(geo, mat);
  afGhost.position.set(Number(g.x), Number(g.y), Number(g.z) + Number(g.h) / 2);
  afGhost.rotation.z = Number(g.r) * Math.PI / 180;
  afGhost.renderOrder = 20;
  scene.add(afGhost);
};
''')
