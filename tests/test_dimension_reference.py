"""Walls drawn on their outside (new) or inside (renovation) face, stored on the axis."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent


def _brief(stack, **answers):
    stack.execute(AddEntity(Entity('project_brief', {'project_type': 'new', 'wall_system': 'stone_bearing',
                                                     'measure': 'exterior', 'floor_system': 'rc_slab', **answers})))


def _draw(ctrl, pts):
    """Draw walls with the real tool, point to point (each segment: press, move, release)."""
    ctrl.set_tool('wall')
    ctrl.grid = None
    ctrl.snap_enabled = False
    for a, b in zip(pts, pts[1:]):
        ctrl.pointer_down(PointerEvent(*a))
        ctrl.pointer_move(PointerEvent(*b))
        ctrl.pointer_up(PointerEvent(*b))


def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall']


def _bbox_outer(doc):
    xs, ys = [], []
    for w in _walls(doc):
        p = w.params
        t = p['thickness'] / 2
        xs += [p['x1'] - t, p['x1'] + t, p['x2'] - t, p['x2'] + t]
        ys += [p['y1'] - t, p['y1'] + t, p['y2'] - t, p['y2'] + t]
    return min(xs), min(ys), max(xs), max(ys)


def test_exterior_measured_10x10_stone_is_10x10_outside_and_9x9_inside():
    from archforge.quantities.takeoff import take_off
    doc = Document(); st = CommandStack(doc); _brief(st, wall_system='stone_bearing')
    ctrl = PointerController(doc, st)
    _draw(ctrl, [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    walls = _walls(doc)
    assert len(walls) == 4 and all(w.params.get('reference_applied') for w in walls)
    t = walls[0].params['thickness']
    assert t == pytest.approx(0.54)
    x0, y0, x1, y1 = _bbox_outer(doc)
    assert (x0, y0, x1, y1) == pytest.approx((0.0, 0.0, 10.0, 10.0), abs=1e-6)     # the drawn lines are the outside
    inside = take_off(doc)['rooms'][0]
    assert inside['floor_m2'] == pytest.approx((10 - 2 * t) ** 2, abs=0.01)
    # One undo removes the closing wall and its corner; the others stay on their faces (owner 21/10: the outline
    # is on its faces while it is drawn, not only once it closes).
    st.undo()
    assert len(_walls(doc)) == 3 and all(w.params.get('reference_applied') for w in _walls(doc))


def test_interior_measured_room_keeps_its_inside_size():
    doc = Document(); st = CommandStack(doc)
    _brief(st, project_type='renovation', measure='interior', wall_system='brick_double_insulated')
    ctrl = PointerController(doc, st)
    _draw(ctrl, [(0, 0), (4, 0), (4, 3), (0, 3), (0, 0)])
    from archforge.quantities.takeoff import take_off
    room = take_off(doc)['rooms'][0]
    assert room['floor_m2'] == pytest.approx(12.0, abs=0.01)                        # 4×3 measured inside


def test_partition_and_window_follow_the_moved_walls():
    doc = Document(); st = CommandStack(doc); _brief(st, wall_system='brick_double_insulated')
    ctrl = PointerController(doc, st)
    _draw(ctrl, [(0, 0), (8, 0)])
    south = _walls(doc)[0]
    assert south.params['y1'] == 0 and south.params['y2'] == 0                       # alone: on its axis, as drawn
    win = Entity('window', {'offset': 4.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=south.id)
    st.execute(AddEntity(win))
    # Owner 21/10: the outline goes to its faces while it is drawn (not only when it closes).
    _draw(ctrl, [(8, 0), (8, 6), (0, 6), (0, 0)])
    t = south.params['thickness']
    s = doc.get(south.id).params
    assert s['y1'] == pytest.approx(t / 2) and s['y2'] == pytest.approx(t / 2)       # moved inwards
    assert len(_walls(doc)) == 4 and all(w.params.get('reference_applied') for w in _walls(doc))
    # The window keeps its place along its wall; the drawn line stays the outer face.
    w = doc.get(win.id).params
    assert s['x1'] + w['offset'] == pytest.approx(4.0 + t / 2)
    assert _bbox_outer(doc) == pytest.approx((0.0, 0.0, 8.0, 6.0), abs=1e-6)


def test_without_brief_walls_stay_on_their_axis():
    doc = Document(); st = CommandStack(doc)
    ctrl = PointerController(doc, st)
    _draw(ctrl, [(0, 0), (5, 0), (5, 5), (0, 5), (0, 0)])
    assert _bbox_outer(doc)[0] == pytest.approx(-0.075)                              # axis drawing, 15 cm
