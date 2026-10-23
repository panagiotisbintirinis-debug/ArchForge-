"""Ασθενή (owner 17/10): network / TV star from the rack, own layer, 2D + 3D, own sub-tab, materials."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.model import Document
from tests.test_electrical import _house, _pt


def _net(stack):
    _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    _pt(stack, 'socket', 0.3, 1.0)
    rack = _pt(stack, 'network_rack', 0.3, 4.0)
    outlets = [_pt(stack, 'data_outlet', x, y) for x, y in ((0.3, 1.5), (3.7, 5.0), (7.7, 3.0))]
    ap = _pt(stack, 'wifi_ap', 4.0, 3.0)
    tv = _pt(stack, 'tv_outlet', 6.0, 0.3)
    return rack, outlets, ap, tv


def _id(e):
    return e if isinstance(e, str) else e.id


def test_low_voltage_points_never_enter_power_circuits():
    from archforge.mep.electrical import route_cables
    doc = Document(); st = CommandStack(doc); rack, outlets, ap, tv = _net(st)
    lv_ids = {_id(e) for e in [rack, ap, tv, *outlets]}
    wiring = route_cables(doc)
    assert not any(lv_ids & set(c['points']) for c in wiring['circuits'])


def test_star_from_the_rack_one_cable_per_outlet_and_own_conduit_run():
    from archforge.mep.electrical import WALL_RUN_Z
    from archforge.mep.low_voltage import LV_RUN_DROP, route_low_voltage
    doc = Document(); st = CommandStack(doc); rack, outlets, ap, tv = _net(st)
    r = route_low_voltage(doc)
    assert r['rack'] == _id(rack) and not r['warnings']
    by = {o['id']: o for o in r['outlets']}
    assert set(by) == {_id(e) for e in [*outlets, ap, tv]}
    assert {by[_id(ap)]['system'], by[_id(tv)]['system']} == {'network', 'tv'}
    rx, ry = 0.3, 4.0
    for o in r['outlets']:
        # A home run is never shorter than the plan distance from the rack (it follows the walls).
        assert o['cable_m'] >= abs(o['x'] - rx) + abs(o['y'] - ry) - 0.3
    net = r['totals']['network']
    assert net['points'] == 4 and net['cable_m'] == pytest.approx(sum(o['cable_m'] for o in r['outlets'] if o['system'] == 'network'), abs=0.2)
    # Material economy (owner rule 17/10): one shared conduit tree per floor, far shorter than the cables.
    assert net['conduit_m'] < net['cable_m']
    runs_z = {round(a[2], 3) for a, b, s, _t in r['runs'] if abs(a[2] - b[2]) < 1e-9 and s == 'network'}
    assert round(WALL_RUN_Z - LV_RUN_DROP, 3) in runs_z                       # owner 23/10: own run above power (legacy signed DROP alias)


def test_without_rack_the_program_asks_for_one():
    from archforge.mep.low_voltage import route_low_voltage
    doc = Document(); st = CommandStack(doc); _house(st); _pt(st, 'data_outlet', 1.0, 0.3)
    r = route_low_voltage(doc)
    assert r['runs'] == [] and any('rack' in w for w in r['warnings'])


def test_low_voltage_has_its_own_layer_in_plan_and_3d():
    from archforge.core.layers import LAYERS, SCENE_LAYERS, entity_layer, primitive_layer
    from archforge.core.plan_scene import build_plan_frame
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); st = CommandStack(doc); rack, outlets, ap, tv = _net(st)
    assert 'low_voltage' in LAYERS and SCENE_LAYERS['lv'] == 'low_voltage'
    assert entity_layer('electrical_point', doc.get(_id(rack)).params) == 'low_voltage'
    assert entity_layer('electrical_point', {'point_type': 'socket'}) == 'electrical'
    frame = build_plan_frame(doc)
    lv = [p for p in frame.primitives if p.role == 'lv-cable']
    assert lv and all(primitive_layer(doc, p) == 'low_voltage' for p in lv)
    assert any(p.role == 'cable' for p in frame.primitives)                   # power still drawn, apart
    objects = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    assert any(o.get('layer') == 'lv' and o['render_part'] == 'lv:network' for o in objects)
    assert any(o.get('layer') == 'elec' for o in objects)


def test_materials_count_low_voltage_apart():
    from archforge.quantities.materials import electrical_list
    doc = Document(); st = CommandStack(doc); _net(st)
    rows = electrical_list(doc)
    labels = [r[0] for r in rows]
    assert any(l.startswith('Καλώδιο δικτύου') for l in labels) and any(l.startswith('Σωλήνας ασθενών') for l in labels)
    assert sum(1 for l in labels if l.startswith('Πρίζα δικτύου RJ45')) == 1
    cable = next(r for r in rows if r[0].startswith('Καλώδιο δικτύου'))
    assert 'κατηγορία από τη μελέτη' in cable[0] and cable[2] > 0


def test_board_tab_low_voltage_page_and_cable_category_on_the_rack():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.electrical_board_tab import BoardTab
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        rack, outlets, ap, tv = _net(window.stack)
        tab = BoardTab(window)
        tab.refresh()
        assert tab.pages.tabText(tab.lv_index).startswith('Ασθενή')
        tops = [tab.lv_tree.topLevelItem(i).text(0) for i in range(tab.lv_tree.topLevelItemCount())]
        assert tops[0].startswith('Rack') and 'Δίκτυο δεδομένων' in tops and 'TV / SAT' in tops
        tab._set_rack('network_cable', 'Cat 6A')
        assert window.doc.get(_id(rack)).params['network_cable'] == 'Cat 6A'
        assert tab.result['low_voltage']['cable'] == 'Cat 6A'
        window.stack.undo()
        assert 'network_cable' not in window.doc.get(_id(rack)).params
    finally:
        window._mark_clean(); window.close(); app.processEvents()
