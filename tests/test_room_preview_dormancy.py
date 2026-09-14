from archforge.architecture.intent import infer_architecture
from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.preview import PreviewBackend


def _closed_room():
    doc=Document();walls=[]
    for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4)),((0,4),(0,0))]:
        w=Entity('wall',{'x1':a[0],'y1':a[1],'x2':b[0],'y2':b[1],'z':0,'height':2.8,'thickness':.2})
        doc.add(w);walls.append(w)
    infer_architecture(doc)
    return doc,walls


def test_temporarily_unclosed_room_slabs_do_not_make_preview_evaluation_fail():
    doc,walls=_closed_room()
    assert PreviewBackend().evaluate(doc).ok
    assert TessellatedPreviewBackend().evaluate(doc).ok

    doc.remove(walls[0].id)
    assert doc.active_room_faces()==[]

    fast=PreviewBackend().evaluate(doc)
    tess=TessellatedPreviewBackend().evaluate(doc)

    assert fast.ok
    assert tess.ok
    derived={e.id for e in doc.entities.values() if e.kind.startswith('room_')}
    assert derived
    assert not derived & {b.entity_id for b in fast.bodies}
    assert not derived & {b.entity_id for b in tess.bodies}
    assert all(i.severity!='error' for i in fast.issues if i.entity_id in derived)
