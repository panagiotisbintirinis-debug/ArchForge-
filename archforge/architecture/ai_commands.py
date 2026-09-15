"""Headless typed AI-to-ArchForge command execution surface.

This module defines the machine-facing contract allowing external AI agents,
autonomous loops, or headless orchestrators to inspect and mutate ArchForge models
strictly through valid semantic commands without bypassing model invariants
or pretending preliminary successes represent fabrication validity.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from archforge.architecture.measurements import (
    EntityMeasurements,
    Measurement,
    MeasurementStatus,
    measure_entity,
)
from archforge.architecture.openings import (
    infer_organic_opening_patches,
    validate_pod_opening,
)
from archforge.core.commands import (
    AddEntity,
    CommandStack,
    DeleteEntities,
    MoveEntities,
    RotateEntities,
    UpdateEntity,
)
from archforge.core.model import Document, Entity
from archforge.organic.junctions import infer_organic_junctions


@dataclass(frozen=True)
class AICommandError:
    """Explicit, machine-readable validation error."""

    code: str
    message: str
    target_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "target_id": self.target_id,
            "details": copy.deepcopy(self.details),
        }


@dataclass(frozen=True)
class AIExecutionResult:
    """Structured, deterministic execution outcome returned to AI callers."""

    success: bool
    action: str
    entity_ids: Tuple[str, ...] = ()
    data: Dict[str, Any] = field(default_factory=dict)
    errors: Tuple[AICommandError, ...] = ()
    undo_available: bool = False
    redo_available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "entity_ids": list(self.entity_ids),
            "data": copy.deepcopy(self.data),
            "errors": [err.to_dict() for err in self.errors],
            "undo_available": self.undo_available,
            "redo_available": self.redo_available,
        }


class ArchForgeAIClient:
    """Typed execution client bridging AI orchestrators and ArchForge core semantics."""

    def __init__(self, doc: Optional[Document] = None, stack: Optional[CommandStack] = None):
        self.doc = doc if doc is not None else Document()
        self.stack = stack if stack is not None else CommandStack(self.doc)

    def _result(
        self,
        action: str,
        success: bool,
        entity_ids: Sequence[str] = (),
        data: Optional[Dict[str, Any]] = None,
        errors: Sequence[AICommandError] = (),
    ) -> AIExecutionResult:
        return AIExecutionResult(
            success=success,
            action=action,
            entity_ids=tuple(entity_ids),
            data=data or {},
            errors=tuple(errors),
            undo_available=self.stack.can_undo,
            redo_available=self.stack.can_redo,
        )

    # -------------------------------------------------------------------------
    # Pod Lifecycle Actions
    # -------------------------------------------------------------------------

    def create_pod(
        self,
        cx: float,
        cy: float,
        floor_level: float = 0.0,
        diameter_x: float = 6.0,
        diameter_y: float = 6.0,
        height: float = 3.5,
        shell_thickness: float = 0.18,
        rotation: float = 0.0,
        name: str = "Pod",
        custom_id: Optional[str] = None,
    ) -> AIExecutionResult:
        """Create a new parametric pod entity."""
        params = {
            "cx": float(cx),
            "cy": float(cy),
            "floor_level": float(floor_level),
            "diameter_x": float(diameter_x),
            "diameter_y": float(diameter_y),
            "height": float(height),
            "shell_thickness": float(shell_thickness),
            "rotation": float(rotation),
        }
        try:
            pod = Entity("pod", params, name=name, id=custom_id) if custom_id else Entity("pod", params, name=name)
            self.stack.execute(AddEntity(pod))
            return self._result("create_pod", True, entity_ids=[pod.id], data={"pod": asdict(pod)})
        except Exception as exc:
            err = AICommandError(
                code="create_pod_failed",
                message=str(exc),
                details={"params": params},
            )
            return self._result("create_pod", False, errors=[err])

    def edit_pod(self, pod_id: str, changes: Dict[str, Any]) -> AIExecutionResult:
        """Update semantic parameters for an existing pod."""
        if pod_id not in self.doc.entities:
            err = AICommandError(code="entity_not_found", message=f"Entity {pod_id} does not exist", target_id=pod_id)
            return self._result("edit_pod", False, errors=[err])

        entity = self.doc.get(pod_id)
        if entity.kind != "pod":
            err = AICommandError(code="invalid_entity_kind", message=f"Entity {pod_id} is not a pod ({entity.kind})", target_id=pod_id)
            return self._result("edit_pod", False, errors=[err])

        try:
            self.stack.execute(UpdateEntity(pod_id, changes))
            return self._result("edit_pod", True, entity_ids=[pod_id], data={"params": copy.deepcopy(self.doc.get(pod_id).params)})
        except Exception as exc:
            err = AICommandError(code="edit_pod_failed", message=str(exc), target_id=pod_id, details={"changes": changes})
            return self._result("edit_pod", False, errors=[err])

    def delete_pod(self, pod_id: str) -> AIExecutionResult:
        """Delete an existing pod entity and its dependent structures."""
        if pod_id not in self.doc.entities:
            err = AICommandError(code="entity_not_found", message=f"Entity {pod_id} does not exist", target_id=pod_id)
            return self._result("delete_pod", False, errors=[err])

        try:
            self.stack.execute(DeleteEntities([pod_id]))
            return self._result("delete_pod", True, entity_ids=[pod_id])
        except Exception as exc:
            err = AICommandError(code="delete_pod_failed", message=str(exc), target_id=pod_id)
            return self._result("delete_pod", False, errors=[err])

    # -------------------------------------------------------------------------
    # Opening Lifecycle Actions
    # -------------------------------------------------------------------------

    def create_opening(
        self,
        host_pod_id: str,
        kind: str,
        surface_u: float,
        width: float,
        height: float,
        sill: float = 0.0,
        flat_margin: float = 0.25,
        name: Optional[str] = None,
        custom_id: Optional[str] = None,
    ) -> AIExecutionResult:
        """Create a door or window opening hosted on a pod."""
        if kind not in ("door", "window"):
            err = AICommandError(code="unsupported_opening_kind", message=f"Opening kind must be 'door' or 'window', got '{kind}'")
            return self._result("create_opening", False, errors=[err])

        if host_pod_id not in self.doc.entities:
            err = AICommandError(code="host_not_found", message=f"Host pod {host_pod_id} does not exist", target_id=host_pod_id)
            return self._result("create_opening", False, errors=[err])

        host = self.doc.get(host_pod_id)
        if host.kind != "pod":
            err = AICommandError(code="invalid_host_kind", message=f"Host entity {host_pod_id} is not a pod ({host.kind})", target_id=host_pod_id)
            return self._result("create_opening", False, errors=[err])

        params = {
            "surface_u": float(surface_u),
            "width": float(width),
            "height": float(height),
            "sill": float(sill),
            "flat_margin": float(flat_margin),
        }

        try:
            validate_pod_opening(host.params, params, kind)
            opening_name = name or ("Pod Door" if kind == "door" else "Pod Window")
            opening = Entity(kind, params, name=opening_name, parent_id=host_pod_id, id=custom_id) if custom_id else Entity(kind, params, name=opening_name, parent_id=host_pod_id)
            self.stack.execute(AddEntity(opening))
            return self._result("create_opening", True, entity_ids=[opening.id], data={"opening": asdict(opening)})
        except Exception as exc:
            err = AICommandError(code="create_opening_failed", message=str(exc), target_id=host_pod_id, details={"params": params})
            return self._result("create_opening", False, errors=[err])

    def edit_opening(self, opening_id: str, changes: Dict[str, Any]) -> AIExecutionResult:
        """Update parameters for an existing pod opening."""
        if opening_id not in self.doc.entities:
            err = AICommandError(code="entity_not_found", message=f"Opening {opening_id} does not exist", target_id=opening_id)
            return self._result("edit_opening", False, errors=[err])

        entity = self.doc.get(opening_id)
        if entity.kind not in ("door", "window"):
            err = AICommandError(code="invalid_entity_kind", message=f"Entity {opening_id} is not an opening ({entity.kind})", target_id=opening_id)
            return self._result("edit_opening", False, errors=[err])

        try:
            self.stack.execute(UpdateEntity(opening_id, changes))
            return self._result("edit_opening", True, entity_ids=[opening_id], data={"params": copy.deepcopy(self.doc.get(opening_id).params)})
        except Exception as exc:
            err = AICommandError(code="edit_opening_failed", message=str(exc), target_id=opening_id, details={"changes": changes})
            return self._result("edit_opening", False, errors=[err])

    def delete_opening(self, opening_id: str) -> AIExecutionResult:
        """Delete an opening entity."""
        if opening_id not in self.doc.entities:
            err = AICommandError(code="entity_not_found", message=f"Opening {opening_id} does not exist", target_id=opening_id)
            return self._result("delete_opening", False, errors=[err])

        try:
            self.stack.execute(DeleteEntities([opening_id]))
            return self._result("delete_opening", True, entity_ids=[opening_id])
        except Exception as exc:
            err = AICommandError(code="delete_opening_failed", message=str(exc), target_id=opening_id)
            return self._result("delete_opening", False, errors=[err])

    # -------------------------------------------------------------------------
    # Spatial Manipulation (Move, Resize, Rotate)
    # -------------------------------------------------------------------------

    def move_entities(self, entity_ids: Sequence[str], dx: float, dy: float, dz: float = 0.0) -> AIExecutionResult:
        """Translate supported entities in 3D space."""
        ids = list(entity_ids)
        missing = [eid for eid in ids if eid not in self.doc.entities]
        if missing:
            err = AICommandError(code="entities_not_found", message=f"Entities not found: {missing}", details={"missing_ids": missing})
            return self._result("move_entities", False, errors=[err])

        try:
            self.stack.execute(MoveEntities(ids, dx=float(dx), dy=float(dy), dz=float(dz)))
            return self._result("move_entities", True, entity_ids=ids, data={"dx": dx, "dy": dy, "dz": dz})
        except Exception as exc:
            err = AICommandError(code="move_failed", message=str(exc), details={"entity_ids": ids})
            return self._result("move_entities", False, errors=[err])

    def rotate_entities(self, entity_ids: Sequence[str], angle_deg: float) -> AIExecutionResult:
        """Rotate supported entities by angle in degrees."""
        ids = list(entity_ids)
        missing = [eid for eid in ids if eid not in self.doc.entities]
        if missing:
            err = AICommandError(code="entities_not_found", message=f"Entities not found: {missing}", details={"missing_ids": missing})
            return self._result("rotate_entities", False, errors=[err])

        try:
            self.stack.execute(RotateEntities(ids, angle=float(angle_deg)))
            return self._result("rotate_entities", True, entity_ids=ids, data={"angle_deg": angle_deg})
        except Exception as exc:
            err = AICommandError(code="rotate_failed", message=str(exc), details={"entity_ids": ids})
            return self._result("rotate_entities", False, errors=[err])

    def resize_pod(
        self,
        pod_id: str,
        diameter_x: Optional[float] = None,
        diameter_y: Optional[float] = None,
        height: Optional[float] = None,
    ) -> AIExecutionResult:
        """Resize dimensional parameters of a pod."""
        changes: Dict[str, float] = {}
        if diameter_x is not None:
            changes["diameter_x"] = float(diameter_x)
        if diameter_y is not None:
            changes["diameter_y"] = float(diameter_y)
        if height is not None:
            changes["height"] = float(height)

        if not changes:
            err = AICommandError(code="empty_resize_request", message="At least one dimension must be specified", target_id=pod_id)
            return self._result("resize_pod", False, errors=[err])

        return self.edit_pod(pod_id, changes)

    # -------------------------------------------------------------------------
    # Inferred Relationships & Topology
    # -------------------------------------------------------------------------

    def infer_junctions(self) -> AIExecutionResult:
        """Infer and reconcile semantic organic junctions from pod spatial overlaps."""
        try:
            res = infer_organic_junctions(self.doc)
            return self._result(
                "infer_junctions",
                True,
                entity_ids=list(res.active_ids),
                data={
                    "active_ids": list(res.active_ids),
                    "created_ids": list(res.created_ids),
                    "dormant_ids": list(res.dormant_ids),
                },
            )
        except Exception as exc:
            err = AICommandError(code="infer_junctions_failed", message=str(exc))
            return self._result("infer_junctions", False, errors=[err])

    def infer_opening_patches(self) -> AIExecutionResult:
        """Infer and reconcile persistent planar opening patches for pod openings."""
        try:
            res = infer_organic_opening_patches(self.doc)
            return self._result(
                "infer_opening_patches",
                True,
                entity_ids=list(res.active_ids),
                data={
                    "active_ids": list(res.active_ids),
                    "created_ids": list(res.created_ids),
                    "dormant_ids": list(res.dormant_ids),
                },
            )
        except Exception as exc:
            err = AICommandError(code="infer_opening_patches_failed", message=str(exc))
            return self._result("infer_opening_patches", False, errors=[err])

    # -------------------------------------------------------------------------
    # Undo / Redo
    # -------------------------------------------------------------------------

    def undo(self) -> AIExecutionResult:
        """Undo the last executed command."""
        if not self.stack.can_undo:
            err = AICommandError(code="nothing_to_undo", message="Command stack has no actions to undo")
            return self._result("undo", False, errors=[err])

        self.stack.undo()
        return self._result("undo", True)

    def redo(self) -> AIExecutionResult:
        """Redo the previously undone command."""
        if not self.stack.can_redo:
            err = AICommandError(code="nothing_to_redo", message="Command stack has no actions to redo")
            return self._result("redo", False, errors=[err])

        self.stack.redo()
        return self._result("redo", True)

    # -------------------------------------------------------------------------
    # Save / Load Persistence
    # -------------------------------------------------------------------------

    def save(self, filepath: str) -> AIExecutionResult:
        """Save current document to file."""
        try:
            self.doc.save(filepath)
            return self._result("save", True, data={"filepath": filepath})
        except Exception as exc:
            err = AICommandError(code="save_failed", message=str(exc), details={"filepath": filepath})
            return self._result("save", False, errors=[err])

    def load(self, filepath: str) -> AIExecutionResult:
        """Load document from file into this client."""
        try:
            self.doc = Document.load(filepath)
            self.stack = CommandStack(self.doc)
            return self._result("load", True, entity_ids=list(self.doc.entities.keys()), data={"filepath": filepath})
        except Exception as exc:
            err = AICommandError(code="load_failed", message=str(exc), details={"filepath": filepath})
            return self._result("load", False, errors=[err])

    # -------------------------------------------------------------------------
    # Inspection & Measurements
    # -------------------------------------------------------------------------

    def inspect_entity(self, entity_id: str) -> AIExecutionResult:
        """Inspect the current semantic state of an entity."""
        if entity_id not in self.doc.entities:
            err = AICommandError(code="entity_not_found", message=f"Entity {entity_id} does not exist", target_id=entity_id)
            return self._result("inspect_entity", False, errors=[err])

        e = self.doc.get(entity_id)
        data = {
            "id": e.id,
            "kind": e.kind,
            "name": e.name,
            "params": copy.deepcopy(e.params),
            "parent_id": e.parent_id,
            "children": list(self.doc.children.get(e.id, ())),
            "dependencies": sorted(list(self.doc.dependencies.get(e.id, ()))),
            "revision": e.revision,
            "visible": e.visible,
            "locked": e.locked,
        }
        return self._result("inspect_entity", True, entity_ids=[entity_id], data=data)

    def list_entities(self, kind: Optional[str] = None) -> AIExecutionResult:
        """List entities in the document, optionally filtered by kind."""
        entities = [
            e for e in self.doc.entities.values()
            if kind is None or e.kind == kind
        ]
        items = [
            {"id": e.id, "kind": e.kind, "name": e.name, "parent_id": e.parent_id}
            for e in entities
        ]
        return self._result("list_entities", True, entity_ids=[e.id for e in entities], data={"entities": items})

    def measure(self, entity_id: str, quantities: Optional[Sequence[str]] = None) -> AIExecutionResult:
        """Request model-derived measurements with explicit units and provenance."""
        if entity_id not in self.doc.entities:
            err = AICommandError(code="entity_not_found", message=f"Entity {entity_id} does not exist", target_id=entity_id)
            return self._result("measure", False, errors=[err])

        try:
            res: EntityMeasurements = measure_entity(self.doc, entity_id, quantities=quantities)
            meas_dict = {}
            for k, m in res.items():
                meas_dict[k] = {
                    "value": m.value,
                    "unit": m.unit,
                    "status": m.status.value,
                    "method": m.method,
                    "reason": m.reason,
                }
            return self._result(
                "measure",
                True,
                entity_ids=[entity_id],
                data={
                    "entity_id": res.entity_id,
                    "entity_kind": res.entity_kind,
                    "measurements": meas_dict,
                },
            )
        except Exception as exc:
            err = AICommandError(code="measure_failed", message=str(exc), target_id=entity_id)
            return self._result("measure", False, errors=[err])

    # -------------------------------------------------------------------------
    # Generic Action Dispatcher & Introspection
    # -------------------------------------------------------------------------

    def execute_action(self, action: str, params: Optional[Dict[str, Any]] = None) -> AIExecutionResult:
        """Execute a typed command from action name and parameters dictionary."""
        p = params or {}
        dispatch_map = {
            "create_pod": lambda: self.create_pod(**p),
            "edit_pod": lambda: self.edit_pod(**p),
            "delete_pod": lambda: self.delete_pod(**p),
            "create_opening": lambda: self.create_opening(**p),
            "edit_opening": lambda: self.edit_opening(**p),
            "delete_opening": lambda: self.delete_opening(**p),
            "move_entities": lambda: self.move_entities(**p),
            "rotate_entities": lambda: self.rotate_entities(**p),
            "resize_pod": lambda: self.resize_pod(**p),
            "infer_junctions": lambda: self.infer_junctions(),
            "infer_opening_patches": lambda: self.infer_opening_patches(),
            "undo": lambda: self.undo(),
            "redo": lambda: self.redo(),
            "save": lambda: self.save(**p),
            "load": lambda: self.load(**p),
            "inspect_entity": lambda: self.inspect_entity(**p),
            "list_entities": lambda: self.list_entities(**p),
            "measure": lambda: self.measure(**p),
        }
        if action not in dispatch_map:
            err = AICommandError(
                code="unknown_action",
                message=f"Action '{action}' is not supported",
                details={"supported_actions": sorted(list(dispatch_map.keys()))},
            )
            return self._result(action, False, errors=[err])

        try:
            return dispatch_map[action]()
        except TypeError as te:
            err = AICommandError(code="invalid_parameters", message=str(te), details={"parameters": p})
            return self._result(action, False, errors=[err])
        except Exception as exc:
            err = AICommandError(code="action_execution_failed", message=str(exc), details={"parameters": p})
            return self._result(action, False, errors=[err])

    @staticmethod
    def get_action_manifest() -> Dict[str, Any]:
        """Return machine-readable documentation and input parameter schemas for all AI actions."""
        return {
            "version": "0.1",
            "scope": "Pod Designer Semantic Execution Contract",
            "invariants": [
                "No engineering or fabrication validity is claimed from command success",
                "Validation failures are strictly typed, machine-readable, and deterministic",
                "Entity IDs are returned to the caller and remain stable across mutations",
            ],
            "actions": {
                "create_pod": {
                    "description": "Create a new parametric pod entity",
                    "parameters": {
                        "cx": "float", "cy": "float", "floor_level": "float=0.0",
                        "diameter_x": "float=6.0", "diameter_y": "float=6.0", "height": "float=3.5",
                        "shell_thickness": "float=0.18", "rotation": "float=0.0", "name": "str='Pod'",
                        "custom_id": "Optional[str]=None"
                    }
                },
                "edit_pod": {
                    "description": "Update parameters on an existing pod",
                    "parameters": {"pod_id": "str", "changes": "Dict[str, Any]"}
                },
                "delete_pod": {
                    "description": "Delete an existing pod entity",
                    "parameters": {"pod_id": "str"}
                },
                "create_opening": {
                    "description": "Create a parametric door or window opening hosted on a pod",
                    "parameters": {
                        "host_pod_id": "str", "kind": "'door' | 'window'",
                        "surface_u": "float", "width": "float", "height": "float",
                        "sill": "float=0.0", "flat_margin": "float=0.25", "name": "Optional[str]=None",
                        "custom_id": "Optional[str]=None"
                    }
                },
                "edit_opening": {
                    "description": "Update parameters on an existing pod opening",
                    "parameters": {"opening_id": "str", "changes": "Dict[str, Any]"}
                },
                "delete_opening": {
                    "description": "Delete an opening entity",
                    "parameters": {"opening_id": "str"}
                },
                "move_entities": {
                    "description": "Translate entities in 3D space",
                    "parameters": {"entity_ids": "Sequence[str]", "dx": "float", "dy": "float", "dz": "float=0.0"}
                },
                "rotate_entities": {
                    "description": "Rotate entities by angle in degrees",
                    "parameters": {"entity_ids": "Sequence[str]", "angle_deg": "float"}
                },
                "resize_pod": {
                    "description": "Resize dimensional parameters of a pod",
                    "parameters": {
                        "pod_id": "str", "diameter_x": "Optional[float]=None",
                        "diameter_y": "Optional[float]=None", "height": "Optional[float]=None"
                    }
                },
                "infer_junctions": {
                    "description": "Infer and reconcile semantic organic junctions from pod spatial overlaps",
                    "parameters": {}
                },
                "infer_opening_patches": {
                    "description": "Infer and reconcile planar opening patches for pod openings",
                    "parameters": {}
                },
                "undo": {
                    "description": "Undo last executed command",
                    "parameters": {}
                },
                "redo": {
                    "description": "Redo previously undone command",
                    "parameters": {}
                },
                "save": {
                    "description": "Save current project to file",
                    "parameters": {"filepath": "str"}
                },
                "load": {
                    "description": "Load project from file into client",
                    "parameters": {"filepath": "str"}
                },
                "inspect_entity": {
                    "description": "Inspect current semantic state of an entity",
                    "parameters": {"entity_id": "str"}
                },
                "list_entities": {
                    "description": "List entities in the project",
                    "parameters": {"kind": "Optional[str]=None"}
                },
                "measure": {
                    "description": "Request model-derived measurements with explicit units and provenance",
                    "parameters": {"entity_id": "str", "quantities": "Optional[Sequence[str]]=None"}
                }
            }
        }

