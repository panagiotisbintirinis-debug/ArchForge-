from __future__ import annotations

from typing import Iterable, Mapping

from archforge.geometry.mesh import MeshPayload
from archforge.rendering.materials import material_spec


_MATERIALS: Mapping[str, dict] = {
    "wall": {"color": "#d8d2c7", "roughness": 0.72, "metalness": 0.02},
    "floor": {"color": "#aeb6bd", "roughness": 0.82, "metalness": 0.01},
    "room_floor": {"color": "#b9b4aa", "roughness": 0.82, "metalness": 0.01},
    "terrain": {"color": "#7d9a5a", "roughness": 0.95, "metalness": 0.0},
    "room_ceiling": {"color": "#dedbd2", "roughness": 0.78, "metalness": 0.01},
    "room_foundation": {"color": "#9ea4aa", "roughness": 0.9, "metalness": 0.0},
    "room_roof": {"color": "#8f979f", "roughness": 0.68, "metalness": 0.02},
    "pod": {"color": "#c7cbd0", "roughness": 0.55, "metalness": 0.02},
    "box": {"color": "#bfc7cf", "roughness": 0.58, "metalness": 0.03},
    "structural_column": {"color": "#b9b2a6", "roughness": 0.72, "metalness": 0.02},
    "structural_beam": {"color": "#aeb5bb", "roughness": 0.62, "metalness": 0.05},
    "mechanical_part": {"color": "#9da7b1", "roughness": 0.38, "metalness": 0.42},
    "arboreal_branch": {"color": "#856a4f", "roughness": 0.88, "metalness": 0.0},
    "stair": {"color": "#c7b99f", "roughness": 0.72, "metalness": 0.01},
    "ramp": {"color": "#b8c2c9", "roughness": 0.74, "metalness": 0.01},
}
_DEFAULT_MATERIAL = {"color": "#bdc5ce", "roughness": 0.64, "metalness": 0.02}

_STRUCTURAL_CONSTRUCTION_MATERIAL = {
    "reinforced_concrete": "concrete_smooth",
    "steel": "steel_brushed",
    "timber": "wood_oak",
    "aluminium": "aluminium",
}


def _surface_material_id(entity, surface_role: str | None = None):
    if entity is None:
        return None
    if surface_role:
        overrides = entity.params.get("surface_materials") or {}
        if isinstance(overrides, dict) and surface_role in overrides:
            return overrides.get(surface_role)
    return entity.params.get("material_id")


def _material(kind: str, selected: bool, entity=None, doc=None, surface_role: str | None = None) -> dict:
    spec = dict(_MATERIALS.get(kind, _DEFAULT_MATERIAL))
    material_id = _surface_material_id(entity, surface_role)

    # Construction is semantic intent; it only supplies the default look.
    # An explicit finish/material always wins.
    if (
        not material_id
        and entity is not None
        and kind in ("structural_column", "structural_beam")
    ):
        material_id = _STRUCTURAL_CONSTRUCTION_MATERIAL.get(
            str(entity.params.get("construction", "generic"))
        )

    custom = material_spec(material_id)
    if custom is not None:
        spec.update({
            "color": custom.get("color", spec.get("color")),
            "roughness": custom.get("roughness", spec.get("roughness", 0.65)),
            "metalness": custom.get("metalness", spec.get("metalness", 0.02)),
            "material_id": str(material_id),
            "material_name": str(custom.get("name", material_id)),
        })
    if selected:
        # Keep the real surface visible while selected; use a subtle emissive
        # accent instead of replacing the material with selection blue.
        spec["emissive"] = "#1f5f93"
        spec["emissiveIntensity"] = 0.28
    return spec


def build_pbr_scene_payload(evaluation, selected_ids: Iterable[str] = (), mesh_overrides=None, doc=None) -> dict:
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
        entity = doc.entities.get(body.entity_id) if doc is not None else None
        vertices = [[float(x), float(y), float(z)] for x, y, z in mesh.vertices]

        # Walls can carry independent finish materials on semantic faces. Group
        # triangles by resolved material so one authoritative wall may render as
        # multiple derived WebGL meshes while retaining one entity identity.
        if body.semantic_kind == "wall" and entity is not None:
            groups = {}
            for tri, role in zip(mesh.triangles, mesh.triangle_surfaces):
                role = str(role)
                material_id = _surface_material_id(entity, role)
                key = str(material_id) if material_id else "__default__"
                group = groups.setdefault(key, {"triangles": [], "surfaces": [], "role": role})
                group["triangles"].append([int(tri[0]), int(tri[1]), int(tri[2])])
                group["surfaces"].append(role)
            for key, group in groups.items():
                representative_role = group["role"]
                objects.append(
                    {
                        "id": str(body.entity_id),
                        "render_part": f"{body.entity_id}:{key}",
                        "kind": str(body.semantic_kind),
                        "vertices": vertices,
                        "triangles": group["triangles"],
                        "surfaces": group["surfaces"],
                        "material": _material(
                            body.semantic_kind,
                            body.entity_id in selected,
                            entity=entity,
                            doc=doc,
                            surface_role=representative_role,
                        ),
                    }
                )
            continue

        objects.append(
            {
                "id": str(body.entity_id),
                "kind": str(body.semantic_kind),
                "vertices": vertices,
                "triangles": [[int(a), int(b), int(c)] for a, b, c in mesh.triangles],
                "surfaces": [str(role) for role in mesh.triangle_surfaces],
                "material": _material(
                    body.semantic_kind,
                    body.entity_id in selected,
                    entity=entity,
                    doc=doc,
                ),
            }
        )
    return {"objects": objects}
