"""Electrical board: conductors per circuit, metres per wall/section, board analysis and the «Ηλεκτρ. πίνακας» tab."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.model import Document
from archforge.mep.electrical import route_cables
from archforge.mep.electrical_board import UNVERIFIED, analyse, board_csv
from tests.test_electrical import _house, _pt


def _flat(stack):
    _house(stack)
    panel = _pt(stack, 'panel', 0.3, 3.0)
    for x, y in [(0.3, 1), (0.3, 5), (2, 5.8), (3.7, 5), (1, 0.3), (6, 0.3), (7.7, 3)]:
        _pt(stack, 'socket', x, y)
    _pt(stack, 'light', 2, 3); _pt(stack, 'light', 6, 3)
    _pt(stack, 'switch', 4.4, 1.0); _pt(stack, 'switch', 3.6, 1.0)
    _pt(stack, 'cooker', 1, 5.7); _pt(stack, 'water_heater', 7.7, 5.5); _pt(stack, 'air_conditioner', 6, 5.8)
    _pt(stack, 'kitchen_socket', 2.0, 3.6)                       # island: fed through the floor
    return panel


def test_conductors_per_circuit_at_the_circuit_section():
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    r = analyse(doc)
    for c in r['circuits']:
        assert [code for code, *_x in c['conductors']] == ['L', 'N', 'PE']
        assert {s for *_x, s in c['conductors']} == {c['mm2']}
        assert 'iz_a' not in c and 'drop_pct' not in c          # owner 15/10: no unverified table values
    lighting = next(c for c in r['circuits'] if c['group'] == 'lighting')
    # Switch legs (phase + return, at the lighting circuit's section) add to its three line conductors.
    assert lighting['switch_leg'] and lighting['wire_m'][lighting['mm2']] > 3 * lighting['conduit_m'] + 1.0
    assert r['unverified'] == list(UNVERIFIED) and any('Iz' in u for u in UNVERIFIED)
    assert 'μνήμη' in r['provenance'] and 'ηλεκτρολόγο' in r['provenance']


def test_metres_per_wall_add_up_to_the_routed_cable():
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    r = analyse(doc)
    wiring = route_cables(doc)
    conduit = sum(math.dist(a, b) for a, b, _g, _c in wiring['runs'])
    assert abs(sum(w['conduit_m'] for w in r['walls']) - conduit) < 0.05      # nothing lost, nothing counted twice
    by_section = {}
    for w in r['walls']:
        for s, m in w['by_section'].items():
            by_section[s] = by_section.get(s, 0.0) + m
    for p in r['purchase']:
        assert abs(by_section[p['mm2']] - p['metres']) < 0.1
        assert p['with_waste'] == p['metres']                               # no hidden allowance
    walls = [w for w in r['walls'] if w['kind'] == 'wall']
    assert len(walls) >= 4 and all(w['label'].startswith('Τ') for w in walls)
    assert all(doc.get(w['wall']).kind == 'wall' for w in walls)
    assert any(w['kind'] == 'ceiling' for w in r['walls'])                  # ceiling lights through the slab
    assert any(w['kind'] == 'floor' and 'Κ' in ' '.join(w['circuits']) for w in r['walls'])   # the island socket
    assert not any(w['kind'] == 'free' for w in r['walls'])


def test_board_uses_only_what_the_user_entered_and_settings_are_undoable():
    doc = Document(); stack = CommandStack(doc); panel = _flat(stack)
    r = analyse(doc)
    b = r['board']
    assert b['installed_w'] == sum(c['load_w'] for c in r['circuits'])
    assert b['demand_kva'] is None and b['supply_kva'] is None and b['main_switch'] is None
    assert set(b['missing']) == {'συντελεστής ταυτοχρονισμού', 'παροχή kVA', 'φάσεις', 'ασφάλεια παροχής'}
    # The engineer's factor and the ΔΕΔΔΗΕ connection as entered: three-phase balance, then undo.
    stack.execute(UpdateEntity(panel.id, {'demand_factor': 0.5, 'supply_kva': 15.0, 'supply_phases': 3, 'supply_fuse_a': 25.0}))
    b3 = analyse(doc)['board']
    assert b3['demand_kva'] == pytest.approx(round(0.5 * b3['installed_w'] / 1000, 1)) and b3['missing'] == []
    assert b3['main_switch'] == 'Γενικός διακόπτης 4P 25 A'
    assert set(b3['phase_w']) == {'L1', 'L2', 'L3'} and sum(b3['phase_w'].values()) == b3['installed_w']
    assert {c['phase'] for c in analyse(doc)['circuits']} <= {'L1', 'L2', 'L3'}
    stack.undo()
    assert analyse(doc)['board']['supply_kva'] is None
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(panel.id, {'supply_phases': 2}))
    # Saved with the project.
    stack.execute(UpdateEntity(panel.id, {'waste_pct': 15.0}))
    again = Document.from_dict(doc.to_dict())
    assert analyse(again)['waste_pct'] == 15.0


def test_farthest_point_is_measured_along_the_route():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    doc = Document(); stack = CommandStack(doc)
    for x1, y1, x2, y2 in [(0, 0, 40, 0), (40, 0, 40, 4), (40, 4, 0, 4), (0, 4, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    _pt(stack, 'panel', 0.3, 2.0)
    _pt(stack, 'water_heater', 39.7, 2.0)
    c = analyse(doc)['circuits'][0]
    assert 40 < c['farthest_m'] <= c['conduit_m'] + 1e-6


def test_csv_lists_circuits_walls_and_purchase():
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    text = board_csv(analyse(doc))
    for part in ('Κυκλώματα', 'Μέτρα ανά τοίχο', 'Αγορά (φύρα 0 %', 'L 2,5 + N 2,5 + PE 2,5', 'σκέλη διακοπτών',
                 'Μη επαληθευμένα', '— (δεν εισήχθη)'):
        assert part in text, part


def test_board_tab_shows_the_figures_and_follows_changes(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        tab = window._board_tab
        tabs = window._central_tabs
        assert tabs.indexOf(tab) < 0                                  # approved layout: two drawing tabs until asked for
        tab.refresh()
        assert tab.empty.isVisibleTo(tab) and not tab.pages.isVisibleTo(tab)
        window.plan_view.sitePointRequested.emit('elec_panel', 0.5, 0.5)
        window.plan_view.sitePointRequested.emit('elec_socket', 2.0, 0.5)
        window.plan_view.sitePointRequested.emit('elec_cooker', 3.0, 0.5)
        window._show_circuit_schedule()
        assert tabs.currentWidget() is tab and tabs.tabText(tabs.indexOf(tab)) == 'Ηλεκτρ. πίνακας'
        assert tab.circuits.topLevelItemCount() == 2
        first = tab.circuits.topLevelItem(0)
        assert first.childCount() == 3 and [first.child(i).text(0) for i in range(3)] == ['L', 'N', 'PE']
        assert tab.card_labels['supply'][2].text() == '— εισάγετε' and tab.purchase.topLevelItemCount() >= 2
        # Clicking a circuit selects its points in the drawing.
        tab._select_item(first)
        assert set(window.doc.selection) == set(tab.result['circuits'][0]['point_ids'])
        # Settings go through the command stack.
        tab.waste.setValue(20); tab.waste.editingFinished.emit()
        assert tab.result['waste_pct'] == 20.0
        window._undo()
        assert tab.refresh()['waste_pct'] == 0.0
        assert tab.export_csv(str(tmp_path / 'p.csv')) and (tmp_path / 'p.csv').read_text(encoding='utf-8-sig').startswith('Κυκλώματα')
        assert tab.export_pdf(str(tmp_path / 'p.pdf')) and (tmp_path / 'p.pdf').stat().st_size > 1000
        # The drawing tools still go to the plan from the board tab.
        assert window.view is window.plan_view
    finally:
        window._mark_clean(); window.close(); app.processEvents()
