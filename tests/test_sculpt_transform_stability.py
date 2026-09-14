from archforge.core.model import Document, Entity
from archforge.core.commands import MoveEntities, CommandStack
from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from archforge.geometry.selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
from archforge.geometry.sculpt import SculptedPreviewBackend


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


def test_sculpt_attachment_undo_redo():
    """Undoing an entity move must restore the sculpt modifier's position."""
    doc = Document()
    stack = CommandStack(doc)
    wall = Entity(
        'wall',
        {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0, 'height': 2.8, 'thickness': 0.2},
    )
    doc.add(wall)
    hit = SurfaceHit(wall.id, 'exterior', (2.5, 0.1, 1.4), (0, 1, 0))
    modifier = sculpt_modifier_from_hit(doc, hit, BrushSpec(1.25), 'pull', 0.25)
    doc.add_surface_modifier(modifier)

    before = _wall_sculpt_profile(doc, wall.id)
    cmd = MoveEntities([wall.id], dx=5.0, dy=4.0, dz=1.0)
    stack.execute(cmd)
    moved = _wall_sculpt_profile(doc, wall.id)
    assert abs((moved[0] - before[0]) - 4.0) < 1e-9
    assert abs((moved[1] - before[1]) - 4.0) < 1e-9

    stack.undo()
    undone = _wall_sculpt_profile(doc, wall.id)
    assert abs(undone[0] - before[0]) < 1e-9
    assert abs(undone[1] - before[1]) < 1e-9

    stack.redo()
    redone = _wall_sculpt_profile(doc, wall.id)
    assert abs(redone[0] - moved[0]) < 1e-9
    assert abs(redone[1] - moved[1]) < 1e-9


def test_sculpt_moves_with_mechanical_part():
    """MoveEntities must support moving mechanical_part and evaluate attached sculpt modifiers correctly."""
    doc = Document()
    part = Entity('mechanical_part', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0.0})
    doc.add(part)
    hit = SurfaceHit(part.id, 'top', (0.5, 0.5, 1.0), (0, 0, 1))
    modifier = sculpt_modifier_from_hit(doc, hit, BrushSpec(0.8), 'pull', 0.2)
    doc.add_surface_modifier(modifier)

    body_before = SculptedPreviewBackend().evaluate(doc).body(part.id)
    zs_before = [v[2] for v in body_before.payload.vertices]
    max_z_before = max(zs_before)

    MoveEntities([part.id], dx=2.0, dy=2.0, dz=5.0).do(doc)

    body_after = SculptedPreviewBackend().evaluate(doc).body(part.id)
    zs_after = [v[2] for v in body_after.payload.vertices]
    max_z_after = max(zs_after)

    # Base part top moved from z=1.0 to z=6.0; sculpt deformation travels with the part.
    assert abs((max_z_after - max_z_before) - 5.0) < 1e-9


def test_sculpt_moves_with_box():
    """MoveEntities must translate sculpt modifiers attached to box entities."""
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 2.0, 'depth': 2.0, 'height': 2.0, 'rotation': 0.0})
    doc.add(box)
    hit = SurfaceHit(box.id, 'top', (1.0, 1.0, 2.0), (0, 0, 1))
    modifier = sculpt_modifier_from_hit(doc, hit, BrushSpec(2.0), 'pull', 0.3)
    doc.add_surface_modifier(modifier)

    body_before = SculptedPreviewBackend().evaluate(doc).body(box.id)
    zs_before = [v[2] for v in body_before.payload.vertices]

    MoveEntities([box.id], dx=3.0, dy=-1.0, dz=4.0).do(doc)

    body_after = SculptedPreviewBackend().evaluate(doc).body(box.id)
    zs_after = [v[2] for v in body_after.payload.vertices]
    assert abs((max(zs_after) - max(zs_before)) - 4.0) < 1e-9


def test_sculpt_moves_multiple_entities():
    """MoveEntities with multiple entities must translate and evaluate modifiers for each moved entity."""
    doc = Document()
    w1 = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0, 'height': 2.5, 'thickness': 0.2})
    w2 = Entity('wall', {'x1': 0, 'y1': 5, 'x2': 4, 'y2': 5, 'z': 0, 'height': 2.5, 'thickness': 0.2})
    doc.add(w1)
    doc.add(w2)

    m1 = sculpt_modifier_from_hit(doc, SurfaceHit(w1.id, 'exterior', (2.0, 0.1, 1.0), (0, 1, 0)), BrushSpec(1.0), 'pull', 0.2)
    m2 = sculpt_modifier_from_hit(doc, SurfaceHit(w2.id, 'exterior', (2.0, 5.1, 1.0), (0, 1, 0)), BrushSpec(1.0), 'pull', 0.2)
    doc.add_surface_modifier(m1)
    doc.add_surface_modifier(m2)

    b1_before = SculptedPreviewBackend().evaluate(doc).body(w1.id)
    b2_before = SculptedPreviewBackend().evaluate(doc).body(w2.id)

    MoveEntities([w1.id, w2.id], dx=1.0, dy=2.0, dz=0.5).do(doc)

    b1_after = SculptedPreviewBackend().evaluate(doc).body(w1.id)
    b2_after = SculptedPreviewBackend().evaluate(doc).body(w2.id)

    assert abs((max(v[1] for v in b1_after.payload.vertices) - max(v[1] for v in b1_before.payload.vertices)) - 2.0) < 1e-9
    assert abs((max(v[1] for v in b2_after.payload.vertices) - max(v[1] for v in b2_before.payload.vertices)) - 2.0) < 1e-9


def test_legacy_world_space_modifier_translation_and_undo():
    """Legacy pre-UV modifiers with world_center must be translated by MoveEntities and restored on undo."""
    doc = Document()
    stack = CommandStack(doc)
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0, 'height': 2.8, 'thickness': 0.2})
    doc.add(wall)

    # Create a legacy modifier without uv_center
    target = SurfaceRef(wall.id, 'exterior', {'world_center': [2.5, 0.1, 1.4], 'radius': 1.0})
    mod = SurfaceModifier(target, 'pull', {'amount': 0.2})
    doc.add_surface_modifier(mod)

    cmd = MoveEntities([wall.id], dx=2.0, dy=3.0, dz=1.0)
    stack.execute(cmd)
    assert doc.surface_modifiers[mod.id].target.subregion['world_center'] == [4.5, 3.1, 2.4]

    stack.undo()
    assert doc.surface_modifiers[mod.id].target.subregion['world_center'] == [2.5, 0.1, 1.4]

    stack.redo()
    assert doc.surface_modifiers[mod.id].target.subregion['world_center'] == [4.5, 3.1, 2.4]
