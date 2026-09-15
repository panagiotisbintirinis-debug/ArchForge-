from archforge.core.model import Document, Entity
from archforge.architecture.openings import infer_organic_opening_patches
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.organic.junctions import infer_organic_junctions


def _pod(cx):
    return Entity('pod', {
        'cx': float(cx), 'cy': 0.0, 'floor_level': 0.0,
        'diameter_x': 8.0, 'diameter_y': 6.0,
        'height': 4.0, 'shell_thickness': 0.18,
        'rotation': 0.0,
    })


def _door(parent_id, u):
    return Entity('door', {
        'surface_u': float(u), 'width': 0.9, 'height': 2.1,
        'sill': 0.0, 'flat_margin': 0.25,
    }, parent_id=parent_id)


def _body_ids(evaluation):
    return {body.entity_id for body in evaluation.bodies}


def _setup_facing_opening():
    doc = Document()
    a = _pod(0.0); b = _pod(4.0)
    doc.add(a); doc.add(b)
    door = _door(a.id, 0.0)  # +X side, directly inside the A/B junction region.
    doc.add(door)
    patch_id = infer_organic_opening_patches(doc).active_ids[0]
    infer_organic_junctions(doc)
    return doc, a, b, door, patch_id


def test_opening_patch_on_shell_removed_by_junction_is_not_rendered_floating():
    doc, _, _, door, patch_id = _setup_facing_opening()

    fast = PreviewBackend().evaluate(doc)
    tess = TessellatedPreviewBackend().evaluate(doc)

    assert door.id in doc.entities and patch_id in doc.entities
    assert patch_id not in _body_ids(fast)
    assert patch_id not in _body_ids(tess)
    assert any(i.entity_id == patch_id and 'junction' in i.message.lower() for i in fast.issues)
    assert any(i.entity_id == patch_id and 'junction' in i.message.lower() for i in tess.issues)


def test_junction_occlusion_is_reversible_without_changing_opening_or_patch_identity():
    doc, _, b, door, patch_id = _setup_facing_opening()
    assert patch_id not in _body_ids(TessellatedPreviewBackend().evaluate(doc))

    doc.update(b.id, {'cx': 30.0})
    infer_organic_junctions(doc)
    restored = TessellatedPreviewBackend().evaluate(doc)

    assert door.id in doc.entities
    assert patch_id in doc.entities
    assert patch_id in _body_ids(restored)


def test_opening_on_retained_outer_shell_remains_visible_with_active_junction():
    doc = Document()
    a = _pod(0.0); b = _pod(4.0)
    doc.add(a); doc.add(b)
    door = _door(a.id, 0.5)  # -X outer side, away from B.
    doc.add(door)
    patch_id = infer_organic_opening_patches(doc).active_ids[0]
    infer_organic_junctions(doc)

    evaluation = TessellatedPreviewBackend().evaluate(doc)
    assert patch_id in _body_ids(evaluation)
