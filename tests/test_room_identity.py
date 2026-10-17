import os
import tempfile

from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack
from archforge.core.wall_junction import ConnectedWallEndpointStretchTransaction
from archforge.architecture.topology import room_faces, room_metrics
from archforge.core.plan_scene import build_plan_frame


def wall(x1,y1,x2,y2,z=0.0):
    return Entity('wall',{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'z':z,'height':2.7,'thickness':0.15})


def rectangle(doc):
    walls=[]
    for a,b in [((0,0),(4,0)),((4,0),(4,3)),((4,3),(0,3)),((0,3),(0,0))]:
        e=wall(*a,*b);doc.add(e);walls.append(e)
    return walls


def test_room_face_has_stable_signature_and_boundary_wall_ids():
    d=Document();walls=rectangle(d);face=room_faces(d)[0]
    assert face.signature.startswith('room-')
    assert set(face.wall_ids)=={w.id for w in walls}
    assert abs(room_metrics(face.polygon)['area']-12)<1e-9


def test_room_signature_survives_connected_corner_move():
    d=Document();walls=rectangle(d);before=room_faces(d)[0].signature;s=CommandStack(d)
    tx=ConnectedWallEndpointStretchTransaction(d,s,walls[0].id,2,grid=None);tx.update(5,0.5);tx.commit()
    after=room_faces(d)[0].signature
    assert after==before


def test_adjacent_rooms_get_distinct_signatures():
    d=Document()
    for a,b in [((0,0),(4,0)),((4,0),(8,0)),((8,0),(8,3)),((8,3),(4,3)),((4,3),(0,3)),((0,3),(0,0)),((4,0),(4,3))]:d.add(wall(*a,*b))
    faces=room_faces(d)
    assert len(faces)==2 and len({f.signature for f in faces})==2


def test_room_metadata_roundtrip_does_not_store_geometry_copy():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature
    d.set_room_metadata(sig,name='Living Room',use='Living',floor_finish='Oak')
    data=d.to_dict()
    # Room metadata was introduced in format 5. Newer project formats must preserve it
    # without forcing this subsystem's tests to freeze the whole application version.
    assert data['format']>=5 and data['room_data'][sig]['name']=='Living Room'
    assert 'points' not in data['room_data'][sig]
    q=Document.from_dict(data)
    assert q.room_metadata(sig)=={'name':'Living Room','use':'Living','floor_finish':'Oak'}
    assert q.active_room_faces()[0].signature==sig


def test_room_metadata_file_persistence():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature;d.set_room_metadata(sig,name='Kitchen',notes='Island')
    fd,path=tempfile.mkstemp(suffix='.archforge');os.close(fd)
    try:
        d.save(path);q=Document.load(path)
        assert q.room_metadata(sig)['name']=='Kitchen' and q.room_metadata(sig)['notes']=='Island'
    finally:
        os.remove(path)


def test_room_metadata_remains_dormant_and_returns_when_boundary_restored():
    d=Document();walls=rectangle(d);sig=room_faces(d)[0].signature;d.set_room_metadata(sig,name='Studio')
    original=walls[-1].params.copy();d.update(walls[-1].id,{'x2':1,'y2':1})
    assert room_faces(d)==[] and d.room_metadata(sig)['name']=='Studio'
    d.update(walls[-1].id,original)
    assert room_faces(d)[0].signature==sig and d.room_metadata(sig)['name']=='Studio'


def test_plan_frame_uses_room_name_use_and_area_label():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature;d.set_room_metadata(sig,name='Kitchen',use='Cooking')
    frame=build_plan_frame(d);labels=[p for p in frame.primitives if p.role=='derived-room-label']
    assert len(labels)==1
    text=dict(labels[0].meta)['text']
    # Owner 17/10: net area between the wall faces (walls 15 cm): 3.85 × 2.85, not 12.00 on the axes.
    assert 'Kitchen' in text and 'Cooking' in text and '10.97 m²' in text
    regions=[p for p in frame.primitives if p.role=='derived-room']
    assert dict(regions[0].meta)['signature']==sig


def test_room_metadata_rejects_unknown_fields():
    d=Document();rectangle(d);sig=room_faces(d)[0].signature
    try:
        d.set_room_metadata(sig,secret_geometry='bad')
        assert False
    except ValueError:
        pass


def test_room_name_and_use_is_one_undo_step():
    from archforge.core.commands import CommandStack, SetRoomMetadata
    d=Document();rectangle(d);sig=room_faces(d)[0].signature;st=CommandStack(d)
    st.execute(SetRoomMetadata(sig,{'name':'Σαλόνι','use':'Σαλόνι'}))
    labels=[p for p in build_plan_frame(d).primitives if p.role=='derived-room-label']
    assert dict(labels[0].meta)['text'].startswith('Σαλόνι\n')                 # use = name: written once
    st.execute(SetRoomMetadata(sig,{'name':'Μπάνιο','use':'Μπάνιο'}))
    st.undo()
    assert d.room_metadata(sig)['name']=='Σαλόνι'
    st.undo()
    assert d.room_metadata(sig)=={}
    st.redo()
    assert d.room_metadata(sig)['name']=='Σαλόνι'


def test_mouse_menu_sets_the_room_use_with_one_undo():
    """Owner 17/10: rooms named by use (Σαλόνι, Κουζίνα, Υπνοδωμάτιο, Μπάνιο …) from right click on the room."""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.marking_menu import ROOM_USES, all_ids, build_menu, run
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w._no_modal_dialogs = True
    try:
        for e in rectangle(w.doc):
            pass
        sig = room_faces(w.doc)[0].signature
        ids = all_ids(build_menu(w, 'plan', xy=(2.0, 1.5))['entries'])
        bath = ROOM_USES.index('Μπάνιο')
        assert f'mm:roomuse:{bath}' in ids and 'mm:roomuse:name' in ids
        run(w, 'plan', None, f'mm:roomuse:{bath}', (2.0, 1.5))
        assert w.doc.room_metadata(sig)['name'] == 'Μπάνιο'
        from archforge.assistant.understanding import _use_from_text
        assert _use_from_text(w.doc.room_metadata(sig)['use']) == 'bathroom'      # wet room: moisture boards etc.
        w.stack.undo()
        assert 'name' not in w.doc.room_metadata(sig)
    finally:
        w._mark_clean(); w.close(); app.processEvents()
