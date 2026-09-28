import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.ui.wall_top_3d_controller import WallTop3DController


def _wall(doc):
    wall = Entity("wall", {
        "x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 5.0,
        "z": 0.0, "height": 3.0, "thickness": 0.2,
    })
    doc.add(wall)
    doc.selection = [wall.id]
    return wall


def test_controller_preview_is_transient_then_commits_through_stack():
    doc = Document()
    wall = _wall(doc)
    stack = CommandStack(doc)
    controller = WallTop3DController(doc, stack)

    controller.begin(wall.id, "start")
    height = controller.update_from_ray((1.0, -8.0, 6.0), (0.0, 1.0, -0.2))

    assert "start_height" not in wall.params
    handles = controller.handles()
    start = next(h for h in handles if h["endpoint"] == "start")
    assert start["preview"] is True
    assert start["position"][:2] == [1.0, 2.0]
    assert start["position"][2] == pytest.approx(height)

    assert controller.finish() is True
    assert wall.params["start_height"] == pytest.approx(height)
    stack.undo()
    assert "start_height" not in wall.params


def test_controller_active_preview_stays_bound_to_captured_wall_if_selection_changes():
    doc = Document()
    dragged = _wall(doc)
    other = Entity("wall", {
        "x1": 20.0, "y1": 10.0, "x2": 24.0, "y2": 10.0,
        "z": 0.0, "height": 2.5, "thickness": 0.2,
    })
    doc.add(other)
    stack = CommandStack(doc)
    controller = WallTop3DController(doc, stack)

    controller.begin(dragged.id, "start")
    height = controller.update_from_ray((1.0, -8.0, 6.0), (0.0, 1.0, -0.2))
    doc.selection = [other.id]

    handles = controller.handles()
    assert {handle["entity_id"] for handle in handles} == {dragged.id}
    start = next(handle for handle in handles if handle["endpoint"] == "start")
    assert start["preview"] is True
    assert start["position"][:2] == [1.0, 2.0]
    assert start["position"][2] == pytest.approx(height)
    assert "start_height" not in dragged.params
    assert "start_height" not in other.params

    controller.cancel()
    assert stack.can_undo is False


def test_controller_cancel_and_noop_finish_are_history_neutral():
    doc = Document()
    wall = _wall(doc)
    stack = CommandStack(doc)
    controller = WallTop3DController(doc, stack)

    controller.begin(wall.id, "end")
    controller.cancel()
    assert "end_height" not in wall.params
    assert stack.can_undo is False

    controller.begin(wall.id, "end")
    assert controller.finish() is False
    assert "end_height" not in wall.params
    assert stack.can_undo is False


def test_controller_rejects_handle_not_owned_by_current_selection():
    doc = Document()
    wall = _wall(doc)
    stack = CommandStack(doc)
    controller = WallTop3DController(doc, stack)
    doc.selection = []

    with pytest.raises(ValueError, match="current selection"):
        controller.begin(wall.id, "start")
