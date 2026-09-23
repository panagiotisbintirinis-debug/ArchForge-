import pytest

from archforge.core.commands import CommandStack, RouteAndConnectInfrastructure
from archforge.core.model import Document, Entity
from archforge.core.router import MEPPathRouter


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


def test_astar_route_bypasses_wall_voxel_volume():
    doc = Document()
    doc.add(_wall())
    router = MEPPathRouter(doc, grid_resolution=0.05, clearance=0.025)

    start = (0.0, 0.0, 0.5)
    end = (2.0, 0.0, 0.5)
    route = router.compute_route(start, end)

    assert route[0] == start
    assert route[-1] == end
    assert len(route) >= 4

    route_voxels = [router._world_to_grid(point) for point in route]
    assert all(voxel not in router.obstacles for voxel in route_voxels[1:-1])
    assert any(abs(point[1]) > 0.6 or point[2] < 0.0 or point[2] > 1.2 for point in route[1:-1])

    # Every simplified segment is axis-aligned because it is reconstructed from
    # the six-neighbor A* voxel path, so it cannot cut diagonally through the wall.
    for a, b in zip(route, route[1:]):
        changed_axes = sum(abs(a[i] - b[i]) > 1e-9 for i in range(3))
        assert changed_axes == 1


def test_route_and_connect_creates_authoritative_multisegment_mesh():
    doc = Document()
    doc.add(_box('source', 0.0))
    doc.add(_box('sink', 2.0))
    doc.add(_wall())
    stack = CommandStack(doc)
    events = []
    stack.subscribe(events.append)

    command = RouteAndConnectInfrastructure(
        'source',
        'sink',
        0.05,
        'electrical',
        grid_resolution=0.05,
    )
    stack.execute(command)

    pipe = doc.get(command.generated_id)
    assert pipe.kind == 'mesh'
    assert len(pipe.params['vertices']) > 0
    assert len(pipe.params['faces']) > 0

    metadata = pipe.params['metadata']
    route = metadata['source_path_vertices']
    assert len(route) >= 4
    assert metadata['semantic_type'] == 'conduit'
    assert metadata['routing']['algorithm'] == 'astar-3d'
    assert metadata['routing']['grid_resolution'] == 0.05
    assert metadata['routing']['route_nodes'] == len(route)
    assert events[-1] == [command.generated_id]

    # The exact route baked into the authoritative mesh is orthographic at every segment.
    for a, b in zip(route, route[1:]):
        assert sum(abs(a[i] - b[i]) > 1e-9 for i in range(3)) == 1

    # The authoritative mesh was generated from more than one routed segment,
    # not a direct start/end fallback.
    assert len(route) > 2
    assert any(abs(point[1]) > 0.6 or point[2] < 0.0 or point[2] > 1.2 for point in route[1:-1])

    stack.undo()
    assert command.generated_id not in doc.entities
    stack.redo()
    assert doc.get(command.generated_id).kind == 'mesh'
    assert doc.get(command.generated_id).params['metadata']['source_path_vertices'] == route


def test_non_grid_boundary_anchors_are_clamped_to_strict_orthographic_segments():
    doc = Document()
    router = MEPPathRouter(doc, grid_resolution=0.05)

    start = (0.013, 0.017, 0.523)
    end = (0.187, 0.083, 0.571)
    route = router.compute_route(start, end)

    assert route[0] == start
    assert route[-1] == end
    assert len(route) > 2

    start_vector = tuple(route[1][i] - start[i] for i in range(3))
    end_vector = tuple(end[i] - route[-2][i] for i in range(3))
    assert sum(abs(value) > 1e-9 for value in start_vector) == 1
    assert sum(abs(value) > 1e-9 for value in end_vector) == 1

    directions = []
    for a, b in zip(route, route[1:]):
        delta = tuple(b[i] - a[i] for i in range(3))
        changed_axes = [i for i, value in enumerate(delta) if abs(value) > 1e-9]
        assert len(changed_axes) == 1
        directions.append(changed_axes[0])

    # Every baked centerline segment is parallel to exactly one world axis.
    assert set(directions) <= {0, 1, 2}


def test_same_voxel_micro_partition_is_rejected_by_continuous_collision_guard():
    doc = Document()
    doc.add(Entity(
        'wall',
        {
            'x1': 0.0,
            'y1': -0.02,
            'z': 0.0,
            'x2': 0.0,
            'y2': 0.02,
            'height': 1.0,
            'thickness': 0.002,
        },
        id='micro-partition',
    ))
    router = MEPPathRouter(doc, grid_resolution=0.05)

    start = (-0.024, 0.0, 0.5)
    end = (0.024, 0.0, 0.5)

    assert router._world_to_grid(start) == router._world_to_grid(end)
    with pytest.raises(
        ValueError,
        match='sub-voxel obstruction',
    ):
        router.compute_route(start, end)
