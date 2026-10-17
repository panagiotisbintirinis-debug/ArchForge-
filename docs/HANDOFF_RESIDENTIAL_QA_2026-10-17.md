# Residential QA handoff — 17 October 2026

Owner's execution order is binding: complete the current residential scenario,
inspect real UI images, correct failures, rerun its complete gate, then advance.
The uploaded PDF is phase two, after phase one and its corrections, not a replacement.

Repository: `panagiotisbintirinis-debug/ArchForge-`

Base: `test/residential-scenario-suite` at `4b18ae781b5af3a50b34c637a717a41aa3e0a842`.
Work branch: `codex/residential-s01-quality-gate`.
Draft PR: https://github.com/panagiotisbintirinis-debug/ArchForge-/pull/127
First fix commit: `78e3d9e6ce56782d1e2d300aa1e00c225cb43d2e`; later evidence/fixes in the same branch.
No merge has been performed. Do not overwrite other agents' branches.

## Actual fixes

- Reproduced S01 railing load failure; use `railings.default_params` with valid complete schema.
- Replaced generic main floor boxes with canonical storey slab commands; added a canonical U stair.
- Added real door/window hosts, room identities/names and core-library furniture/bathroom assets.
- Added the missing hot-water source; separated bathroom points from kitchen points.
- Fixed lower-storey attic ceiling candidates using actual upper-storey coverage.
- Fixed the related omission of the interstorey slab when a pitched roof is above two storeys.
- Aligned top-storey frame and pitched-roof eaves with actual wall-top elevations in the fixture.
- Unified canonical `price_list.entries` and legacy `trade_prices`/`prices` reads. Conflicting duplicate prices are an error; edits migrate formats and remain undoable.
- Fixture prices have explicit TEST_FIXTURE provenance; they are never market prices. Missing whole-project prices/quantities stay missing.
- Fixed capture of hidden nested 3D tabs and the fit-to-infinite-grid error. Capture both floors, actual PBR frames, Structural and three MEP plans, plus real UI selection/level switching/close/reopen.
- Added a renderer frame-export hook that captures the actual active WebGL technique; it does not create an alternate model/renderer.
- Reproduced an intermittent populated-project startup failure: initial pending scene invoked `setWalkMode` before `walkMode`/`walkKeys` initialisation. Drain pending scene state after the walking state is initialised.
- Fixed pipe-only plumbing presentation missing the actual `plumbing-label` role.
- Removed the carpet of drainage segment labels by presentation-only density grouping and the existing collision-managed annotation helper. No route, diameter, slope or quantity is changed.

## Current gate and limits

S01 remains **BLOCKED**; S02–S10 are not approved. Read the versioned
`tests/residential_scenarios/output/S01_REPORT.md` and raw `S01_EVIDENCE.json`.

The structural solver reports several `capacity_joints[].meets=False` at top/roof
nodes. Follow-up correction: the same six flags now reach the top-level warnings
with node, direction, elevation, ratio and explicit unverified/review wording.
Each raw joint entry also carries rule ID/status/source, comparison factor and
ENGINEER_REVIEW applicability. No exemption or section change is applied. They are software output under unverified/review rules, not proof of a
confirmed code violation. Do not waive them, invent a regulatory exception, or
resize members from memory merely to obtain a green test.

The current heating/HVAC module is inventory-only and explicitly does not supply
a hydraulic-network solver. The full network-continuity check cannot honestly be
reported PASS. Engineering verification and real construction pricing are not
provided by this fixture. Preserve all original rule provenance/status.

## Commands

From the repo root, with requirements installed:

```
python tests/residential_scenarios/generate_projects.py --scenario S01
python -m pytest tests/test_residential_scenarios_e2e.py tests/test_residential_scenario_gate.py tests/test_shared_pricebook_compat.py -q
python tests/residential_scenarios/capture_projects.py --scenario S01
python tests/residential_scenarios/audit_scenario.py --scenario S01
```

The final command deliberately exits nonzero for incomplete/failed checks.
Generating or running S02 requires S01's complete recorded gate to be PASS.
Screenshots alone and the narrow pipeline pytest do not approve a scenario.
UI evidence carries the exact project file hash, so regenerating a different
project invalidates old UI evidence.

On Linux the capture needs a functioning graphical/WebGL environment. In this
container real Qt windows were run under Xvfb with Mesa and their actual WebGL
frames exported. Blank/uninitialised images are rejected. The separate Windows
Actions workflow captures through the shipped UI, then uploads diagnostic files
even when the full gate fails.

The monolithic Linux pytest run exhausted the container's memory. Verification
was repeated in bounded worker batches to release Qt/OCP state. See VALIDATION.md
for exact completed results and runner/shutdown limitations; never describe a
partial run as a complete green suite.

## Phase two

Unmodified source: `tests/residential_scenarios/phase2/owner_stress_scenarios.pdf`.
Execution order and trust requirements: `phase2/README.md`.
Status: QUEUED, not executed. Its numeric expectations must be checked against
primary engineering/manufacturer sources before they become verified rules.

## Follow-up: unresolved checks investigated, 17 October

The owner asked that remaining issues be investigated and fixed rather than just
listed. Reproduced the missing joint diagnostics with a failing regression before
fixing the analysis summary. All six raw numerical flags remain unchanged.
The complete scenario audit remains BLOCKED, now also explicitly failing the
no-warnings check: surfacing warnings is not resolving the underlying applicability.

Source investigated: European Commission JRC, *Eurocode 8: Seismic Design of
Buildings*, 2012, chapter 3, Fardis and Tsionis, printed p.61 (PDF p.74), section
3.4.4:
https://eurocodes.jrc.ec.europa.eu/sites/default/files/2022-06/EC8_Seismic_Design_of_Buildings-Worked_examples.pdf
This is primary authored training/worked-example material, not the normative
standard or the Greek National Annex. It explicitly depends on structural-system
classification and its particular example. It does not establish a top-node
exemption for S01. No rule status was promoted to VERIFIED from this report.
Still needed: applicable normative edition/clauses and National Annex, verified
applicability for the actual frame, and validation of capacities/actions.

Heating investigation: archforge/mep/heating.py currently reads only authored
points/zones and optional entered lengths. It has no pipe graph, source-to-emitter
connections, supply/return model or hydraulic calculation. S01 contains no heating
entities. Adding an automatic heat/pump/pipe design to clear this check would
require a genuine user-editable model/UI and verified project/method/manufacturer
inputs. No hidden fixture-only network or invented engineering sizing was added.
This check is still unsupported, rather than a skipped test of an existing solver.

The delivered .archforge geometry/state remains byte-identical. The fix is in the
application analysis code; opening the project in an older application does not
install this fix. Updated diagnostics require the PR branch version.
