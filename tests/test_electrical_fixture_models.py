import json
import math

import pytest

from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.model import Document
from archforge.library import assets
from archforge.library.bundled_lights import seed_lights
from archforge.mep.lighting import replace_fixture, replacement_choices
from tests.test_electrical import _house, _pt


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    assets._CACHE.clear()
    return [assets.load_asset(aid) for aid in seed_lights()]


def test_electrical_fixture_accepts_real_model_without_changing_circuit_or_state(installed):
    from archforge.mep.electrical import design_circuits
    doc=Document(); stack=CommandStack(doc); _house(stack)
    _pt(stack,'panel',0.3,3)
    _pt(stack,'switch',0.3,2,automation_group='Living')
    lamp=_pt(stack,'spot',2,3,automation_group='Living',dim_level=0.4,light_on=0,
             power_w=17,kelvin=4000,aim_tilt_deg=50,aim_azimuth_deg=90)
    wiring=design_circuits(doc)
    before=doc.to_dict()
    assert {ref for _,kind,ref in replacement_choices(lamp) if kind=='library'} == {r['id'] for r in installed}
    record=next(r for r in installed if r['light_capabilities']['aimable'])
    command,new=replace_fixture(doc,lamp.id,'library',record['id'])
    stack.execute(command)
    current=doc.get(lamp.id)
    assert new.id==lamp.id and current.kind=='electrical_point'
    assert current.params['fixture_asset']==record['id']
    assert {k:v for k,v in current.params.items() if k!='fixture_asset'} == lamp.params
    assert design_circuits(doc)==wiring
    assert len(doc.entities)==len(before['entities'])
    loaded=Document.from_dict(json.loads(json.dumps(doc.to_dict())))
    assert loaded.get(lamp.id).params==current.params
    stack.undo();assert doc.to_dict()['entities']==before['entities']
    stack.redo();assert doc.get(lamp.id).params['fixture_asset']==record['id']


def test_bound_model_geometry_emitters_and_aim_share_the_native_controls(installed):
    from archforge.mep.fixture_models import attached_instance, attached_light_specs
    from archforge.mep.lighting import fixture_aimable
    from archforge.geometry.mesh import _payload
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc=Document();stack=CommandStack(doc);_house(stack)
    lamp=_pt(stack,'spot',2,3,dim_level=0.4,kelvin=4000,aim_tilt_deg=60,aim_azimuth_deg=90)
    r=next(r for r in installed if r['light_capabilities']['aimable'])
    command,_=replace_fixture(doc,lamp.id,'library',r['id']);stack.execute(command)
    assert fixture_aimable(doc.get(lamp.id))
    specs=attached_light_specs(doc,doc.get(lamp.id))
    assert len(specs)==len(r['lights']) and specs[0]['owner_id']==lamp.id
    assert specs[0]['intensity']==pytest.approx(r['lights'][0]['intensity_cd']*0.4)
    assert specs[0]['kelvin']==4000
    assert [t-p for t,p in zip(specs[0]['target'],specs[0]['position'])]==pytest.approx([math.sin(math.pi/3),0,-.5])
    ev=IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
    objects=[o for o in build_pbr_scene_payload(ev,doc=doc)['objects'] if o['id']==lamp.id]
    assert objects and sum(len(o['triangles']) for o in objects)==len(r['triangles'])
    assert any(o['material'].get('projectLightEmissive') for o in objects)
    stack.execute(UpdateEntity(lamp.id,{'light_on':0}))
    assert attached_light_specs(doc,doc.get(lamp.id))==[]
    fixed=next(r for r in installed if not r['light_capabilities']['aimable'])
    command,_=replace_fixture(doc,lamp.id,'library',fixed['id']);stack.execute(command)
    assert not fixture_aimable(doc.get(lamp.id))


def test_strip_cannot_be_replaced_with_a_point_model(installed):
    doc=Document();stack=CommandStack(doc)
    strip=_pt(stack,'led_strip',0,0,x2=2,y2=0)
    assert not any(kind=='library' for _,kind,ref in replacement_choices(strip))
    with pytest.raises(ValueError):replace_fixture(doc,strip.id,'library',installed[0]['id'])


def test_cached_fixture_mesh_follows_a_changed_ceiling_with_its_emitters(installed):
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.mep.fixture_models import attached_instance
    doc=Document();stack=CommandStack(doc);_house(stack)
    lamp=_pt(stack,'light',2,3)
    ceiling=next(r for r in installed if r['light_capabilities']['mount']=='ceiling')
    command,_=replace_fixture(doc,lamp.id,'library',ceiling['id']);stack.execute(command)
    cache=IncrementalEvaluationCache(SculptedPreviewBackend())
    cache.sync(doc)
    for wall in list(doc.entities.values()):
        if wall.kind=='wall':stack.execute(UpdateEntity(wall.id,{'height':1.8}))
    result=cache.sync(doc)
    body=next(b for b in result.bodies if b.entity_id==lamp.id)
    proxy=attached_instance(doc,doc.get(lamp.id))
    assert min(v[2] for v in body.payload.vertices)==pytest.approx(proxy.params['z'])
