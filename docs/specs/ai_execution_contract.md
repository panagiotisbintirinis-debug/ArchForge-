# Headless AI-to-ArchForge Command Execution Contract

## Overview

This specification defines the machine-facing, typed execution interface that allows any external AI agent, autonomous design loop, or headless orchestrator to operate ArchForge without mutating raw document internals or relying on UI mouse automation.

## Core Architectural Invariants

1. **Deterministic Input & Output Schemas**: Every action consumes validated scalar parameters or dictionaries and returns an `AIExecutionResult` containing:
   - `success: bool`
   - `action: str`
   - `entity_ids: Tuple[str, ...]` (stable IDs for created or mutated entities)
   - `data: Dict[str, Any]` (structured payload)
   - `errors: Tuple[AICommandError, ...]` (machine-readable failure records)
   - `undo_available: bool`
   - `redo_available: bool`

2. **Explicit Machine-Readable Errors (`AICommandError`)**:
   - `code: str` (e.g., `entity_not_found`, `create_opening_failed`, `unsupported_opening_kind`)
   - `message: str` (diagnostic explanation)
   - `target_id: Optional[str]` (target entity ID if applicable)
   - `details: Dict[str, Any]` (contextual parameters)

3. **Strict Invariant Enforcement**:
   - No command may bypass model validation rules or geometry constraints.
   - For instance, pod openings are strictly validated against host geometry (vertical clearance, sill bounds, flat margin constraints).

4. **No Inferred Fabrication Claims**:
   - Success of a semantic command does not imply physical engineering or manufacturing validity. Measurements indicate provenance explicitly (`semantic_parameter`, `analytic_ellipse_from_semantic_parameters`) and report unsupported metrics as `UNSUPPORTED` with no invented numbers.

5. **Model-Agnostic Design**:
   - The contract is purely Python / JSON serializable and callable by any AI model vendor (Gemini, Claude, GPT, local LLMs) via direct library import or JSON-RPC.

---

## Supported Action Surface (Pod Designer v0.1)

| Action | Description | Parameters |
|---|---|---|
| `create_pod` | Create a new parametric pod entity | `cx`, `cy`, `floor_level`, `diameter_x`, `diameter_y`, `height`, `shell_thickness`, `rotation`, `name`, `custom_id` |
| `edit_pod` | Update parameters on an existing pod | `pod_id`, `changes` |
| `delete_pod` | Delete an existing pod and cascades | `pod_id` |
| `create_opening` | Create a parametric door or window on a host pod | `host_pod_id`, `kind` ('door'/'window'), `surface_u`, `width`, `height`, `sill`, `flat_margin`, `name`, `custom_id` |
| `edit_opening` | Update parameters on a pod opening | `opening_id`, `changes` |
| `delete_opening` | Delete an opening entity | `opening_id` |
| `move_entities` | Translate entities in 3D space | `entity_ids`, `dx`, `dy`, `dz` |
| `rotate_entities` | Rotate entities around centroid or pivot | `entity_ids`, `angle_deg` |
| `resize_pod` | Resize dimensional parameters of a pod | `pod_id`, `diameter_x`, `diameter_y`, `height` |
| `infer_junctions` | Infer organic junctions from pod intersections | None |
| `infer_opening_patches` | Infer planar opening patches for pod openings | None |
| `undo` | Undo last transaction on the stack | None |
| `redo` | Redo previously undone transaction | None |
| `save` | Save document to `.archforge` project file | `filepath` |
| `load` | Load document from `.archforge` project file | `filepath` |
| `inspect_entity` | Inspect current semantic state of an entity | `entity_id` |
| `list_entities` | List entities in current document | `kind` (optional) |
| `measure` | Request model-derived measurements with provenance | `entity_id`, `quantities` (optional) |
| `execute_action` | Generic JSON-RPC style dispatcher | `action`, `params` |
| `get_action_manifest` | Retrieve complete introspection schema | None |

---

## Python API Usage Example

```python
from archforge.architecture.ai_commands import ArchForgeAIClient

client = ArchForgeAIClient()

# 1. Create Pod
result = client.create_pod(cx=0.0, cy=0.0, diameter_x=6.0, diameter_y=6.0, height=3.5)
pod_id = result.entity_ids[0]

# 2. Add Door Opening
res_door = client.create_opening(host_pod_id=pod_id, kind="door", surface_u=0.25, width=1.0, height=2.1, sill=0.0)

# 3. Request Measurements
res_meas = client.measure(pod_id)
print("Footprint area:", res_meas.data["measurements"]["floor_footprint_area"])

# 4. Undo / Redo
client.undo()
client.redo()
```
