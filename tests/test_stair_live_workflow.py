import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from archforge.architecture.stairs import solve_stair_candidates
from archforge.core.commands import CommandStack
from archforge.core.interaction import StairPlaceTransaction
from archforge.core.model import Document, WorkPlane
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
