from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple
import math

from .plan import EvaluationPlan, build_evaluation_plan


@dataclass(frozen=True)
class GeometryIssue:
    severity: str
    code: str
    message: str
    entity_id: Optional[str] = None


@dataclass(frozen=True)
class GeometryBody:
    """Backend-neutral evaluated body metadata.

    ``payload`` is deliberately opaque: a mesh backend may store vertices/faces while an
    OCC backend may hold a B-rep handle. Semantic surface keys remain backend independent.
    """
    entity_id: str
    semantic_kind: str
    surface_keys: Tuple[str, ...]
    modifier_ids: Tuple[str, ...] = ()
    payload: Any = None


@dataclass(frozen=True)
class GeometryEvaluation:
    backend: str
    bodies: Tuple[GeometryBody, ...]
    issues: Tuple[GeometryIssue, ...] = ()

    @property
    def ok(self) -> bool:
        return not any(i.severity == 'error' for i in self.issues)

    def body(self, entity_id: str) -> GeometryBody:
        for body in self.bodies:
            if body.entity_id == entity_id: return body
        raise KeyError(entity_id)


class GeometryBackend(ABC):
    """Contract shared by preview-mesh and future OpenCascade evaluators."""
    name = 'abstract'

    @abstractmethod
    def evaluate_plan(self, doc, plan: EvaluationPlan) -> GeometryEvaluation:
        raise NotImplementedError

    def evaluate(self, doc, joint_values: Optional[Mapping[str, float]] = None) -> GeometryEvaluation:
        return self.evaluate_plan(doc, build_evaluation_plan(doc, joint_values))


class ContractBackend(GeometryBackend):
    """Headless evaluator that validates semantic-to-geometry contracts.

    It intentionally does not pretend to create final solids. It is useful now for CI and
    becomes a gate before expensive mesh/OCC evaluation later.
    """
    name = 'contract'

    def evaluate_plan(self, doc, plan: EvaluationPlan) -> GeometryEvaluation:
        from .surfaces import surface_catalog, resolve_surface

        bodies = []
        issues = []
        for node in plan.geometry_nodes():
            surfaces = surface_catalog(doc, node.entity_id)
            keys = tuple(s.key for s in surfaces)
            modifier_ids = []
            for raw in node.modifiers:
                if not raw.get('enabled', True):
                    continue
                mid = str(raw.get('id', ''))
                target = raw.get('target', {})
                try:
                    surface = resolve_surface(doc, node.entity_id, str(target.get('surface_role', '')))
                    if target.get('owner_id') != node.entity_id:
                        raise ValueError('modifier owner does not match evaluation node')
                    if not surface.deformable:
                        raise ValueError('modifier target is not deformable')
                    modifier_ids.append(mid)
                except Exception as exc:
                    issues.append(GeometryIssue('error', 'invalid_modifier_target', str(exc), node.entity_id))
            if node.transform is not None:
                vals = [v for row in node.transform for v in row]
                if len(vals) != 16 or not all(math.isfinite(float(v)) for v in vals):
                    issues.append(GeometryIssue('error', 'invalid_transform', 'non-finite or malformed transform', node.entity_id))
            bodies.append(GeometryBody(node.entity_id, node.semantic_kind, keys, tuple(modifier_ids)))
        return GeometryEvaluation(self.name, tuple(bodies), tuple(issues))
