from archforge.architecture.intent import infer_architecture
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
    """Replacing one wall with identical geometry must not create a new semantic room."""
    doc, walls = _closed_house()
    before = room_faces(doc)
    assert len(before) == 1
    old_signature = before[0].signature
    doc.set_room_metadata(old_signature, name='Living Room', use='living')
    infer_architecture(doc)
    old_derived_ids = {
        e.id for e in doc.entities.values() if e.kind.startswith('room_')
    }

    old = doc.get(walls[0]).clone()
    doc.remove(old.id)
    replacement = Entity('wall', dict(old.params))
    doc.add(replacement)

    after = room_faces(doc)
    assert len(after) == 1
    new_signature = after[0].signature

    # Foundation contract: semantic room identity and its user metadata survive
    # replacing a boundary object that describes the same physical boundary.
    assert new_signature == old_signature
    assert doc.room_metadata(new_signature) == {'name': 'Living Room', 'use': 'living'}

    infer_architecture(doc)
    new_derived_ids = {
        e.id for e in doc.entities.values() if e.kind.startswith('room_')
    }
    assert new_derived_ids == old_derived_ids


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

    # Translation must preserve the deformation profile in host-local space.
    assert abs((after[0] - before[0]) - 3.0) < 1e-9
    assert abs((after[1] - before[1]) - 3.0) < 1e-9
