"""Imported photo textures remain portable, at exact user-specified metric scale."""
import base64
import copy

import pytest

from archforge.core.commands import AddEntity, CommandStack, SetMaterial
from archforge.core.model import Document, Entity
from archforge.rendering import user_materials as um


JPEG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0sample\xff\xd9").decode("ascii")


def test_image_texture_requires_explicit_real_dimensions_and_embedded_jpeg():
    base = um.build_spec("Photo wall", base_id="stone_karystos")
    with pytest.raises(ValueError):
        um.with_image_texture(base, JPEG, 0, 2)
    with pytest.raises(ValueError):
        um.with_image_texture(base, "C:/Users/stone.png", 3, 2)
    with pytest.raises(ValueError):
        um.with_image_texture(base, "data:image/jpeg;base64,AAAA", 3, 2)
    spec = um.with_image_texture(base, JPEG, 3.5, 2.0)
    assert "pattern" not in spec  # photo OR procedural stone pattern, not two competing skins
    assert um.valid_spec(spec)
    assert spec["image_texture"] == {"data": JPEG, "width_m": 3.5, "height_m": 2.0}
    assert um.image_texture_key(spec["image_texture"]) == um.image_texture_key(copy.deepcopy(spec["image_texture"]))
    assert not um.valid_spec({**spec, "image_texture": {**spec["image_texture"], "width_m": -1}})


def test_photo_texture_is_embedded_once_and_can_travel_with_project():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload

    spec = um.with_image_texture(um.build_spec("Stone from photo"), JPEG, 4, 3)
    doc = Document()
    stack = CommandStack(doc)
    stack.execute(SetMaterial("user_photo_wall", copy.deepcopy(spec)))
    for y in (0, 4):
        stack.execute(AddEntity(Entity('wall', {
            'x1': 0, 'y1': y, 'x2': 5, 'y2': y, 'z': 0.0,
            'height': 2.7, 'thickness': 0.2, 'material_id': 'user_photo_wall',
        })))
    payload = build_pbr_scene_payload(
        IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), doc=doc)
    keys = {o['material']['image_texture_key'] for o in payload['objects']
            if o['material'].get('material_id') == 'user_photo_wall'}
    assert len(keys) == 1
    key = keys.pop()
    assert payload['image_textures'] == {key: spec['image_texture']}
    assert all('image_texture' not in o['material'] for o in payload['objects'])
    reloaded = Document.from_dict(doc.to_dict())
    assert reloaded.materials['user_photo_wall']['image_texture'] == spec['image_texture']
    from archforge.ui.pbr_viewport import _PBR_HTML
    assert 'function imageTextureFor' in _PBR_HTML
    assert 'spec.image_texture_key' in _PBR_HTML


def test_same_material_properties_dialog_can_preview_and_save_a_photo(monkeypatch, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from archforge.ui.material_properties import MaterialPropertiesDialog
    from archforge.ui.pattern_swatch import material_swatch

    _app = QApplication.instance() or QApplication([])
    raw = QImage(32, 32, QImage.Format.Format_RGB32)
    raw.fill(QColor('#765432'))
    path = tmp_path / 'my-wall.png'
    assert raw.save(str(path), 'PNG')
    monkeypatch.setattr('PySide6.QtWidgets.QFileDialog.getOpenFileName',
                        lambda *args, **kwargs: (str(path), ''))
    dialog = MaterialPropertiesDialog(None, 'stone_karystos')
    try:
        dialog._choose_image()
        assert not dialog.has_pattern.isChecked()
        assert not dialog.ok_button.isEnabled()  # never assume physical dimensions
        dialog.image_width.setValue(3.2)
        dialog.image_height.setValue(2.6)
        spec = dialog.spec()
        assert um.valid_image_texture(spec['image_texture'])
        assert dialog.ok_button.isEnabled()
        swatch = material_swatch('stone_karystos', 200, 100, spec=spec)
        assert swatch.width() == 200 and not swatch.isNull()
    finally:
        dialog.close()


def test_photo_swatch_shows_one_whole_undistorted_image_at_any_real_size():
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from archforge.ui.pattern_swatch import material_swatch

    app = QApplication.instance() or QApplication([])
    source = QImage(40, 40, QImage.Format.Format_RGB32)
    for y in range(40):
        for x in range(40):
            source.setPixelColor(x, y, QColor(
                '#bb1616' if x < 20 and y < 20 else
                '#16bb16' if x >= 20 and y < 20 else
                '#1616bb' if x < 20 else '#bbbb16'))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert source.save(buffer, 'JPEG', 95)
    data = 'data:image/jpeg;base64,' + base64.b64encode(bytes(buffer.data())).decode()

    def swatch(w, h):
        spec = um.with_image_texture(um.build_spec('Photo'), data, w, h)
        return material_swatch('user_photo', 240, 120, spec=spec)

    original, wide, tall = swatch(1, 1), swatch(2, 1), swatch(1, 2)
    # The properties dialog previews the entire source ONCE; metres control
    # placement in 3D, never duplicate or stretch this source photograph.
    samples = [(x, y) for x in range(0, 240, 10) for y in range(0, 120, 10)]
    expected = [original.pixel(x, y) for x, y in samples]
    assert [wide.pixel(x, y) for x, y in samples] == expected
    assert [tall.pixel(x, y) for x, y in samples] == expected
    # A square source in a 2:1 swatch is letterboxed, not duplicated across X.
    assert original.pixel(10, 60) == original.pixel(220, 60)
    assert original.pixel(10, 60) != original.pixel(80, 60)
    assert original.pixel(80, 10) != original.pixel(160, 10)


def test_import_photo_locks_native_aspect_ratio_by_default(monkeypatch, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from archforge.ui.material_properties import MaterialPropertiesDialog

    app = QApplication.instance() or QApplication([])
    source = QImage(260, 100, QImage.Format.Format_RGB32)
    source.fill(QColor('#887766'))
    path = tmp_path / 'wall.png'
    assert source.save(str(path), 'PNG')
    monkeypatch.setattr('PySide6.QtWidgets.QFileDialog.getOpenFileName',
                        lambda *args, **kwargs: (str(path), ''))
    dialog = MaterialPropertiesDialog(None, 'stone_karystos')
    try:
        dialog._choose_image()
        assert dialog.aspect_lock.isChecked()
        dialog.image_width.setValue(2.60)
        assert dialog.image_height.value() == pytest.approx(1.0, abs=0.01)
        dialog.image_height.setValue(2.0)
        assert dialog.image_width.value() == pytest.approx(5.20, abs=0.01)
        dialog.aspect_lock.setChecked(False)
        dialog.image_width.setValue(3.0)
        assert dialog.image_height.value() == pytest.approx(2.0, abs=0.01)
    finally:
        dialog.close()


def test_owner_flow_photo_becomes_a_material_on_a_wall_in_3d_and_survives_save(monkeypatch, tmp_path):
    """Owner 28/10: «το ζητούμενο ήταν να μπορούμε να φτιάχνουμε υλικό από φωτογραφίες» — the whole path with the mouse:
    Βιβλιοθήκη ▸ υλικό ▸ Ιδιότητες υλικού ▸ Εικόνα… ▸ πραγματικό πλάτος ▸ «Αποθήκευση και εφαρμογή στο επιλεγμένο»."""
    import json
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.material_properties import MaterialPropertiesDialog
    from archforge.rendering.scene import build_pbr_scene_payload
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend

    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    photo = QImage(300, 150, QImage.Format.Format_RGB32); photo.fill(QColor('#8a6f52'))
    path = tmp_path / 'petra.jpg'; assert photo.save(str(path), 'JPEG')
    monkeypatch.setattr('PySide6.QtWidgets.QFileDialog.getOpenFileName', lambda *a, **k: (str(path), ''))
    window = MainWindow()
    try:
        wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
        window.stack.execute(AddEntity(wall))
        window.doc.select([wall.id])
        menu = window._library_tree_menu(SimpleItem(('material', 'stone_karystos')))
        assert any('εικόνα' in a.text() for a in menu.actions())                 # the entry says it takes a photo
        dialog = MaterialPropertiesDialog(window, 'stone_karystos', window.doc)
        dialog._choose_image()
        dialog.image_width.setValue(2.0)                                         # 2 m wide → 1 m high (locked 2:1)
        assert dialog.image_height.value() == pytest.approx(1.0, abs=0.01)
        dialog.apply_button.click()
        saved = window._edit_material_properties('stone_karystos', dialog=dialog)
        assert saved and um.is_user_material(saved)
        assert window.doc.get(wall.id).params.get('material_id') == saved
        payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(window.doc),
                                          doc=window.doc)
        assert payload.get('image_textures')                                     # the photo reaches the 3D
        reopened = Document.from_dict(json.loads(json.dumps(window.doc.to_dict())))
        assert reopened.materials[saved]['image_texture']['width_m'] == 2.0      # travels with the project file
        window._undo()
        assert window.doc.get(wall.id).params.get('material_id') != saved        # one undo takes it off the wall
    finally:
        window._mark_clean(); window.close(); app.processEvents()


class SimpleItem:
    """Stand-in for a library tree leaf (data() returns its action)."""
    def __init__(self, action):
        self.action = action

    def data(self, *_):
        return self.action
