"""Electrical points in the Document; circuits and cables derived by stated rules."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.mep.electrical import POINT_TYPES, design_circuits, route_cables, route_cables_cached


def _house(stack):
    for x1, y1, x2, y2 in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0), (4, 0, 4, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))


def _pt(stack, kind, x, y, **kw):
    p = {'x': x, 'y': y, 'z': 0.0, 'point_type': kind, 'power_w': float(POINT_TYPES[kind][2])}
    p.update(kw)
    e = Entity('electrical_point', p, name=POINT_TYPES[kind][0]); stack.execute(AddEntity(e))
    return e


def test_circuits_follow_the_stated_rules():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    sockets = [_pt(stack, 'socket', x, y) for x, y in [(0.3, 1), (0.3, 5), (2, 5.8), (3.7, 5), (1, 0.3), (2, 0.3), (3, 0.3)]]
    lights = [_pt(stack, 'light', 2, 3), _pt(stack, 'light', 6, 3)]
    cooker = _pt(stack, 'cooker', 1, 5.7)
    d = design_circuits(doc)
    by_group = {}
    for c in d['circuits']:
        by_group.setdefault(c['group'], []).append(c)
    # 7 sockets in one room -> two 16 A / 2.5 mm² circuits of at most 6
    assert [len(c['points']) for c in by_group['sockets']] in ([6, 1], [4, 3], [3, 4], [5, 2])
    assert all((c['breaker_a'], c['cable_mm2']) == (16, 2.5) for c in by_group['sockets'])
    assert (by_group['lighting'][0]['breaker_a'], by_group['lighting'][0]['cable_mm2']) == (10, 1.5)
    assert by_group['cooker'][0]['points'] == [cooker.id] and by_group['cooker'][0]['breaker_a'] == 32
    assert d['report']['warnings'] == [] and 'ηλεκτρολόγο' in d['report']['provenance']
    assert sorted(i for c in d['circuits'] for i in c['points']) == sorted(e.id for e in sockets + lights + [cooker])


def test_overload_is_flagged_and_no_panel_means_no_circuits():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    s = _pt(stack, 'socket', 1, 1)
    d = design_circuits(doc)
    assert d['circuits'] == [] and d['report']['warnings']
    _pt(stack, 'panel', 0.3, 3.0)
    stack.execute(UpdateEntity(s.id, {'power_w': 4000.0}))       # 17.4 A on a 16 A socket circuit
    d = design_circuits(doc)
    assert not d['circuits'][0]['ok'] and 'χωρίστε' in d['report']['warnings'][0]


def test_switch_controls_lights_of_its_room_and_cables_follow_moves():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0)
    left, right = _pt(stack, 'light', 2, 3), _pt(stack, 'light', 6, 3)
    sw = _pt(stack, 'switch', 4.4, 1.0)
    r = route_cables(doc)
    assert r['switch_links'] == [{'switch': sw.id, 'lights': [right.id]}]
    before = route_cables_cached(doc)['report']['cable_m']
    stack.execute(MoveEntities([right.id], 1.5, 2.5))
    assert route_cables_cached(doc)['report']['cable_m'] != before
    assert all(abs(a[2] - b[2]) < 1e-9 or abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-9 for a, b, _g, _c in r['runs'])


def test_plan_labels_and_elec_layer_in_3d():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _pt(stack, 'panel', 0.3, 3.0); _pt(stack, 'socket', 1, 1); _pt(stack, 'light', 2, 3)
    prims = build_plan_frame(doc).primitives
    assert any(p.role == 'cable' for p in prims)
    labels = [dict(p.meta)['text'] for p in prims if p.role == 'electrical-label']
    assert any(t.startswith('Ρ Κ') for t in labels) and any(t.startswith('Φ Κ') for t in labels)
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    assert {o['render_part'] for o in objs if o.get('layer') == 'elec'} == {'elec:lighting', 'elec:sockets'}


def test_menu_places_points_and_schedule_lists_circuits():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    original = QMessageBox.information
    QMessageBox.information = staticmethod(lambda *a, **k: None)
    try:
        assert len(window._mockup_electrical_menu.actions()) == len(POINT_TYPES)
        window.plan_view.sitePointRequested.emit('elec_panel', 0.5, 0.5)
        window.plan_view.sitePointRequested.emit('elec_socket', 2.0, 0.5)
        wiring = window._show_circuit_schedule()
        assert len(wiring['circuits']) == 1
        window._elec_layer_action.setChecked(False)
        assert 'elec' in window.pbr_view.hidden_layers
    finally:
        QMessageBox.information = original
        window._mark_clean(); window.close(); app.processEvents()
