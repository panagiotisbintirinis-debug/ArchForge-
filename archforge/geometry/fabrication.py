from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .backend import GeometryEvaluation


@dataclass(frozen=True)
class FabricationFinding:
    severity: str
    code: str
    message: str
    entity_id: Optional[str] = None


@dataclass(frozen=True)
class FabricationReport:
    findings: Tuple[FabricationFinding, ...]

    @property
    def ready(self) -> bool:
        return not any(f.severity == 'error' for f in self.findings)


def assess_fabrication(evaluation: GeometryEvaluation, entity_ids=None) -> FabricationReport:
    """Refuse fabrication unless geometry carries explicit proof required for STL.

    This prevents a dangerous future shortcut where viewport triangles are exported while
    sculpt modifiers, manifold checks, or watertightness were never evaluated.
    """
    selected = set(entity_ids) if entity_ids is not None else None
    findings=[]
    for issue in evaluation.issues:
        if issue.severity=='error' and (selected is None or issue.entity_id in selected):
            findings.append(FabricationFinding('error','geometry_evaluation_error',issue.message,issue.entity_id))
    bodies=[b for b in evaluation.bodies if selected is None or b.entity_id in selected]
    if selected is not None:
        missing=selected-{b.entity_id for b in bodies}
        for eid in sorted(missing): findings.append(FabricationFinding('error','missing_body','no evaluated geometry body',eid))
    for body in bodies:
        if body.quality not in ('fabrication_mesh','exact_brep'):
            findings.append(FabricationFinding('error','insufficient_geometry_quality',f'{body.quality} geometry is not fabrication geometry',body.entity_id))
        if body.modifier_ids and not body.modifiers_applied:
            findings.append(FabricationFinding('error','modifiers_not_applied','active sculpt modifiers are not present in evaluated geometry',body.entity_id))
        if body.watertight is not True:
            findings.append(FabricationFinding('error','not_proven_watertight','watertightness has not been proven',body.entity_id))
        if body.manifold is not True:
            findings.append(FabricationFinding('error','not_proven_manifold','manifoldness has not been proven',body.entity_id))
    return FabricationReport(tuple(findings))


def require_fabrication_ready(evaluation: GeometryEvaluation, entity_ids=None) -> None:
    report=assess_fabrication(evaluation,entity_ids)
    if not report.ready:
        summary='; '.join(f'{f.code}: {f.message}' for f in report.findings)
        raise ValueError('fabrication gate failed: '+summary)
