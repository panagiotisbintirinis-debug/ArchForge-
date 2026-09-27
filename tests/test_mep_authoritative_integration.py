import pytest

from archforge.core.commands import (
    CommandStack,
    ConnectInfrastructure,
    FreezeToMesh,
    MoveVertices,
    RouteAndConnectInfrastructure,
)
from archforge.core.model import Document, Entity
from archforge.core.router import MEPPathRouter
from archforge.geometry.mesh import TessellatedPreviewBackend


def _box(entity_id, x):
    return Entity(
        'box',
        {
            'x': x,
            'y': 0.0,
            'z': 0.0,
            'width': 0.30,
            'depth': 0.30,
            'height': 1.0,
            'rotation': 0.0,
        },
        id=entity_id,
    )


def _wall():
    return Entity(
        'wall',
        {
            'x1': 1.0,
            'y1': -0.6,
            'z': 0.0,
            'x2': 1.0,
            'y2': 0.6,
            'height': 1.2,
            'thickness': 0.20,
        },
        id='wall-blocker',
    )


def test_mep_router_bypasses_authoritative_wall_volume():
    doc = Document()
    doc.add(_wall())
    router = MEPPathRouter(doc, grid_resolution=0.05, clearance=0.025)
    start = (0.0, 0.0, 0.5)
    end = (2.0, 0.0, 0.5)

    route = router.compute_route(start, end)

    assert route[0] == start
    assert route[-1] == end
    assert len(route) >= 4
    for a, b in zip(route, route[1:]):
        assert sum(abs(a[i] - b[i]) > 1e-9 for i in range(3)) == 1


def test_routed_conduit_is_authoritative_mesh_visible_to_mesh_backend_and_reversible():
    doc = Document()
    doc.add(_box('source', 0.0))
    doc.add(_box('sink', 2.0))
    doc.add(_wall())
    stack = CommandStack(doc)

    command = RouteAndConnectInfrastructure(
        'source',
        'sink',
        0.05,
        'electrical',
        grid_resolution=0.05,
    )
    stack.execute(command)

    conduit = doc.get(command.generated_id)
    assert conduit.kind == 'mesh'
    assert conduit.params['metadata']['semantic_type'] == 'conduit'
    assert conduit.params['metadata']['routing']['algorithm'] == 'astar-3d'
    assert command.generated_id in doc.dependencies['source']
    assert command.generated_id in doc.dependencies['sink']

    body = TessellatedPreviewBackend().evaluate(doc).body(command.generated_id)
    assert body.semantic_kind == 'mesh'
    assert body.payload.vertices
    assert body.payload.triangles

    state = doc.to_dict()
    restored = Document.from_dict(state)
    assert restored.get(command.generated_id).params == conduit.params

    stack.undo()
    assert command.generated_id not in doc.entities
    stack.redo()
    assert doc.get(command.generated_id).kind == 'mesh'


def test_authoritative_mesh_vertex_edit_is_undoable():
    doc = Document()
    doc.add(_box('source', 0.0))
    doc.add(_box('sink', 2.0))
    stack = CommandStack(doc)
    connect = ConnectInfrastructure(
        'source',
        'sink',
        0.05,
        'hydraulic',
        [[0.0, 0.0, 0.5], [1.0, 0.4, 0.5], [2.0, 0.0, 0.5]],
    )
    stack.execute(connect)

    mesh = doc.get(connect.generated_id)
    before = list(mesh.params['vertices'][0])
    stack.execute(MoveVertices(connect.generated_id, 0, 0.2, -0.1, 0.3))
    after = doc.get(connect.generated_id).params['vertices'][0]
    assert after == pytest.approx([before[0] + 0.2, before[1] - 0.1, before[2] + 0.3])

    stack.undo()
    assert doc.get(connect.generated_id).params['vertices'][0] == pytest.approx(before)


def test_deleting_mep_endpoint_cascades_linked_conduit():
    doc = Document()
    doc.add(_box('source', 0.0))
    doc.add(_box('sink', 2.0))
    stack = CommandStack(doc)
    connect = ConnectInfrastructure(
        'source',
        'sink',
        0.05,
        'hvac',
        [[0.0, 0.0, 0.5], [2.0, 0.0, 0.5]],
    )
    stack.execute(connect)
    assert connect.generated_id in doc.entities

    doc.remove('source')
    assert connect.generated_id not in doc.entities


def test_freeze_to_mesh_is_safe_and_reversible_for_standalone_pod():
    doc = Document()
    pod = Entity(
        'pod',
        {
            'cx': 0.0,
            'cy': 0.0,
            'floor_level': 0.0,
            'diameter_x': 4.0,
            'diameter_y': 3.0,
            'height': 2.5,
            'shell_thickness': 0.2,
            'rotation': 0.0,
        },
        id='pod-1',
    )
    doc.add(pod)
    stack = CommandStack(doc)

    stack.execute(FreezeToMesh('pod-1'))
    assert doc.get('pod-1').kind == 'mesh'
    assert doc.get('pod-1').params['metadata']['source_kind'] == 'pod'
    assert TessellatedPreviewBackend().evaluate(doc).body('pod-1').payload.vertices

    stack.undo()
    assert doc.get('pod-1').kind == 'pod'


def test_freeze_to_mesh_rejects_pod_with_semantic_children():
    doc = Document()
    pod = Entity(
        'pod',
        {
            'cx': 0.0,
            'cy': 0.0,
            'floor_level': 0.0,
            'diameter_x': 4.0,
            'diameter_y': 3.0,
            'height': 2.5,
            'shell_thickness': 0.2,
            'rotation': 0.0,
        },
        id='pod-1',
    )
    doc.add(pod)
    opening = Entity(
        'window',
        {
            'offset': 0.0,
            'surface_u': 0.0,
            'width': 0.8,
            'height': 0.8,
            'sill': 0.8,
            'flat_margin': 0.1,
        },
        id='window-1',
        parent_id='pod-1',
    )
    doc.add(opening)

    with pytest.raises(ValueError, match='hosts child'):
        FreezeToMesh('pod-1').do(doc)
    assert doc.get('pod-1').kind == 'pod'


def test_mep_terminal_pointer_placement_is_authoritative_and_undoable():
    from archforge.core.viewport import PointerController, PointerEvent

    doc=Document()
    stack=CommandStack(doc)
    controller=PointerController(doc,stack)
    controller.grid=None
    controller.set_tool('mep_hydraulic')

    preview=controller.pointer_down(PointerEvent(1.2,2.3))
    assert preview.kind=='mep-terminal'
    result=controller.pointer_up(PointerEvent(1.2,2.3))

    terminal=doc.get(result.entity_id)
    assert terminal.kind=='mep_terminal'
    assert terminal.params['system_type']=='hydraulic'
    assert terminal.params['x']==pytest.approx(1.2)
    assert terminal.params['y']==pytest.approx(2.3)
    assert terminal.params['elevation']==pytest.approx(0.50)

    stack.undo()
    assert result.entity_id not in doc.entities


def test_mep_terminal_is_semantic_relationship_and_has_plan_marker():
    from archforge.geometry.plan import build_evaluation_plan
    from archforge.core.plan_scene import entity_primitive

    doc=Document()
    terminal=Entity(
        'mep_terminal',
        {
            'x':1.0,'y':2.0,'level_z':0.0,'elevation':0.45,
            'system_type':'electrical','diameter':0.020,
        },
        id='socket-point',
    )
    doc.add(terminal)

    plan=build_evaluation_plan(doc)
    assert plan.node(terminal.id).role=='relationship'
    assert terminal.id not in {node.entity_id for node in plan.geometry_nodes()}

    primitive=entity_primitive(doc,terminal.id)
    assert primitive.kind=='ellipse'
    assert primitive.role=='mep-terminal'
    assert primitive.points==((1.0,2.0),)


def test_human_route_selected_connects_two_matching_mep_points():
    from archforge.ui.main_window import MainWindow
    from archforge.core.plan_scene import entity_primitive

    window=MainWindow()
    a=Entity(
        'mep_terminal',
        {
            'x':0.0,'y':0.0,'level_z':0.0,'elevation':0.50,
            'system_type':'hydraulic','diameter':0.025,
        },
        id='water-a',
    )
    b=Entity(
        'mep_terminal',
        {
            'x':2.0,'y':0.0,'level_z':0.0,'elevation':0.50,
            'system_type':'hydraulic','diameter':0.025,
        },
        id='water-b',
    )
    window.doc.add(a);window.doc.add(b)
    window.doc.select([a.id,b.id])

    window._route_selected_mep()

    conduit_id='mep_water-a_water-b'
    assert conduit_id in window.doc.entities
    conduit=window.doc.get(conduit_id)
    assert conduit.params['metadata']['semantic_type']=='conduit'
    assert conduit.params['metadata']['system_type']=='hydraulic'

    primitive=entity_primitive(window.doc,conduit_id)
    assert primitive.kind=='polyline'
    assert primitive.role=='mep-conduit'
    assert len(primitive.points)>=2

    window._undo()
    assert conduit_id not in window.doc.entities
    window.close()
