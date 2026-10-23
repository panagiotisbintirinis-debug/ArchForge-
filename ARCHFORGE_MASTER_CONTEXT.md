# ArchForge Master Context

This file is the authoritative product-direction document for ArchForge. It consolidates the project's prior design discussions, manifesto decisions, UI/UX direction, architecture rules, and development priorities into one coherent baseline.

When older notes, issues, chat transcripts, experimental branches, or historical roadmaps conflict with this file, the newer rule in this file wins unless the human owner explicitly changes it.

## 1. Product identity

ArchForge is a **human-first visual design environment**.

Its target experience combines:
- the approachability and semantic architectural workflow of Home Designer / Chief Architect,
- progressively richer geometric freedom inspired by Blender,
- one coherent model spanning architecture, organic geometry, mechanics, fabrication, and later rendering.

ArchForge is **not**:
- an AI Architect,
- an AI-first design product,
- a pod-only or dome-only designer,
- a collection of headless commands with a viewport attached,
- a test-count optimization exercise.

A person must be able to complete the core design workflow without configuring or invoking AI.

## 2. Core interaction principle

The primary product loop is:

`see -> select -> directly manipulate -> inspect dimensions/properties -> commit -> undo/redo if needed`

The intended manual edit pipeline is:

`pointer/handle/gizmo -> interaction transaction -> shared Command -> CommandStack -> authoritative Document -> derived views`

When AI is explicitly invoked, the pipeline is:

`AI intent -> the same shared Command semantics -> CommandStack -> authoritative Document -> derived views`

There must not be a parallel AI mutation engine or AI-only design state.

## 3. One authoritative model

The `Document` is the design source of truth.

2D plans, orthographic views, 3D previews, render meshes, selection overlays, previews, caches, exporters, AI context, fabrication views, and analysis views are derived from the authoritative model.

Do not create competing design truths such as:
- a plan-only wall model,
- a separate 3D wall model,
- render-only authoritative geometry,
- AI-owned geometry state,
- runtime-only mechanical geometry that cannot be edited or persisted.

The preferred direction is:

`authoritative model -> events/pub-sub -> derived views`

rather than imperative chains that manually synchronize multiple caches after every edit.

## 4. Reversibility is mandatory

Every committed user operation must be reversible and persistent.

For supported operations:
- Undo restores the exact previous authoritative state.
- Redo restores the exact next authoritative state.
- Save/close/load preserves IDs, relationships, parameters, modifiers, and deterministic geometry.
- A visually correct edit with broken undo/redo is not complete.
- A command that partially restores state is not acceptable.

Previews may be transient, but committed design state must flow through shared command/transaction semantics.

## 5. Human validation is a first-class gate

Green tests are necessary engineering evidence, not proof that ArchForge is human-usable.

Every important feature is judged through three gates:

### MODEL GATE
Is the authoritative state correct and coherent?

### REVERSIBILITY GATE
Do undo/redo and persistence restore the correct state?

### HUMAN GATE
Can a person actually perform the intended action naturally in the running application and see the correct result?

A feature is unfinished if any one of these gates fails.

Do not use pass counts such as 235, 391, 427, or any future number as a substitute for product validation.

## 6. Direct manipulation

Direct manipulation is core product architecture, not cosmetic UI.

Important objects should support:
- visual selection,
- move,
- rotate,
- stretch/resize where semantically valid,
- numerical property editing,
- live dimensions,
- snapping,
- contextual handles/gizmos.

Default architectural snapping should favor 90-degree workflows, while still allowing non-orthogonal geometry.

Move, Stretch, Scale, and Sculpt are distinct operations and should remain conceptually separate.

## 7. 2D and 3D are views of the same project

The plan view and the 3D view must represent the same authoritative objects.

An edit made in one view must be reflected in the other through the shared model.

Do not implement separate editable model copies for 2D and 3D.

## 8. Conventional architecture is the foundation

ArchForge must first work as a credible house-design environment.

Core conventional architecture includes:
- walls,
- rooms,
- openings,
- floors,
- ceilings,
- roofs,
- levels/storeys,
- multi-floor buildings,
- dimensions,
- materials/properties,
- direct editing.

Users must be able to design a complete conventional rectangular building without using domes, pods, AI, or sculpting.

Walls should not remain permanently limited to simple rectangular extrusions. The architecture should support richer top profiles and local geometry while retaining semantic identity where practical.

## 9. Openings must be real host relationships

Doors and windows are not decorative meshes placed in front of walls.

An opening must:
- belong to a host,
- persist through host edits,
- create the appropriate geometric opening,
- preserve stable relationships,
- participate correctly in save/load and undo/redo.

The same host/dependent principle should extend to compatible organic and free-form hosts.

## 10. Roof editing

A roof is not complete merely because a slab appears above walls.

The direction includes:
- correct derivation from the exterior wall footprint,
- independently editable edges/overhangs,
- direct-manipulation roof controls,
- live dimensions,
- local roof/canopy behavior where appropriate,
- reversible edits.

Any roof change that cannot be restored exactly by undo is unfinished.

## 11. Sculpting

Sculpting is universal and local.

The preferred user experience is:

`select surface -> point at the exact region -> drag -> see local deformation -> release -> undo/redo if needed`

The user should not have to think in terms of brush radius and strength just to pull one part of a wall.

Radius, falloff, and strength may exist as advanced controls or internal implementation parameters, but they are not the primary mental model.

Sculpting should ultimately work on suitable:
- walls,
- ceilings,
- roofs,
- floors,
- facades,
- pod/dome shells,
- junctions,
- compatible mechanical/free-form surfaces.

Sculpting should be non-destructive by default where the semantic object can reasonably survive the operation. A sculpted wall should remain a wall rather than becoming an unrelated anonymous object merely because its surface changed.

## 12. Parametric-to-freeform bridge

One of ArchForge's central architecture problems is bridging semantic/parametric objects and authoritative free-form geometry.

Parametric generators are useful for:
- walls,
- openings,
- roofs,
- pods,
- repeated construction systems,
- deterministic dimensions.

But the visible surface cannot remain forever uneditable if the product promises local geometric freedom.

The architecture must provide a controlled path from semantic/parametric geometry toward editable vertex/edge/face or equivalent authoritative free-form representation without creating a second competing model.

Do not claim Blender-like modeling until this bridge genuinely exists in the user workflow.

## 13. Domes, pods, and organic architecture

Domes and pods are first-class building forms, not decorative spheres.

ArchForge must support:
- conventional buildings,
- organic buildings,
- hybrids combining both,
- flattened/shared interfaces where forms meet,
- openings in organic hosts,
- floors/slabs intersecting compatible organic spaces,
- partial dome use rather than forcing an entire building to be dome-based,
- geodesic/ghost-brick style representations as future construction systems.

The Pod Designer remains an integration proving ground for difficult geometry. It is not the identity of ArchForge.

## 14. Construction systems are independent of shape

Building shape does not dictate construction method.

A rectangular building, dome, pod, or free-form object may use different construction systems where technically appropriate.

Systems such as Spectre/Ghost should be modeled as selectable construction logic applied to suitable geometry, not hard-coded as the definition of a shape family.

## 15. Mechanical and MEP geometry

Architecture and mechanics must coexist in one project and one XYZ space.

The long-term product includes:
- concealed mechanical arms,
- actuators,
- moving assemblies,
- joints and travel limits,
- embedded mechanisms,
- conduits and MEP elements.

Mechanical/MEP entities should be authoritative, editable, persistent project objects.

Avoid runtime-only procedural render geometry that has no stable editable representation in the Document.

Where mesh editing is appropriate, architecture, sculpting, and MEP should reuse coherent geometry infrastructure rather than creating incompatible subsystems.

## 16. Materials, rendering, and fabrication

Rendering should derive from the actual ArchForge model.

Do not substitute an AI-generated image that merely resembles the design for model-based rendering.

Photorealistic rendering is important but follows the stabilization of the editor workflow.

Fabrication/export is a first-class destination. Geometry architecture should preserve a path toward:
- watertight evaluated meshes,
- STL and related export,
- explicit measurement provenance,
- fabrication validation where actually implemented.

Do not label preview geometry as fabrication-ready unless a real validation gate proves it.

## 17. Truth and provenance

Never present guessed or heuristic engineering values as verified results.

Structural, mechanical, environmental, fabrication, code-compliance, cost, and safety claims require explicit provenance and appropriate validation.

Unsupported derived quantities remain unsupported.

AI approval means "apply the requested proposal," not "engineering verified."

## 18. Automatic behavior must allow manual override

Useful automation is encouraged:
- automatic rooms,
- wall joins,
- floor generation,
- roof derivation,
- dome junctions,
- opening placement assistance,
- snapping.

But automatic behavior must not trap the user.

Manual overrides must remain explicit, persistent, and reversible.

## 19. Development method

Prefer small, verifiable slices over broad feature expansion.

For behavior-changing work:
1. identify the user-facing contract,
2. add the smallest useful regression evidence where appropriate,
3. implement the smallest coherent production change,
4. run the full relevant test suite,
5. validate reversibility,
6. validate the real UI workflow when visual interaction is involved,
7. open/merge through the normal branch and PR process.

Do not create placeholder buttons, parsers, fake panels, or geometry stubs and call the subsystem complete.

Do not build AI-only evidence, logs, or fingerprints merely to prove autonomous agent activity.

## 20. Priority order

Until explicitly changed by the human owner, the development priority is:

1. Stable application shell and viewport.
2. Selection, picking, and direct manipulation.
3. Walls, openings, floors, ceilings, roofs, levels, and multi-floor workflow.
4. Editable dimensions, snapping, handles, and Inspector/property editing.
5. Fully coherent 2D <-> 3D behavior.
6. Local point-and-drag sculpting.
7. Parametric <-> authoritative free-form geometry bridge.
8. Domes, pods, and rectangular/organic hybrids.
9. Mechanical/MEP integration using the same coherent model and geometry principles.
10. Materials, rendering, fabrication, and export.
11. Optional AI assistance on top of the mature human workflow.

This priority order replaces older AI-first, pod-first, test-count-driven, or broad-expansion roadmaps.

## 21. Repository and specification truth

Two truths must remain distinct:

- **Repository truth:** live `develop` tells us what is currently implemented.
- **Product truth:** this file tells us what ArchForge is intended to become and which architectural principles govern implementation.

Never infer that a product requirement is already implemented merely because it appears in this document.

Before starting work, agents must inspect live `develop`, current issues/PRs, `ROADMAP.md`, `AGENTS.md`, and this file.

## 22. Conflict resolution rule

If an older issue, note, experiment, chat transcript, or document conflicts with this Master Context:

1. prefer this Master Context,
2. then prefer the newest explicit human-owner decision,
3. then prefer current repository contracts and tests where they do not contradict the product direction,
4. escalate only when a genuine unresolved product-semantic decision remains.

Routine implementation details do not require owner confirmation.

## 23. Definition of progress

Progress is not "more code" and not "more green tests."

Progress means the live application moves closer to a coherent visual design environment in which a person can build, inspect, directly edit, undo, save, reopen, and continue the same project confidently.

That is the ArchForge standard.
