import math

from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.organic.biospectre import junction_plane
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx, cy, rotation=0.0):
    return Entity('pod', {
        'cx': float(cx),
        'cy': float(cy),
        'floor_level': 0.0,
        'diameter_x': 8.0,
        'diameter_y': 6.0,
        'height': 4.0,
        'shell_thickness': 0.18,
        'rotation': float(rotation),
    })


def _signed_xy(point, plane):
    x, y, _ = point
    px, py = plane['point']
    nx, ny = plane['normal']
    return (x - px) * nx + (y - py) * ny


def test_active_junction_clips_each_pod_shell_to_its_own_side():
    doc = Document()
    a = _pod(0.0, 0.0, 20.0)
    b = _pod(4.0, 0.4, -15.0)
    doc.add(a)
    doc.add(b)

    full_eval = TessellatedPreviewBackend().evaluate(doc)
    full_a = full_eval.body(a.id).payload
    full_b = full_eval.body(b.id).payload

    infer_organic_junctions(doc)
    clipped_eval = TessellatedPreviewBackend().evaluate(doc)
    clipped_a = clipped_eval.body(a.id).payload
    clipped_b = clipped_eval.body(b.id).payload

    plane = junction_plane(a.params, b.params)
    assert plane is not None
    sign_a = -1.0 if _signed_xy((a.params['cx'], a.params['cy'], 0.0), plane) < 0 else 1.0
    sign_b = -1.0 if _signed_xy((b.params['cx'], b.params['cy'], 0.0), plane) < 0 else 1.0

    assert len(clipped_a.triangles) < len(full_a.triangles)
    assert len(clipped_b.triangles) < len(full_b.triangles)
    assert all(sign_a * _signed_xy(v, plane) >= -1e-8 for v in clipped_a.vertices)
    assert all(sign_b * _signed_xy(v, plane) >= -1e-8 for v in clipped_b.vertices)


def test_clipped_shell_boundary_matches_flat_junction_plane():
    doc = Document()
    a = _pod(0.0, 0.0, 35.0)
    b = _pod(4.2, 0.2, -10.0)
    doc.add(a)
    doc.add(b)
    result = infer_organic_junctions(doc)
    junction_id = result.active_ids[0]

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    junction_mesh = evaluation.body(junction_id).payload
    plane = junction_plane(a.params, b.params)
    assert plane is not None

    assert junction_mesh.triangles
    assert all(abs(_signed_xy(v, plane)) < 1e-8 for v in junction_mesh.vertices)

    for pod in (a, b):
        shell = evaluation.body(pod.id).payload
        on_plane = [v for v in shell.vertices if abs(_signed_xy(v, plane)) < 1e-8]
        assert len(on_plane) >= 2


def test_dormant_junction_no_longer_clips_reseparated_pod():
    doc = Document()
    a = _pod(0.0, 0.0)
    b = _pod(4.0, 0.0)
    doc.add(a)
    doc.add(b)
    infer_organic_junctions(doc)

    clipped_count = len(TessellatedPreviewBackend().evaluate(doc).body(a.id).payload.triangles)

    doc.update(b.id, {'cx': 30.0})
    infer_organic_junctions(doc)
    restored = TessellatedPreviewBackend().evaluate(doc).body(a.id).payload

    reference = Document()
    only_a = Entity('pod', dict(a.params))
    reference.add(only_a)
    full = TessellatedPreviewBackend().evaluate(reference).body(only_a.id).payload

    assert len(restored.triangles) > clipped_count
    assert len(restored.triangles) == len(full.triangles)
