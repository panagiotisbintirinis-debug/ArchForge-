# ArchForge Agent Operating Contract

This repository is developed by multiple AI agents and a human owner. The repository, not chat memory, is the source of truth.

## Source of truth
- `develop` is the integration branch.
- Before starting work, read the live `develop` HEAD, open PRs, and open task issues.
- Never assume a previous chat or local state is current.
- Never reset, rewrite, force-push, or discard `develop` history.

## Work isolation
- Do not push feature work directly to `develop`.
- Every task uses a dedicated branch and PR.
- Re-check live `develop` before opening or merging a PR.
- If `develop` moved, reconcile on a fresh branch or otherwise prove the combined tree is green before merge.

## Task queue protocol
GitHub Issues are the shared queue.

Issue title states:
- `[READY]` = unclaimed and safe for an agent to pick up.
- `[IN-PROGRESS][GPT]` = claimed by GPT.
- `[IN-PROGRESS][GEMINI]` = claimed by Gemini.
- `[NEEDS-HUMAN]` = blocked on a real product/policy decision.
- `[DONE]` = completed and merged; close the issue.

To claim a task, first re-read the issue and live `develop`, then atomically change its title from `[READY]` to `[IN-PROGRESS][<AGENT>]`. If the title has already changed, pick another task.

When work is merged, update the issue with the PR/merge SHA, change the title to `[DONE]`, and close it. If blocked by a genuine product decision, change the title to `[NEEDS-HUMAN]`, explain the minimum decision required, and stop only that task.

## Engineering workflow
For behavior-changing fixes, use regression-first development:
1. Add the smallest test that expresses the intended contract.
2. Run the full existing suite and confirm the new test fails for the intended reason while old tests remain green.
3. Implement the smallest coherent production fix.
4. Run full tests and compile checks.
5. Open a PR against live `develop`.
6. Require independent PR CI to pass.
7. Re-check live `develop` for races before merge.
8. Merge without rewriting history.
9. Verify post-merge CI on `develop`.

Do not treat green CI as proof of engineering truth. Tests only prove encoded contracts.

## Truth and provenance
- Never present heuristic values as verified engineering results.
- Structural, mechanical, environmental, fabrication, code-compliance, cost, and safety claims must carry explicit provenance.
- AI approval of a design proposal means "apply the proposal", not "engineering verified".
- Preview geometry must not be described as fabrication geometry unless the fabrication gate actually proves it.

## Product focus for the autonomy pilot
Until `ROADMAP.md` says otherwise, prioritize the Pod Designer v0.1 production milestone over broad new subsystems.

Prefer work that improves:
- persistent semantic identity and dependencies,
- deterministic parametric edits,
- 2D/3D consistency,
- openings and junction topology,
- save/load determinism,
- undo/redo correctness,
- exact measurements derived from geometry,
- automated multi-step edit robustness,
- clean AI-to-command execution contracts.

Defer broad feature expansion, generalized structural simulation, new fabrication claims, or UI imitation of mature CAD/BIM products unless a queued issue explicitly requires it.

## Human intervention threshold
Do not ask the human to choose routine implementation details. Escalate only when the answer would materially change product semantics, user-facing policy, safety, cost, or architecture direction and cannot be resolved from existing repository contracts.

The goal of this file is to let agents continue productively without requiring the owner to type "continue" between tasks.
