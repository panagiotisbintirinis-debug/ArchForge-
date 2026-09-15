from archforge.core.model import Document, Entity
from archforge.organic.biospectre import all_pod_junctions, junction_plane, junction_section_polygon
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx, floor, height=1.0, diameter=4.0):
    return Entity('pod', {
        'cx': float(cx), 'cy': 0.0,
        'floor_level': float(floor),
        'diameter_x': float(diameter), 'diameter_y': float(diameter),
        'height': float(height), 'shell_thickness': 0.18,
        'rotation': 0.0,
    })


def test_xy_overlap_and_z_range_overlap_do_not_create_false_3d_junction():
    # Base footprints overlap: radius 2 + radius 2 > center distance 3.5.
    # Vertical ranges also overlap: A=[0,1], B=[0.9,1.9].
    # But at the first shared slice z=0.9, A has already narrowed to radius ~0.872,
    # so the largest possible shared-slice reach is ~2.872 < 3.5. The upper-half
    # ellipsoids therefore never physically intersect in 3D.
    a = _pod(0.0, 0.0)
    b = _pod(3.5, 0.9)

    assert junction_plane(a.params, b.params) is None
    assert junction_section_polygon(a.params, b.params) is None

    doc = Document(); doc.add(a); doc.add(b)
    assert all_pod_junctions(doc) == {}
    inferred = infer_organic_junctions(doc)
    assert inferred.active_ids == ()
    assert inferred.created_ids == ()


def test_moving_same_staggered_pods_close_enough_creates_real_junction():
    a = _pod(0.0, 0.0)
    b = _pod(2.5, 0.9)

    plane = junction_plane(a.params, b.params)
    assert plane is not None
    assert plane['z0'] == 0.9
    assert plane['z1'] == 1.0
    assert junction_section_polygon(a.params, b.params) is not None

    doc = Document(); doc.add(a); doc.add(b)
    inferred = infer_organic_junctions(doc)
    assert len(inferred.active_ids) == 1
    assert len(inferred.created_ids) == 1
