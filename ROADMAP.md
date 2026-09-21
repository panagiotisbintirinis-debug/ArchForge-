# ArchForge Product Roadmap

## Product definition
ArchForge is a human-first visual design environment. Its target is to combine the approachable semantic/parametric workflow of a home-design application with progressively richer free-form modeling, while preserving one deterministic, persistent, inspectable design model.

The core product claim is:

> The human creates. The ArchForge model structures. AI assists only when explicitly invoked.

AI is optional. ArchForge must remain useful when no AI service is configured or called. Manual UI actions and AI-requested actions must operate on the same authoritative `Document` through the same command semantics; there must not be a parallel AI design state or execution engine.

## Current production milestone: First Human-Usable ArchForge
The current milestone is a narrow end-to-end proof that a person can create and edit a real ArchForge project visually, then optionally ask AI to perform an equivalent edit on that same project without changing the source of truth.

The existing Pod Designer scenario remains a useful integration proving ground for difficult geometry, persistent identity, openings, junctions, and multi-view consistency. It is not the product definition and is not an AI-only go/no-go gate.

### Required capabilities
1. Launch a real desktop ArchForge application with a project lifecycle and one authoritative `Document`.
2. Create supported objects from the UI, including at minimum walls/openings and the existing pod family used by the integration scenario.
3. Select objects directly in a visual view and perform move, rotate, and supported resize/stretch operations with pointer-driven handles/gizmos or equivalent direct-manipulation controls.
4. Edit supported numeric parameters through the Inspector/properties UI.
5. Route committed manual edits through the shared `CommandStack`; previews may be transient, but committed design state must not live in a view-only model.
6. Preserve persistent entity IDs, host/dependent relationships, and deterministic derived geometry through edits.
7. Undo/redo must restore the authoritative model exactly; save -> close -> load must preserve IDs, relationships, parameters, and deterministic geometry.
8. 2D plan, orthographic views, and 3D preview must derive from the authoritative model and must not maintain competing design truth.
9. Measurements and fabrication claims must carry explicit provenance/status. Unsupported quantities remain unsupported rather than guessed.
10. Demonstrate a manual -> optional AI -> manual sequence on the same entity/project. Equivalent manual and AI edits must resolve to the same command semantics and authoritative serialized state.
11. Preserve the existing Pod Designer integration contracts for supported junction/opening geometry without making pod-specific behavior the general modeling architecture.
12. Establish an explicit path toward free-form authoritative geometry. Parametric Pod/Wall classes may remain useful semantic objects, but they must not be mistaken for Blender-style vertex/edge/face editing capability.

### Direct-manipulation contract
The intended committed edit pipeline is:

`Pointer/handle/gizmo -> interaction transaction -> shared Command -> CommandStack -> Document -> derived views`

The optional AI pipeline is:

`User explicitly invokes AI -> intent translation -> the same shared Command semantics -> CommandStack -> Document -> derived views`

A mouse move and an AI-requested move that express the same semantic edit must not reach different mutation code paths. View caches may optimize rendering but are never authoritative design state.

### Explicitly not required for this milestone
- Full Revit/Rhino/Blender feature parity.
- A complete arbitrary-solid Boolean/B-rep kernel.
- Production-grade sculpting or mesh-edit tool parity with Blender.
- General-purpose structural engineering verification.
- Building-code compliance certification.
- Production-grade fabrication for all organic geometry.
- Photorealistic rendering.

These exclusions limit milestone breadth; they do not redefine ArchForge as an AI or pod-only product.

## Evidence policy
Green headless tests are necessary engineering evidence, not proof that the product is human-usable.

Freeze new machine-readable logs, deterministic fingerprints, or scripted AI pilot artifacts whose only purpose is to prove that an AI can drive headless scenarios. Such evidence may be added only when it validates a user-facing/manual contract, catches a real regression, or proves deterministic model behavior needed by the product.

The milestone succeeds only when a human can perform the core workflow directly in the application. AI capability is then tested as an optional second entry point to the same model and commands.

## Next regression-first architecture contract
Before claiming unified manual/AI control, add a regression test that starts from identical documents and applies the same supported edit through (a) the manual interaction transaction/commit path and (b) the public AI command path. The test must require equivalent command semantics and identical authoritative serialized state. If the paths diverge, fix the execution architecture rather than weakening the assertion.

## Priority order
P0: one authoritative model, transactional correctness, and truth/provenance
P1: human direct manipulation: selection, handles/gizmos, move/rotate/stretch, Inspector edits
P2: coherent 2D/3D derived representations and persistence/history
P3: manual/AI command-pipeline equivalence with AI strictly optional
P4: semantic/free-form geometry bridge and progressively richer modeling tools
P5: materials, rendering, site tools, broader architectural families
P6: engineering/fabrication integrations only with validated provenance

## Agent rule
New work should normally originate from a `[READY]` GitHub Issue and follow `AGENTS.md`. Prefer the smallest work that advances the first human-usable loop. Do not create AI-only evidence work, pod-specific special cases, or broad feature expansion merely to keep agents busy.
