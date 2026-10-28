# Branches — τι σβήνεται χωρίς απώλεια (28/10/2026, develop `5afa949`)

> Εντολή ιδιοκτήτη: «να είσαι σίγουρος 100% ότι τα branches που σβήνεις είναι ολόκληρα, με τις ίδιες ακριβώς
> λειτουργίες, και όχι αποσπασματικά». Τα AI δεν σβήνουν branches· σβήνει ο ιδιοκτήτης με τις εντολές στο τέλος.
> Ξαναπαράγεται με `python scripts/toolbox/branch_audit.py` (docs/TOOLBOX.md).

## Μέθοδος (μόνο απόδειξη git, καμία εκτίμηση)

| Κατάσταση | Τι αποδεικνύει | Σβήνεται; |
|---|---|---|
| MERGED | Κάθε commit του branch **είναι** commit του develop (`merge-base --is-ancestor`). | Ναι |
| SAME_PATCH | Κάθε commit έχει στο develop commit με **ίδιο diff γραμμή-γραμμή** (`git cherry`), χωρίς δικά του merge commits. Διασταυρώθηκε και με `git log --cherry-pick`: 0 διαφορές. | Ναι |
| NO_NET_CHANGE | Τα τελικά αρχεία του branch είναι **byte-byte ίδια** με commit του develop (αλλαγή + αναίρεσή της). | Ναι |
| KEEP | Έστω ένα commit (ή merge) χωρίς ίδιο αντίγραφο στο develop. | **Όχι** χωρίς απόφαση ιδιοκτήτη |
| PROTECTED | develop, main, ανοιχτά PR και οι βάσεις τους, ενεργή εργασία. | **Όχι** |

Για τα KEEP / PROTECTED έτρεξαν επιπλέον **τα δικά τους τεστ πάνω στο σημερινό develop**
(`scripts/toolbox/branch_tests_on_develop.py`). Πράσινα = η συμπεριφορά υπάρχει ήδη, όχι ότι ο κώδικας είναι ίδιος·
γι' αυτό ούτε αυτά μπαίνουν στη λίστα διαγραφής χωρίς δικό σου «ναι».

## Αποτέλεσμα

**129 branches σβήνονται με απόδειξη** (116 MERGED, 12 SAME_PATCH, 1 NO_NET_CHANGE) · 16 KEEP · 14 PROTECTED.

## KEEP — πρόταση ανά branch (αποφασίζεις εσύ)

**Λείπει δουλειά από το develop (να μη χαθεί):**
- `feature/plumbing-rules-audit` (31 commits, 19 αρχεία): τα `mep/plumbing_assemblies.py`, `mep/plumbing_components.py`,
  `ui/mep_3d_visibility.py` **δεν υπάρχουν** στο develop. → Μεταφορά πάνω στο develop με τεστ, ή ρητό «δεν το θέλω».

**Τα τεστ τους περνούν στο develop: η συμπεριφορά υπάρχει ήδη** (πρόταση: κλείνουν· όσα είναι μόνο τεστ μπορούν πρώτα
να μπουν στο develop ως επιπλέον regression):
- `feature/preview-inferred-architecture` 3/3 · `feature/arboreal-surface-contract` 8/8 ·
  `gpt-issue-38-junction-consistency-v2` και `gpt/issue-38-junction-view-consistency` 1/1 (ίδιο τεστ, δύο αντίγραφα) ·
  `gpt/issue-68-rotated-ellipse-projection` 3/3 · `gpt/issue-76-pointer-move-transaction` 5/5 ·
  `gpt/issue-91-close-unsaved-guard` και `…-reconcile` 4/4 · `claude/charming-darwin-r9eunu` 10/10.

**Το develop άλλαξε συμβόλαιο από τότε** (τα τεστ ελέγχουν παλιά ονόματα/μορφή· πρόταση: κλείνουν):
- `feature/incremental-viewport-cache` 4/6: οι 2 αποτυχίες ψάχνουν ονόματα μεθόδων στο κείμενο του UI
  (`_update_interaction_proxies`, `_redraw_views`)· το develop έχει incremental cache με άλλη υλοποίηση.
- `feature/gemini-sculpt-transform-stability` 4/5: `KeyError 'world_center'` — το develop κρατά πια τα sculpt σε
  UV/τοπικές συντεταγμένες (`commands.py`, `_legacy_world_modifier`).
- `gpt/issue-96-smooth-sculpt-sampling` 11/12 (μόνο τεστ): το παράθυρο δεν έχει πια `view_3d`.
- `gpt/issue-100-view-menu-visibility` 0/1: ψάχνει μενού «View»· τα μενού είναι πια ελληνικά. Θέλει έλεγχο αν το
  μενού «Προβολή» έχει τους ίδιους διακόπτες ορατότητας πριν κλείσει.

**Παλιές σημειώσεις:** `claude/clever-einstein-8lalhs` (μία γραμμή HANDOFF «1679 passed»),
`codex/residential-s01-quality-gate` (σημείωμα συντονισμού για το PR #128) → κλείνουν.

## PROTECTED — ανοιχτά PR (από `docs/RELEASE_PLAN.md` §6)

| PR | Branch | Τεστ του πάνω στο develop | Τι λείπει από το develop |
|---|---|---|---|
| #163 | `claude/roof-under-upper-storey` | — (πράσινο CI) | στέγη U01/U02· περιμένει merge |
| #88 | `gpt/issue-64-runnable-pilot` | 4 errors | `VertexMoveTransaction`, `ApplyStructuralFrame`, `MutateEntityProperty` (ο `MEPPathRouter` υπάρχει ήδη) |
| #106 | `gpt/issue-103-roof-edge-offsets` | 2 errors | `core/roof_commands.py`, `core/roof_edge_transaction.py` |
| #114 | `gpt/issue-104-wall-top-endpoints` | 1 error | `wall_detail.opening_fits_wall_profile` (το `SetWallTopEndpoint` υπάρχει ήδη) |
| #122 | `codex/library-icons-material-transform` | 7 αποτυχίες, μετά κόλλησε (παράθυρο διαλόγου) | 611 commits πίσω· σχέδιο: ξαναχτίσιμο πάνω στο develop |
| #123 | `feature/material-browser-properties` | χωρίς τεστ | browser υλικών (patches 3/4) |
| #130 / #132 | `codex/s01-foundation-comparison`, `codex/s02-furnished-review` | 41 αποτυχίες / 10 περνούν | τα αρχεία-σενάρια δεν φορτώνουν (`railing_type` λείπει)· σχέδιο: μόνο κώδικας/τεστ |
| #112 | `docs/archforge-master-context` | — | `ARCHFORGE_MASTER_CONTEXT.md` δεν υπάρχει στο develop |

## Πλήρης πίνακας και εντολές διαγραφής

Σύνολο 159 · MERGED 116 · SAME_PATCH 12 · NO_NET_CHANGE 1 · KEEP 16 · PROTECTED 14

| Κατάσταση | Branch | Τελευταίο commit | Δικά του commits (χωρίς ίδιο αντίγραφο στο develop) |
|---|---|---|---|
| KEEP | `feature/gemini-sculpt-transform-stability` | 2026-09-14 `03215f3` | 1 Fix CRIT-03: preserve sculpt and cavity modifiers under MoveEntities with undo/redo support |
| KEEP | `feature/preview-inferred-architecture` | 2026-09-14 `3d09b52` | 2 Support all inferred room slabs in preview backend; Test preview parity for inferred house geometry |
| KEEP | `feature/arboreal-surface-contract` | 2026-09-15 `01e60a0` | 1 Prove arboreal mesh roles are registered semantic surfaces |
| KEEP | `gpt-issue-38-junction-consistency-v2` | 2026-09-15 `6079513` | 1 Add regression for junction-aware orthographic views |
| KEEP | `gpt/issue-38-junction-view-consistency` | 2026-09-15 `97fe2f7` | 1 Add regression for junction-aware orthographic views |
| KEEP | `feature/incremental-viewport-cache` | 2026-09-16 `e7b8e0c` | 10 Add RED regressions for incremental viewport synchronization; Implement entity-granular incremental evaluation cache; Use indexed opening and modifier lookups in evaluation plans … |
| KEEP | `gpt/issue-68-rotated-ellipse-projection` | 2026-09-21 `bb20b94` | 8 test: require exact rotated ellipse junction projection; feat: support rotated ellipse orthographic junction clipping; fix: preserve axis-aligned ellipse projection boundary … |
| KEEP | `gpt/issue-76-pointer-move-transaction` | 2026-09-22 `d34882d` | 2 test(viewport): require pointer move to use MoveTransaction; refactor(viewport): route pointer move through MoveTransaction |
| KEEP | `gpt/issue-91-close-unsaved-guard` | 2026-09-24 `c7f9216` | 10 test(ui): guard application close with unsaved edits; fix(ui): guard application close with unsaved edits; test(ui): keep QApplication alive in close guard regressions … |
| KEEP | `gpt/issue-91-close-unsaved-guard-reconcile` | 2026-09-25 `52b7662` | 1 fix(ui): guard application close with unsaved edits |
| KEEP | `gpt/issue-100-view-menu-visibility` | 2026-09-26 `54219b9` | 4 feat(ui): add real View visibility controls; test(ui): cover View visibility controls; test(ui): exercise View actions through user trigger path … |
| KEEP | `gpt/issue-96-smooth-sculpt-sampling` | 2026-09-26 `3aff28f` | 2 test(sculpt): follow current sampling contract; test(sculpt): align dense preview with sampling constant |
| KEEP | `claude/clever-einstein-8lalhs` | 2026-10-15 `9476664` | 1 HANDOFF: πλήρης σουίτα 1679 passed μετά τις μονώσεις και το κέλυφος |
| KEEP | `codex/residential-s01-quality-gate` | 2026-10-17 `4b9b5bf` | 1 Σημείωμα συντονισμού από τον Claude: το branch ενώθηκε στο PR #128 — μία πύλη, ρόλοι |
| KEEP | `feature/plumbing-rules-audit` | 2026-10-17 `9178195` | 31 Resolve legacy hidden MEP layers against authoritative workspace; Make Layers workspace authoritative for 3D MEP visibility; Test authoritative Layers visibility for 3D MEP … |
| KEEP | `claude/charming-darwin-r9eunu` | 2026-10-18 `5e0496a` | 1 Σενάρια S01–S10 με εργαλείο στέγης, πίνακες και σωληνώσεις· κουτί διέλευσης αντί για μεγαλύτερο σωλήνα όταν φταίνε οι καμπύλες· μία παροχή θέρμανσης στον χώρο του λέβητα |
| PROTECTED | `main` | 2026-09-20 `8b44c71` | 0  |
| PROTECTED | `gpt/issue-64-runnable-pilot` | 2026-09-23 `39625b4` | 84 core: add authoritative mesh schema validators; core: reactive CommandStack and FreezeToMesh bridge; geometry: expose reactive cache invalidation … |
| PROTECTED | `docs/archforge-master-context` | 2026-09-26 `9700271` | 4 docs: add authoritative ArchForge master context; docs: point agents to master context; docs: align roadmap with master context … |
| PROTECTED | `gpt/issue-103-roof-edge-offsets` | 2026-09-28 `9417a79` | 4 fix(roof): make edge offsets exactly reversible; test(roof): exercise semantic edge offset command; feat(roof): add semantic edge drag transaction … |
| PROTECTED | `gpt/issue-104-wall-top-endpoints` | 2026-09-28 `2d83bae` | 55 feat(wall): derive plain wall mesh from endpoint top heights; test(wall): lock endpoint-specific sloped top contract; feat(wall): validate openings against local sloped top … |
| PROTECTED | `integration/pbr-salvage-test` | 2026-09-28 `298d4de` | 0  |
| PROTECTED | `integration/mockup-shell-on-14` | 2026-10-02 `e95055b` | 0  |
| PROTECTED | `codex/library-icons-material-transform` | 2026-10-14 `928f81e` | 1 Add visual library, component finishes, surface eyedropper and transform controls |
| PROTECTED | `feature/material-browser-properties` | 2026-10-14 `bf97f2a` | 3 feat(materials): add visual material browser linked to object selection; feat(materials): wire material browser into ArchForge runtime; Expand material browser with properties integration and per-surface targets |
| PROTECTED | `gpt/fix-empty-frame-storey` | 2026-10-14 `20dc9b2` | 0  |
| PROTECTED | `codex/s01-foundation-comparison` | 2026-10-18 `73b118a` | 3 Add visually inspected S01 foundation option comparison; Replace S01 commercial quote requirement with unpriced materials by work; Export surfaces and unpriced materials for all ten residential review files |
| PROTECTED | `codex/s02-furnished-review` | 2026-10-18 `b8867a9` | 6 Add visually inspected S01 foundation option comparison; Replace S01 commercial quote requirement with unpriced materials by work; Export surfaces and unpriced materials for all ten residential review files … |
| PROTECTED | `claude/roof-under-upper-storey` | 2026-10-28 `a2d1e35` | 2 Στέγη κάτω ορόφου: σταματά στον τοίχο του πάνω ορόφου, κάθεται στα δοκάρια (U01, U02 — αρχείο ιδιοκτήτη «…111»); merge a2d1e35 (δεν ελέγχεται με patch-id) |
| PROTECTED | `develop` | 2026-10-28 `5afa949` | 0  |
| NO_NET_CHANGE | `gpt/issue-102-display-palette` | 2026-09-26 `c897ec6` | 2 feat(ui): add viewport display settings palette; chore: revert incomplete display palette spike |
| SAME_PATCH | `feature/foundation-identity-regressions` | 2026-09-14 `294ef76` | 0  |
| SAME_PATCH | `feature/room-preview-dormancy` | 2026-09-14 `865ebf1` | 0  |
| SAME_PATCH | `feature/room-preview-dormancy-v2` | 2026-09-14 `cf97515` | 0  |
| SAME_PATCH | `feature/arboreal-persistent-branches` | 2026-09-15 `2130af7` | 0  |
| SAME_PATCH | `feature/biospectre-true-3d-overlap` | 2026-09-15 `159cea4` | 0  |
| SAME_PATCH | `feature/issue-42-ai-execution-contract` | 2026-09-15 `eaef83d` | 0  |
| SAME_PATCH | `ops/architecture-merit-rule` | 2026-09-15 `5d9b77b` | 0  |
| SAME_PATCH | `ops/autonomous-agent-pilot-v2` | 2026-09-15 `bc9d849` | 0  |
| SAME_PATCH | `test/issue-60-v01-acceptance` | 2026-09-20 `9cde841` | 0  |
| SAME_PATCH | `feat/issue-70-clipped-net-footprint-area` | 2026-09-21 `e52c624` | 0  |
| SAME_PATCH | `feat/issue-74-manual-ai-pipeline-equivalence` | 2026-09-22 `3e49a80` | 0  |
| SAME_PATCH | `gpt/issue-102-pbr-display-palette` | 2026-09-27 `298f371` | 0  |
| MERGED | `feature/automatic-house-intent` | 2026-09-14 `29e1039` | 0  |
| MERGED | `feature/embedded-mechanism-cavities` | 2026-09-14 `7b8ea61` | 0  |
| MERGED | `feature/end-to-end-sculpt-start` | 2026-09-14 `e5c117d` | 0  |
| MERGED | `feature/fabrication-empty-scope-gate` | 2026-09-14 `25627eb` | 0  |
| MERGED | `feature/fabrication-interbody-duplicates` | 2026-09-14 `4fe731c` | 0  |
| MERGED | `feature/foundation-hardening-after-pr5` | 2026-09-14 `7e0a447` | 0  |
| MERGED | `feature/geometry-evaluation-plan` | 2026-09-14 `7dc2b16` | 0  |
| MERGED | `feature/kinematic-evaluation` | 2026-09-14 `83b1dfd` | 0  |
| MERGED | `feature/local-wall-sculpt-resolution` | 2026-09-14 `126660e` | 0  |
| MERGED | `feature/mechanical-foundation` | 2026-09-14 `cc25c9c` | 0  |
| MERGED | `feature/mesh-coincident-face-validation` | 2026-09-14 `dc2d2e6` | 0  |
| MERGED | `feature/mesh-fabrication-validation` | 2026-09-14 `271ef75` | 0  |
| MERGED | `feature/pod-junction-vertical-overlap` | 2026-09-14 `1d32d6b` | 0  |
| MERGED | `feature/preview-inferred-architecture-v2` | 2026-09-14 `8337d0b` | 0  |
| MERGED | `feature/room-identity-collinear-split` | 2026-09-14 `1e9bc79` | 0  |
| MERGED | `feature/room-preview-dormancy-final` | 2026-09-14 `83dd235` | 0  |
| MERGED | `feature/sculpt-mesh-chain` | 2026-09-14 `470ade2` | 0  |
| MERGED | `feature/sculpt-ops-expansion` | 2026-09-14 `e6debb2` | 0  |
| MERGED | `feature/stl-export-payload-hardening` | 2026-09-14 `056ce2c` | 0  |
| MERGED | `feature/surface-backend-contract` | 2026-09-14 `e3718b5` | 0  |
| MERGED | `feature/tessellated-preview` | 2026-09-14 `1263580` | 0  |
| MERGED | `feature/validated-fabrication-mesh` | 2026-09-14 `1d5f5f7` | 0  |
| MERGED | `feature/30-edit-parametric-stress-test` | 2026-09-15 `3e33d14` | 0  |
| MERGED | `feature/ai-proposal-validation-provenance` | 2026-09-15 `deddf99` | 0  |
| MERGED | `feature/ai-proposal-validation-provenance-2` | 2026-09-15 `37d993e` | 0  |
| MERGED | `feature/ai-proposal-validation-provenance-red` | 2026-09-15 `37d993e` | 0  |
| MERGED | `feature/arboreal-command-undo` | 2026-09-15 `5ca08bf` | 0  |
| MERGED | `feature/arboreal-fast-preview` | 2026-09-15 `7b55657` | 0  |
| MERGED | `feature/arboreal-mount-deletion-lifecycle` | 2026-09-15 `41498b0` | 0  |
| MERGED | `feature/arboreal-mounted-pod-follow` | 2026-09-15 `edfce51` | 0  |
| MERGED | `feature/arboreal-persistent-branches-v2` | 2026-09-15 `32e1c58` | 0  |
| MERGED | `feature/arboreal-surface-contract-v2` | 2026-09-15 `e8f0bb5` | 0  |
| MERGED | `feature/biospectre-bounded-junction-clipping` | 2026-09-15 `16a274a` | 0  |
| MERGED | `feature/biospectre-rotated-junctions` | 2026-09-15 `b5e5cea` | 0  |
| MERGED | `feature/biospectre-shell-clipping` | 2026-09-15 `d9884dc` | 0  |
| MERGED | `feature/biospectre-true-3d-overlap-v2` | 2026-09-15 `c8f3565` | 0  |
| MERGED | `feature/building-envelope-storeys` | 2026-09-15 `edd8cea` | 0  |
| MERGED | `feature/fabrication-openings-regression` | 2026-09-15 `f7401ce` | 0  |
| MERGED | `feature/fluid-organic-surface-frame` | 2026-09-15 `9eb645e` | 0  |
| MERGED | `feature/organic-junction-surfaces` | 2026-09-15 `0ac3cb8` | 0  |
| MERGED | `feature/organic-opening-junction-conflicts` | 2026-09-15 `5908519` | 0  |
| MERGED | `feature/organic-opening-junction-visibility` | 2026-09-15 `26bb64e` | 0  |
| MERGED | `feature/pod-flat-openings` | 2026-09-15 `b3605e0` | 0  |
| MERGED | `feature/pod-junction-plan-boundary` | 2026-09-15 `7ba49ad` | 0  |
| MERGED | `feature/pod-opening-lifecycle` | 2026-09-15 `917b5be` | 0  |
| MERGED | `feature/pod-opening-preview-voids` | 2026-09-15 `c098220` | 0  |
| MERGED | `feature/pod-opening-shell-flattening` | 2026-09-15 `7770900` | 0  |
| MERGED | `feature/shared-opening-host-topology` | 2026-09-15 `9f27957` | 0  |
| MERGED | `feature/transactional-delete-undo` | 2026-09-15 `a52fb31` | 0  |
| MERGED | `feature/wall-opening-conflict-validation` | 2026-09-15 `26ed492` | 0  |
| MERGED | `gpt/issue-38-junction-view-consistency-reconcile` | 2026-09-15 `86a264e` | 0  |
| MERGED | `gpt/p0-brep-solid-validity-gate` | 2026-09-15 `19fc857` | 0  |
| MERGED | `gpt/p0-brep-solid-validity-gate-v2` | 2026-09-15 `e6b6465` | 0  |
| MERGED | `ops/autonomous-agent-pilot` | 2026-09-15 `39f21b2` | 0  |
| MERGED | `feature/pod-measurements-provenance` | 2026-09-16 `6cc7854` | 0  |
| MERGED | `chore/pytest-ini-configuration` | 2026-09-20 `324a470` | 0  |
| MERGED | `feature/langgraph-multi-agent-orchestrator` | 2026-09-20 `f89bd03` | 0  |
| MERGED | `gpt/issue-60-v01-acceptance` | 2026-09-20 `28ed1d3` | 0  |
| MERGED | `ops/langgraph-github-action` | 2026-09-20 `308a81e` | 0  |
| MERGED | `test/issue-53-ai-30-edit-execution` | 2026-09-20 `2dd69e1` | 0  |
| MERGED | `test/issue-54-v01-acceptance-benchmarks` | 2026-09-20 `39ec66e` | 0  |
| MERGED | `gpt/issue-66-orthographic-junction-clipping` | 2026-09-21 `5e753b9` | 0  |
| MERGED | `gpt/issue-72-human-first-contract` | 2026-09-21 `19e407a` | 0  |
| MERGED | `gpt/issue-78-pointer-rotate-shared-command` | 2026-09-23 `82b64ee` | 0  |
| MERGED | `gpt/issue-80-direct-rotate-click-target` | 2026-09-23 `c128bb4` | 0  |
| MERGED | `gpt/issue-82-direct-move-click-target` | 2026-09-23 `db3a625` | 0  |
| MERGED | `gpt/issue-84-direct-stretch-click-target` | 2026-09-23 `70104bf` | 0  |
| MERGED | `gpt/issue-86-new-project-lifecycle` | 2026-09-23 `a71c079` | 0  |
| MERGED | `gpt/issue-89-unsaved-project-guard` | 2026-09-24 `78c0123` | 0  |
| MERGED | `gpt/issue-98-flat-roof-outer-footprint` | 2026-09-25 `13bacc1` | 0  |
| MERGED | `gpt/recovery-human-runnable` | 2026-09-25 `6196be1` | 0  |
| MERGED | `gpt/sculpt-flat-roof-pilot` | 2026-09-25 `dd2b15d` | 0  |
| MERGED | `gpt/issue-107-authoritative-pbr-preview` | 2026-09-26 `81cdd6d` | 0  |
| MERGED | `gpt/human-opening-structural-context` | 2026-09-28 `d50d023` | 0  |
| MERGED | `integration/pbr-stepwise` | 2026-09-28 `c6d5c10` | 0  |
| MERGED | `gpt/fix-structural-legacy-column-compat` | 2026-09-29 `b24251c` | 0  |
| MERGED | `gpt/issue-104-wall-top-on-working-salvage` | 2026-09-29 `254b8d2` | 0  |
| MERGED | `ai-panel-current` | 2026-10-03 `27443ee` | 0  |
| MERGED | `integration/mep-kitchen-isolated` | 2026-10-03 `27443ee` | 0  |
| MERGED | `claude/new-session-l1o9gl` | 2026-10-05 `6fec26f` | 0  |
| MERGED | `claude/new-session-hiekda` | 2026-10-08 `b7cad7a` | 0  |
| MERGED | `gpt/terrain-regions-basement` | 2026-10-11 `bcb3304` | 0  |
| MERGED | `claude/charming-keller-v3r9lm` | 2026-10-14 `0ed657d` | 0  |
| MERGED | `claude/eager-mccarthy-cl2wgn` | 2026-10-14 `22e5f65` | 0  |
| MERGED | `claude/festive-tesla-dqdcxi` | 2026-10-14 `c5d4d4f` | 0  |
| MERGED | `claude/gracious-goldberg-xoia25` | 2026-10-14 `81a57aa` | 0  |
| MERGED | `claude/happy-einstein-l2xl3i` | 2026-10-14 `fb2095e` | 0  |
| MERGED | `claude/peaceful-babbage-uzo71b` | 2026-10-14 `704272b` | 0  |
| MERGED | `claude/serene-johnson-t64vsi` | 2026-10-14 `03dc320` | 0  |
| MERGED | `claude/trusting-allen-fndrfd` | 2026-10-14 `044285d` | 0  |
| MERGED | `claude/upbeat-cray-7mtdeo` | 2026-10-14 `d915284` | 0  |
| MERGED | `claude/confident-volta-zn2tpd` | 2026-10-15 `839d80a` | 0  |
| MERGED | `feature/material-library-from-22a0f8b` | 2026-10-15 `3a7deac` | 0  |
| MERGED | `claude/funny-ride-f05bva` | 2026-10-17 `f27c2dd` | 0  |
| MERGED | `claude/practical-cannon-jebioi` | 2026-10-17 `d18431e` | 0  |
| MERGED | `integration/plumbing-validated-on-develop` | 2026-10-17 `ae377f6` | 0  |
| MERGED | `merge/plumbing-validated-2026-10-17` | 2026-10-17 `026302b` | 0  |
| MERGED | `test/residential-scenario-suite` | 2026-10-17 `4b18ae7` | 0  |
| MERGED | `fix/slab-edge-face-materials` | 2026-10-18 `b143710` | 0  |
| MERGED | `claude/nifty-gates-yed5je` | 2026-10-21 `ec386c2` | 0  |
| MERGED | `claude/affectionate-goodall-xnag99` | 2026-10-23 `7f13959` | 0  |
| MERGED | `claude/great-cori-7javsh` | 2026-10-23 `b0093a2` | 0  |
| MERGED | `claude/zen-goodall-6nu73o` | 2026-10-23 `f6c2983` | 0  |
| MERGED | `codex/joinery-design-library` | 2026-10-23 `ea50427` | 0  |
| MERGED | `claude/peaceful-fermi-k1kuc9` | 2026-10-24 `dc52b5a` | 0  |
| MERGED | `codex/conduit-fill-30` | 2026-10-24 `46b5ee4` | 0  |
| MERGED | `codex/electrical-bom-comparison` | 2026-10-24 `dad313d` | 0  |
| MERGED | `codex/electrical-conduit-display` | 2026-10-24 `8bc8c1d` | 0  |
| MERGED | `codex/electrical-routing-ceiling` | 2026-10-24 `a35e5dd` | 0  |
| MERGED | `claude/sleepy-bell-me939s` | 2026-10-25 `813b4c2` | 0  |
| MERGED | `codex/lighting-content-integration` | 2026-10-25 `84dc0a9` | 0  |
| MERGED | `feature/library-active-luminaires` | 2026-10-25 `432233b` | 0  |
| MERGED | `claude/complete-building-differential` | 2026-10-28 `0ae27e9` | 0  |
| MERGED | `claude/image-materials` | 2026-10-28 `0a8e8c5` | 0  |
| MERGED | `claude/kind-cannon-nvcs2f` | 2026-10-28 `28692db` | 0  |
| MERGED | `claude/move-atomic-undo` | 2026-10-28 `1aa68fd` | 0  |

Εντολή διαγραφής (129 branches, μόνο MERGED, SAME_PATCH, NO_NET_CHANGE):

```
git push origin --delete gpt/issue-102-display-palette
git push origin --delete feature/foundation-identity-regressions
git push origin --delete feature/room-preview-dormancy
git push origin --delete feature/room-preview-dormancy-v2
git push origin --delete feature/arboreal-persistent-branches
git push origin --delete feature/biospectre-true-3d-overlap
git push origin --delete feature/issue-42-ai-execution-contract
git push origin --delete ops/architecture-merit-rule
git push origin --delete ops/autonomous-agent-pilot-v2
git push origin --delete test/issue-60-v01-acceptance
git push origin --delete feat/issue-70-clipped-net-footprint-area
git push origin --delete feat/issue-74-manual-ai-pipeline-equivalence
git push origin --delete gpt/issue-102-pbr-display-palette
git push origin --delete feature/automatic-house-intent
git push origin --delete feature/embedded-mechanism-cavities
git push origin --delete feature/end-to-end-sculpt-start
git push origin --delete feature/fabrication-empty-scope-gate
git push origin --delete feature/fabrication-interbody-duplicates
git push origin --delete feature/foundation-hardening-after-pr5
git push origin --delete feature/geometry-evaluation-plan
git push origin --delete feature/kinematic-evaluation
git push origin --delete feature/local-wall-sculpt-resolution
git push origin --delete feature/mechanical-foundation
git push origin --delete feature/mesh-coincident-face-validation
git push origin --delete feature/mesh-fabrication-validation
git push origin --delete feature/pod-junction-vertical-overlap
git push origin --delete feature/preview-inferred-architecture-v2
git push origin --delete feature/room-identity-collinear-split
git push origin --delete feature/room-preview-dormancy-final
git push origin --delete feature/sculpt-mesh-chain
git push origin --delete feature/sculpt-ops-expansion
git push origin --delete feature/stl-export-payload-hardening
git push origin --delete feature/surface-backend-contract
git push origin --delete feature/tessellated-preview
git push origin --delete feature/validated-fabrication-mesh
git push origin --delete feature/30-edit-parametric-stress-test
git push origin --delete feature/ai-proposal-validation-provenance
git push origin --delete feature/ai-proposal-validation-provenance-2
git push origin --delete feature/ai-proposal-validation-provenance-red
git push origin --delete feature/arboreal-command-undo
git push origin --delete feature/arboreal-fast-preview
git push origin --delete feature/arboreal-mount-deletion-lifecycle
git push origin --delete feature/arboreal-mounted-pod-follow
git push origin --delete feature/arboreal-persistent-branches-v2
git push origin --delete feature/arboreal-surface-contract-v2
git push origin --delete feature/biospectre-bounded-junction-clipping
git push origin --delete feature/biospectre-rotated-junctions
git push origin --delete feature/biospectre-shell-clipping
git push origin --delete feature/biospectre-true-3d-overlap-v2
git push origin --delete feature/building-envelope-storeys
git push origin --delete feature/fabrication-openings-regression
git push origin --delete feature/fluid-organic-surface-frame
git push origin --delete feature/organic-junction-surfaces
git push origin --delete feature/organic-opening-junction-conflicts
git push origin --delete feature/organic-opening-junction-visibility
git push origin --delete feature/pod-flat-openings
git push origin --delete feature/pod-junction-plan-boundary
git push origin --delete feature/pod-opening-lifecycle
git push origin --delete feature/pod-opening-preview-voids
git push origin --delete feature/pod-opening-shell-flattening
git push origin --delete feature/shared-opening-host-topology
git push origin --delete feature/transactional-delete-undo
git push origin --delete feature/wall-opening-conflict-validation
git push origin --delete gpt/issue-38-junction-view-consistency-reconcile
git push origin --delete gpt/p0-brep-solid-validity-gate
git push origin --delete gpt/p0-brep-solid-validity-gate-v2
git push origin --delete ops/autonomous-agent-pilot
git push origin --delete feature/pod-measurements-provenance
git push origin --delete chore/pytest-ini-configuration
git push origin --delete feature/langgraph-multi-agent-orchestrator
git push origin --delete gpt/issue-60-v01-acceptance
git push origin --delete ops/langgraph-github-action
git push origin --delete test/issue-53-ai-30-edit-execution
git push origin --delete test/issue-54-v01-acceptance-benchmarks
git push origin --delete gpt/issue-66-orthographic-junction-clipping
git push origin --delete gpt/issue-72-human-first-contract
git push origin --delete gpt/issue-78-pointer-rotate-shared-command
git push origin --delete gpt/issue-80-direct-rotate-click-target
git push origin --delete gpt/issue-82-direct-move-click-target
git push origin --delete gpt/issue-84-direct-stretch-click-target
git push origin --delete gpt/issue-86-new-project-lifecycle
git push origin --delete gpt/issue-89-unsaved-project-guard
git push origin --delete gpt/issue-98-flat-roof-outer-footprint
git push origin --delete gpt/recovery-human-runnable
git push origin --delete gpt/sculpt-flat-roof-pilot
git push origin --delete gpt/issue-107-authoritative-pbr-preview
git push origin --delete gpt/human-opening-structural-context
git push origin --delete integration/pbr-stepwise
git push origin --delete gpt/fix-structural-legacy-column-compat
git push origin --delete gpt/issue-104-wall-top-on-working-salvage
git push origin --delete ai-panel-current
git push origin --delete integration/mep-kitchen-isolated
git push origin --delete claude/new-session-l1o9gl
git push origin --delete claude/new-session-hiekda
git push origin --delete gpt/terrain-regions-basement
git push origin --delete claude/charming-keller-v3r9lm
git push origin --delete claude/eager-mccarthy-cl2wgn
git push origin --delete claude/festive-tesla-dqdcxi
git push origin --delete claude/gracious-goldberg-xoia25
git push origin --delete claude/happy-einstein-l2xl3i
git push origin --delete claude/peaceful-babbage-uzo71b
git push origin --delete claude/serene-johnson-t64vsi
git push origin --delete claude/trusting-allen-fndrfd
git push origin --delete claude/upbeat-cray-7mtdeo
git push origin --delete claude/confident-volta-zn2tpd
git push origin --delete feature/material-library-from-22a0f8b
git push origin --delete claude/funny-ride-f05bva
git push origin --delete claude/practical-cannon-jebioi
git push origin --delete integration/plumbing-validated-on-develop
git push origin --delete merge/plumbing-validated-2026-10-17
git push origin --delete test/residential-scenario-suite
git push origin --delete fix/slab-edge-face-materials
git push origin --delete claude/nifty-gates-yed5je
git push origin --delete claude/affectionate-goodall-xnag99
git push origin --delete claude/great-cori-7javsh
git push origin --delete claude/zen-goodall-6nu73o
git push origin --delete codex/joinery-design-library
git push origin --delete claude/peaceful-fermi-k1kuc9
git push origin --delete codex/conduit-fill-30
git push origin --delete codex/electrical-bom-comparison
git push origin --delete codex/electrical-conduit-display
git push origin --delete codex/electrical-routing-ceiling
git push origin --delete claude/sleepy-bell-me939s
git push origin --delete codex/lighting-content-integration
git push origin --delete feature/library-active-luminaires
git push origin --delete claude/complete-building-differential
git push origin --delete claude/image-materials
git push origin --delete claude/kind-cannon-nvcs2f
git push origin --delete claude/move-atomic-undo
```
