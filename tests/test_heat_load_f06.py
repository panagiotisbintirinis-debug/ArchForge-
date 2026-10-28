"""F06 (owner 28/10): heating without a source → suggested power from the losses + a standard connection point.

The kind of source stays the mechanical engineer's decision; temperatures and air changes are the owner's
assumptions, changed per project on the connection point; what is not measured is said.
"""
import math

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import heat_load as H


def _box(wall_type='brick_double_insulated', window=True):
    doc = Document()
    stack = CommandStack(doc)
    pts = [(0, 0), (6, 0), (6, 5), (0, 5), (0, 0)]
    ids = []
    for a, b in zip(pts, pts[1:]):
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3.0,
                            'thickness': .3, 'wall_type': wall_type})
        stack.execute(AddEntity(e))
        ids.append(e.id)
    if window:
        stack.execute(AddEntity(Entity('window', {'offset': 3.0, 'width': 1.0, 'height': 1.0, 'sill': .9},
                                       parent_id=ids[0])))
    return doc, stack


def test_the_power_is_the_sum_of_walls_and_air_with_the_owner_assumptions():
    from archforge.architecture.wall_types import indicative_u
    doc, _ = _box()
    r = H.heat_load(doc)
    u = indicative_u('brick_double_insulated')
    dt = 20.0 - 12.0
    walls = (2 * (6 + 5) * 3.0 - 1.0) * u * dt                     # exterior wall faces on the axes, minus the window
    parts = dict(r['parts'])
    assert parts['Εξωτερικοί τοίχοι'] == pytest.approx(walls, abs=1)
    assert parts['Κουφώματα'] == 0                                  # no U given: not counted, said
    assert any('κουφώματα 1,0 m²' in n for n in r['not_counted'])
    assert parts['Αερισμός'] == pytest.approx(H.AIR_HEAT * 0.5 * r['volume_m3'] * dt, abs=1)
    assert r['delta_t'] == 8.0 and 'υπόθεση, όχι μελέτη' in H.summary(r)
    assert {'οροφή / στέγη', 'δάπεδο', 'θερμογέφυρες'} <= set(r['not_counted'])


def test_walls_without_a_build_up_are_said_until_the_project_gives_a_u():
    doc, stack = _box(wall_type='generic', window=False)
    r = H.heat_load(doc)
    assert dict(r['parts'])['Εξωτερικοί τοίχοι'] == 0
    assert any('4 εξωτερικοί τοίχοι χωρίς σύνθεση' in n for n in r['not_counted'])
    stack.execute(AddEntity(Entity('heating_point', {'x': 1, 'y': 1, 'z': 0, 'point_type': 'heat_source',
                                                     'heat_u_walls': 1.0, 'heat_theta_ext_winter': 0.0})))
    r = H.heat_load(doc)
    assert dict(r['parts'])['Εξωτερικοί τοίχοι'] == pytest.approx(2 * (6 + 5) * 3.0 * 1.0 * 20.0, abs=1)
    assert r['delta_t'] == 20.0


def test_a_connection_point_only_without_a_source_with_the_suggested_power():
    doc, stack = _box()
    point = H.connection_point(doc)
    assert point.params['point_type'] == 'heat_source' and 'μηχανολόγος' in point.name
    assert point.params['power_w'] == H.heat_load(doc)['watts'] > 0
    assert point.params['heat_theta_int'] == 20.0                        # the assumptions live on the point
    stack.execute(AddEntity(point))
    assert H.connection_point(doc) is None                               # a source exists now


def test_the_point_is_outside_a_blind_wall_never_inside_a_room():
    """Owner 28/10: «απλά ένα σημείο… μην το βάλεις μέσα στο χώρο»."""
    from archforge.geometry.regions import point_in_polygon
    from archforge.mep.heating_layout import BODY
    doc, _stack = _box()                                                 # the window is on the y = 0 wall
    point = H.connection_point(doc)
    x, y = point.params['x'], point.params['y']
    assert not any(point_in_polygon(x, y, f.polygon) for f in doc.active_room_faces(z=0.0))
    assert y == pytest.approx(5.0 + 0.15 + BODY['heat_source'][1] / 2)   # just outside the blind wall, not the window one
    assert 'room_w' not in point.params                                  # a point, not a room
