"""Θερμοκρασίες σχεδιασμού του έργου (mep/design_climate.py, ιδιοκτήτης 04/11: «πάντα περιθώριο να αλλάζουμε τις
θερμοκρασίες, τίποτα fixed»): έτοιμες επιλογές με πηγή, δική σου τιμή σε κάθε πεδίο, μία αναίρεση, αποθήκευση."""
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import design_climate as C
from archforge.mep import heat_load as H


def _doc():
    doc = Document(); stack = CommandStack(doc)
    for a, b in zip([(0, 0), (6, 0), (6, 5), (0, 5)], [(6, 0), (6, 5), (0, 5), (0, 0)]):
        stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3.0,
                                                'thickness': .3, 'wall_type': 'brick_double_insulated'})))
    return doc, stack


def test_default_is_a_design_day_with_its_source():
    doc, _ = _doc()
    v = C.values(doc)
    assert v['heat_theta_ext_winter'] == 2.5 and v['heat_theta_int'] == 20.0     # 05/11: ΤΟΤΕΕ 20701-3, Πίν. 2.1
    assert C.preset_of(doc) == 'totee:Αθήνα (Ν. Φιλαδέλφεια)'
    assert 'Πίνακας 2.1, DB 1 %' in C.source_text(doc)


def test_a_preset_changes_the_power_with_one_undo():
    doc, stack = _doc()
    before = H.heat_load(doc)['watts']
    stack.execute(C.set_command(doc, {'preset': 'totee:Φλώρινα'}))
    r = H.heat_load(doc)
    assert r['delta_t'] == pytest.approx(28.05) and r['watts'] > before
    assert 'Φλώρινα' in H.summary(r)
    stack.undo()
    assert H.heat_load(doc)['watts'] == before


@pytest.mark.parametrize('field,value', [('heat_theta_ext_winter', -3.5), ('heat_theta_int', 21.0),
                                         ('heat_theta_ext_summer', 35.0), ('heat_air_changes', 0.8)])
def test_every_value_is_the_users_to_change(field, value):
    doc, stack = _doc()
    stack.execute(C.set_command(doc, {field: value}))
    assert C.values(doc)[field] == value and H.assumptions(doc)[field] == value
    if field == 'heat_theta_ext_winter':
        assert C.preset_of(doc) == C.CUSTOM and 'δική σας' in C.source_text(doc)


def test_older_projects_keep_the_values_on_their_heat_source():
    doc, stack = _doc()
    stack.execute(AddEntity(Entity('heating_point', {'x': 1, 'y': 1, 'z': 0, 'point_type': 'heat_source',
                                                     'heat_theta_ext_winter': 12.0})))
    assert H.heat_load(doc)['delta_t'] == 8.0                       # what the project had stays
    stack.execute(C.set_command(doc, {'preset': 'totee:Αθήνα (Ελληνικό)'}))
    assert H.heat_load(doc)['delta_t'] == 17.0                      # the project's own choice wins


def test_saved_and_loaded_with_the_project(tmp_path):
    from archforge.project.persistence import load_project, save_project
    doc, stack = _doc()
    stack.execute(C.set_command(doc, {'preset': 'totee:Φλώρινα', 'heat_air_changes': 0.7}))
    path = tmp_path / 'c.archforge'
    save_project(doc, str(path))
    loaded = load_project(str(path))
    doc2 = getattr(loaded, 'document', None) or getattr(loaded, 'doc', None)
    assert C.values(doc2)['heat_theta_ext_winter'] == -8.05 and C.values(doc2)['heat_air_changes'] == 0.7
    assert C.preset_of(doc2) == 'totee:Φλώρινα'


def test_dialog_from_the_heating_menu_changes_any_value_with_one_undo():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    from archforge.ui.design_climate_dialog import DesignClimateDialog
    w = MainWindow()
    try:
        found = [p for top in w.menuBar().actions() if top.menu() for p in _leaves(top.menu(), (top.text(),))
                 if p[-1] == 'Θερμοκρασίες σχεδιασμού…']
        assert found and found[0][:2] == ('Εγκαταστάσεις', 'Θέρμανση')
        d = DesignClimateDialog(w)
        assert d.preset.currentData() == 'totee:Αθήνα (Ν. Φιλαδέλφεια)'
        assert d.preset.findData('athens_b') < 0                        # replaced 05/11: not offered to a new project
        d.preset.setCurrentIndex(d.preset.findData('totee:Φλώρινα'))
        assert d.fields['heat_theta_ext_winter'].value() == pytest.approx(-8.05, abs=0.05)
        d.fields['heat_theta_ext_winter'].setValue(-7.0)                # by hand: the user's own value
        assert d.preset.currentData() == C.CUSTOM
        d.fields['heat_theta_int'].setValue(21.0)
        d.apply()
        v = C.values(w.doc)
        assert v['heat_theta_ext_winter'] == -7.0 and v['heat_theta_int'] == 21.0
        w.stack.undo()
        assert C.values(w.doc)['heat_theta_ext_winter'] == 2.5
        d.close()
    finally:
        w._mark_clean(); w.close()


def _leaves(menu, path):
    for a in menu.actions():
        if a.isSeparator() or not a.text():
            continue
        p = path + (a.text().replace('&&', '&'),)
        if a.menu() is not None:
            yield from _leaves(a.menu(), p)
        else:
            yield p


def test_the_official_table_and_the_section_2_1_rule():
    """ΤΟΤΕΕ 20701-3 (PDF από τον ιδιοκτήτη 05/11): Πίνακας 2.1 DB 1 %, και §2.1 για πόλεις εκτός πίνακα."""
    from archforge.mep import totee_20701_3 as T
    assert len(T.TABLE_2_1) == 30
    assert T.TABLE_2_1['Αθήνα (Ελληνικό)'] == (3.0, 4.0, 5.5)
    assert T.TABLE_2_1['Θεσσαλονίκη'][0] == -2.0 and T.TABLE_2_1['Καστοριά'][0] == -7.5
    assert T.TABLE_2_1['Ηράκλειο'][0] == 7.0 and T.TABLE_2_1['Αλεξανδρούπολη'][0] == -4.0
    # §2.1: mean of Πίν. 3.4 (−3,5) and Πίν. 3.6 (−12,6) in January → −8,05 (the old secondary figure was −9).
    value, source = T.winter_design('Φλώρινα')
    assert value == -8.05 and '§2.1' in source and '-3,5' in source and '-12,6' in source
    assert T.winter_design('Δράμα') is not None                 # «∆» of the PDF read as the Greek letter
    assert T.winter_design('Ατλαντίδα') is None
    assert all(c not in T.ESTIMATE_2_1 for c in T.TABLE_2_1)    # the table's own value wins
    assert T.altitude_corrected(2.5, 100, 600) == pytest.approx(2.5 - 3.25)


def test_a_project_that_stored_the_old_choice_still_reads_it():
    doc, stack = _doc()
    stack.execute(C.set_command(doc, {'preset': 'athens_b'}))
    assert C.values(doc)['heat_theta_ext_winter'] == 0.0 and C.preset_of(doc) == 'athens_b'
    assert 'αντικαταστάθηκε' in C.source_text(doc)
