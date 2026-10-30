"""«Σύνθεση·υλικά» in a wall's Ιδιότητες: closed by default, layers when opened, changes with one undo."""
import pytest

from archforge.architecture import wall_assemblies as wa
from archforge.core.commands import AddEntity
from archforge.core.model import Entity


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _select_wall(w, wall_type='brick_double_insulated', thickness=0.27, y=0.0):
    wall = Entity('wall', {'x1': 0.0, 'y1': y, 'x2': 4.0, 'y2': y, 'z': 0.0, 'height': 2.7, 'thickness': thickness,
                           'wall_type': wall_type})
    w.stack.execute(AddEntity(wall))
    w.doc.select([wall.id]); w.refresh_inspector()
    return wall.id


def _open(w):
    from PySide6.QtWidgets import QApplication
    w._wall_layers_toggle.click(); QApplication.processEvents(); w.refresh_inspector()


def test_closed_it_is_one_line_opened_it_lists_the_layers(window):
    from archforge.ui import wall_layers_panel as panel
    w = window
    eid = _select_wall(w)
    panel._OPEN.discard(eid)
    w.refresh_inspector()
    assert w._wall_layers_toggle.text() == 'Στρώσεις ▸'
    _open(w)
    assert w._wall_layers_toggle.text() == 'Στρώσεις ▾' and len(w._wall_layer_rows) == 5
    assert [r['material'].currentData() for r in w._wall_layer_rows][2] == 'xps'
    assert 'ενδεικτικό' in panel.summary(w.doc, 'brick_double_insulated')


def test_a_thickness_typed_on_a_built_in_type_gives_this_wall_its_own_copy(window):
    from archforge.ui import wall_layers_panel as panel
    w = window
    eid = _select_wall(w)
    other = _select_wall(w, y=3.0)
    w.doc.select([eid]); panel._OPEN.add(eid); w.refresh_inspector()
    spin = w._wall_layer_rows[2]['thickness']
    spin.setValue(10.0); spin.editingFinished.emit()
    p = w.doc.get(eid).params
    assert p['wall_type'].startswith('proj_') and p['thickness'] == pytest.approx(0.32)
    assert w.doc.get(other).params['wall_type'] == 'brick_double_insulated'
    w.stack.undo()
    assert w.doc.get(eid).params['wall_type'] == 'brick_double_insulated'


def test_a_project_type_changes_for_all_its_walls_unless_only_this_one(window):
    from archforge.ui import wall_layers_panel as panel
    w = window
    key, cmd = wa.copy_type_command(w.doc, 'brick_double_insulated'); w.stack.execute(cmd)
    a = _select_wall(w, key); b = _select_wall(w, key, y=3.0)
    w.doc.select([a]); panel._OPEN.add(a); w.refresh_inspector()
    assert w._wall_layers_scope is not None and not w._wall_layers_scope.isChecked()
    w._wall_layer_rows[0]['drop'].click()
    assert [w.doc.get(i).params['thickness'] for i in (a, b)] == pytest.approx([0.25, 0.25])
    w.refresh_inspector()
    w._wall_layers_scope.setChecked(True)
    w._wall_layers_add.click()
    assert w.doc.get(a).params['wall_type'] != key and w.doc.get(b).params['wall_type'] == key


def test_material_info_shows_its_status_and_takes_the_data_sheet_value(window):
    from archforge.construction.building_materials import material
    from archforge.ui import wall_layers_panel as panel
    w = window
    text = panel.material_text(w.doc, 'xps')
    assert 'Μη επαληθευμένο' in text and 'bmat.xps' in text and 'από το φύλλο' in text
    dlg = panel.material_dialog(w, 'xps')
    from PySide6.QtWidgets import QDialogButtonBox, QLineEdit
    lam, rho, src = dlg.findChildren(QLineEdit)
    lam.setText('0,029'); src.setText('Φύλλο XPS')
    dlg.findChild(QDialogButtonBox).button(QDialogButtonBox.Ok).click()
    assert material('xps', w.doc).conductivity == 0.029
    w.stack.undo()
    assert material('xps', w.doc).conductivity == 0.034
