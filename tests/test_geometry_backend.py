import math

from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from archforge.geometry.backend import ContractBackend
from archforge.geometry.preview import PreviewBackend


def test_contract_backend_carries_enabled_modifier_to_body():
    doc=Document(); w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':4,'y2':0,'height':3,'thickness':0.2}); doc.add(w)
    m=SurfaceModifier(SurfaceRef(w.id,'exterior',{'uv_bounds':[0.2,0.4,0.6,0.8]}),'pull',{'amount':0.3}); doc.add_surface_modifier(m)
    result=ContractBackend().evaluate(doc)
    assert result.ok
    body=result.body(w.id)
    assert m.id in body.modifier_ids
    assert f'{w.id}:exterior' in body.surface_keys


def test_disabled_modifier_is_preserved_in_document_but_not_active_geometry():
    doc=Document(); w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':4,'y2':0,'height':3,'thickness':0.2}); doc.add(w)
    m=SurfaceModifier(SurfaceRef(w.id,'exterior',{}),'pull',{'amount':0.3},enabled=False); doc.add_surface_modifier(m)
    result=ContractBackend().evaluate(doc)
    assert m.id in doc.surface_modifiers
    assert m.id not in result.body(w.id).modifier_ids


def test_preview_wall_bounds_include_thickness_and_height():
    doc=Document(); w=Entity('wall',{'x1':0,'y1':0,'z':1,'x2':4,'y2':0,'height':3,'thickness':0.2}); doc.add(w)
    result=PreviewBackend().evaluate(doc); assert result.ok
    lo,hi=result.body(w.id).payload.bounds
    assert lo == (0.0,-0.1,1.0)
    assert hi == (4.0,0.1,4.0)


def test_preview_pod_respects_hard_floor_boundary():
    doc=Document(); p=Entity('pod',{'cx':2,'cy':3,'floor_level':1.5,'diameter_x':6,'diameter_y':4,'height':3,'shell_thickness':0.15,'rotation':0}); doc.add(p)
    result=PreviewBackend().evaluate(doc); assert result.ok
    lo,hi=result.body(p.id).payload.bounds
    assert lo[2] == 1.5
    assert hi[2] == 4.5
    assert result.body(p.id).payload.primitive == 'upper_ellipsoid'


def test_preview_rotated_box_has_world_bounds():
    doc=Document(); b=Entity('box',{'x':10,'y':20,'z':2,'width':2,'depth':1,'height':3,'rotation':90}); doc.add(b)
    result=PreviewBackend().evaluate(doc); assert result.ok
    lo,hi=result.body(b.id).payload.bounds
    assert math.isclose(lo[0],9.0,abs_tol=1e-9) and math.isclose(hi[0],10.0,abs_tol=1e-9)
    assert math.isclose(lo[1],20.0,abs_tol=1e-9) and math.isclose(hi[1],22.0,abs_tol=1e-9)
    assert (lo[2],hi[2]) == (2.0,5.0)


def test_mechanical_part_uses_kinematic_transform_in_same_backend():
    doc=Document(); part=Entity('mechanical_part',{'x':5,'y':6,'z':1,'width':2,'depth':1,'height':1,'rotation':0}); doc.add(part)
    result=PreviewBackend().evaluate(doc); assert result.ok
    lo,hi=result.body(part.id).payload.bounds
    assert lo == (5.0,6.0,1.0)
    assert hi == (7.0,7.0,2.0)
