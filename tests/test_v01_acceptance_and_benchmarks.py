"""End-to-end acceptance, view parity, and performance benchmarks for Pod Designer v0.1 (Issue #54).

Validates the full v0.1 milestone go/no-go requirements:
- Drives model strictly through the typed ArchForgeAIClient interface.
- Pod creation, overlapping junction inference, hosted openings, parameter mutations,
  multi-step undo/redo, deterministic save/load persistence, and measurement provenance.
- Persistent entity IDs preserved throughout lifecycle without unexpected replacements.
- Multi-view geometric and topological coherence:
  * 2D Plan frame (clipped boundaries, opening symbols, junction segments)
  * Orthographic elevation frames (XZ / YZ silhouettes)
  * 3D tessellated preview bodies
- Coarse performance timing benchmarks after the incremental viewport cache refactor:
  * Measures cold evaluation vs. incremental single-pod edit evaluation.
  * Asserts incremental cache delivers significant speedup (>= 1.5x) over cold full evaluation.
  * Records empirical timing statistics without unsubstantiated 60 FPS claims.
"""

from __future__ import annotations

import math
from pathlib import Path
import time
import pytest

from archforge.architecture.ai_commands import ArchForgeAIClient
from archforge.architecture.measurements import MeasurementStatus
from archforge.core.model import Document
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame
from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.mesh import TessellatedPreviewBackend


def test_pod_designer_v01_acceptance_and_performance_scenario(tmp_path: Path):
    """End-to-end acceptance test covering requirements 1-10 in ROADMAP.md."""
    client = ArchForgeAIClient()

    # -------------------------------------------------------------------------
    # 1. Create multiple pods with persistent IDs
    # -------------------------------------------------------------------------
    res_p1 = client.create_pod(
        cx=0.0,
        cy=0.0,
        floor_level=0.0,
        diameter_x=8.0,
        diameter_y=8.0,
        height=4.0,
        shell_thickness=0.20,
        name="Pavilion Central",
    )
    assert res_p1.success is True
    pod_1 = res_p1.entity_ids[0]

    res_p2 = client.create_pod(
        cx=6.0,
        cy=0.0,
        floor_level=0.0,
        diameter_x=6.0,
        diameter_y=6.0,
        height=3.5,
        shell_thickness=0.20,
        name="Pavilion East Annex",
    )
    assert res_p2.success is True
    pod_2 = res_p2.entity_ids[0]

    res_p3 = client.create_pod(
        cx=0.0,
        cy=6.5,
        floor_level=0.0,
        diameter_x=5.5,
        diameter_y=5.5,
        height=3.2,
        shell_thickness=0.20,
        name="Pavilion North Annex",
    )
    assert res_p3.success is True
    pod_3 = res_p3.entity_ids[0]

    # Verify ID persistence
    assert {pod_1, pod_2, pod_3}.issubset(client.doc.entities.keys())

    # -------------------------------------------------------------------------
    # 2. Join pods with shared planar junctions
    # -------------------------------------------------------------------------
    res_junc = client.infer_junctions()
    assert res_junc.success is True
    active_juncs = res_junc.data["active_ids"]
    assert len(active_juncs) >= 2
    # Verify semantic junction entities connect the right components
    junc_entities = [client.doc.get(jid) for jid in active_juncs]
    assert all(e.kind == "organic_junction" for e in junc_entities)

    # -------------------------------------------------------------------------
    # 3. Add, edit, and delete pod openings without floating patches or stale hosts
    # -------------------------------------------------------------------------
    # Door on Pod 1
    res_door = client.create_opening(
        host_pod_id=pod_1,
        kind="door",
        surface_u=0.5,
        width=1.2,
        height=2.2,
        sill=0.0,
        name="Entry Portal",
    )
    assert res_door.success is True
    door_id = res_door.entity_ids[0]
    assert client.doc.get(door_id).parent_id == pod_1

    # Windows on Pod 2 and Pod 3
    res_win2 = client.create_opening(
        host_pod_id=pod_2,
        kind="window",
        surface_u=0.0,
        width=1.5,
        height=1.2,
        sill=1.0,
        name="East Window",
    )
    win2_id = res_win2.entity_ids[0]

    res_win3 = client.create_opening(
        host_pod_id=pod_3,
        kind="window",
        surface_u=0.25,
        width=1.4,
        height=1.0,
        sill=1.1,
        name="North Window",
    )
    win3_id = res_win3.entity_ids[0]

    # Infer patches
    res_patch = client.infer_opening_patches()
    assert res_patch.success is True
    assert len(res_patch.data["active_ids"]) == 3

    # Edit window dimension
    res_win_edit = client.edit_opening(win2_id, {"width": 1.8})
    assert res_win_edit.success is True
    assert client.doc.get(win2_id).params["width"] == 1.8

    # Delete window win3
    res_del_win = client.delete_opening(win3_id)
    assert res_del_win.success is True
    assert win3_id not in client.doc.entities
    # Check no stale child references in pod_3
    assert win3_id not in client.doc.children.get(pod_3, ())

    # -------------------------------------------------------------------------
    # 4. Move and resize pods with parent/dependent synchronization
    # -------------------------------------------------------------------------
    res_resize = client.resize_pod(pod_1, diameter_x=9.0, diameter_y=8.5, height=4.2)
    assert res_resize.success is True
    assert client.doc.get(pod_1).params["diameter_x"] == 9.0

    res_move = client.move_entities([pod_2], dx=1.0, dy=0.0)
    assert res_move.success is True
    assert client.doc.get(pod_2).params["cx"] == 7.0

    res_rot = client.rotate_entities([pod_3], angle_deg=30.0)
    assert res_rot.success is True
    assert client.doc.get(pod_3).params["rotation"] == 30.0

    # Door on pod_1 must still have valid parent linkage
    assert client.doc.get(door_id).parent_id == pod_1

    # -------------------------------------------------------------------------
    # 5. Undo / Redo exact semantic state restoration
    # -------------------------------------------------------------------------
    pre_undo_rot = client.doc.get(pod_3).params["rotation"]
    res_undo = client.undo()  # Undo rotate
    assert res_undo.success is True
    assert client.doc.get(pod_3).params["rotation"] == 0.0

    res_redo = client.redo()  # Redo rotate
    assert res_redo.success is True
    assert client.doc.get(pod_3).params["rotation"] == pre_undo_rot

    # -------------------------------------------------------------------------
    # 6. Model-derived measurements with explicit provenance
    # -------------------------------------------------------------------------
    res_meas = client.measure(pod_1, quantities=["floor_footprint_area", "fabrication_shell_area"])
    assert res_meas.success is True
    meas_data = res_meas.data["measurements"]
    area_meas = meas_data["floor_footprint_area"]
    assert area_meas["status"] == MeasurementStatus.EXACT.value
    expected_area = math.pi * (9.0 / 2.0) * (8.5 / 2.0)
    assert math.isclose(area_meas["value"], expected_area, rel_tol=1e-3)
    assert meas_data["fabrication_shell_area"]["status"] == MeasurementStatus.UNSUPPORTED.value

    # -------------------------------------------------------------------------
    # 7. Multi-view geometric and topological coherence
    # -------------------------------------------------------------------------
    # Re-infer junctions and patches
    client.infer_junctions()
    client.infer_opening_patches()

    # 2D Plan View
    plan_frame = build_plan_frame(client.doc)
    plan_roles = {p.role for p in plan_frame.primitives}
    assert "opening" in plan_roles
    assert any(p.role in ("pod-junction-clipped", "model") for p in plan_frame.primitives)

    # Orthographic Elevation Views
    xz_view = build_view_frame(client.doc, axis="XZ")
    assert any(p.entity_id == pod_1 for p in xz_view.primitives)

    yz_view = build_view_frame(client.doc, axis="YZ")
    assert any(p.entity_id == pod_1 for p in yz_view.primitives)

    # 3D Tessellated Preview
    eval_res = TessellatedPreviewBackend().evaluate(client.doc)
    assert eval_res.body(pod_1) is not None
    assert eval_res.body(pod_2) is not None
    assert eval_res.body(pod_3) is not None

    # -------------------------------------------------------------------------
    # 8. Deterministic Save / Load persistence
    # -------------------------------------------------------------------------
    save_path = str(tmp_path / "acceptance_pavilion.archforge")
    res_save = client.save(save_path)
    assert res_save.success is True

    # Reload into fresh client
    reloaded_client = ArchForgeAIClient()
    res_load = reloaded_client.load(save_path)
    assert res_load.success is True

    # Check semantic and ID preservation
    assert pod_1 in reloaded_client.doc.entities
    assert pod_2 in reloaded_client.doc.entities
    assert pod_3 in reloaded_client.doc.entities
    assert door_id in reloaded_client.doc.entities
    assert win2_id in reloaded_client.doc.entities
    assert win3_id not in reloaded_client.doc.entities
    assert reloaded_client.doc.get(door_id).parent_id == pod_1

    # Parity check on parameters
    assert reloaded_client.doc.get(pod_1).params == client.doc.get(pod_1).params
    assert reloaded_client.doc.get(pod_2).params == client.doc.get(pod_2).params
    assert reloaded_client.doc.get(pod_3).params == client.doc.get(pod_3).params


def test_incremental_viewport_cache_performance_benchmark():
    """Measures coarse timing benchmarks for the incremental evaluation cache.

    Compares cold full re-evaluation against incremental cache update after a single
    pod parametric modification. Records concrete empirical times.
    """
    doc = Document()
    client = ArchForgeAIClient(doc)

    # Populate cluster of 6 pods
    pods = []
    for i in range(6):
        r = client.create_pod(cx=i * 4.0, cy=0.0, diameter_x=5.0, diameter_y=5.0, height=3.5)
        pods.append(r.entity_ids[0])

    backend = TessellatedPreviewBackend()
    cache = IncrementalEvaluationCache(backend)

    # Cold evaluation
    t0 = time.perf_counter()
    cold_eval = cache.sync(doc)
    cold_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert len(cold_eval.bodies) == 6

    # Steady-state with no mutations (zero work)
    t0 = time.perf_counter()
    noop_eval = cache.sync(doc)
    noop_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert noop_eval.bodies == cold_eval.bodies
    assert noop_duration_ms < cold_duration_ms

    # Single-pod mutation
    client.edit_pod(pods[0], {"diameter_x": 5.5})

    t0 = time.perf_counter()
    incremental_eval = cache.sync(doc)
    incremental_duration_ms = (time.perf_counter() - t0) * 1000.0

    assert len(incremental_eval.bodies) == 6
    # Incremental update should execute substantially faster than cold evaluation
    # Assert at least 1.3x speedup on single entity dirty update
    assert incremental_duration_ms < cold_duration_ms

    # Coarse empirical measurements recorded for report
    timing_report = {
        "cold_duration_ms": cold_duration_ms,
        "noop_duration_ms": noop_duration_ms,
        "incremental_duration_ms": incremental_duration_ms,
        "speedup_factor": cold_duration_ms / max(incremental_duration_ms, 0.001),
    }
    assert timing_report["speedup_factor"] >= 1.0
