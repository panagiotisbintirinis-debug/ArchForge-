import math
import pytest

from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
from archforge.geometry.surface_frame import evaluate_surface_point, project_surface_point


def _pod(rotation=0.0):
    return Entity('pod', {
        'cx': 10.0,
        'cy': -4.0,
        'floor_level': 1.0,
        'diameter_x': 8.0,
        'diameter_y': 4.0,
        'height': 3.0,
        'shell_thickness': 0.18,
        'rotation': rotation,
    })


def _shell_point(p, u, v):
    theta = 2.0 * math.pi * u
    phi = 0.5 * math.pi * v
    rx = float(p['diameter_x']) / 2.0
    ry = float(p['diameter_y']) / 2.0
    lx = rx * math.cos(phi) * math.cos(theta)
    ly = ry * math.cos(phi) * math.sin(theta)
    a = math.radians(float(p.get('rotation', 0.0)))
    c, s = math.cos(a), math.sin(a)
    return (
        float(p['cx']) + c * lx - s * ly,
        float(p['cy']) + s * lx + c * ly,
        float(p['floor_level']) + float(p['height']) * math.sin(phi),
    )


def test_pod_shell_uses_intrinsic_coordinates_that_follow_shape_changes():
    doc = Document()
    pod = _pod(rotation=20.0)
    doc.add(pod)
    expected_uv = (0.125, 0.4)
    point = _shell_point(pod.params, *expected_uv)

    uv = project_surface_point(doc, pod.id, 'pod_shell', point)
    assert uv is not None
    assert uv[0] == pytest.approx(expected_uv[0], abs=1e-9)
    assert uv[1] == pytest.approx(expected_uv[1], abs=1e-9)
    assert evaluate_surface_point(doc, pod.id, 'pod_shell', uv) == pytest.approx(point)

    hit = SurfaceHit(pod.id, 'pod_shell', point, (1.0, 0.0, 0.0))
    modifier = sculpt_modifier_from_hit(doc, hit, BrushSpec(0.8), 'pull', 0.2)
    region = modifier.target.subregion
    assert region['coord_system'] == 'surface_uv'
    assert region['uv_center'] == pytest.approx(expected_uv)
    assert 'world_center' not in region

    # The same semantic shell location follows later freeform parameter edits.
    doc.update(pod.id, {'diameter_x': 10.0, 'diameter_y': 6.0, 'height': 4.5, 'rotation': 95.0})
    moved = evaluate_surface_point(doc, pod.id, 'pod_shell', uv)
    assert moved == pytest.approx(_shell_point(doc.get(pod.id).params, *expected_uv))
    assert moved != pytest.approx(point)


def test_rotated_pod_mesh_uses_entity_rotation_in_universal_xyz():
    doc = Document()
    pod = _pod(rotation=90.0)
    doc.add(pod)

    mesh = TessellatedPreviewBackend().evaluate(doc).body(pod.id).payload
    xs = [v[0] for v in mesh.vertices]
    ys = [v[1] for v in mesh.vertices]

    # A 90-degree rotation swaps the XY extents of the unequal ellipse.
    assert (max(xs) - min(xs)) == pytest.approx(4.0, abs=1e-6)
    assert (max(ys) - min(ys)) == pytest.approx(8.0, abs=1e-6)


def test_rotated_pod_fast_preview_bounds_match_rotated_ellipse():
    doc = Document()
    pod = _pod(rotation=90.0)
    doc.add(pod)

    bounds = PreviewBackend().evaluate(doc).body(pod.id).payload.bounds
    (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
    assert xmax - xmin == pytest.approx(4.0, abs=1e-6)
    assert ymax - ymin == pytest.approx(8.0, abs=1e-6)
    assert zmin == pytest.approx(1.0)
    assert zmax == pytest.approx(4.0)
