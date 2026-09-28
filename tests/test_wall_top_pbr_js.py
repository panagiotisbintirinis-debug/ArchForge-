import json

import pytest

from archforge.ui.wall_top_pbr_js import (
    wall_top_handle_root_js,
    wall_top_handle_scene_script,
)


def test_handle_scene_script_uses_separate_renderer_entrypoint():
    payload = {
        "wall_top_handles": [
            {
                "handle_id": "wall-top:w1:start",
                "position": [1.0, 2.0, 3.0],
                "radius": 0.11,
                "preview": False,
            }
        ]
    }
    script = wall_top_handle_scene_script(payload)

    assert "archforgeSetWallTopHandles" in script
    assert "archforgeSetScene(" not in script
    assert "wall-top:w1:start" in script
    assert "entity_id" not in script


def test_handle_scene_script_rejects_non_list_handle_payload():
    with pytest.raises(ValueError, match="must be a list"):
        wall_top_handle_scene_script({"wall_top_handles": {"bad": True}})


def test_handle_root_is_separate_from_authoritative_model_root():
    js = wall_top_handle_root_js()

    assert 'new THREE.Group()' in js
    assert 'wallTopHandleRoot.name = "wall-top-handles"' in js
    assert "scene.add(wallTopHandleRoot)" in js
    assert "wallTopHandleRoot.add(mesh)" in js
    assert "modelRoot.add(mesh)" not in js
    assert "intersectObjects(wallTopHandleRoot.children, false)" in js
    assert "userData.handleId" in js
    assert "pointerRay(event)" in js
    assert "origin:" in js
    assert "direction:" in js


def test_handle_root_does_not_embed_authoritative_mutation_semantics():
    js = wall_top_handle_root_js()

    forbidden = (
        "CommandStack",
        "SetWallTopEndpoint",
        "doc.update",
        "entity_id",
        "start_height",
        "end_height",
    )
    assert all(token not in js for token in forbidden)
