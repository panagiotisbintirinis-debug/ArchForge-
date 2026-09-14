from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack, CreateRoomFloors
from archforge.architecture.topology import room_faces
from archforge.architecture.rooms import room_floor_geometry


def wall(x1,y1,x2,y2):
    return Entity('wall',{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'z':0.0,'height':2.7,'thickness':0.15})


def rectangle(doc,x0=0,w=4):
    walls=[]
    for a,b in [((x0,0),(x0+w,0)),((x0+w,0),(x0+w,3)),((x0+w,3),(x0,3)),((x0,3),(x0,0))]:
        e=wall(*a,*b);doc.add(e);walls.append(e)
    return walls


def test_create_room_floors_is_single_undo_step():
    d=Document();rectangle(d);s=CommandStack(d);sig=room_faces(d)[0].signature
    s.execute(CreateRoomFloors([sig],thickness=.2))
    floors=[e for e in d.entities.values() if e.kind=='room_floor']
    assert len(floors)==1 and floors[0].params['thickness']==.2 and len(s.done)==1
    s.undo();assert not [e for e in d.entities.values() if e.kind=='room_floor']
    s.redo();assert len([e for e in d.entities.values() if e.kind=='room_floor'])==1


def test_create_room_floors_handles_multiple_rooms_atomically():
    d=Document();rectangle(d,0);rectangle(d,10);faces=room_faces(d);s=CommandStack(d)
    s.execute(CreateRoomFloors([f.signature for f in faces]))
    assert len([e for e in d.entities.values() if e.kind=='room_floor'])==2
    s.undo();assert len([e for e in d.entities.values() if e.kind=='room_floor'])==0


def test_create_room_floors_does_not_duplicate_existing_floor():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature;s=CommandStack(d)
    s.execute(CreateRoomFloors([sig]));first=[e.id for e in d.entities.values() if e.kind=='room_floor']
    s.execute(CreateRoomFloors([sig]));second=[e.id for e in d.entities.values() if e.kind=='room_floor']
    assert second==first


def test_auto_floor_tracks_wall_edit_after_command_creation():
    d=Document();walls=rectangle(d);sig=room_faces(d)[0].signature;s=CommandStack(d);s.execute(CreateRoomFloors([sig]))
    floor=next(e for e in d.entities.values() if e.kind=='room_floor');before=room_floor_geometry(d,floor)['points']
    # preserve the room by moving a shared corner on both participating walls
    d.update(walls[0].id,{'x2':5,'y2':.5});d.update(walls[1].id,{'x1':5,'y1':.5})
    after=room_floor_geometry(d,floor)['points']
    assert after!=before and floor.id in d.dirty
