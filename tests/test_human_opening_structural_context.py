import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
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
