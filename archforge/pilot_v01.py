"""Runnable evidence pilot for the AI-native Pod Designer v0.1 milestone.

The pilot intentionally uses only ArchForgeAIClient.execute_action() for semantic
mutations. Derived views/backends are inspected as evidence, never mutated.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from archforge.architecture.ai_commands import ArchForgeAIClient
from archforge.core.plan_scene import build_plan_frame
from archforge.core.view_frame import build_view_frame
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend


SCENARIO_ID = "pod-designer-v0.1-runnable-pilot"
SCENARIO_VERSION = 1


def _json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _semantic_identity_map(client: ArchForgeAIClient) -> Dict[str, str]:
    """Map runtime ids to deterministic semantic identities for replay comparison."""
    identities: Dict[str, str] = {}
    for entity in client.doc.entities.values():
        if entity.kind == "organic_junction":
            key = str(entity.params.get("junction_key", "missing"))
            identities[entity.id] = f"organic_junction:{key}"
        elif entity.kind == "organic_opening_patch":
            opening_id = str(entity.params.get("opening_id", "missing"))
            identities[entity.id] = f"organic_opening_patch:{opening_id}"
        else:
            # Pilot-created source entities use explicit deterministic IDs.
            identities[entity.id] = entity.id
    return identities


def _canonical_state(client: ArchForgeAIClient) -> Dict[str, Any]:
    identities = _semantic_identity_map(client)

    def ref(raw: Any) -> Any:
        if isinstance(raw, str):
            return identities.get(raw, raw)
        if isinstance(raw, list):
            return [ref(x) for x in raw]
        if isinstance(raw, tuple):
            return [ref(x) for x in raw]
        if isinstance(raw, dict):
            return {str(k): ref(v) for k, v in sorted(raw.items())}
        return raw

    entities = []
    for entity in client.doc.entities.values():
        params = {
            str(k): ref(v)
            for k, v in sorted(entity.params.items())
            if str(k) not in {"_runtime_id"}
        }
        entities.append(
            {
                "semantic_id": identities[entity.id],
                "kind": entity.kind,
                "name": entity.name,
                "params": params,
                "parent_id": ref(entity.parent_id),
                "locked": entity.locked,
                "visible": entity.visible,
                "revision": entity.revision,
            }
        )
    entities.sort(key=lambda item: (item["semantic_id"], item["kind"]))

    dependencies = []
    for source, dependents in client.doc.dependencies.items():
        for dependent in dependents:
            dependencies.append((str(ref(source)), str(ref(dependent))))
    dependencies.sort()

    children = []
    for parent, child_ids in client.doc.children.items():
        for child in child_ids:
            children.append((str(ref(parent)), str(ref(child))))
    children.sort()

    return {
        "entities": entities,
        "dependencies": dependencies,
        "children": children,
    }


def _runtime_entity_ids(client: ArchForgeAIClient) -> Dict[str, str]:
    identities = _semantic_identity_map(client)
    return {
        semantic_id: runtime_id
        for runtime_id, semantic_id in sorted(identities.items(), key=lambda item: item[1])
    }


def _representation_evidence(client: ArchForgeAIClient) -> Dict[str, Any]:
    plan = build_plan_frame(client.doc)
    xz = build_view_frame(client.doc, "XZ")
    yz = build_view_frame(client.doc, "YZ")
    fast = PreviewBackend().evaluate(client.doc)
    mesh = TessellatedPreviewBackend().evaluate(client.doc)

    plan_roles = sorted({primitive.role for primitive in plan.primitives})
    xz_roles = sorted({primitive.role for primitive in xz.primitives})
    yz_roles = sorted({primitive.role for primitive in yz.primitives})

    pod_ids = ("pilot-pod-alpha", "pilot-pod-beta", "pilot-pod-gamma")
    fast_pods = {pod_id: fast.body(pod_id) is not None for pod_id in pod_ids}
    mesh_pods = {pod_id: mesh.body(pod_id) is not None for pod_id in pod_ids}

    unsupported_elevation = any(
        primitive.role == "pod-junction-unclipped-unsupported"
        and dict(primitive.meta).get("junction_projection") == "unsupported"
        for primitive in xz.primitives + yz.primitives
    )

    return {
        "plan_roles": plan_roles,
        "xz_roles": xz_roles,
        "yz_roles": yz_roles,
        "fast_preview_pods_present": fast_pods,
        "tessellated_preview_pods_present": mesh_pods,
        "unsupported_elevation_explicit": unsupported_elevation,
        "fast_preview_issue_codes": sorted(issue.code for issue in fast.issues),
        "tessellated_preview_issue_codes": sorted(issue.code for issue in mesh.issues),
    }


def _run_once(project_path: Path) -> Dict[str, Any]:
    client = ArchForgeAIClient()
    steps = []

    def execute(label: str, action: str, params: Dict[str, Any] | None = None):
        result = client.execute_action(action, params or {})
        steps.append({"label": label, "result": result.to_dict()})
        if not result.success:
            raise RuntimeError(f"{label} failed: {[error.message for error in result.errors]}")
        return result

    # Deterministic source IDs make user-authored identity inspectable across runs.
    execute("create pod alpha", "create_pod", {
        "cx": 0.0, "cy": 0.0, "floor_level": 0.0,
        "diameter_x": 8.0, "diameter_y": 8.0, "height": 4.0,
        "shell_thickness": 0.20, "name": "Pod Alpha", "custom_id": "pilot-pod-alpha",
    })
    execute("create pod beta", "create_pod", {
        "cx": 6.0, "cy": 0.0, "floor_level": 0.0,
        "diameter_x": 6.0, "diameter_y": 6.0, "height": 3.6,
        "shell_thickness": 0.20, "name": "Pod Beta", "custom_id": "pilot-pod-beta",
    })
    execute("create pod gamma", "create_pod", {
        "cx": 0.0, "cy": 6.2, "floor_level": 0.0,
        "diameter_x": 5.6, "diameter_y": 5.6, "height": 3.2,
        "shell_thickness": 0.20, "name": "Pod Gamma", "custom_id": "pilot-pod-gamma",
    })

    junction_first = execute("infer junctions", "infer_junctions")
    junction_second = execute("verify junction inference idempotence", "infer_junctions")
    junction_idempotent = (
        not junction_second.data["created_ids"]
        and tuple(junction_second.data["active_ids"]) == tuple(junction_first.data["active_ids"])
    )

    execute("create alpha door", "create_opening", {
        "host_pod_id": "pilot-pod-alpha", "kind": "door", "surface_u": 0.5,
        "width": 1.2, "height": 2.2, "sill": 0.0, "name": "Portal Alpha",
        "custom_id": "pilot-opening-alpha-door",
    })
    execute("create beta window", "create_opening", {
        "host_pod_id": "pilot-pod-beta", "kind": "window", "surface_u": 0.0,
        "width": 1.5, "height": 1.2, "sill": 1.0, "name": "Window Beta",
        "custom_id": "pilot-opening-beta-window",
    })
    execute("create gamma window", "create_opening", {
        "host_pod_id": "pilot-pod-gamma", "kind": "window", "surface_u": 0.25,
        "width": 1.4, "height": 1.0, "sill": 1.1, "name": "Window Gamma",
        "custom_id": "pilot-opening-gamma-window",
    })

    patches_first = execute("infer opening patches", "infer_opening_patches")
    patches_second = execute("verify opening patch inference idempotence", "infer_opening_patches")
    patches_idempotent = (
        not patches_second.data["created_ids"]
        and tuple(patches_second.data["active_ids"]) == tuple(patches_first.data["active_ids"])
    )

    execute("resize alpha", "resize_pod", {
        "pod_id": "pilot-pod-alpha", "diameter_x": 8.8, "diameter_y": 8.4, "height": 4.2,
    })
    execute("rotate gamma", "rotate_entities", {
        "entity_ids": ["pilot-pod-gamma"], "angle_deg": 45.0,
    })

    beta_before = client.doc.get("pilot-pod-beta").params["cx"]
    execute("move beta", "move_entities", {
        "entity_ids": ["pilot-pod-beta"], "dx": 0.5, "dy": 0.0, "dz": 0.0,
    })
    beta_after_move = client.doc.get("pilot-pod-beta").params["cx"]
    execute("undo beta move", "undo")
    beta_after_undo = client.doc.get("pilot-pod-beta").params["cx"]
    execute("redo beta move", "redo")
    beta_after_redo = client.doc.get("pilot-pod-beta").params["cx"]
    undo_redo_exact = (
        beta_after_move == beta_after_redo
        and beta_after_undo == beta_before
        and beta_after_move != beta_before
    )

    execute("reconcile junctions after edits", "infer_junctions")
    execute("reconcile opening patches after edits", "infer_opening_patches")

    measurement = execute("measure alpha", "measure", {
        "entity_id": "pilot-pod-alpha",
        "quantities": ["floor_footprint_area", "fabrication_shell_area"],
    })
    measurements = measurement.data["measurements"]
    measurement_contract = {
        "floor_footprint_area": measurements["floor_footprint_area"],
        "fabrication_shell_area": measurements["fabrication_shell_area"],
    }

    representations = _representation_evidence(client)
    state_before_save = _canonical_state(client)
    fingerprint_before_save = _json_hash(state_before_save)
    ids_before_save = _runtime_entity_ids(client)

    execute("save project", "save", {"filepath": str(project_path)})

    reloaded = ArchForgeAIClient()
    load_result = reloaded.execute_action("load", {"filepath": str(project_path)})
    steps.append({"label": "load project in fresh client", "result": load_result.to_dict()})
    if not load_result.success:
        raise RuntimeError(f"load failed: {[error.message for error in load_result.errors]}")

    state_after_load = _canonical_state(reloaded)
    fingerprint_after_load = _json_hash(state_after_load)
    ids_after_load = _runtime_entity_ids(reloaded)
    save_load_preserved = (
        state_after_load == state_before_save
        and ids_after_load == ids_before_save
        and fingerprint_after_load == fingerprint_before_save
    )

    checks = {
        "all_command_steps_succeeded": all(step["result"]["success"] for step in steps),
        "junction_inference_idempotent": junction_idempotent,
        "opening_patch_inference_idempotent": patches_idempotent,
        "undo_redo_exact": undo_redo_exact,
        "save_load_preserved_semantic_state_and_runtime_ids": save_load_preserved,
        "plan_has_opening": "opening" in representations["plan_roles"],
        "plan_has_clipped_pod": "pod-junction-clipped" in representations["plan_roles"],
        "plan_has_junction": "organic-junction" in representations["plan_roles"],
        "unsupported_elevation_is_explicit": representations["unsupported_elevation_explicit"],
        "fast_preview_contains_all_pods": all(representations["fast_preview_pods_present"].values()),
        "tessellated_preview_contains_all_pods": all(representations["tessellated_preview_pods_present"].values()),
        "exact_measurement_is_model_derived": (
            measurement_contract["floor_footprint_area"]["status"] == "exact"
            and measurement_contract["floor_footprint_area"]["value"] is not None
            and measurement_contract["floor_footprint_area"]["unit"] == "m^2"
            and bool(measurement_contract["floor_footprint_area"]["method"])
        ),
        "unsupported_fabrication_measurement_not_invented": (
            measurement_contract["fabrication_shell_area"]["status"] == "unsupported"
            and measurement_contract["fabrication_shell_area"]["value"] is None
        ),
    }

    return {
        "steps": steps,
        "checks": checks,
        "canonical_state": state_after_load,
        "fingerprint": fingerprint_after_load,
        "runtime_entity_ids": ids_after_load,
        "measurements": measurement_contract,
        "representations": representations,
    }


def run_pilot(output_dir: Path | str | None = None) -> Dict[str, Any]:
    """Run the scenario twice and return evidence plus a data-derived GO/NO-GO result."""
    if output_dir is None:
        output_root = Path(tempfile.mkdtemp(prefix="archforge-v01-pilot-"))
    else:
        output_root = Path(output_dir)
        output_root.mkdir(parents=True, exist_ok=True)

    first = _run_once(output_root / "pilot-run-1.archforge")
    second = _run_once(output_root / "pilot-run-2.archforge")
    deterministic_replay = first["fingerprint"] == second["fingerprint"]
    all_checks = dict(first["checks"])
    all_checks["deterministic_replay_fingerprint"] = deterministic_replay
    all_checks["second_run_checks_match_first"] = second["checks"] == first["checks"]

    outcome = "GO" if all(all_checks.values()) else "NO-GO"

    evidence = {
        "scenario": {"id": SCENARIO_ID, "version": SCENARIO_VERSION},
        "outcome": outcome,
        "criteria": all_checks,
        "determinism": {
            "run_1_fingerprint": first["fingerprint"],
            "run_2_fingerprint": second["fingerprint"],
            "match": deterministic_replay,
            "fingerprint_scope": "canonical semantic state; auto-inferred UUIDs are normalized to semantic keys",
        },
        "persistence": {
            "runtime_entity_ids_after_reload": first["runtime_entity_ids"],
            "exact_ids_preserved_within_save_load": first["checks"]["save_load_preserved_semantic_state_and_runtime_ids"],
        },
        "measurements": first["measurements"],
        "representations": first["representations"],
        "operations": first["steps"],
        "limitations": [
            "This pilot demonstrates deterministic semantic operations and inspectable evidence, not structural, code, environmental, cost, safety, or fabrication certification.",
            "Auto-inferred junction and opening-patch entities currently receive runtime UUIDs; replay fingerprints normalize them by stable semantic keys.",
            "Junction-clipped orthographic pod shell projection remains explicitly unsupported rather than inferred.",
            "A GO outcome means the narrow v0.1 execution criteria in this pilot passed; it does not by itself prove broad product-market advantage.",
        ],
    }
    evidence["evidence_hash"] = _json_hash({k: v for k, v in evidence.items() if k != "evidence_hash"})
    return evidence


def write_evidence(output_dir: Path | str) -> Tuple[Path, Path, Dict[str, Any]]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    evidence = run_pilot(output_root)
    json_path = output_root / "pod_designer_v01_pilot_evidence.json"
    summary_path = output_root / "pod_designer_v01_pilot_summary.txt"

    json_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    failed = [name for name, passed in evidence["criteria"].items() if not passed]
    lines = [
        f"Pod Designer v0.1 runnable pilot: {evidence['outcome']}",
        f"Scenario: {evidence['scenario']['id']} v{evidence['scenario']['version']}",
        f"Semantic fingerprint: {evidence['determinism']['run_1_fingerprint']}",
        f"Evidence hash: {evidence['evidence_hash']}",
        "All criteria passed." if not failed else "Failed criteria: " + ", ".join(failed),
        "",
        "Evidence boundary:",
        "- GO/NO-GO is computed from this execution evidence, not from the unit-test count.",
        "- Exact/model-derived and unsupported quantities retain their provenance/status.",
        "- See the JSON artifact for operations, IDs, representations, measurements, limitations, and criteria.",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, summary_path, evidence
