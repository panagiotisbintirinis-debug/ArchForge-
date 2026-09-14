import pytest

from archforge.core.model import Document,Entity
from archforge.geometry.selection import BrushSpec,SurfaceHit,sculpt_modifier_from_hit


def make_wall(doc):
    w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':0.2});doc.add(w);return w


def test_surface_hit_becomes_persistent_semantic_sculpt_without_face_index():
    doc=Document();w=make_wall(doc)
    hit=SurfaceHit(w.id,'exterior',(2.5,-0.1,2.2),(0,-1,0),(0.5,0.73))
    mod=sculpt_modifier_from_hit(doc,hit,BrushSpec(0.6,0.8,'smooth'),'pull',0.35)
    doc.add_surface_modifier(mod)
    region=mod.target.subregion
    assert region['uv_center']==[0.5,0.73]
    assert region['radius']==0.6 and region['strength']==0.8
    assert not any('face' in key.lower() or 'triangle' in key.lower() for key in region)


def test_surface_hit_rejects_unknown_role_before_sculpt():
    doc=Document();w=make_wall(doc)
    hit=SurfaceHit(w.id,'mesh_face_42',(0,0,0),(0,1,0),(0,0))
    with pytest.raises(ValueError):sculpt_modifier_from_hit(doc,hit,BrushSpec(1),'pull',0.1)


def test_brush_validation_rejects_invalid_radius_strength_and_falloff():
    with pytest.raises(ValueError):BrushSpec(0).validate()
    with pytest.raises(ValueError):BrushSpec(1,1.1).validate()
    with pytest.raises(ValueError):BrushSpec(1,0.5,'magic').validate()


def test_world_only_hit_is_allowed_for_surface_without_uv_mapping_yet():
    doc=Document();w=make_wall(doc)
    mod=sculpt_modifier_from_hit(doc,SurfaceHit(w.id,'top',(2,0,3),(0,0,1)),BrushSpec(0.4),'recess',0.1)
    assert 'uv_center' not in mod.target.subregion
    assert mod.target.subregion['world_center']==[2.0,0.0,3.0]
