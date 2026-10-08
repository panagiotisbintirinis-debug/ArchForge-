"""OBJ1 with the mouse: Library drag & drop (QMimeData) onto the plan, rotation handle,
body drag, door flip handle, mouse-menu actions and the visual Object Modifier."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent, QKeyEvent, QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QApplication

from archforge.core.commands import AddEntity
from archforge.core.model import Document, Entity
from archforge.library import assets
from archforge.ui.library_drag import LibraryCarry, mime_for


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    assets._CACHE.clear()


@pytest.fixture
def window():
    from archforge.library.catalog import seed_core_library
    from archforge.ui.main_window import MainWindow
    seed_core_library()
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    yield w
    w.hide()          # no close(): it would ask to save the changes


def _asset(name):
    return next(r['id'] for r in assets.list_assets() if r['name'].startswith(name))


def _vp(view, x, y):
    return view.mapFromScene(QPointF(x, y))


def _drag(view, action, x, y, drop=True):
    mime = mime_for(action)
    pos = QPointF(_vp(view, x, y))
    enter = QDragEnterEvent(pos.toPoint(), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), enter)
    move = QDragMoveEvent(pos.toPoint(), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(view.viewport(), move)
    if drop:
        ev = QDropEvent(pos, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(view.viewport(), ev)
    QApplication.processEvents()


def _mouse(view, kind, x, y, buttons=Qt.MouseButton.LeftButton, mods=Qt.KeyboardModifier.NoModifier):
    t = {'press': QEvent.Type.MouseButtonPress, 'move': QEvent.Type.MouseMove, 'release': QEvent.Type.MouseButtonRelease}[kind]
    button = Qt.MouseButton.NoButton if kind == 'move' else Qt.MouseButton.LeftButton
    held = Qt.MouseButton.NoButton if kind == 'release' else buttons
    ev = QMouseEvent(t, QPointF(_vp(view, x, y)), button, held, mods)
    QApplication.sendEvent(view.viewport(), ev)
    QApplication.processEvents()


def _wall(window, x1=0.0, y1=0.0, x2=5.0, y2=0.0):
    wall = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.8, 'thickness': .2})
    window.stack.execute(AddEntity(wall))
    return wall


def _new(window, before, kind):
    return [e for i, e in window.doc.entities.items() if i not in before and e.kind == kind]


def test_drop_sofa_from_library_snaps_back_to_wall_one_undo(window):
    plan = window.plan_view
    _wall(window)
    before = set(window.doc.entities)
    sofa = _asset('Καναπές τριθέσιος')
    _drag(plan, ('asset', sofa), 2.5, 0.9, drop=False)
    assert plan.carry is not None and plan.carry.ghost['snapped'] == 'wall'
    ghost = plan.carry.ghost['params']
    assert ghost['y'] == pytest.approx(0.1 + 0.45, abs=0.02)            # back on the wall face
    _drag(plan, ('asset', sofa), 2.5, 0.9)
    (obj,) = _new(window, before, 'library_object')
    assert obj.params['y'] == pytest.approx(0.55, abs=0.02)
    assert window.doc.selection == [obj.id] and plan.carry is None
    window.stack.undo()
    assert obj.id not in window.doc.entities


def test_wheel_and_r_turn_the_ghost_esc_cancels(window):
    plan = window.plan_view
    bed = _asset('Διπλό κρεβάτι 160')
    before = set(window.doc.entities)
    _drag(plan, ('asset', bed), 3.0, 3.0, drop=False)
    wheel = QWheelEvent(QPointF(_vp(plan, 3.0, 3.0)), QPointF(plan.viewport().mapToGlobal(_vp(plan, 3.0, 3.0))),
                        QPoint(0, 0), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(plan.viewport(), wheel)
    assert plan.carry.ghost['params']['rotation'] == pytest.approx(15.0)
    QApplication.sendEvent(plan, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_R, Qt.KeyboardModifier.NoModifier))
    assert plan.carry.ghost['params']['rotation'] == pytest.approx(105.0)
    QApplication.sendEvent(plan, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
    assert plan.carry is None and set(window.doc.entities) == before


def test_drop_cabinet_door_and_material(window):
    plan = window.plan_view
    wall = _wall(window)
    label = next(iter(window._kitchen_defs))
    before = set(window.doc.entities)
    _drag(plan, ('cabinet', label), 1.0, 0.6)
    assert len(_new(window, before, 'cabinet')) == 1
    from archforge.architecture.joinery import PRESETS
    door_key = next(k for k, kind, *_ in PRESETS if kind == 'door')
    _drag(plan, ('opening', door_key), 3.5, 0.05)
    doors = _new(window, before, 'door')
    assert len(doors) == 1 and doors[0].parent_id == wall.id
    # A material dropped on the wall paints the side under the cursor (side B: below the axis).
    _drag(plan, ('material', 'plaster_warm'), 4.6, -0.05)
    assert window.doc.get(wall.id).params['surface_materials'] == {'interior': 'plaster_warm'}
    window.stack.undo()
    assert not window.doc.get(wall.id).params.get('surface_materials')


def test_rotate_handle_body_drag_and_delete(window):
    plan = window.plan_view
    obj = Entity('library_object', {'x': 2.0, 'y': 2.0, 'z': 0.0, 'rotation': 0.0, 'width': 1.0, 'depth': .6,
                                    'height': .8, 'uniform': 1.0, 'asset': _asset('Νιπτήρας με κολόνα')}, name='Νιπτήρας')
    window.stack.execute(AddEntity(obj))
    window.doc.select([obj.id])
    plan.set_tool('select')
    plan.redraw()
    handle = next(h for h in plan._handle_items.values() if h.handle == 'rotate')
    assert (handle.x, handle.y) == pytest.approx((2.0, 2.0 - .3 - .35))
    _mouse(plan, 'press', handle.x, handle.y)
    _mouse(plan, 'move', 2.66, 2.0)               # quarter turn about the centre (+90°)
    assert plan.controller.preview.kind == 'rotate'
    _mouse(plan, 'release', 2.66, 2.0)
    assert window.doc.get(obj.id).params['rotation'] == pytest.approx(90.0)
    assert plan.controller.tool == 'select'
    # Drag the body: one move.
    _mouse(plan, 'press', 2.0, 2.0)
    _mouse(plan, 'move', 2.5, 2.0)
    _mouse(plan, 'move', 3.0, 2.5)
    _mouse(plan, 'release', 3.0, 2.5)
    assert (window.doc.get(obj.id).params['x'], window.doc.get(obj.id).params['y']) == pytest.approx((3.0, 2.5), abs=.06)
    window.stack.undo()
    assert window.doc.get(obj.id).params['x'] == pytest.approx(2.0)
    window.stack.undo()
    assert window.doc.get(obj.id).params['rotation'] == pytest.approx(0.0)
    window.doc.select([obj.id])
    window._delete_selection()
    assert obj.id not in window.doc.entities
    window.stack.undo()
    assert obj.id in window.doc.entities


def test_mouse_menu_object_actions_and_door_flip_handle(window):
    from archforge.ui.marking_menu import build_menu, run
    plan = window.plan_view
    obj = Entity('library_object', {'x': 2.0, 'y': 2.0, 'z': 0.0, 'rotation': 0.0, 'width': 1.0, 'depth': .6,
                                    'height': .8, 'uniform': 1.0, 'asset': 'x'}, name='Τραπέζι')
    window.stack.execute(AddEntity(obj))
    for view in ('plan', 'pbr'):
        ids = [e['id'] for e in build_menu(window, view, obj.id)['entries']]
        assert {'mm:obj:rot90', 'mm:obj:mirror', 'mm:obj:duplicate', 'delete'} <= set(ids)
    run(window, 'plan', obj.id, 'mm:obj:rot90')
    assert window.doc.get(obj.id).params['rotation'] == pytest.approx(90.0)
    n = len(window.doc.entities)
    run(window, 'plan', obj.id, 'mm:obj:duplicate')
    assert len(window.doc.entities) == n + 1
    window.stack.undo()
    window.stack.undo()
    assert window.doc.get(obj.id).params['rotation'] == pytest.approx(0.0) and len(window.doc.entities) == n
    wall = _wall(window, 0.0, 5.0, 5.0, 5.0)
    door = Entity('door', {'offset': 2.0, 'width': .9, 'height': 2.1, 'sill': 0.0, 'opening_type': 'interior_flush',
                           'hinge': 'left', 'swing': 'in'}, parent_id=wall.id)
    window.stack.execute(AddEntity(door))
    ids = [e['id'] for e in build_menu(window, 'pbr', door.id)['entries']]
    assert {'mm:obj:hinge', 'mm:obj:swing'} <= set(ids)
    run(window, 'pbr', door.id, 'mm:obj:hinge')
    assert window.doc.get(door.id).params['hinge'] == 'right'
    window.doc.select([door.id])
    plan.redraw()
    flip = next(h for h in plan._handle_items.values() if h.handle == 'flip_swing')
    _mouse(plan, 'press', flip.x, flip.y)
    _mouse(plan, 'release', flip.x, flip.y)
    assert window.doc.get(door.id).params['swing'] == 'out'
    window.stack.undo()
    assert window.doc.get(door.id).params['swing'] == 'in'
    # «Ανοιχτά κουφώματα στο 3D» lives in the view menus; off by default.
    from archforge.rendering import fixtures
    assert window.open_joinery_action.isChecked() is False
    window.open_joinery_action.setChecked(True)
    assert fixtures.SHOW_OPEN is True
    window.open_joinery_action.setChecked(False)
    assert fixtures.SHOW_OPEN is False


def test_visual_object_modifier_handles_parts_and_palette(window, tmp_path):
    obj = Entity('library_object', {'x': 2.0, 'y': 2.0, 'z': 0.0, 'rotation': 0.0, 'width': 2.1, 'depth': .9,
                                    'height': .85, 'uniform': 1.0, 'asset': _asset('Καναπές τριθέσιος')}, name='Καναπές')
    window.stack.execute(AddEntity(obj))
    dialog = window._open_object_modifier(obj.id)
    QApplication.processEvents()
    preview = dialog.preview
    preview.repaint()
    assert preview._screen_tris and set(preview._handles) == {'width', 'depth', 'height'}
    # Drag the width handle outwards: live in the preview, one UpdateEntity on release.
    hx, hy = preview._handles['width']
    (_a, (ax, ay)) = preview.handle_points()['width']
    press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(hx, hy), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(preview, press)
    move = QMouseEvent(QEvent.Type.MouseMove, QPointF(hx + ax * .1, hy + ay * .1), Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(preview, move)
    assert window.doc.get(obj.id).params['width'] == pytest.approx(2.1)          # not yet in the project
    assert preview.sizes()['width'] == pytest.approx(2.3, abs=.02)
    release = QMouseEvent(QEvent.Type.MouseButtonRelease, QPointF(hx + ax * .1, hy + ay * .1), Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(preview, release)
    p = window.doc.get(obj.id).params
    assert p['width'] == pytest.approx(2.3, abs=.02)
    assert p['depth'] == pytest.approx(.9 * p['width'] / 2.1, abs=.01)          # proportions locked
    window.stack.undo()
    assert window.doc.get(obj.id).params['width'] == pytest.approx(2.1)
    # Click a part in the preview, then a palette swatch: that part gets the material.
    preview.repaint()
    poly, role = preview._screen_tris[0]
    c = poly.boundingRect().center()
    centre = next((QPointF(q) for q in (c, poly.at(0) * .34 + poly.at(1) * .33 + poly.at(2) * .33)
                   if preview.part_at(q.x(), q.y()) == role), poly.at(0) * .34 + poly.at(1) * .33 + poly.at(2) * .33)
    for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
        QApplication.sendEvent(preview, QMouseEvent(kind, centre, Qt.MouseButton.LeftButton,
                                                    Qt.MouseButton.LeftButton if kind == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
                                                    Qt.KeyboardModifier.NoModifier))
    picked = preview.selected_role
    assert picked and picked.startswith('part')
    dialog.palette.setCurrentRow(0)
    material = dialog.palette.item(0).data(Qt.ItemDataRole.UserRole)
    dialog.apply_palette(material)
    assert window.doc.get(obj.id).params['surface_materials'] == {picked: material}
    path = tmp_path / 'm.archforge'
    window.doc.save(path)
    assert Document.load(path).get(obj.id).params['surface_materials'] == {picked: material}
    dialog.close()


def test_library_carry_for_mep_point_and_railing(window):
    before = set(window.doc.entities)
    carry = LibraryCarry(window, ('tool', 'elec_socket'))
    carry.move(1.0, 1.0)
    carry.drop(1.0, 1.0)
    assert len(_new(window, before, 'electrical_point')) == 1
    from archforge.architecture.railings import TYPES
    carry = LibraryCarry(window, ('railing', next(iter(TYPES))))
    carry.turn_by(90.0)
    carry.drop(4.0, 4.0)
    (railing,) = _new(window, before, 'railing')
    (x0, y0), (x1, y1) = [q[:2] for q in railing.params['points']]
    assert abs(x1 - x0) < 1e-6 and abs(y1 - y0) == pytest.approx(2.0)
