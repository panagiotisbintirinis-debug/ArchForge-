from types import SimpleNamespace

from archforge.geometry.mesh import MeshPayload
from archforge.rendering.scene import build_pbr_scene_payload


def test_pbr_scene_payload_uses_authoritative_mesh_and_identity():
    mesh = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 3.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    body = SimpleNamespace(entity_id="wall-1", semantic_kind="wall", payload=mesh)
    evaluation = SimpleNamespace(bodies=(body,))

    payload = build_pbr_scene_payload(evaluation, selected_ids={"wall-1"})

    assert payload["objects"] == [
        {
            "id": "wall-1",
            "kind": "wall",
            "vertices": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0], [0.0, 0.0, 3.0]],
            "triangles": [[0, 1, 2]],
            "surfaces": ["front"],
            "material": {"color": "#46a6ff", "roughness": 0.42, "metalness": 0.06},
        }
    ]


def test_pbr_scene_payload_ignores_non_mesh_bodies():
    body = SimpleNamespace(entity_id="x", semantic_kind="unsupported", payload={"preview": True})
    evaluation = SimpleNamespace(bodies=(body,))

    assert build_pbr_scene_payload(evaluation) == {"objects": []}


def test_pbr_scene_payload_accepts_transient_mesh_override():
    base = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    preview = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.5)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    body = SimpleNamespace(entity_id="wall-1", semantic_kind="wall", payload=base)
    evaluation = SimpleNamespace(bodies=(body,))

    payload = build_pbr_scene_payload(
        evaluation,
        mesh_overrides={"wall-1": preview},
    )

    assert payload["objects"][0]["vertices"][2] == [0.0, 0.0, 1.5]
