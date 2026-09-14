from archforge.core.model import Document, Entity
from archforge.organic.biospectre import all_pod_junctions, junction_plane


def _pod(cx, cy, rotation):
    return {
        'cx': float(cx),
        'cy': float(cy),
        'floor_level': 0.0,
        'diameter_x': 8.0,
        'diameter_y': 2.0,
        'height': 4.0,
        'shell_thickness': 0.18,
        'rotation': float(rotation),
    }


def test_rotated_slender_pods_do_not_false_positive_along_short_world_axis():
    # Both ellipses are rotated 90 degrees, so their short semi-axis (1 m) points in X.
    # Centers 5 m apart in X cannot overlap: available radial reach is only 1+1=2 m.
    a = _pod(0.0, 0.0, 90.0)
    b = _pod(5.0, 0.0, 90.0)
    assert junction_plane(a, b) is None


def test_rotated_slender_pods_overlap_along_long_world_axis():
    # After a 90-degree rotation the long semi-axis (4 m) points in world Y, so pods
    # separated by 5 m in Y do overlap because their combined radial reach is 8 m.
    a = _pod(0.0, 0.0, 90.0)
    b = _pod(0.0, 5.0, 90.0)
    plane = junction_plane(a, b)
    assert plane is not None
    assert plane['normal'][0] == 0.0
    assert plane['normal'][1] == 1.0


def test_document_junction_query_uses_rotated_organic_geometry():
    doc = Document()
    a = Entity('pod', _pod(0.0, 0.0, 90.0))
    b = Entity('pod', _pod(5.0, 0.0, 90.0))
    c = Entity('pod', _pod(0.0, 5.0, 90.0))
    for pod in (a, b, c):
        doc.add(pod)

    junctions = all_pod_junctions(doc)
    pairs = {frozenset((j['pod_a'], j['pod_b'])) for j in junctions.values()}
    assert frozenset((a.id, b.id)) not in pairs
    assert frozenset((a.id, c.id)) in pairs
