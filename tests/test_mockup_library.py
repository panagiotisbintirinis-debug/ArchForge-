"""Library UI: import a catalog, place by click, resize with locked proportions."""
import os
import sqlite3
import struct

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.library import assets
from archforge.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    assets._CACHE.clear()


def _catalog(path):
    c = [(x * 80, y * 32, z * 34) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    quads = [[c[i] for i in q] for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))]
    rec = b'\xcd\xab\x74\x00\xaf\x08' + b'\xff' * 4 + struct.pack('<I', len(quads))
    for pl in quads:
        rec += struct.pack('<HHIH', 4, 0x1000, 0, 0) + b''.join(struct.pack('<3d', *v) for v in pl)
        rec += struct.pack('<4i', -1, -1, -1, -1) + struct.pack('<I', 0) + struct.pack('<2d', 20.0, 20.0)
    blob = b'\x01\x00\x00\x00\x01' + rec + b'\x00' * 1200
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE LibraryObjects (LibraryObjectId INTEGER PRIMARY KEY, Name TEXT, Type INTEGER);
        CREATE TABLE SymbolData4LibraryObjects (LibraryObjectId INTEGER PRIMARY KEY, SymbolData BLOB);""")
    conn.execute("INSERT INTO LibraryObjects VALUES (3, 'Sofa', 14)")
    conn.execute("INSERT INTO SymbolData4LibraryObjects VALUES (3, ?)", (blob,))
    conn.commit(); conn.close()


def test_import_place_and_resize_sofa_through_the_ui(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(); window.show(); app.processEvents()
    try:
        assert 'Βιβλιοθήκη' in [m.title() for m in window.menuBar().findChildren(type(window._mockup_library_menu))]
        cat = tmp_path / 'Sofas.calib'
        _catalog(cat)
        imported = window._import_hd_catalog(str(cat), object_ids=[3])
        assert len(imported) == 1
        assert window._library_item_count() == 1
        window._choose_library_asset(imported[0])
        assert window.plan_view.controller.tool == 'library_place'
        window.plan_view.sitePointRequested.emit('library_place', 4.0, 2.0)
        objs = [e for e in window.doc.entities.values() if e.kind == 'library_object']
        assert len(objs) == 1
        sofa = objs[0]
        assert (sofa.params['x'], sofa.params['y']) == (4.0, 2.0)
        assert [sofa.params[k] for k in ('width', 'depth', 'height')] == pytest.approx([2.032, 0.8128, 0.8636])
        window._commit_property(sofa.id, 'width', 2.54)
        p = window.doc.get(sofa.id).params
        assert [p[k] for k in ('width', 'depth', 'height')] == pytest.approx([2.54, 1.016, 1.0795])
        window.stack.undo()
        assert window.doc.get(sofa.id).params['width'] == pytest.approx(2.032)
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_user_gltf_import_lands_in_library(tmp_path):
    import base64
    import json
    raw = b''.join(struct.pack('<3f', *v) for v in [(0, 0, 0), (0.6, 0, 0), (0.6, 0.9, 0.5)])
    doc = {'asset': {'version': '2.0'}, 'scenes': [{'nodes': [0]}], 'nodes': [{'mesh': 0}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}],
           'buffers': [{'byteLength': 36, 'uri': 'data:application/octet-stream;base64,' + base64.b64encode(raw).decode()}],
           'bufferViews': [{'buffer': 0, 'byteLength': 36}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3'}]}
    path = tmp_path / 'stool.gltf'
    path.write_text(json.dumps(doc))
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        asset_id = window._import_gltf_model(str(path), name='Σκαμπό')
        record = assets.load_asset(asset_id)
        assert record['size'] == pytest.approx([0.6, 0.5, 0.9])
        assert record['provenance']['redistributable'] is False
        assert window._library_item_count() == 1
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_object_modifier_edits_size_parts_and_sculpt_through_commands():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.geometry.selection import BrushSpec, SurfaceHit, sculpt_modifier_from_hit
    from archforge.rendering.materials import MATERIAL_PRESETS
    c = [(x, y, z) for x in (0, 1) for y in (0, 0.5) for z in (0, 0.4)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = [tuple(c[i] for i in t) for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]
    asset_id, size = assets.store_asset('Table', tris, {'source': 'test'},
                                        colors=['#884422'] * 6 + ['#ddccaa'] * 6,
                                        part_names={'#884422': 'legs', '#ddccaa': 'top'})
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        obj = Entity('library_object', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rotation': 0.0, 'width': size[0],
                                        'depth': size[1], 'height': size[2], 'uniform': 1.0, 'asset': asset_id}, name='Table')
        window.stack.execute(AddEntity(obj))
        window.doc.select([obj.id]); window.refresh_inspector()
        dialog = window._open_object_modifier(obj.id)
        assert dialog.parts.count() == 2 and 'legs' in dialog.parts.item(0).text()
        dialog.set_size('width', 150.0)                      # locked: depth scales too
        p = window.doc.get(obj.id).params
        assert (p['width'], p['depth']) == pytest.approx((1.5, 0.75))
        dialog.set_lock(False); dialog.set_size('height', 60.0)
        assert window.doc.get(obj.id).params['depth'] == pytest.approx(0.75)
        mid = next(iter(MATERIAL_PRESETS))
        dialog.set_part_material('part1', mid)
        assert window.doc.get(obj.id).params['surface_materials'] == {'part1': mid}
        assert MATERIAL_PRESETS[mid]['name'] in dialog.parts.item(1).text()
        hit = SurfaceHit(obj.id, 'body', (0.0, 0.0, 0.6), (0, 0, 1))
        mod = sculpt_modifier_from_hit(window.doc, hit, BrushSpec(0.3), 'pull', 0.05)
        window.doc.add_surface_modifier(mod); dialog.refresh()
        assert dialog.modifiers.count() == 1
        dialog.set_modifier_enabled(mod.id, False)
        assert window.doc.surface_modifiers[mod.id].enabled is False
        dialog.remove_modifier(mod.id)
        assert mod.id not in window.doc.surface_modifiers and dialog.modifiers.count() == 0
        window.stack.undo()                                   # modifier back
        assert mod.id in window.doc.surface_modifiers
        dialog.reset_size()
        assert window.doc.get(obj.id).params['width'] == pytest.approx(size[0])
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_core_library_seeds_every_item_at_its_expected_size():
    from archforge.library.builder import build, size_cm
    from archforge.library.catalog import CATEGORIES, seed_core_library, specs
    for spec in specs():
        got = size_cm(build(spec)[0])
        assert max(abs(a - b) for a, b in zip(got, spec['expect_cm'])) <= 1.01, spec['name']
        assert spec['category'][0] in CATEGORIES
    ids = seed_core_library()
    assert len(ids) == len(specs()) and seed_core_library() == []      # once per version
    records = assets.list_assets()
    assert all(r['provenance']['redistributable'] for r in records)
    assert all(assets.load_asset(r['id'])['plan']['outline'] for r in records)


def test_library_tabs_materials_structural_and_kitchen_appliances():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.rendering.materials import MATERIAL_PRESETS
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._seed_core_library()
        assert window._library_item_count() >= 39
        mats = window._library_materials_list
        ids = [mats.item(i).data(0x0100) for i in range(mats.count()) if mats.item(i).data(0x0100)]
        assert set(ids) == set(MATERIAL_PRESETS)
        box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1, 'depth': 1, 'height': 1, 'rotation': 0})
        window.stack.execute(AddEntity(box)); window.doc.select([box.id])
        assert window._apply_material_to_selection(ids[0])
        assert window.doc.get(box.id).params['material_id'] == ids[0]
        window._start_structural_preset('structural_column', {'width': .4, 'depth': .4})
        assert window.plan_view.controller.tool == 'structural_column'
        assert window.plan_view.controller.structural_preset == {'width': .4, 'depth': .4}
        window._place_library_by_name('Ψυγειοκαταψύκτης 60')
        assert window.plan_view.controller.tool == 'library_place'
        assert window._pending_library_asset['name'] == 'Ψυγειοκαταψύκτης 60'
    finally:
        window._mark_clean(); window.close(); app.processEvents()
