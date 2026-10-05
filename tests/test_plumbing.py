"""Plumbing points in the Document; cold/hot networks derived from them."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.mep.plumbing import POINT_TYPES, SCREED, route_plumbing, route_plumbing_cached


def _house(stack):
    for x1, y1, x2, y2 in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0), (4, 0, 4, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': 0.2})))


def _point(stack, kind, x, y, z=0.0):
    e = Entity('plumbing_point', {'x': x, 'y': y, 'z': z, 'point_type': kind}, name=POINT_TYPES[kind][0])
    stack.execute(AddEntity(e))
    return e


def _ends(pipes):
    return {(round(p[0], 3), round(p[1], 3)) for a, b, _d in pipes for p in (a, b)}


def _touches(pipes, x, y, tol=0.25):
    return any(math.hypot(px - x, py - y) <= tol for px, py in _ends(pipes))


def test_every_fixture_gets_the_water_it_needs_and_wc_only_cold():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _point(stack, 'water_supply', 0.3, 0.3)
    _point(stack, 'solar_heater', 6.0, 3.0, z=6.0)
    basin = _point(stack, 'basin', 5.0, 5.7)
    wc = _point(stack, 'wc', 6.5, 5.7)
    sink = _point(stack, 'kitchen_sink', 1.0, 5.7)
    r = route_plumbing(doc)
    assert r['report']['unserved'] == []
    for e in (basin, wc, sink):
        assert _touches(r['cold'], e.params['x'], e.params['y'])
    assert _touches(r['hot'], basin.params['x'], basin.params['y'] + 0.05, tol=0.3)
    assert not _touches(r['hot'], wc.params['x'], wc.params['y'], tol=0.15)
    # The solar heater on the roof drops a riser and also gets a cold feed.
    assert any(abs(a[2] - b[2]) > 5 for a, b, _d in r['hot'])
    assert _touches(r['cold'], 6.0, 3.0)
    # Runs are axis-aligned, in the screed, sized 16/20 mm.
    for a, b, d in r['cold'] + r['hot']:
        assert d in (16, 20)
        assert a[0] == pytest.approx(b[0]) or a[1] == pytest.approx(b[1])
    assert {d for _a, _b, d in r['cold']} == {16, 20}


def test_fixture_without_a_source_is_reported_not_guessed():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _point(stack, 'basin', 5.0, 5.7)
    r = route_plumbing(doc)
    assert r['cold'] == [] and r['hot'] == [] and len(r['report']['unserved']) == 2
    assert 'μηχανολόγο' in r['report']['provenance']


def test_moving_a_point_reroutes_immediately_and_undo_restores():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _point(stack, 'water_supply', 0.3, 0.3)
    wm = _point(stack, 'washing_machine', 3.6, 0.4)
    before = route_plumbing_cached(doc)['report']['cold_m']
    stack.execute(MoveEntities([wm.id], 0.0, 5.0))
    after = route_plumbing_cached(doc)
    assert after['report']['cold_m'] > before and _touches(after['cold'], 3.6, 5.4)
    stack.undo()
    assert route_plumbing_cached(doc)['report']['cold_m'] == pytest.approx(before)


def test_pipes_in_plan_and_on_the_mep_layer_in_3d():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc); _house(stack)
    _point(stack, 'water_supply', 0.3, 0.3); _point(stack, 'water_heater', 7.5, 0.4)
    _point(stack, 'shower', 7.5, 5.5)
    roles = [p.role for p in build_plan_frame(doc).primitives]
    assert 'pipe-cold' in roles and 'pipe-hot' in roles and roles.count('plumbing-point') == 3
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    pipes = [o for o in objs if o.get('layer') == 'mep']
    assert {o['render_part'] for o in pipes} == {'mep:cold', 'mep:hot'}
    assert all(o['id'] == '' for o in pipes)        # derived, not selectable entities
    zs = [v[2] for o in pipes for v in o['vertices']]
    assert min(zs) == pytest.approx(SCREED - 0.02, abs=0.005)   # drawn Ø40 for legibility


def test_menu_places_points_and_layer_can_be_hidden():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window._mockup_plumbing_menu.actions()
        window._start_site_tool('plumb_water_supply', '')
        window.plan_view.sitePointRequested.emit('plumb_water_supply', 0.5, 0.5)
        window.plan_view.sitePointRequested.emit('plumb_basin', 3.0, 0.5)
        kinds = sorted(e.params['point_type'] for e in window.doc.entities.values() if e.kind == 'plumbing_point')
        assert kinds == ['basin', 'water_supply']
        window._mep_layer_action.setChecked(False)
        assert 'mep' in window.pbr_view.hidden_layers
    finally:
        window._mark_clean(); window.close(); app.processEvents()
