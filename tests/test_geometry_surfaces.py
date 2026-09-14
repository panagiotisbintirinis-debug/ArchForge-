import pytest

from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceModifier, SurfaceRef
from archforge.geometry.surfaces import resolve_surface, surface_roles


def wall():
    return Entity('wall', {'x1':0,'y1':0,'z':0,'x2':4,'y2':0,'height':3,'thickness':0.2})


def test_wall_has_stable_architectural_surface_roles():
    doc=Document(); w=wall(); doc.add(w)
    assert surface_roles(doc,w.id) == ('exterior','interior','top','start','end','bottom')
    assert resolve_surface(doc,w.id,'exterior').key == f'{w.id}:exterior'


def test_unknown_surface_role_is_rejected_at_modifier_creation():
    doc=Document(); w=wall(); doc.add(w)
    mod=SurfaceModifier(SurfaceRef(w.id,'random_mesh_face',{}),'pull',{'amount':0.2})
    with pytest.raises(ValueError, match='unsupported semantic surface role'):
        doc.add_surface_modifier(mod)


def test_non_deformable_semantic_surface_rejects_sculpt():
    doc=Document(); w=wall(); doc.add(w)
    mod=SurfaceModifier(SurfaceRef(w.id,'bottom',{}),'pull',{'amount':0.1})
    with pytest.raises(ValueError, match='not deformable'):
        doc.add_surface_modifier(mod)


def test_room_ceiling_is_valid_sculpt_target_without_making_room_a_solid():
    doc=Document(); r=Entity('room',{'points':[(0,0),(3,0),(3,3),(0,3)],'z':0,'height':2.8}); doc.add(r)
    mod=SurfaceModifier(SurfaceRef(r.id,'ceiling',{'uv_center':[0.5,0.5]}),'recess',{'amount':0.15})
    doc.add_surface_modifier(mod)
    assert doc.surface_modifiers[mod.id].target.surface_role == 'ceiling'
    assert not resolve_surface(doc,r.id,'ceiling').fabrication_surface


def test_pod_shell_and_generated_junction_are_both_semantic_targets():
    doc=Document(); p=Entity('pod',{'cx':0,'cy':0,'floor_level':1,'diameter_x':6,'diameter_y':5,'height':3,'shell_thickness':0.15,'rotation':0}); doc.add(p)
    assert set(surface_roles(doc,p.id)) == {'pod_shell','junction','floor'}
    doc.add_surface_modifier(SurfaceModifier(SurfaceRef(p.id,'junction',{}),'inflate',{'amount':0.25}))
