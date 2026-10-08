"""Walls that move (joined walls, openings and objects follow) and split at a T (W2)."""
import copy
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.wall_edit import MoveWall, SplitWalls, junction_cuts, plan_move, split_at_point
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent
from archforge.kitchen.cabinets import default_params


def _draw(ctrl, pts):
    """Walls with the real tool, point to point (press, move, release per segment)."""
    ctrl.set_tool('wall')
    ctrl.grid = None
    ctrl.snap_enabled = False
    for a, b in zip(pts, pts[1:]):
        ctrl.pointer_down(PointerEvent(*a))
        ctrl.pointer_move(PointerEvent(*b))
        ctrl.pointer_up(PointerEvent(*b))


def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall']


def _wall_at(doc, a, b, tol=1e-6):
    for w in _walls(doc):
        p = w.params
        e = ((p['x1'], p['y1']), (p['x2'], p['y2']))
        if (math.dist(e[0], a) <= tol and math.dist(e[1], b) <= tol) or (math.dist(e[0], b) <= tol and math.dist(e[1], a) <= tol):
            return w
    raise AssertionError(f'no wall {a}–{b}: {[_ends(w) for w in _walls(doc)]}')


def _ends(w):
    p = w.params
    return (round(p['x1'], 6), round(p['y1'], 6)), (round(p['x2'], 6), round(p['y2'], 6))


def _length(w):
    p = w.params
    return math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1'])


def _rect(stack=None):
    doc = Document(); stack = CommandStack(doc); ctrl = PointerController(doc, stack)
    _draw(ctrl, [(0, 0), (8, 0), (8, 6), (0, 6), (0, 0)])
    return doc, stack, ctrl


def _snapshot(doc):
    d = doc.to_dict()
    return {'entities': sorted((e['id'], e['kind'], e['parent_id'], repr(sorted(e['params'].items()))) for e in d['entities'])}


def _junctions_closed(doc):
    """Every wall end sits on another wall's end or axis (no gaps opened by an edit)."""
    walls = _walls(doc)
    for w in walls:
        for q in _ends(w):
            ok = False
            for o in walls:
                if o.id == w.id:
                    continue
                a, b = _ends(o)
                L = math.dist(a, b)
                t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / L
                off = abs((q[0] - a[0]) * (b[1] - a[1]) - (q[1] - a[1]) * (b[0] - a[0])) / L
                if off <= 1e-6 and -1e-6 <= t <= L + 1e-6:
                    ok = True
            assert ok, f'wall end {q} of {_ends(w)} is loose'


# ------------------------------------------------------------------ split (T)

def test_partition_splits_8m_wall_at_3_2_into_3_2_and_4_8_with_same_properties():
    doc, stack, ctrl = _rect()
    south = _wall_at(doc, (0, 0), (8, 0))
    stack.execute(UpdateEntity(south.id, {'wall_type': 'brick_double_insulated', 'surface_materials': {'interior': 'paint_white'},
                                          'phase': 'new', 'height': 3.0}))
    before = copy.deepcopy(south.params)
    _draw(ctrl, [(3.2, 0), (3.2, 6)])
    walls = _walls(doc)
    assert len(walls) == 4 + 1 + 2                      # partition + one extra piece of south and of north
    a = _wall_at(doc, (0, 0), (3.2, 0)); b = _wall_at(doc, (3.2, 0), (8, 0))
    assert a.id == south.id and b.id != south.id
    assert _length(a) == pytest.approx(3.2) and _length(b) == pytest.approx(4.8)
    for piece in (a, b):
        for key in ('wall_type', 'thickness', 'height', 'surface_materials', 'phase', 'z'):
            assert piece.params[key] == before[key]
    # Independent afterwards: a different finish on one piece only.
    stack.execute(UpdateEntity(b.id, {'surface_materials': {'interior': 'paint_blue'}}))
    assert a.params['surface_materials'] == {'interior': 'paint_white'}
    # 8×6 + a partition = two rooms.
    assert len(doc.active_room_faces()) == 2
    _junctions_closed(doc)


def test_split_is_the_same_undo_step_as_the_new_wall_and_redo_keeps_ids():
    doc, stack, ctrl = _rect()
    before = _snapshot(doc)
    _draw(ctrl, [(3.2, 0), (3.2, 6)])
    after = _snapshot(doc)
    stack.undo()
    assert _snapshot(doc) == before
    stack.redo()
    assert _snapshot(doc) == after


def test_openings_go_to_their_piece_and_one_on_the_junction_blocks_that_split_with_a_warning():
    doc, stack, ctrl = _rect()
    south = _wall_at(doc, (0, 0), (8, 0)); north = _wall_at(doc, (8, 6), (0, 6))
    win = Entity('window', {'offset': 6.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=south.id)
    door = Entity('door', {'offset': 4.8, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=north.id)
    stack.execute(AddEntity(win)); stack.execute(AddEntity(door))
    world = lambda e: _world_centre(doc, e.id)
    w0, d0 = world(win), world(door)
    _draw(ctrl, [(3.2, 0), (3.2, 6)])                   # north runs 8→0: x=3.2 is offset 4.8, under the door
    piece = _wall_at(doc, (3.2, 0), (8, 0))
    assert doc.get(win.id).parent_id == piece.id
    assert doc.get(win.id).params['offset'] == pytest.approx(2.8)
    assert world(win) == pytest.approx(w0)
    assert doc.get(door.id).parent_id == north.id and world(door) == pytest.approx(d0)
    assert _length(doc.get(north.id)) == pytest.approx(8.0)  # not split under the door
    assert ctrl.last_warning and 'πόρτα' in ctrl.last_warning


def _world_centre(doc, oid):
    op = doc.get(oid); p = doc.get(op.parent_id).params
    L = math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1'])
    c = op.params['offset']
    return (p['x1'] + (p['x2'] - p['x1']) * c / L, p['y1'] + (p['y2'] - p['y1']) * c / L)


def test_crossing_walls_split_both():
    doc, stack, ctrl = _rect()
    _draw(ctrl, [(4, 0), (4, 6)])
    _draw(ctrl, [(0, 3), (8, 3)])                       # crosses the first partition
    assert len([w for w in _walls(doc) if abs(w.params['x1'] - 4) < 1e-9 and abs(w.params['x2'] - 4) < 1e-9]) == 2
    assert len([w for w in _walls(doc) if abs(w.params['y1'] - 3) < 1e-9 and abs(w.params['y2'] - 3) < 1e-9]) == 2
    assert len(doc.active_room_faces()) == 4
    _junctions_closed(doc)


def test_split_by_hand_at_a_point():
    doc, stack, ctrl = _rect()
    south = _wall_at(doc, (0, 0), (8, 0))
    stack.execute(SplitWalls(split_at_point(doc, south.id, 2.5, 0.05)))
    assert _length(doc.get(south.id)) == pytest.approx(2.5)
    assert len(doc.active_room_faces()) == 1


# ------------------------------------------------------------------ move

def test_moving_a_corner_wall_stretches_the_l_neighbours_and_keeps_room_id():
    doc, stack, ctrl = _rect()
    from archforge.architecture.room_identity import reconcile_room_bindings
    room_before = [rid for _f, rid in reconcile_room_bindings(doc, z=0.0)]
    east = _wall_at(doc, (8, 0), (8, 6))
    stack.execute(MoveWall(east.id, 0.5))                # + is right for a vertical wall
    assert _ends(doc.get(east.id)) in (((8.5, 0), (8.5, 6)), ((8.5, 6), (8.5, 0)))
    _wall_at(doc, (0, 0), (8.5, 0)); _wall_at(doc, (8.5, 6), (0, 6))
    _junctions_closed(doc)
    from archforge.architecture.room_identity import reconcile_room_bindings
    (face, rid), = reconcile_room_bindings(doc, z=0.0)
    assert rid == room_before[0]
    from archforge.architecture.topology import room_metrics
    assert room_metrics(face.polygon)['area'] == pytest.approx(8.5 * 6)


def test_moving_a_wall_with_a_t_moves_the_whole_straight_line_and_stretches_the_partition():
    doc, stack, ctrl = _rect()
    _draw(ctrl, [(3.2, 0), (3.2, 6)])
    from archforge.architecture.room_identity import reconcile_room_bindings
    rooms = {rid for _f, rid in reconcile_room_bindings(doc, z=0.0)}
    assert len(rooms) == 2
    north_piece = _wall_at(doc, (8, 6), (3.2, 6))
    stack.execute(MoveWall(north_piece.id, 1.0))        # up
    _wall_at(doc, (8, 7), (3.2, 7)); _wall_at(doc, (3.2, 7), (0, 7))
    _wall_at(doc, (3.2, 0), (3.2, 7)); _wall_at(doc, (8, 0), (8, 7)); _wall_at(doc, (0, 7), (0, 0))
    _junctions_closed(doc)
    assert {rid for _f, rid in reconcile_room_bindings(doc, z=0.0)} == rooms


def test_moving_the_partition_slides_the_split_point():
    doc, stack, ctrl = _rect()
    _draw(ctrl, [(3.2, 0), (3.2, 6)])
    part = _wall_at(doc, (3.2, 0), (3.2, 6))
    stack.execute(MoveWall(part.id, 0.4))
    _wall_at(doc, (3.6, 0), (3.6, 6))
    assert _length(_wall_at(doc, (0, 0), (3.6, 0))) == pytest.approx(3.6)
    assert _length(_wall_at(doc, (3.6, 0), (8, 0))) == pytest.approx(4.4)
    _junctions_closed(doc)


def test_openings_follow_their_wall_and_stay_put_on_stretched_walls():
    doc, stack, ctrl = _rect()
    east = _wall_at(doc, (8, 0), (8, 6)); north = _wall_at(doc, (8, 6), (0, 6))
    door = Entity('door', {'offset': 3.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=east.id)
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=north.id)
    stack.execute(AddEntity(door)); stack.execute(AddEntity(win))
    d0, w0 = _world_centre(doc, door.id), _world_centre(doc, win.id)
    stack.execute(MoveWall(east.id, 0.7))
    assert _world_centre(doc, door.id) == pytest.approx((d0[0] + 0.7, d0[1]))
    assert _world_centre(doc, win.id) == pytest.approx(w0)   # north's start moved, the window did not
    assert doc.get(win.id).params['offset'] == pytest.approx(2.7)


def test_cabinet_against_the_wall_rides_along_a_free_table_does_not():
    doc, stack, ctrl = _rect()
    east = _wall_at(doc, (8, 0), (8, 6))
    t = east.params['thickness']
    from archforge.kitchen.cabinets import wall_aligned
    x, y, rot = wall_aligned(doc, 7.5, 3.0, 0.6)
    cab = Entity('cabinet', default_params('base', x, y, 0.0, rot))
    table = Entity('library_object', {'x': 4.0, 'y': 3.0, 'z': 0.0, 'rotation': 0.0, 'width': 1.6, 'depth': 0.9,
                                       'height': 0.75, 'uniform': 1.0, 'asset': 'table'})
    socket = Entity('electrical_point', {'x': 8 - t / 2 - 0.01, 'y': 1.0, 'z': 0.3, 'point_type': 'socket'})
    for e in (cab, table, socket):
        stack.execute(AddEntity(e))
    assert x == pytest.approx(8 - t / 2 - 0.3)
    stack.execute(MoveWall(east.id, -0.5))
    assert doc.get(cab.id).params['x'] == pytest.approx(x - 0.5) and doc.get(cab.id).params['y'] == pytest.approx(y)
    assert doc.get(socket.id).params['x'] == pytest.approx(8 - t / 2 - 0.01 - 0.5)
    assert (doc.get(table.id).params['x'], doc.get(table.id).params['y']) == (4.0, 3.0)


def test_move_is_one_undo_step_and_undo_restores_exactly():
    doc, stack, ctrl = _rect()
    _draw(ctrl, [(3.2, 0), (3.2, 6)])
    east = _wall_at(doc, (8, 0), (8, 6))
    stack.execute(AddEntity(Entity('door', {'offset': 3.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=east.id)))
    before = _snapshot(doc); bindings = copy.deepcopy(doc.room_bindings)
    stack.execute(MoveWall(east.id, 1.2))
    after = _snapshot(doc)
    stack.undo()
    assert _snapshot(doc) == before and doc.room_bindings.keys() == bindings.keys()
    stack.redo()
    assert _snapshot(doc) == after


def test_move_refused_when_it_would_crush_a_wall_or_drop_an_opening():
    doc, stack, ctrl = _rect()
    east = _wall_at(doc, (8, 0), (8, 6)); south = _wall_at(doc, (0, 0), (8, 0))
    stack.execute(AddEntity(Entity('window', {'offset': 6.5, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=south.id)))
    with pytest.raises(ValueError):
        plan_move(doc, east.id, -9.0)
    with pytest.raises(ValueError, match='χωράει'):
        plan_move(doc, east.id, -1.0)                    # the window would hang past the shorter south wall


def test_existing_wall_in_renovation_does_not_move():
    doc, stack, ctrl = _rect()
    east = _wall_at(doc, (8, 0), (8, 6))
    stack.execute(UpdateEntity(east.id, {'phase': 'existing'}))
    with pytest.raises(ValueError, match='υφιστάμενος'):
        stack.execute(MoveWall(east.id, 0.3))


def test_drag_wall_body_with_the_pointer_controller():
    doc, stack, ctrl = _rect()
    ctrl.set_tool('select')
    east = _wall_at(doc, (8, 0), (8, 6))
    ctrl.begin_wall_move(east.id, 8.0, 3.0)
    ctrl.pointer_move(PointerEvent(8.437, 3.4))
    assert ctrl.preview.kind == 'wall-move' and ctrl.preview.geometry['distance'] == pytest.approx(0.44)
    ctrl.pointer_up(PointerEvent(8.437, 3.4))
    _wall_at(doc, (8.44, 0), (8.44, 6))
    assert len(stack.done) == 5
    from archforge.core.plan_scene import build_plan_frame
    ctrl.begin_wall_move(east.id, 8.44, 3.0)
    ctrl.pointer_move(PointerEvent(8.0, 3.0))
    labels = [dict(p.meta).get('text') for p in build_plan_frame(doc, ctrl.preview).primitives if p.role == 'wall-move-label']
    assert labels and '44' in labels[0]
    ctrl.cancel()


def test_save_load_round_trip_after_split_and_move():
    doc, stack, ctrl = _rect()
    _draw(ctrl, [(3.2, 0), (3.2, 6)])
    stack.execute(MoveWall(_wall_at(doc, (3.2, 0), (3.2, 6)).id, -0.2))
    loaded = Document.from_dict(copy.deepcopy(doc.to_dict()))
    assert _snapshot(loaded) == _snapshot(doc)
    assert len(loaded.active_room_faces()) == 2


def test_junction_cuts_ignore_corners():
    doc, stack, ctrl = _rect()
    for w in _walls(doc):
        assert junction_cuts(doc, w.id) == ({}, [])
