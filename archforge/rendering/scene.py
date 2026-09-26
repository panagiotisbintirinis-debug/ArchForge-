from __future__ import annotations

from typing import Iterable, Mapping

from archforge.geometry.mesh import MeshPayload


_MATERIALS: Mapping[str, dict] = {
    "wall": {"color": "#d8d2c7", "roughness": 0.72, "metalness": 0.02},
    "floor": {"color": "#aeb6bd", "roughness": 0.82, "metalness": 0.01},
    "room_floor": {"color": "#b9b4aa", "roughness": 0.82, "metalness": 0.01},
    "room_ceiling": {"color": "#dedbd2", "roughness": 0.78, "metalness": 0.01},
    "room_foundation": {"color": "#9ea4aa", "roughness": 0.9, "metalness": 0.0},
    "room_roof": {"color": "#8f979f", "roughness": 0.68, "metalness": 0.02},
    "pod": {"color": "#c7cbd0", "roughness": 0.55, "metalness": 0.02},
    "box": {"color": "#bfc7cf", "roughness": 0.58, "metalness": 0.03},
    "mechanical_part": {"color": "#9da7b1", "roughness": 0.38, "metalness": 0.42},
    "arboreal_branch": {"color": "#856a4f", "roughness": 0.88, "metalness": 0.0},
    "stair": {"color": "#c7b99f", "roughness": 0.72, "metalness": 0.01},
}
_DEFAULT_MATERIAL = {"color": "#bdc5ce", "roughness": 0.64, "metalness": 0.02}
_SELECTED_MATERIAL = {"color": "#46a6ff", "roughness": 0.42, "metalness": 0.06}


def _material(kind: str, selected: bool) -> dict:
    return dict(_SELECTED_MATERIAL if selected else _MATERIALS.get(kind, _DEFAULT_MATERIAL))


def build_pbr_scene_payload(evaluation, selected_ids: Iterable[str] = (), mesh_overrides=None) -> dict:
    """Serialize evaluated MeshPayloads for the derived WebGL renderer.

    The returned structure contains no authoritative state and is safe to discard at any
    time. Entity identity is retained only so display selection can be represented.
    """
    selected = set(selected_ids)
    overrides = dict(mesh_overrides or {})
    objects = []
    for body in evaluation.bodies:
        mesh = overrides.get(body.entity_id, body.payload)
        if not isinstance(mesh, MeshPayload):
            continue
        objects.append(
            {
                "id": str(body.entity_id),
                "kind": str(body.semantic_kind),
                "vertices": [[float(x), float(y), float(z)] for x, y, z in mesh.vertices],
                "triangles": [[int(a), int(b), int(c)] for a, b, c in mesh.triangles],
                "surfaces": [str(role) for role in mesh.triangle_surfaces],
                "material": _material(body.semantic_kind, body.entity_id in selected),
            }
        )
    return {"objects": objects}
