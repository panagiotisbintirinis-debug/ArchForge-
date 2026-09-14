# ArchForge Product Principles

ArchForge is being developed as a future-facing, saleable architectural and engineering design system. The repository being public does not reduce the quality bar. Every subsystem should be designed as if it must later support a commercial desktop product.

## Product mission

ArchForge must combine, in one coherent model:

- fast semantic architectural design for conventional buildings,
- domes, pods and other organic architectural systems,
- universal 3D sculpting and non-destructive surface deformation,
- mechanical components, joints, actuators and moving assemblies,
- manufacturing-ready geometry suitable for fabrication workflows such as STL export for 3D printing,
- precise dimensions, constraints, materials, constructions, levels, work planes and documentation.

These are not separate applications glued together. A single project must be able to contain all of them in the same XYZ space.

## Non-negotiable architecture rules

### 1. Semantic model first
Walls, rooms, floors, ceilings, openings, roofs, pods, junctions, mechanical parts and assemblies remain identifiable semantic objects. Display meshes are derived representations, not the source of truth.

### 2. Sculpting is universal
Sculpting must eventually work on any suitable 3D surface: conventional walls, ceilings, roofs, floors, facades, pod shells, flat dome junctions, soffits and compatible freeform/mechanical surfaces. It is not a dome-only feature.

### 3. Sculpting is non-destructive by default
A sculpted wall is still a wall. A sculpted ceiling is still a ceiling. A deformed pod junction is still a junction. Surface modifications are stored as ordered modifiers/overrides on top of the semantic base geometry and can be edited, disabled or removed.

### 4. Topology must survive regeneration
Persistent references must not depend on unstable mesh face numbers. Surface regions and modifiers must use semantic/topological references that can be remapped when base geometry changes.

### 5. Architecture and mechanics must coexist
Mechanical assemblies may be embedded into or hidden inside architectural geometry. A moving arm, actuator, shutter, articulated panel or future device must be able to occupy the same model, attach to architectural geometry, use joints/constraints and be revealed through openings or sculpted surfaces.

### 6. Construction is independent of shape
A rectangular building, dome, pod or freeform object does not determine its construction method. Construction systems such as Spectre/Ghost are selectable systems applied to suitable surfaces or assemblies.

### 7. Direct manipulation and numerical precision are equal
Every important modeling action should support both mouse-driven interaction with live preview and exact numerical control. Move, Stretch and Scale are distinct operations.

### 8. Automatic behavior must allow manual override
Automatic rooms, floors, wall joins, dome junctions, openings, derived geometry and other systems must be useful by default but must not trap the user. Manual overrides remain explicit and reversible.

### 9. Manufacturing is a first-class destination
The geometry architecture must be designed from the beginning so the evaluated final form can later produce watertight printable meshes and manufacturing/export formats. STL export is a required destination, not an afterthought.

### 10. No placeholder architecture presented as completion
A button, menu item, parser, fake AI panel or simplified geometry stub is not considered a completed feature. A subsystem is only called implemented when its underlying model, interaction, validation, undo/redo, persistence and tests meet the acceptance contract appropriate to that subsystem.

## Example target workflows

A user should ultimately be able to:

1. Draw a conventional two-storey building with walls, rooms, doors and windows.
2. Attach an ellipsoidal pod or dome to part of that building.
3. Let intersecting pods create flat shared junctions automatically.
4. Enter 3D sculpt mode and pull part of an exterior wall above a door outward to form an integrated rain canopy.
5. Pull or recess part of an interior ceiling for decorative geometry.
6. Sculpt a pod junction without destroying the pod relationship.
7. Place a concealed mechanical arm or actuator inside a sculpted wall cavity.
8. Define joints, travel limits and future simulation behavior for that mechanism.
9. Return to architectural mode and continue editing dimensions, openings and levels.
10. Evaluate the final geometry and export fabrication-ready meshes such as STL where appropriate.

## Development standard

ArchForge does not need to be perfect in the first implementation. It does need to be architected correctly from the start. Early versions may have limited tools or simplified evaluation, but they must not knowingly choose data structures or workflows that make the stated product mission impossible without a later rewrite.

When there is a conflict between a quick demo and a sound production architecture, choose the production architecture.
