import pytest

from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from archforge.geometry.backend import GeometryBody, GeometryEvaluation
from archforge.geometry.fabrication import assess_fabrication, require_fabrication_ready
from archforge.geometry.preview import PreviewBackend
from archforge.geometry.validated_mesh import ValidatedMeshBackend


def test_preview_geometry_is_never_mislabeled_printable():
    doc=Document(); b=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});doc.add(b)
    report=assess_fabrication(PreviewBackend().evaluate(doc),[b.id])
    assert not report.ready
    codes={f.code for f in report.findings}
    assert {'insufficient_geometry_quality','not_proven_watertight','not_proven_manifold'} <= codes


def test_active_sculpt_must_be_applied_before_fabrication():
    body=GeometryBody('wall-1','wall',('wall-1:exterior',),('sculpt-1',),payload=object(),quality='fabrication_mesh',modifiers_applied=False,watertight=True,manifold=True)
    report=assess_fabrication(GeometryEvaluation('test',(body,)))
    assert not report.ready
    assert any(f.code=='modifiers_not_applied' for f in report.findings)


def test_verified_fabrication_mesh_passes_gate():
    body=GeometryBody('part-1','mechanical_part',('part-1:top',),(),payload=object(),quality='fabrication_mesh',modifiers_applied=True,watertight=True,manifold=True)
    evaluation=GeometryEvaluation('test',(body,))
    assert assess_fabrication(evaluation).ready
    require_fabrication_ready(evaluation)


def test_exactly_coincident_selected_bodies_are_not_collectively_fabrication_ready():
    doc=Document()
    a=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0})
    b=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0})
    doc.add(a);doc.add(b)
    evaluation=ValidatedMeshBackend().evaluate(doc)
    assert evaluation.body(a.id).quality=='fabrication_mesh'
    assert evaluation.body(b.id).quality=='fabrication_mesh'
    report=assess_fabrication(evaluation,[a.id,b.id])
    assert not report.ready
    assert any(f.code=='interbody_duplicate_face' for f in report.findings)


def test_missing_selected_body_is_blocker():
    report=assess_fabrication(GeometryEvaluation('test',()),['missing'])
    assert not report.ready
    assert report.findings[0].code=='missing_body'


def test_empty_evaluation_is_not_fabrication_ready():
    report=assess_fabrication(GeometryEvaluation('test',()))
    assert not report.ready
    assert any(f.code=='empty_fabrication_scope' for f in report.findings)


def test_explicit_empty_selection_is_not_fabrication_ready():
    body=GeometryBody('part-1','mechanical_part',('part-1:top',),(),payload=object(),quality='fabrication_mesh',modifiers_applied=True,watertight=True,manifold=True)
    report=assess_fabrication(GeometryEvaluation('test',(body,)),[])
    assert not report.ready
    assert any(f.code=='empty_fabrication_scope' for f in report.findings)


def test_require_ready_raises_with_actionable_reason():
    body=GeometryBody('x','box',(),quality='preview')
    with pytest.raises(ValueError,match='fabrication gate failed'):
        require_fabrication_ready(GeometryEvaluation('preview',(body,)))
