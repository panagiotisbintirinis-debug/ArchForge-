import pytest

from archforge.core.commands import CommandStack, ConnectInfrastructure
from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend


def _box(entity_id, x):
    return Entity(
        'box',
        {'x': x, 'y': 0, 'z': 0, 'width': 1, 'depth': 1, 'height': 1, 'rotation': 0},
        id=entity_id,
    )


def _conduit_params(diameter):
    return {
        'start_node': 'source',
        'end_node': 'sink',
        'diameter': diameter,
        'path_vertices': [[0, 0, 0], [1, 0, 0], [1, 1, 0.5]],
        'system_type': 'hydraulic',
    }


def test_conduit_rejects_zero_and_negative_diameter():
    for diameter in (0, -0.1):
        doc = Document()
        with pytest.raises(ValueError):
            doc.add(Entity('conduit', _conduit_params(diameter)))


def test_connect_infrastructure_uses_stack_and_notifies_reactively():
    doc = Document()
    start = _box('source', 0)
    end = _box('sink', 4)
    doc.add(start)
    doc.add(end)
    stack = CommandStack(doc)
    events = []
    stack.subscribe(events.append)

    command = ConnectInfrastructure(
        start.id,
        end.id,
        0.05,
        'hydraulic',
        [[0, 0, 0.5], [2, 0, 0.5], [4, 0, 0.5]],
    )
    stack.execute(command)

    conduit = doc.get(command.generated_id)
    assert conduit.kind == 'conduit'
    assert conduit.params['diameter'] == 0.05
    assert conduit.params['system_type'] == 'hydraulic'
    assert events[-1] == [command.generated_id]
    assert command.generated_id in doc.dependencies[start.id]
    assert command.generated_id in doc.dependencies[end.id]

    stack.undo()
    assert command.generated_id not in doc.entities
    assert events[-1] == [command.generated_id]


def test_conduit_tessellates_into_visible_routed_mesh():
    doc = Document()
    start = _box('source', 0)
    end = _box('sink', 4)
    doc.add(start)
    doc.add(end)
    command = ConnectInfrastructure(
        start.id,
        end.id,
        0.08,
        'electrical',
        [[0, 0, 0.5], [1, 0, 0.5], [2, 1, 1.0], [4, 1, 1.0]],
    )
    CommandStack(doc).execute(command)

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    body = evaluation.body(command.generated_id)
    assert body.semantic_kind == 'conduit'
    assert body.payload.vertices
    assert body.payload.triangles
    assert 'conduit_shell' in body.payload.triangle_surfaces
