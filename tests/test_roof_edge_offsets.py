import pytest

from archforge.architecture.rooms import room_slab_geometry
from archforge.core.commands import CommandStack, CreateRoomRoofs, UpdateEntity
from archforge.core.model import Document, Entity


def _closed_room():
    doc = Document()
    walls = [
        Entity('wall', {'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2}, id='south'),
        Entity('wall', {'x1':4,'y1':0,'x2':4,'y2':3,'z':0,'height':3,'thickness':.2}, id='east'),
        Entity('wall', {'x1':4,'y1':3,'x2':0,'y2':3,'z':0,'height':3,'thickness':.2}, id='north'),
        Entity('wall', {'x1':0,'y1':3,'x2':0,'y2':0,'z':0,'height':3,'thickness':.2}, id='west'),
    ]
    for wall in walls:
        doc.add(wall)
    return doc


def _roof(doc):
    return next(e for e in doc.entities.values() if e.kind == 'room_roof')


def test_flat_roof_one_semantic_edge_offset_is_asymmetric_and_undoable():
    doc = _closed_room()
    stack = CommandStack(doc)
    face = doc.active_room_faces()[0]
    stack.execute(CreateRoomRoofs([face.signature], thickness=.20))
    roof = _roof(doc)
    baseline = room_slab_geometry(doc, roof)['points']

    stack.execute(UpdateEntity(roof.id, {'edge_offsets': {'east': .40}}))
    edited = room_slab_geometry(doc, roof)['points']
    assert min(x for x, _y in edited) == pytest.approx(-.10)
    assert max(x for x, _y in edited) == pytest.approx(4.50)
    assert min(y for _x, y in edited) == pytest.approx(-.10)
    assert max(y for _x, y in edited) == pytest.approx(3.10)

    stack.undo()
    assert room_slab_geometry(doc, roof)['points'] == baseline
    stack.redo()
    assert room_slab_geometry(doc, roof)['points'] == edited


def test_flat_roof_edge_offsets_round_trip_with_authoritative_document():
    doc = _closed_room()
    stack = CommandStack(doc)
    face = doc.active_room_faces()[0]
    stack.execute(CreateRoomRoofs([face.signature], thickness=.20))
    roof = _roof(doc)
    stack.execute(UpdateEntity(roof.id, {'edge_offsets': {'east': .40, 'north': -.05}}))

    restored = Document.from_dict(doc.to_dict())
    restored_roof = restored.get(roof.id)
    assert restored_roof.params['edge_offsets'] == {'east': .40, 'north': -.05}
    assert room_slab_geometry(restored, restored_roof)['points'] == room_slab_geometry(doc, roof)['points']


def _owner_room_with_short_closing_wall(z=0.0):
    # Walls from the owner's project: an 11 cm closing wall meets the top
    # wall only 1.6 deg off straight.
    doc = Document()
    pts = (((-4.545454545454545, 2.4727272727272727), (-0.2180290324909846, 2.4727272727272727)),
           ((-0.2180290324909846, 2.4727272727272727), (-0.2180290324909846, -0.89213)),
           ((-0.2180290324909846, -0.89213), (-4.65512, -0.89213)),
           ((-4.65512, -0.89213), (-4.65512, 2.47584)),
           ((-4.545454545454545, 2.4727272727272727), (-4.65512, 2.47584)))
    for a, b in pts:
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                                'z': z, 'height': 2.7, 'thickness': .15}))
    return doc


def test_flat_roof_has_no_spike_where_walls_meet_almost_straight():
    doc = _owner_room_with_short_closing_wall()
    stack = CommandStack(doc)
    stack.execute(CreateRoomRoofs([doc.active_room_faces()[0].signature], thickness=.20))
    points = room_slab_geometry(doc, _roof(doc))['points']
    xs = [p[0] for p in points]; ys = [p[1] for p in points]
    # Outer wall faces bound the roof (half thickness 0.075 m) plus a small margin.
    assert min(xs) >= -4.65512 - 0.075 - 0.02
    assert max(xs) <= -0.2180290324909846 + 0.075 + 0.02
    assert min(ys) >= -0.89213 - 0.075 - 0.02
    assert max(ys) <= 2.47584 + 0.075 + 0.02


def test_flat_roof_square_corners_are_unchanged_by_the_miter_limit():
    doc = _closed_room()
    stack = CommandStack(doc)
    stack.execute(CreateRoomRoofs([doc.active_room_faces()[0].signature], thickness=.20))
    points = sorted((round(x, 9), round(y, 9)) for x, y in room_slab_geometry(doc, _roof(doc))['points'])
    assert points == sorted([(-0.1, -0.1), (4.1, -0.1), (4.1, 3.1), (-0.1, 3.1)])


def test_flat_roof_has_no_spike_at_a_very_sharp_corner():
    # A sliver room: the corner at the origin is only ~2.9 deg wide, so an
    # unbounded miter would shoot the roof ~4 m past the walls.
    doc = Document()
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 0.3)), ((6, 0.3), (0, 0))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1],
                                'z': 0, 'height': 3, 'thickness': .2}))
    stack = CommandStack(doc)
    stack.execute(CreateRoomRoofs([doc.active_room_faces()[0].signature], thickness=.20))
    points = room_slab_geometry(doc, _roof(doc))['points']
    assert min(p[0] for p in points) >= -0.5
    assert max(p[0] for p in points) <= 6.5
    assert min(p[1] for p in points) >= -0.5
    assert max(p[1] for p in points) <= 0.8
