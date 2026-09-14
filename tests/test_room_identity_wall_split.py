from archforge.architecture.room_identity import room_id_for_signature
from archforge.core.model import Document, Entity


def _wall(a,b):
    return Entity('wall',{
        'x1':a[0],'y1':a[1],'x2':b[0],'y2':b[1],
        'z':0,'height':2.8,'thickness':0.2,
    })


def test_room_identity_survives_collinear_boundary_wall_split():
    doc=Document();walls=[]
    for a,b in [((0,0),(6,0)),((6,0),(6,4)),((6,4),(0,4)),((0,4),(0,0))]:
        w=_wall(a,b);doc.add(w);walls.append(w)
    before=doc.active_room_faces();assert len(before)==1
    old_signature=before[0].signature;room_id=room_id_for_signature(doc,old_signature)
    doc.set_room_metadata(old_signature,name='Workshop')

    # Replace one physical boundary by two collinear semantic walls. The topology
    # fingerprint and polygon vertex count change, but the enclosed physical space does not.
    doc.remove(walls[0].id)
    doc.add(_wall((0,0),(2.5,0)))
    doc.add(_wall((2.5,0),(6,0)))

    after=doc.active_room_faces();assert len(after)==1
    new_signature=after[0].signature
    assert new_signature!=old_signature
    assert len(after[0].polygon)==len(before[0].polygon)+1
    assert room_id_for_signature(doc,new_signature)==room_id
    assert doc.room_metadata(new_signature)=={'name':'Workshop'}
