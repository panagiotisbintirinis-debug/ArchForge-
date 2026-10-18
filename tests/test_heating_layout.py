"""Heating layout: supply + return from the source, manifolds with their parts, underfloor loops (owner 17/10)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.mep.heating_layout import emitter_positions, fittings, route_heating


def _house(stack, z=0.0):
    """8 × 6, two rooms split at x = 4, a window in each room on the south wall (the left one wider)."""
    walls = {}
    for key, (x1, y1, x2, y2) in {'s': (0, 0, 8, 0), 'e': (8, 0, 8, 6), 'n': (8, 6, 0, 6), 'w': (0, 6, 0, 0), 'p': (4, 0, 4, 6)}.items():
        e = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': 2.7, 'thickness': 0.2})
        stack.execute(AddEntity(e))
        walls[key] = e
    for offset, width in ((2.0, 1.6), (6.0, 1.0)):
        stack.execute(AddEntity(Entity('window', {'offset': offset, 'width': width, 'height': 1.4, 'sill': 0.9}, parent_id=walls['s'].id)))
    return walls


def _point(stack, kind, x, y, z=0.0, **extra):
    e = Entity('heating_point', dict({'x': x, 'y': y, 'z': z, 'point_type': kind}, **extra))
    stack.execute(AddEntity(e))
    return e


def _connected(pipes):
    from archforge.scenarios.gate import _components
    return len(_components([(a, b) for a, b, _d in pipes]))


def _radiator_house():
    doc = Document(); st = CommandStack(doc); _house(st)
    src = _point(st, 'boiler', 7.5, 5.5)
    for x, y, rot, _room in emitter_positions(doc, 0.0):
        _point(st, 'radiator', x, y, rotation=rot)
    return doc, st, src


def test_radiators_go_under_the_widest_window_of_every_room():
    doc = Document(); st = CommandStack(doc); _house(st)
    pos = emitter_positions(doc, 0.0)
    assert len(pos) == 2
    assert sorted(round(p[0], 1) for p in pos) == [2.0, 6.0]                 # window centres
    assert all(0.1 < p[1] < 0.3 and p[2] == 0.0 for p in pos)               # against the inner face of the south wall


def test_radiators_on_a_manifold_get_supply_and_return_at_the_owner_sizes_with_every_part():
    doc, _st, _src = _radiator_house()
    r = route_heating(doc)
    rep = r['report']
    assert rep['system'] == 'radiators' and rep['distribution'] == 'manifold' and not rep['unserved']
    assert set(rep['length_by_dn']) == {18, 20}                              # Φ18 per radiator, Φ20 to the manifold
    assert rep['supply_m'] == pytest.approx(rep['return_m'])
    assert _connected(r['supply']) == 1 and _connected(r['return']) == 1     # one network each, source to radiator
    (m,) = r['manifolds']
    assert len(m['outlets']) == 2 and not m['underfloor'] and m['auto']
    parts = fittings(r)
    assert parts['heating.fitting.radiator_valve'][1] == 2 and parts['heating.fitting.lockshield'][1] == 2
    assert parts['heating.fitting.return_valve'][1] == 2 and parts['heating.fitting.ball_valve'][1] == 2
    assert 'heating.fitting.flow_meter' not in parts and 'heating.fitting.mixing_group' not in parts


def test_two_pipe_fan_coils_use_phi20_branches_and_phi26_mains():
    doc, st, src = _radiator_house()
    for e in [e for e in doc.entities.values() if e.params.get('point_type') == 'radiator']:
        st.execute(UpdateEntity(e.id, {'point_type': 'fan_coil'}))
    st.execute(UpdateEntity(src.id, {'heating_system': 'fan_coil', 'distribution': 'two_pipe'}))
    r = route_heating(doc)
    assert r['report']['distribution'] == 'two_pipe' and not r['manifolds']
    assert set(r['report']['length_by_dn']) <= {20, 26} and 26 in r['report']['length_by_dn']
    assert _connected(r['supply']) == 1
    assert fittings(r)['heating.fitting.fan_coil_valves'][1] == 2


def test_underfloor_needs_a_declared_spacing_then_lays_a_loop_per_room_from_the_manifold():
    doc = Document(); st = CommandStack(doc); _house(st)
    src = _point(st, 'boiler', 7.5, 5.5, heating_system='underfloor')
    r = route_heating(doc)
    assert not r['loops'] and any('βήμα' in w for w in r['report']['warnings'])    # nothing assumed
    st.execute(UpdateEntity(src.id, {'loop_spacing': 0.15}))
    r = route_heating(doc)
    assert len(r['loops']) == 4 and r['report']['loop_m'] > 2 * 20 / 0.15 * 0.8   # 24 m² → 2 loops each (≤ 100 m)
    assert set(r['report']['length_by_dn']) == {16, 20}
    (m,) = r['manifolds']
    assert m['underfloor'] and m['mixing'] and len(m['outlets']) == 4
    parts = fittings(r)
    assert parts['heating.fitting.flow_meter'][1] == 4 and parts['heating.fitting.mixing_group'][1] == 1
    assert parts['heating.underfloor.board'][1] == pytest.approx(48.0)
    # A heat pump already gives low-temperature water: no mixing group.
    st.execute(UpdateEntity(src.id, {'point_type': 'heat_pump'}))
    assert 'heating.fitting.mixing_group' not in fittings(route_heating(doc))


def test_no_source_leaves_the_radiators_unserved_and_no_pipe_is_counted():
    from archforge.mep.heating import heating_quantities
    doc = Document(); st = CommandStack(doc); _house(st)
    _point(st, 'radiator', 2.0, 0.2)
    r = route_heating(doc)
    assert r['report']['unserved'] and not r['supply']
    assert not any(q.code.startswith('heating.pipe.') for q in heating_quantities(doc))


def test_quote_has_a_line_for_every_pipe_size_and_part():
    from archforge.mep.heating import heating_quantities
    doc, _st, _src = _radiator_house()
    codes = {q.code: q for q in heating_quantities(doc)}
    assert {'heating.pipe.pexal.18', 'heating.pipe.pexal.20', 'heating.point.radiator', 'heating.point.boiler',
            'heating.fitting.radiator_valve', 'heating.manifold.2'} <= set(codes)
    assert codes['heating.pipe.pexal.18'].rule_status == 'OWNER_RULE_ENGINEER_REVIEW'


def test_menu_tools_place_points_and_the_plan_and_3d_show_the_network():
    from PySide6.QtWidgets import QApplication
    from archforge.core.plan_scene import build_plan_frame
    from archforge.project.persistence import load_project, save_project
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._no_modal_dialogs = True
        _house(window.stack)
        window._place_site_point('heat_boiler', 7.5, 5.5)
        assert window._auto_heating_emitters('radiator') == 2
        window._set_heating_option('heating_system', 'underfloor')
        window._set_heating_option('loop_spacing', 0.15)
        roles = {p.role for p in build_plan_frame(window.doc, layers=False).primitives}
        assert {'heat-supply', 'heat-return', 'heat-loop', 'heat-manifold', 'heat-fitting', 'heat-label'} <= roles
        payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(window.doc), [], doc=window.doc)
        parts = {o.get('render_part') for o in payload['objects']}
        assert {'heat:supply', 'heat:return', 'heat:loop', 'heat:manifold'} <= parts
        window.stack.undo(); window.stack.undo()
        assert route_heating(window.doc)['report']['system'] == 'radiators'
        path = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'heating_roundtrip.archforge')
        save_project(window.doc, path)
        again = load_project(path).doc
        assert route_heating(again)['report']['supply_m'] == route_heating(window.doc)['report']['supply_m']
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_underfloor_circuits_stay_within_100_m_with_their_leads():
    """Owner 17/10: «100 m μέγιστο μήκος» — a big room gets more loops, side by side, each ≤ 100 m with its leads."""
    from archforge.mep.heating_layout import MAX_CIRCUIT
    doc = Document(); st = CommandStack(doc)
    for x1, y1, x2, y2 in ((0, 0, 12, 0), (12, 0, 12, 8), (12, 8, 0, 8), (0, 8, 0, 0)):     # one 96 m² room
        st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    _point(st, 'boiler', 11.5, 7.5, heating_system='underfloor', loop_spacing=0.15)
    r = route_heating(doc)
    assert len(r['loops']) >= 6 and not r['report']['warnings']
    (m,) = r['manifolds']
    assert len(m['outlets']) == len(r['loops'])                              # one outlet (υδρονομέας) per loop
    for loop in r['loops']:
        lead = abs(loop['entry'][0] - m['x']) + abs(loop['entry'][1] - m['y'])
        assert loop['length_m'] + 2 * lead <= MAX_CIRCUIT + 1.0
    assert sum(l['area_m2'] for l in r['loops']) == pytest.approx(96.0, abs=0.1)


def test_manifold_board_lists_every_circuit_and_the_controls_reach_the_quote():
    """Owner 18/10: «το σημαντικό είναι ο πίνακας διανομής» — each manifold's circuits, numbered, with their parts."""
    from archforge.mep.heating_layout import manifold_schedule
    doc, _st, _src = _radiator_house()
    r = route_heating(doc)
    (board,) = manifold_schedule(r)
    assert [row['no'] for row in board['rows']] == ['Κ1', 'Κ2']
    assert all(row['dn'] == 18 and row['length_m'] > 0 and 'κεφαλή' in row['return'] for row in board['rows'])
    parts = fittings(r)
    assert parts['heating.control.actuator'][1] == 2 and parts['heating.control.wiring_centre'][1] == 1
    assert parts['heating.control.thermostat'][1] == 2


def test_heating_supplies_go_on_the_electrical_board():
    """The burner and every manifold's wiring centre get their supply; the board shows a heating circuit."""
    from archforge.core.commands import AddEntities
    from archforge.mep.electrical import design_circuits
    from archforge.mep.heating_layout import missing_supplies
    doc, st, _src = _radiator_house()
    st.execute(AddEntity(Entity('electrical_point', {'x': 7.5, 'y': 3.0, 'z': 0.0, 'point_type': 'panel'})))
    need = missing_supplies(doc)
    assert sorted(k for *_xyz, k, _n in need) == ['heating_supply', 'heating_supply']      # burner + wiring centre
    st.execute(AddEntities([Entity('electrical_point', {'x': x, 'y': y, 'z': z, 'point_type': k, 'power_w': 60.0})
                            for x, y, z, k, _n in need]))
    assert not missing_supplies(doc)
    (heating,) = [c for c in design_circuits(doc)['circuits'] if c['group'] == 'heating']
    assert len(heating['points']) == 2 and heating['breaker_a'] == 10
    # Without the data-sheet W the board asks for it, never guesses.
    doc2, st2, _ = _radiator_house()
    st2.execute(AddEntity(Entity('electrical_point', {'x': 7.5, 'y': 3.0, 'z': 0.0, 'point_type': 'panel'})))
    st2.execute(AddEntity(Entity('electrical_point', {'x': 7.6, 'y': 5.5, 'z': 0.0, 'point_type': 'heat_pump_supply'})))
    assert any('φύλλο' in w for w in design_circuits(doc2)['report']['warnings'])
