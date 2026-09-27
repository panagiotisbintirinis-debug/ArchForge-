import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.core.interaction import StructuralBeamEndpointStretchTransaction
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import selection_handles
from archforge.core.viewport import PointerController, PointerEvent
from archforge.ui.object_context_menu import object_context_actions
from archforge.ui.pbr_viewport import PBRViewport
from archforge.ui.plan_view import PlanView


def _app():
    return QApplication.instance() or QApplication([])


def _wall():
    return Entity(
        "wall",
        {
            "x1": 0.0,
            "y1": 0.0,
            "x2": 4.0,
            "y2": 0.0,
            "z": 0.0,
            "height": 3.0,
            "thickness": 0.20,
        },
        name="Wall",
    )


def _column():
    return Entity(
        "structural_column",
        {
            "x": 1.0,
            "y": 1.0,
            "z": 0.0,
            "width": 0.30,
            "depth": 0.30,
            "height": 3.0,
            "rotation": 0.0,
            "role": "structural",
            "construction": "reinforced_concrete",
            "base_level": "Ground",
        },
        name="Column",
    )


def test_pbr_frame_free_arch_opening_uses_authoritative_opening_transaction():
    _app()
    doc = Document()
    wall = _wall()
    doc.add(wall)
    stack = CommandStack(doc)
    view = PBRViewport(doc, stack)

    view._place_opening_from_web(
        "opening_arch",
        json.dumps(
            {
                "entity_id": wall.id,
                "point": [2.0, 0.0, 1.20],
            }
        ),
    )

    openings = [entity for entity in doc.entities.values() if entity.kind == "opening"]
    assert len(openings) == 1
    opening = openings[0]
    assert opening.parent_id == wall.id
    assert opening.params["shape"] == "arch"
    assert opening.params["arch_rise"] > 0.0
    assert doc.selection == [opening.id]

    stack.undo()
    assert opening.id not in doc.entities


def test_structural_plan_retains_noninteractive_architectural_wall_context():
    _app()

    doc = Document()
    wall = _wall()
    column = _column()
    doc.add(wall)
    doc.add(column)
    view = PlanView(doc, CommandStack(doc), structural_only=True)
    view.redraw()

    interactive_ids = set(view._entity_items.values())
    assert column.id in interactive_ids
    assert wall.id not in interactive_ids

    reference_doc = Document()
    reference_column = _column()
    reference_doc.add(reference_column)
    reference_view = PlanView(
        reference_doc,
        CommandStack(reference_doc),
        structural_only=True,
    )
    reference_view.redraw()

    # The wall is still rendered as orientation context even though it is not
    # selectable/editable in Structural mode.
    assert len(view._scene.items()) > len(reference_view._scene.items())


def _beam():
    return Entity(
        "structural_beam",
        {
            "x1": 0.0,
            "y1": 0.0,
            "x2": 2.0,
            "y2": 0.0,
            "z": 2.70,
            "width": 0.20,
            "height": 0.30,
            "role": "structural",
            "construction": "reinforced_concrete",
            "section": "rectangular",
            "level": "Ground",
        },
        name="Beam",
    )


def test_structural_beam_endpoint_stretches_to_column_and_undoes():
    doc = Document()
    column = _column()
    column.params["x"] = 4.0
    column.params["y"] = 1.0
    beam = _beam()
    doc.add(column)
    doc.add(beam)
    stack = CommandStack(doc)

    tx = StructuralBeamEndpointStretchTransaction(
        doc, stack, beam.id, 2, grid=0.10, snap_tol=0.20
    )
    tx.update(4.02, 1.01)
    assert tx.last_snap is not None
    assert tx.preview["x2"] == 4.0
    assert tx.preview["y2"] == 1.0
    tx.commit()

    assert doc.get(beam.id).params["x2"] == 4.0
    assert doc.get(beam.id).params["y2"] == 1.0
    stack.undo()
    assert doc.get(beam.id).params["x2"] == 2.0
    assert doc.get(beam.id).params["y2"] == 0.0
    stack.redo()
    assert doc.get(beam.id).params["x2"] == 4.0
    assert doc.get(beam.id).params["y2"] == 1.0


def test_structural_selection_handles_support_direct_beam_editing():
    doc = Document()
    column = _column()
    beam = _beam()
    doc.add(column)
    doc.add(beam)

    doc.select([beam.id])
    beam_handles = selection_handles(doc)
    assert {(h.handle, h.cursor) for h in beam_handles} == {
        ("endpoint1", "stretch"),
        ("endpoint2", "stretch"),
        ("move", "move"),
    }

    doc.select([column.id])
    column_handles = selection_handles(doc)
    assert [(h.handle, h.cursor) for h in column_handles] == [("move", "move")]

    action_ids = [
        entry["id"]
        for entry in object_context_actions("structural_beam", "plan")
        if entry is not None
    ]
    assert "stretch" in action_ids


def test_beam_authored_from_ground_stays_owned_by_ground_storey():
    doc = Document()
    doc.levels["First"] = 3.0
    stack = CommandStack(doc)
    controller = PointerController(doc, stack)
    controller.set_tool("structural_beam")

    controller.pointer_down(PointerEvent(0.0, 0.0))
    controller.pointer_move(PointerEvent(3.0, 0.0))
    result = controller.pointer_up(PointerEvent(3.0, 0.0))

    beam = doc.get(result.entity_id)
    assert beam.kind == "structural_beam"
    assert beam.params["level"] == "Ground"
    assert abs(float(beam.params["z"]) - 2.70) < 1e-9
    assert abs(float(beam.params["z"]) + float(beam.params["height"]) - 3.0) < 1e-9

    doc.select([beam.id])
    assert selection_handles(doc)
