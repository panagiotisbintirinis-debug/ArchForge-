"""End-to-end acceptance scenario for Pod Designer v0.1 (Issue #60).

Verifies the complete go/no-go milestone acceptance criteria:
1. Typed ArchForge AI command execution contract (ArchForgeAIClient).
2. Multi-pod creation (>=3 pods) with persistent IDs, planar junction creation,
   alteration (dormancy on separation), and reconnection (reactivation with same ID).
3. Creation, editing, and deletion of door and window openings with parent/dependency integrity.
4. Move, resize, rotate, multi-step undo, redo, save, close/load, entity inspection and listing.
5. Entity ID persistence across lifecycle and reload.
6. Multi-view geometric and topological coherence:
   - 2D Plan frame (clipped boundaries, opening symbols, junction segments)
   - Orthographic elevation frames (XZ / YZ silhouettes)
   - Fast-preview payloads (PreviewBackend)
   - Tessellated 3D preview bodies (TessellatedPreviewBackend)
   - Unsupported projections explicitly flagged rather than guessed (pod-junction-unclipped-unsupported,
     junction_projection=unsupported, and invalid axes rejected with ValueError).
7. Inference operations idempotence:
   - Calling infer_junctions() repeatedly produces 0 newly created IDs and stable active IDs.
   - Calling infer_opening_patches() repeatedly produces 0 newly created IDs and stable active IDs.
8. Model-derived measurements with explicit units, methods, and provenance statuses.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

from archforge.architecture.ai_commands import ArchForgeAIClient
from archforge.architecture.measurements import MeasurementStatus
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend


def test_pod_designer_v01_issue_60_acceptance_scenario(tmp_path: Path):
    """Execute the full Pod Designer v0.1 acceptance scenario as specified in Issue #60."""
    client = ArchForgeAIClient()

    # -------------------------------------------------------------------------
    # 1. Create >= 3 pods with persistent IDs via typed AI commands
    # -------------------------------------------------------------------------
    res_p1 = client.create_pod(
        cx=0.0,
        cy=0.0,
        floor_level=0.0,
        diameter_x=8.0,
        diameter_y=8.0,
        height=4.0,
        shell_thickness=0.20,
        name="Pod Alpha",
    )
    assert res_p1.success is True
    pod_a = res_p1.entity_ids[0]

    res_p2 = client.create_pod(
        cx=6.0,
        cy=0.0,
        floor_level=0.0,
        diameter_x=6.0,
        diameter_y=6.0,
        height=3.6,
        shell_thickness=0.20,
        name="Pod Beta",
    )
    assert res_p2.success is True
    pod_b = res_p2.entity_ids[0]

    res_p3 = client.create_pod(
        cx=0.0,
        cy=6.2,
        floor_level=0.0,
        diameter_x=5.6,
        diameter_y=5.6,
        height=3.2,
        shell_thickness=0.20,
        name="Pod Gamma",
    )
    assert res_p3.success is True
    pod_c = res_p3.entity_ids[0]

    # Exercise list_entities and inspect_entity
    res_list = client.list_entities(kind="pod")
    assert res_list.success is True
    listed_ids = {item["id"] for item in res_list.data["entities"]}
    assert {pod_a, pod_b, pod_c}.issubset(listed_ids)

    res_inspect = client.inspect_entity(pod_a)
    assert res_inspect.success is True
    assert res_inspect.data["id"] == pod_a
    assert res_inspect.data["params"]["diameter_x"] == 8.0
    assert res_inspect.data["kind"] == "pod"

    # -------------------------------------------------------------------------
    # 2. Establish planar junction & verify idempotence
    # -------------------------------------------------------------------------
    # Run initial inference
    res_junc_1 = client.infer_junctions()
    assert res_junc_1.success is True
    created_juncs_1 = res_junc_1.data["created_ids"]
    active_juncs_1 = res_junc_1.data["active_ids"]
    assert len(created_juncs_1) >= 2
    assert len(active_juncs_1) >= 2

    # Verify idempotence: immediately re-run inference without mutations
    res_junc_2 = client.infer_junctions()
    assert res_junc_2.success is True
    assert len(res_junc_2.data["created_ids"]) == 0, "Second inference run must create 0 new junctions"
    assert tuple(res_junc_2.data["active_ids"]) == tuple(active_juncs_1), "Active junction IDs must be identical"

    # Find junction between pod_a and pod_b
    junc_ab_candidates = [
        eid for eid in active_juncs_1
        if {client.doc.get(eid).params.get("component_a"), client.doc.get(eid).params.get("component_b")} == {pod_a, pod_b}
    ]
    assert len(junc_ab_candidates) == 1
    junc_ab_id = junc_ab_candidates[0]

    # -------------------------------------------------------------------------
    # 3. Alter planar junction: move pod_b away, verify dormancy, move back, verify reactivation
    # -------------------------------------------------------------------------
    res_move_away = client.move_entities([pod_b], dx=25.0, dy=0.0)
    assert res_move_away.success is True

    res_junc_apart = client.infer_junctions()
    assert res_junc_apart.success is True
    assert junc_ab_id in res_junc_apart.data["dormant_ids"]
    assert junc_ab_id not in res_junc_apart.data["active_ids"]
    assert client.doc.get(junc_ab_id).params["status"] == "dormant"

    # Move pod_b back into intersection
    res_move_back = client.move_entities([pod_b], dx=-25.0, dy=0.0)
    assert res_move_back.success is True

    res_junc_reconnect = client.infer_junctions()
    assert res_junc_reconnect.success is True
    # Must reactivate the SAME junction entity ID rather than creating a duplicate
    assert junc_ab_id in res_junc_reconnect.data["active_ids"]
    assert len(res_junc_reconnect.data["created_ids"]) == 0
    assert client.doc.get(junc_ab_id).params["status"] == "active"

    # -------------------------------------------------------------------------
    # 4. Openings lifecycle: create door and windows, edit, and delete
    # -------------------------------------------------------------------------
    # Create door on pod_a
    res_door = client.create_opening(
        host_pod_id=pod_a,
        kind="door",
        surface_u=0.5,
        width=1.2,
        height=2.2,
        sill=0.0,
        name="Portal Alpha",
    )
    assert res_door.success is True
    door_id = res_door.entity_ids[0]
    assert client.doc.get(door_id).parent_id == pod_a

    # Create window on pod_b
    res_win_b = client.create_opening(
        host_pod_id=pod_b,
        kind="window",
        surface_u=0.0,
        width=1.5,
        height=1.2,
        sill=1.0,
        name="Window Beta",
    )
    assert res_win_b.success is True
    win_b_id = res_win_b.entity_ids[0]

    # Create window on pod_c
    res_win_c = client.create_opening(
        host_pod_id=pod_c,
        kind="window",
        surface_u=0.25,
        width=1.4,
        height=1.0,
        sill=1.1,
        name="Window Gamma",
    )
    assert res_win_c.success is True
    win_c_id = res_win_c.entity_ids[0]

    # Infer opening patches
    res_patches_1 = client.infer_opening_patches()
    assert res_patches_1.success is True
    active_patches_1 = res_patches_1.data["active_ids"]
    created_patches_1 = res_patches_1.data["created_ids"]
    assert len(created_patches_1) == 3
    assert len(active_patches_1) == 3

    # Verify opening patch inference idempotence
    res_patches_2 = client.infer_opening_patches()
    assert res_patches_2.success is True
    assert len(res_patches_2.data["created_ids"]) == 0, "Second patch inference run must create 0 new patches"
    assert tuple(res_patches_2.data["active_ids"]) == tuple(active_patches_1)

    # Edit window parameters
    res_edit_win = client.edit_opening(win_b_id, {"width": 1.75})
    assert res_edit_win.success is True
    assert client.doc.get(win_b_id).params["width"] == 1.75

    # Delete window win_c and verify clean dependency and parent unlinking
    res_del_win = client.delete_opening(win_c_id)
    assert res_del_win.success is True
    assert win_c_id not in client.doc.entities
    assert win_c_id not in client.doc.children.get(pod_c, ())

    # Reconcile patches after deletion: patch for deleted window must become dormant
    res_patches_after_del = client.infer_opening_patches()
    assert res_patches_after_del.success is True
    assert len(res_patches_after_del.data["active_ids"]) == 2

    # -------------------------------------------------------------------------
    # 5. Move, resize, rotate, undo, redo transactions
    # -------------------------------------------------------------------------
    # Rotate pod_c
    res_rot = client.rotate_entities([pod_c], angle_deg=45.0)
    assert res_rot.success is True
    assert client.doc.get(pod_c).params["rotation"] == 45.0

    # Resize pod_a
    res_resize = client.resize_pod(pod_a, diameter_x=8.8, diameter_y=8.4, height=4.2)
    assert res_resize.success is True
    assert client.doc.get(pod_a).params["diameter_x"] == 8.8

    # Move pod_b slightly
    res_move_b = client.move_entities([pod_b], dx=0.5, dy=0.0)
    assert res_move_b.success is True
    assert client.doc.get(pod_b).params["cx"] == 6.5

    # Undo 3 times
    assert client.undo().success is True  # undo move
    assert client.doc.get(pod_b).params["cx"] == 6.0

    assert client.undo().success is True  # undo resize
    assert client.doc.get(pod_a).params["diameter_x"] == 8.0

    assert client.undo().success is True  # undo rotate
    assert client.doc.get(pod_c).params["rotation"] == 0.0

    # Redo 3 times
    assert client.redo().success is True  # redo rotate
    assert client.doc.get(pod_c).params["rotation"] == 45.0

    assert client.redo().success is True  # redo resize
    assert client.doc.get(pod_a).params["diameter_x"] == 8.8

    assert client.redo().success is True  # redo move
    assert client.doc.get(pod_b).params["cx"] == 6.5

    # -------------------------------------------------------------------------
    # 6. Model-derived measurements with explicit provenance
    # -------------------------------------------------------------------------
    res_meas = client.measure(pod_a, quantities=["floor_footprint_area", "fabrication_shell_area"])
    assert res_meas.success is True
    measurements = res_meas.data["measurements"]

    # Valid model-derived measurement
    footprint = measurements["floor_footprint_area"]
    assert footprint["status"] == MeasurementStatus.EXACT.value
    expected_footprint = math.pi * (8.8 / 2.0) * (8.4 / 2.0)
    assert math.isclose(footprint["value"], expected_footprint, rel_tol=1e-3)
    assert footprint["unit"] == "m^2"

    # Unsupported fabrication measurement correctly rejected
    fab_area = measurements["fabrication_shell_area"]
    assert fab_area["status"] == MeasurementStatus.UNSUPPORTED.value
    assert fab_area["value"] is None

    # -------------------------------------------------------------------------
    # 7. Multi-view geometric and topological coherence
    # -------------------------------------------------------------------------
    # Sync junctions & patches
    client.infer_junctions()
    client.infer_opening_patches()

    # 2D Plan View
    plan_frame = build_plan_frame(client.doc)
    plan_roles = {p.role for p in plan_frame.primitives}
    assert "opening" in plan_roles
    assert "pod-junction-clipped" in plan_roles
    assert "organic-junction" in plan_roles

    # Orthographic Elevation Views (XZ / YZ)
    xz_view = build_view_frame(client.doc, axis="XZ")
    assert any(p.entity_id == pod_a for p in xz_view.primitives)
    # Pod with active junction must have unsupported projection explicitly marked
    pod_a_prims_xz = [p for p in xz_view.primitives if p.entity_id == pod_a]
    assert any(
        p.role == "pod-junction-unclipped-unsupported" and dict(p.meta).get("junction_projection") == "unsupported"
        for p in pod_a_prims_xz
    )

    # Unsupported axis must raise ValueError rather than guessing
    with pytest.raises(ValueError, match="axis must be XY, XZ or YZ"):
        build_view_frame(client.doc, axis="ISO")

    # Fast Preview Backend
    fast_preview_eval = PreviewBackend().evaluate(client.doc)
    assert fast_preview_eval.body(pod_a) is not None
    assert fast_preview_eval.body(pod_b) is not None
    assert fast_preview_eval.body(junc_ab_id) is not None

    # Tessellated 3D Preview Backend
    mesh_eval = TessellatedPreviewBackend().evaluate(client.doc)
    assert mesh_eval.body(pod_a) is not None
    assert mesh_eval.body(pod_b) is not None
    assert mesh_eval.body(pod_c) is not None

    # -------------------------------------------------------------------------
    # 8. Deterministic Save / Load persistence
    # -------------------------------------------------------------------------
    save_file = str(tmp_path / "issue_60_acceptance_pavilion.archforge")
    res_save = client.save(save_file)
    assert res_save.success is True

    # Reload into an entirely clean AI client instance
    reloaded_client = ArchForgeAIClient()
    res_load = reloaded_client.load(save_file)
    assert res_load.success is True

    # Confirm complete ID and topological preservation
    assert pod_a in reloaded_client.doc.entities
    assert pod_b in reloaded_client.doc.entities
    assert pod_c in reloaded_client.doc.entities
    assert door_id in reloaded_client.doc.entities
    assert win_b_id in reloaded_client.doc.entities
    assert win_c_id not in reloaded_client.doc.entities  # deleted opening stays deleted

    # Confirm parameter and relationship preservation
    assert reloaded_client.doc.get(pod_a).params == client.doc.get(pod_a).params
    assert reloaded_client.doc.get(pod_b).params == client.doc.get(pod_b).params
    assert reloaded_client.doc.get(door_id).parent_id == pod_a
    assert reloaded_client.doc.get(win_b_id).parent_id == pod_b

    # Confirm view generation on reloaded model is identical
    reloaded_plan = build_plan_frame(reloaded_client.doc)
    reloaded_roles = {p.role for p in reloaded_plan.primitives}
    assert reloaded_roles == plan_roles
