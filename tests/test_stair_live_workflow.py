import pytest
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from archforge.architecture.stairs import discover_building_levels, solve_stair_candidates, stair_footprint, stair_opening_polygon, stair_opening_polygons
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



def test_moved_wall_prefers_semantic_midpoint_on_another_wall_centerline():
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

    assert move.last_snap_kind == 'midpoint'
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



def test_rotated_straight_stair_opening_preserves_rotation_in_slab_mesh():
    doc = Document()
    doc.levels = {'Ground': 0.0, 'Floor 2': 2.7}
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))

    doc.add(Entity(
        'floor',
        {
            'points': [(-8.0, -8.0), (8.0, -8.0), (8.0, 8.0), (-8.0, 8.0)],
            'z': 2.7,
            'thickness': 0.15,
        },
        id='rotated-upper-floor',
    ))

    stack = CommandStack(doc)
    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0))
    tx.update(4.0, 4.0)
    stair_id = tx.commit()

    stair = doc.get(stair_id)
    assert stair.params['layout'] == 'straight'
    assert 40.0 < stair.params['angle_deg'] < 50.0

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    slab = evaluation.body('rotated-upper-floor').payload

    edge_vertices = []
    for tri, role in zip(slab.triangles, slab.triangle_surfaces):
        if role != 'stair_opening_edge':
            continue
        edge_vertices.extend(slab.vertices[index] for index in tri)

    unique_xy = sorted({(round(v[0], 6), round(v[1], 6)) for v in edge_vertices})
    assert len(unique_xy) >= 4

    # An axis-aligned rectangle would have exactly two distinct Xs and Ys.
    # A rotated opening must expose more than two in at least one axis.
    xs = {x for x, _ in unique_xy}
    ys = {y for _, y in unique_xy}
    assert len(xs) > 2 or len(ys) > 2



def test_l_stair_opening_is_composed_from_multiple_flight_pieces():
    candidates = solve_stair_candidates(
        0.0,
        2.85,
        (0.0, 0.0),
        (2.0, 0.0),
        upper_floor_z=2.7,
        upper_slab_thickness=0.15,
    )
    candidate = next(c for c in candidates if c.layout == 'l' and c.turn_direction == 1)

    pieces = stair_opening_polygons(candidate)

    assert len(pieces) >= 2
    assert all(len(piece) == 4 for piece in pieces)


def test_u_stair_opening_is_composed_from_multiple_flight_pieces():
    candidates = solve_stair_candidates(
        0.0,
        2.85,
        (0.0, 0.0),
        (1.6, 0.0),
        upper_floor_z=2.7,
        upper_slab_thickness=0.15,
    )
    candidate = next(c for c in candidates if c.layout == 'u' and c.turn_direction == 1)

    pieces = stair_opening_polygons(candidate)

    assert len(pieces) >= 3
    assert all(len(piece) == 4 for piece in pieces)


def test_stair_options_offer_every_layout_and_keep_the_chosen_one_while_moving():
    doc = _two_level_document()
    tx = StairPlaceTransaction(doc, CommandStack(doc), (0.0, 0.0))
    for pointer in ((5.0, 0.0), (2.0, 0.0)):
        tx.update(*pointer)
        offered = [c.layout for c in tx.candidates[:4]]
        assert sorted(offered) == ['l', 'spiral', 'straight', 'u']

    tx.update(5.0, 0.0)
    while tx.active_candidate.layout != 'spiral':
        tx.cycle_candidate(1)
    for pointer in ((4.0, 0.5), (2.0, 0.0), (5.5, 0.0)):
        tx.update(*pointer)
        assert tx.active_candidate.layout == 'spiral'


def test_stair_layout_can_be_chosen_explicitly_before_placing():
    doc = _two_level_document()
    stack = CommandStack(doc)
    tx = StairPlaceTransaction(doc, stack, (0.0, 0.0), layout='u')
    tx.update(5.0, 0.0)
    assert tx.active_candidate.layout == 'u'
    stair_id = tx.commit()
    assert doc.get(stair_id).params['layout'] == 'u'


def test_plan_pointer_stair_uses_the_chosen_layout_and_tab_cycles():
    from archforge.core.viewport import PointerController, PointerEvent

    doc = _two_level_document()
    controller = PointerController(doc, CommandStack(doc))
    controller.stair_layout = 'l'
    controller.set_tool('stair')
    controller.pointer_down(PointerEvent(0.0, 0.0))
    controller.pointer_move(PointerEvent(5.0, 0.0))
    assert controller.active.active_candidate.layout == 'l'
    controller.cycle_option(1)
    assert controller.active.active_candidate.layout != 'l'
    result = controller.pointer_up(PointerEvent(5.0, 0.0))
    assert doc.get(result.entity_id).params['layout'] != 'l'


def _ground_room_with_flat_roof():
    doc = Document()
    for a, b in (((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                'height': 2.7, 'thickness': 0.2}))
    stack = CommandStack(doc)
    stack.execute(CreateRoomRoofs([doc.active_room_faces()[0].signature], thickness=0.20))
    return doc, stack


def test_external_stair_climbs_to_the_roof_terrace_without_a_second_floor():
    doc, stack = _ground_room_with_flat_roof()
    assert set(doc.levels) == {'Ground'}
    roof = next(e for e in doc.entities.values() if e.kind == 'room_roof')
    from archforge.architecture.rooms import room_slab_geometry
    geom = room_slab_geometry(doc, roof)
    roof_top = float(geom['z']) + float(geom['thickness'])

    # Outside the building, running along the east wall.
    tx = StairPlaceTransaction(doc, stack, (4.8, -2.0))
    tx.update(4.8, 3.0)
    stair_id = tx.commit()
    stair = doc.get(stair_id)
    assert abs(stair.params['upper_z'] - roof_top) < 1e-9
    assert abs(stair.params['riser_count'] * stair.params['riser_height'] - roof_top) < 1e-6


def test_stair_still_needs_a_target_without_floor_or_roof():
    doc = Document()
    with pytest.raises(ValueError):
        StairPlaceTransaction(doc, CommandStack(doc), (0.0, 0.0))


def test_stair_on_a_slab_is_selectable_by_click_in_the_plan_on_both_storeys():
    """Reported: the stair could not be selected — the Auto Floor slab was drawn over it and took the click."""
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from archforge.architecture.stairs import candidate_from_params
    from archforge.core.commands import AddEntity
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show()
    try:
        doc = w.doc
        doc.levels['Floor 2'] = 2.7
        for z in (0.0, 2.7):
            for s in [(0, 0, 6, 0), (6, 0, 6, 5), (6, 5, 0, 5), (0, 5, 0, 0)]:
                w.stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': z,
                                                          'height': 2.7, 'thickness': 0.2})))
        tx = StairPlaceTransaction(doc, w.stack, (1.0, 1.0)); tx.update(5.0, 1.0); sid = tx.commit()
        w._create_auto_floors()
        assert any(e.kind == 'room_floor' for e in doc.entities.values())
        fp = stair_footprint(candidate_from_params(doc.get(sid).params))
        cx, cy = sum(p[0] for p in fp) / len(fp), sum(p[1] for p in fp) / len(fp)
        w._set_active_tool('select')
        for level in ('Ground', 'Floor 2'):
            w._activate_level_by_name(level); w._redraw_views(all_views=True); app.processEvents()
            doc.select([])
            pos = w.plan_view.mapFromScene(QPointF(cx, cy))
            QTest.mouseClick(w.plan_view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
            assert doc.selection == [sid], level
        # The slab itself stays selectable where nothing else is on it.
        w._activate_level_by_name('Ground'); w._redraw_views(all_views=True); app.processEvents()
        doc.select([])
        QTest.mouseClick(w.plan_view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                         w.plan_view.mapFromScene(QPointF(5.0, 4.2)))
        assert [doc.get(i).kind for i in doc.selection] == ['room_floor']
    finally:
        w._mark_clean(); w.close(); app.processEvents()
