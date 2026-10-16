"""Hood and extract fans in the Document; ducts to the outside derived from them."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.mep.ventilation import (POINT_TYPES, exterior_walls, route_ventilation, route_ventilation_cached)


def _walls(stack, segments, z=0.0, height=2.7):
    out = []
    for x1, y1, x2, y2 in segments:
        w = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': height, 'thickness': 0.2})
        stack.execute(AddEntity(w))
        out.append(w)
    return out


def _box(stack, w, d, partition_x=None, z=0.0):
    segs = [(0, 0, w, 0), (w, 0, w, d), (w, d, 0, d), (0, d, 0, 0)]
    if partition_x is not None:
        segs.append((partition_x, 0, partition_x, d))
    return _walls(stack, segs, z)


def _vent(stack, kind, x, y, z=0.0, **extra):
    e = Entity('ventilation_point', {'x': x, 'y': y, 'z': z, 'point_type': kind, **extra}, name=POINT_TYPES[kind][0])
    stack.execute(AddEntity(e))
    return e


def test_only_walls_with_open_space_on_one_side_are_exterior():
    doc = Document(); stack = CommandStack(doc)
    outer = _box(stack, 8, 6, partition_x=4)
    found = {w.id: n for w, n in exterior_walls(doc, 0.0)}
    assert set(found) == {w.id for w in outer[:4]}
    assert found[outer[0].id] == pytest.approx((0.0, -1.0))       # wall y=0 opens to -y
    assert found[outer[1].id] == pytest.approx((1.0, 0.0))        # wall x=8 opens to +x


def test_wall_hood_goes_straight_through_the_nearest_exterior_wall_under_the_ceiling():
    doc = Document(); stack = CommandStack(doc); _box(stack, 8, 6, partition_x=4)
    hood = _vent(stack, 'hood', 1.0, 5.6)
    r = route_ventilation(doc)
    info = r['report']['points'][hood.id]
    assert info['outlet'] == 'wall' and info['diameter'] == 125 and info['bends'] == 1
    assert info['horizontal_m'] == pytest.approx(0.3)
    (riser, run, through) = [(a, b) for a, b, _d, _p in r['ducts']]
    assert riser[0][2] == pytest.approx(2.10) and riser[1][2] == pytest.approx(2.60)   # 10 cm under the 2.70 ceiling
    assert run[1][:2] == pytest.approx((1.0, 5.9)) and through[1][:2] == pytest.approx((1.0, 6.15))
    (grille,) = r['terminals']
    assert grille['kind'] == 'wall' and grille['y'] == pytest.approx(6.15)
    assert 'μηχανολόγο' in r['report']['provenance']


def test_island_hood_rises_into_the_ceiling_and_reaches_the_nearest_outside_wall():
    doc = Document(); stack = CommandStack(doc); _box(stack, 8, 6, partition_x=4)
    hood = _vent(stack, 'hood', 1.5, 3.0)
    r = route_ventilation(doc)
    info = r['report']['points'][hood.id]
    assert info['outlet'] == 'wall' and info['horizontal_m'] == pytest.approx(1.4)
    assert r['terminals'][0]['x'] == pytest.approx(-0.15)
    assert info['wall_crossings'] == 0


def test_partition_in_the_way_is_reported_as_a_penetration():
    doc = Document(); stack = CommandStack(doc); _box(stack, 8, 6, partition_x=2)
    fan = _vent(stack, 'bath_fan', 2.5, 3.0)
    r = route_ventilation(doc)
    assert r['report']['points'][fan.id]['wall_crossings'] == 1
    assert any('διάτρηση' in w for w in r['report']['warnings'])


def test_interior_bathroom_far_from_outside_goes_through_the_roof_and_user_can_force_the_wall():
    doc = Document(); stack = CommandStack(doc); _box(stack, 14, 14)
    fan = _vent(stack, 'bath_fan', 7.0, 7.0)
    r = route_ventilation(doc)
    assert r['report']['points'][fan.id]['outlet'] == 'roof'
    (duct,) = r['ducts']
    assert duct[0][:2] == duct[1][:2] and duct[1][2] == pytest.approx(2.7 + 0.3 + 0.5)
    assert duct[2] == 100
    stack.execute(UpdateEntity(fan.id, {'outlet': 'wall'}))
    forced = route_ventilation_cached(doc)
    assert forced['report']['points'][fan.id]['outlet'] == 'wall'
    assert any('6.9 m > 4 m' in w for w in forced['report']['warnings'])
    stack.undo()
    assert route_ventilation_cached(doc)['report']['points'][fan.id]['outlet'] == 'roof'


def test_lower_storey_keeps_the_wall_outlet_and_flags_the_length():
    doc = Document(); stack = CommandStack(doc)
    doc.levels['Όροφος 1'] = 3.0
    _box(stack, 14, 14); _box(stack, 14, 14, z=3.0)
    fan = _vent(stack, 'wc_fan', 7.0, 7.0)
    r = route_ventilation(doc)
    info = r['report']['points'][fan.id]
    assert info['outlet'] == 'wall' and info['diameter'] == 100
    assert r['ducts'][1][0][2] == pytest.approx(3.0 - 0.20 - 0.10)      # under the slab above
    assert any('> 4 m' in w for w in r['report']['warnings'])


def test_large_hood_gets_a_bigger_duct_and_velocity_is_reported():
    doc = Document(); stack = CommandStack(doc); _box(stack, 8, 6)
    small = _vent(stack, 'hood', 1.0, 5.6)
    big = _vent(stack, 'hood', 6.0, 5.6, airflow=600.0)
    pts = route_ventilation(doc)['report']['points']
    assert pts[small.id]['diameter'] == 125 and pts[big.id]['diameter'] == 150
    assert pts[small.id]['velocity_ms'] == pytest.approx(9.1, abs=0.05)


def test_moving_a_point_reroutes_and_undo_restores():
    doc = Document(); stack = CommandStack(doc); _box(stack, 8, 6)
    hood = _vent(stack, 'hood', 1.0, 5.6)
    before = route_ventilation_cached(doc)['terminals'][0]
    stack.execute(MoveEntities([hood.id], 6.4, -2.6))
    after = route_ventilation_cached(doc)['terminals'][0]
    assert after['x'] == pytest.approx(8.15) and after['y'] == pytest.approx(3.0)
    stack.undo()
    assert route_ventilation_cached(doc)['terminals'][0] == before


def test_bad_outlet_is_rejected_by_the_document():
    doc = Document(); stack = CommandStack(doc)
    with pytest.raises(ValueError):
        stack.execute(AddEntity(Entity('ventilation_point', {'x': 0, 'y': 0, 'z': 0, 'point_type': 'hood', 'outlet': 'window'})))


def test_ducts_in_plan_and_on_the_vent_layer_in_3d():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc); _box(stack, 8, 6)
    _vent(stack, 'hood', 1.0, 5.6); _vent(stack, 'bath_fan', 7.5, 0.5)
    roles = [p.role for p in build_plan_frame(doc).primitives]
    assert roles.count('ventilation-point') == 2 and roles.count('vent-terminal') == 2 and 'duct' in roles
    assert roles.count('ventilation-label') == 2
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    vent = [o for o in objs if o.get('layer') == 'vent']
    assert {o['render_part'] for o in vent} == {'vent:duct', 'vent:terminal'}
    assert all(o['id'] == '' for o in vent)
    assert any(o['kind'] == 'ventilation_point' or o.get('id') for o in objs)


def test_menu_places_points_and_layer_can_be_hidden():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert len(window._mockup_ventilation_menu.actions()) == len(POINT_TYPES)
        window._start_site_tool('vent_hood', '')
        window.plan_view.sitePointRequested.emit('vent_hood', 1.0, 1.0)
        window.plan_view.sitePointRequested.emit('vent_bath_fan', 3.0, 1.0)
        kinds = sorted(e.params['point_type'] for e in window.doc.entities.values() if e.kind == 'ventilation_point')
        assert kinds == ['bath_fan', 'hood']
        window._vent_layer_action.setChecked(False)
        assert 'vent' in window.pbr_view.hidden_layers
    finally:
        window._mark_clean(); window.close(); app.processEvents()
