"""Θερμογέφυρες (κριτική v5 k7): θέσεις και μήκη από τη γεωμετρία, ψ μόνο από τον χρήστη, Ψ·l στην ισχύ θέρμανσης."""
import os

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import thermal_bridges as TB


def _box(doc=None, st=None):
    """6 × 5 m, walls 3,0 m high, 25 cm; a partition at x = 3; a 1,00 × 1,20 window in the south wall."""
    if doc is None:
        doc = Document(); st = CommandStack(doc)
    ids = {}
    for name, (a, b) in {'s': ((0, 0), (6, 0)), 'e': ((6, 0), (6, 5)), 'n': ((6, 5), (0, 5)), 'w': ((0, 5), (0, 0)),
                         'mid': ((3, 0), (3, 5))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3.0, 'thickness': 0.25,
                            'wall_type': 'brick_double_insulated'})
        st.execute(AddEntity(e)); ids[name] = e.id
    win = Entity('window', {'offset': 1.0, 'width': 1.0, 'height': 1.2, 'sill': 0.9}, parent_id=ids['s'])
    st.execute(AddEntity(win)); ids['win'] = win.id
    return doc, st, ids


def _lengths(doc):
    out = {}
    for f in TB.find(doc):
        out[f['type']] = round(out.get(f['type'], 0.0) + f['length_m'], 3)
    return out


def test_the_drawing_gives_every_bridge_with_its_length():
    doc, _st, ids = _box()
    L = _lengths(doc)
    assert L['corner_out'] == pytest.approx(4 * 3.0)          # four outside corners × wall height
    assert 'corner_in' not in L
    assert L['partition'] == pytest.approx(2 * 3.0)           # the partition meets the south and north walls
    assert L['floor_ground'] == pytest.approx(2 * (6 + 5))    # one storey: the ground junction all round …
    assert L['roof'] == pytest.approx(2 * (6 + 5))            # … and the roof junction all round
    assert L['lintel'] == pytest.approx(1.0) and L['sill'] == pytest.approx(1.0)
    assert L['jamb'] == pytest.approx(2 * 1.2)                # three bridges of the window, not one point
    win = [f for f in TB.find(doc) if ids['win'] in f['ids']]
    assert {f['type'] for f in win} == {'lintel', 'sill', 'jamb'} and win[0]['at'] == (1.5, 0.0)


def test_an_l_shape_has_a_re_entrant_corner_and_an_upper_storey_takes_the_roof_off():
    doc = Document(); st = CommandStack(doc)
    pts = [(0, 0), (4, 0), (8, 0), (8, 4), (4, 4), (4, 8), (0, 8)]   # the south wall drawn in two pieces: no corner
    for k, a in enumerate(pts):
        b = pts[(k + 1) % len(pts)]
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3.0,
                                             'thickness': 0.2})))
    L = _lengths(doc)
    assert L['corner_out'] == pytest.approx(5 * 3.0) and L['corner_in'] == pytest.approx(3.0)
    # Upper storey over the 4 × 4 square at the origin corner: its walls cover part of the lower walls' tops.
    for a, b in (((0, 0), (4, 0)), ((4, 0), (4, 4)), ((4, 4), (0, 4)), ((0, 4), (0, 0))):
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 3.0, 'height': 3.0,
                                             'thickness': 0.2})))
    L = _lengths(doc)
    lower_perimeter = 32.0
    assert L['floor_mid'] == pytest.approx(16.0)             # the four upper exterior walls stand on the slab
    assert L['roof'] == pytest.approx(lower_perimeter - 8.0 + 16.0)   # lower tops not under walls + upper tops


def test_psi_comes_only_from_the_user_and_goes_into_the_heating_power_with_one_undo():
    from archforge.mep.heat_load import heat_load
    doc, st, _ids = _box()
    before = heat_load(doc)
    assert dict(before['parts'])['Θερμογέφυρες'] == 0
    assert any(n.startswith('θερμογέφυρες: ') for n in before['not_counted'])
    s = TB.summary(doc)
    assert all(r['psi'] is None and r['psi_l'] is None for r in s['rows'])     # nothing from memory
    st.execute(TB.set_command(doc, 'corner_out', 0.08, code='ΤΟΤΕΕ 20701-1 Π.15 (π.χ.)', source='μελέτη του έργου'))
    st.execute(TB.set_command(doc, 'jamb', 0.10, source='φύλλο κατασκευαστή'))
    s = TB.summary(doc)
    row = {r['type']: r for r in s['rows']}
    assert row['corner_out']['psi_l'] == pytest.approx(0.08 * 12.0) and row['corner_out']['code'].startswith('ΤΟΤΕΕ')
    assert s['h_tb'] == pytest.approx(0.08 * 12.0 + 0.10 * 2.4)
    after = heat_load(doc)
    assert dict(after['parts'])['Θερμογέφυρες'] == pytest.approx(s['h_tb'] * after['delta_t'], abs=1)
    assert after['watts'] > before['watts']
    st.undo(); st.undo()
    assert TB.summary(doc)['h_tb'] == 0


def test_the_catalogue_saves_and_loads(tmp_path):
    from archforge.project.persistence import load_project, save_project
    doc, st, _ids = _box()
    st.execute(TB.set_command(doc, 'lintel', 0.25, code='Λ1', source='μελέτη'))
    path = str(tmp_path / 'tb.archforge')
    save_project(doc, path)
    again = load_project(path).doc
    assert TB.catalogue(again)['lintel'] == {'psi': 0.25, 'code': 'Λ1', 'source': 'μελέτη'}


def test_dialog_writes_psi_with_one_undo_and_shows_the_places(monkeypatch):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.thermal_bridges_dialog import ThermalBridgesDialog
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); app.processEvents()
    try:
        assert w._thermal_bridges_action in w._mockup_heating_menu.actions()
        _box(w.doc, w.stack)
        d = ThermalBridgesDialog(w)
        rows = {r['type']: k for k, r in enumerate(d.rows)}
        d.table.item(rows['corner_out'], 3).setText('0,08')
        d.table.item(rows['corner_out'], 4).setText('Λ-γωνία')
        d.table.item(rows['jamb'], 3).setText('0,1')
        assert d.apply() is not None
        cat = TB.catalogue(w.doc)
        assert cat['corner_out']['psi'] == pytest.approx(0.08) and cat['corner_out']['code'] == 'Λ-γωνία'
        assert TB.summary(w.doc)['h_tb'] == pytest.approx(0.08 * 12 + 0.1 * 2.4)
        assert 'W/K' in d.power.text() and 'χωρίς ψ' in d.power.text()
        w.stack.undo()                                              # the whole table is one undo
        assert TB.summary(w.doc)['h_tb'] == 0
        d.refresh(); d.table.setCurrentCell(rows['jamb'], 0)
        shown = d.show_selected()
        assert shown and set(w.doc.selection) == set(shown)
        d.close()
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_heating_power_on_its_own_adds_nothing_to_the_project():
    """Σ10 (κριτική v5): the power came only through «Ολοκλήρωση κτιρίου…», which also adds emitters and supplies."""
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w._no_modal_dialogs = True; app.processEvents()
    try:
        _box(w.doc, w.stack)
        count, done = len(w.doc.entities), len(w.stack.done)
        assert w._heat_power_action in w._mockup_heating_menu.actions()
        w._heat_power_action.trigger(); app.processEvents()
        assert len(w.doc.entities) == count and len(w.stack.done) == done
        assert 'Ενδεικτική ισχύς θέρμανσης' in w.statusBar().currentMessage()
        from archforge.ui.thermal_bridges_dialog import power_text
        text = power_text(w.doc)
        assert 'Εξωτερικοί τοίχοι:' in text and 'Θερμογέφυρες:' in text and 'δεν μετρήθηκαν' in text
    finally:
        w._mark_clean(); w.close(); app.processEvents()
