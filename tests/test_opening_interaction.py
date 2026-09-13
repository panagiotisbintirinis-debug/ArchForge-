from archforge.core.model import Document,Entity
from archforge.core.commands import CommandStack
from archforge.core.interaction import OpeningPlaceTransaction
from archforge.core.viewport import PointerController,PointerEvent
from archforge.architecture.openings import project_to_wall,nearest_wall_projection

def wall(doc):
    w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':.2});doc.add(w);return w

def test_project_to_wall():
    off,x,y,d=project_to_wall({'x1':0,'y1':0,'x2':5,'y2':0},2,.2);assert(off,x,y)==(2.,2.,0.) and abs(d-.2)<1e-12

def test_nearest_wall_projection_respects_tolerance():
    d=Document();w=wall(d);assert nearest_wall_projection(d,2,.1,.2)['wall_id']==w.id;assert nearest_wall_projection(d,2,1,.2) is None

def test_window_place_transaction_preview_and_commit():
    d=Document();w=wall(d);s=CommandStack(d);tx=OpeningPlaceTransaction(d,s,'window',2,.1);assert tx.host_id==w.id and tx.preview['offset']==2.;assert tx.preview_segment()==((1.4,0.),(2.6,0.));oid=tx.commit();assert d.get(oid).kind=='window' and d.get(oid).parent_id==w.id

def test_pointer_controller_door_drag_commits_attached_door():
    d=Document();w=wall(d);s=CommandStack(d);c=PointerController(d,s);c.set_tool('door');p=c.pointer_down(PointerEvent(2,.1));assert p.kind=='opening' and p.hud['valid']==1.;c.pointer_move(PointerEvent(3,.05));r=c.pointer_up(PointerEvent(3,.05));assert r.entity_id in d.entities and d.get(r.entity_id).parent_id==w.id and d.get(r.entity_id).kind=='door'
