from __future__ import annotations

import math

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
    # Typed joinery roles (architecture/joinery.py); frame/leaf colours come from the finish.
    "window_leaf": {"color": "#3d4247", "roughness": 0.38, "metalness": 0.55},
    "window_handle": {"color": "#b8bcc0", "roughness": 0.3, "metalness": 0.85},
    "window_shading": {"color": "#3d4247", "roughness": 0.45, "metalness": 0.35},
    "window_sill": {"color": "#e6e2da", "roughness": 0.3, "metalness": 0.0},
    "door_glass": {"color": "#a9c3d2", "roughness": 0.03, "metalness": 0.1, "opacity": 0.28},
    "door_handle": {"color": "#b8bcc0", "roughness": 0.3, "metalness": 0.85},
    "door_shading": {"color": "#3d4247", "roughness": 0.45, "metalness": 0.35},
    "door_sill": {"color": "#e6e2da", "roughness": 0.3, "metalness": 0.0},
    "plant_trunk": {"color": "#6b4a2f", "roughness": 0.9, "metalness": 0.0},
    "library_object": {"color": "#b9b2a6", "roughness": 0.6, "metalness": 0.0},
    "roof_plate": {"color": "#8a6038", "roughness": 0.8, "metalness": 0.0},
    "roof_gable": {"color": "#d8d2c7", "roughness": 0.72, "metalness": 0.02},
    "roof_ridge": {"color": "#8a6038", "roughness": 0.8, "metalness": 0.0},
    "roof_hip": {"color": "#8a6038", "roughness": 0.8, "metalness": 0.0},
    "roof_rafter": {"color": "#a37548", "roughness": 0.8, "metalness": 0.0},
    "roof_batten": {"color": "#c19a6b", "roughness": 0.8, "metalness": 0.0},
    "roof_counter_batten": {"color": "#b48a5c", "roughness": 0.8, "metalness": 0.0},
    "roof_boarding": {"color": "#c9a46e", "roughness": 0.85, "metalness": 0.0},
    "roof_vapour_barrier": {"color": "#5b6c80", "roughness": 0.4, "metalness": 0.0},
    "roof_insulation": {"color": "#9cc3d9", "roughness": 0.9, "metalness": 0.0},
    "roof_membrane": {"color": "#d8dde2", "roughness": 0.5, "metalness": 0.0},
    "plumbing_point": {"color": "#2d6fb3", "roughness": 0.4, "metalness": 0.1},
    "electrical_point": {"color": "#e08a00", "roughness": 0.4, "metalness": 0.1},
    "ceiling_joists": {"color": "#c8a46e", "roughness": 0.8, "metalness": 0.0},
    "drainage_point": {"color": "#6b4a2b", "roughness": 0.6, "metalness": 0.0},
    "drain_pipe": {"color": "#c46a2b", "roughness": 0.55, "metalness": 0.0},
    "ventilation_point": {"color": "#b8bec6", "roughness": 0.3, "metalness": 0.6},
    "vent_duct": {"color": "#a9b0b8", "roughness": 0.35, "metalness": 0.7},
    "vent_terminal": {"color": "#5b6470", "roughness": 0.5, "metalness": 0.3},
    "mep_cold": {"color": "#1f6fd1", "roughness": 0.35, "metalness": 0.0},
    "mep_hot": {"color": "#d1301f", "roughness": 0.35, "metalness": 0.0},
    "cabinet_carcass": {"color": "#e9e5dd", "roughness": 0.6, "metalness": 0.0},
    "cabinet_shelf": {"color": "#e9e5dd", "roughness": 0.6, "metalness": 0.0},
    "cabinet_front": {"color": "#f4f1ea", "roughness": 0.45, "metalness": 0.0},
    "cabinet_handle": {"color": "#a7a9ac", "roughness": 0.3, "metalness": 0.85},
    "cabinet_plinth": {"color": "#3b3b3b", "roughness": 0.7, "metalness": 0.0},
    "cabinet_worktop": {"color": "#77716a", "roughness": 0.35, "metalness": 0.0},
    "cabinet_rail": {"color": "#b5b7ba", "roughness": 0.25, "metalness": 0.9},
    "cabinet_glass": {"color": "#b9d3de", "roughness": 0.05, "metalness": 0.1, "opacity": 0.35},
    "cabinet_mechanism": {"color": "#c9ccd0", "roughness": 0.3, "metalness": 0.8},
    "plant_canopy": {"color": "#4f7a3a", "roughness": 0.85, "metalness": 0.0},
    # Railings: the type / finish sets the look per role (railings.role_material).
    "railing_handrail": {"color": "#33373b", "roughness": 0.55, "metalness": 0.35},
    "railing_post": {"color": "#33373b", "roughness": 0.55, "metalness": 0.35},
    "railing_infill": {"color": "#33373b", "roughness": 0.55, "metalness": 0.35},
    "railing_glass": {"color": "#a9c3d2", "roughness": 0.03, "metalness": 0.1, "opacity": 0.3},
    "railing_base": {"color": "#c9c4bb", "roughness": 0.85, "metalness": 0.0},
    "drywall_ceiling": {"color": "#f3f1ec", "roughness": 0.85, "metalness": 0.0},
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
        if "opacity" in custom:  # glass presets
            spec["opacity"] = custom["opacity"]
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
        if body.semantic_kind == "pitched_roof" and entity is not None:
            # Timber members and the tiled surface as separate derived meshes.
            from archforge.structure.timber_roof import TILES
            groups = {}
            for tri, role in zip(mesh.triangles, mesh.triangle_surfaces):
                groups.setdefault(str(role), []).append([int(tri[0]), int(tri[1]), int(tri[2])])
            for role, tris in groups.items():
                if role == "tiles":
                    material = _material("roof_tiles", body.entity_id in selected, entity=entity, doc=doc, surface_role=role)
                    if not _surface_material_id(entity, role) and body.entity_id not in selected:
                        material["color"] = TILES[entity.params.get("tile", "roman")][2]
                        material["roughness"] = 0.75
                else:
                    material = _material(f"roof_{role}", body.entity_id in selected, entity=entity, doc=doc, surface_role=role)
                objects.append({"id": str(body.entity_id), "render_part": f"{body.entity_id}:{role}", "kind": "pitched_roof",
                                # Gable walls are walls: always shown, not part of the roof-frame layer.
                                "layer": None if role == "gable" else ("roof_structure" if role != "tiles" else "roof_tiles"),
                                "vertices": vertices, "triangles": tris, "surfaces": [role] * len(tris), "material": material})
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
        if body.semantic_kind == "railing" and entity is not None:
            # One derived mesh per role (handrail, posts, infill, glass, base); a palette
            # finish per role lives in surface_materials, like cabinets and wall faces.
            from archforge.architecture.railings import role_material
            groups = {}
            for tri, role in zip(mesh.triangles, mesh.triangle_surfaces):
                groups.setdefault(str(role), []).append([int(tri[0]), int(tri[1]), int(tri[2])])
            for role, tris in groups.items():
                material = _material(f"railing_{role}", body.entity_id in selected, entity=entity, doc=doc, surface_role=role)
                if not _surface_material_id(entity, role):
                    material.update(role_material(entity.params, role))
                objects.append({"id": str(body.entity_id), "render_part": f"{body.entity_id}:{role}", "kind": "railing",
                                "vertices": vertices, "triangles": tris, "surfaces": [role] * len(tris), "material": material})
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
            from archforge.architecture.wall_types import face_colors
            type_colors = face_colors(entity.params.get("wall_type", "generic"))
            groups = {}
            for tri, role in zip(mesh.triangles, mesh.triangle_surfaces):
                role = str(role)
                material_id = _surface_material_id(entity, role)
                key = str(material_id) if material_id else "__default__"
                if not material_id and role in ("exterior", "interior") and type_colors:
                    key = f"__type_{role}__"   # finishing layer of the wall assembly
                group = groups.setdefault(key, {"triangles": [], "surfaces": [], "role": role})
                group["triangles"].append([int(tri[0]), int(tri[1]), int(tri[2])])
                group["surfaces"].append(role)
            for key, group in groups.items():
                representative_role = group["role"]
                material = _material(
                    body.semantic_kind,
                    body.entity_id in selected,
                    entity=entity,
                    doc=doc,
                    surface_role=representative_role,
                )
                if key.startswith("__type_") and body.entity_id not in selected:
                    material["color"] = type_colors[0] if representative_role == "exterior" else type_colors[1]
                objects.append(
                    {
                        "id": str(body.entity_id),
                        "render_part": f"{body.entity_id}:{key}",
                        "kind": str(body.semantic_kind),
                        "vertices": vertices,
                        "triangles": group["triangles"],
                        "surfaces": group["surfaces"],
                        "material": material,
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
        # Derived water pipes (layer "mep"): one mesh per system, not entities.
        from archforge.mep.plumbing import pipe_mesh, route_plumbing_cached
        network = route_plumbing_cached(doc)
        from archforge.mep.plumbing import manifold_mesh
        for system in ("cold", "hot"):
            verts, tris = [], []
            for m in network.get("manifolds", ()):
                if m["system"] == system:
                    v, t = manifold_mesh(m)
                    base = len(verts)
                    verts += [list(map(float, q)) for q in v]
                    tris += [[base + i for i in tri] for tri in t]
            for a, b, dia in network[system]:
                # Drawn at least Ø40 so the route reads in 3D; the real Ø stays in the data/plan.
                v, t = pipe_mesh(a, b, max(dia, 40))
                base = len(verts)
                verts += [list(map(float, q)) for q in v]
                tris += [[base + i for i in tri] for tri in t]
            if tris:
                objects.append({
                    "id": "",
                    "render_part": f"mep:{system}",
                    "kind": "mep_pipe",
                    "layer": "mep",
                    "vertices": verts,
                    "triangles": tris,
                    "surfaces": ["pipe"] * len(tris),
                    "material": dict(_MATERIALS[f"mep_{system}"]),
                })
        # Derived cable runs (layer "elec"), one mesh per circuit kind.
        if any(e.kind == "electrical_point" for e in doc.entities.values()):
            from archforge.mep.electrical import CABLE_COLORS, route_cables_cached
            groups = {}
            wiring = route_cables_cached(doc)
            boxes = ([], [])
            for x, y, z, _kind, _cid in wiring["boxes"]:
                s = 0.05
                base = len(boxes[0])
                boxes[0].extend([float(x + dx), float(y + dy), float(z + dz)] for dx in (-s, s) for dy in (-s, s) for dz in (-s, s))
                for q in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
                    boxes[1].extend([[base + q[0], base + q[1], base + q[2]], [base + q[0], base + q[2], base + q[3]]])
            if boxes[1]:
                objects.append({"id": "", "render_part": "elec:boxes", "kind": "elec_box", "layer": "elec",
                                "vertices": boxes[0], "triangles": boxes[1], "surfaces": ["box"] * len(boxes[1]),
                                "material": {"color": "#3a3f48", "roughness": 0.6, "metalness": 0.0}})
            for a, b, group, _cid in wiring["runs"]:
                v, t = pipe_mesh(a, b, 25, sides=6)
                g = groups.setdefault(group, ([], []))
                base = len(g[0])
                g[0].extend(list(map(float, q)) for q in v)
                g[1].extend([base + i for i in tri] for tri in t)
            for group, (verts, tris) in groups.items():
                objects.append({"id": "", "render_part": f"elec:{group}", "kind": "elec_cable", "layer": "elec",
                                "vertices": verts, "triangles": tris, "surfaces": ["cable"] * len(tris),
                                "material": {"color": CABLE_COLORS.get(group, "#e07a00"), "roughness": 0.5, "metalness": 0.0}})
        # Foundation (layer "foundation"): footings and tie beams from the up-to-date analysis (never computed here).
        if any(e.kind == "structural_column" for e in doc.entities.values()):
            from archforge.structure.analysis import last_result
            from archforge.structure.foundation import TIE_B, TIE_H, levels
            fd = (last_result(doc) or {}).get("foundation") or {}
            verts, tris = [], []

            def box(corners, z0, z1):
                base = len(verts)
                for zz in (z0, z1):
                    verts.extend([float(cx), float(cy), float(zz)] for cx, cy in corners)
                for a, b, c in ((0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7)):
                    tris.append([base + a, base + b, base + c])
                for i in range(4):
                    j = (i + 1) % 4
                    tris.extend([[base + i, base + j, base + 4 + j], [base + i, base + 4 + j, base + 4 + i]])
            for ft in fd.get("footings", ()):
                h = float(ft["B_m"]) / 2
                top, bottom = levels(ft)
                box(((ft["x"] - h, ft["y"] - h), (ft["x"] + h, ft["y"] - h), (ft["x"] + h, ft["y"] + h), (ft["x"] - h, ft["y"] + h)),
                    bottom, top)
            for sp in fd.get("strips", ()):
                (ax, ay), (bx, by) = sp["a"], sp["b"]
                L = math.hypot(bx - ax, by - ay) or 1.0
                ux, uy = (bx - ax) / L, (by - ay) / L
                z = float(sp.get("z", 0.0))
                for half, z0, z1 in ((float(sp["B_m"]) / 2, z - float(sp["H_m"]), z - float(sp["H_m"]) + float(sp["hf_m"])),
                                     (float(sp["bw_m"]) / 2, z - float(sp["H_m"]) + float(sp["hf_m"]), z)):
                    nx, ny = -uy * half, ux * half
                    box(((ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)), z0, z1)
            for t in fd.get("ties", ()):
                (ax, ay), (bx, by) = t["a"], t["b"]
                L = math.hypot(bx - ax, by - ay) or 1.0
                nx, ny = -(by - ay) / L * TIE_B / 2, (bx - ax) / L * TIE_B / 2
                z = float(t.get("z", 0.0))
                box(((ax + nx, ay + ny), (bx + nx, by + ny), (bx - nx, by - ny), (ax - nx, ay - ny)), z - TIE_H, z)
            if tris:
                objects.append({"id": "", "render_part": "foundation", "kind": "foundation", "layer": "foundation",
                                "vertices": verts, "triangles": tris, "surfaces": ["concrete"] * len(tris),
                                "material": {"color": "#9a9a95", "roughness": 0.8, "metalness": 0.0}})
        # Derived drainage (layer "drain"): sloped pipes, stacks, floor drains and manhole, true diameters.
        if any(e.kind == "plumbing_point" for e in doc.entities.values()):
            from archforge.mep.drainage import route_drainage_cached
            from archforge.mep.plumbing import pipe_mesh as _pipe
            route = route_drainage_cached(doc)
            verts, tris = [], []
            parts = [_pipe(a, b, max(dn, 50), sides=10) for a, b, dn, _k in route["pipes"]]
            for n in route["nodes"]:
                if n["kind"] == "manhole":
                    parts.append(_pipe((n["x"], n["y"], n["z"] - 0.6), (n["x"], n["y"], n["z"]), 600, sides=4))
                elif n["kind"] == "floor_drain":
                    parts.append(_pipe((n["x"], n["y"], n["z"] - 0.02), (n["x"], n["y"], n["z"] + 0.005), 150, sides=8))
            for v, t in parts:
                base = len(verts)
                verts += [list(map(float, q)) for q in v]
                tris += [[base + i for i in tri] for tri in t]
            if tris:
                objects.append({"id": "", "render_part": "drain:pipes", "kind": "drain_pipe", "layer": "drain",
                                "vertices": verts, "triangles": tris, "surfaces": ["pipe"] * len(tris),
                                "material": dict(_MATERIALS["drain_pipe"])})
        # Derived extract ducts (layer "vent"): ducts at their true Ø, grilles and roof caps.
        if any(e.kind == "ventilation_point" for e in doc.entities.values()):
            from archforge.mep.ventilation import duct_meshes, route_ventilation_cached
            for part, (verts, tris) in zip(("duct", "terminal"), duct_meshes(route_ventilation_cached(doc))):
                if tris:
                    objects.append({"id": "", "render_part": f"vent:{part}", "kind": f"vent_{part}", "layer": "vent",
                                    "vertices": verts, "triangles": tris, "surfaces": [part] * len(tris),
                                    "material": dict(_MATERIALS[f"vent_{part}"])})
        # Door/window fixtures fill the wall holes (render only, see fixtures.py).
        from archforge.rendering.fixtures import opening_fixture_parts
        for entity in list(doc.entities.values()):
            if entity.kind not in ("door", "window") or not entity.visible:
                continue
            try:
                parts = opening_fixture_parts(doc, entity)
            except (KeyError, ValueError, TypeError):
                continue
            typed = _is_typed_opening(entity)
            for key, verts, tris in parts:
                material = _material(key, entity.id in selected, entity=None, doc=doc)
                if typed:
                    # Joinery roles (κάσα, φύλλο, τζάμι, …): finish of the type,
                    # palette override per role in surface_materials.
                    from archforge.architecture.joinery import material_look
                    role = key.split('_', 1)[1]
                    material = _material(key, entity.id in selected, entity=entity, doc=doc, surface_role=role)
                    if not _surface_material_id(entity, role):
                        material.update(material_look(entity.params, entity.kind, role))
                objects.append({
                    "id": str(entity.id),
                    "render_part": f"{entity.id}:{key}",
                    "kind": str(entity.kind),
                    "vertices": [[float(x), float(y), float(z)] for x, y, z in verts],
                    "triangles": [[int(a), int(b), int(c)] for a, b, c in tris],
                    "surfaces": [key] * len(tris),
                    "material": material,
                })
    return {"objects": objects}


def _is_typed_opening(entity):
    from archforge.architecture.joinery import is_typed
    return is_typed(entity.params)
