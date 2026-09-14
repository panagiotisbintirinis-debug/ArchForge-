import math

from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.surfaces import surface_roles
from archforge.organic.biospectre import junction_plane, junction_section_polygon
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


def test_junction_section_is_a_real_planar_polygon_inside_semantic_plane():
    a = _pod(0.0, 0.0, 20.0).params
    b = _pod(4.0, 0.5, -15.0).params
    plane = junction_plane(a, b)
    points = junction_section_polygon(a, b)

    assert plane is not None
    assert points is not None
    assert len(points) >= 4
    px, py = plane['point']
    nx, ny = plane['normal']
    for x, y, z in points:
        assert math.isfinite(x) and math.isfinite(y) and math.isfinite(z)
        assert abs((x - px) * nx + (y - py) * ny) < 1e-8
        assert plane['z0'] - 1e-9 <= z <= plane['z1'] + 1e-9


def test_inference_materializes_stable_organic_junction_geometry():
    doc = Document()
    a = _pod(0.0, 0.0, 25.0)
    b = _pod(4.0, 0.0, -10.0)
    doc.add(a)
    doc.add(b)

    result = infer_organic_junctions(doc)
    assert len(result.active_ids) == 1
    assert len(result.created_ids) == 1
    junction_id = result.active_ids[0]
    junction = doc.get(junction_id)

    assert junction.kind == 'organic_junction'
    assert junction.params['status'] == 'active'
    assert {junction.params['component_a'], junction.params['component_b']} == {a.id, b.id}
    assert surface_roles(doc, junction_id) == ('junction',)

    preview = PreviewBackend().evaluate(doc)
    assert preview.body(junction_id).payload.primitive == 'organic_junction'

    mesh = TessellatedPreviewBackend().evaluate(doc).body(junction_id).payload
    assert len(mesh.triangles) > 0
    assert set(mesh.triangle_surfaces) == {'junction'}


def test_junction_identity_survives_separation_and_reconnection():
    doc = Document()
    a = _pod(0.0, 0.0)
    b = _pod(4.0, 0.0)
    doc.add(a)
    doc.add(b)

    first = infer_organic_junctions(doc)
    junction_id = first.active_ids[0]

    doc.update(b.id, {'cx': 30.0})
    separated = infer_organic_junctions(doc)
    assert separated.active_ids == ()
    assert junction_id in separated.dormant_ids
    assert doc.get(junction_id).params['status'] == 'dormant'
    assert junction_id not in {body.entity_id for body in TessellatedPreviewBackend().evaluate(doc).bodies}

    doc.update(b.id, {'cx': 4.0})
    rejoined = infer_organic_junctions(doc)
    assert rejoined.created_ids == ()
    assert rejoined.active_ids == (junction_id,)
    assert doc.get(junction_id).params['status'] == 'active'
    assert TessellatedPreviewBackend().evaluate(doc).body(junction_id).payload.triangles
