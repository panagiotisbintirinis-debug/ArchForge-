"""Owner 06/11: «Σε πολλούς ορόφους κάθε όροφος πρέπει να έχει υποπίνακα — αυτός είναι κανόνας».

A storey with loads, other than the main panel's, without a «Υποπίνακας ορόφου» is said; «Υποπίνακες ορόφων
(αυτόματα)» places them (one undo); each storey's circuits then come from its own board, never mixing storeys, and a
sized feeder runs from the main panel to every sub-board."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import electrical as E


def _house():
    doc = Document(); doc.levels = {'Ground': 0.0, 'Floor 1': 2.7}
    st = CommandStack(doc)
    for z in (0.0, 2.7):
        for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 6)), ((8, 6), (0, 6)), ((0, 6), (0, 0)), ((4, 0), (4, 6))):
            st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': z, 'height': 2.7,
                                                 'thickness': 0.25})))
    st.execute(AddEntity(Entity('electrical_point', {'point_type': 'panel', 'x': 0.13, 'y': 3.0, 'z': 0.0})))
    for z in (0.0, 2.7):
        for t, x, y in (('socket', 7.87, 1.5), ('socket', 2.0, 5.87), ('light', 2.0, 3.0), ('light', 6.0, 3.0),
                        ('switch', 3.87, 1.0)):
            st.execute(AddEntity(Entity('electrical_point', {'point_type': t, 'x': x, 'y': y, 'z': z})))
    return doc, st


def test_a_storey_without_its_sub_board_is_said_and_one_command_places_it():
    doc, st = _house()
    assert E.missing_subpanels(doc) == [2.7]
    d = E.design_circuits(doc)
    assert any('Υποπίνακας ορόφου' in w and 'κανόνας' in w for w in d['report']['warnings'])
    cmd = E.subpanel_command(doc)
    st.execute(cmd)
    subs = [e for e in doc.entities.values() if e.kind == 'electrical_point' and e.params['point_type'] == 'subpanel']
    assert len(subs) == 1 and abs(float(subs[0].params['z']) - 2.7) < 1e-9
    assert E.missing_subpanels(doc) == [] and E.subpanel_command(doc) is None
    d = E.design_circuits(doc)
    assert not any('Υποπίνακας ορόφου' in w for w in d['report']['warnings'])
    st.undo()
    assert E.missing_subpanels(doc) == [2.7]                                   # one undo


def test_each_storey_from_its_own_board_and_a_sized_feeder_from_the_main_panel():
    doc, st = _house()
    st.execute(E.subpanel_command(doc))
    sub = next(e for e in doc.entities.values() if e.kind == 'electrical_point' and e.params['point_type'] == 'subpanel')
    panel = next(e for e in doc.entities.values() if e.kind == 'electrical_point' and e.params['point_type'] == 'panel')
    d = E.design_circuits(doc)
    for c in d['circuits']:
        floors = {E._floor_of(doc, float(doc.get(p).params['z'])) for p in c['points']}
        assert len(floors) == 1                                                # never two storeys in one circuit
        assert c['board'] == (sub.id if floors == {2.7} else panel.id)
    (feeder,) = d['feeders']
    upstairs = sum(c['load_w'] for c in d['circuits'] if c['board'] == sub.id)
    assert feeder['board'] == panel.id and feeder['points'] == [sub.id] and feeder['load_w'] == upstairs
    assert feeder['breaker_a'] >= feeder['current_a'] and feeder['cable_mm2'] >= 2.5
    r = E.route_cables(doc)
    assert [x for x in r['runs'] if x[3] == feeder['id']]                     # the feeder is routed (riser)
    from archforge.scenarios.gate import _components, _nearest_component
    for c in r['circuits'] + r['feeders']:
        b = doc.get(c['board'])
        comp = _components([(a, bb) for a, bb, _g, cid in r['runs'] if cid == c['id']])
        home = _nearest_component(comp, (float(b.params['x']), float(b.params['y'])))
        assert all(_nearest_component(comp, (float(doc.get(p).params['x']), float(doc.get(p).params['y']))) == home
                   for p in c['points']), c['id']


def test_one_storey_needs_no_sub_board():
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('electrical_point', {'point_type': 'panel', 'x': 0.1, 'y': 1.0, 'z': 0.0})))
    st.execute(AddEntity(Entity('electrical_point', {'point_type': 'socket', 'x': 3.0, 'y': 1.0, 'z': 0.0})))
    assert E.missing_subpanels(doc) == [] and E.subpanel_command(doc) is None
