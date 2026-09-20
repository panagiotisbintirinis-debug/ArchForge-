from __future__ import annotations

import json

from archforge.pilot_v01 import SCENARIO_ID, SCENARIO_VERSION, run_pilot, write_evidence


def test_v01_runnable_pilot_schema_and_evidence(tmp_path):
    evidence = run_pilot(tmp_path)

    assert evidence["scenario"] == {"id": SCENARIO_ID, "version": SCENARIO_VERSION}
    assert evidence["outcome"] == "GO"
    assert evidence["criteria"]
    assert all(evidence["criteria"].values())

    determinism = evidence["determinism"]
    assert determinism["match"] is True
    assert determinism["run_1_fingerprint"] == determinism["run_2_fingerprint"]
    assert len(determinism["run_1_fingerprint"]) == 64

    persistence = evidence["persistence"]
    assert persistence["exact_ids_preserved_within_save_load"] is True
    runtime_ids = persistence["runtime_entity_ids_after_reload"]
    assert runtime_ids["pilot-pod-alpha"] == "pilot-pod-alpha"
    assert runtime_ids["pilot-pod-beta"] == "pilot-pod-beta"
    assert runtime_ids["pilot-pod-gamma"] == "pilot-pod-gamma"

    footprint = evidence["measurements"]["floor_footprint_area"]
    assert footprint["status"] == "exact"
    assert footprint["value"] is not None
    assert footprint["unit"] == "m^2"
    assert footprint["method"]

    fabrication = evidence["measurements"]["fabrication_shell_area"]
    assert fabrication["status"] == "unsupported"
    assert fabrication["value"] is None
    assert fabrication["method"] == "unsupported"

    reps = evidence["representations"]
    assert "opening" in reps["plan_roles"]
    assert "pod-junction-clipped" in reps["plan_roles"]
    assert "organic-junction" in reps["plan_roles"]
    assert reps["unsupported_elevation_explicit"] is True
    assert all(reps["fast_preview_pods_present"].values())
    assert all(reps["tessellated_preview_pods_present"].values())

    assert evidence["operations"]
    assert all(step["result"]["success"] for step in evidence["operations"])
    assert len(evidence["evidence_hash"]) == 64


def test_v01_pilot_replay_fingerprint_is_stable_across_independent_invocations(tmp_path):
    first = run_pilot(tmp_path / "first")
    second = run_pilot(tmp_path / "second")

    assert first["determinism"]["run_1_fingerprint"] == second["determinism"]["run_1_fingerprint"]
    assert first["criteria"] == second["criteria"]
    assert first["outcome"] == second["outcome"] == "GO"


def test_v01_pilot_writes_machine_and_human_readable_artifacts(tmp_path):
    json_path, summary_path, evidence = write_evidence(tmp_path)

    assert json_path.exists()
    assert summary_path.exists()

    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["evidence_hash"] == evidence["evidence_hash"]
    assert loaded["outcome"] == "GO"

    summary = summary_path.read_text(encoding="utf-8")
    assert "Pod Designer v0.1 runnable pilot: GO" in summary
    assert "GO/NO-GO is computed from this execution evidence" in summary
    assert evidence["determinism"]["run_1_fingerprint"] in summary
