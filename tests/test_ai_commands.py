"""Tests for the typed AI-to-ArchForge command execution surface (Issue #42)."""

import pytest
from pathlib import Path
from archforge.architecture.ai_commands import ArchForgeAIClient, AICommandError, AIExecutionResult
from archforge.architecture.measurements import MeasurementStatus


def test_ai_client_pod_lifecycle_and_undo_redo():
    client = ArchForgeAIClient()
    
    # 1. Create Pod
    res = client.create_pod(cx=1.0, cy=2.0, floor_level=0.0, diameter_x=6.0, diameter_y=5.0, height=3.2, name="Main Pod")
    assert res.success is True
    assert len(res.entity_ids) == 1
    pod_id = res.entity_ids[0]
    assert res.undo_available is True
    assert res.redo_available is False
    
    # Check inspection
    insp = client.inspect_entity(pod_id)
    assert insp.success is True
    assert insp.data["params"]["cx"] == 1.0
    assert insp.data["params"]["diameter_x"] == 6.0
    
    # 2. Edit Pod
    res_edit = client.edit_pod(pod_id, {"cx": 2.5, "rotation": 45.0})
    assert res_edit.success is True
    assert client.doc.get(pod_id).params["cx"] == 2.5
    assert client.doc.get(pod_id).params["rotation"] == 45.0
    
    # 3. Undo Edit
    res_undo = client.undo()
    assert res_undo.success is True
    assert client.doc.get(pod_id).params["cx"] == 1.0
    assert res_undo.redo_available is True
    
    # 4. Redo Edit
    res_redo = client.redo()
    assert res_redo.success is True
    assert client.doc.get(pod_id).params["cx"] == 2.5


def test_ai_client_spatial_manipulations():
    client = ArchForgeAIClient()
    p1 = client.create_pod(cx=0.0, cy=0.0, diameter_x=4.0, diameter_y=4.0).entity_ids[0]
    p2 = client.create_pod(cx=5.0, cy=0.0, diameter_x=4.0, diameter_y=4.0).entity_ids[0]
    
    # Move both entities
    res_move = client.move_entities([p1, p2], dx=1.0, dy=-2.0)
    assert res_move.success is True
    assert client.doc.get(p1).params["cx"] == 1.0
    assert client.doc.get(p1).params["cy"] == -2.0
    assert client.doc.get(p2).params["cx"] == 6.0
    assert client.doc.get(p2).params["cy"] == -2.0
    
    # Rotate entity
    res_rot = client.rotate_entities([p1], angle_deg=30.0)
    assert res_rot.success is True
    assert client.doc.get(p1).params["rotation"] == 30.0
    
    # Resize pod
    res_resize = client.resize_pod(p2, diameter_x=7.0, height=4.5)
    assert res_resize.success is True
    assert client.doc.get(p2).params["diameter_x"] == 7.0
    assert client.doc.get(p2).params["height"] == 4.5


def test_ai_client_openings_and_validation():
    client = ArchForgeAIClient()
    pod_id = client.create_pod(cx=0.0, cy=0.0, diameter_x=6.0, diameter_y=6.0, height=3.5).entity_ids[0]
    
    # Create valid door
    res_door = client.create_opening(pod_id, kind="door", surface_u=0.25, width=1.0, height=2.1, sill=0.0)
    assert res_door.success is True
    door_id = res_door.entity_ids[0]
    assert client.doc.get(door_id).parent_id == pod_id
    
    # Attempt invalid opening kind
    res_invalid_kind = client.create_opening(pod_id, kind="skylight", surface_u=0.5, width=1.0, height=1.0)
    assert res_invalid_kind.success is False
    assert res_invalid_kind.errors[0].code == "unsupported_opening_kind"
    
    # Attempt opening exceeding pod vertical bounds (sill + height > pod height)
    res_overflow = client.create_opening(pod_id, kind="window", surface_u=0.5, width=1.0, height=3.0, sill=1.5)
    assert res_overflow.success is False
    assert res_overflow.errors[0].code == "create_opening_failed"
    
    # Infer opening patches
    res_patch = client.infer_opening_patches()
    assert res_patch.success is True
    assert len(res_patch.data["created_ids"]) >= 1


def test_ai_client_junction_inference_and_persistence(tmp_path):
    client = ArchForgeAIClient()
    p1 = client.create_pod(cx=0.0, cy=0.0, diameter_x=6.0, diameter_y=6.0).entity_ids[0]
    p2 = client.create_pod(cx=4.0, cy=0.0, diameter_x=6.0, diameter_y=6.0).entity_ids[0]
    
    # Infer active junction
    res_junc = client.infer_junctions()
    assert res_junc.success is True
    assert len(res_junc.data["active_ids"]) == 1
    junc_id = res_junc.data["active_ids"][0]
    assert client.doc.get(junc_id).params["status"] == "active"
    
    # Save document
    save_path = tmp_path / "ai_client_test.archforge"
    res_save = client.save(str(save_path))
    assert res_save.success is True
    
    # Load into new client
    client2 = ArchForgeAIClient()
    res_load = client2.load(str(save_path))
    assert res_load.success is True
    assert set(client2.doc.entities.keys()) == set(client.doc.entities.keys())
    assert client2.doc.get(junc_id).params["status"] == "active"


def test_ai_client_measurements_provenance():
    client = ArchForgeAIClient()
    pod_id = client.create_pod(cx=0.0, cy=0.0, diameter_x=8.0, diameter_y=6.0, height=4.0).entity_ids[0]
    
    res_meas = client.measure(pod_id)
    assert res_meas.success is True
    measurements = res_meas.data["measurements"]
    
    assert measurements["diameter_x"]["value"] == 8.0
    assert measurements["diameter_x"]["unit"] == "m"
    assert measurements["diameter_x"]["status"] == MeasurementStatus.EXACT.value
    assert measurements["floor_footprint_area"]["value"] == pytest.approx(3.141592653589793 * 4.0 * 3.0)
    
    # Querying unsupported fabrication metric explicitly carries UNSUPPORTED status and no invented numbers
    res_unsupported = client.measure(pod_id, quantities=["fabrication_shell_area"])
    assert res_unsupported.success is True
    meas_unsupported = res_unsupported.data["measurements"]["fabrication_shell_area"]
    assert meas_unsupported["status"] == MeasurementStatus.UNSUPPORTED.value
    assert meas_unsupported["value"] is None
    assert "fabrication" in meas_unsupported["reason"].lower()


def test_ai_client_explicit_machine_readable_errors():
    client = ArchForgeAIClient()
    
    # Edit nonexistent entity
    res = client.edit_pod("nonexistent-id", {"cx": 10.0})
    assert res.success is False
    assert len(res.errors) == 1
    err = res.errors[0]
    assert err.code == "entity_not_found"
    assert err.target_id == "nonexistent-id"
    err_dict = err.to_dict()
    assert err_dict["code"] == "entity_not_found"
    assert err_dict["target_id"] == "nonexistent-id"
    
    # Measure nonexistent entity
    res_m = client.measure("missing-id")
    assert res_m.success is False
    assert res_m.errors[0].code == "entity_not_found"
    
    # Undo on empty stack
    res_undo = client.undo()
    assert res_undo.success is False
    assert res_undo.errors[0].code == "nothing_to_undo"


def test_ai_client_generic_dispatch_and_manifest():
    client = ArchForgeAIClient()
    
    # 1. Inspect manifest
    manifest = client.get_action_manifest()
    assert manifest["version"] == "0.1"
    assert "create_pod" in manifest["actions"]
    assert "infer_junctions" in manifest["actions"]
    assert "measure" in manifest["actions"]
    
    # 2. Generic execute_action dispatch
    res = client.execute_action("create_pod", {"cx": 3.0, "cy": 1.5, "diameter_x": 5.0, "diameter_y": 5.0})
    assert res.success is True
    assert len(res.entity_ids) == 1
    pod_id = res.entity_ids[0]
    
    # 3. Generic dispatch for edit
    res_edit = client.execute_action("edit_pod", {"pod_id": pod_id, "changes": {"cx": 4.0}})
    assert res_edit.success is True
    assert client.doc.get(pod_id).params["cx"] == 4.0
    
    # 4. Unknown action dispatch returns machine-readable error
    res_unknown = client.execute_action("teleport_pod", {"pod_id": pod_id})
    assert res_unknown.success is False
    assert res_unknown.errors[0].code == "unknown_action"
    assert "supported_actions" in res_unknown.errors[0].details

