from __future__ import annotations

from .backend import GeometryBackend, GeometryBody, GeometryEvaluation, GeometryIssue
from .mesh import MeshPayload, TessellatedPreviewBackend
from .mesh_validation import validate_mesh
from .solid_validation import require_mesh_exact_solid_validity


class ValidatedMeshBackend(GeometryBackend):
    """Topology-check tessellation without pretending it proves an exact solid.

    A closed, edge-manifold triangle mesh can still contain face/face
    self-intersections or other invalid-solid conditions. Until an exact B-Rep backend
    supplies native OpenCascade solid-validity evidence, this backend must fail closed at
    the old fabrication promotion boundary.
    """

    name = "validated-mesh"

    def evaluate_plan(self, doc, plan):
        source = TessellatedPreviewBackend().evaluate_plan(doc, plan)
        bodies = []
        issues = list(source.issues)

        for body in source.bodies:
            payload = body.payload
            if not isinstance(payload, MeshPayload):
                bodies.append(body)
                continue

            report = validate_mesh(payload)
            for finding in report.findings:
                severity = "warning" if finding.code == "boundary_edges" else finding.severity
                issues.append(
                    GeometryIssue(
                        severity,
                        "mesh_" + finding.code,
                        finding.message,
                        body.entity_id,
                    )
                )

            modifiers_ok = not body.modifier_ids or body.modifiers_applied
            old_promotion_boundary = report.watertight and report.manifold and modifiers_ok

            if old_promotion_boundary:
                require_mesh_exact_solid_validity(payload, entity_id=body.entity_id)

            bodies.append(
                GeometryBody(
                    body.entity_id,
                    body.semantic_kind,
                    body.surface_keys,
                    body.modifier_ids,
                    payload,
                    body.quality,
                    body.modifiers_applied,
                    report.watertight,
                    report.manifold,
                )
            )

        return GeometryEvaluation(self.name, tuple(bodies), tuple(issues))
