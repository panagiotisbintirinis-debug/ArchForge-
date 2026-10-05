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
        assert window._library_assets_list.count() == 1
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
        assert window._library_assets_list.count() == 1
    finally:
        window._mark_clean(); window.close(); app.processEvents()
