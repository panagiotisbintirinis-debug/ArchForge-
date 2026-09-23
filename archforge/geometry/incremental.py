from __future__ import annotations

from typing import Dict, Mapping, Optional, Tuple

from .backend import GeometryBody, GeometryEvaluation, GeometryIssue
from .plan import build_evaluation_plan


class IncrementalEvaluationCache:
    """Entity-granular cache for expensive geometry backend evaluation.

    The cache never clears ``Document.dirty`` because several views/backends may consume
    the same semantic mutations independently. Instead each cache remembers the document
    dirty-generation it has observed for each entity. Deleted entities are purged without
    re-evaluating clean survivors.
    """

    def __init__(self, backend):
        self.backend = backend
        self._bodies: Dict[str, GeometryBody] = {}
        self._issues: Dict[str, Tuple[GeometryIssue, ...]] = {}
        self._global_issues: Tuple[GeometryIssue, ...] = ()
        self._seen_generation: Dict[str, int] = {}
        self._initialized = False
        self._joint_key: Tuple[Tuple[str, float], ...] = ()

    def clear(self) -> None:
        self._bodies.clear()
        self._issues.clear()
        self._global_issues = ()
        self._seen_generation.clear()
        self._initialized = False
        self._joint_key = ()


    def invalidate(self, entity_ids=None) -> None:
        """Invalidate cached observations without touching authoritative Document state."""
        if entity_ids is None:
            self._seen_generation.clear()
            self._initialized = False
            return
        for entity_id in entity_ids:
            self._seen_generation.pop(str(entity_id), None)

    def _evaluation(self) -> GeometryEvaluation:
        bodies = tuple(self._bodies[eid] for eid in sorted(self._bodies))
        issues = list(self._global_issues)
        for eid in sorted(self._issues):
            issues.extend(self._issues[eid])
        return GeometryEvaluation(self.backend.name, bodies, tuple(issues))

    def sync(self, doc, joint_values: Optional[Mapping[str, float]] = None) -> GeometryEvaluation:
        joint_key = tuple(sorted((str(k), float(v)) for k, v in (joint_values or {}).items()))
        force_all = not self._initialized or joint_key != self._joint_key

        current_ids = set(doc.entities)
        cached_ids = set(self._bodies) | set(self._seen_generation)
        deleted_ids = cached_ids - current_ids
        for eid in deleted_ids:
            self._bodies.pop(eid, None)
            self._issues.pop(eid, None)
            self._seen_generation[eid] = doc.dirty_generation(eid)

        if force_all:
            rebuild_ids = current_ids
        else:
            rebuild_ids = {
                eid for eid in current_ids
                if (
                    eid not in self._seen_generation
                    or doc.dirty_generation(eid) > self._seen_generation.get(eid, -1)
                )
            }

        if rebuild_ids:
            plan = build_evaluation_plan(doc, joint_values, entity_ids=rebuild_ids)
            evaluated = self.backend.evaluate_plan(doc, plan)
            returned = {body.entity_id: body for body in evaluated.bodies}

            for eid in rebuild_ids:
                body = returned.get(eid)
                if body is None:
                    self._bodies.pop(eid, None)
                else:
                    self._bodies[eid] = body
                self._issues[eid] = tuple(issue for issue in evaluated.issues if issue.entity_id == eid)
                self._seen_generation[eid] = doc.dirty_generation(eid)

            self._global_issues = tuple(issue for issue in evaluated.issues if issue.entity_id is None)

        self._initialized = True
        self._joint_key = joint_key
        return self._evaluation()
