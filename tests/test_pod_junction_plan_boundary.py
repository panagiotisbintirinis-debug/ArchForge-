import math

from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.organic.biospectre import junction_plane
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx, cy=0.0, rotation=0.0):
    return Entity('pod', {
        'cx': float(cx), 'cy': float(cy),
        'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0,
        'height': 4.0, 'shell_thickness': 0.18,
        'rotation': float(rotation),
    })


def _signed_xy(point, plane):
    px, py = plane['point']
    nx, ny = plane['normal']
    return (point[0] - px) * nx + (point[1] - py) * ny


def test_plan_clips_joined_pod_footprints_to_the_same_flat_interface():
    doc = Document()
    a = _pod(0.0, rotation=20.0)
    b = _pod(4.0, 0.4, rotation=-15.0)
    doc.add(a); doc.add(b)
    inferred = infer_organic_junctions(doc)
    assert len(inferred.active_ids) == 1

    plane = junction_plane(a.params, b.params)
    assert plane is not None
    frame = build_plan_frame(doc)

    pod_primitives = {p.entity_id: p for p in frame.primitives if p.entity_id in (a.id, b.id)}
    assert pod_primitives[a.id].kind == 'polygon'
    assert pod_primitives[b.id].kind == 'polygon'

    sign_a = 1.0 if _signed_xy((a.params['cx'], a.params['cy']), plane) > 0 else -1.0
    sign_b = 1.0 if _signed_xy((b.params['cx'], b.params['cy']), plane) > 0 else -1.0
    assert all(sign_a * _signed_xy(q, plane) >= -1e-7 for q in pod_primitives[a.id].points)
    assert all(sign_b * _signed_xy(q, plane) >= -1e-7 for q in pod_primitives[b.id].points)

    junction_lines = [p for p in frame.primitives if p.role == 'organic-junction']
    assert len(junction_lines) == 1
    junction = junction_lines[0]
    assert junction.kind == 'line'
    assert len(junction.points) == 2
    assert all(abs(_signed_xy(q, plane)) <= 1e-7 for q in junction.points)


def test_reseparating_pods_restores_full_ellipses_and_removes_flat_plan_interface():
    doc = Document()
    a = _pod(0.0)
    b = _pod(4.0)
    doc.add(a); doc.add(b)
    infer_organic_junctions(doc)

    doc.update(b.id, {'cx': 30.0})
    infer_organic_junctions(doc)
    frame = build_plan_frame(doc)

    pod_primitives = {p.entity_id: p for p in frame.primitives if p.entity_id in (a.id, b.id)}
    assert pod_primitives[a.id].kind == 'ellipse'
    assert pod_primitives[b.id].kind == 'ellipse'
    assert not [p for p in frame.primitives if p.role == 'organic-junction']
