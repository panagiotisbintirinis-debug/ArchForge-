from archforge.core.model import Document, Entity
from archforge.core.view_frame import build_view_frame
from archforge.organic.biospectre import junction_key_for_pods


def _pod(pod_id, cx, cy):
    return Entity(
        'pod',
        {
            'cx': cx,
            'cy': cy,
            'floor_level': 0.0,
            'diameter_x': 8.0,
            'diameter_y': 8.0,
            'height': 4.0,
            'shell_thickness': 0.2,
            'rotation': 0.0,
        },
        id=pod_id,
    )


def _joined_pair():
    doc = Document()
    a = _pod('pod-a', 0.0, 0.0)
    b = _pod('pod-b', 6.0, 0.0)
    doc.add(a)
    doc.add(b)
    junction = Entity(
        'organic_junction',
        {
            'component_a': a.id,
            'component_b': b.id,
            'junction_key': junction_key_for_pods(a.id, b.id),
            'status': 'active',
        },
        id='junction-a-b',
    )
    doc.add(junction)
    return doc


def test_axis_aligned_planar_junction_clips_xz_pod_shells():
    doc = _joined_pair()
    frame = build_view_frame(doc, 'XZ')

    pods = [p for p in frame.primitives if p.entity_id in {'pod-a', 'pod-b'}]
    assert len(pods) == 2
    assert all(p.role == 'pod-junction-clipped' for p in pods)
    assert all(p.kind == 'polygon' for p in pods)
    assert all(dict(p.meta).get('junction_projection') == 'supported-axis-aligned' for p in pods)
    assert not any(p.role == 'pod-junction-unclipped-unsupported' for p in pods)

    # The separator is x=3.0 for equal pods: each projected shell stays on its own side.
    a = next(p for p in pods if p.entity_id == 'pod-a')
    b = next(p for p in pods if p.entity_id == 'pod-b')
    assert max(x for x, _ in a.points) <= 3.0 + 1e-9
    assert min(x for x, _ in b.points) >= 3.0 - 1e-9


def test_depth_aligned_planar_junction_is_supported_without_changing_yz_silhouette():
    doc = _joined_pair()
    frame = build_view_frame(doc, 'YZ')

    pods = [p for p in frame.primitives if p.entity_id in {'pod-a', 'pod-b'}]
    assert len(pods) == 2
    assert all(p.role == 'pod-junction-clipped' for p in pods)
    assert all(dict(p.meta).get('junction_projection') == 'supported-axis-aligned' for p in pods)
    assert not any(p.role == 'pod-junction-unclipped-unsupported' for p in pods)
