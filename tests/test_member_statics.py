"""«Στατικά μέλους»: checking the bars the user gives, the analysis keeping them, the dialog."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.structure.analysis.settings import DEFAULTS
from test_structural_analysis import _building


def test_given_beam_bars_are_checked_not_chosen():
    from archforge.structure.analysis.rc import design_beam
    s = dict(DEFAULTS)
    # Hand check: 3Ø20 = 9.42 cm², As·fyd = 409.8 kN, x = 409.8/(0.8·0.25·16 667) = 0.123 m,
    # MRd = 409.8·(0.45 − 0.4·0.123) = 164.2 kNm..
    r = design_beam(0.25, 0.50, 150.0, 0.0, 50.0, 5.0, s, rebar={'bottom': {'n': 3, 'd': 20}})
    assert r['ok'] and r['bottom']['given'] and r['bottom']['MRd'] == pytest.approx(164.2, abs=0.5)
    weak = design_beam(0.25, 0.50, 150.0, 0.0, 50.0, 5.0, s, rebar={'bottom': {'n': 2, 'd': 14}})
    assert not weak['ok'] and any('απαιτούμενο' in c for c in weak['checks']) and weak['utilisation'] > 1
    crowded = design_beam(0.25, 0.50, 150.0, 0.0, 50.0, 5.0, s, rebar={'bottom': {'n': 6, 'd': 25}})
    assert not crowded['ok'] and any('δεν χωρά' in c for c in crowded['checks'])
    sparse = design_beam(0.25, 0.50, 150.0, 0.0, 200.0, 5.0, s,
                         rebar={'bottom': {'n': 3, 'd': 20}, 'stirrups': {'d': 8, 's': 0.30, 's_crit': 0.10}})
    assert not sparse['ok'] and any('VRd,s' in c for c in sparse['checks'])


def test_given_column_bars_are_checked():
    from archforge.structure.analysis.rc import design_column
    s = dict(DEFAULTS)
    acts = [(800.0, 60.0, 20.0)]
    auto = design_column(0.40, 0.40, 3.0, acts, 30.0, s)
    assert auto['ok']
    same = design_column(0.40, 0.40, 3.0, acts, 30.0, s,
                         rebar={'d': auto['bars']['d'], 'nb': auto['bars']['nb'], 'nh': auto['bars']['nh']})
    assert same['ok'] and same['bars']['given'] and same['utilisation'] == pytest.approx(auto['utilisation'], abs=0.01)
    few = design_column(0.40, 0.40, 3.0, acts, 30.0, s, rebar={'d': 12, 'nb': 2, 'nh': 2})
    assert not few['ok'] and any('20 cm' in c or 'ρ' in c for c in few['checks'])


def test_analysis_keeps_stored_bars_and_apply_is_one_undo():
    from archforge.structure.analysis.member import apply_command, member_entry, proposal, rebar_of, recheck
    from archforge.structure.analysis.settings import get_settings
    doc, st = _building(storeys=1)
    bid = next(i for i, e in doc.entities.items() if e.kind == 'structural_beam')
    entry, err = member_entry(doc, bid)
    assert err is None and entry['combos'] and entry['diagram'] and entry['inputs']['span'] > 0
    top = doc.get(bid).params['z'] + doc.get(bid).params['height']
    weak = {'bottom': {'n': 2, 'd': 12}, 'top': {'n': 2, 'd': 12}}
    assert not recheck(entry, get_settings(doc), 0.25, 0.50, weak)['ok']
    st.execute(apply_command(doc, bid, 0.25, 0.55, weak))
    p = doc.get(bid).params
    assert p['rebar'] == weak and p['z'] + p['height'] == pytest.approx(top)   # slab level kept
    stored, _ = member_entry(doc, bid)
    assert stored['bottom']['given'] and stored['h'] == pytest.approx(0.55)
    b, h, d = proposal(doc, stored, get_settings(doc))
    assert d['ok'] and rebar_of(d)['bottom']['n'] >= 2
    st.undo()
    assert not doc.get(bid).params.get('rebar') and doc.get(bid).params['height'] == pytest.approx(0.50)


def test_member_statics_dialog_rechecks_applies_and_undoes():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.marking_menu import build_menu
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._no_modal_dialogs = True
        _building(window.doc, storeys=1)
        cid = next(i for i, e in window.doc.entities.items() if e.kind == 'structural_column')
        menu = build_menu(window, 'plan', cid)
        assert any(e['id'] == 'mm:member_statics' and e['placement'] == 'radial' for e in menu['entries'])
        dlg = window._show_member_statics(cid)
        assert dlg.entry['kind'] == 'column' and dlg.table.rowCount() == len(dlg.entry['combos'])
        dlg.fields['d'].setCurrentIndex(dlg.fields['d'].findData(12))
        dlg.fields['nb'].setValue(2); dlg.fields['nh'].setValue(2)
        assert not dlg.design['ok']                                  # live re-check on every change
        dlg.fill_proposal()
        assert dlg.design['ok']
        dlg.fields['b'].setValue(50)
        dlg.apply()
        assert window.doc.get(cid).params['width'] == pytest.approx(0.50) and window.doc.get(cid).params['rebar']
        assert dlg.entry['b'] == pytest.approx(0.50)                 # frame re-solved, still open
        dlg.undo()
        assert window.doc.get(cid).params['width'] == pytest.approx(0.40) and not window.doc.get(cid).params.get('rebar')
    finally:
        window._mark_clean(); window.close(); app.processEvents()
