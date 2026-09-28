import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.core.roof_edge_transaction import RoofEdgeOffsetTransaction


def _document():
    doc = Document()
    wall = Entity(
        "wall",
        {"x1": 1.0, "y1": 2.0, "x2": 4.0, "y2": 5.0, "z": 0.0,
         "height": 3.0, "thickness": 0.2},
        id="rotated-wall",
    )
    roof = Entity(
        "room_roof",
        {"roof_type": "flat", "room_signature": "room-a", "thickness": 0.2},
        id="roof-a",
    )
    doc.add(wall)
    doc.add(roof)
    return doc, roof


def test_roof_edge_drag_preview_is_transient_and_commits_shared_semantic_command():
    doc, roof = _document()
    stack = CommandStack(doc)
    tx = RoofEdgeOffsetTransaction(doc, stack, roof.id, "rotated-wall")

    assert tx.update_local_displacement(0.35) == pytest.approx(0.35)
    assert "edge_offsets" not in roof.params

    assert tx.commit() is True
    assert roof.params["edge_offsets"] == {"rotated-wall": pytest.approx(0.35)}

    stack.undo()
    assert "edge_offsets" not in roof.params
    stack.redo()
    assert roof.params["edge_offsets"]["rotated-wall"] == pytest.approx(0.35)


def test_roof_edge_drag_cancel_and_noop_do_not_mutate_document():
    doc, roof = _document()
    stack = CommandStack(doc)
    tx = RoofEdgeOffsetTransaction(doc, stack, roof.id, "rotated-wall")

    tx.update_local_displacement(-0.12)
    tx.cancel()
    assert tx.preview_offset == pytest.approx(0.0)
    assert "edge_offsets" not in roof.params
    assert tx.commit() is False
    assert "edge_offsets" not in roof.params


def test_roof_edge_drag_starts_from_existing_semantic_offset_not_global_axis_state():
    doc, roof = _document()
    roof.params["edge_offsets"] = {"rotated-wall": 0.20}
    stack = CommandStack(doc)
    tx = RoofEdgeOffsetTransaction(doc, stack, roof.id, "rotated-wall")

    assert tx.update_local_displacement(0.15) == pytest.approx(0.35)
    assert roof.params["edge_offsets"]["rotated-wall"] == pytest.approx(0.20)
    assert tx.commit() is True
    assert roof.params["edge_offsets"]["rotated-wall"] == pytest.approx(0.35)
