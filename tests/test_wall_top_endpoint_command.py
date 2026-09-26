import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.core.wall_profile_commands import SetWallTopEndpoint


def _document_with_wall(**changes):
    params = {
        'x1': 0.0, 'y1': 0.0, 'z': 0.0,
        'x2': 4.0, 'y2': 3.0,
        'height': 3.0, 'thickness': 0.2,
    }
    params.update(changes)
    doc = Document()
    wall = Entity('wall', params)
    doc.add(wall)
    return doc, wall.id


def test_numeric_endpoint_edit_uses_command_stack_and_round_trips():
    doc, wall_id = _document_with_wall()
    stack = CommandStack(doc)

    stack.execute(SetWallTopEndpoint(wall_id, 'start', 2.25))
    assert doc.get(wall_id).params['start_height'] == pytest.approx(2.25)
    assert 'end_height' not in doc.get(wall_id).params

    stack.undo()
    assert 'start_height' not in doc.get(wall_id).params
    assert doc.get(wall_id).params['height'] == pytest.approx(3.0)

    stack.redo()
    assert doc.get(wall_id).params['start_height'] == pytest.approx(2.25)


def test_endpoint_command_preserves_existing_endpoint_value_on_undo():
    doc, wall_id = _document_with_wall(end_height=3.4)
    stack = CommandStack(doc)

    stack.execute(SetWallTopEndpoint(wall_id, 'end', 4.1))
    assert doc.get(wall_id).params['end_height'] == pytest.approx(4.1)
    stack.undo()
    assert doc.get(wall_id).params['end_height'] == pytest.approx(3.4)


def test_endpoint_command_is_host_local_not_axis_specific():
    doc, wall_id = _document_with_wall(x1=1.0, y1=2.0, x2=4.0, y2=6.0)
    before = {key: doc.get(wall_id).params[key] for key in ('x1', 'y1', 'x2', 'y2')}
    CommandStack(doc).execute(SetWallTopEndpoint(wall_id, 'end', 3.75))
    assert {key: doc.get(wall_id).params[key] for key in before} == before
    assert doc.get(wall_id).params['end_height'] == pytest.approx(3.75)


@pytest.mark.parametrize('endpoint,height', [('middle', 3.0), ('start', 0.0), ('end', float('nan'))])
def test_endpoint_command_rejects_invalid_semantic_edits(endpoint, height):
    doc, wall_id = _document_with_wall()
    stack = CommandStack(doc)
    with pytest.raises(ValueError):
        stack.execute(SetWallTopEndpoint(wall_id, endpoint, height))
    assert not stack.can_undo
