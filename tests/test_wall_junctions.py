from archforge.core.model import Document, Entity
from archforge.core.commands import CommandStack, UpdateEntities
from archforge.core.wall_junction import ConnectedWallEndpointStretchTransaction
from archforge.core.viewport import PointerController, PointerEvent
from archforge.core.plan_scene import build_plan_frame


def wall(x1,y1,x2,y2):
    return Entity('wall',{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'z':0.0,'height':2.7,'thickness':0.15})


def test_update_entities_is_one_undo_step():
    d=Document();a=wall(0,0,4,0);b=wall(4,0,4,3);d.add(a);d.add(b);s=CommandStack(d)
    s.execute(UpdateEntities({a.id:{'x2':5,'y2':1},b.id:{'x1':5,'y1':1}}))
    assert (d.get(a.id).params['x2'],d.get(b.id).params['x1'])==(5,5)
    assert len(s.done)==1
    s.undo()
    assert (d.get(a.id).params['x2'],d.get(a.id).params['y2'])==(4,0)
    assert (d.get(b.id).params['x1'],d.get(b.id).params['y1'])==(4,0)


def test_connected_junction_preview_is_non_destructive():
    d=Document();a=wall(0,0,4,0);b=wall(4,0,4,3);d.add(a);d.add(b);s=CommandStack(d)
    tx=ConnectedWallEndpointStretchTransaction(d,s,a.id,2,grid=None)
    hud=tx.update(5,1)
    assert d.get(a.id).params['x2']==4 and d.get(b.id).params['x1']==4
    assert tx.previews[a.id]['x2']==5 and tx.previews[b.id]['x1']==5
    assert hud.values['joined_walls']==2.0


def test_connected_junction_commit_moves_all_joined_wall_ends():
    d=Document();a=wall(0,0,4,0);b=wall(4,0,4,3);c=wall(4,0,7,-2);d.add(a);d.add(b);d.add(c);s=CommandStack(d)
    tx=ConnectedWallEndpointStretchTransaction(d,s,a.id,2,grid=None);tx.update(5,1);tx.commit()
    assert (d.get(a.id).params['x2'],d.get(a.id).params['y2'])==(5,1)
    assert (d.get(b.id).params['x1'],d.get(b.id).params['y1'])==(5,1)
    assert (d.get(c.id).params['x1'],d.get(c.id).params['y1'])==(5,1)
    s.undo()
    assert (d.get(a.id).params['x2'],d.get(b.id).params['x1'],d.get(c.id).params['x1'])==(4,4,4)


def test_unconnected_nearby_endpoint_is_not_moved():
    d=Document();a=wall(0,0,4,0);b=wall(4.01,0,4.01,3);d.add(a);d.add(b);s=CommandStack(d)
    tx=ConnectedWallEndpointStretchTransaction(d,s,a.id,2,grid=None,join_tol=1e-4);tx.update(5,1);tx.commit()
    assert d.get(b.id).params['x1']==4.01


def test_pointer_controller_uses_connected_junction_edit():
    d=Document();a=wall(0,0,4,0);b=wall(4,0,4,3);d.add(a);d.add(b);d.select([a.id]);s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('stretch');c.set_target(a.id,'endpoint2')
    c.pointer_down(PointerEvent(4,0));preview=c.pointer_move(PointerEvent(5,1))
    assert 'entities' in preview.geometry and len(preview.geometry['entities'])==2
    assert d.get(b.id).params['x1']==4
    c.pointer_up(PointerEvent(5,1))
    assert d.get(b.id).params['x1']==5 and d.get(b.id).params['y1']==1


def test_plan_preview_draws_all_connected_walls():
    d=Document();a=wall(0,0,4,0);b=wall(4,0,4,3);d.add(a);d.add(b);d.select([a.id]);s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('stretch');c.set_target(a.id,'endpoint2')
    c.pointer_down(PointerEvent(4,0));preview=c.pointer_move(PointerEvent(5,1));frame=build_plan_frame(d,preview)
    moved=[p for p in frame.primitives if p.role=='preview']
    assert len(moved)==2


def test_free_end_is_lengthened_along_its_own_line():
    # Owner 24/10: a short wall left at a corner, its free end dragged to make it longer, swung to −111°.
    d=Document();a=wall(0,0,4,0);stub=wall(4,0,4,-0.7);d.add(a);d.add(stub);s=CommandStack(d)
    tx=ConnectedWallEndpointStretchTransaction(d,s,stub.id,2,grid=0.1)
    hud=tx.update(4.25,-2.1)                         # the hand drifts 7° off the line
    assert tx.angle_snapped and abs(tx.preview['x2']-4)<1e-9 and abs(tx.preview['y2']+2.1)<1e-9
    assert abs(hud.values['angle_deg']+90)<1e-9
    tx.commit()
    assert (d.get(stub.id).params['x1'],d.get(stub.id).params['y1'])==(4,0)
    assert (d.get(a.id).params['x2'],d.get(a.id).params['y2'])==(4,0)


def test_free_end_turns_freely_with_shift_or_far_from_any_held_angle():
    d=Document();stub=wall(4,0,4,-0.7);d.add(stub);s=CommandStack(d)
    tx=ConnectedWallEndpointStretchTransaction(d,s,stub.id,2,grid=None)
    tx.angle_enabled=False;tx.update(4.25,-2.1)
    assert (tx.preview['x2'],tx.preview['y2'])==(4.25,-2.1)
    tx.angle_enabled=True;tx.update(3.2,-2.0)        # −111°: neither its own line nor 90°/45°
    assert not tx.angle_snapped and (tx.preview['x2'],tx.preview['y2'])==(3.2,-2.0)


def test_stretch_preview_shows_the_wall_body():
    from archforge.core.plan_scene import preview_primitives
    d=Document();stub=wall(4,0,4,-0.7);d.add(stub);d.select([stub.id]);s=CommandStack(d);c=PointerController(d,s);c.grid=None
    c.set_tool('stretch');c.set_target(stub.id,'endpoint2')
    c.pointer_down(PointerEvent(4,-0.7));pv=c.pointer_move(PointerEvent(4.1,-2))
    prims=preview_primitives(pv)
    assert [p.kind for p in prims]==['polygon'] and dict(prims[0].meta)['semantic']=='wall-body-preview'
    xs=[q[0] for q in prims[0].points];ys=[q[1] for q in prims[0].points]
    assert abs(max(xs)-min(xs)-0.15)<1e-9 and abs(min(ys)+2)<1e-9
