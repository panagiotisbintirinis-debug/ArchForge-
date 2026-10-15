"""Electrical board: conductors per circuit, metres per wall/section, board analysis and the «Ηλεκτρ. πίνακας» tab."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.model import Document
from archforge.mep.electrical import route_cables
from archforge.mep.electrical_board import SECTIONS, analyse, board_csv
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


def test_conductors_per_circuit_and_sections_from_0_75_to_10():
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    r = analyse(doc)
    assert {0.75, 1.5, 2.5, 4.0, 6.0, 10.0} <= set(SECTIONS)
    assert SECTIONS[0.75][1] is None                             # flexible cords only, never a fixed circuit
    for c in r['circuits']:
        assert [code for code, *_x in c['conductors']] == ['L', 'N', 'PE']
        assert {s for *_x, s in c['conductors']} == {c['mm2']} and c['mm2'] >= 1.5
        assert c['iz_a'] is not None and c['breaker_a'] <= c['iz_a']
    cooker = next(c for c in r['circuits'] if c['group'] == 'cooker')
    assert cooker['mm2'] == 6.0 and cooker['breaker_a'] == 32
    lighting = next(c for c in r['circuits'] if c['group'] == 'lighting')
    # Switch legs (phase + return, 1.5 mm²) add to the three line conductors of the lighting circuit.
    assert lighting['switch_leg'] and lighting['wire_m'][1.5] > 3 * lighting['conduit_m'] + 1.0
    assert 'HD 60364-5-52' in r['provenance'] and 'ηλεκτρολόγο' in r['provenance']


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
        assert abs(p['with_waste'] - p['metres'] * 1.10) < 0.15              # default allowance 10 %
    walls = [w for w in r['walls'] if w['kind'] == 'wall']
    assert len(walls) >= 4 and all(w['label'].startswith('Τ') for w in walls)
    assert all(doc.get(w['wall']).kind == 'wall' for w in walls)
    assert any(w['kind'] == 'ceiling' for w in r['walls'])                  # ceiling lights through the slab
    assert any(w['kind'] == 'floor' and 'Κ' in ' '.join(w['circuits']) for w in r['walls'])   # the island socket
    assert not any(w['kind'] == 'free' for w in r['walls'])


def test_board_supply_rcds_phases_and_settings_are_undoable_commands():
    doc = Document(); stack = CommandStack(doc); panel = _flat(stack)
    b = analyse(doc)['board']
    assert b['installed_w'] == sum(c['load_w'] for c in analyse(doc)['circuits'])
    # IET On-Site Guide A1: socket circuits count by their breaker (16 A + 40 % of 16 A per further circuit).
    sockets = [c for c in analyse(doc)['circuits'] if c['group'] in ('sockets', 'kitchen_sockets')]
    assert b['demand_a'] >= 16 + 0.4 * 16 * (len(sockets) - 1) and 'ασφάλεια' in b['demand_method']
    assert b['supply_kva'] >= b['demand_kva'] and 'ΔΕΔΔΗΕ' in b['supply_provenance']
    assert sum(len(d['circuits']) for d in b['rcds']) == len(analyse(doc)['circuits'])
    assert all('30 mA' in d['label'] for d in b['rcds'])
    # The engineer's own factor and a three-phase supply: phases balanced, then undo.
    stack.execute(UpdateEntity(panel.id, {'demand_factor': 0.5, 'supply': '3'}))
    b3 = analyse(doc)['board']
    assert b3['phases'] == 3 and b3['main_switch'].endswith('25 A') and 'συντελεστής 0.50' in b3['demand_method']
    assert abs(b3['demand_kva'] - 0.5 * b3['installed_w'] / 1000) < 0.06
    assert set(b3['phase_w']) == {'L1', 'L2', 'L3'} and sum(b3['phase_w'].values()) == b3['installed_w']
    assert {c['phase'] for c in analyse(doc)['circuits']} <= {'L1', 'L2', 'L3'}
    stack.undo()
    assert analyse(doc)['board']['supply'] == b['supply']
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(panel.id, {'supply': '9'}))
    # Saved with the project.
    stack.execute(UpdateEntity(panel.id, {'waste_pct': 15.0}))
    again = Document.from_dict(doc.to_dict())
    assert analyse(again)['waste_pct'] == 15.0


def test_voltage_drop_is_flagged_on_a_long_run():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    doc = Document(); stack = CommandStack(doc)
    for x1, y1, x2, y2 in [(0, 0, 40, 0), (40, 0, 40, 4), (40, 4, 0, 4), (0, 4, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    _pt(stack, 'panel', 0.3, 2.0)
    heater = _pt(stack, 'water_heater', 39.7, 2.0, power_w=2000.0)
    c = analyse(doc)['circuits'][0]
    assert c['farthest_m'] > 40 and 0 < c['drop_pct'] < c['drop_limit_pct'] and c['ok']
    stack.execute(UpdateEntity(heater.id, {'power_w': 4500.0}))          # 19.6 A over > 40 m on 2.5 mm²
    r = analyse(doc)
    c = r['circuits'][0]
    assert c['drop_pct'] > 5.0 and not c['ok'] and any('πτώση τάσης' in w for w in r['warnings'])


def test_csv_lists_circuits_walls_and_purchase():
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    text = board_csv(analyse(doc))
    for part in ('Κυκλώματα', 'Μέτρα ανά τοίχο', 'Αγορά (φύρα 10 %)', 'Διαφορικός', 'L 2,5 + N 2,5 + PE 2,5', 'επιστροφές 1,5'):
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
        assert tab.card_labels['supply'][2].text() and tab.purchase.topLevelItemCount() >= 2
        # Clicking a circuit selects its points in the drawing.
        tab._select_item(first)
        assert set(window.doc.selection) == set(tab.result['circuits'][0]['point_ids'])
        # Settings go through the command stack.
        tab.waste.setValue(20)
        assert tab.result['waste_pct'] == 20.0
        window._undo()
        assert tab.refresh()['waste_pct'] == 10.0
        assert tab.export_csv(str(tmp_path / 'p.csv')) and (tmp_path / 'p.csv').read_text(encoding='utf-8-sig').startswith('Κυκλώματα')
        assert tab.export_pdf(str(tmp_path / 'p.pdf')) and (tmp_path / 'p.pdf').stat().st_size > 1000
        # The drawing tools still go to the plan from the board tab.
        assert window.view is window.plan_view
    finally:
        window._mark_clean(); window.close(); app.processEvents()
