import io
import struct
import pytest

from archforge.core.model import Document, Entity
from archforge.geometry.backend import GeometryBody, GeometryEvaluation
from archforge.geometry.mesh import MeshPayload, TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.fabrication import (
    assess_fabrication,
    export_stl_text,
    export_stl_binary,
    export_stl,
    export_document_stl,
)
from archforge.geometry.solid_validation import IncompleteSolidValidityError


def _synthetic_fabrication_evaluation(doc):
    """Exercise the STL writer independently of the exact-solid validation backend."""
    source = TessellatedPreviewBackend().evaluate(doc)
    bodies = tuple(
        GeometryBody(
            body.entity_id,
            body.semantic_kind,
            body.surface_keys,
            (),
            body.payload,
            'fabrication_mesh',
            True,
            True,
            True,
        )
        for body in source.bodies
    )
    return GeometryEvaluation('synthetic-solid-proof', bodies)


def test_stl_export_refuses_preview_quality_mesh():
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1, 'depth': 1, 'height': 1, 'rotation': 0})
    doc.add(box)
    preview_eval = PreviewBackend().evaluate(doc)
    with pytest.raises(ValueError, match='fabrication gate failed'):
        export_stl_text(preview_eval, [box.id])
    with pytest.raises(ValueError, match='fabrication gate failed'):
        export_stl_binary(preview_eval, [box.id])


def test_stl_export_refuses_empty_scope():
    eval_empty = GeometryEvaluation('test', ())
    with pytest.raises(ValueError, match='empty_fabrication_scope'):
        export_stl_text(eval_empty)


def test_stl_export_refuses_fabrication_ready_nonmesh_payload():
    body = GeometryBody(
        'brep-1', 'mechanical_part', ('brep-1:top',), (), payload=object(),
        quality='exact_brep', modifiers_applied=True, watertight=True, manifold=True,
    )
    evaluation = GeometryEvaluation('exact-test', (body,))
    assert assess_fabrication(evaluation, ['brep-1']).ready
    with pytest.raises(ValueError, match='triangulated mesh payload'):
        export_stl_text(evaluation, ['brep-1'])


def test_stl_export_refuses_zero_facet_mesh_payload():
    body = GeometryBody(
        'mesh-1', 'mechanical_part', (), (), payload=MeshPayload((), (), ()),
        quality='fabrication_mesh', modifiers_applied=True, watertight=True, manifold=True,
    )
    evaluation = GeometryEvaluation('mesh-test', (body,))
    assert assess_fabrication(evaluation, ['mesh-1']).ready
    with pytest.raises(ValueError, match='no triangle facets'):
        export_stl_binary(evaluation, ['mesh-1'])


def test_low_level_stl_export_ascii_box_still_works_with_explicit_proof_fixture():
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 2.0, 'depth': 1.0, 'height': 3.0, 'rotation': 0})
    doc.add(box)
    evaluation = _synthetic_fabrication_evaluation(doc)

    text = export_stl_text(evaluation, [box.id], name='test_box')
    lines = text.strip().splitlines()
    assert lines[0] == 'solid test_box'
    assert lines[-1] == 'endsolid test_box'
    assert sum(1 for line in lines if line.strip().startswith('facet normal')) == 12
    assert sum(1 for line in lines if line.strip().startswith('vertex')) == 36


def test_low_level_stl_export_binary_assembly_still_works_with_explicit_proof_fixture():
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0})
    part = Entity('mechanical_part', {'x': 5, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0})
    doc.add(box)
    doc.add(part)
    evaluation = _synthetic_fabrication_evaluation(doc)

    buf = io.BytesIO()
    count = export_stl(evaluation, buf, entity_ids=[box.id, part.id], binary=True, name='assembly')
    assert count == 24

    raw = buf.getvalue()
    assert len(raw) == 80 + 4 + 24 * 50
    assert b'ArchForge STL - assembly' in raw[:80]
    (triangle_count,) = struct.unpack('<I', raw[80:84])
    assert triangle_count == 24


def test_document_stl_export_is_frozen_until_exact_solid_backend(tmp_path):
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0})
    doc.add(box)
    out_file = tmp_path / 'exported_box.stl'

    with pytest.raises(IncompleteSolidValidityError, match='BRepCheck_Analyzer'):
        export_document_stl(doc, out_file, entity_ids=[box.id], binary=True)
    assert not out_file.exists()


def test_document_ascii_export_is_frozen_until_exact_solid_backend(tmp_path):
    doc = Document()
    part = Entity('mechanical_part', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 2.0, 'height': 3.0, 'rotation': 0})
    doc.add(part)
    out_file = tmp_path / 'part_ascii.stl'

    with pytest.raises(IncompleteSolidValidityError, match='BRepCheck_Analyzer'):
        export_document_stl(doc, out_file, entity_ids=[part.id], binary=False, name='part_mesh')
    assert not out_file.exists()


def test_architectural_wall_requires_exact_solid_proof_before_export(tmp_path):
    doc = Document()
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'z': 0, 'x2': 4.0, 'y2': 0, 'height': 3.0, 'thickness': 0.2})
    doc.add(wall)
    out_file = tmp_path / 'wall.stl'

    with pytest.raises(IncompleteSolidValidityError, match='self-intersections are not proven absent'):
        export_document_stl(doc, out_file, entity_ids=[wall.id], binary=True)
    assert not out_file.exists()
