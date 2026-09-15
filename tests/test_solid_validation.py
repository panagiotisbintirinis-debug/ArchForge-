import pytest

from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCP.TopoDS import TopoDS_Shape

from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.geometry.solid_validation import (
    IncompleteSolidValidityError,
    require_mesh_exact_solid_validity,
    require_valid_ocp_brep,
)


def _overlapping_closed_tetrahedra():
    # Two individually closed tetrahedra overlap in space without sharing topology.
    # The current edge-based validator therefore sees a watertight/manifold mesh even
    # though the combined triangle body has geometric self-intersection/overlap.
    a = [
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
    ]
    b = [
        (0.2, 0.2, 0.2),
        (1.2, 0.2, 0.2),
        (0.2, 1.2, 0.2),
        (0.2, 0.2, 1.2),
    ]
    faces = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]
    triangles = tuple(faces + [tuple(i + 4 for i in face) for face in faces])
    roles = tuple('shell' for _ in triangles)
    return MeshPayload(tuple(a + b), triangles, roles)


def test_edge_manifold_mesh_can_still_hide_geometric_self_intersection():
    mesh = _overlapping_closed_tetrahedra()
    report = validate_mesh(mesh)
    assert report.watertight
    assert report.manifold

    with pytest.raises(IncompleteSolidValidityError, match='self-intersections are not proven absent'):
        require_mesh_exact_solid_validity(mesh, entity_id='overlap')


def test_recursive_brepcheck_accepts_valid_native_box():
    shape = BRepPrimAPI_MakeBox(1.0, 2.0, 3.0).Shape()
    report = require_valid_ocp_brep(shape, entity_id='native-box')
    assert report.engine == 'OpenCascade BRepCheck_Analyzer'
    assert report.checked_subshapes > 1


def test_null_native_shape_is_rejected_explicitly():
    with pytest.raises(IncompleteSolidValidityError, match='null or unavailable'):
        require_valid_ocp_brep(TopoDS_Shape(), entity_id='null-shape')
