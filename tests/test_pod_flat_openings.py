import math

from archforge.core.model import Document, Entity


def _pod(rotation=0.0):
    return Entity('pod', {
        'cx': 0.0, 'cy': 0.0, 'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0, 'height': 4.0,
        'shell_thickness': 0.18, 'rotation': rotation,
    })


def _door(parent_id, u=0.0):
    return Entity('door', {
        'surface_u': u, 'width': 0.9, 'height': 2.1, 'sill': 0.0,
        'flat_margin': 0.25,
    }, parent_id=parent_id)


def test_standard_door_can_be_attached_to_pod_shell():
    doc = Document(); pod = _pod(); doc.add(pod)
    door = _door(pod.id, 0.0)
    doc.add(door)
    assert doc.get(door.id).parent_id == pod.id
    assert math.isclose(doc.get(door.id).params['surface_u'], 0.0)


def test_pod_opening_materializes_stable_planar_patch():
    from archforge.architecture.openings import infer_organic_opening_patches, pod_opening_patch_geometry

    doc = Document(); pod = _pod(); doc.add(pod); door = _door(pod.id, 0.125); doc.add(door)
    result = infer_organic_opening_patches(doc)
    assert len(result.active_ids) == 1
    patch = doc.get(result.active_ids[0])
    assert patch.kind == 'organic_opening_patch'
    assert patch.params['opening_id'] == door.id
    assert patch.params['host_id'] == pod.id
    assert patch.params['status'] == 'active'

    geom = pod_opening_patch_geometry(doc, door.id)
    assert geom is not None
    points = geom['points']
    assert len(points) == 4
    # All four corners lie on one vertical plane, and the patch is wider/taller than the opening.
    px, py = geom['plane']['point']; nx, ny = geom['plane']['normal']
    assert all(abs((x-px)*nx + (y-py)*ny) < 1e-8 for x, y, _ in points)
    assert geom['patch_width'] > door.params['width']
    assert geom['patch_height'] >= door.params['height']


def test_pod_opening_patch_follows_host_rotation_without_changing_semantic_u():
    from archforge.architecture.openings import pod_opening_patch_geometry

    doc = Document(); pod = _pod(0.0); doc.add(pod); door = _door(pod.id, 0.0); doc.add(door)
    before = pod_opening_patch_geometry(doc, door.id)
    u_before = door.params['surface_u']
    doc.update(pod.id, {'rotation': 90.0})
    after = pod_opening_patch_geometry(doc, door.id)

    assert door.params['surface_u'] == u_before
    assert before is not None and after is not None
    n0 = before['plane']['normal']; n1 = after['plane']['normal']
    assert abs(n0[0]) > 0.9 and abs(n0[1]) < 0.1
    assert abs(n1[1]) > 0.9 and abs(n1[0]) < 0.1
