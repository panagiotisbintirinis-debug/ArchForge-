from archforge.core.model import Document, Entity
from archforge.architecture.topology import room_faces
from archforge.architecture.rooms import create_room_floor, room_floor_geometry
from archforge.core.plan_scene import entity_primitive
from archforge.core.view_frame import entity_view_primitives


def wall(x1,y1,x2,y2,z=0.0):
    return Entity('wall',{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'z':z,'height':2.7,'thickness':0.15})


def rectangle(doc,z=0.0):
    walls=[]
    for a,b in [((0,0),(4,0)),((4,0),(4,3)),((4,3),(0,3)),((0,3),(0,0))]:
        e=wall(*a,*b,z=z);doc.add(e);walls.append(e)
    return walls


def test_create_room_floor_links_to_boundary_walls():
    d=Document();walls=rectangle(d);sig=room_faces(d)[0].signature
    f=create_room_floor(d,sig,thickness=.2)
    assert f.kind=='room_floor' and f.params['room_signature']==sig
    assert all(f.id in d.dependencies.get(w.id,set()) for w in walls)


def test_room_floor_geometry_follows_room_boundary_without_copying_points():
    d=Document();walls=rectangle(d);sig=room_faces(d)[0].signature;f=create_room_floor(d,sig)
    assert 'points' not in f.params
    before=room_floor_geometry(d,f);assert before['points'][1] != ()
    # Move a connected corner by editing the two joined semantic wall endpoints.
    d.update(walls[0].id,{'x2':5,'y2':0})
    d.update(walls[1].id,{'x1':5,'y1':0})
    after=room_floor_geometry(d,f)
    assert after is not None and after['points']!=before['points'] and after['room_signature']==sig


def test_room_floor_becomes_dormant_if_room_opens_and_returns_when_restored():
    d=Document();walls=rectangle(d);sig=room_faces(d)[0].signature;f=create_room_floor(d,sig)
    original=walls[-1].params.copy();d.update(walls[-1].id,{'x2':1,'y2':1})
    assert room_floor_geometry(d,f) is None
    d.update(walls[-1].id,original)
    assert room_floor_geometry(d,f) is not None


def test_room_floor_respects_level_and_offset():
    d=Document();rectangle(d,z=3);sig=room_faces(d,z=3)[0].signature;f=create_room_floor(d,sig,thickness=.25,offset_z=.1)
    g=room_floor_geometry(d,f)
    assert abs(g['z']-3.1)<1e-9 and abs(g['thickness']-.25)<1e-9


def test_room_floor_plan_primitive_uses_live_polygon():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature;f=create_room_floor(d,sig)
    p=entity_primitive(d,f.id)
    assert p.role=='room-floor' and p.entity_id==f.id and len(p.points)==4


def test_room_floor_projects_as_slab_in_elevation():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature;f=create_room_floor(d,sig,thickness=.2)
    p=entity_view_primitives(d,f.id,'XZ')[0]
    assert p.role=='room-floor'
    assert min(z for _,z in p.points)==0 and max(z for _,z in p.points)==.2


def test_room_floor_persists_semantically_and_dependencies_reload():
    d=Document();walls=rectangle(d);sig=room_faces(d)[0].signature;f=create_room_floor(d,sig,thickness=.18)
    q=Document.from_dict(d.to_dict());rf=q.get(f.id)
    assert rf.kind=='room_floor' and 'points' not in rf.params
    assert room_floor_geometry(q,rf) is not None
    assert all(f.id in q.dependencies.get(w.id,set()) for w in walls)


def test_create_floor_rejects_inactive_room_signature():
    d=Document();rectangle(d)
    try:
        create_room_floor(d,'room-0000000000000000')
        assert False
    except ValueError:
        pass
