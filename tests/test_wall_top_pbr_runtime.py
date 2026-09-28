import json

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.ui.wall_top_pbr_runtime import PBRWallTopRuntime


def _wall_doc():
    doc = Document()
    wall = Entity(
        kind="wall",
        params={
            "x1": 1.0,
            "y1": 2.0,
            "z": 0.0,
            "x2": 5.0,
            "y2": 4.0,
            "height": 3.0,
            "thickness": 0.2,
        },
        id="wall-1",
    )
    doc.add(wall)
    doc.select([wall.id])
    return doc, wall


def test_runtime_derives_two_pickable_handles_without_mutating_document():
    doc, wall = _wall_doc()
    stack = CommandStack(doc)
    before = dict(wall.params)

    runtime = PBRWallTopRuntime(doc, stack)
    payload = runtime.scene_payload()

    handles = payload["wall_top_handles"]
    assert [item["handle_id"] for item in handles] == [
        "wall-top:wall-1:start",
        "wall-top:wall-1:end",
    ]
    assert all(item["pickable"] for item in handles)
    assert handles[0]["center"] == [1.0, 2.0, 3.0]
    assert handles[1]["center"] == [5.0, 4.0, 3.0]
    assert wall.params == before
    assert not runtime.active


def test_runtime_serializes_handles_as_separate_view_payload():
    doc, wall = _wall_doc()
    stack = CommandStack(doc)
    before = dict(wall.params)

    runtime = PBRWallTopRuntime(doc, stack)
    payload = json.loads(runtime.scene_payload_json())

    assert set(payload) == {"wall_top_handles"}
    assert [item["handle_id"] for item in payload["wall_top_handles"]] == [
        "wall-top:wall-1:start",
        "wall-top:wall-1:end",
    ]
    assert all("entity_id" not in item for item in payload["wall_top_handles"])
    assert wall.params == before
    assert stack.undo_stack == []


def test_runtime_drag_preview_is_transient_and_finish_uses_commandstack():
    doc, wall = _wall_doc()
    stack = CommandStack(doc)
    runtime = PBRWallTopRuntime(doc, stack)

    runtime.begin("wall-top:wall-1:start")
    assert runtime.active

    # Endpoint XY is (1,2). This ray reaches that vertical edit line at z=4.
    height = runtime.update_ray((1.0, 0.0, 2.0), (0.0, 1.0, 1.0))
    assert height == 4.0
    assert "start_height" not in wall.params

    preview = runtime.scene_payload()["wall_top_handles"]
    assert preview[0]["preview"] is True
    assert preview[0]["center"] == [1.0, 2.0, 4.0]

    assert runtime.finish() is True
    assert wall.params["start_height"] == 4.0
    assert not runtime.active

    stack.undo()
    assert "start_height" not in wall.params
    stack.redo()
    assert wall.params["start_height"] == 4.0


def test_runtime_rebind_cancels_transient_drag_without_touching_old_document():
    doc, wall = _wall_doc()
    stack = CommandStack(doc)
    runtime = PBRWallTopRuntime(doc, stack)
    runtime.begin("wall-top:wall-1:end")

    other_doc, _other_wall = _wall_doc()
    other_stack = CommandStack(other_doc)
    runtime.rebind(other_doc, other_stack)

    assert not runtime.active
    assert "end_height" not in wall.params
