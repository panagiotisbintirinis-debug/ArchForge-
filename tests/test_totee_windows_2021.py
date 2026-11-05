"""ΤΟΤΕΕ 20701-2/2021 (επίσημο PDF, web.tee.gr): πίνακες κουφωμάτων και solver σχεδιασμού (ιδιοκτήτης 05/11: «πιο
αναλυτικούς πίνακες… και ένα solver σχεδιασμού»)."""
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import opening_thermal as O
from archforge.mep import totee_20701_2_2021 as T


def test_spot_values_of_the_official_tables():
    assert T.TABLE_9['2|le05|4-16-4'][3] == {'air': 1.4, 'argon': 1.2, 'krypton': 1.2}
    assert T.TABLE_9['2|none|4-6-4'][3]['air'] == 3.3 and T.TABLE_9['3|le05|4-12-4-12-4'][3]['krypton'] == 0.5
    assert T.TABLE_10['metal_no_break'][2] == 7.0 and T.TABLE_10['metal_break'][2] == (1.0, 4.0)
    assert T.TABLE_10['softwood_10'][2] == 1.5 and T.TABLE_10['pvc_3'][2] == 2.0
    assert T.psi_g('metal_break', '2|le05|4-16-4') == 0.11 and T.psi_g('metal_break', '2|le05|4-16-4', 'warm') == 0.08
    assert T.psi_g('softwood_5', '2|none|4-16-4') == 0.06 and T.psi_g('metal_no_break', '2|none|4-16-4', 'warm') == 0.01
    assert T.TABLE_12['metal_no_break'][1] == 7.0 and T.TABLE_13['synthetic_foam'][1] == (0.13, 0.19, 0.26)
    assert T.u_max('opening', 'Β') == 2.60 and T.u_max('opening', 'Β', renovation=True) == 3.00
    assert T.u_max('wall_exterior', 'Δ') == 0.35 and T.u_max('curtain_wall', 'Α', True) == 2.20
    assert T.horizontal(2.0) == pytest.approx(1 / (0.5 - 0.03))
    assert T.corrected(2.0, 0.16) == pytest.approx(2.0 * 0.5 + 0.5 / (0.5 + 0.16))


def _window(**p):
    doc = Document(); st = CommandStack(doc)
    w = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.27,
                        'wall_type': 'brick_double_insulated'})
    st.execute(AddEntity(w))
    o = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9, **p}, parent_id=w.id)
    st.execute(AddEntity(o))
    return doc, st, o


def test_uw_from_the_choices_with_the_table_values_said_and_the_makers_values_first():
    doc, _st, o = _window(frame_material='pvc_3', glazing='2|le05|4-16-4|argon', spacer='warm', frame_width=0.10)
    # Ag 1,0 × 1,2 = 1,20 · Af 0,48 · lg 4,4 → (2,0·0,48 + 1,2·1,20 + Ψg·4,4) / 1,68
    expect = (2.0 * 0.48 + 1.2 * 1.20 + 0.06 * 4.4) / 1.68          # Πίν. 11β, συνθετικό, low-e: 0,06
    value, source = O.uw(doc, o)
    assert value == pytest.approx(expect) and 'Uf Πίν. 10' in source and 'Ug Πίν. 9' in source and '11β' in source
    doc, _st, o = _window(frame_material='pvc_3', glazing='2|le05|4-16-4|argon', frame_width=0.10, uf=1.3)
    assert O.uw(doc, o)[0] == pytest.approx((1.3 * 0.48 + 1.2 * 1.20 + 0.08 * 4.4) / 1.68)      # the maker's Uf wins
    doc, _st, o = _window(frame_material='metal_break', glazing='2|le05|4-16-4|argon', frame_width=0.10)
    assert O.uw(doc, o)[1] != O.SOURCE_TABLES and 'Uf' in O.components(o)['missing'][0]   # a range is never picked
    doc, _st, o = _window(frame_material='pvc_3', glazing='2|le05|4-16-4|argon')
    assert 'πλάτος πλαισίου' in O.components(o)['missing']                               # never assumed


def test_roller_box_and_shutters_by_relations_2_17_to_2_19():
    from archforge.architecture.joinery import ROLLER_BOX
    base = dict(frame_material='pvc_3', glazing='2|le05|4-16-4|argon', frame_width=0.10, opening_type='casement')
    doc, _st, o = _window(**base, shading='roller', roller_box='metal_no_break', shutter_slats='aluminium',
                          shutter_airtightness='medium')
    h = 1.4 - ROLLER_BOX
    ag, lg = 1.0 * (h - 0.2), 2 * (1.0 + h - 0.2)
    expect = (2.0 * (1.2 * h - ag) + 1.2 * ag + 0.08 * lg + 7.0 * 1.2 * ROLLER_BOX) / (1.2 * h)
    assert O.uw(doc, o)[0] == pytest.approx(expect)
    rb, corr = O.uw_with_shutters(doc, o)
    assert rb == pytest.approx(1 / (1 / expect + 0.12)) and corr == pytest.approx(0.5 * expect + 0.5 * rb)


def test_the_design_solver_lists_what_meets_the_target_and_what_uf_to_ask_the_maker_for():
    opts = O.design(1.2, 1.4, 0.10, 1.6)
    ok = [x for x in opts if x['ok']]
    assert ok and all(x['uw'] is None or x['uw'] <= 1.6 + 1e-9 for x in ok)
    fixed = [x for x in ok if x['uw'] is not None]
    assert O.complexity(fixed[0]) == min(O.complexity(x) for x in fixed)  # the most usual build-up that passes first
    same = [x for x in fixed if O.complexity(x) == O.complexity(fixed[0])]
    assert fixed[0]['uw'] == max(x['uw'] for x in same)                  # then the smallest margin
    assert not opts[-1]['ok']
    rng = next(x for x in opts if x['frame'] == 'metal_break' and x['glazing'] == '2|le05|4-16-4|argon'
               and x['spacer'] == 'standard')
    # Uf ≤ (1,6·1,68 − 1,2·1,20 − 0,11·4,4) / 0,48
    assert rng['uf_needed'] == pytest.approx((1.6 * 1.68 - 1.2 * 1.20 - 0.11 * 4.4) / 0.48)
    assert O.required_ug(1.2, 1.4, 0.10, 2.0, 0.08, 1.6) == pytest.approx((1.6 * 1.68 - 2.0 * 0.48 - 0.08 * 4.4) / 1.2)
    with pytest.raises(ValueError):
        O.design(0.3, 0.3, 0.2, 1.6)


# ------------------------------------------------------------------ the solver in the program
import os  # noqa: E402

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def test_the_solver_opens_from_the_list_and_applies_one_combination_with_one_undo(window):
    from archforge.ui import live_lists
    w, app = window
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.27})
    w.stack.execute(AddEntity(wall))
    o = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9, 'uw_required': 1.6}, parent_id=wall.id)
    w.stack.execute(AddEntity(o))
    lists = live_lists.show(w, 'openings') and w._lists_tab
    assert lists.design_btn.isVisible()
    lists.table.selectRow(0); app.processEvents()
    dlg = lists.design_opening()
    assert dlg.target.value() == pytest.approx(1.6) and dlg.table.rowCount() == 0     # no frame width: asks for it
    dlg.frame_width.setValue(10.0); app.processEvents()
    assert dlg.table.rowCount() > 0 and all(x['ok'] for x in dlg.options)
    dlg.group.setCurrentIndex(dlg.group.findData('synthetic')); app.processEvents()
    assert all(T.TABLE_10[x['frame']][0] == 'synthetic' for x in dlg.options)
    chosen = dlg.apply(0)
    p = w.doc.get(o.id).params
    assert p['frame_material'] == chosen['frame'] and p['glazing'] == chosen['glazing'] and p['frame_width'] == 0.10
    if chosen['uw'] is not None:
        assert O.uw(w.doc, w.doc.get(o.id))[0] == pytest.approx(chosen['uw'])
    w.stack.undo()
    assert w.doc.get(o.id).params.get('frame_material') is None
    dlg.close()
