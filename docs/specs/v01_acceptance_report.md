# Pod Designer v0.1 Acceptance & Go/No-Go Evaluation Report

## Milestone Context
In accordance with `ROADMAP.md`, milestone **AI-native Pod Designer v0.1** is the go/no-go evaluation test for whether ArchForge provides deterministic value beyond general AI chat plus conventional CAD tools.

Core claim:
> AI proposes and operates. ArchForge preserves geometric and semantic truth.

## Evidence Layers
The milestone now has two distinct evidence layers:

1. **Automated contract/regression tests** prove encoded behaviors remain stable.
2. **Runnable pilot evidence** executes the real typed AI command contract, writes inspectable machine-readable evidence, and derives GO/NO-GO from the execution results rather than from the test count.

The runnable pilot is:

```bash
python scripts/run_pod_designer_v01_pilot.py --output-dir pilot_artifacts/v01
```

It writes:
- `pod_designer_v01_pilot_evidence.json`
- `pod_designer_v01_pilot_summary.txt`
- two saved `.archforge` project runs used for persistence/replay evidence

The pilot performs semantic mutations only through `ArchForgeAIClient.execute_action()`. View and geometry backends are inspected only as derived evidence.

## Scenario Execution Summary
The established acceptance scenarios (`tests/test_issue_60_acceptance.py`, `tests/test_v01_acceptance_and_benchmarks.py`, and `tests/test_ai_autonomous_30_edits.py`) remain regression evidence for the milestone contract.

The new runnable pilot independently exercises:
- three pods with deterministic source IDs,
- inferred junctions and opening patches,
- openings,
- move/resize/rotate,
- undo/redo,
- save/load into a fresh client,
- exact and unsupported measurements,
- 2D plan / orthographic / fast-preview / tessellated-preview observations,
- idempotent inference,
- canonical semantic replay fingerprinting.

### Required Capabilities Verification Matrix

| Requirement | Description | Status | Evidence / Implementation |
|---|---|---|---|
| **1. Persistent IDs** | Create multiple pods with persistent IDs surviving lifecycle operations. | **PASS** | Source objects use stable IDs; runtime IDs are recorded and verified unchanged across save/load. |
| **2. Shared Planar Junctions** | Join pods with shared planar junctions; remove overlapping shell portions consistently. | **PASS** | `infer_junctions` creates persistent semantic junction entities and plan view exposes clipped pod boundaries plus junction primitives. |
| **3. Opening Lifecycle** | Add, move, resize, and delete pod openings without floating patches or stale relationships. | **PASS** | Typed opening actions preserve host relationships and derived opening-patch inference is checked for idempotence. |
| **4. Relationship Integrity** | Preserve parent/dependent relationships through parameter edits. | **PASS** | Canonical pilot state includes parent/child and dependency edges and is fingerprinted before/after persistence. |
| **5. Dynamic Synchronization** | Keep mounted/derived objects synchronized when parents move or change shape. | **PASS** | Reconciliation is rerun after pod edits and the resulting semantic/view evidence is inspected. |
| **6. Exact State Restoration** | Undo/redo returns the semantic model to the exact previous state. | **PASS** | Pilot records the moved coordinate, verifies undo restores the exact prior value, and redo restores the exact moved value. |
| **7. Persistence Determinism** | Save -> close -> load preserves entity IDs, relationships, parameters, and geometry. | **PASS** | Pilot saves, loads into a fresh client, then compares canonical semantic state, fingerprint, and actual runtime entity IDs. |
| **8. Multi-View Coherence** | 2D plan, orthographic views, fast preview, and tessellated 3D express consistent topology; unsupported projections are explicitly flagged. | **PASS** | Pilot records plan/elevation roles and backend body presence. Junction-clipped pod elevation remains explicitly marked `junction_projection=unsupported` instead of being guessed. |
| **9. Model-Derived Measurements** | Areas, volumes, and lengths derived from geometry with provenance, never invented by AI. | **PASS** | Pilot requires `floor_footprint_area` to be `exact` with unit/method and `fabrication_shell_area` to be `unsupported` with no invented value. |
| **10. Autonomous Edit Sequence** | Scripted sequence of >=30 meaningful AI-style edits without semantic corruption or topology drift. | **PASS** | Existing 35-step regression remains the explicit stress-test evidence; the runnable pilot complements it with human/machine-readable execution evidence. |

### Determinism and Identity Boundary
Auto-inferred junction and opening-patch entities currently receive runtime UUIDs. Those UUIDs are preserved across save/load, but independently repeated fresh runs need not allocate the same UUID strings.

Therefore the replay fingerprint is intentionally computed from **canonical semantic identity**:
- junctions are identified by their stable `junction_key`,
- opening patches are identified by the stable opening ID they derive from,
- source pod/opening IDs remain explicit and deterministic.

This distinction prevents random UUID allocation from being mistaken for semantic nondeterminism while still recording and checking the real runtime IDs for persistence.

## Go / No-Go Evaluation
The runnable pilot computes its own outcome from explicit execution criteria. It does **not** hard-code GO based on unit-test counts.

A pilot GO requires all of the following in the actual run:
- every typed command step succeeds,
- junction and opening-patch inference are idempotent,
- undo/redo restores exact values,
- save/load preserves canonical state and runtime IDs,
- repeated independent runs produce the same canonical semantic fingerprint,
- supported views/backends contain the expected model evidence,
- unsupported orthographic projection is explicitly marked unsupported,
- exact measurements carry value/unit/method,
- unsupported fabrication measurements remain value-less and unsupported.

If any criterion fails, the pilot returns **NO-GO** and exits non-zero.

## Evidence Boundary / Remaining Limitations
A successful pilot demonstrates the narrow v0.1 advantages that ArchForge is specifically intended to provide: persistent semantic state, deterministic command execution, reproducible semantic replay, exact state restoration, explicit measurement provenance, and inspectable derived representations.

It does **not** prove:
- structural engineering validity,
- building-code compliance,
- fabrication readiness of organic geometry,
- environmental or cost accuracy,
- safety certification,
- product-market fit or broad superiority over established CAD/BIM systems.

The most important current known representation limitation remains explicit: pod shells intersected by junctions do not yet have a junction-clipped orthographic shell projection. The system reports that projection as unsupported rather than fabricating a plausible result.
