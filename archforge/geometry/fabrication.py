from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Optional, Tuple, Union, BinaryIO, TextIO
from pathlib import Path

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
    sculpt modifiers, manifold checks, or watertightness were never evaluated. An empty
    scope is also unsafe: there is no fabrication-ready result when no geometry body was
    actually selected/evaluated.
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
    if not bodies:
        findings.append(FabricationFinding('error','empty_fabrication_scope','no evaluated geometry bodies were selected for fabrication'))
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


def _facet_normal(v0, v1, v2) -> Tuple[float, float, float]:
    """Compute unit normal vector for a triangular facet."""
    ax, ay, az = v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2]
    bx, by, bz = v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2]
    nx = ay * bz - az * by
    ny = az * bx - ax * bz
    nz = ax * by - ay * bx
    mag = math.sqrt(nx * nx + ny * ny + nz * nz)
    if mag > 1e-12:
        return (nx / mag, ny / mag, nz / mag)
    return (0.0, 0.0, 0.0)


def _iter_facets(evaluation: GeometryEvaluation, entity_ids=None):
    """Iterate validated STL facets; never silently skip a selected fabrication body."""
    selected = set(entity_ids) if entity_ids is not None else None
    for body in evaluation.bodies:
        if selected is not None and body.entity_id not in selected:
            continue
        payload = body.payload
        verts = getattr(payload, 'vertices', None)
        tris = getattr(payload, 'triangles', None)
        if verts is None or tris is None:
            raise ValueError(f'STL export requires triangulated mesh payload for {body.entity_id}')
        if len(tris) == 0:
            raise ValueError(f'STL export has no triangle facets for {body.entity_id}')
        for i0, i1, i2 in tris:
            v0, v1, v2 = verts[i0], verts[i1], verts[i2]
            n = _facet_normal(v0, v1, v2)
            yield n, v0, v1, v2


def export_stl_text(evaluation: GeometryEvaluation, entity_ids=None, name: str = 'archforge') -> str:
    """Export fabrication-ready geometry to ASCII STL string."""
    require_fabrication_ready(evaluation, entity_ids=entity_ids)
    safe_name = name.replace('\n', ' ').strip() or 'archforge'
    lines = [f"solid {safe_name}"]
    for n, v0, v1, v2 in _iter_facets(evaluation, entity_ids=entity_ids):
        lines.append(f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}")
        lines.append("    outer loop")
        lines.append(f"      vertex {v0[0]:.6e} {v0[1]:.6e} {v0[2]:.6e}")
        lines.append(f"      vertex {v1[0]:.6e} {v1[1]:.6e} {v1[2]:.6e}")
        lines.append(f"      vertex {v2[0]:.6e} {v2[1]:.6e} {v2[2]:.6e}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {safe_name}\n")
    return "\n".join(lines)


def export_stl_binary(evaluation: GeometryEvaluation, entity_ids=None, name: str = 'archforge') -> bytes:
    """Export fabrication-ready geometry to binary STL bytes."""
    require_fabrication_ready(evaluation, entity_ids=entity_ids)
    facets = list(_iter_facets(evaluation, entity_ids=entity_ids))
    header_text = f"ArchForge STL - {name}"[:80].encode('ascii', errors='replace')
    header = header_text.ljust(80, b'\x00')
    out = bytearray(header)
    out.extend(struct.pack('<I', len(facets)))
    for n, v0, v1, v2 in facets:
        out.extend(struct.pack(
            '<12fH',
            float(n[0]), float(n[1]), float(n[2]),
            float(v0[0]), float(v0[1]), float(v0[2]),
            float(v1[0]), float(v1[1]), float(v1[2]),
            float(v2[0]), float(v2[1]), float(v2[2]),
            0
        ))
    return bytes(out)


def export_stl(
    evaluation: GeometryEvaluation,
    target: Union[str, Path, BinaryIO, TextIO],
    entity_ids=None,
    binary: bool = True,
    name: str = 'archforge',
) -> int:
    """Export fabrication-ready geometry to an STL file or stream.

    Returns the number of exported facet triangles.
    """
    require_fabrication_ready(evaluation, entity_ids=entity_ids)
    facets = list(_iter_facets(evaluation, entity_ids=entity_ids))
    if binary:
        data = export_stl_binary(evaluation, entity_ids=entity_ids, name=name)
        if isinstance(target, (str, Path)):
            with open(target, 'wb') as f:
                f.write(data)
        elif hasattr(target, 'write'):
            target.write(data)
        else:
            raise TypeError(f"unsupported target type: {type(target)}")
    else:
        text = export_stl_text(evaluation, entity_ids=entity_ids, name=name)
        if isinstance(target, (str, Path)):
            with open(target, 'w', encoding='utf-8') as f:
                f.write(text)
        elif hasattr(target, 'write'):
            target.write(text)
        else:
            raise TypeError(f"unsupported target type: {type(target)}")
    return len(facets)


def export_document_stl(
    doc,
    target: Union[str, Path, BinaryIO, TextIO],
    entity_ids=None,
    binary: bool = True,
    name: str = 'archforge',
) -> int:
    """Evaluate document with ValidatedMeshBackend and export fabrication STL."""
    from .validated_mesh import ValidatedMeshBackend
    evaluation = ValidatedMeshBackend().evaluate(doc)
    return export_stl(evaluation, target, entity_ids=entity_ids, binary=binary, name=name)

