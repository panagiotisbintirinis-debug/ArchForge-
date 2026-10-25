import copy
import json
import math
from types import SimpleNamespace

import pytest

from archforge.core.model import Document, Entity
from archforge.core.commands import AddEntity, MoveEntities, RotateEntities, UpdateEntity
from archforge.core.commands import CommandStack


def _source():
    return dict(kind='spot', position=[0.1, 0.0, 0.2], direction=[0, 0, -1],
                intensity_cd=100.0, color=[1.0, 0.5, 0.25], range_m=0.0,
                outer_cone_rad=math.pi/6, inner_cone_rad=0.0)


def test_library_light_follows_instance_and_survives_undo_and_file_roundtrip():
    from archforge.library.lighting import instance_light_specs
    from archforge.ui.library_instance_integration import library_instance_params
    record = dict(id='a-test', size=[1, 1, 1], lights=[_source()])
    params = library_instance_params(record, x=2, y=3, z=1)
    assert params['light_sources'] == record['lights']
    record['lights'][0]['intensity_cd'] = 777  # placements own their emission settings
    doc = Document(); stack = CommandStack(doc)
    obj = Entity('library_object', params)
    stack.execute(AddEntity(obj))
    spec = instance_light_specs(doc.get(obj.id))[0]
    assert spec['position'] == pytest.approx([2.1, 3, 1.2])
    assert spec['intensity'] == 100
    stack.execute(MoveEntities([obj.id], 4, 5, 1))
    stack.execute(RotateEntities([obj.id], 90))
    spec = instance_light_specs(doc.get(obj.id))[0]
    assert spec['position'] == pytest.approx([6, 8.1, 2.2])
    stack.execute(UpdateEntity(obj.id, {'light_level': 0.25}))
    assert instance_light_specs(doc.get(obj.id))[0]['intensity'] == 25
    stack.undo()
    assert instance_light_specs(doc.get(obj.id))[0]['intensity'] == 100
    loaded = Document.from_dict(json.loads(json.dumps(doc.to_dict())))
    assert instance_light_specs(loaded.get(obj.id)) == instance_light_specs(doc.get(obj.id))
    stack.undo(); stack.undo(); stack.undo()
    assert obj.id not in doc.entities
    stack.redo(); stack.redo(); stack.redo()
    assert instance_light_specs(doc.get(obj.id)) == instance_light_specs(loaded.get(obj.id))


def test_disabled_hidden_and_mirrored_scaled_instances():
    from archforge.library.lighting import instance_light_specs
    from archforge.ui.library_instance_integration import library_instance_params
    p = library_instance_params(dict(id='a-test', size=[1,1,1], lights=[_source()]), x=0, y=0, z=0)
    p.update(width=2, height=3, mirror=1)
    e = Entity('library_object', p)
    assert instance_light_specs(e)[0]['position'] == pytest.approx([-0.2,0,0.6])
    e.params['light_level'] = 0
    assert instance_light_specs(e) == []
    e.params['light_level'] = 1; e.visible = False
    assert instance_light_specs(e) == []


def test_lit_glb_import_keeps_light_at_normalised_geometry_origin(tmp_path, monkeypatch):
    from archforge.library import assets
    from archforge.library.lighting import read_gltf_lighting
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path/'data'))
    doc = dict(asset={'version':'2.0'}, scene=0, scenes=[{'nodes':[0]}],
               nodes=[{'translation':[2,3,4], 'extensions':{'KHR_lights_punctual':{'light':0}}}],
               extensions={'KHR_lights_punctual':{'lights':[{'type':'point','intensity':42, 'color':[1,.5,.2]}]}})
    path = tmp_path/'light.gltf'; path.write_text(json.dumps(doc))
    lighting = read_gltf_lighting(path)
    assert lighting['sources'][0]['position'] == [2,-4,3]
    tris = [((1,-5,2),(3,-5,2),(2,-3,4))]
    aid,_ = assets.store_asset('test',tris,{'source':'test'},lighting=lighting)
    r = assets.load_asset(aid)
    assert r['lights'][0]['position'] == pytest.approx([0,0,1])
    other = copy.deepcopy(lighting); other['sources'][0]['intensity_cd'] = 43
    bid,_ = assets.store_asset('test',tris,{'source':'test'},lighting=other)
    assert bid != aid


def test_renderer_receives_library_light_after_drag_drop(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from archforge.library import assets
    from archforge.ui.main_window import MainWindow
    from archforge.ui.lighting_system import install_lighting_system
    from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
    install_rendering_quality_upgrade()
    install_lighting_system()
    from archforge.ui.library_drag import LibraryCarry
    monkeypatch.setenv('ARCHFORGE_DATA',str(tmp_path))
    aid,_ = assets.store_asset('Lit fixture', [((-.1,-.1,0),(.1,-.1,0),(0,.1,.2))],
                              {'source':'test'},lighting={'sources':[_source()]})
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        carry = LibraryCarry(w,('asset',aid)); carry.move(2,3,free=True)
        eid = carry._commit(2,3,None)
        assert len(w.doc.entities) == 1
        obj = w.doc.get(eid)
        assert obj.params['light_sources']
        lights = w.pbr_view._lighting_payload()['lights']
        assert len(lights)==1 and lights[0]['intensity']==100
        from archforge.ui.library_icons import library_icon
        assert not library_icon(('asset',aid)).isNull()
        w.stack.undo(); assert not w.pbr_view._lighting_payload()['lights']
        w.stack.redo(); assert len(w.pbr_view._lighting_payload()['lights']) == 1
        # Double-click / click placement must not lose emission through the
        # summary-only list_assets record, unlike a direct library drag.
        w._choose_library_asset(aid)
        clicked = w._place_library_object(2,3)
        assert clicked.params['light_sources'] == obj.params['light_sources']
    finally:
        w._mark_clean(); w.close(); app.processEvents()


@pytest.mark.parametrize('bad',[float('nan'),-1,float('inf')])
def test_invalid_lamp_intensity_rejected(bad):
    from archforge.library.lighting import validate_sources
    s = _source(); s['intensity_cd']=bad
    with pytest.raises(ValueError): validate_sources([s])


def test_emissive_glass_does_not_block_its_own_light(tmp_path, monkeypatch):
    from archforge.library import assets
    from archforge.ui.library_instance_integration import library_instance_params
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    monkeypatch.setenv('ARCHFORGE_DATA',str(tmp_path))
    triangles = [((-.1,-.1,0),(.1,-.1,0),(0,.1,.2))]
    aid,_=assets.store_asset('globe',triangles,{'source':'test'},colors=['#ffffff'],
                            part_names={'#ffffff':'Globe'},
                            lighting={'sources':[_source()],'emissive_materials':{'Globe':'#ffcc88'}})
    doc=Document();obj=Entity('library_object',library_instance_params(assets.load_asset(aid),x=0,y=0,z=0))
    doc.add(obj)
    def objects():
        evaluation=IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
        return build_pbr_scene_payload(evaluation,doc=doc)['objects']
    part=next(o for o in objects() if o['id']==obj.id)
    assert part['material']['emissiveIntensity']==1
    assert part['cast_shadow'] is False
    doc.update(obj.id,{'light_enabled':0})
    part=next(o for o in objects() if o['id']==obj.id)
    assert part['material']['emissiveIntensity']==0


def test_colour_override_and_ui_level_are_undoable(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QCheckBox, QSlider, QComboBox, QFormLayout
    from archforge.ui.library_light_properties import add_rows
    from archforge.ui.library_instance_integration import library_instance_params
    from archforge.library.lighting import instance_light_specs
    app=QApplication.instance() or QApplication([])
    doc=Document();stack=CommandStack(doc)
    obj=Entity('library_object',library_instance_params(dict(id='x',size=[1,1,1],lights=[_source()]),x=0,y=0,z=0));doc.add(obj)
    form=QFormLayout()
    window=SimpleNamespace(doc=doc,form=form,
                           _set_entity_choice=lambda eid,k,v:stack.execute(UpdateEntity(eid,{k:v})))
    add_rows(window,obj)
    widgets=[form.itemAt(i).widget() for i in range(form.count())]
    checkbox=next(w for w in widgets if isinstance(w,QCheckBox))
    checkbox.setChecked(False);assert instance_light_specs(obj)==[]
    stack.undo();assert instance_light_specs(obj)
    slider=next(w for w in widgets if isinstance(w,QSlider))
    slider.setValue(40);slider.sliderReleased.emit()
    assert instance_light_specs(obj)[0]['intensity']==40
    color=next(w for w in widgets if isinstance(w,QComboBox))
    color.setCurrentIndex(color.findData(4000.));color.activated.emit(color.currentIndex())
    assert instance_light_specs(obj)[0]['kelvin']==4000
    color.setCurrentIndex(0);color.activated.emit(0)
    assert instance_light_specs(obj)[0]['color']==[1,.5,.25]
