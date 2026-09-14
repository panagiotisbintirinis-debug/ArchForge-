from archforge.architecture.intent import infer_architecture
from archforge.architecture.room_identity import room_id_for_signature
from archforge.architecture.topology import room_faces
from archforge.core.commands import MoveEntities
from archforge.core.model import Document, Entity
from archforge.geometry.selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
from archforge.geometry.sculpt import SculptedPreviewBackend


def _closed_house():
    doc = Document()
    walls = []
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))]:
        wall = Entity(
            'wall',
            {
                'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                'z': 0, 'height': 2.8, 'thickness': 0.2,
            },
        )
        doc.add(wall)
        walls.append(wall.id)
    return doc, walls


def test_room_identity_survives_identical_boundary_wall_redraw():
    """Topology may change IDs; the semantic room identity must survive equivalent redraw."""
    doc, walls = _closed_house()
    before = doc.active_room_faces()
    assert len(before) == 1
    old_signature = before[0].signature
    old_room_id = room_id_for_signature(doc, old_signature)
    assert old_room_id is not None
    doc.set_room_metadata(old_signature, name='Living Room', use='living')
    infer_architecture(doc)
    old_derived_ids = {
        e.id for e in doc.entities.values() if e.kind.startswith('room_')
    }

    old = doc.get(walls[0]).clone()
    doc.remove(old.id)
    replacement = Entity('wall', dict(old.params))
    doc.add(replacement)

    after = doc.active_room_faces()
    assert len(after) == 1
    new_signature = after[0].signature
    new_room_id = room_id_for_signature(doc, new_signature)

    assert new_signature != old_signature
    assert new_room_id == old_room_id
    assert doc.room_metadata(new_signature) == {'name': 'Living Room', 'use': 'living'}

    infer_architecture(doc)
    new_derived_ids = {
        e.id for e in doc.entities.values() if e.kind.startswith('room_')
    }
    assert new_derived_ids == old_derived_ids
    assert all(e.params.get('room_id') == old_room_id for e in doc.entities.values() if e.kind.startswith('room_'))


def test_room_binding_metadata_and_derived_ids_survive_save_load_roundtrip():
    doc, _ = _closed_house()
    face = doc.active_room_faces()[0]
    room_id = room_id_for_signature(doc, face.signature)
    doc.set_room_metadata(face.signature, name='Kitchen', use='cooking')
    infer_architecture(doc)
    derived = {e.id for e in doc.entities.values() if e.kind.startswith('room_')}

    loaded = Document.from_dict(doc.to_dict())
    loaded_face = loaded.active_room_faces()[0]
    assert room_id_for_signature(loaded, loaded_face.signature) == room_id
    assert loaded.room_metadata(loaded_face.signature) == {'name': 'Kitchen', 'use': 'cooking'}
    assert {e.id for e in loaded.entities.values() if e.kind.startswith('room_')} == derived
    assert all(e.params.get('room_id') == room_id for e in loaded.entities.values() if e.kind.startswith('room_'))


def test_legacy_signature_keyed_room_metadata_migrates_on_reconciliation():
    doc, _ = _closed_house()
    signature = room_faces(doc)[0].signature
    doc.room_data[signature] = {'name': 'Legacy Room'}
    assert not doc.room_bindings

    doc.active_room_faces()
    room_id = room_id_for_signature(doc, signature)
    assert room_id is not None
    assert signature not in doc.room_data
    assert doc.room_data[room_id] == {'name': 'Legacy Room'}
    assert doc.room_metadata(signature) == {'name': 'Legacy Room'}


def _wall_sculpt_profile(doc, wall_id):
    body = SculptedPreviewBackend().evaluate(doc).body(wall_id)
    ys = [v[1] for v in body.payload.vertices]
    return min(ys), max(ys)


def test_sculpt_attachment_moves_with_host_wall():
    """A semantic sculpt feature must remain attached when its host wall is translated."""
    doc = Document()
    wall = Entity(
        'wall',
        {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0, 'height': 2.8, 'thickness': 0.2},
    )
    doc.add(wall)
    hit = SurfaceHit(wall.id, 'exterior', (2.5, 0.1, 1.4), (0, 1, 0))
    modifier = sculpt_modifier_from_hit(doc, hit, BrushSpec(1.25), 'pull', 0.25)
    doc.add_surface_modifier(modifier)

    before = _wall_sculpt_profile(doc, wall.id)
    MoveEntities([wall.id], dx=10.0, dy=3.0, dz=0.0).do(doc)
    after = _wall_sculpt_profile(doc, wall.id)

    assert abs((after[0] - before[0]) - 3.0) < 1e-9
    assert abs((after[1] - before[1]) - 3.0) < 1e-9


def test_sculpt_attachment_follows_kinematic_part_transform():
    doc = Document()
    root = Entity('mechanical_part', {'x': 0, 'y': 0, 'z': 0, 'width': .2, 'depth': .2, 'height': .2, 'rotation': 0})
    child = Entity('mechanical_part', {'x': 1, 'y': 0, 'z': 0, 'width': .4, 'depth': .2, 'height': .2, 'rotation': 0})
    doc.add(root);doc.add(child)
    joint = Entity('mechanical_joint', {
        'joint_type': 'prismatic', 'parent_part': root.id, 'child_part': child.id,
        'anchor': [0, 0, 0], 'axis': [0, 1, 0], 'min_value': 0, 'max_value': 1, 'value': 0,
    })
    doc.add(joint)
    hit = SurfaceHit(child.id, 'top', (1.2, .1, .2), (0, 0, 1))
    mod = sculpt_modifier_from_hit(doc, hit, BrushSpec(.3), 'pull', .1)
    doc.add_surface_modifier(mod)

    rest = SculptedPreviewBackend().evaluate(doc, {joint.id: 0}).body(child.id)
    moved = SculptedPreviewBackend().evaluate(doc, {joint.id: .5}).body(child.id)
    rest_y = (min(v[1] for v in rest.payload.vertices), max(v[1] for v in rest.payload.vertices))
    moved_y = (min(v[1] for v in moved.payload.vertices), max(v[1] for v in moved.payload.vertices))
    assert abs((moved_y[0] - rest_y[0]) - .5) < 1e-9
    assert abs((moved_y[1] - rest_y[1]) - .5) < 1e-9
    assert max(v[2] for v in moved.payload.vertices) == max(v[2] for v in rest.payload.vertices)
    assert moved.modifiers_applied is True
