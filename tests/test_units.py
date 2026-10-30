"""Owner 30/10: «όλοι δουλεύουν σε εκατοστά» — dimensions in cm by default (mm / m to choose), IFC in m or mm."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core import units


def test_lengths_read_as_drawn_in_each_unit():
    assert [units.fmt_length(3.45, u) for u in ('cm', 'mm', 'm')] == ['345', '3450', '3,45']
    assert units.fmt_length(3.455, 'cm') == '345,5' and units.fmt_length(0.6) == '60'      # cm by default


def test_the_choice_is_kept_as_a_program_setting(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))
    from archforge.ui import autosave
    monkeypatch.setattr(units, '_settings', autosave.load_settings)
    units.reset_cache()
    units.save(display='mm', ifc='mm')
    units.reset_cache()
    assert (units.display_unit(), units.ifc_unit()) == ('mm', 'mm')
    with pytest.raises(ValueError):
        units.save(display='inch')


def test_ifc_in_millimetres_reads_back_at_true_size(tmp_path):
    import ifcopenshell
    import ifcopenshell.util.unit
    from archforge.core.model import Document, Entity
    from archforge.exchange.ifc import export_ifc
    from archforge.exchange.ifc_import import read
    doc = Document()
    w = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 3.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.27,
                        'wall_type': 'brick_double_insulated'})
    doc.add(w)
    doc.add(Entity('window', {'offset': 1.5, 'width': 1.0, 'height': 1.2, 'sill': 0.9}, parent_id=w.id))
    path = tmp_path / 'mm.ifc'
    assert export_ifc(doc, path, unit='mm')['unit'] == 'mm'
    f = ifcopenshell.open(str(path))
    assert ifcopenshell.util.unit.calculate_unit_scale(f) == pytest.approx(0.001)
    data = read(path)
    wall, = data['walls']
    assert [*wall['a'], *wall['b']] == pytest.approx([0.0, 0.0, 3.0, 0.0], abs=1e-6)
    assert (wall['thickness'], wall['height']) == pytest.approx((0.27, 2.7), abs=1e-6)
    opening, = data['openings']
    assert (opening['width'], opening['height']) == pytest.approx((1.0, 1.2))


def test_the_dialog_changes_the_plan_dimensions(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QApplication
    from archforge.architecture.dimensions import fmt
    from archforge.ui import autosave, units_dialog
    from archforge.ui.main_window import MainWindow
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path))                 # the settings file of this test only
    monkeypatch.setattr(units, '_settings', autosave.load_settings)
    units.reset_cache()
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        assert w._units_action in w._mockup_menus['Επεξεργασία'].actions()
        assert fmt(3.45) == '345'
        dlg = units_dialog.open_dialog(w)
        dlg.display.setCurrentIndex(dlg.display.findData('m'))
        dlg.apply()
        assert units.display_unit() == 'm' and fmt(3.45) == '3,45'
    finally:
        w._mark_clean(); w.close(); app.processEvents()
