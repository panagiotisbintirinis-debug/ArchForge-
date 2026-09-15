# ArchForge Product Roadmap

## Current product hypothesis
ArchForge should not try to beat general AI at architectural conversation. Its value is to give any capable AI a deterministic, persistent, inspectable design model that survives repeated edits and can be measured and validated.

The core product claim is:

> AI proposes and operates. ArchForge preserves geometric and semantic truth.

## Production milestone: AI-native Pod Designer v0.1
This milestone is intentionally narrow. It is the go/no-go test for whether ArchForge provides value beyond a general AI chat plus a conventional modeling tool.

A v0.1 project must support a small pod-based building through a long edit session while preserving one coherent model.

### Required capabilities
1. Create multiple pods with persistent IDs.
2. Join pods with one shared planar junction and remove overlapping internal shell portions consistently in supported views.
3. Add, move, resize, and delete pod openings without floating patches or stale host relationships.
4. Preserve parent/dependent relationships through parameter edits.
5. Keep mounted/derived objects synchronized when parents move or change shape.
6. Undo/redo returns the semantic model to the exact previous state.
7. Save -> close -> load preserves entity IDs, relationships, parameters, and deterministic geometry.
8. 2D plan, orthographic views, fast preview, and tessellated 3D must not express contradictory topology for supported entities.
9. Areas, volumes, lengths, and similar reported quantities must be computed from the model/geometry, never invented by the AI.
10. Run a scripted sequence of at least 30 meaningful AI-style edits without semantic corruption, stale references, invalid dependencies, or unexplained topology drift.

### Explicitly not required for v0.1
- Full Revit/Rhino/Blender feature parity.
- General-purpose structural engineering verification.
- Building-code compliance certification.
- General arbitrary-solid Boolean/B-rep modeling.
- Production-grade fabrication for all organic geometry.
- Large UI/toolbars that duplicate mature CAD workflows.

## Go / no-go test
After the v0.1 scenario is implemented, evaluate the product by using it as an AI-controlled design system.

Continue expanding ArchForge only if the pilot demonstrates a practical advantage that a normal AI conversation cannot reliably provide, especially persistent identity, deterministic edits, exact state restoration, measurable geometry, and reproducible design history.

If those advantages are not convincing in the narrow pod scenario, do not hide the result by adding more features. Reassess or stop the product direction.

## Priority order
P0: model correctness and transactional behavior
P1: pod/opening/junction consistency across representations
P2: deterministic persistence and measurements
P3: autonomous AI command execution and 30-edit stress test
P4: UX improvements required to demonstrate the milestone
P5: broader geometry families and engineering integrations after the milestone is proven

## Agent rule
New work should normally originate from a `[READY]` GitHub Issue and follow `AGENTS.md`. Broad feature expansion that does not directly strengthen this milestone should be deferred unless explicitly approved.
