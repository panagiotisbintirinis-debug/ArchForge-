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
