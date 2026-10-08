"""Walls by click-click (one corner per click) next to the existing drag."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent


def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall']


def _click(ctrl, x, y):
    ctrl.pointer_move(PointerEvent(x, y))
    ctrl.pointer_down(PointerEvent(x, y))
    return ctrl.pointer_up(PointerEvent(x, y))


def _ctrl():
    d = Document(); stack = CommandStack(d); ctrl = PointerController(d, stack)
    ctrl.set_tool('wall')
    return d, stack, ctrl


def test_click_starts_a_chain_without_error_or_wall():
    d, _stack, ctrl = _ctrl()
    _click(ctrl, 0, 0)
    assert ctrl.wall_chain is not None and ctrl.active is not None
    assert not _walls(d)
    # Moving (no button) shows the rubber wall with its length.
    pv = ctrl.pointer_move(PointerEvent(3.0, 0.02))
    assert pv.kind == 'wall' and abs(pv.hud['length'] - 3.0) < .05


def test_click_click_chain_closes_on_the_first_corner():
    d, stack, ctrl = _ctrl()
    for x, y in ((0, 0), (5, 0), (5, 4), (0, 4)):
        _click(ctrl, x, y)
    assert len(_walls(d)) == 3 and ctrl.wall_chain is not None
    _click(ctrl, 0.05, 0.05)                         # near the first corner: snaps and closes
    assert ctrl.wall_chain is None and ctrl.active is None
    walls = _walls(d)
    assert len(walls) == 4
    ends = sorted((round(w.params['x2'], 3), round(w.params['y2'], 3)) for w in walls)
    assert (0.0, 0.0) in ends
    # One undo per wall.
    stack.undo()
    assert len(_walls(d)) == 3


def test_double_click_or_finish_ends_the_chain_keeping_walls():
    d, _stack, ctrl = _ctrl()
    _click(ctrl, 0, 0); _click(ctrl, 4, 0)
    _click(ctrl, 4, 0)                               # second click on the same corner = double click
    assert ctrl.wall_chain is None and len(_walls(d)) == 1
    _click(ctrl, 0, 2); _click(ctrl, 3, 2)
    ctrl.finish_wall_chain()                         # Enter / right click
    assert ctrl.active is None and len(_walls(d)) == 2


def test_escape_cancels_the_rubber_segment_only():
    d, _stack, ctrl = _ctrl()
    _click(ctrl, 0, 0); _click(ctrl, 4, 0)
    ctrl.pointer_move(PointerEvent(4, 3))
    ctrl.cancel()
    assert ctrl.wall_chain is None and ctrl.active is None and len(_walls(d)) == 1


def test_drag_still_draws_one_wall_and_no_chain():
    d, _stack, ctrl = _ctrl()
    ctrl.pointer_down(PointerEvent(0, 0)); ctrl.pointer_move(PointerEvent(3, 0)); ctrl.pointer_up(PointerEvent(3, 0))
    assert len(_walls(d)) == 1 and ctrl.wall_chain is None and ctrl.active is None


def test_chain_follows_the_brief_and_splits_on_a_tee():
    d, stack, ctrl = _ctrl()
    stack.execute(AddEntity(Entity('project_brief', {'project_type': 'new', 'wall_system': 'stone_bearing',
                                                     'measure': 'exterior', 'floor_system': 'rc_slab'})))
    stack.execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': .2})))
    ctrl.set_tool('wall')
    _click(ctrl, 3, 3); _click(ctrl, 3, 0.02)        # ends on the existing wall: T junction
    ctrl.finish_wall_chain()
    walls = _walls(d)
    assert len(walls) == 3                           # the old wall split in two
    new = [w for w in walls if abs(w.params['x1'] - 3) < 1e-6 and abs(w.params['x2'] - 3) < 1e-6]
    assert new and new[0].params.get('wall_type') not in (None, 'generic')
