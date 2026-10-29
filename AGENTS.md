# ArchForge Agent Operating Contract

This repository is developed by multiple AI agents and a human owner. The repository, not chat memory, is the source of truth.

## Source of truth
- `develop` is the integration branch.
- Before starting work, read the live `develop` HEAD, `ROADMAP.md`, open PRs, and open task issues.
- Never assume a previous chat or local state is current.
- Never reset, rewrite, force-push, or discard `develop` history.

## Product invariant: human-first ArchForge
ArchForge is a human-first visual design environment. AI is optional assistance, not the product, not the authoritative designer, and not a required execution layer.

The architectural direction is:

`manual UI -> shared commands -> authoritative Document -> derived views`

and, only when the user explicitly invokes AI:

`AI intent -> the same shared command semantics -> authoritative Document -> derived views`

Rules:
- A user must be able to perform the core design workflow without AI.
- The `Document` is the design source of truth. UI/view caches, previews, render state, and AI context must not become competing design models.
- A committed manual edit and the equivalent AI edit must converge on the same command semantics and authoritative state. Do not build a parallel AI mutation engine.
- Direct manipulation (selection, click/drag, handles/gizmos, Inspector/property edits) is core product work, not cosmetic UI work.
- Parametric/semantic objects are valuable, but do not describe them as Blender-like free-form modeling unless authoritative vertex/edge/face or equivalent free-form editing actually exists.
- The Pod Designer scenario is an integration proving ground, not the identity of the product.

## Work isolation
- Do not push feature work directly to `develop`.
- Every task uses a dedicated branch and PR.
- Re-check live `develop` before opening or merging a PR.
- If `develop` moved, reconcile on a fresh branch or otherwise prove the combined tree is green before merge.

## Architecture merit rule
- Architecture choices are decided by technical merit and product coherence, not by which agent proposed them.
- GPT must not defend a GPT-specific implementation when Gemini has a demonstrably better solution for the shared ArchForge product; GPT should adopt or reconcile to the better design.
- Gemini is expected to follow the same rule in the opposite direction.
- When two approaches disagree, compare them against existing contracts, regression evidence, maintainability, determinism, integration cost, and the current product milestone.
- Prefer one coherent ArchForge architecture over parallel GPT and Gemini implementations.
- If one approach is clearly better, converge on it. If neither is clearly better and the choice materially changes product semantics or architecture direction, escalate the minimum decision to the human owner.

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

For manual/AI equivalence work, regression evidence must compare authoritative state, not screenshots or similar-looking geometry. If the two entry points bypass one another, fix the pipeline rather than weakening the test.

## Truth and provenance
- Never present heuristic values as verified engineering results.
- Structural, mechanical, environmental, fabrication, code-compliance, cost, and safety claims must carry explicit provenance.
- AI approval of a design proposal means "apply the proposal", not "engineering verified".
- Preview geometry must not be described as fabrication geometry unless the fabrication gate actually proves it.
- Unsupported derived quantities must remain explicitly unsupported; never fill a missing engineering value with an LLM guess or an undocumented mathematical shortcut.

## Product focus
Until `ROADMAP.md` says otherwise, prioritize the First Human-Usable ArchForge milestone.

Prefer work that improves:
- one authoritative semantic/model state,
- direct manipulation and manual editing through shared commands,
- persistent semantic identity and dependencies,
- deterministic parametric edits,
- 2D/3D derivation from the same model,
- save/load determinism,
- undo/redo correctness,
- exact measurements derived from validated model/geometry,
- optional AI-to-command equivalence,
- an explicit path from semantic/parametric geometry toward free-form editing.

Do not add machine-readable logs, fingerprints, or headless AI pilot evidence whose sole purpose is to prove autonomous AI operation. Such evidence is justified only when it validates a user-facing/manual contract or a deterministic model invariant.

Defer broad feature expansion, generalized structural simulation, or new fabrication claims unless a queued issue directly advances the current milestone. Do not defer necessary human interaction work merely because mature CAD/BIM tools already contain similar interaction patterns.

## NO VALUES FROM MEMORY — NO FAKE DATA (owner, 2026-10-15, binding)
Owner, in his words: «ό,τι βάζεις θα είναι διασταυρωμένο με κανόνες· απαγορεύεται να γράφεις από μνήμης ή ψεύτικα στοιχεία … ο στόχος είναι επιθετικός: να φτιάξουμε ένα πρόγραμμα που μπορεί να πουληθεί και να είναι συνώνυμο της εμπιστοσύνης».
- **Forbidden:** writing any engineering, regulatory, product or price value (tables, limits, factors, sizes, supply categories, catalogue figures) from an agent's memory, or inventing data of any kind (example projects shown as real, test fixtures presented as real-world values, made-up sources).
- **Required:** every such value is cross-checked against a citable source — the standard/regulation (clause/table), the utility's or authority's published document, or the manufacturer's data sheet — and the code records that source next to the value (document, edition, table/clause, and the URL or file when there is one).
- **When a value cannot be verified now:** it does not enter results as a fact. Either it is a user setting with no hidden default, or it is shown as «μη επαληθευμένο — εισάγετε από …» and excluded from automatic decisions. The HANDOFF keeps the list of open verifications.
- Existing values written before this rule are audited under the same rule; until audited they are listed in the HANDOFF as unverified.
- Green tests never count as verification of a value.
- **Status of every rule** (`archforge/core/provenance.py`, owner 15/10): `VERIFIED` (cross-checked with a source in force — named with clause/table/URL) · `DESIGN_DEFAULT` (our choice, not a regulation) · `MANUFACTURER_DATA` (data sheet, entered by the user) · `ENGINEER_REVIEW` (needs a study) · `UNVERIFIED` (never shown as a technical requirement). A rule is not VERIFIED because it already exists in the code; a summary (AI or otherwise) of a standard is not the standard — VERIFIED needs the text of the clause in force.

## Owner's trust rules (2026-10-15)
Agreed with the owner after an honest review of where an AI agent cannot be trusted on its own:
- **Ask before deciding** anything that changes what the owner sees on screen (placement of tabs/panels/menus, new tools in the mouse menu) or what an engineer would sign (rules, limits, sizing). A small mockup or one question is enough; "ξεκίνα από όπου πιστεύεις" covers the order of work, not these decisions.
- **Engineering values from memory are not facts.** Any table value (supply sizes, ampacities, factors, code limits) must name its source and be marked «προς έλεγχο» until the owner or an engineer confirms it; list such values in the HANDOFF under «προς επιβεβαίωση».
- **Never change a test just to make it pass.** Changing an existing test is allowed only when the owner changed the contract it encodes; say which owner decision in the commit message.
- Say plainly what was not verified (Windows, real users, performance on a full house) instead of reporting green tests as proof.
- Prefer one branch at a time; when parallel work exists, write the integration contract in the HANDOFF instead of duplicating the feature.

## Material economy (owner, 2026-10-17, binding)
Owner: «πρέπει να υπάρχει η λογική της οικονομίας υλικών γενικά — αυτό είναι κανόνας».
- Every routing / layout the program proposes (conduits, cables, pipes, ducts, members, cuts) takes the arrangement with the
  least material that still meets the system's own rules: shared trees over separate runs, shortest path along the allowed
  zones, one cable per point only where the system needs it (e.g. Ethernet home runs).
- Where economy and a rule conflict, the rule wins and the extra material is shown with its reason.
- Quantities are always reported, so the economy can be checked.

- **Safety first (owner 17/10):** economy applies only after safety — above all seismic safety in Greece. Never pick
  the lighter solution if it fails a check («τι είναι καλύτερο, να γλιτώσεις 15 κυβικά ή να χάσεις το σπίτι;»):
  e.g. strip footings that keep every seismic resultant on the base win over cheaper pads that overturn.

## Scenario quality gate & shared tools (owner, 2026-10-17, binding)

**Full index of shared tools and libraries: `docs/TOOLBOX.md` (owner 28/10, binding for every agent with repo
access).** Libraries (objects, materials, wall types, joinery, luminaires, cabinets, prices) are tools too. Search the
index before writing a helper script, check, test house, material or object; use what exists, extend it instead of
copying it; whatever new tool or library item you need is saved in the repo, tested, and listed there in the same PR.

Every test scenario passes the full gate in `docs/scenarios/QUALITY_GATE.md` before the next one starts: all six
sections (design, statics, MEP, quote, program behaviour, visual), fix, rerun the WHOLE list, regression on earlier
scenarios. "Built without an exception" is never a pass. Reuse these instead of writing your own:

- `archforge/scenarios/gate.py` — the checks (`Gate(s, module, out).run()`), report `Sxx_REPORT.md` with PASS / FAIL /
  N/A and the findings history (FIXED / OPEN, files, commit). Build: `py scripts/build_scenarios.py 01`.
- `archforge/scenarios/render3d.py` — real 3D pictures without a GPU: the app's own 3D page (`pbr_page_html`) and scene
  (`pbr_viewport.scene_payload`) in headless Chromium; camera presets `top` / `dollhouse`. Look at the pictures.
- `archforge/scenarios/common.py` — scenario steps through the UI's own paths (walls, openings, levels, stairs,
  room use, «Κουζίνα/Μπάνιο εδώ», Library furniture, MEP point tools).
- `archforge/quantities/price_book.py` — the user's common price book (project prices override; never invents a
  price); `quote()['by_trade']` = totals per trade. Tests isolate it (`tests/conftest.py`).
- Plan: `plan_scene.wall_poche` (walls with both faces), `_declutter_labels` (MEP labels without overlap);
  `joinery.inside_sign(doc, wall, opening)` (an interior door opens into the room it serves);
  `interaction.next_name` (Greek numbered names); `SetRoomMetadata` (room name/use, one undo).
- Full suite in the cloud: `QTWEBENGINE_DISABLE_SANDBOX=1 QT_QPA_PLATFORM=offscreen python -m pytest -q` (~10 min).

## Human intervention threshold
Do not ask the human to choose routine implementation details. Escalate only when the answer would materially change product semantics, user-facing policy, safety, cost, or architecture direction and cannot be resolved from existing repository contracts.

The goal of this file is to let agents continue productively without requiring the owner to type "continue" between tasks while keeping the human-first product definition stable.

## Every check the user's way — in movement and in sight (owner rule, 29/10)
1. Movement: a user task is checked through what the human touches — menu / button / key, mouse drags and clicks a
   few pixels off the target at a realistic zoom — never through direct function calls or exact coordinates.
2. Sight: the result is checked as the human sees it — the plan / 3D on screen, the PDF page as an image, the status
   message — not only internal numbers.
3. Existing direct-call tests stay (fast, precise) but do not prove a task works; every command also needs a user-way
   check. Backlog: `scripts/toolbox/user_way_coverage.py`. Examples: `tests/test_section_line_user.py`,
   `scripts/user_drive/wall_face_check.py`.
