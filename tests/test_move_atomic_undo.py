"""Audit F01 / F04 (28/10): a move is all or nothing, and a move that changes nothing leaves no undo step."""
import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document, Entity


def _column(phase):
    return Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.3, 'depth': 0.3, 'height': 3.0,
                                        'rotation': 0.0, 'phase': phase, 'section': 'rectangular', 'top_level': 'Unassigned',
                                        'base_level': 'Ground', 'construction': 'reinforced_concrete', 'role': 'structural'})


def _box(x=0.0):
    return Entity('box', {'x': x, 'y': 0.0, 'z': 0.0, 'width': 1.0, 'depth': 1.0, 'height': 1.0})


def test_mixed_selection_with_a_protected_column_moves_nothing():
    """F01: the box moved, the existing column refused, and the box's move could not be undone."""
    doc = Document(); stack = CommandStack(doc)
    box, column = _box(), _column('existing')
    stack.execute(AddEntity(box)); stack.execute(AddEntity(column))
    n = len(stack.done)
    with pytest.raises(ValueError):
        stack.execute(MoveEntities([box.id, column.id], 1.0, 0.0, 0.0))
    assert doc.get(box.id).params['x'] == 0.0 and doc.get(column.id).params['x'] == 3.0
    assert len(stack.done) == n


def test_a_failure_while_applying_restores_what_already_moved():
    """Order does not matter: an entity rejected by validation half-way leaves the earlier ones where they were."""
    doc = Document(); stack = CommandStack(doc)
    first, second = _box(0.0), _box(5.0)
    stack.execute(AddEntity(first)); stack.execute(AddEntity(second))
    doc.get(second.id).params['x'] = float('nan')        # a broken value the schema refuses on update
    with pytest.raises(ValueError):
        stack.execute(MoveEntities([first.id, second.id], 1.0, 0.0, 0.0))
    assert doc.get(first.id).params['x'] == 0.0


def test_a_move_that_changes_nothing_leaves_no_undo_step():
    """F04: an entity the move does not apply to used to add an empty undo step."""
    doc = Document(); stack = CommandStack(doc)
    box = _box()
    stack.execute(AddEntity(box))
    n = len(stack.done)
    stack.execute(MoveEntities([box.id], 0.0, 0.0, 0.0))          # zero move
    assert len(stack.done) == n


def test_a_dimension_moves_with_its_ends():
    doc = Document(); stack = CommandStack(doc)
    dim = Entity('dimension', {'x1': 0.0, 'y1': 0.0, 'x2': 2.0, 'y2': 0.0, 'level_z': 0.0, 'offset': 0.5})
    stack.execute(AddEntity(dim))
    n = len(stack.done)
    stack.execute(MoveEntities([dim.id], 1.0, 2.0, 0.0))
    p = doc.get(dim.id).params
    assert (p['x1'], p['y1'], p['x2'], p['y2']) == (1.0, 2.0, 3.0, 2.0) and len(stack.done) == n + 1
    stack.undo()
    assert doc.get(dim.id).params['x1'] == 0.0


def test_ordinary_mixed_move_still_one_undo_step():
    doc = Document(); stack = CommandStack(doc)
    box, column = _box(), _column('new')
    stack.execute(AddEntity(box)); stack.execute(AddEntity(column))
    stack.execute(MoveEntities([box.id, column.id], 1.0, 0.0, 0.0))
    assert doc.get(box.id).params['x'] == 1.0 and doc.get(column.id).params['x'] == 4.0
    stack.undo()
    assert doc.get(box.id).params['x'] == 0.0 and doc.get(column.id).params['x'] == 3.0
