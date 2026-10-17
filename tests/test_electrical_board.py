"""Electrical board: conductors per circuit, metres per wall/section, board analysis and the «Ηλεκτρ. πίνακας» tab."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.model import Document
from archforge.mep.electrical import route_cables
from archforge.mep.electrical_board import analyse, board_csv, unverified_lines
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
        assert c['method'] == 'B1' and c['iz_a'] is not None and c['drop_pct'] is not None
    lighting = next(c for c in r['circuits'] if c['group'] == 'lighting')
    # Switch legs (phase + return, at the lighting circuit's section) add to its three line conductors.
    assert lighting['switch_leg'] and lighting['wire_m'][lighting['mm2']] > 3 * lighting['conduit_m'] + 1.0
    assert r['unverified'] == unverified_lines() and any('Iz' in u for u in r['unverified'])
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


def test_farthest_point_and_indicative_voltage_drop_along_the_route():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.core.provenance import ENGINEER_REVIEW, rule
    doc = Document(); stack = CommandStack(doc)
    for x1, y1, x2, y2 in [(0, 0, 40, 0), (40, 0, 40, 4), (40, 4, 0, 4), (0, 4, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))
    _pt(stack, 'panel', 0.3, 2.0)
    heater = _pt(stack, 'water_heater', 39.7, 2.0, power_w=2000.0)
    c = analyse(doc)['circuits'][0]
    assert 40 < c['farthest_m'] <= c['conduit_m'] + 1e-6
    ib = 2000.0 / 230
    assert c['mm2'] == 4.0 and c['drop_pct'] == pytest.approx(2 * 100 * ib * c['farthest_m'] * 0.0225 / (230 * 4.0), abs=0.02)
    stack.execute(UpdateEntity(heater.id, {'power_w': 4500.0}))
    assert analyse(doc)['circuits'][0]['drop_pct'] < 5.0          # 4 mm² (owner 15/10) over > 40 m stays within 5 %
    # A heavy socket at the far end on 2,5 mm²: flagged, with the review tag.
    _pt(stack, 'socket', 39.7, 3.7, power_w=3500.0)
    r = analyse(doc)
    c = next(c for c in r['circuits'] if c['group'] == 'sockets')
    assert c['drop_pct'] > 5.0 and not c['ok'] and any('[προς έλεγχο]' in w and 'πτώση τάσης' in w for w in r['warnings'])
    assert rule('board.voltage_drop').status == ENGINEER_REVIEW and '4 %' in rule('board.voltage_drop').note


def test_iz_check_follows_the_installation_method():
    doc = Document(); stack = CommandStack(doc); panel = _flat(stack)
    heater = next(c for c in analyse(doc)['circuits'] if c['group'] == 'water_heater')
    assert (heater['mm2'], heater['iz_a']) == (4.0, 32.0)                # B1, 4 mm², 2 loaded conductors
    stack.execute(UpdateEntity(panel.id, {'install_method': 'A1'}))
    r = analyse(doc)
    heater = next(c for c in r['circuits'] if c['group'] == 'water_heater')
    # Owner 15/10: 20 A on 4 mm² passes in an insulated wall too (Iz 26 A); 2,5 mm² (Iz 19,5 A) did not.
    assert heater['iz_a'] == 26.0 and heater['ok']
    sockets = next(c for c in r['circuits'] if c['group'] == 'sockets')
    assert sockets['iz_a'] == 19.5 and sockets['ok']                    # 16 A on 2,5 mm² in A1


def test_at_least_two_lighting_circuits():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    _pt(stack, 'light', 2, 3); _pt(stack, 'light', 6, 3)
    lighting = [c for c in analyse(doc)['circuits'] if c['group'] == 'lighting']
    assert len(lighting) == 2 and all(len(c['point_ids']) == 1 for c in lighting)


def test_csv_lists_circuits_walls_and_purchase():
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    text = board_csv(analyse(doc))
    for part in ('Κυκλώματα', 'Μέτρα ανά τοίχο', 'Αγορά (φύρα 0 %', 'L 2,5 + N 2,5 + PE 2,5', 'σκέλη διακοπτών',
                 'Κατάσταση κανόνων', '— (δεν εισήχθη)'):
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


def test_electrical_take_off_goes_into_the_priced_list_with_only_the_users_prices():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.quantities.materials import all_lists, electrical_list
    from archforge.quantities.quote import priced, quote
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    rows = electrical_list(doc)
    descs = {d: (u, q, m) for d, u, q, m in rows}
    assert any(d.startswith('Καλώδιο αγωγός 2,5 mm²') for d in descs)
    unit, qty, meta = descs['Μικροαυτόματος 40 A και σύνδεση κυκλώματος στον πίνακα']   # the cooker line
    assert (unit, qty, meta['code']) == ('τεμ.', 1, 'electrical.breaker.40A') and meta['why']
    assert descs['Διαφορικοί διακόπτες 30 mA — πλήθος/τύπος από τη μελέτη'][1] is None
    assert 'Ηλεκτρολογικά' in [s[0] for s in all_lists(doc)]
    # No prices typed: nothing is costed, everything is listed as missing (never guessed).
    c = priced(doc, rows)
    assert c['total'] == 0 and c['priced'] == 0 and len(c['missing']) == len(rows)
    # Material and labour on the same line (one costing path for every trade).
    stack.execute(AddEntity(Entity('price_list', {'trade_prices': {'electrical.breaker.40A': {'material': 12.5, 'labour': 15.0}},
                                                  'vat': 24.0})))
    c = priced(doc, rows)
    assert (c['total'], c['material'], c['labour'], c['priced']) == (27.5, 12.5, 15.0, 1)
    q = quote(doc, only=('Ηλεκτρολογικά',))
    row = next(r for _t, sec in q['sections'] for r in sec if r['code'] == 'electrical.breaker.40A')
    assert (row['material'], row['labour'], row['amount'], row['complete']) == (12.5, 15.0, 27.5, True)
    owner = next(o for o in q['owner_view'] if o['item'] == row['description'])
    assert owner['why'] and owner['total'] == 27.5 and owner['status']

def test_knx_is_the_clients_option_and_both_are_costed_with_the_projects_prices():
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.quantities.materials import compare_control_options, electrical_list
    doc = Document(); stack = CommandStack(doc); panel = _flat(stack)
    r = analyse(doc)
    assert r['settings']['control_system'] == 'conventional' and r['knx'] is None     # default: conventional On/Off
    lighting = next(c for c in r['circuits'] if c['group'] == 'lighting')
    assert lighting['switch_leg'] and [c for c, *_x in lighting['conductors']] == ['L', 'N', 'PE']
    stack.execute(UpdateEntity(panel.id, {'control_system': 'knx'}))
    light = next(e for e in doc.entities.values() if e.params.get('point_type') == 'light')
    stack.execute(UpdateEntity(light.id, {'dimming': 'dali2'}))
    k = analyse(doc)
    assert k['knx']['buttons'] == 2 and k['knx']['bus_m'] > 0 and k['knx']['dali_addresses'] == 1
    assert k['knx']['dali_gateways'] == 1
    dali_c = next(c for c in k['circuits'] if light.id in c['point_ids'])
    assert [c for c, *_x in dali_c['conductors']] == ['L', 'N', 'PE', 'DA+', 'DA-'] and not dali_c['switch_leg']
    rows = {m['code']: q for _d, _u, q, m in electrical_list(doc, k)}
    assert rows['electrical.knx.button'] == 2 and rows['knx.dali_gateway'] == 1
    assert 'electrical.point.switch' not in rows
    stack.execute(AddEntity(Entity('price_list', {'trade_prices': {'electrical.knx.button': {'material': 90.0, 'labour': 10.0},
                                                                   'electrical.point.switch': {'material': 8.0, 'labour': 7.0}},
                                                  'vat': 24.0})))
    cmp = compare_control_options(doc)
    assert cmp['knx']['total'] == 200.0 and cmp['conventional']['total'] == 30.0
    assert cmp['knx']['missing'] and cmp['conventional']['missing']               # the rest: no price, not guessed


def test_electricians_quote_has_labour_and_only_the_electrical_section(tmp_path):
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.quantities.quote import quote
    doc = Document(); stack = CommandStack(doc); _flat(stack)
    stack.execute(AddEntity(Entity('price_list', {'trade_prices': {'electrical.point.socket': {'material': 4.0, 'labour': 16.0}},
                                                  'prices': {'Βαφή τοίχων': 5.0}, 'vat': 24.0, 'client': 'Πελάτης'})))
    q = quote(doc, only=('Ηλεκτρολογικά',))
    assert [t for t, _r in q['sections']] == ['Ηλεκτρολογικά — καλώδια, σωλήνες, κουτιά, ασφάλειες, σημεία, φωτιστικά']
    assert (q['material'], q['labour'], q['subtotal'], q['total']) == (28.0, 112.0, 140.0, 173.6) and q['missing'] > 0
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from archforge.output.pdf import export_pdf
    out = export_pdf(doc, tmp_path / 'offer.pdf', include=('quote',), only=('Ηλεκτρολογικά',))
    assert out['pages'] >= 1 and (tmp_path / 'offer.pdf').stat().st_size > 1000


def test_board_front_follows_phases_and_rcd_groups_without_inventing_ratings():
    from archforge.mep.electrical_board import front
    doc = Document(); stack = CommandStack(doc); panel = _flat(stack)
    pid = panel if isinstance(panel, str) else panel.id
    f = front(analyse(doc))
    assert f['ask_phases'] and f['rcd_count'] == 1                         # not entered: the program asks
    main = f['devices'][0]
    assert main['kind'] == 'main' and main['poles'] is None and main['rating_a'] is None
    mcbs = [d for d in f['devices'] if d['kind'] == 'mcb']
    assert [d['circuit'] for d in mcbs] == [c['id'] for c in analyse(doc)['circuits']]
    stack.execute(UpdateEntity(pid, {'supply_phases': 1, 'supply_fuse_a': 40.0}))
    f = front(analyse(doc))
    assert not f['ask_phases'] and f['devices'][0]['poles'] == 2 and f['devices'][0]['rating_a'] == 40.0
    assert all(d['phase'] == 'L1' for d in f['devices'] if d['kind'] == 'mcb')
    rcd = next(d for d in f['devices'] if d['kind'] == 'rcd')
    assert rcd['poles'] == 2 and rcd['rating_a'] is None and rcd['sensitivity_ma'] == 30   # rating: from the study
    first = mcbs[0]['circuit']
    stack.execute(UpdateEntity(pid, {'supply_phases': 3, 'rcd_groups': {first: 2}, 'rcd_ratings': [40.0, 25.0]}))
    f = front(analyse(doc))
    assert f['rcd_count'] == 2 and f['devices'][0]['poles'] == 4
    bars = {nb['group']: nb['terminals'] for nb in f['neutral_bars']}
    assert bars[2] == [first] and first not in bars[1]                      # one neutral bar per RCD
    assert [d['rating_a'] for d in f['devices'] if d['kind'] == 'rcd'] == [40.0, 25.0]
    assert f['earth_bar'][0] == 'ΠΑΡΟΧΗ' and set(f['earth_bar'][1:]) == {d['circuit'] for d in mcbs}
    assert all(sum(d['modules'] for d in rail) <= 12 for rail in f['rails'])
    from archforge.core.provenance import VERIFIED, rule
    assert rule('board.conductor_colours').status != VERIFIED and rule('board.rcd_groups').status != VERIFIED


def test_board_tab_shows_the_front_first_and_the_rules_in_their_own_tab():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.electrical_board_tab import BoardTab
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        panel = _flat(window.stack)
        pid = panel if isinstance(panel, str) else panel.id
        tab = BoardTab(window)
        r = tab.refresh()
        assert tab.pages.tabText(0) == 'Πρόσοψη πίνακα' and tab.front_view.front is r['front']
        assert tab.pages.tabText(tab.rules_index).startswith('Κατάσταση κανόνων (')
        assert 'Κανένας' in tab.rules_line.text() and len(tab.rules_line.text()) < 200   # one line, not a wall of text
        cid = r['circuits'][0]['id']
        tab._assign_rcd(cid, 2)                                                # same command path: undoable
        assert window.doc.get(pid).params['rcd_groups'] == {cid: 2} and tab.result['front']['rcd_count'] == 2
        tab._rate_rcd(2, 25.0)
        assert window.doc.get(pid).params['rcd_ratings'] == [0.0, 25.0]
        window.stack.undo(); window.stack.undo()
        assert not window.doc.get(pid).params.get('rcd_groups')
        assert tab._select_circuit(cid) and set(window.doc.selection) == set(r['circuits'][0]['point_ids'])
        tab.front_view.resize(tab.front_view.minimumSize())
        assert not tab.front_view.grab().isNull()
    finally:
        window._mark_clean(); window.close(); app.processEvents()
