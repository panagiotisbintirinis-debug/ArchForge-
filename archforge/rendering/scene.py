from __future__ import annotations

from typing import Iterable, Mapping

from archforge.geometry.mesh import MeshPayload
from archforge.rendering.materials import material_spec


_MATERIALS: Mapping[str, dict] = {
    "wall": {"color": "#d8d2c7", "roughness": 0.72, "metalness": 0.02},
    "floor": {"color": "#aeb6bd", "roughness": 0.82, "metalness": 0.01},
    "room_floor": {"color": "#b9b4aa", "roughness": 0.82, "metalness": 0.01},
    "terrain": {"color": "#7d9a5a", "roughness": 0.95, "metalness": 0.0},
    "site_path": {"color": "#a9a39a", "roughness": 0.9, "metalness": 0.0},
    "window_frame": {"color": "#3d4247", "roughness": 0.38, "metalness": 0.55},
    "door_frame": {"color": "#5a4636", "roughness": 0.6, "metalness": 0.0},
    "door_leaf": {"color": "#7a5c43", "roughness": 0.55, "metalness": 0.0},
    "window_glass": {"color": "#a9c3d2", "roughness": 0.03, "metalness": 0.1, "opacity": 0.28},
    "plant_trunk": {"color": "#6b4a2f", "roughness": 0.9, "metalness": 0.0},
    "library_object": {"color": "#b9b2a6", "roughness": 0.6, "metalness": 0.0},
    "cabinet_carcass": {"color": "#e9e5dd", "roughness": 0.6, "metalness": 0.0},
    "cabinet_shelf": {"color": "#e9e5dd", "roughness": 0.6, "metalness": 0.0},
    "cabinet_front": {"color": "#f4f1ea", "roughness": 0.45, "metalness": 0.0},
    "cabinet_handle": {"color": "#a7a9ac", "roughness": 0.3, "metalness": 0.85},
    "cabinet_plinth": {"color": "#3b3b3b", "roughness": 0.7, "metalness": 0.0},
    "cabinet_worktop": {"color": "#77716a", "roughness": 0.35, "metalness": 0.0},
    "cabinet_rail": {"color": "#b5b7ba", "roughness": 0.25, "metalness": 0.9},
    "plant_canopy": {"color": "#4f7a3a", "roughness": 0.85, "metalness": 0.0},
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
        if body.semantic_kind == "plant":
            # Bark and foliage are two derived meshes of one plant entity.
            for role in ("trunk", "canopy"):
                picked = [(tri, r) for tri, r in zip(mesh.triangles, mesh.triangle_surfaces) if r == role]
                if not picked:
                    continue
                objects.append({
                    "id": str(body.entity_id),
                    "render_part": f"{body.entity_id}:{role}",
                    "kind": "plant",
                    "vertices": vertices,
                    "triangles": [[int(t[0]), int(t[1]), int(t[2])] for t, _ in picked],
                    "surfaces": [r for _, r in picked],
                    "material": _material(f"plant_{role}", body.entity_id in selected, entity=entity, doc=doc),
                })
            continue
        if body.semantic_kind == "cabinet" and entity is not None:
            # One derived mesh per cabinet role; palette finishes per role live in
            # surface_materials like wall faces (material_id = whole cabinet).
            groups = {}
            for tri, role in zip(mesh.triangles, mesh.triangle_surfaces):
                g = groups.setdefault(str(role), [])
                g.append([int(tri[0]), int(tri[1]), int(tri[2])])
            for role, tris in groups.items():
                objects.append({
                    "id": str(body.entity_id),
                    "render_part": f"{body.entity_id}:{role}",
                    "kind": "cabinet",
                    "vertices": vertices,
                    "triangles": tris,
                    "surfaces": [role] * len(tris),
                    "material": _material(f"cabinet_{role}", body.entity_id in selected, entity=entity, doc=doc,
                                          surface_role=role),
                })
            continue
        if body.semantic_kind == "library_object" and entity is not None:
            # One derived mesh per material part of the referenced asset. A part
            # keeps its catalogue colour until the user assigns a palette
            # material to it (surface_materials["part<i>"]) or to the whole
            # object (material_id), exactly like wall faces.
            from archforge.library.objects import asset_parts, triangle_part_indices
            parts = asset_parts(entity.params)
            indices = triangle_part_indices(entity.params)
            if parts and indices is not None and len(indices) == len(mesh.triangles):
                groups = {}
                for tri, role, index in zip(mesh.triangles, mesh.triangle_surfaces, indices):
                    g = groups.setdefault(index, ([], []))
                    g[0].append([int(tri[0]), int(tri[1]), int(tri[2])])
                    g[1].append(str(role))
                for index, (tris, roles) in sorted(groups.items()):
                    part_role, color, _name = parts[index]
                    material = _material("library_object", body.entity_id in selected, entity=entity, doc=doc,
                                         surface_role=part_role)
                    if not _surface_material_id(entity, part_role) and body.entity_id not in selected:
                        material["color"] = color
                    objects.append({
                        "id": str(body.entity_id),
                        "render_part": f"{body.entity_id}:{part_role}",
                        "kind": "library_object",
                        "vertices": vertices,
                        "triangles": tris,
                        "surfaces": roles,
                        "material": material,
                    })
                continue
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
    if doc is not None:
        # Door/window fixtures fill the wall holes (render only, see fixtures.py).
        from archforge.rendering.fixtures import opening_fixture_parts
        for entity in list(doc.entities.values()):
            if entity.kind not in ("door", "window") or not entity.visible:
                continue
            try:
                parts = opening_fixture_parts(doc, entity)
            except (KeyError, ValueError, TypeError):
                continue
            for key, verts, tris in parts:
                objects.append({
                    "id": str(entity.id),
                    "render_part": f"{entity.id}:{key}",
                    "kind": str(entity.kind),
                    "vertices": [[float(x), float(y), float(z)] for x, y, z in verts],
                    "triangles": [[int(a), int(b), int(c)] for a, b, c in tris],
                    "surfaces": [key] * len(tris),
                    "material": _material(key, entity.id in selected, entity=None, doc=doc),
                })
    return {"objects": objects}
