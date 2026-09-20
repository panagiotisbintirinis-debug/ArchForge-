"""Autonomous 30+ step AI command execution stress test via ArchForgeAIClient (Issue #53).

Validates the full v0.1 milestone contract (ROADMAP.md requirement #10):
- Executes >=30 scripted autonomous AI commands exclusively through ArchForgeAIClient.
- Tests pod creation, spatial translations, rotations, dimension resizing.
- Tests hosted door/window opening lifecycle, geometry validation, reveal patches.
- Tests organic junction inference, dormancy, and re-activation through client actions.
- Tests measurement querying with mathematical provenance and unsupported flags.
- Tests multi-step undo and redo transactions across the command stack.
- Tests save/load persistence preserving entity IDs, relationships, and geometric truth.
- Tests deliberate invalid AI operations asserting deterministic machine-readable errors
  and rollback without corrupting document state.
"""

from __future__ import annotations

import math
from pathlib import Path
import pytest

from archforge.architecture.ai_commands import ArchForgeAIClient, AICommandError, AIExecutionResult
from archforge.architecture.measurements import MeasurementStatus
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame
from archforge.geometry.mesh import TessellatedPreviewBackend


def test_autonomous_ai_client_30_step_execution_scenario(tmp_path: Path):
    """Run an autonomous 35-step architectural design sequence through ArchForgeAIClient."""
    client = ArchForgeAIClient()
    executed_steps = 0

    # -------------------------------------------------------------------------
    # STEP 1: AI creates Primary Central Living Pod (pod_1)
    # -------------------------------------------------------------------------
    res = client.create_pod(
        cx=0.0,
        cy=0.0,
        floor_level=0.0,
        diameter_x=8.0,
        diameter_y=8.0,
        height=4.0,
        shell_thickness=0.20,
        rotation=0.0,
        name="Living Hub",
    )
    executed_steps += 1
    assert res.success is True
    assert len(res.entity_ids) == 1
    pod_1 = res.entity_ids[0]
    assert client.doc.get(pod_1).params["diameter_x"] == 8.0

    # -------------------------------------------------------------------------
    # STEP 2: AI creates Secondary Studio Pod (pod_2) in overlapping position
    # -------------------------------------------------------------------------
    res = client.create_pod(
        cx=5.5,
        cy=0.0,
        floor_level=0.0,
        diameter_x=6.0,
        diameter_y=6.0,
        height=3.6,
        shell_thickness=0.20,
        rotation=0.0,
        name="Studio Pod",
    )
    executed_steps += 1
    assert res.success is True
    pod_2 = res.entity_ids[0]
    assert client.doc.get(pod_2).params["cx"] == 5.5

    # -------------------------------------------------------------------------
    # STEP 3: AI creates Disjoint Terrace Pod (pod_3)
    # -------------------------------------------------------------------------
    res = client.create_pod(
        cx=0.0,
        cy=12.0,
        floor_level=0.0,
        diameter_x=6.0,
        diameter_y=5.0,
        height=3.2,
        shell_thickness=0.20,
        rotation=0.0,
        name="Terrace Pod",
    )
    executed_steps += 1
    assert res.success is True
    pod_3 = res.entity_ids[0]

    # -------------------------------------------------------------------------
    # STEP 4: AI infers organic junctions (pod_1 and pod_2 overlap)
    # -------------------------------------------------------------------------
    res_junc = client.infer_junctions()
    executed_steps += 1
    assert res_junc.success is True
    assert len(res_junc.data["active_ids"]) == 1
    junc_1_2 = res_junc.data["active_ids"][0]
    assert client.doc.get(junc_1_2).kind == "organic_junction"

    # -------------------------------------------------------------------------
    # STEP 5: AI creates an exterior door opening on pod_1
    # -------------------------------------------------------------------------
    res_door1 = client.create_opening(
        host_pod_id=pod_1,
        kind="door",
        surface_u=0.5,  # Azimuth pi (-X direction, facing away from pod_2)
        width=1.2,
        height=2.2,
        sill=0.0,
        name="Main Entry",
    )
    executed_steps += 1
    assert res_door1.success is True
    door_1 = res_door1.entity_ids[0]
    assert client.doc.get(door_1).parent_id == pod_1

    # -------------------------------------------------------------------------
    # STEP 6: AI creates a window opening on pod_1
    # -------------------------------------------------------------------------
    res_win1 = client.create_opening(
        host_pod_id=pod_1,
        kind="window",
        surface_u=0.25,  # +Y direction
        width=1.8,
        height=1.4,
        sill=0.9,
        name="North Window",
    )
    executed_steps += 1
    assert res_win1.success is True
    win_1 = res_win1.entity_ids[0]
    assert client.doc.get(win_1).params["sill"] == 0.9

    # -------------------------------------------------------------------------
    # STEP 7: AI creates a window opening on studio pod_2
    # -------------------------------------------------------------------------
    res_win2 = client.create_opening(
        host_pod_id=pod_2,
        kind="window",
        surface_u=0.0,  # +X direction
        width=1.6,
        height=1.2,
        sill=1.0,
        name="East Studio Window",
    )
    executed_steps += 1
    assert res_win2.success is True
    win_2 = res_win2.entity_ids[0]

    # -------------------------------------------------------------------------
    # STEP 8: AI infers planar opening patches for pod openings
    # -------------------------------------------------------------------------
    res_patches = client.infer_opening_patches()
    executed_steps += 1
    assert res_patches.success is True
    assert len(res_patches.data["active_ids"]) == 3

    # -------------------------------------------------------------------------
    # STEP 9: AI queries model-derived measurements with provenance for pod_1
    # -------------------------------------------------------------------------
    res_meas1 = client.measure(pod_1, quantities=["floor_footprint_area", "fabrication_shell_area"])
    executed_steps += 1
    assert res_meas1.success is True
    m_footprint = res_meas1.data["measurements"]["floor_footprint_area"]
    assert m_footprint["status"] == MeasurementStatus.EXACT.value
    expected_area = math.pi * 4.0 * 4.0
    assert math.isclose(m_footprint["value"], expected_area, rel_tol=1e-3)
    # Fabrication metrics must be explicitly unsupported
    m_cost = res_meas1.data["measurements"]["fabrication_shell_area"]
    assert m_cost["status"] == MeasurementStatus.UNSUPPORTED.value

    # -------------------------------------------------------------------------
    # STEP 10: AI attempts an invalid opening (height exceeding pod clearance)
    # Assert deterministic machine-readable rejection and document safety.
    # -------------------------------------------------------------------------
    res_invalid_open = client.create_opening(
        host_pod_id=pod_1,
        kind="door",
        surface_u=0.75,
        width=1.0,
        height=5.0,  # Exceeds pod_1 height of 4.0
        sill=0.0,
    )
    executed_steps += 1
    assert res_invalid_open.success is False
    assert res_invalid_open.errors[0].code == "create_opening_failed"
    # Ensure no orphan entity was introduced
    assert len([e for e in client.doc.entities.values() if e.kind == "door"]) == 1

    # -------------------------------------------------------------------------
    # STEP 11: AI edits pod_1 dimensions via resize_pod
    # -------------------------------------------------------------------------
    res_resize1 = client.resize_pod(pod_1, diameter_x=9.0, diameter_y=8.0, height=4.2)
    executed_steps += 1
    assert res_resize1.success is True
    assert client.doc.get(pod_1).params["diameter_x"] == 9.0
    assert client.doc.get(pod_1).params["height"] == 4.2

    # -------------------------------------------------------------------------
    # STEP 12: AI edits door_1 parameters (widens entry)
    # -------------------------------------------------------------------------
    res_edit_door = client.edit_opening(door_1, {"width": 1.5})
    executed_steps += 1
    assert res_edit_door.success is True
    assert client.doc.get(door_1).params["width"] == 1.5

    # -------------------------------------------------------------------------
    # STEP 13: AI rotates pod_2 by 45 degrees
    # -------------------------------------------------------------------------
    res_rot = client.rotate_entities([pod_2], angle_deg=45.0)
    executed_steps += 1
    assert res_rot.success is True
    assert client.doc.get(pod_2).params["rotation"] == 45.0

    # -------------------------------------------------------------------------
    # STEP 14: AI translates pod_3 closer to pod_1 to form a 3-pod cluster
    # -------------------------------------------------------------------------
    res_move_p3 = client.move_entities([pod_3], dx=0.0, dy=-6.2, dz=0.0)
    executed_steps += 1
    assert res_move_p3.success is True
    assert math.isclose(client.doc.get(pod_3).params["cy"], 5.8)

    # -------------------------------------------------------------------------
    # STEP 15: AI re-infers junctions (now forms junctions with both pod_2 and pod_3)
    # -------------------------------------------------------------------------
    res_junc2 = client.infer_junctions()
    executed_steps += 1
    assert res_junc2.success is True
    assert len(res_junc2.data["active_ids"]) >= 2

    # -------------------------------------------------------------------------
    # STEP 16: AI moves pod_2 away to break intersection (junction dormancy test)
    # -------------------------------------------------------------------------
    res_move_p2_away = client.move_entities([pod_2], dx=10.0, dy=0.0)
    executed_steps += 1
    assert res_move_p2_away.success is True
    assert client.doc.get(pod_2).params["cx"] == 15.5

    # -------------------------------------------------------------------------
    # STEP 17: AI re-infers junctions -> pod_1/pod_2 junction becomes dormant
    # -------------------------------------------------------------------------
    res_junc_dormant = client.infer_junctions()
    executed_steps += 1
    assert res_junc_dormant.success is True
    assert junc_1_2 in res_junc_dormant.data["dormant_ids"]

    # -------------------------------------------------------------------------
    # STEP 18: AI undoes moving pod_2 away -> restores proximity
    # -------------------------------------------------------------------------
    res_undo_move = client.undo()
    executed_steps += 1
    assert res_undo_move.success is True
    assert math.isclose(client.doc.get(pod_2).params["cx"], 5.5)

    # -------------------------------------------------------------------------
    # STEP 19: AI re-infers junctions -> junction 1-2 re-awakens
    # -------------------------------------------------------------------------
    res_junc_reawake = client.infer_junctions()
    executed_steps += 1
    assert res_junc_reawake.success is True
    assert junc_1_2 in res_junc_reawake.data["active_ids"]

    # -------------------------------------------------------------------------
    # STEP 20: AI creates window on pod_3
    # -------------------------------------------------------------------------
    res_win3 = client.create_opening(
        host_pod_id=pod_3,
        kind="window",
        surface_u=0.5,
        width=1.4,
        height=1.1,
        sill=1.0,
        name="Terrace Window",
    )
    executed_steps += 1
    assert res_win3.success is True
    win_3 = res_win3.entity_ids[0]

    # -------------------------------------------------------------------------
    # STEP 21: AI deletes window win_1 from pod_1
    # -------------------------------------------------------------------------
    res_del_win = client.delete_opening(win_1)
    executed_steps += 1
    assert res_del_win.success is True
    assert win_1 not in client.doc.entities

    # -------------------------------------------------------------------------
    # STEP 22: AI re-infers patches -> patch for win_1 is removed/dormant
    # -------------------------------------------------------------------------
    res_patches2 = client.infer_opening_patches()
    executed_steps += 1
    assert res_patches2.success is True

    # -------------------------------------------------------------------------
    # STEP 23: AI undoes deletion of win_1
    # -------------------------------------------------------------------------
    res_undo_win = client.undo()
    executed_steps += 1
    assert res_undo_win.success is True
    assert win_1 in client.doc.entities
    assert client.doc.get(win_1).parent_id == pod_1

    # -------------------------------------------------------------------------
    # STEP 24: AI redoes deletion of win_1
    # -------------------------------------------------------------------------
    res_redo_win = client.redo()
    executed_steps += 1
    assert res_redo_win.success is True
    assert win_1 not in client.doc.entities

    # -------------------------------------------------------------------------
    # STEP 25: AI moves the entire cluster simultaneously
    # -------------------------------------------------------------------------
    res_move_all = client.move_entities([pod_1, pod_2, pod_3], dx=-2.0, dy=1.0)
    executed_steps += 1
    assert res_move_all.success is True
    assert math.isclose(client.doc.get(pod_1).params["cx"], -2.0)
    assert math.isclose(client.doc.get(pod_2).params["cx"], 3.5)
    assert math.isclose(client.doc.get(pod_3).params["cx"], -2.0)

    # -------------------------------------------------------------------------
    # STEP 26: AI executes action via generic execute_action dispatcher (edit pod_3)
    # -------------------------------------------------------------------------
    res_gen_edit = client.execute_action(
        "edit_pod",
        {"pod_id": pod_3, "changes": {"diameter_x": 7.5, "height": 3.8}}
    )
    executed_steps += 1
    assert res_gen_edit.success is True
    assert client.doc.get(pod_3).params["diameter_x"] == 7.5
    assert client.doc.get(pod_3).params["height"] == 3.8

    # -------------------------------------------------------------------------
    # STEP 27: AI queries measurements for pod_3 via execute_action
    # -------------------------------------------------------------------------
    res_gen_meas = client.execute_action("measure", {"entity_id": pod_3})
    executed_steps += 1
    assert res_gen_meas.success is True
    assert "floor_footprint_area" in res_gen_meas.data["measurements"]

    # -------------------------------------------------------------------------
    # STEP 28: AI saves the project to a file
    # -------------------------------------------------------------------------
    proj_file = str(tmp_path / "autonomous_session.archforge")
    res_save = client.save(proj_file)
    executed_steps += 1
    assert res_save.success is True
    assert Path(proj_file).exists()

    # -------------------------------------------------------------------------
    # STEP 29: AI creates a fresh client instance and loads project from disk
    # -------------------------------------------------------------------------
    fresh_client = ArchForgeAIClient()
    res_load = fresh_client.load(proj_file)
    executed_steps += 1
    assert res_load.success is True
    assert pod_1 in fresh_client.doc.entities
    assert pod_2 in fresh_client.doc.entities
    assert pod_3 in fresh_client.doc.entities
    assert door_1 in fresh_client.doc.entities
    assert win_1 not in fresh_client.doc.entities  # Stays deleted after save/load

    # Switch working reference to the restored fresh client
    client = fresh_client

    # -------------------------------------------------------------------------
    # STEP 30: AI creates an auxiliary Skylight pod (pod_4) on top of pod_1
    # -------------------------------------------------------------------------
    res_p4 = client.create_pod(
        cx=-2.0,
        cy=2.0,
        floor_level=3.5,
        diameter_x=3.0,
        diameter_y=3.0,
        height=2.0,
        name="Observatory Cupola",
    )
    executed_steps += 1
    assert res_p4.success is True
    pod_4 = res_p4.entity_ids[0]

    # -------------------------------------------------------------------------
    # STEP 31: AI executes invalid delete on non-existent entity
    # -------------------------------------------------------------------------
    res_bad_del = client.delete_pod("non_existent_entity_999")
    executed_steps += 1
    assert res_bad_del.success is False
    assert res_bad_del.errors[0].code == "entity_not_found"

    # -------------------------------------------------------------------------
    # STEP 32: AI resizes pod_4
    # -------------------------------------------------------------------------
    res_p4_res = client.resize_pod(pod_4, diameter_x=3.5, height=2.4)
    executed_steps += 1
    assert res_p4_res.success is True
    assert client.doc.get(pod_4).params["diameter_x"] == 3.5

    # -------------------------------------------------------------------------
    # STEP 33: AI inspects pod_4 via inspect_entity
    # -------------------------------------------------------------------------
    res_insp = client.inspect_entity(pod_4)
    executed_steps += 1
    assert res_insp.success is True
    assert res_insp.data["params"]["height"] == 2.4

    # -------------------------------------------------------------------------
    # STEP 34: AI re-infers opening patches and junctions
    # -------------------------------------------------------------------------
    res_sync_junc = client.infer_junctions()
    res_sync_patch = client.infer_opening_patches()
    executed_steps += 1
    assert res_sync_junc.success is True
    assert res_sync_patch.success is True

    # -------------------------------------------------------------------------
    # STEP 35: AI lists entities and verifies model semantic coherence
    # -------------------------------------------------------------------------
    res_list = client.list_entities(kind="pod")
    executed_steps += 1
    assert res_list.success is True
    found_pod_ids = {e["id"] for e in res_list.data["entities"]}
    assert {pod_1, pod_2, pod_3, pod_4}.issubset(found_pod_ids)

    # -------------------------------------------------------------------------
    # POST-EXECUTION TOPOLOGY AND VIEW CONSISTENCY VERIFICATION
    # -------------------------------------------------------------------------
    # Verify 2D plan frame
    plan_frame = build_plan_frame(client.doc)
    assert any(p.role in ("pod-junction-clipped", "model") and p.entity_id in (pod_1, pod_2) for p in plan_frame.primitives)
    assert any(p.role == "opening" for p in plan_frame.primitives)

    # Verify orthographic projection
    xz_view = build_view_frame(client.doc, axis="XZ")
    assert any(p.kind == "upper_ellipse" and p.entity_id in (pod_1, pod_2, pod_4) for p in xz_view.primitives)

    # Verify 3D tessellated preview
    eval_res = TessellatedPreviewBackend().evaluate(client.doc)
    assert eval_res.body(pod_1) is not None
    assert eval_res.body(pod_2) is not None
    assert eval_res.body(pod_3) is not None
    assert eval_res.body(pod_4) is not None

    # Assert at least 30 autonomous AI steps executed successfully
    assert executed_steps >= 35
