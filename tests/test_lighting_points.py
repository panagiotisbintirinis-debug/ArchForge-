"""Luminaires are electrical points: load, circuit, dimmer/group, cove of the plasterboard ceiling, light effect."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, AddEntities, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.mep.electrical import POINT_TYPES, design_circuits, mount_z, route_cables
from archforge.mep.lighting import cove_strips, light_spec, light_specs, lighting_report
from tests.test_electrical import _house, _pt


def _cove_ceiling(stack):
    from archforge.construction.drywall import default_params
    p = default_params(points=[(0.1, 0.1), (3.9, 0.1), (3.9, 5.9), (0.1, 5.9)], level_z=0.0)
    p.update(cove=1, cove_width=0.30, cove_depth=0.10, drop=0.30)
    e = Entity('drywall_ceiling', p, name='Ψευδοροφή σαλονιού')
    stack.execute(AddEntity(e))
    return e


def test_strip_load_is_w_per_m_times_length_on_a_lighting_circuit():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    strip = _pt(stack, 'led_strip', 1.0, 1.0, x2=3.5, y2=1.0, w_per_m=14.4)
    spot = _pt(stack, 'spot', 2.0, 3.0)
    d = design_circuits(doc)
    lighting = lambda d: [c for c in d['circuits'] if c['group'] == 'lighting']
    assert {strip.id, spot.id} == {i for c in lighting(d) for i in c['points']}   # two lighting circuits (owner 15/10)
    # No catalogue default: the spot counts 0 W and says so until its data-sheet W is entered.
    assert POINT_TYPES['spot'][2] == 0 and sum(c['load_w'] for c in lighting(d)) == round(14.4 * 2.5)
    assert any('φύλλο' in w and spot.id[:6] in w for w in d['report']['warnings'])
    stack.execute(UpdateEntity(spot.id, {'power_w': 6.0}))
    assert sum(c['load_w'] for c in lighting(design_circuits(doc))) == round(14.4 * 2.5 + 6.0)
    c = next(c for c in design_circuits(doc)['circuits'] if strip.id in c['points'])
    stack.execute(UpdateEntity(strip.id, {'x2': 5.0}))                 # longer strip -> more load
    assert next(c for c in design_circuits(doc)['circuits'] if strip.id in c['points'])['load_w'] > c['load_w']
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(spot.id, {'kelvin': 500.0}))
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(spot.id, {'beam_deg': 0.0}))


def test_cove_strips_sit_in_the_plasterboard_slot_and_follow_its_drop():
    from archforge.construction.drywall import BOARD_THICKNESS, ceiling_level
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    ceiling = _cove_ceiling(stack)
    strips = cove_strips(doc, ceiling)
    assert len(strips) == 4 and len({s['automation_group'] for s in strips}) == 1
    stack.execute(AddEntities([Entity('electrical_point', p) for p in strips]))
    ids = [e.id for e in doc.entities.values() if e.params.get('point_type') == 'led_strip']
    board = ceiling_level(doc, ceiling.params)
    for i in ids:
        z = mount_z(doc, doc.get(i).params)
        assert z == pytest.approx(board + BOARD_THICKNESS)                # on the low band, behind the upstand
        assert light_spec(doc, doc.get(i))['direction'] == 'up'           # indirect, into the slot
    total = sum(math.hypot(doc.get(i).params['x2'] - doc.get(i).params['x'], doc.get(i).params['y2'] - doc.get(i).params['y']) for i in ids)
    assert total == pytest.approx(2 * (3.8 - 0.5) + 2 * (5.8 - 0.5), abs=0.05)
    stack.execute(UpdateEntity(ceiling.id, {'drop': 0.40}))
    assert mount_z(doc, doc.get(ids[0]).params) == pytest.approx(ceiling_level(doc, doc.get(ceiling.id).params) + BOARD_THICKNESS)
    # A ceiling without a cove refuses, with the reason.
    stack.execute(UpdateEntity(ceiling.id, {'cove': 0}))
    with pytest.raises(ValueError):
        cove_strips(doc, doc.get(ceiling.id))


def test_dimmer_of_the_group_controls_the_hidden_light_and_the_report_sizes_the_driver():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    ceiling = _cove_ceiling(stack)
    strips = cove_strips(doc, ceiling)
    stack.execute(AddEntities([Entity('electrical_point', p) for p in strips]))
    lamp = _pt(stack, 'downlight', 2.0, 3.0)
    plain = _pt(stack, 'switch', 3.6, 1.0)
    dimmer = _pt(stack, 'dimmer', 3.6, 1.4, automation_group=strips[0]['automation_group'])
    links = {l['switch']: l for l in design_circuits(doc)['switch_links']}
    strip_ids = {e.id for e in doc.entities.values() if e.params.get('point_type') == 'led_strip'}
    assert set(links[dimmer.id]['lights']) == strip_ids and links[dimmer.id]['dimmer']
    assert links[plain.id]['lights'] == [lamp.id]                         # the room switch keeps the downlight
    report = lighting_report(doc)
    hidden = next(g for g in report['groups'] if g['group'] == strips[0]['automation_group'])
    assert hidden['strip_m'] > 15 and hidden['load_w'] == 0 and len(hidden['missing']) == 4   # W/m, lm/m, K not entered
    assert all('w_per_m' not in s and 'lumen' not in s and 'kelvin' not in s for s in strips)
    spec = light_spec(doc, doc.get(next(iter(strip_ids))))
    assert spec['dimmer'] and spec['switch'] == dimmer.id and spec['circuit'].startswith('Κ')
    assert 'φύλλο' in report['provenance']


def test_light_spec_is_the_renderer_view_of_the_same_entity():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    spot = _pt(stack, 'spot', 2.0, 3.0, lumen=600.0, beam_deg=24.0, kelvin=2700.0, target_x=2.0, target_y=5.9, target_z=1.0)
    washer = _pt(stack, 'wall_washer', 6.0, 5.5)
    strip = _pt(stack, 'led_strip', 5.0, 1.0, x2=7.0, y2=1.0, dim_level=0.5, lumen=800.0, kelvin=3000.0)
    s = light_spec(doc, spot)
    assert s['kind'] == 'spot' and s['angle_deg'] == 12.0 and s['kelvin'] == 2700.0 and s['target'] == [2.0, 5.9, 1.0]
    assert s['intensity'] == pytest.approx(600 / (2 * math.pi * (1 - math.cos(math.radians(12))))) and s['photometry_entered']
    w = light_spec(doc, washer)
    assert w['target'][1] == pytest.approx(6.0) and w['target'][2] < w['position'][2]   # aimed at the nearest wall
    # Nothing entered for the washer: no invented lumen/K/beam, the renderer keeps its display look.
    assert w['lumen'] is None and w['kelvin'] is None and w['intensity'] is None and not w['photometry_entered']
    st = light_spec(doc, strip)
    assert st['kind'] == 'strip' and st['start'][0] == 5.0 and st['end'][0] == 7.0 and st['length_m'] == 2.0
    assert st['lumen'] == pytest.approx(2.0 * 800 * 0.5)
    stack.execute(UpdateEntity(strip.id, {'dim_level': 0.0}))
    assert light_spec(doc, doc.get(strip.id))['enabled'] is False
    assert {x['id'] for x in light_specs(doc)} == {spot.id, washer.id, strip.id}   # sockets/panel are not lights
    # The strip is drawn on the plan as its own line.
    from archforge.core.plan_scene import build_plan_frame
    lines = [p for p in build_plan_frame(doc).primitives if p.role == 'led-strip']
    assert len(lines) == 1 and lines[0].entity_id == strip.id


def test_drag_a_strip_and_cove_command_from_the_menu():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.plan_view.sitePointRequested.emit('elec_panel', 0.5, 0.5)
        window.plan_view.siteLineRequested.emit('elec_led_strip', 1.0, 1.0, 3.0, 1.0)
        strip = next(e for e in window.doc.entities.values() if e.params.get('point_type') == 'led_strip')
        assert (strip.params['x2'], strip.params['y2']) == (3.0, 1.0)
        assert window._cove_lighting() == []                              # no cove ceiling yet: says so
        _cove_ceiling(window.stack)
        n = len(window.doc.entities)
        added = window._cove_lighting()
        assert len(added) == 4 and len(window.doc.entities) == n + 4
        window._undo()
        assert len(window.doc.entities) == n                              # one undo
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_board_counts_cove_cable_as_ceiling():
    from archforge.mep.electrical_board import analyse
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    ceiling = _cove_ceiling(stack)
    stack.execute(AddEntities([Entity('electrical_point', p) for p in cove_strips(doc, ceiling)]))
    r = analyse(doc)
    assert not any(w['kind'] == 'free' for w in r['walls'])
    assert any(w['kind'] == 'ceiling' for w in r['walls'])


def test_properties_of_a_luminaire_have_no_hidden_defaults():
    from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QLabel
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.plan_view.sitePointRequested.emit('elec_spot', 2.0, 2.0)
        spot = next(e for e in window.doc.entities.values() if e.params.get('point_type') == 'spot')
        window.doc.select([spot.id]); window.refresh_inspector()
        labels = [window.form.itemAt(i, window.form.ItemRole.LabelRole).widget().text()
                  for i in range(window.form.rowCount()) if window.form.itemAt(i, window.form.ItemRole.LabelRole)]
        for row in ('Ισχύς', 'Φωτεινή ροή', 'Δέσμη', 'Χρώμα φωτός', 'Ένταση (ροοστάτης)', 'Κατεύθυνση', 'Ομάδα αυτοματισμού'):
            assert row in labels, row
        spins = [w for w in window.form.parentWidget().findChildren(QDoubleSpinBox) if w.specialValueText() == '— από το φύλλο']
        assert spins and all(w.value() == 0 for w in spins)
        beams = next(w for w in window.form.parentWidget().findChildren(QComboBox) if w.itemText(1) == '10°')
        assert beams.currentText() == '— από το φύλλο'
        beams.setCurrentIndex(3); beams.activated.emit(3)                 # 36°
        assert window.doc.get(spot.id).params['beam_deg'] == 36.0
        window._undo()
        assert 'beam_deg' not in window.doc.get(spot.id).params
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_catalog_template_fills_the_point_but_stays_unverified_until_a_real_product():
    from archforge.core.provenance import MANUFACTURER_DATA, UNVERIFIED
    from archforge.mep.luminaire_catalog import Entry, ENTRIES, apply_values, entries_for, status_of
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    strip = _pt(stack, 'led_strip', 1.0, 1.0, x2=4.0, y2=1.0)
    assert status_of(strip.params)[0] == UNVERIFIED
    tpl = entries_for('led_strip')[0]
    assert tpl.status == UNVERIFIED and not tpl.product_code              # owner's summary: no product code
    stack.execute(UpdateEntity(strip.id, apply_values(tpl.id)))
    p = doc.get(strip.id).params
    assert p['w_per_m'] == tpl.values['w_per_m'] and p['catalog_id'] == tpl.id
    status, text = status_of(p)
    assert status == UNVERIFIED and 'όχι φύλλο συγκεκριμένου προϊόντος' in text
    assert light_spec(doc, doc.get(strip.id))['data_status'] == UNVERIFIED
    stack.undo()
    assert 'w_per_m' not in doc.get(strip.id).params                       # one undo
    real = Entry('x', 'x', ('led_strip',), {'w_per_m': 10.0}, manufacturer='M', product_code='P-1', datasheet='p1.pdf')
    assert real.status == MANUFACTURER_DATA


def test_group_with_mixed_dimming_protocols_is_flagged():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    _pt(stack, 'downlight', 2.0, 3.0, automation_group='Σαλόνι', dimming='dali2', power_w=12.0)
    _pt(stack, 'led_strip', 1.0, 1.0, x2=3.0, y2=1.0, automation_group='Σαλόνι', dimming='phase_cut', w_per_m=14.4)
    _pt(stack, 'dimmer', 3.6, 1.0, automation_group='Σαλόνι')
    rep = lighting_report(doc)
    g = next(g for g in rep['groups'] if g['group'] == 'Σαλόνι')
    assert g['dimming'] == ['dali2', 'phase_cut'] and any('διαφορετικά πρωτόκολλα' in w for w in rep['warnings'])
    assert g['driver_hint_w'] == pytest.approx(2.0 * 14.4 * 1.2, abs=0.1)
