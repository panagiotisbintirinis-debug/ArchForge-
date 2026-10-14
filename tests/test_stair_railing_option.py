"""Owner (2026-10-14): «βάλε και επιλογή για κάγκελο … να ακολουθεί τη σκάλα».

A stair carries its railing choice; its railings are children that follow it (move, rotate,
undo) and leave with it.
"""
import pytest

from archforge.architecture.railings import stair_railing_lines
from archforge.architecture.stair_options import railing_choice, railing_command
from archforge.core.commands import AddEntity, CommandStack, DeleteEntities, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.architecture.stairs import solve_stair_candidates


def _stair(doc, stack, layout='straight'):
    cands = solve_stair_candidates(0.0, 2.72, (1.0, 1.0), (6.0, 1.0))
    c = next(c for c in cands if c.layout == layout)
    e = Entity('stair', c.to_params(), name='Stair')
    stack.execute(AddEntity(e))
    return e.id


def _rails(doc, sid, visible_only=True):
    return [doc.get(c) for c in doc.children.get(sid, ()) if c in doc.entities and doc.get(c).kind == 'railing'
            and (doc.get(c).visible or not visible_only)]


def test_choice_adds_railings_that_follow_a_move_and_undo():
    doc = Document(); stack = CommandStack(doc)
    sid = _stair(doc, stack)
    stack.execute(railing_command(doc, sid, 'both'))
    assert railing_choice(doc, sid) == 'both'
    rails = _rails(doc, sid)
    assert {r.params['stair_side'] for r in rails} == {'left', 'right'} and len(rails) == 2   # straight: 1 flight
    left = next(r for r in rails if r.params['stair_side'] == 'left')
    assert left.params['points'] == stair_railing_lines(doc.get(sid).params, 'left')[0]
    x0 = left.params['points'][0][0]
    stack.execute(MoveEntities([sid], 2.0, 0.0, 0.0))
    assert left.params['points'][0][0] == pytest.approx(x0 + 2.0)
    stack.execute(MoveEntities([sid, left.id], 1.0, 0.0, 0.0))         # selected together: moved once
    assert left.params['points'][0][0] == pytest.approx(x0 + 3.0)
    stack.undo(); stack.undo()
    assert doc.get(left.id).params['points'][0][0] == pytest.approx(x0)


def test_one_side_none_and_undo_of_the_choice():
    doc = Document(); stack = CommandStack(doc)
    sid = _stair(doc, stack)
    stack.execute(railing_command(doc, sid, 'left'))
    assert [r.params['stair_side'] for r in _rails(doc, sid)] == ['left']
    stack.execute(railing_command(doc, sid, 'none'))
    assert not _rails(doc, sid, visible_only=False) and railing_choice(doc, sid) == 'none'
    stack.undo()
    assert [r.params['stair_side'] for r in _rails(doc, sid)] == ['left']


def test_layout_change_shows_the_second_flight_and_auto_skips_a_wall_side():
    doc = Document(); stack = CommandStack(doc)
    sid = _stair(doc, stack)
    stack.execute(railing_command(doc, sid, 'both'))
    assert len(_rails(doc, sid)) == 2 and len(_rails(doc, sid, visible_only=False)) == 4
    p = doc.get(sid).params
    l = next(c for c in solve_stair_candidates(0.0, 2.72, (1.0, 1.0), (4.0, 1.0)) if c.layout == 'l').to_params()
    stack.execute(UpdateEntity(sid, {k: l[k] for k in ('layout', 'landing_depth', 'turn_direction')}))
    assert len(_rails(doc, sid)) == 4                                      # L: two flights per side
    stack.undo()
    assert len(_rails(doc, sid)) == 2
    # A wall along the right side (going up east, right = south): «αυτόματα» leaves that side out.
    right_y = stair_railing_lines(p, 'right')[0][0][1]
    stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': right_y - 0.12, 'x2': 8.0, 'y2': right_y - 0.12, 'z': 0.0,
                                            'height': 2.7, 'thickness': 0.2})))
    stack.execute(railing_command(doc, sid, 'auto'))
    assert [r.params['stair_side'] for r in _rails(doc, sid)] == ['left']


def test_deleting_the_stair_takes_its_railings():
    doc = Document(); stack = CommandStack(doc)
    sid = _stair(doc, stack)
    stack.execute(railing_command(doc, sid, 'both'))
    stack.execute(DeleteEntities([sid]))
    assert not any(e.kind == 'railing' for e in doc.entities.values())
    stack.undo()
    assert len(_rails(doc, sid)) == 2
