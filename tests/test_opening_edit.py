import copy
import math
import pytest

from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack
from archforge.core.interaction import OpeningEditTransaction
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.plan_scene import build_plan_frame


def make_wall(length=6.0):
    return Entity('wall',{'x1':0.0,'y1':0.0,'x2':length,'y2':0.0,'z':0.0,'height':3.0,'thickness':0.15},name='Wall')


def add_door(doc, wall, offset=3.0, width=1.0):
    door=Entity('door',{'offset':offset,'width':width,'height':2.1,'sill':0.0},name='Door',parent_id=wall.id)
    doc.add(door)
    return door


def test_opening_move_projects_to_host_wall_and_undoes():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w);s=CommandStack(d)
    tx=OpeningEditTransaction(d,s,door.id,'move')
    hud=tx.update(4.0,1.5)
    assert d.get(door.id).params['offset']==3.0
    assert math.isclose(tx.preview['offset'],4.0)
    assert math.isclose(hud.values['distance'],1.5)
    tx.commit();assert math.isclose(d.get(door.id).params['offset'],4.0)
    s.undo();assert math.isclose(d.get(door.id).params['offset'],3.0)


def test_opening_left_jamb_stretch_preserves_right_jamb():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w,offset=3.0,width=1.0);s=CommandStack(d)
    old_right=door.params['offset']+door.params['width']/2
    tx=OpeningEditTransaction(d,s,door.id,'left');tx.update(2.0,0.3)
    assert math.isclose(tx.preview['offset']+tx.preview['width']/2,old_right)
    assert math.isclose(tx.preview['width'],1.5)
    tx.commit();assert math.isclose(d.get(door.id).params['width'],1.5)


def test_opening_jamb_cannot_cross_opposite_jamb():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w);s=CommandStack(d)
    tx=OpeningEditTransaction(d,s,door.id,'left')
    with pytest.raises(ValueError):tx.update(3.6,0.0)
    assert d.get(door.id).params['width']==1.0


def test_selected_opening_has_two_jamb_handles_and_move_handle():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w);d.select([door.id])
    handles={(h.handle,round(h.x,3),round(h.y,3)) for h in build_plan_frame(d).handles}
    assert ('left',2.5,0.0) in handles
    assert ('right',3.5,0.0) in handles
    assert ('move',3.0,0.0) in handles


def test_pointer_move_opening_is_preview_then_single_commit():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w);d.select([door.id]);s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('move')
    p=c.pointer_down(PointerEvent(3.0,0.0));assert p.kind=='opening-edit'
    p=c.pointer_move(PointerEvent(4.0,1.0));assert math.isclose(d.get(door.id).params['offset'],3.0)
    assert math.isclose(p.geometry['params']['offset'],4.0)
    c.pointer_up(PointerEvent(4.0,1.0));assert math.isclose(d.get(door.id).params['offset'],4.0)
    s.undo();assert math.isclose(d.get(door.id).params['offset'],3.0)


def test_pointer_stretch_opening_jamb_is_non_destructive_until_release():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w);s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('stretch');c.set_target(door.id,'right')
    c.pointer_down(PointerEvent(3.5,0.0));p=c.pointer_move(PointerEvent(4.0,0.2))
    assert math.isclose(d.get(door.id).params['width'],1.0)
    assert math.isclose(p.geometry['params']['width'],1.5)
    c.pointer_up(PointerEvent(4.0,0.2));assert math.isclose(d.get(door.id).params['width'],1.5)


def test_reordered_persistence_loads_opening_after_host():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w)
    raw=d.to_dict();entities=copy.deepcopy(raw['entities']);raw['entities']=[next(e for e in entities if e['kind']=='door'),next(e for e in entities if e['kind']=='wall')]
    q=Document.from_dict(raw)
    assert q.get(door.id).parent_id==w.id
    assert door.id in q.children[w.id]
    assert door.id in q.dependencies[w.id]


def test_wall_edit_still_rejects_orphaning_existing_opening():
    d=Document();w=make_wall();d.add(w);door=add_door(d,w,offset=5.0,width=1.0)
    with pytest.raises(ValueError):d.update(w.id,{'x2':5.0})
    assert math.isclose(d.get(w.id).params['x2'],6.0)
