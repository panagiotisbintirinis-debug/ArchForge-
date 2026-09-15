from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class IncompleteSolidValidityError(RuntimeError):
    """Raised when ArchForge cannot prove exact solid validity for fabrication.

    A closed, edge-manifold triangle mesh is not sufficient evidence because it can
    still contain face/face self-intersections or other solid inconsistencies that the
    current mesh topology validator does not detect.
    """


@dataclass(frozen=True)
class SolidValidityReport:
    engine: str
    checked_subshapes: int


def _entity_prefix(entity_id: Optional[str]) -> str:
    return f"{entity_id}: " if entity_id else ""


def require_mesh_exact_solid_validity(mesh: Any, *, entity_id: Optional[str] = None) -> None:
    """Fail closed for triangle meshes that lack native exact-solid validity evidence.

    This deliberately does not attempt centroid filtering, triangle-pair heuristics, or
    mesh-to-BRep reconstruction. Such shortcuts can miss general self-intersections and
    must never promote viewport tessellation to fabrication geometry.
    """
    del mesh
    raise IncompleteSolidValidityError(
        _entity_prefix(entity_id)
        + "triangle-mesh topology is insufficient to prove solid validity; "
        "general self-intersections are not proven absent. A native OpenCascade/OCP "
        "B-Rep solid must pass BRepCheck_Analyzer before fabrication quality can be granted."
    )


def require_valid_ocp_brep(shape: Any, *, entity_id: Optional[str] = None) -> SolidValidityReport:
    """Recursively validate a native OpenCascade shape with BRepCheck_Analyzer.

    The function is intentionally isolated from tessellated preview geometry. It accepts
    a native ``TopoDS_Shape`` (or compatible OCP wrapper), validates the root shape, then
    recursively validates each direct subshape. A future exact-solid backend can use this
    report as fabrication evidence without changing the semantic model.
    """
    try:
        from OCP.BRepCheck import BRepCheck_Analyzer
        from OCP.TopoDS import TopoDS_Iterator
    except Exception as exc:  # pragma: no cover - exercised only on missing binary dependency
        raise IncompleteSolidValidityError(
            _entity_prefix(entity_id)
            + "OpenCascade/OCP solid validation is unavailable; install cadquery-ocp."
        ) from exc

    if shape is None or not hasattr(shape, "IsNull") or shape.IsNull():
        raise IncompleteSolidValidityError(
            _entity_prefix(entity_id) + "exact B-Rep shape is null or unavailable."
        )

    checked = 0

    def walk(current: Any, path: str) -> None:
        nonlocal checked
        checked += 1
        try:
            analyzer = BRepCheck_Analyzer(current)
            valid = bool(analyzer.IsValid())
        except Exception as exc:
            raise IncompleteSolidValidityError(
                _entity_prefix(entity_id)
                + f"OpenCascade BRepCheck_Analyzer failed at {path}: {exc}"
            ) from exc
        if not valid:
            raise IncompleteSolidValidityError(
                _entity_prefix(entity_id)
                + f"OpenCascade BRepCheck_Analyzer rejected exact B-Rep subshape at {path}."
            )

        iterator = TopoDS_Iterator(current)
        child_index = 0
        while iterator.More():
            walk(iterator.Value(), f"{path}/{child_index}")
            iterator.Next()
            child_index += 1

    walk(shape, "root")
    return SolidValidityReport(
        engine="OpenCascade BRepCheck_Analyzer",
        checked_subshapes=checked,
    )
