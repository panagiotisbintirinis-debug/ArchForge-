import io
import struct
import pytest

from archforge.core.model import Document, Entity
from archforge.geometry.backend import GeometryBody, GeometryEvaluation
from archforge.geometry.mesh import MeshPayload
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.validated_mesh import ValidatedMeshBackend
from archforge.geometry.fabrication import (
    assess_fabrication,
    require_fabrication_ready,
    export_stl_text,
    export_stl_binary,
    export_stl,
    export_document_stl,
)


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


def test_stl_export_ascii_box():
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 2.0, 'depth': 1.0, 'height': 3.0, 'rotation': 0})
    doc.add(box)
    evaluation = ValidatedMeshBackend().evaluate(doc)

    text = export_stl_text(evaluation, [box.id], name='test_box')
    lines = text.strip().splitlines()
    assert lines[0] == "solid test_box"
    assert lines[-1] == "endsolid test_box"

    # Box has 12 triangles (2 per 6 faces)
    facet_count = sum(1 for line in lines if line.strip().startswith("facet normal"))
    assert facet_count == 12
    vertex_count = sum(1 for line in lines if line.strip().startswith("vertex"))
    assert vertex_count == 36


def test_stl_export_binary_box_and_part():
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0})
    part = Entity('mechanical_part', {'x': 5, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0})
    doc.add(box)
    doc.add(part)
    evaluation = ValidatedMeshBackend().evaluate(doc)

    buf = io.BytesIO()
    count = export_stl(evaluation, buf, entity_ids=[box.id, part.id], binary=True, name='assembly')
    assert count == 24  # 12 triangles each

    raw = buf.getvalue()
    # Binary STL format: 80 bytes header + 4 bytes count + 50 bytes per facet
    expected_size = 80 + 4 + 24 * 50
    assert len(raw) == expected_size

    header = raw[:80]
    assert b"ArchForge STL - assembly" in header

    (triangle_count,) = struct.unpack('<I', raw[80:84])
    assert triangle_count == 24


def test_stl_export_document_helper(tmp_path):
    doc = Document()
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 1.0, 'height': 1.0, 'rotation': 0})
    doc.add(box)

    out_file = tmp_path / "exported_box.stl"
    count = export_document_stl(doc, out_file, entity_ids=[box.id], binary=True)
    assert count == 12
    assert out_file.exists()
    assert out_file.stat().st_size == 80 + 4 + 12 * 50


def test_stl_export_ascii_file(tmp_path):
    doc = Document()
    part = Entity('mechanical_part', {'x': 0, 'y': 0, 'z': 0, 'width': 1.0, 'depth': 2.0, 'height': 3.0, 'rotation': 0})
    doc.add(part)

    out_file = tmp_path / "part_ascii.stl"
    count = export_document_stl(doc, out_file, entity_ids=[part.id], binary=False, name='part_mesh')
    assert count == 12
    assert out_file.exists()
    content = out_file.read_text(encoding='utf-8')
    assert "solid part_mesh" in content
    assert "endsolid part_mesh" in content
