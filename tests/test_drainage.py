"""Drainage derived from the fixtures: Φ, slope, stacks, floor drains, manhole (EN 12056-2, owner's trade rules)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.mep.drainage import (FIXTURES, POINT_TYPES, SCREED, SLOPE, collector_dn, route_drainage,
                                    route_drainage_cached, stack_dn)
from archforge.mep.plumbing import POINT_TYPES as PLUMB


def _storey(stack, z, w=8.0, d=6.0, partition_x=4.0):
    for x1, y1, x2, y2 in [(0, 0, w, 0), (w, 0, w, d), (w, d, 0, d), (0, d, 0, 0), (partition_x, 0, partition_x, d)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': 3.0, 'thickness': 0.2})))


def _fix(stack, kind, x, y, z=0.0):
    e = Entity('plumbing_point', {'x': x, 'y': y, 'z': z, 'point_type': kind}, name=PLUMB[kind][0])
    stack.execute(AddEntity(e))
    return e


def _bath(stack, z):
    _fix(stack, 'wc', 1.0, 5.5, z); _fix(stack, 'basin', 2.0, 5.6, z); _fix(stack, 'shower', 3.4, 5.4, z)


def _building(floors):
    doc = Document(); stack = CommandStack(doc)
    for k in range(floors):
        _storey(stack, 3.0 * k)
        _bath(stack, 3.0 * k)
    return doc, stack


def test_owner_trade_sizes_wc_phi100_and_stack_phi100_up_to_two_storeys():
    assert FIXTURES['wc'][1] == 100
    assert collector_dn(2.0, True) == 100 and collector_dn(80.0, True) == 125
    assert collector_dn(0.5, False) == 50
    assert stack_dn(8.0) == 100 and stack_dn(80.0) == 125            # by volume: 0.5·√ΣDU ≤ 4 l/s → Φ100
    assert stack_dn(8.0, rain_area=100.0) == 125                     # + rainwater 0.03 l/s·m² → Φ125
    assert SCREED == pytest.approx(0.20)


def test_single_storey_drains_to_an_auto_manhole_with_floor_drain_and_slope():
    doc, _s = _building(1)
    r = route_drainage(doc)
    kinds = sorted(n['kind'] for n in r['nodes'])
    assert kinds == ['floor_drain', 'manhole']
    assert all(n['auto'] for n in r['nodes'])
    assert not [p for p in r['pipes'] if p[3] == 'stack']
    for a, b, dn, kind in r['pipes']:
        if kind == 'collector':
            run = abs(a[0] - b[0]) + abs(a[1] - b[1])
            assert a[2] - b[2] == pytest.approx(SLOPE * run, abs=1e-6)     # 2 % towards the outlet
    assert 100 in r['report']['length_by_dn'] and 40 in r['report']['length_by_dn']
    assert 'μηχανολόγο' in r['report']['provenance']


def test_stack_is_phi100_or_phi125_by_volume_and_rainwater():
    for floors, served in ((2, 1), (3, 2)):
        r = route_drainage(_building(floors)[0])
        (st,) = [p for p in r['pipes'] if p[3] == 'stack']
        (node,) = [n for n in r['nodes'] if n['kind'] == 'stack']
        assert (node['floors'], st[2], node['dn']) == (served, 100, 100) and node['flow_ls'] <= 4.0
    doc, stack = _building(2)
    st = Entity('drainage_point', {'x': 0.1, 'y': 5.5, 'z': 0.0, 'point_type': 'stack', 'rain_area': 120.0})
    stack.execute(AddEntity(st))
    r = route_drainage(doc)
    (node,) = [n for n in r['nodes'] if n['kind'] == 'stack']
    assert node['dn'] == 125 and not node['auto'] and node['rain_area'] == 120.0
    assert any('όμβρια' in w for w in r['report']['warnings'])
    with pytest.raises(ValueError):
        doc.add(Entity('drainage_point', {'x': 0, 'y': 0, 'z': 0, 'point_type': 'stack', 'rain_area': -1}))


def test_floor_depth_beyond_20cm_is_made_up_with_cement_screed():
    doc = Document(); stack = CommandStack(doc)
    _storey(stack, 0.0, w=14.0, partition_x=7.0); _storey(stack, 3.0, w=14.0, partition_x=7.0)
    _fix(stack, 'wc', 1.0, 5.5, 3.0); _fix(stack, 'kitchen_sink', 13.5, 0.5, 3.0); _fix(stack, 'basin', 6.5, 0.5, 3.0)
    r = route_drainage(doc)
    depth = r['report']['depth_m'][3.0]
    assert depth > SCREED
    assert any('τσιμεντοκονία' in w for w in r['report']['warnings'])
    assert r['report']['screed_m'][3.0] == pytest.approx(depth - SCREED, abs=0.011)
    small, _s = _building(2)
    rep = route_drainage(small)['report']
    assert rep['depth_m'][3.0] <= SCREED and not any('τσιμεντοκονία' in w for w in rep['warnings'])


def test_placed_points_are_entities_that_replace_the_auto_ones_and_move_with_undo():
    doc, stack = _building(1)
    m = Entity('drainage_point', {'x': 2.0, 'y': -1.5, 'z': 0.0, 'point_type': 'manhole'}, name=POINT_TYPES['manhole'][0])
    stack.execute(AddEntity(m))
    (node,) = [n for n in route_drainage_cached(doc)['nodes'] if n['kind'] == 'manhole']
    assert not node['auto'] and (node['x'], node['y']) == pytest.approx((2.0, -1.5))
    stack.execute(MoveEntities([m.id], 1.0, 0.0))
    (node,) = [n for n in route_drainage_cached(doc)['nodes'] if n['kind'] == 'manhole']
    assert node['x'] == pytest.approx(3.0)
    stack.undo()
    (node,) = [n for n in route_drainage_cached(doc)['nodes'] if n['kind'] == 'manhole']
    assert node['x'] == pytest.approx(2.0)
    with pytest.raises(ValueError):
        doc.add(Entity('drainage_point', {'x': 0, 'y': 0, 'z': 0, 'point_type': 'gutter'}))


def test_plan_and_3d_show_the_drainage_layer():
    doc, _s = _building(2)
    frame = build_plan_frame(doc)
    roles = {p.role for p in frame.primitives}
    assert {'drain', 'drain-node', 'drain-label', 'drain-stack'} <= roles
    texts = [dict(p.meta).get('text', '') for p in frame.primitives if p.role == 'drain-label']
    assert any(t.startswith('Φ100 2%') for t in texts) and any('Φρεάτιο' in t for t in texts)
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)
    objs = [o for o in payload['objects'] if o.get('layer') == 'drain']
    assert objs and objs[0]['triangles']


def test_menu_places_a_manhole_from_the_plan_and_the_tree_lists_the_network():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        for k in range(2):
            _storey(window.stack, 3.0 * k); _bath(window.stack, 3.0 * k)
        menu = getattr(window, '_mockup_drainage_menu', None)
        if menu is not None:
            assert [a.text() for a in menu.actions()] == [v[0] for v in POINT_TYPES.values()]
        window._start_site_tool('drain_manhole', '')
        window.plan_view.sitePointRequested.emit('drain_manhole', 2.0, -1.5)
        assert sum(e.kind == 'drainage_point' for e in window.doc.entities.values()) == 1
        assert 'Φ100' in window.statusBar().currentMessage()
        window.stack.undo()
        assert not any(e.kind == 'drainage_point' for e in window.doc.entities.values())
    finally:
        window._mark_clean(); window.close(); app.processEvents()
