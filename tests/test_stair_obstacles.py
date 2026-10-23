"""Found driving the two-storey house as a user (owner 14/10, «πάρε τη θέση του χρήστη»; again 23/10): an L stair
«fitted» in the living room with its landing in the swing of the bedroom door and its upper flight along the
kitchen run — only walls were looked at.  Now the free space each side of a door and the cabinets / objects of
the storey count as well: the stair moves clear of them, or is shown red."""
import copy
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.architecture.stairs import (candidate_from_params, stair_obstacle_conflicts, stair_obstacles,
                                           stair_wall_conflicts)
from archforge.core.commands import AddEntity, CommandStack, CreateFloorLevel, SetWorkPlane
from archforge.core.interaction import StairPlaceTransaction
from archforge.core.model import Document, Entity


def _house(door=True, cabinet=False):
    """Living room 6 × 8 (x 0–6), bedroom door in the wall x = 6 at y 6,8; storey above at +2,70."""
    doc = Document(); stack = CommandStack(doc); ids = {}
    for name, (a, b) in {'s': ((0, 0), (10, 0)), 'e': ((10, 0), (10, 8)), 'n': ((10, 8), (0, 8)),
                         'w': ((0, 8), (0, 0)), 'mid': ((6, 0), (6, 8))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7, 'thickness': 0.25})
        stack.execute(AddEntity(e)); ids[name] = e.id
    if door:
        d = Entity('door', {'offset': 6.8, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=ids['mid'])
        stack.execute(AddEntity(d)); ids['door'] = d.id
    if cabinet:
        c = Entity('cabinet', {'x': 3.0, 'y': 7.55, 'z': 0.0, 'rotation': 0.0, 'width': 1.2, 'depth': 0.6,
                               'height': 0.9, 'cabinet_type': 'base'})
        stack.execute(AddEntity(c)); ids['cab'] = c.id
    plane = copy.deepcopy(doc.work_plane)
    stack.execute(CreateFloorLevel('Floor 2', 2.7))
    stack.execute(SetWorkPlane(plane))
    return doc, stack, ids


def test_a_stair_in_front_of_a_door_or_on_a_cabinet_is_a_conflict():
    doc, stack, ids = _house(cabinet=True)
    tx = StairPlaceTransaction(doc, stack, (1.0, 4.0)); tx.update(5.0, 4.0)
    base = tx.active_candidate.to_params()
    obstacles = stair_obstacles(doc, 0.0, 2.7)
    assert {oid for oid, _ in obstacles} == {ids['door'], ids['cab']}
    # A straight flight along the wall x = 6, through the door's free space (no wall is crossed).
    at_door = candidate_from_params(dict(base, layout='straight', x=5.3, y=2.5, angle_deg=90.0))
    assert not stair_wall_conflicts(doc, at_door)
    assert stair_obstacle_conflicts(at_door, obstacles) == [ids['door']]
    # Running west along the north wall, over the cabinet.
    on_cab = candidate_from_params(dict(base, layout='straight', x=5.0, y=7.4, angle_deg=180.0))
    assert ids['cab'] in stair_obstacle_conflicts(on_cab, obstacles)
    # In the middle of the room: clear.
    free = candidate_from_params(dict(base, layout='straight', x=1.0, y=2.0, angle_deg=0.0))
    assert stair_obstacle_conflicts(free, obstacles) == []


def test_dragging_the_stair_next_to_the_door_moves_it_clear_or_shows_red():
    doc, stack, ids = _house()
    tx = StairPlaceTransaction(doc, stack, (5.9, 7.0))
    for x in (4.5, 3.0, 1.5):
        tx.update(x, 7.0)
    obstacles = stair_obstacles(doc, 0.0, 2.7)
    c = tx.active_candidate
    if tx.preview['fits']:
        assert stair_obstacle_conflicts(c, obstacles) == []
    else:
        assert stair_obstacle_conflicts(c, obstacles) or stair_wall_conflicts(doc, c)
        assert 'πόρτα' in tx.preview['suggestions'][0]


def test_stairs_meet_in_3d_only_where_the_headroom_is_missing():
    """Driving the house: the basement stair came up where the ground floor's stair starts (its low steps over the
    opening) — a clash. A stacked stairwell (S02: the same U a storey higher) is not: the flights are 3 m apart."""
    from archforge.architecture.stairs import _stair_cells, _stairs_clash
    doc, stack, ids = _house(door=False)
    tx = StairPlaceTransaction(doc, stack, (1.0, 1.5)); tx.update(1.0, 6.0)
    base = tx.active_candidate.to_params()
    ground = candidate_from_params(dict(base, layout='straight', x=1.0, y=1.5, angle_deg=90.0))
    cells = _stair_cells(ground)
    # Same floor, crossing it: clash.
    across = candidate_from_params(dict(base, layout='straight', x=-0.5 + 0.6, y=3.0, angle_deg=0.0))
    assert _stairs_clash(across, cells)
    # The same flight a storey lower (stacked): no clash.
    rise = ground.upper_z - ground.lower_z
    below = candidate_from_params(dict(base, layout='straight', x=1.0, y=1.5, angle_deg=90.0,
                                       lower_z=-3.0, upper_z=0.0, upper_floor_z=0.0, riser_height=3.0 / base['riser_count']))
    assert not _stairs_clash(below, cells) and rise > 2.1
    # A basement flight arriving where the ground flight starts (its top under the ground flight's low steps): clash.
    under = candidate_from_params(dict(base, layout='straight', x=1.0, y=-2.0, angle_deg=90.0,
                                       lower_z=-3.0, upper_z=0.0, upper_floor_z=0.0, riser_height=3.0 / base['riser_count']))
    assert _stairs_clash(under, cells)


def test_the_stair_from_the_basement_is_drawn_on_the_floor_it_arrives_on():
    """Driving the house: the basement stair arrives at +0,15 (finished floor over the slab) and the ground floor
    plan, at 0,00, did not draw it — no ΚΑΤ, no opening."""
    from archforge.core.plan_scene import build_plan_frame
    doc, stack, ids = _house(door=False)
    plane = copy.deepcopy(doc.work_plane)
    stack.execute(CreateFloorLevel('Basement', -3.0))
    tx = StairPlaceTransaction(doc, stack, (1.0, 1.5)); tx.update(1.0, 4.5)
    params = tx.active_candidate.to_params()
    params.update(upper_z=0.15, riser_height=(0.15 - params['lower_z']) / params['riser_count'])   # finished floor
    e = Entity('stair', params); stack.execute(AddEntity(e))
    stack.execute(SetWorkPlane(plane))
    roles = [p.role for p in build_plan_frame(doc).primitives if p.entity_id == e.id]
    assert 'stair' in roles and any(r.startswith('stair-') for r in roles)


def test_an_outside_stair_must_arrive_on_the_balcony_not_in_mid_air():
    """Driving the house: dragged towards the balcony, the automatic L turned away and ended in mid-air at +2,85."""
    from archforge.architecture.stairs import arrival_point
    doc, stack, ids = _house(door=False)
    up = 2.7
    stack.execute(AddEntity(Entity('floor', {'points': [[1, -1.5], [9, -1.5], [9, 0], [1, 0]], 'z': up - 0.18,
                                             'thickness': 0.18, 'role': 'balcony'})))
    tx = StairPlaceTransaction(doc, stack, (13.8, -0.8)); tx.update(9.4, -0.8)
    base = tx.active_candidate.to_params()
    obstacles = stair_obstacles(doc, 0.0, up)
    away = candidate_from_params(dict(base, layout='l', x=13.8, y=-0.8, angle_deg=180.0, turn_direction=-1))
    assert 'arrival' in stair_obstacle_conflicts(away, obstacles)
    onto = candidate_from_params(dict(base, layout='straight', x=13.6, y=-0.75, angle_deg=180.0))
    ax, ay = arrival_point(onto)
    assert 1 < ax < 9 and -1.5 < ay < 0
    assert 'arrival' not in stair_obstacle_conflicts(onto, obstacles)


def test_a_stair_arriving_at_the_balcony_opens_its_railing_in_one_undo():
    """Driving the house: the outside stair reached the balcony through its closed railing."""
    from archforge.architecture.balcony import balcony_entities
    from archforge.core.commands import AddEntities
    doc, stack, ids = _house(door=False)
    stack.execute(AddEntities(balcony_entities(doc, [(1, -1.5), (9, -1.5), (9, 0), (1, 0)], 2.7)))
    before = [e.params['points'] for e in doc.entities.values() if e.kind == 'railing']
    tx = StairPlaceTransaction(doc, stack, (13.8, -0.75)); tx.update(9.4, -0.75)
    assert tx.preview['fits'] and tx.active_candidate.layout == 'straight'
    sid = tx.commit()
    rails = [e.params['points'] for e in doc.entities.values() if e.kind == 'railing' and 'stair_side' not in e.params]
    # The stair itself has its railings on its open sides from the start (same undo).
    own = [e for e in doc.entities.values() if e.kind == 'railing' and e.parent_id == sid and e.visible]
    assert doc.get(sid).params['railing'] == 'auto' and own
    assert rails != before                                                 # opened (a closed one) or cut in two
    # Nothing of the railing left across the stair's top (x = 9, its width round y = -0,75).
    w = doc.get(sid).params['width']
    for pts in rails:
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            if abs(ax - 9) < 0.05 and abs(bx - 9) < 0.05:
                lo, hi = sorted((ay, by))
                assert hi <= -0.75 - w / 2 + 1e-6 or lo >= -0.75 + w / 2 - 1e-6
    stack.undo()
    assert sid not in doc.entities and [e.params['points'] for e in doc.entities.values() if e.kind == 'railing'] == before
    assert not [e for e in doc.entities.values() if e.kind == 'railing' and 'stair_side' in e.params]
