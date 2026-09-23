import pytest

from archforge.core.commands import CommandStack, ConnectInfrastructure
from archforge.core.interaction import VertexMoveTransaction
from archforge.core.model import Document, Entity, SCHEMAS
from archforge.geometry.mesh import TessellatedPreviewBackend


def _box(entity_id, x):
    return Entity(
        'box',
        {'x': x, 'y': 0, 'z': 0, 'width': 1, 'depth': 1, 'height': 1, 'rotation': 0},
        id=entity_id,
    )


def _connect(stack, diameter=0.05, system_type='hydraulic'):
    command = ConnectInfrastructure(
        'source',
        'sink',
        diameter,
        system_type,
        [[0, 0, 0.5], [2, 1, 1.0], [4, 0, 0.5]],
    )
    stack.execute(command)
    return command


def test_invalid_mep_diameter_is_rejected_before_mesh_commit():
    assert 'conduit' not in SCHEMAS
    for diameter in (0, -0.1, 0.004, 0.501):
        doc = Document()
        doc.add(_box('source', 0))
        doc.add(_box('sink', 4))
        stack = CommandStack(doc)
        with pytest.raises(ValueError):
            _connect(stack, diameter=diameter)
        assert 'mep_source_sink' not in doc.entities


def test_connect_infrastructure_commits_authoritative_mesh_and_notifies_reactively():
    doc = Document()
    start = _box('source', 0)
    end = _box('sink', 4)
    doc.add(start)
    doc.add(end)
    stack = CommandStack(doc)
    events = []
    stack.subscribe(events.append)

    command = _connect(stack, diameter=0.05, system_type='hydraulic')
    pipe = doc.get(command.generated_id)

    assert pipe.kind == 'mesh'
    assert pipe.params['vertices']
    assert pipe.params['faces']
    assert any(len(face) == 4 for face in pipe.params['faces'])
    assert pipe.params['matrix'] == [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    metadata = pipe.params['metadata']
    assert metadata['semantic_type'] == 'conduit'
    assert metadata['system_type'] == 'hydraulic'
    assert metadata['diameter'] == 0.05
    assert metadata['start_node'] == start.id
    assert metadata['end_node'] == end.id
    assert events[-1] == [command.generated_id]
    assert command.generated_id in doc.dependencies[start.id]
    assert command.generated_id in doc.dependencies[end.id]

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    body = evaluation.body(command.generated_id)
    assert body.semantic_kind == 'mesh'
    assert body.payload.vertices
    assert body.payload.triangles


def test_generated_pipe_bend_vertex_uses_standard_vertex_transaction_and_persists():
    doc = Document()
    doc.add(_box('source', 0))
    doc.add(_box('sink', 4))
    stack = CommandStack(doc)
    events = []
    stack.subscribe(events.append)
    command = _connect(stack, system_type='electrical')

    pipe = doc.get(command.generated_id)
    segments = pipe.params['metadata']['sweep_segments']
    bend_vertex_index = segments
    before = tuple(pipe.params['vertices'][bend_vertex_index])

    tx = VertexMoveTransaction(stack, command.generated_id, bend_vertex_index)
    tx.update_drag(0.25, -0.10, 0.20)

    assert tuple(doc.get(command.generated_id).params['vertices'][bend_vertex_index]) == before
    preview = tx.preview_position
    tx.commit()

    after = tuple(doc.get(command.generated_id).params['vertices'][bend_vertex_index])
    assert after == pytest.approx(preview)
    assert after == pytest.approx((before[0] + 0.25, before[1] - 0.10, before[2] + 0.20))
    assert events[-1] == (command.generated_id,)

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    assert evaluation.body(command.generated_id).semantic_kind == 'mesh'

    stack.undo()
    restored = tuple(doc.get(command.generated_id).params['vertices'][bend_vertex_index])
    assert restored == pytest.approx(before)
