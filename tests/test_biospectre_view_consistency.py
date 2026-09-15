from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx, cy, rotation=0.0):
    return Entity('pod', {
        'cx': float(cx), 'cy': float(cy), 'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0, 'height': 4.0,
        'shell_thickness': 0.18, 'rotation': float(rotation),
    })


def _meta(primitive):
    return dict(primitive.meta)


def test_active_junction_is_explicit_in_every_supported_view_contract():
    doc = Document()
    a = _pod(0.0, 0.0, 20.0)
    b = _pod(4.0, 0.4, -15.0)
    doc.add(a); doc.add(b)
    result = infer_organic_junctions(doc)
    junction_id = result.active_ids[0]

    plan = build_plan_frame(doc)
    plan_pods = [p for p in plan.primitives if p.entity_id in (a.id, b.id)]
    assert all(p.role == 'pod-junction-clipped' for p in plan_pods)
    assert any(p.entity_id == junction_id and p.role == 'organic-junction' for p in plan.primitives)

    for axis in ('XY', 'XZ', 'YZ'):
        frame = build_view_frame(doc, axis)
        junctions = [p for p in frame.primitives if p.entity_id == junction_id]
        assert junctions and junctions[0].role == 'organic-junction'
        pods = [p for p in frame.primitives if p.entity_id in (a.id, b.id)]
        assert len(pods) == 2
        if axis == 'XY':
            assert all(p.role == 'pod-junction-clipped' for p in pods)
        else:
            # Elevation projection cannot yet faithfully project the clipped sampled shell.
            # It must say so explicitly rather than presenting an unqualified full pod outline.
            assert all(p.role == 'pod-junction-unclipped-unsupported' for p in pods)
            assert all(_meta(p).get('junction_projection') == 'unsupported' for p in pods)

    preview = PreviewBackend().evaluate(doc)
    assert preview.body(junction_id).quality == 'preview'
    tess = TessellatedPreviewBackend().evaluate(doc)
    assert tess.body(junction_id).payload.triangles
    assert tess.body(a.id).payload.triangles and tess.body(b.id).payload.triangles
