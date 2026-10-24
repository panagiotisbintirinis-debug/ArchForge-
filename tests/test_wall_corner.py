"""«Γωνία» (handoff 24/10, Revit Trim/Extend to Corner): click two walls → they meet in a corner.

Each wall goes to the crossing of the two axes; the part of a wall that was clicked is the part that stays.
"""
import copy
import math

import pytest

from archforge.architecture.topology import polygon_area
from archforge.architecture.wall_edit import CornerWalls, plan_corner
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity


def _wall(stack, a, b, **extra):
    params = {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 3.0, 'thickness': 0.25}
    params.update(extra)
    e = Entity('wall', params)
    stack.execute(AddEntity(e))
    return e.id


def _ends(doc, wid):
    p = doc.get(wid).params
    return (round(p['x1'], 6), round(p['y1'], 6)), (round(p['x2'], 6), round(p['y2'], 6))


def _doc():
    doc = Document()
    return doc, CommandStack(doc)


def test_two_walls_that_do_not_reach_meet_in_a_corner():
    doc, stack = _doc()
    south = _wall(stack, (0, 0), (5.6, 0))                # stops short of the east wall
    east = _wall(stack, (6, 0.4), (6, 4))                 # starts above the south wall
    stack.execute(CornerWalls(south, (2, 0), east, (6, 3)))
    assert _ends(doc, south) == ((0, 0), (6, 0))
    assert _ends(doc, east) == ((6, 0), (6, 4))


def test_overshooting_walls_are_trimmed_and_the_clicked_part_stays():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (7, 0))                      # runs 1 m past x = 6
    b = _wall(stack, (6, -1), (6, 4))                     # runs 1 m below y = 0
    stack.execute(CornerWalls(a, (2, 0), b, (6, 3)))      # clicked the long parts
    assert _ends(doc, a) == ((0, 0), (6, 0))
    assert _ends(doc, b) == ((6, 0), (6, 4))


def test_clicking_the_other_side_keeps_that_side():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (7, 0))
    b = _wall(stack, (6, -1), (6, 4))
    stack.execute(CornerWalls(a, (6.6, 0), b, (6, -0.5)))  # the short stubs past the crossing
    assert _ends(doc, a) == ((6, 0), (7, 0))
    assert _ends(doc, b) == ((6, -1), (6, 0))


def test_slanted_wall_meets_at_the_axis_crossing():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (4, 0))
    b = _wall(stack, (5, 1), (7, 3))                      # 45°, its line crosses y = 0 at x = 4
    stack.execute(CornerWalls(a, (1, 0), b, (6, 2)))
    assert _ends(doc, a) == ((0, 0), (4, 0))
    assert _ends(doc, b) == ((4, 0), (7, 3))


def test_openings_stay_where_they_are_in_the_world():
    doc, stack = _doc()
    a = _wall(stack, (1, 0), (6, 0))
    b = _wall(stack, (6.5, 0.5), (6.5, 4))
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=a)
    door = Entity('door', {'offset': 2.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=b)
    stack.execute(AddEntity(win)); stack.execute(AddEntity(door))
    stack.execute(CornerWalls(a, (2, 0), b, (6.5, 3)))
    # a keeps its start: the window offset is unchanged; b's start moved down 0.5 m: the door's offset grows by 0.5.
    assert doc.get(win.id).params['offset'] == pytest.approx(2.0)
    assert doc.get(door.id).params['offset'] == pytest.approx(2.5)


def test_opening_on_the_part_cut_away_refuses():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (8, 0))
    b = _wall(stack, (6, -1), (6, 4))
    stack.execute(AddEntity(Entity('window', {'offset': 7.0, 'width': 1.0, 'height': 1.2, 'sill': 0.9}, parent_id=a)))
    with pytest.raises(ValueError, match='παράθυρο'):
        plan_corner(doc, a, (2, 0), b, (6, 3))


def test_refusals_parallel_same_existing_locked_other_storey():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (5, 0))
    p = _wall(stack, (0, 2), (5, 2))
    with pytest.raises(ValueError, match='παράλληλοι'):
        plan_corner(doc, a, (1, 0), p, (1, 2))
    with pytest.raises(ValueError, match='δύο διαφορετικούς'):
        plan_corner(doc, a, (1, 0), a, (3, 0))
    old = _wall(stack, (6, 1), (6, 4), phase='existing')
    with pytest.raises(ValueError, match='υφιστάμενος'):
        plan_corner(doc, a, (1, 0), old, (6, 3))
    up = _wall(stack, (6, 1), (6, 4), z=3.0)
    with pytest.raises(ValueError, match='όροφο'):
        plan_corner(doc, a, (1, 0), up, (6, 3))
    near = _wall(stack, (5.02, 0.5), (5.02, 4))
    stack.execute(UpdateEntity(near, {}))
    doc.get(near).locked = True
    with pytest.raises(ValueError, match='κλειδωμένος'):
        plan_corner(doc, a, (1, 0), near, (5.02, 3))


def test_corner_is_one_undo_step_and_redo_repeats_it():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (5.6, 0))
    b = _wall(stack, (6, 0.4), (6, 4))
    before = copy.deepcopy(doc.to_dict())
    stack.execute(CornerWalls(a, (2, 0), b, (6, 3)))
    after = (_ends(doc, a), _ends(doc, b))
    stack.undo()
    assert doc.to_dict()['entities'] == before['entities']
    stack.redo()
    assert (_ends(doc, a), _ends(doc, b)) == after


def test_four_walls_cornered_by_hand_close_a_room():
    doc, stack = _doc()
    s = _wall(stack, (0.3, 0), (5.7, 0))
    e = _wall(stack, (6, 0.2), (6, 3.9))
    n = _wall(stack, (6.4, 4), (-0.2, 4))                 # overshoots both ends
    w = _wall(stack, (0, 4.3), (0, 0.4))
    for (p, cp), (q, cq) in (((s, (3, 0)), (e, (6, 2))), ((e, (6, 2)), (n, (3, 4))),
                             ((n, (3, 4)), (w, (0, 2))), ((w, (0, 2)), (s, (3, 0)))):
        stack.execute(CornerWalls(p, cp, q, cq))
    corners = {pt for wid in (s, e, n, w) for pt in _ends(doc, wid)}
    assert corners == {(0, 0), (6, 0), (6, 4), (0, 4)}        # every end at a shared corner, nothing sticks out
    faces = doc.active_room_faces()
    assert len(faces) == 1
    assert polygon_area(faces[0].polygon) == pytest.approx(24.0)


def test_save_load_after_corner():
    doc, stack = _doc()
    a = _wall(stack, (0, 0), (5.6, 0))
    b = _wall(stack, (6, 0.4), (6, 4))
    stack.execute(CornerWalls(a, (2, 0), b, (6, 3)))
    loaded = Document.from_dict(copy.deepcopy(doc.to_dict()))
    assert _ends(loaded, a) == ((0, 0), (6, 0)) and _ends(loaded, b) == ((6, 0), (6, 4))
    assert math.isclose(loaded.get(b).params['thickness'], 0.25)


def test_owner_file_123_two_room_boxes_close_with_one_corner():
    """Owner 25/10 («δεν μπορώ να τα ενώσω»): room 1's wall with the door ends 27 / 13,5 cm from room 2's top wall;
    one «Γωνία» lengthens both, the big room between closes and the others stay closed — no false warning."""
    doc, stack = _doc()
    t1 = _wall(stack, (-3.935, 3.408), (2.295, 3.408))                  # room 2: top …
    _wall(stack, (-3.935, -4.758), (-3.935, 3.408))                      # … left
    t8 = _wall(stack, (-4.217, 5.975), (-4.205, 3.543))                  # room 1: right wall (the door)
    _wall(stack, (-4.205, 3.543), (-7.758, 3.543))                       # room 1: bottom, joined at t8's end
    stack.execute(CornerWalls(t8, (-4.21, 5.0), t1, (0.0, 3.408)))
    assert _ends(doc, t8)[1] == _ends(doc, t1)[0]
    assert stack.done[-1].plan['warnings'] == []
