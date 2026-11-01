"""Human changes storey levels and interior height through one semantic undo step."""
from pathlib import Path

import pytest

from archforge.core.commands import CommandStack, CompositeCommand
from archforge.core.model import Document, Entity, WorkPlane
from archforge.core.storey_height import ChangeStoreyElevation, ChangeStoreyClearHeight


def house():
    doc = Document()
    doc.levels = {"Ground": 0.0, "Floor 1": 3.7, "Floor 2": 7.0}
    doc.work_plane = WorkPlane("Floor 1", (0, 0, 3.7))
    lower = Entity("wall", dict(x1=0, y1=0, x2=4, y2=0, z=0, height=3.5, thickness=.2))
    upper = Entity("wall", dict(x1=0, y1=0, x2=4, y2=0, z=3.7, height=2.7, thickness=.2))
    doc.add(lower); doc.add(upper)
    door = Entity("door", dict(offset=1, surface_u=.25, width=.9, height=2.1, sill=0), parent_id=upper.id)
    doc.add(door)
    slab = Entity("room_floor", dict(scope="storey", level_z=3.7, thickness=.18, offset_z=0))
    ceiling = Entity("room_ceiling", dict(scope="storey", level_z=3.7, thickness=.10, offset_z=2.7))
    doc.add(slab); doc.add(ceiling)
    stairs = Entity("stair", dict(x=0, y=0, lower_z=0, upper_z=3.7, upper_floor_z=3.7,
                                  upper_slab_thickness=0, layout="straight", angle_deg=0,
                                  width=1, riser_count=20, riser_height=.185, tread_depth=.28,
                                  landing_depth=1, turn_direction=1, opening_margin=.1))
    doc.add(stairs)
    furniture = Entity("box", dict(x=1, y=1, z=3.7, width=.8, depth=.6, height=.8, rotation=0))
    doc.add(furniture)
    doc.room_bindings["persist-room"] = {"signature": "prior-face", "polygon": [[0,0], [4,0], [4,4], [0,4]],
                                         "z": 3.7, "status": "enclosed"}
    doc.room_data["persist-room"] = {"name": "Δικό μου δωμάτιο"}
    return doc, (lower, upper, door, slab, ceiling, stairs, furniture)


def test_relevel_follows_semantic_members_and_preserves_identifiers_undo_save():
    doc, (lower, upper, door, slab, ceiling, stairs, furniture) = house()
    stack = CommandStack(doc)
    before = doc.to_dict()
    original_ids = set(doc.entities)
    stack.execute(ChangeStoreyElevation("Floor 1", 3.2))
    after = doc.to_dict()
    assert doc.levels["Floor 1"] == pytest.approx(3.2)
    assert doc.get(lower.id).params["z"] == 0
    assert doc.get(upper.id).params["z"] == pytest.approx(3.2)
    assert doc.get(slab.id).params["level_z"] == pytest.approx(3.2)
    assert doc.get(ceiling.id).params["level_z"] == pytest.approx(3.2)
    assert doc.get(stairs.id).params["upper_z"] == pytest.approx(3.2)
    assert doc.get(stairs.id).params["upper_floor_z"] == pytest.approx(3.2)
    assert doc.get(stairs.id).params["riser_height"] == pytest.approx(.16)
    assert doc.get(furniture.id).params["z"] == pytest.approx(3.2)
    assert doc.get(door.id).parent_id == upper.id
    assert set(doc.entities) == original_ids
    assert doc.room_data["persist-room"]["name"] == "Δικό μου δωμάτιο"
    assert doc.room_bindings["persist-room"]["z"] == pytest.approx(3.2)
    assert doc.work_plane.origin[2] == pytest.approx(3.2)
    assert Document.from_dict(after).to_dict() == after
    stack.undo()
    assert doc.to_dict() == before
    stack.redo()
    assert doc.to_dict() == after


def test_clear_height_changes_walls_and_ceiling_but_not_floor_elevation_or_stair():
    doc, (lower, upper, door, slab, ceiling, stairs, furniture) = house()
    stack = CommandStack(doc)
    before = doc.to_dict()
    stack.execute(ChangeStoreyClearHeight("Floor 1", 2.9))
    after = doc.to_dict()
    assert doc.levels == before["levels"]
    assert doc.get(upper.id).params["height"] == pytest.approx(2.9)
    assert doc.get(lower.id).params["height"] == pytest.approx(3.5)
    assert doc.get(ceiling.id).params["offset_z"] == pytest.approx(2.9)
    assert doc.get(slab.id).params["level_z"] == pytest.approx(3.7)
    assert doc.get(stairs.id).params["upper_z"] == pytest.approx(3.7)
    assert doc.get(door.id).parent_id == upper.id
    stack.undo()
    assert doc.to_dict() == before
    stack.redo()
    assert doc.to_dict() == after


def test_mixed_wall_heights_refuse_uniform_clear_height_without_changing_model():
    doc, (_lower, upper, *_other) = house()
    doc.add(Entity("wall", dict(x1=5, y1=0, x2=8, y2=0, z=3.7, height=1.2, thickness=.2)))
    before = doc.to_dict()
    stack = CommandStack(doc)
    with pytest.raises(ValueError, match="ύψος τοίχου"):
        stack.execute(ChangeStoreyClearHeight("Floor 1", 2.9))
    assert doc.to_dict() == before and not stack.can_undo
    assert doc.get(upper.id).params["height"] == pytest.approx(2.7)


def test_relevel_rejects_crossing_another_storey_and_locked_members():
    doc, (_lower, upper, *_other) = house()
    stack = CommandStack(doc)
    before = doc.to_dict()
    with pytest.raises(ValueError, match="στάθμ"):
        stack.execute(ChangeStoreyElevation("Floor 1", 8.0))
    assert doc.to_dict() == before and not stack.can_undo
    upper.locked = True
    locked_before = doc.to_dict()
    with pytest.raises(PermissionError):
        stack.execute(ChangeStoreyElevation("Floor 1", 3.2))
    assert doc.to_dict() == locked_before and not stack.can_undo


def test_relevel_updates_structural_members_and_pitched_roof_without_relinking():
    doc, (_lower, upper, *_other) = house()
    column_below = Entity("structural_column", dict(x=0, y=0, z=0, width=.3, depth=.3,
                           height=3.7, rotation=0, role="structural", construction="reinforced_concrete",
                           base_level="Ground", top_level="Floor 1"))
    column_above = Entity("structural_column", dict(x=2, y=0, z=3.7, width=.3, depth=.3,
                           height=3.3, rotation=0, role="structural", construction="reinforced_concrete",
                           base_level="Floor 1", top_level="Floor 2"))
    beam = Entity("structural_beam", dict(x1=0, y1=0, x2=3, y2=0, z=3.7, width=.25,
                   height=.35, role="structural", construction="reinforced_concrete",
                   section="rectangular", level="Floor 1"))
    roof = Entity("pitched_roof", dict(x0=0, y0=0, x1=4, y1=4, eave_z=6.4,
                   pitch=30, overhang=.3, rafter_spacing=.6))
    for entity in (column_below, column_above, beam, roof):
        doc.add(entity)
    before = doc.to_dict()
    stack = CommandStack(doc)
    stack.execute(ChangeStoreyElevation("Floor 1", 3.2))
    assert doc.get(column_below.id).params["z"] == 0
    assert doc.get(column_below.id).params["height"] == pytest.approx(3.2)
    assert doc.get(column_above.id).params["z"] == pytest.approx(3.2)
    assert doc.get(column_above.id).params["height"] == pytest.approx(3.8)
    assert doc.get(beam.id).params["z"] == pytest.approx(3.2)
    assert doc.get(roof.id).params["eave_z"] == pytest.approx(5.9)
    assert doc.get(upper.id).params["z"] == pytest.approx(3.2)
    assert {e.id for e in doc.entities.values()} == {e["id"] for e in before["entities"]}
    after = doc.to_dict()
    stack.undo()
    assert doc.to_dict() == before
    stack.redo()
    assert doc.to_dict() == after


def test_clear_height_keeps_pitched_roof_attached_to_previous_wall_top():
    doc, (_lower, upper, *_other) = house()
    roof = Entity("pitched_roof", dict(x0=0, y0=0, x1=4, y1=4, eave_z=6.4,
                  pitch=30, overhang=.3, rafter_spacing=.6))
    doc.add(roof)
    stack = CommandStack(doc)
    before = doc.to_dict()
    stack.execute(ChangeStoreyClearHeight("Floor 1", 2.9))
    assert doc.get(roof.id).params["eave_z"] == pytest.approx(6.6)
    assert doc.get(upper.id).params["height"] == pytest.approx(2.9)
    assert doc.levels == before["levels"]
    stack.undo()
    assert doc.to_dict() == before


def test_relevel_ramp_recalculates_slope_and_keeps_fixed_run():
    doc, _ = house()
    ramp = Entity("ramp", dict(x=0, y=2, lower_z=0, upper_z=3.7, upper_floor_z=3.7,
                  upper_slab_thickness=0, angle_deg=0, width=1.5, slope_pct=18.5,
                  run_length=20, thickness=.2, opening_margin=.1))
    doc.add(ramp)
    CommandStack(doc).execute(ChangeStoreyElevation("Floor 1", 3.2))
    assert doc.get(ramp.id).params["upper_z"] == pytest.approx(3.2)
    assert doc.get(ramp.id).params["run_length"] == pytest.approx(20)
    assert doc.get(ramp.id).params["slope_pct"] == pytest.approx(16)


def test_relevel_resolves_unnamed_active_work_plane_before_level_moves():
    doc, _ = house()
    doc.work_plane = WorkPlane("XY", (0, 0, 3.7))
    CommandStack(doc).execute(ChangeStoreyElevation("Floor 1", 3.2))
    assert doc.work_plane.name == "Floor 1"
    assert doc.work_plane.origin[2] == pytest.approx(3.2)


def test_both_heights_form_one_atomic_undo_even_when_second_change_fails():
    doc, _ = house()
    before = doc.to_dict()
    stack = CommandStack(doc)
    with pytest.raises(ValueError, match="επόμενη στάθμη"):
        stack.execute(CompositeCommand([
            ChangeStoreyElevation("Floor 1", 6.0),
            ChangeStoreyClearHeight("Floor 1", 2.9),
        ], label="Ύψη ορόφου"))
    assert doc.to_dict() == before
    assert not stack.can_undo


def test_independent_suspended_ceiling_does_not_shorten_taller_walls():
    doc, (_lower, upper, *_other) = house()
    doc.update(upper.id, {"height": 3.1})
    before = doc.to_dict()
    stack = CommandStack(doc)
    stack.execute(ChangeStoreyClearHeight("Floor 1", 2.8))
    assert doc.get(upper.id).params["height"] == pytest.approx(3.1)
    assert doc.levels == before["levels"]
    stack.undo()
    assert doc.to_dict() == before


def test_existing_two_storey_s06_full_project_retains_every_entity_and_relation():
    """Exercise a real shipped two-storey model, not only tiny test geometry."""
    from archforge.project.persistence import load_project

    sample = Path(__file__).resolve().parent.parent / "docs/scenarios/S06_diorofo.archforge"
    doc = load_project(sample).doc
    before = doc.to_dict()
    ids = set(doc.entities)
    parent_links = {e.id: e.parent_id for e in doc.entities.values() if e.parent_id}
    stack = CommandStack(doc)
    stack.execute(ChangeStoreyElevation("Floor 1", 3.2))
    stack.execute(ChangeStoreyClearHeight("Floor 1", 2.9))
    assert doc.levels["Floor 1"] == 3.2
    assert set(doc.entities) == ids
    assert {e.id: e.parent_id for e in doc.entities.values() if e.parent_id} == parent_links
    assert len(doc.entities) > 200
    after = doc.to_dict()
    assert Document.from_dict(after).to_dict() == after
    stack.undo()
    stack.undo()
    assert doc.to_dict() == before
    stack.redo()
    stack.redo()
    assert doc.to_dict() == after
