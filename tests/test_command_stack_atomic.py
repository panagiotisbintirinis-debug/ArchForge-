"""Λίστα εργασιών Α2 (28/10): ΚΑΘΕ εντολή είναι «όλα ή τίποτα» — μια αποτυχία δεν αφήνει μισή αλλαγή χωρίς αναίρεση.

The guarantee lives in ``CommandStack`` (execute / amend / undo / redo), so it also covers commands written later.
"""
import json

import pytest

from archforge.architecture.dimension_reference import ApplyDimensionReference
from archforge.architecture.wall_edit import MoveWall
from archforge.core.commands import (AddEntities, AddEntity, Command, CommandStack, DeleteEntities, MoveEntities,
                                     RotateEntities, UpdateEntities)
from archforge.core.model import Document, Entity


def _state(doc):
    return json.dumps(doc.to_dict(), sort_keys=True, default=str)


def _room(reference=None):
    doc = Document()
    stack = CommandStack(doc)
    ids = []
    pts = [(0, 0), (10, 0), (10, 8), (0, 8), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        p = {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3, 'thickness': .5}
        if reference:
            p['reference'] = reference
        e = Entity('wall', p)
        stack.execute(AddEntity(e))
        ids.append(e.id)
    box = Entity('box', {'x': 3, 'y': 3, 'z': 0, 'w': 1, 'd': 1, 'h': 1})
    stack.execute(AddEntity(box))
    return doc, stack, ids, box.id


def test_dimension_reference_with_a_locked_wall_changes_nothing():
    """Reproduced 28/10: 2 of 4 walls moved onto their axis, then PermissionError — and no undo step."""
    doc, stack, ids, _ = _room(reference='exterior')
    doc.get(ids[2]).locked = True
    before, steps = _state(doc), len(stack.done)
    with pytest.raises(PermissionError):
        stack.execute(ApplyDimensionReference(0.0))
    assert _state(doc) == before
    assert len(stack.done) == steps


class _HalfThenFail(Command):
    """A command written without its own rollback: changes one thing, then fails."""

    def __init__(self, eid):
        self.eid = eid

    def do(self, doc):
        doc.update(self.eid, {'x': 7.0})
        raise RuntimeError('half way')

    def undo(self, doc):
        pass


def test_the_stack_puts_back_a_half_change_of_any_command():
    doc, stack, _, box = _room()
    before, steps = _state(doc), len(stack.done)
    with pytest.raises(RuntimeError):
        stack.execute(_HalfThenFail(box))
    assert _state(doc) == before and len(stack.done) == steps
    with pytest.raises(RuntimeError):
        stack.amend(_HalfThenFail(box))
    assert _state(doc) == before and len(stack.done) == steps


def _commands(ids, box):
    return {
        'MoveEntities': lambda: MoveEntities(ids[:2] + [box], 1.0, 0.5),
        'RotateEntities': lambda: RotateEntities(ids[:2] + [box], 30.0),
        'UpdateEntities': lambda: UpdateEntities({ids[0]: {'height': 3.2}, ids[1]: {'height': 3.2}, box: {'h': 2}}),
        'MoveWall': lambda: MoveWall(ids[1], 0.5),
        'AddEntities': lambda: AddEntities([Entity('box', {'x': i, 'y': 1, 'z': 0, 'w': .5, 'd': .5, 'h': .5})
                                            for i in range(3)]),
        'DeleteEntities': lambda: DeleteEntities(ids[:3]),
    }


@pytest.mark.parametrize('name', ['MoveEntities', 'RotateEntities', 'UpdateEntities', 'MoveWall', 'AddEntities',
                                  'DeleteEntities'])
def test_a_failure_at_any_step_of_a_real_command_leaves_the_document_as_it_was(name, monkeypatch):
    """Document.update/add/remove fails at the 1st, 2nd, 3rd … call: never a half change, never an empty undo step."""
    for n in range(1, 8):
        doc, stack, ids, box = _room()
        before, steps = _state(doc), len(stack.done)
        calls = {'n': 0}
        for method in ('update', 'add', 'remove'):
            real = getattr(Document, method)

            def failing(self, *a, _real=real, **k):
                calls['n'] += 1
                if calls['n'] == n:
                    raise RuntimeError(f'injected failure at call {n}')
                return _real(self, *a, **k)
            monkeypatch.setattr(Document, method, failing)
        try:
            stack.execute(_commands(ids, box)[name]())
            failed = False
        except RuntimeError:
            failed = True
        monkeypatch.undo()
        if not failed:
            break                                  # the command needs fewer calls than n: all steps covered
        assert _state(doc) == before, f'{name}: half change after a failure at call {n}'
        assert len(stack.done) == steps


def test_a_redo_that_fails_stays_redoable_and_changes_nothing():
    doc, stack, ids, box = _room()
    stack.execute(MoveEntities([box, ids[0]], 1.0, 0.0))
    stack.undo()
    doc.get(ids[0]).locked = True                  # the wall got locked meanwhile
    before = _state(doc)
    with pytest.raises(PermissionError):
        stack.redo()
    assert _state(doc) == before
    assert stack.can_redo                          # not lost: unlock and redo again
    doc.get(ids[0]).locked = False
    stack.redo()
    assert doc.get(box).params['x'] == 4.0


def test_an_undo_that_fails_stays_undoable_and_changes_nothing():
    doc, stack, ids, box = _room()
    stack.execute(MoveEntities([box, ids[0]], 1.0, 0.0))
    doc.get(ids[0]).locked = True
    before = _state(doc)
    with pytest.raises(PermissionError):
        stack.undo()
    assert _state(doc) == before
    assert stack.can_undo
    doc.get(ids[0]).locked = False
    stack.undo()
    assert doc.get(box).params['x'] == 3.0
