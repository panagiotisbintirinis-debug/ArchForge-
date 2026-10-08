"""OBJ1: move / rotate / delete (+ undo, save/load) for every kind the user places;
mirror, duplicate, door flips and open leaves in 3D."""
import math

import pytest

from archforge.architecture.pergola import pergola_entities
from archforge.architecture.railings import default_params as railing_params
from archforge.core import object_ops
from archforge.core.commands import AddEntities, AddEntity, CommandStack
from archforge.core.interaction import MoveTransaction, RotateTransaction
from archforge.core.model import Document, Entity
from archforge.kitchen.cabinets import default_params as cabinet_params


def _stair():
    return {'x': 0.0, 'y': 0.0, 'lower_z': 0.0, 'upper_z': 2.89, 'upper_floor_z': 2.89, 'upper_slab_thickness': 0.0,
            'layout': 'l', 'angle_deg': 0.0, 'width': 1.0, 'riser_count': 17, 'riser_height': 0.17,
            'tread_depth': 0.28, 'landing_depth': 1.0, 'turn_direction': 1, 'opening_margin': 0.05}


def _ramp():
    return {'x': 0.0, 'y': 0.0, 'lower_z': 0.0, 'upper_z': 0.5, 'upper_floor_z': 0.5, 'upper_slab_thickness': 0.0,
            'angle_deg': 0.0, 'width': 1.2, 'slope_pct': 6.0, 'run_length': 0.5 / 0.06, 'thickness': 0.2, 'opening_margin': 0.05}


def _column():
    return {'x': 2.0, 'y': 1.0, 'z': 0.0, 'width': .3, 'depth': .3, 'height': 2.7, 'rotation': 0.0, 'role': 'structural',
            'construction': 'reinforced_concrete', 'section': 'rectangular', 'base_level': 'Ground', 'top_level': 'Unassigned'}


def _beam():
    return {'x1': 0.0, 'y1': 3.0, 'x2': 4.0, 'y2': 3.0, 'z': 2.4, 'width': .25, 'height': .5, 'role': 'structural',
            'construction': 'reinforced_concrete', 'section': 'rectangular', 'level': 'Ground'}


def _placed():
    """One entity of each user-placed kind: (kind, Entity)."""
    lib = {'x': 1.0, 'y': 1.0, 'z': 0.0, 'rotation': 0.0, 'width': 2.2, 'depth': .95, 'height': .8, 'uniform': 1.0,
           'asset': 'missing-asset'}
    pts = {'x': 1.0, 'y': 2.0, 'z': 0.0}
    return [
        Entity('library_object', lib, name='Καναπές'),
        Entity('cabinet', cabinet_params('base', 1.0, 1.0, rotation=0.0)),
        Entity('kitchen_part', {'x': 1.0, 'y': 1.0, 'z': 0.0, 'width': .6, 'depth': .6, 'height': .9, 'rotation': 0.0,
                                'role': 'base', 'run_id': 'manual', 'roughness': .5, 'metallic': 0.0}),
        Entity('plumbing_point', dict(pts, point_type='basin')),
        Entity('electrical_point', dict(pts, point_type='socket', power_w=200.0)),
        Entity('ventilation_point', dict(pts, point_type='bath_fan', outlet='roof', airflow=15.0)),
        Entity('drainage_point', dict(pts, point_type='floor_drain', rain_area=0.0)),
        Entity('plant', {'x': 3.0, 'y': 3.0, 'z': 0.0, 'height': 4.0, 'canopy': 3.0, 'species': 'tree'}),
        Entity('stair', _stair()),
        Entity('ramp', _ramp()),
        Entity('railing', railing_params('balusters', [[0.0, 5.0], [3.0, 5.0]])),
        Entity('structural_column', _column()),
        Entity('structural_beam', _beam()),
    ]


def _plan_center(doc, eid):
    return object_ops.pivot(doc, object_ops.group_ids(doc, eid))


@pytest.mark.parametrize('index', range(13))
def test_every_user_placed_kind_moves_rotates_deletes_with_undo(index, tmp_path):
    doc = Document(); stack = CommandStack(doc)
    e = _placed()[index]
    stack.execute(AddEntity(e))
    eid = e.id
    assert e.kind in object_ops.USER_PLACED_KINDS
    before = dict(doc.get(eid).params)
    # Move: one command, one undo.
    x0, y0 = _plan_center(doc, eid)
    stack.execute(object_ops.move_command(doc, eid, 1.0, -0.5))
    x1, y1 = _plan_center(doc, eid)
    assert (x1 - x0, y1 - y0) == pytest.approx((1.0, -0.5), abs=1e-6)
    stack.undo()
    assert doc.get(eid).params == before
    # Rotate 90° through the live transaction (as the plan / 3D handles do), then undo.
    tx = RotateTransaction(doc, stack, eid, angle_increment=15.0)
    px, py = tx.pivot
    tx.update_pointer(px, py + 1.0, start_angle_deg=0.0, snap=True)
    assert tx.angle == pytest.approx(90.0)
    tx.commit()
    after = doc.get(eid).params
    assert after != before or e.kind in object_ops.POINT_KINDS + ('plant',)
    if e.kind in object_ops.OWN_ROTATION:
        assert float(after['rotation']) == pytest.approx((float(before.get('rotation', 0.0)) + 90.0) % 360.0)
    assert _plan_center(doc, eid) == pytest.approx((px, py), abs=1e-6)       # turned in place
    # Saved and loaded with the turn.
    path = tmp_path / 'p.archforge'
    doc.save(path)
    loaded = Document.load(path)
    for k, v in after.items():
        if isinstance(v, float):
            assert float(loaded.get(eid).params[k]) == pytest.approx(v)
    stack.undo()
    assert doc.get(eid).params == before
    # Delete and undo.
    stack.execute(object_ops.delete_command(doc, eid))
    assert eid not in doc.entities
    stack.undo()
    assert doc.get(eid).params == before


def test_rotate_handle_sits_in_front_of_the_object():
    doc = Document()
    e = Entity('library_object', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rotation': 90.0, 'width': 2.0, 'depth': 1.0,
                                  'height': .8, 'uniform': 1.0, 'asset': 'x'})
    doc.add(e)
    hx, hy = object_ops.rotate_handle_point(doc, e.id)
    # Turned 90°: the front (local -Y) faces +X.
    assert (hx, hy) == pytest.approx((0.5 + .35, 0.0))
    doc.select([e.id])
    from archforge.core.plan_scene import selection_handles
    assert any(h.handle == 'rotate' for h in selection_handles(doc))


def test_pergola_moves_and_turns_as_one():
    doc = Document(); stack = CommandStack(doc)
    parts, _report = pergola_entities(doc, 0.0, 0.0, 3.0, 4.0)
    stack.execute(AddEntities(parts))
    ids = [p.id for p in parts]
    first = next(i for i in ids if doc.get(i).kind == 'structural_column')
    group = object_ops.group_ids(doc, first)
    assert set(group) == set(doc.entities)
    tx = MoveTransaction(doc, stack, [first], origin=(0.0, 0.0, 0.0))
    assert set(tx.ids) == set(doc.entities)
    stack.execute(object_ops.rotate_command(doc, first, 90.0))
    x0, y0, x1, y1 = object_ops._bbox_of([q for i in ids for q in object_ops.plan_outline(doc, i)])
    assert (x1 - x0) == pytest.approx(4.0 + .12, abs=.05) and (y1 - y0) == pytest.approx(3.0 + .12, abs=.05)
    stack.undo()


def test_existing_column_is_not_moved_or_turned():
    doc = Document(); stack = CommandStack(doc)
    col = Entity('structural_column', dict(_column(), phase='existing'))
    stack.execute(AddEntity(col))
    with pytest.raises(ValueError):
        stack.execute(object_ops.move_command(doc, col.id, 1.0, 0.0))
    with pytest.raises(ValueError):
        stack.execute(object_ops.rotate_command(doc, col.id, 90.0))


def test_mirror_and_duplicate_are_one_undo_each():
    doc = Document(); stack = CommandStack(doc)
    sofa = Entity('library_object', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rotation': 0.0, 'width': 2.0, 'depth': 1.0,
                                     'height': .8, 'uniform': 1.0, 'asset': 'x'})
    stack.execute(AddEntity(sofa))
    stack.execute(object_ops.mirror_command(doc, sofa.id))
    assert doc.get(sofa.id).params['mirror'] == 1.0
    stack.undo()
    assert not doc.get(sofa.id).params.get('mirror')
    command, new_ids = object_ops.duplicate_command(doc, sofa.id)
    stack.execute(command)
    assert len(doc.entities) == 2 and doc.get(new_ids[0]).params['x'] == pytest.approx(2.0)
    stack.undo()
    assert list(doc.entities) == [sofa.id]
    stair = Entity('stair', _stair())
    stack.execute(AddEntity(stair))
    stack.execute(object_ops.mirror_command(doc, stair.id))
    assert doc.get(stair.id).params['turn_direction'] == -1


def _door_doc(**extra):
    doc = Document(); stack = CommandStack(doc)
    wall = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.8, 'thickness': .2})
    stack.execute(AddEntity(wall))
    door = Entity('door', dict({'offset': 2.0, 'width': .9, 'height': 2.1, 'sill': 0.0, 'opening_type': 'interior_flush',
                                'hinge': 'left', 'swing': 'in'}, **extra), parent_id=wall.id)
    stack.execute(AddEntity(door))
    return doc, stack, door


def test_door_flips_hinge_and_swing_with_one_undo_and_handle_follows():
    from archforge.core.plan_scene import selection_handles
    doc, stack, door = _door_doc()
    doc.select([door.id])
    h0 = next(h for h in selection_handles(doc) if h.handle == 'flip_swing')
    stack.execute(object_ops.flip_command(doc, door.id, 'swing'))
    assert doc.get(door.id).params['swing'] == 'out'
    h1 = next(h for h in selection_handles(doc) if h.handle == 'flip_swing')
    assert h0.y * h1.y < 0                                  # the handle went to the other side
    stack.execute(object_ops.flip_command(doc, door.id, 'hinge'))
    assert doc.get(door.id).params['hinge'] == 'right'
    stack.undo()
    stack.undo()
    assert doc.get(door.id).params['swing'] == 'in' and doc.get(door.id).params['hinge'] == 'left'


@pytest.mark.parametrize('typ,leaves', [('interior_flush', 1), ('casement', 2), ('sliding', 2), ('pocket', 1)])
def test_open_leaves_turn_about_the_hinge_or_slide(typ, leaves):
    from archforge.architecture.joinery import joinery_boxes, joinery_boxes_posed, pose_point
    kind = 'window' if typ in ('casement', 'sliding') else 'door'
    p = {'width': 1.2 if leaves > 1 else .9, 'height': 2.1 if kind == 'door' else 1.2, 'opening_type': typ,
         'leaves': leaves, 'hinge': 'left', 'swing': 'in'}
    closed = joinery_boxes(kind, p, .25, 1)
    posed = joinery_boxes_posed(kind, p, .25, 1, 0.0)
    assert [(r, lo, hi) for r, lo, hi, _pose in posed] == closed and all(q[3] is None for q in posed)
    opened = joinery_boxes_posed(kind, p, .25, 1, 90.0)
    moving = [q for q in opened if q[3] is not None]
    assert moving, 'no leaf moves'
    assert all(q[0] in ('leaf', 'glass', 'handle') for q in moving)
    for role, lo, hi, pose in moving:
        if pose[0] == 'rot':
            # Swing in (sign_in +1): the free edge ends up on the +s (inside) side, a leaf width away.
            u, s = pose_point(pose, (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2)
            assert s > hi[1] - 1e-6
        else:
            assert abs(pose[1]) > .2


def test_open_angle_is_validated_and_show_open_changes_3d():
    from archforge.rendering import fixtures
    doc, stack, door = _door_doc()
    with pytest.raises(ValueError):
        doc.update(door.id, {'open_angle': 400.0})
    closed = fixtures.opening_fixture_parts(doc, door)
    fixtures.set_show_open(True)
    try:
        opened = fixtures.opening_fixture_parts(doc, door)
    finally:
        fixtures.set_show_open(False)
    leaf = lambda parts: next(v for k, v, _t in parts if k == 'door_leaf')
    assert max(q[1] for q in leaf(opened)) - max(q[1] for q in leaf(closed)) > .5     # the leaf left the wall
    doc.update(door.id, {'open_angle': 45.0})
    assert fixtures.display_angle(doc.get(door.id).params) == 45.0
