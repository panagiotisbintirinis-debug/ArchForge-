# S01 validation checkpoint — 17 October 2026

## Software regressions

The final collection contains **1,757 cases in 224 test files**. All cases were
covered by passing isolated worker runs, with the final drainage/fixture changes
rechecked in the focused 14-case drainage/scenario run. The 26-case shared-prices,
fixture, plumbing-display and rendering run also passed. Compilation passed.

This is not a claim that the monolithic pytest process completed successfully.
That attempt was killed by the container's memory limit. Bounded workers were used
to release Qt/OCP state between groups. One incomplete worker log was rejected and
all ten files were rerun individually (31 cases). The last four groups recorded
75, 51, 72 and 34 successful case outcomes. Qt native teardown can hang after the
test summary in this container; those workers retained pytest's exact case/exit
status and used a scratch-only process-exit hook after pytest unconfiguration.
The hook never skips a case or changes a failing pytest status to success. This
runner limitation remains explicit; it is not evidence of clean application exit
under every platform/runtime combination.

The newly added regressions were observed failing before the corresponding fixes:
missing hot-water source, wrong-storey attic candidates, missing stair/access
workflows, competing price-book representations, plumbing-label noise and drainage
annotation collisions. The actual populated-project WebEngine startup failure was
also captured before moving pending-scene application past walk-state setup.

## Actual UI evidence

Eight images were produced by the shipped MainWindow/PlanView/PBRViewport path:
ground plan, upper plan, exterior PBR, dollhouse interior, Structural, plumbing,
drainage and electrical. All were opened and visually inspected. Plans are native
Qt widget captures. 3D images are frames exported from the actual running WebGL
renderer with the active application camera/materials; no alternate renderer or
fabricated building image is used.

The real Qt UI was driven to double-click select furniture, change floor through
the floor selector, save, close the window and reopen through a fresh MainWindow.
Shared-command checks separately cover move/edit/system changes/delete/undo/redo,
save/load and protection of the other trade's entities. UI evidence is tied to the
exact project-file SHA-256. Final image inspection is recorded in
`output/S01_VISUAL_REVIEW.json`.

## Windows CI

On commit `78e3d9e6ce56782d1e2d300aa1e00c225cb43d2e`, Windows dependency installation,
fixture generation, compilation and targeted regression checks succeeded. Actual
WebGL capture failed because the runner's Microsoft Basic Render Driver was
blocklisted; the capture correctly refused an empty image. Report writing also
exposed Windows' cp1252 default encoding. Explicit UTF-8 report I/O and the CI
GPU-blocklist override were added. Their subsequent CI result must be read from
PR #127; Linux results must not be relabelled as Windows UI validation.

## Full gate remains BLOCKED

- Six top-storey/roof capacity-joint entries report `meets=False` although the
  solver's top-level warning list is empty. They are recorded as failures to
  examine, with the original unverified/review provenance. No regulatory waiver
  or member resizing has been invented to make them green.
- The current heating/HVAC module is inventory-only; a heating-network continuity
  solver is not implemented. That requested check remains NOT_TESTED.
- Structural/MEP engineering verification and a real fully priced construction
  offer are not provided by software fixtures. Unknown prices/study quantities
  remain explicit. The fixture's entered prices are synthetic TEST_FIXTURE data.

Read `output/S01_REPORT.md` and `output/S01_EVIDENCE.json` for the exact checklist.
S02–S10 and every phase-two PDF case remain unapproved/unexecuted by this gate.
No merge has been performed.
