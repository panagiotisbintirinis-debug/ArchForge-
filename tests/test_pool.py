"""Pool tool (owner 17/10, scenario 9): basin, quantities, pipe velocity, HD 60364-7-702 zones, plan/3D/quote."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.site.pool import DEFAULTS, analyse, inner_diameter, smallest_ok, velocity, zone_of


def _pool(stack, **extra):
    p = dict(DEFAULTS, x=0.0, y=0.0, z=0.0, plant_x=9.0, plant_y=0.0)
    p.update(extra)
    e = Entity('pool', p, name='Πισίνα')
    stack.execute(AddEntity(e))
    return e


def test_basin_quantities_follow_the_sloped_floor():
    doc = Document(); st = CommandStack(doc)
    a = analyse(doc, _pool(st))                              # 8 × 4, 1.10 → 1.80
    assert a['volume_m3'] == pytest.approx(8 * 4 * 1.45)
    floor = 8 * 4 * (1 + (0.7 / 8) ** 2) ** 0.5
    walls = 2 * 8 * 1.45 + 4 * (1.10 + 1.80)
    assert a['wet_area_m2'] == pytest.approx(floor + walls, abs=0.01)
    rows = {r[0]: r for r in a['rows']}
    assert any('C25/30' in k for k in rows) and any('Ψηφίδα' in k for k in rows) and any('Στέψη' in k for k in rows)
    assert any('30 mA' in k for k in rows)                    # separate RCD for the equipment room


def test_owner_spec_pipes_phi50_phi63_fail_1_5_m_per_s_at_20_m3h_and_the_fix_is_proposed():
    # PVC-U PN10 = SDR 21: Φ63 → Ø57.0 inside, Φ50 → Ø45.2.
    assert inner_diameter(63) == pytest.approx(57.0) and inner_diameter(50) == pytest.approx(45.2)
    assert velocity(20, 63) == pytest.approx(2.18, abs=0.01)
    assert smallest_ok(20) == 90                                        # Φ75 gives 1.54 m/s
    doc = Document(); st = CommandStack(doc)
    a = analyse(doc, _pool(st, pump_flow_m3h=20.0))
    failing = [c for c in a['checks'] if not c[1]]
    assert len(failing) == 2 and all('Φ90' in c[2] for c in failing)
    a = analyse(doc, _pool(st, pump_flow_m3h=20.0, suction_dn=90, delivery_dn=90, y=20.0, plant_y=20.0))
    assert all(c[1] for c in a['checks'] if c[0].startswith(('Αναρρόφηση', 'Κατάθλιψη')))


def test_zones_0_1_forbid_a_socket_and_the_selv_transformer_stays_out_of_zone_1():
    doc = Document(); st = CommandStack(doc)
    pool = _pool(st, lights=4)
    assert zone_of(pool.params, 0, 0) == 0 and zone_of(pool.params, 5.5, 0) == 1 and zone_of(pool.params, 7.0, 0) == 2
    st.execute(AddEntity(Entity('electrical_point', {'x': 5.0, 'y': 0.0, 'z': 0.0, 'point_type': 'socket'}, name='Πρίζα')))
    checks = {c[0][:9]: c for c in analyse(doc, pool)['checks']}
    assert not checks['Ζώνες 0–1'][1] and 'Πρίζα' in checks['Ζώνες 0–1'][2]
    assert checks['Τροφοδοτι'][1]                                          # equipment room 4.5 m away
    st.execute(UpdateEntity(pool.id, {'plant_x': 5.0}))
    checks = {c[0][:9]: c for c in analyse(doc, doc.get(pool.id))['checks']}
    assert not checks['Τροφοδοτι'][1]


def test_overflow_pool_has_channel_and_grating_and_asks_for_the_balance_tank():
    doc = Document(); st = CommandStack(doc)
    a = analyse(doc, _pool(st, pool_type='overflow', skimmers=0))
    names = [r[0] for r in a['rows']]
    assert 'Κανάλι υπερχείλισης' in names and 'Σχάρα καναλιού υπερχείλισης' in names and not any('Στέψη' in n for n in names)
    assert any('εξισορρόπησης' in w for w in a['warnings'])


def test_moving_the_pool_takes_its_equipment_room_along():
    doc = Document(); st = CommandStack(doc)
    pool = _pool(st)
    st.execute(MoveEntities([pool.id], 1.0, 2.0))
    p = doc.get(pool.id).params
    assert (p['x'], p['y'], p['plant_x'], p['plant_y']) == (1.0, 2.0, 10.0, 2.0)


def test_menu_tool_places_a_pool_shown_in_plan_3d_and_quote():
    from PySide6.QtWidgets import QApplication
    from archforge.core.plan_scene import build_plan_frame
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.quantities.materials import all_lists
    from archforge.rendering.scene import build_pbr_scene_payload
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._no_modal_dialogs = True
        window._place_site_point('pool_place', 3.0, -8.0)
        (pool,) = [e for e in window.doc.entities.values() if e.kind == 'pool']
        assert pool.params['plant_x'] > 3.0 + 4.0 + 2.0                      # equipment room outside zone 1
        roles = {p.role for p in build_plan_frame(window.doc, layers=False).primitives}
        assert {'pool', 'pool-rim', 'pool-zone', 'pool-pipe', 'pool-plant', 'pool-label'} <= roles
        payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(window.doc), [], doc=window.doc)
        parts = {o.get('render_part') for o in payload['objects']}
        assert {'pool:tile', 'pool:water', 'pool:plant'} <= parts
        sheets = {name: rows for name, _t, rows, _n in all_lists(window.doc)}
        assert 'Πισίνα' in sheets and len(sheets['Πισίνα']) >= 10
        window.select_entity(pool.id) if hasattr(window, 'select_entity') else window.doc.select([pool.id])
        window.refresh_inspector()
        window.stack.undo()
        assert not [e for e in window.doc.entities.values() if e.kind == 'pool']
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_pool_supply_has_its_own_circuit_and_its_own_rcd_on_the_board():
    from PySide6.QtWidgets import QApplication
    from archforge.mep.electrical import design_circuits
    from archforge.mep.electrical_board import settings
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._no_modal_dialogs = True
        window.stack.execute(AddEntity(Entity('electrical_point', {'x': 0.0, 'y': 5.0, 'z': 0.0, 'point_type': 'panel'})))
        window.stack.execute(AddEntity(Entity('electrical_point', {'x': 1.0, 'y': 5.0, 'z': 0.0, 'point_type': 'socket'})))
        window._place_pool(3.0, -8.0, supply_w=1800.0)
        (pool,) = [c for c in design_circuits(window.doc)['circuits'] if c['group'] == 'pool']
        assert pool['breaker_a'] == 16 and pool['load_w'] == 1800
        groups = settings(window.doc)['rcd_groups']
        assert groups[pool['id']] == 2                                     # Δ2: its own 30 mA RCD, the house on Δ1
        window.stack.undo()                                                # pool and its supply go together
        assert not [e for e in window.doc.entities.values() if e.params.get('point_type') == 'pool_supply']
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_the_pool_is_a_hole_in_the_ground():
    """Open since 17/10 («η λεκάνη χωρίς τρύπα στο έδαφος του 3D»): the terrain stops at the basin's outer face."""
    from archforge.geometry.mesh_validation import validate_mesh
    from archforge.geometry.mesh import MeshPayload
    from archforge.site.terrain import building_exclusions, terrain_mesh
    doc = Document(); stack = CommandStack(doc)
    _pool(stack, length=8.0, width=4.0)                                  # inside 8 × 4, walls 25 cm
    p = {"x0": -10.0, "y0": -10.0, "x1": 10.0, "y1": 10.0, "elevation": 0.0, "slope_x": 0.0, "slope_y": 0.0, "thickness": 0.5}
    v, t, r = terrain_mesh(p, exclusions=building_exclusions(doc))
    assert validate_mesh(MeshPayload(v, t, r)).watertight
    area = 0.0
    for tri, role in zip(t, r):
        if role != "top":
            continue
        a, b, c = [v[i] for i in tri]
        x, y = sum(q[0] for q in (a, b, c)) / 3, sum(q[1] for q in (a, b, c)) / 3
        assert not (abs(x) < 4.25 - 1e-7 and abs(y) < 2.25 - 1e-7)
        area += abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
    assert area == pytest.approx(400 - 8.5 * 4.5)
