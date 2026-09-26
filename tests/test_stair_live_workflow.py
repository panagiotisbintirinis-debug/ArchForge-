import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from archforge.architecture.stairs import discover_building_levels, solve_stair_candidates, stair_footprint, stair_opening_polygon
from archforge.architecture.topology import room_faces
from archforge.core.commands import CommandStack, CreateRoomFloors, CreateRoomRoofs
from archforge.core.interaction import MoveTransaction, RotateTransaction, StairPlaceTransaction
from archforge.core.model import Document, Entity, WorkPlane
from archforge.geometry.mesh import TessellatedPreviewBackend


def _two_level_document():
    doc = Document()
    doc.levels = {'Ground': 0.0, 'Floor 2': 2.7}
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    return doc


def test_stair_solver_changes_layout_when_available_run_changes():
    long_run = solve_stair_candidates(0.0, 2.7, (0.0, 0.0), (5.0, 0.0))
    short_run = solve_stair_candidates(0.0, 2.7, (0.0, 0.0), (1.8, 0.0))

    assert long_run[0].layout == 'straight'
    assert short_run[0].layout in {'u', 'l', 'spiral'}
    assert long_run[0].riser_count >= 2
    assert 0.15 <= long_run[0].riser_height <= 0.19
    assert 0.28 <= long_run[0].tread_depth <= 0.30


def test_pointer_direction_rotates_live_stair_solution():
    east = solve_stair_candidates(0.0, 2.7, (1.0, 1.0), (5.0, 1.0))[0]
    north = solve_stair_candidates(0.0, 2.7, (1.0, 1.0), (1.0, 5.0))[0]

    assert abs(east.angle_deg) < 1e-6
    assert abs(north.angle_deg - 90.0) < 1e-6


def test_stair_transaction_commits_authoritative_mesh_and_undoes():
    doc = _two_level_document()
    stack = CommandStack(doc)
    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))

    tx.update(5.0, 0.0)
    stair_id = tx.commit()

    stair = doc.get(stair_id)
    assert stair.kind == 'stair'
    assert stair.params['lower_z'] == 0.0
    assert stair.params['upper_z'] == 2.7
    assert stair.params['layout'] == 'straight'
    assert abs(stair.params['riser_count'] * stair.params['riser_height'] - 2.7) < 1e-6

    body = TessellatedPreviewBackend().evaluate(doc).body(stair_id)
    assert body.semantic_kind == 'stair'
    assert body.payload.vertices
    assert body.payload.triangles

    snapshot = doc.to_dict()
    restored = Document.from_dict(snapshot)
    assert restored.get(stair_id).params == stair.params

    stack.undo()
    assert stair_id not in doc.entities


def test_stair_requires_an_upper_floor_level():
    doc = Document()
    stack = CommandStack(doc)
    try:
        StairPlaceTransaction(doc, stack, (0.0, 0.0))
    except ValueError as exc:
        assert 'upper floor level' in str(exc)
    else:
        raise AssertionError('stair placement should require an upper level')



def test_stair_candidate_cycle_changes_committed_layout():
    doc = _two_level_document()
    stack = CommandStack(doc)
    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))

    tx.update(5.0, 0.0)
    first_layout = tx.active_candidate.layout
    tx.cycle_candidate(1)
    second_layout = tx.active_candidate.layout
    assert tx.active_index == 1
    assert second_layout != first_layout or tx.active_candidate.turn_direction != tx.candidates[0].turn_direction

    stair_id = tx.commit()
    assert doc.get(stair_id).params['layout'] == second_layout


def test_stair_preview_tracks_active_index():
    doc = _two_level_document()
    stack = CommandStack(doc)
    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))

    tx.update(2.0, 0.0)
    tx.cycle_candidate(1)

    assert tx.preview['active_index'] == 1
    assert tx.preview['chosen']['layout'] == tx.active_candidate.layout



def test_stair_automatically_lands_on_top_of_upper_slab():
    doc = _two_level_document()
    doc.add(Entity(
        'floor',
        {
            'points': [(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)],
            'z': 2.7,
            'thickness': 0.15,
        },
        id='upper-slab',
    ))
    stack = CommandStack(doc)

    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    tx.update(5.0, 0.0)
    stair_id = tx.commit()
    stair = doc.get(stair_id)

    assert stair.params['upper_floor_z'] == 2.7
    assert stair.params['upper_slab_thickness'] == 0.15
    assert abs(stair.params['upper_z'] - 2.85) < 1e-9
    assert abs(
        stair.params['riser_count'] * stair.params['riser_height'] - 2.85
    ) < 1e-6


def test_cancelled_stair_transaction_never_creates_entity():
    doc = _two_level_document()
    stack = CommandStack(doc)
    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    tx.update(3.0, 1.0)
    tx.cancel()

    assert not any(entity.kind == 'stair' for entity in doc.entities.values())
    try:
        tx.commit()
    except RuntimeError:
        pass
    else:
        raise AssertionError('cancelled stair transaction must not commit')



def test_stair_finds_legacy_second_storey_even_when_levels_only_contains_ground():
    doc = Document()
    doc.levels = {'Ground': 0.0}
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    doc.add(Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0,
            'z': 2.7, 'height': 2.7, 'thickness': 0.15,
        },
        id='legacy-upper-wall',
    ))
    doc.add(Entity(
        'floor',
        {
            'points': [(-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)],
            'z': 2.7,
            'thickness': 0.15,
        },
        id='legacy-upper-floor',
    ))

    levels = discover_building_levels(doc)
    assert [(item['name'], item['elevation']) for item in levels] == [
        ('Ground', 0.0),
        ('Floor 2', 2.7),
    ]
    assert levels[1]['inferred'] is True

    tx = StairPlaceTransaction(doc, CommandStack(doc), (0.0, 0.0))
    assert tx.upper_floor_z == 2.7
    assert tx.upper_slab_thickness == 0.15
    assert tx.upper_z == 2.85
    assert tx.candidates


def test_geometry_only_upper_walls_are_enough_to_resolve_a_stair_level():
    doc = Document()
    doc.levels = {'Ground': 0.0}
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    doc.add(Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 0.0, 'x2': 3.0, 'y2': 0.0,
            'z': 2.7, 'height': 2.7, 'thickness': 0.15,
        },
        id='upper-wall-only',
    ))

    tx = StairPlaceTransaction(doc, CommandStack(doc), (0.0, 0.0))
    assert tx.upper_floor_z == 2.7
    assert tx.upper_slab_thickness == 0.0
    assert tx.upper_z == 2.7



def test_stair_move_transaction_updates_xy_and_undo_restores_position():
    doc = _two_level_document()
    stack = CommandStack(doc)
    stair_tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    stair_tx.update(5.0, 0.0)
    stair_id = stair_tx.commit()
    before = dict(doc.get(stair_id).params)

    move = MoveTransaction(doc, stack, [stair_id], origin=(0.0, 0.0, 0.0))
    move.update_pointer(1.25, -0.75, snap=False)
    move.commit()

    moved = doc.get(stair_id)
    assert abs(moved.params['x'] - (before['x'] + 1.25)) < 1e-9
    assert abs(moved.params['y'] - (before['y'] - 0.75)) < 1e-9
    assert moved.params['lower_z'] == before['lower_z']
    assert moved.params['upper_z'] == before['upper_z']

    stack.undo()
    restored = doc.get(stair_id)
    assert restored.params['x'] == before['x']
    assert restored.params['y'] == before['y']


def test_stair_rotate_transaction_updates_angle_and_undo_restores_geometry():
    doc = _two_level_document()
    stack = CommandStack(doc)
    stair_tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    stair_tx.update(5.0, 0.0)
    stair_id = stair_tx.commit()
    before = dict(doc.get(stair_id).params)

    rotate = RotateTransaction(doc, stack, stair_id)
    rotate.update_angle(90.0, snap=True)
    rotate.commit()

    rotated = doc.get(stair_id)
    assert abs(((rotated.params['angle_deg'] - before['angle_deg']) % 360.0) - 90.0) < 1e-9

    stack.undo()
    restored = doc.get(stair_id)
    assert restored.params['x'] == before['x']
    assert restored.params['y'] == before['y']
    assert restored.params['angle_deg'] == before['angle_deg']


def test_move_ctrl_axis_constraint_keeps_stair_on_one_axis():
    doc = _two_level_document()
    stack = CommandStack(doc)
    stair_tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    stair_tx.update(5.0, 0.0)
    stair_id = stair_tx.commit()

    move = MoveTransaction(doc, stack, [stair_id], origin=(0.0, 0.0, 0.0))
    move.update_pointer(2.0, 0.7, snap=False, axis_lock=True)

    assert move.axis_lock == 'x'
    assert abs(move.dx - 2.0) < 1e-9
    assert abs(move.dy) < 1e-9



def test_moved_wall_snaps_its_endpoint_to_another_wall_centerline():
    doc = Document()
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    moving = Entity(
        'wall',
        {
            'x1': 0.0, 'y1': 0.0, 'x2': 1.0, 'y2': 0.0,
            'z': 0.0, 'height': 2.7, 'thickness': 0.15,
        },
        id='moving-wall',
    )
    target = Entity(
        'wall',
        {
            'x1': -5.0, 'y1': 2.0, 'x2': 5.0, 'y2': 2.0,
            'z': 0.0, 'height': 2.7, 'thickness': 0.20,
        },
        id='target-wall',
    )
    doc.add(moving)
    doc.add(target)
    move = MoveTransaction(
        doc,
        CommandStack(doc),
        [moving.id],
        origin=(0.0, 0.0, 0.0),
        snap_tol=0.15,
    )

    move.update_pointer(0.0, 1.92, snap=True)

    assert move.last_snap_kind == 'wall'
    assert abs(move.dy - 2.0) < 1e-9


def test_stair_move_snaps_footprint_to_physical_wall_face():
    doc = _two_level_document()
    wall = Entity(
        'wall',
        {
            'x1': -5.0, 'y1': 2.0, 'x2': 5.0, 'y2': 2.0,
            'z': 0.0, 'height': 2.7, 'thickness': 0.20,
        },
        id='snap-wall',
    )
    doc.add(wall)
    stack = CommandStack(doc)
    stair_tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    stair_tx.update(5.0, 0.0)
    stair_id = stair_tx.commit()

    from archforge.architecture.stairs import candidate_from_params, stair_footprint
    footprint = stair_footprint(candidate_from_params(doc.get(stair_id).params))
    top_y = max(y for _, y in footprint)
    desired_dy = (2.0 - 0.10) - top_y - 0.05

    move = MoveTransaction(
        doc,
        stack,
        [stair_id],
        origin=(0.0, 0.0, 0.0),
        snap_tol=0.15,
    )
    move.update_pointer(0.0, desired_dy, snap=True)

    assert move.last_snap_kind == 'wall_face'



def _add_square_room_walls(doc, prefix, z, size=6.0):
    coords = [
        ((0.0, 0.0), (size, 0.0)),
        ((size, 0.0), (size, size)),
        ((size, size), (0.0, size)),
        ((0.0, size), (0.0, 0.0)),
    ]
    for index, (a, b) in enumerate(coords, start=1):
        doc.add(Entity(
            'wall',
            {
                'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                'z': float(z), 'height': 2.7, 'thickness': 0.15,
            },
            id=f'{prefix}-{index}',
        ))


def test_stair_opening_uses_upper_headroom_path_not_full_footprint():
    candidate = solve_stair_candidates(
        0.0,
        2.85,
        (0.0, 0.0),
        (5.0, 0.0),
        upper_floor_z=2.7,
        upper_slab_thickness=0.15,
    )[0]

    full = stair_footprint(candidate)
    opening = stair_opening_polygon(candidate)

    full_width = max(x for x, _ in full) - min(x for x, _ in full)
    opening_width = max(x for x, _ in opening) - min(x for x, _ in opening)
    assert opening_width < full_width


def test_stair_cuts_both_upper_room_floor_and_lower_room_roof():
    doc = Document()
    doc.levels = {'Ground': 0.0, 'Floor 2': 2.7}
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    _add_square_room_walls(doc, 'lower', 0.0)
    _add_square_room_walls(doc, 'upper', 2.7)

    lower_face = room_faces(doc, z=0.0)[0]
    upper_face = room_faces(doc, z=2.7)[0]
    stack = CommandStack(doc)
    stack.execute(CreateRoomRoofs([lower_face.signature], thickness=0.20))
    stack.execute(CreateRoomFloors([upper_face.signature], thickness=0.15))

    tx = StairPlaceTransaction(doc, stack, (1.0, 1.0))
    tx.update(5.0, 1.0)
    stair_id = tx.commit()

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    floor_id = next(e.id for e in doc.entities.values() if e.kind == 'room_floor')
    roof_id = next(e.id for e in doc.entities.values() if e.kind == 'room_roof')

    floor_body = evaluation.body(floor_id)
    roof_body = evaluation.body(roof_id)

    assert 'stair_opening_edge' in floor_body.payload.triangle_surfaces
    assert 'stair_opening_edge' in roof_body.payload.triangle_surfaces
    assert evaluation.body(stair_id).payload.triangles
