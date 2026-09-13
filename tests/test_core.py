import math
from archforge.core.model import Document, Entity, WorkPlane
from archforge.core.commands import CommandStack, AddEntity, UpdateEntity, MoveEntities
from archforge.core.snapping import points_for, best_snap
from archforge.core.interaction import WallDrawTransaction, BoxStretchTransaction
from archforge.core.viewport import IncrementalViewportAdapter, PointerController, PointerEvent
from archforge.organic.biospectre import profile_radius, overlap, junction_plane
from archforge.architecture.floors import area, perimeter, centroid


def box(x=0, y=0):
    return Entity('box', {'x': x, 'y': y, 'z': 0, 'width': 4, 'depth': 2, 'height': 3, 'rotation': 0})


def wall():
    return Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': .15})


def pod(cx=0):
    return Entity('pod', {'cx': cx, 'cy': 0, 'floor_level': 1, 'diameter_x': 4, 'diameter_y': 4, 'height': 2, 'shell_thickness': .1})


def test_document_validation_and_selection():
    d = Document(); e = box(); d.add(e); d.select([e.id])
    assert d.get(e.id).params['width'] == 4 and d.selection == [e.id]


def test_negative_dimension_rejected():
    d = Document(); e = box(); e.params['width'] = -1
    try:
        d.add(e); assert False
    except ValueError:
        pass


def test_command_undo_redo():
    d = Document(); s = CommandStack(d); e = box(); s.execute(AddEntity(e)); s.execute(UpdateEntity(e.id, {'width': 8}))
    assert d.get(e.id).params['width'] == 8
    s.undo(); assert d.get(e.id).params['width'] == 4
    s.redo(); assert d.get(e.id).params['width'] == 8


def test_multi_move_and_undo():
    d = Document(); a = box(); b = box(5); d.add(a); d.add(b); s = CommandStack(d)
    s.execute(MoveEntities([a.id, b.id], 2, 3)); assert (d.get(a.id).params['x'], d.get(b.id).params['x']) == (2, 7)
    s.undo(); assert (d.get(a.id).params['x'], d.get(b.id).params['x']) == (0, 5)


def test_snapping_prefers_wall_endpoint():
    d = Document(); e = wall(); d.add(e)
    assert {'endpoint', 'midpoint'} <= {p.kind for p in points_for(d, e.id)}
    assert best_snap(d, 4.04, .02, .1, 1.0).kind == 'endpoint'


def test_workplane_roundtrip():
    w = WorkPlane(origin=(1, 2, 3)); p = w.unproject(4, 5)
    assert p == (5, 7, 3) and w.project(p) == (4, 5)


def test_wall_transaction_exact_length():
    d = Document(); s = CommandStack(d); tx = WallDrawTransaction(d, s, (0, 0), grid=None); tx.update(3, 4); eid = tx.commit(exact_length=10)
    p = d.get(eid).params
    assert math.isclose(math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1']), 10, abs_tol=1e-9)


def test_box_stretch_preserves_opposite_edge():
    d = Document(); e = box(); d.add(e); s = CommandStack(d); left = e.params['x'] - e.params['width'] / 2
    tx = BoxStretchTransaction(d, s, e.id, 'right'); tx.update(x=5); tx.commit(); p = d.get(e.id).params
    assert math.isclose(p['x'] - p['width']/2, left, abs_tol=1e-9) and math.isclose(p['x'] + p['width']/2, 5, abs_tol=1e-9)


def test_biospectre_hard_floor_and_junction():
    a = pod(0).params; b = pod(2).params
    assert profile_radius(a, .999) is None and profile_radius(a, 1) == (2, 2)
    assert overlap(a, b) and junction_plane(a, b) is not None


def test_floor_metrics():
    pts = [(0,0),(4,0),(4,3),(0,3)]
    assert area(pts) == 12 and perimeter(pts) == 14 and centroid(pts) == (2, 1.5)


def test_incremental_viewport_tracks_only_dirty():
    d = Document(); a = box(); b = box(5); d.add(a); d.add(b); ad = IncrementalViewportAdapter(d)
    first = ad.consume(); assert {r[0] for r in first['updates']} == {a.id, b.id}
    d.update(a.id, {'width': 5}); second = ad.consume(); assert [r[0] for r in second['updates']] == [a.id]


def test_pointer_move_preview_is_non_destructive():
    d = Document(); e = box(); d.add(e); d.select([e.id]); s = CommandStack(d); c = PointerController(d, s); c.set_tool('move')
    c.pointer_down(PointerEvent(0, 0)); preview = c.pointer_move(PointerEvent(2, 3))
    assert d.get(e.id).params['x'] == 0 and preview.geometry['entities'][e.id]['x'] == 2
    c.pointer_up(PointerEvent(2, 3)); assert (d.get(e.id).params['x'], d.get(e.id).params['y']) == (2, 3)
