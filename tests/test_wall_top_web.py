import json

import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.ui.wall_top_web import WallTopWebInteraction


def _adapter():
    doc = Document()
    wall = Entity("wall", {
        "x1": 1.0, "y1": 2.0, "x2": 5.0, "y2": 5.0,
        "z": 0.0, "height": 3.0, "thickness": 0.2,
    })
    doc.add(wall)
    doc.selection = [wall.id]
    stack = CommandStack(doc)
    return doc, wall, stack, WallTopWebInteraction(doc, stack)


def test_web_adapter_exposes_selected_semantic_handles_without_model_state():
    doc, wall, _, adapter = _adapter()

    handles = adapter.handles()

    assert handles == json.loads(adapter.handles_json())
    assert [(h["entity_id"], h["endpoint"]) for h in handles] == [
        (wall.id, "start"), (wall.id, "end")
    ]
    assert adapter.active is False
    assert "start_height" not in wall.params
    assert "end_height" not in wall.params


def test_web_adapter_ray_preview_is_transient_then_commits_through_command_stack():
    _, wall, stack, adapter = _adapter()
    adapter.begin_json(json.dumps({"entity_id": wall.id, "endpoint": "start"}))
    assert adapter.active is True

    height = adapter.update_ray_json(json.dumps({
        "origin": [1.0, -8.0, 6.0],
        "direction": [0.0, 1.0, -0.2],
    }))

    assert "start_height" not in wall.params
    preview = next(h for h in adapter.handles() if h["endpoint"] == "start")
    assert preview["preview"] is True
    assert preview["position"][0:2] == [1.0, 2.0]
    assert preview["position"][2] == pytest.approx(height)

    assert adapter.finish() is True
    assert adapter.active is False
    assert wall.params["start_height"] == pytest.approx(height)
    stack.undo()
    assert "start_height" not in wall.params


def test_web_adapter_cancel_and_malformed_ray_do_not_mutate_document():
    _, wall, stack, adapter = _adapter()
    adapter.begin_json(json.dumps({"entity_id": wall.id, "endpoint": "end"}))

    with pytest.raises(ValueError, match="origin"):
        adapter.update_ray_json(json.dumps({"origin": [1.0, 2.0], "direction": [0, 1, 0]}))

    adapter.cancel()
    assert adapter.active is False
    assert "end_height" not in wall.params
    assert stack.can_undo is False
