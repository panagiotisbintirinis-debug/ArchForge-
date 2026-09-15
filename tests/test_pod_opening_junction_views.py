import math
import pytest

from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame, selection_handles
from archforge.core.view_frame import build_view_frame, entity_view_primitives
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx, cy=0.0, rotation=0.0):
    return Entity('pod', {
        'cx': float(cx), 'cy': float(cy),
        'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0,
        'height': 4.0, 'shell_thickness': 0.18,
        'rotation': float(rotation),
    })


def _door(parent_id, u):
    return Entity('door', {
        'surface_u': float(u), 'width': 0.9, 'height': 2.1,
        'sill': 0.0, 'flat_margin': 0.25,
    }, parent_id=parent_id)


def _window(parent_id, u, sill=1.0, height=1.2):
    return Entity('window', {
        'surface_u': float(u), 'width': 1.0, 'height': height,
        'sill': sill, 'flat_margin': 0.25,
    }, parent_id=parent_id)


def _setup_joined_pods_with_openings():
    doc = Document()
    a = _pod(0.0)
    b = _pod(4.0)
    doc.add(a); doc.add(b)
    # Door on +X side of pod A facing pod B (within junction cut)
    door_facing = _door(a.id, 0.0)
    # Window on -X outer side of pod A away from B
    window_outer = _window(a.id, 0.5)
    doc.add(door_facing); doc.add(window_outer)
    infer_organic_junctions(doc)
    return doc, a, b, door_facing, window_outer


def test_plan_frame_suppresses_pod_openings_occluded_by_active_junction():
    doc, a, b, door_facing, window_outer = _setup_joined_pods_with_openings()

    frame = build_plan_frame(doc)
    opening_eids = {p.entity_id for p in frame.primitives if p.role == 'opening'}

    # Facing door is removed by junction cut; must not be drawn floating into pod B.
    assert door_facing.id not in opening_eids
    # Outer window is on retained shell; must remain visible.
    assert window_outer.id in opening_eids


def test_plan_frame_suppresses_selection_handles_for_occluded_pod_openings():
    doc, a, b, door_facing, window_outer = _setup_joined_pods_with_openings()
    doc.selection = [door_facing.id, window_outer.id]

    frame = build_plan_frame(doc)
    handle_eids = {h.entity_id for h in frame.handles}

    assert door_facing.id not in handle_eids
    assert window_outer.id in handle_eids


def test_reseparating_pods_restores_pod_openings_in_plan_frame():
    doc, a, b, door_facing, window_outer = _setup_joined_pods_with_openings()
    doc.selection = [door_facing.id]

    doc.update(b.id, {'cx': 30.0})
    infer_organic_junctions(doc)

    frame = build_plan_frame(doc)
    opening_eids = {p.entity_id for p in frame.primitives if p.role == 'opening'}
    assert door_facing.id in opening_eids
    assert window_outer.id in opening_eids

    handle_eids = {h.entity_id for h in frame.handles}
    assert door_facing.id in handle_eids


def test_view_frame_renders_pod_openings_across_all_ortho_axes():
    doc = Document()
    a = _pod(0.0)
    doc.add(a)
    win = _window(a.id, 0.25, sill=0.8, height=1.4)
    doc.add(win)

    xy = build_view_frame(doc, 'XY')
    xz = build_view_frame(doc, 'XZ')
    yz = build_view_frame(doc, 'YZ')

    xy_ops = [p for p in xy.primitives if p.entity_id == win.id]
    xz_ops = [p for p in xz.primitives if p.entity_id == win.id]
    yz_ops = [p for p in yz.primitives if p.entity_id == win.id]

    assert len(xy_ops) == 1 and xy_ops[0].kind == 'line'
    assert len(xz_ops) == 1 and xz_ops[0].kind == 'polygon'
    assert len(yz_ops) == 1 and yz_ops[0].kind == 'polygon'

    # Elevation polygons must have vertical span matching [floor + sill, floor + sill + height]
    zs_xz = [pt[1] for pt in xz_ops[0].points]
    assert min(zs_xz) == pytest.approx(0.8)
    assert max(zs_xz) == pytest.approx(2.2)


def test_view_frame_suppresses_occluded_pod_openings_and_shows_junctions():
    doc, a, b, door_facing, window_outer = _setup_joined_pods_with_openings()

    for axis in ('XY', 'XZ', 'YZ'):
        frame = build_view_frame(doc, axis)
        op_eids = {p.entity_id for p in frame.primitives if p.role == 'opening'}
        assert door_facing.id not in op_eids
        assert window_outer.id in op_eids

        junction_prims = [p for p in frame.primitives if p.role == 'organic-junction']
        assert len(junction_prims) == 1
        if axis == 'XY':
            assert junction_prims[0].kind == 'line'
        else:
            assert junction_prims[0].kind == 'polygon'
