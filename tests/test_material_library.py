from types import SimpleNamespace

from archforge.core.model import Document, Entity
from archforge.core.commands import AddEntity, CommandStack
from archforge.ui.material_library import _assigned_material, _apply_material, _targets


class _Status:
    def showMessage(self, *args, **kwargs):
        pass


class _Window:
    def __init__(self, doc):
        self.doc = doc
        self.stack = CommandStack(doc)
        self.redraw_count = 0
        self.inspector_count = 0
        self._status = _Status()

    def _redraw_views(self, **kwargs):
        self.redraw_count += 1

    def refresh_inspector(self):
        self.inspector_count += 1

    def statusBar(self):
        return self._status


def _wall():
    return Entity('wall', {
        'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0,
        'z': 0.0, 'height': 2.7, 'thickness': 0.15,
    }, id='wall-material-library')


def test_material_library_exposes_whole_object_and_wall_sides():
    entity = _wall()
    targets = {target.key: target.label for target in _targets(entity)}
    assert '' in targets
    assert targets[''] == 'Όλος ο τοίχος'
    assert 'exterior' in targets
    assert 'interior' in targets


def test_material_library_applies_whole_object_through_command_stack():
    doc = Document(); entity = _wall(); doc.add(entity)
    window = _Window(doc)

    _apply_material(window, entity.id, '', 'wood_oak')

    assert doc.get(entity.id).params['material_id'] == 'wood_oak'
    assert window.redraw_count == 1
    assert window.inspector_count == 1
    window.stack.undo()
    assert not doc.get(entity.id).params.get('material_id')


def test_material_library_applies_one_surface_without_overwriting_other_side():
    doc = Document(); entity = _wall(); doc.add(entity)
    window = _Window(doc)

    _apply_material(window, entity.id, 'exterior', 'stone_dark')
    _apply_material(window, entity.id, 'interior', 'plaster_white')

    surface = doc.get(entity.id).params['surface_materials']
    assert surface['exterior'] == 'stone_dark'
    assert surface['interior'] == 'plaster_white'
    assert _assigned_material(doc.get(entity.id), 'exterior') == 'stone_dark'
    assert _assigned_material(doc.get(entity.id), 'interior') == 'plaster_white'


def test_whole_wall_application_removes_old_side_overrides_in_one_undo():
    doc = Document(); entity = _wall(); doc.add(entity)
    window = _Window(doc)
    _apply_material(window, entity.id, 'exterior', 'stone_dark')
    _apply_material(window, entity.id, 'interior', 'plaster_white')
    before = dict(doc.get(entity.id).params['surface_materials'])

    _apply_material(window, entity.id, '', 'stone_karystos')
    assert doc.get(entity.id).params['material_id'] == 'stone_karystos'
    assert doc.get(entity.id).params.get('surface_materials') == {}
    window.stack.undo()
    assert doc.get(entity.id).params.get('surface_materials') == before
    assert not doc.get(entity.id).params.get('material_id')


def test_dark_material_browser_contains_the_real_properties_editor(monkeypatch, tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.material_library import MaterialLibraryDialog
    from archforge.rendering import user_materials as um

    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    um.reload()
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    wall = _wall()
    window.stack.execute(AddEntity(wall))
    browser = MaterialLibraryDialog(window, wall.id)
    try:
        item = next(browser.grid.item(i) for i in range(browser.grid.count())
                    if browser.grid.item(i).data(Qt.ItemDataRole.UserRole) == 'stone_karystos')
        browser.grid.setCurrentItem(item)
        editor = browser.properties_editor
        assert editor is not None and editor.embedded
        assert editor.image_button is not None and editor.kind is not None and editor.color_button is not None
        assert editor.apply_button.parentWidget().isHidden()  # no floating standalone dialog buttons
        # The editor is under the left category list, not squeezed into the
        # preview column. Its scroll area has a usable vertical viewport.
        assert browser.properties_scroll.widget() is browser.properties_host
        assert browser.properties_scroll.minimumHeight() >= 320
        assert not browser.roughness.isReadOnly()
        assert browser.roughness.isEnabled()
        browser.roughness.setValue(0.35)
        assert editor.spec()['roughness'] == 0.35
        editor.set_colors(color='#aabbcc')
        saved = browser._save_selected_properties()
        assert saved.startswith('user_') and um.lookup(saved)['color'] == '#aabbcc'
        assert um.lookup(saved)['roughness'] == 0.35
        idx = browser.target.findData('exterior')
        assert idx >= 0
        browser.target.setCurrentIndex(idx)
        browser._apply()
        assert window.doc.get(wall.id).params['surface_materials']['exterior'] == saved
        assert window.doc.materials[saved]['color'] == '#aabbcc'
        assert window.doc.materials[saved]['roughness'] == 0.35
        window.stack.undo()
        assert not window.doc.get(wall.id).params.get('surface_materials')
    finally:
        browser.close()
        window.hide()
        um.reload()


def test_material_tree_properties_opens_dark_browser_without_selected_entity(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication, QDialog
    from archforge.ui.main_window import MainWindow
    from archforge.ui.material_library import MaterialLibraryDialog
    from archforge.rendering import user_materials as um

    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    um.reload()
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    monkeypatch.setattr(MaterialLibraryDialog, 'exec', lambda self: QDialog.DialogCode.Rejected)
    try:
        saved = window._browse_material_properties('stone_karystos')
        dialog = window._material_library_dialog
        assert saved == 'stone_karystos'
        assert dialog.properties_editor is not None
        assert dialog.properties_editor.material_id == 'stone_karystos'
        assert not dialog.apply.isEnabled()  # no selection; editing is still possible
        assert dialog.save_properties_button.isEnabled()
        dialog.close()
    finally:
        window.hide()
        um.reload()


def test_stair_targets_include_piece_roles():
    entity = SimpleNamespace(kind='stair', params={'surface_materials': {}}, name='')
    keys = {target.key for target in _targets(entity)}
    assert {'', 'tread', 'riser', 'landing', 'slab', 'stringer'} <= keys


def test_the_browser_opens_in_the_real_app_with_the_object_integration():
    """Owner's PC 28/10: with ui/app.py's integration installed, opening «Βιβλιοθήκη Υλικών» raised
    TypeError (the wrapped _targets took one argument, the browser passes the document too)."""
    import os
    import subprocess
    import sys
    code = (
        "from PySide6.QtWidgets import QApplication; app = QApplication([])\n"
        "from archforge.ui.material_object_integration import install_material_object_integration\n"
        "install_material_object_integration()\n"
        "from archforge.ui.main_window import MainWindow\n"
        "from archforge.core.commands import AddEntity\n"
        "from archforge.core.model import Entity\n"
        "from archforge.ui.material_library import MaterialLibraryDialog\n"
        "w = MainWindow(); w._no_modal_dialogs = True\n"
        "e = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': .2})\n"
        "w.stack.execute(AddEntity(e))\n"
        "d = MaterialLibraryDialog(w, e.id)\n"
        "print('TARGETS', d.target.count())\n"
    )
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', PYTHONPATH=root)
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, cwd=root, timeout=240)
    assert 'TARGETS 3' in out.stdout, out.stderr[-1500:]
