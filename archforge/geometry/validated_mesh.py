from __future__ import annotations
from .backend import GeometryBackend,GeometryBody,GeometryEvaluation,GeometryIssue
from .mesh import TessellatedPreviewBackend,MeshPayload
from .mesh_validation import validate_mesh

class ValidatedMeshBackend(GeometryBackend):
    """Validate tessellated bodies, but promote only geometry that is actually proven safe.

    Preview tessellation remains preview quality unless it has no active unapplied
    modifiers and passes closed/manifold topology checks. This is a bridge toward STL,
    not permission to export arbitrary viewport meshes.
    """
    name='validated-mesh'
    def evaluate_plan(self,doc,plan):
        source=TessellatedPreviewBackend().evaluate_plan(doc,plan);bodies=[];issues=list(source.issues)
        for body in source.bodies:
            payload=body.payload
            if not isinstance(payload,MeshPayload):
                bodies.append(body);continue
            report=validate_mesh(payload)
            for f in report.findings:
                severity='warning' if f.code=='boundary_edges' else f.severity
                issues.append(GeometryIssue(severity,'mesh_'+f.code,f.message,body.entity_id))
            modifiers_ok=not body.modifier_ids or body.modifiers_applied
            proven=report.watertight and report.manifold and modifiers_ok
            quality='fabrication_mesh' if proven else body.quality
            bodies.append(GeometryBody(body.entity_id,body.semantic_kind,body.surface_keys,body.modifier_ids,payload,quality,body.modifiers_applied,report.watertight,report.manifold))
        return GeometryEvaluation(self.name,tuple(bodies),tuple(issues))
