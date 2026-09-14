from archforge.core.model import Document, Entity
from archforge.organic.biospectre import (
    overlap,
    junction_plane,
    find_pod_junctions,
    all_pod_junctions,
    junction_key_for_pods,
)


def _pod(cx=0, cy=0, floor_level=0, dx=4, dy=4, height=3):
    return Entity('pod', {
        'cx': cx,
        'cy': cy,
        'floor_level': floor_level,
        'diameter_x': dx,
        'diameter_y': dy,
        'height': height,
        'shell_thickness': 0.15,
        'rotation': 0,
    })


def test_overlapping_pods_generate_junction():
    doc = Document()
    p1 = _pod(cx=0, cy=0)
    p2 = _pod(cx=3, cy=0)  # Overlaps since distance 3 < (4+4)/2 = 4
    doc.add(p1)
    doc.add(p2)

    juncs = find_pod_junctions(doc, p1.id)
    assert len(juncs) == 1
    j = juncs[0]
    assert j['other_pod_id'] == p2.id
    assert j['junction_key'] == junction_key_for_pods(p1.id, p2.id)

    plane = j['plane']
    assert plane['point'][0] > 0 and plane['point'][0] < 3
    assert plane['normal'][0] > 0
    assert plane['z0'] == 0
    assert plane['z1'] == 3


def test_disjoint_pods_have_no_junctions():
    doc = Document()
    p1 = _pod(cx=0, cy=0)
    p2 = _pod(cx=10, cy=0)  # Distance 10 > 4
    doc.add(p1)
    doc.add(p2)

    assert find_pod_junctions(doc, p1.id) == []
    assert all_pod_junctions(doc) == {}


def test_xy_overlap_without_vertical_overlap_has_no_junction():
    doc = Document()
    p1 = _pod(cx=0, cy=0, floor_level=0, height=3)
    p2 = _pod(cx=3, cy=0, floor_level=4, height=2)
    doc.add(p1)
    doc.add(p2)

    assert find_pod_junctions(doc, p1.id) == []
    assert all_pod_junctions(doc) == {}


def test_junction_vertical_extent_is_shared_height_interval():
    doc = Document()
    p1 = _pod(cx=0, cy=0, floor_level=0, height=3)
    p2 = _pod(cx=3, cy=0, floor_level=2, height=4)
    doc.add(p1)
    doc.add(p2)

    juncs = find_pod_junctions(doc, p1.id)
    assert len(juncs) == 1
    assert juncs[0]['plane']['z0'] == 2
    assert juncs[0]['plane']['z1'] == 3


def test_all_pod_junctions_multi_cluster():
    doc = Document()
    # 3 pods in a chain: A overlaps B, B overlaps C, but A and C are disjoint
    pA = _pod(cx=0, cy=0)
    pB = _pod(cx=2.5, cy=0)
    pC = _pod(cx=5.0, cy=0)
    doc.add(pA)
    doc.add(pB)
    doc.add(pC)

    all_j = all_pod_junctions(doc)
    assert len(all_j) == 2
    assert junction_key_for_pods(pA.id, pB.id) in all_j
    assert junction_key_for_pods(pB.id, pC.id) in all_j
    assert junction_key_for_pods(pA.id, pC.id) not in all_j


def test_hidden_pod_does_not_create_junction():
    doc = Document()
    p1 = _pod(cx=0, cy=0)
    p2 = _pod(cx=3, cy=0)
    p2.visible = False
    doc.add(p1)
    doc.add(p2)

    assert find_pod_junctions(doc, p1.id) == []
    assert all_pod_junctions(doc) == {}
