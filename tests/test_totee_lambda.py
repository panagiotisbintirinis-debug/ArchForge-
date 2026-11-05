"""λ των υλικών δόμησης από την ΤΟΤΕΕ 20701-2/2010, Πίνακας 2 (PDF από τον ιδιοκτήτη 05/11)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.construction.building_materials import MATERIALS, material
from archforge.core.provenance import DESIGN_DEFAULT, UNVERIFIED, VERIFIED, rules
from archforge.mep import totee_20701_2 as T2


def test_built_in_lambda_say_which_row_of_table_2_they_are():
    m = MATERIALS
    assert m['cement_plaster'].conductivity == 0.87 and m['cement_plaster'].conductivity_status == VERIFIED
    assert '1.4.2' in m['cement_plaster'].conductivity_source
    assert m['reinforced_concrete'].conductivity == 2.30 and m['reinforced_concrete'].conductivity_status == VERIFIED
    assert m['hollow_brick'].conductivity == 0.45 and m['hollow_brick'].conductivity_status == DESIGN_DEFAULT
    assert '1.7.2.2' in m['hollow_brick'].conductivity_source and '1200 kg/m³' in m['hollow_brick'].conductivity_source
    assert m['bearing_masonry'].conductivity == 0.78 and '1.7.2.1' in m['bearing_masonry'].conductivity_source
    assert 'εύρος' in m['eps'].conductivity_source and m['eps'].conductivity_status == DESIGN_DEFAULT
    # Not in the table / outside its range: said, not dressed up.
    assert m['gypsum_board'].conductivity_status == UNVERIFIED and 'Δεν υπάρχει στον Πίνακα 2' in m['gypsum_board'].note
    assert m['isotex_wood_cement'].conductivity_status == UNVERIFIED and '0,090–0,100' in m['isotex_wood_cement'].note
    # Every material keeps its role / look (the source never takes another field's place).
    assert m['hollow_brick'].appearance == 'brick_exposed' and not m['hollow_brick'].insulation
    assert m['mineral_wool'].insulation and m['mineral_wool'].appearance is None
    verified = [r for r in rules() if r.id.startswith('materials.') and r.status == VERIFIED]
    assert verified and all('ΤΟΤΕΕ 20701-2' in r.source for r in verified)


def test_rows_of_table_2_as_read_on_the_page():
    assert T2.TABLE_2['1.7.2.2-1500'][1:3] == (1500, 0.510)
    assert T2.TABLE_2['1.5.3-2%'][1:3] == (2400, 2.500)
    assert T2.TABLE_2['6.3.4.1'][2:] == (0.031, 0.038)
    assert T2.row_values('6.3.3.2')['conductivity'] == 0.038          # a range: its upper (safer) end
    assert T2.row_values('6.3.3.2', 'lower')['conductivity'] == 0.033
    assert T2.row_text('1.7.2.2-1200').startswith('1.7.2.2 ')          # the code keeps its dots
    assert all(code in T2.TABLE_2 for rows in T2.MATERIAL_ROWS.values() for code in rows)
    assert set(T2.MATERIAL_ROWS) == set(MATERIALS)                    # every built-in material is considered


def test_the_material_dialog_takes_a_row_of_the_table_for_this_project():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.wall_layers_panel import material_dialog
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); app.processEvents()
    try:
        dlg = material_dialog(w, 'hollow_brick')
        box = dlg._totee_rows
        box.setCurrentIndex(box.findData('1.7.2.2-1700'))
        buttons = dlg.findChild(__import__('PySide6.QtWidgets', fromlist=['QDialogButtonBox']).QDialogButtonBox)
        buttons.accepted.emit(); app.processEvents()
        m = material('hollow_brick', w.doc)
        assert m.conductivity == 0.58 and m.density == 1700 and '1.7.2.2' in m.conductivity_source
        w.stack.undo()
        assert material('hollow_brick', w.doc).conductivity == 0.45
        gyp = material_dialog(w, 'gypsum_board')
        assert not gyp._totee_rows.isEnabled()                           # nothing in the table to offer
        gyp.reject(); app.processEvents()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
