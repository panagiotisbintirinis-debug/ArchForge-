"""The delivered lighting content must work in a fresh installation, not only an agent's data folder."""
import json

import pytest

from archforge.library import assets


def test_shipped_fixtures_install_once_without_overwriting_user_content(tmp_path, monkeypatch):
    from archforge.library.bundled_lights import seed_lights
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    assets._CACHE.clear()
    ids = seed_lights()
    assert len(ids) == 16
    assert seed_lights() == []
    records = [assets.load_asset(aid) for aid in ids]
    assert sum(len(r['lights']) for r in records) == 26
    for r in records:
        assert r['vertices'] and r['triangles'] and r['plan']['outline']
        assert r['provenance']['redistributable']
        assert r['light_capabilities']['dimming']
        for size in (40, 80):
            assert (assets.asset_dir() / 'thumbs' / f"{r['id']}_{size}.png").is_file()
    path = assets.asset_dir() / f'{ids[0]}.json'
    record = json.loads(path.read_text(encoding='utf-8'))
    record['name'] = 'User name'
    path.write_text(json.dumps(record),encoding='utf-8')
    seed_lights()
    assert json.loads(path.read_text(encoding='utf-8'))['name'] == 'User name'


def test_real_pack_replacement_preserves_instance_and_renders_emitters(tmp_path, monkeypatch):
    from archforge.library.bundled_lights import seed_lights
    from archforge.core.commands import CommandStack, AddEntity, UpdateEntity
    from archforge.core.model import Document, Entity
    from archforge.ui.library_instance_integration import library_instance_params
    from archforge.library.lighting import instance_light_specs
    from archforge.mep.lighting import replace_fixture, replacement_choices
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    assets._CACHE.clear()
    ids = seed_lights()
    record = assets.load_asset(ids[0])
    doc = Document(); stack = CommandStack(doc)
    lamp = Entity('library_object', library_instance_params(record, x=2, y=3, z=1))
    lamp.params.update(rotation=35, light_level=0.4, light_enabled=0, automation_group='Local group')
    stack.execute(AddEntity(lamp))
    assert {ref for label, kind, ref in replacement_choices(lamp)} == set(ids)
    command, new = replace_fixture(doc, lamp.id, 'library', ids[1])
    stack.execute(command)
    assert [new.params[k] for k in ('x','y','z','rotation','light_level','light_enabled')] == [2,3,1,35,0.4,0]
    assert new.params.get('automation_group') == 'Local group'
    assert not instance_light_specs(new)
    stack.execute(UpdateEntity(new.id, {'light_enabled': 1}))
    assert instance_light_specs(doc.get(new.id))
    stack.undo()
    stack.undo()
    assert doc.get(lamp.id).params['asset'] == ids[0]


def test_emissive_parts_are_tagged_for_the_project_light_switch(tmp_path, monkeypatch):
    from archforge.library.bundled_lights import seed_lights
    from archforge.core.model import Document, Entity
    from archforge.ui.library_instance_integration import library_instance_params
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    assets._CACHE.clear()
    record = assets.load_asset(seed_lights()[0])
    doc = Document()
    obj = Entity('library_object', library_instance_params(record, x=0, y=0, z=0))
    obj.params['light_level'] = 0.4
    doc.add(obj)
    evaluation = IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
    objects = build_pbr_scene_payload(evaluation, doc=doc)['objects']
    glow = [o for o in objects if o['material'].get('projectLightEmissive')]
    assert glow
    assert all(o['material']['emissiveIntensity'] == pytest.approx(0.4) for o in glow)


def test_project_switch_controls_emissive_in_the_javascript_renderer():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QJSEngine
    from archforge.ui.lighting_system import _lighting_js
    app = QApplication.instance() or QApplication([])
    engine = QJSEngine()
    prefix = '''
      var window = {};
      function wakeRender() { throw new Error('render loop not initialized'); }
      const THREE = {Group: class {constructor() {this.children=[];} add(x) {this.children.push(x);}}};
      const scene = {add() {}};
      const lamp = {userData: {projectLightEmissive: 0.4}, emissiveIntensity: 0.4};
      const selectionHighlight = {userData: {}, emissiveIntensity: 0.28};
      window.lamp = lamp;
      window.selectionHighlight = selectionHighlight;
      const modelRoot = {traverse(f) {f({material: [lamp, selectionHighlight]});}};
    '''
    result = engine.evaluate(prefix + _lighting_js())
    assert not result.isError(), result.toString()
    for mode, switch, expected in [('day','auto',0), ('night','auto',0.4), ('night','off',0),
                                    ('day','on',0.4), ('day','auto',0), ('night','auto',0.4)]:
        result = engine.evaluate(f'''window.setArchitecturalLights({{lights:[],project_lights:"{switch}"}});
                                     window.setArchitecturalLightingMode("{mode}"); window.lamp.emissiveIntensity;''')
        assert not result.isError(), result.toString()
        assert result.toNumber() == pytest.approx(expected)
    assert engine.evaluate('window.selectionHighlight.emissiveIntensity').toNumber() == pytest.approx(0.28)


def test_open_popup_tracks_undo_and_external_property_edits(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication, QCheckBox, QSlider
    from archforge.ui.main_window import MainWindow
    from archforge.ui.lighting_panel import LightingStrip
    from archforge.library.bundled_lights import seed_lights
    from archforge.ui.library_instance_integration import library_instance_params
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    assets._CACHE.clear()
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        record = assets.load_asset(seed_lights()[0])
        e = Entity('library_object', library_instance_params(record, x=0, y=0, z=0))
        w.stack.execute(AddEntity(e))
        strip = w._lighting_strip
        strip.refresh()
        title = next(iter(strip.buttons))
        menu = strip.buttons[title].menu()
        strip._fill(menu, title)
        row = next(a.defaultWidget() for a in menu.actions() if hasattr(a, 'defaultWidget') and a.defaultWidget())
        on = row.findChild(QCheckBox, 'lightRowOn')
        dim = row.findChild(QSlider, 'lightRowDim')
        on.setChecked(False)
        w.stack.undo()
        strip.refresh()
        assert on.isChecked()
        # An Inspector edit must be reflected without writing a second command from the popup's signals.
        w.stack.execute(UpdateEntity(e.id, {'light_level':0.3}))
        strip.refresh()
        assert dim.value() == 30
        w.stack.undo()
        strip.refresh()
        assert dim.value() == 100
        assert w.doc.get(e.id).params['light_enabled'] == 1
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_double_click_on_a_luminaire_in_3d_opens_its_properties_even_with_the_panel_closed(tmp_path, monkeypatch):
    """Owner 29/10: «δεν μπορώ να πιάσω το φωτιστικό στο 3Δ — πώς θα ελέγξω το αποτέλεσμα»: the click selected it, but
    with Ιδιότητες closed nothing showed its switch and dimmer."""
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.pbr_viewport import PBRInteractionBridge
    from archforge.library.bundled_lights import seed_lights
    from archforge.ui.library_instance_integration import library_instance_params
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    assets._CACHE.clear()
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w.show()
        record = assets.load_asset(seed_lights()[0])
        lamp = Entity('library_object', library_instance_params(record, x=0, y=0, z=2))
        w.stack.execute(AddEntity(lamp))
        w.dock.hide()
        PBRInteractionBridge(w.pbr_view).openEntity(lamp.id)
        app.processEvents()
        assert w.doc.selection == [lamp.id]
        assert w.dock.isVisible()
        labels = [w.form.itemAt(i, w.form.ItemRole.LabelRole).widget().text() for i in range(w.form.rowCount())
                  if w.form.itemAt(i, w.form.ItemRole.LabelRole) and w.form.itemAt(i, w.form.ItemRole.LabelRole).widget()]
        assert 'Αναμμένο' in labels and 'Φωτεινότητα' in labels, labels    # its switch and dimmer are there
    finally:
        w._mark_clean(); w.close(); app.processEvents()
