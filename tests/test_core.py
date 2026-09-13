import os,tempfile,math
from archforge.core.model import Document,Entity,WorkPlane
from archforge.core.commands import CommandStack,AddEntity,UpdateEntity,MoveEntities
from archforge.core.snapping import points_for,best_snap
from archforge.core.interaction import WallDrawTransaction,BoxStretchTransaction
from archforge.organic.biospectre import profile_radius,junction_plane,overlap

def box(x=0,y=0): return Entity('box',{'x':x,'y':y,'z':0,'width':4,'depth':2,'height':3,'rotation':0})
def wall(): return Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':2.7,'thickness':.15})
def pod(cx=0): return Entity('pod',{'cx':cx,'cy':0,'floor_level':1,'diameter_x':4,'diameter_y':4,'height':2,'shell_thickness':.1})

def test_add_and_validate():
    d=Document();e=box();d.add(e);assert d.get(e.id).params['width']==4

def test_negative_dimension_rejected():
    d=Document();e=box();e.params['width']=-1
    try:d.add(e);assert False
    except ValueError:pass

def test_dependency_dirty_propagates():
    d=Document();a=box();b=box(5);d.add(a);d.add(b);d.dirty.clear();d.add_dependency(a.id,b.id);d.update(a.id,{'width':5});assert {a.id,b.id}<=d.dirty

def test_dependency_cycle_rejected():
    d=Document();a=box();b=box(5);d.add(a);d.add(b);d.add_dependency(a.id,b.id)
    try:d.add_dependency(b.id,a.id);assert False
    except ValueError:pass

def test_commands_undo_redo():
    d=Document();s=CommandStack(d);e=box();s.execute(AddEntity(e));s.execute(UpdateEntity(e.id,{'width':8}));assert d.get(e.id).params['width']==8;s.undo();assert d.get(e.id).params['width']==4;s.redo();assert d.get(e.id).params['width']==8

def test_multi_move_one_command():
    d=Document();a=box();b=box(5);d.add(a);d.add(b);s=CommandStack(d);s.execute(MoveEntities([a.id,b.id],2,3));assert d.get(a.id).params['x']==2 and d.get(b.id).params['x']==7;s.undo();assert d.get(a.id).params['x']==0 and d.get(b.id).params['x']==5

def test_snap_wall_endpoint_midpoint():
    d=Document();e=wall();d.add(e);ks={p.kind for p in points_for(d,e.id)};assert 'endpoint' in ks and 'midpoint' in ks

def test_snap_prefers_object_over_grid():
    d=Document();e=wall();d.add(e);sp=best_snap(d,4.04,.02,.1,1.0);assert sp.kind=='endpoint'

def test_snap_exclusion():
    d=Document();e=wall();d.add(e);assert best_snap(d,4,.0,.1,1.0,{e.id}) is None or best_snap(d,4,.0,.1,1.0,{e.id}).kind=='grid'

def test_workplane_roundtrip():
    w=WorkPlane(origin=(1,2,3));p=w.unproject(4,5);assert p==(5,7,3) and w.project(p)==(4,5)

def test_persistence_roundtrip():
    d=Document();e=box();d.add(e);fd,path=tempfile.mkstemp(suffix='.archforge');os.close(fd);d.save(path);q=Document.load(path);os.remove(path);assert q.to_dict()==d.to_dict()

def test_wall_live_transaction_exact_commit():
    d=Document();s=CommandStack(d);tx=WallDrawTransaction(d,s,(0,0),grid=None);hud=tx.update(3,4);assert abs(hud.values['length']-5)<1e-9;eid=tx.commit(exact_length=10);p=d.get(eid).params;assert abs(math.hypot(p['x2'],p['y2'])-10)<1e-9

def test_wall_transaction_cancel():
    d=Document();s=CommandStack(d);tx=WallDrawTransaction(d,s,(0,0));tx.update(2,0);tx.cancel();assert len(d.entities)==0

def test_box_stretch_preserves_opposite_edge():
    d=Document();e=box();d.add(e);s=CommandStack(d);left0=e.params['x']-e.params['width']/2;tx=BoxStretchTransaction(d,s,e.id,'right');hud=tx.update(x=5);tx.commit();p=d.get(e.id).params;assert abs((p['x']-p['width']/2)-left0)<1e-9 and p['x']+p['width']/2==5

def test_box_stretch_undo():
    d=Document();e=box();d.add(e);s=CommandStack(d);tx=BoxStretchTransaction(d,s,e.id,'right');tx.update(x=5);tx.commit();s.undo();assert d.get(e.id).params['width']==4

def test_pod_hard_floor():
    p=pod().params;assert profile_radius(p,.999) is None and profile_radius(p,1)==(2,2)

def test_pod_top_radius_zero():
    p=pod().params;r=profile_radius(p,3);assert r==(0.0,0.0)

def test_pod_overlap_and_junction():
    a=pod(0).params;b=pod(2).params;assert overlap(a,b);j=junction_plane(a,b);assert j and j['normal'][0]>0

def test_selection():
    d=Document();a=box();b=box();d.add(a);d.add(b);d.select([a.id]);d.select([b.id],add=True);assert d.selection==[a.id,b.id]

def test_locked_update_rejected():
    d=Document();e=box();e.locked=True;d.add(e)
    try:d.update(e.id,{'width':5});assert False
    except PermissionError:pass

def test_wall_endpoint_stretch_and_snap():
    from archforge.core.interaction import WallEndpointStretchTransaction
    d=Document();target=wall();target.params.update({'x1':8,'x2':10});d.add(target);e=wall();d.add(e);s=CommandStack(d)
    tx=WallEndpointStretchTransaction(d,s,e.id,2,grid=None,snap_tol=.2);hud=tx.update(8.05,.03);tx.commit();p=d.get(e.id).params
    assert p['x1']==0 and p['y1']==0 and p['x2']==8 and p['y2']==0 and abs(hud.values['length']-8)<1e-9

def test_pod_stretch_preserves_opposite_quadrant():
    from archforge.core.interaction import PodStretchTransaction
    d=Document();e=pod();d.add(e);s=CommandStack(d);left=e.params['cx']-e.params['diameter_x']/2
    tx=PodStretchTransaction(d,s,e.id,'right');tx.update(x=5);tx.commit();p=d.get(e.id).params
    assert abs((p['cx']-p['diameter_x']/2)-left)<1e-9 and abs((p['cx']+p['diameter_x']/2)-5)<1e-9

def test_pod_height_stretch():
    from archforge.core.interaction import PodStretchTransaction
    d=Document();e=pod();d.add(e);s=CommandStack(d);tx=PodStretchTransaction(d,s,e.id,'height');tx.update(z=5);tx.commit();assert d.get(e.id).params['height']==4

def test_rotate_box_angle_snap_and_undo():
    from archforge.core.interaction import RotateTransaction
    d=Document();e=box();d.add(e);s=CommandStack(d);tx=RotateTransaction(d,s,e.id,angle_increment=15);hud=tx.update_angle(22,snap=True);tx.commit()
    assert hud.values['angle_deg']==15 and d.get(e.id).params['rotation']==15;s.undo();assert d.get(e.id).params['rotation']==0

def test_rotate_wall_preserves_length():
    from archforge.core.interaction import RotateTransaction
    d=Document();e=wall();d.add(e);s=CommandStack(d);tx=RotateTransaction(d,s,e.id,angle_increment=None);tx.update_angle(90,False);tx.commit();p=d.get(e.id).params
    assert abs(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])-4)<1e-9 and abs(p['x1']-2)<1e-9

def test_workplane_delta_and_normal():
    w=WorkPlane(origin=(0,0,3),u=(1,0,0),v=(0,0,1));assert w.world_delta(2,4)==(2,0,4) and w.normal()==(0,-1,0)

def test_end_to_end_draw_stretch_numeric_rotate_save_reload():
    from archforge.core.interaction import WallEndpointStretchTransaction,RotateTransaction
    d=Document();s=CommandStack(d);tx=WallDrawTransaction(d,s,(0,0),grid=None);tx.update(4,0);eid=tx.commit()
    st=WallEndpointStretchTransaction(d,s,eid,2,grid=None);st.update(6,0);st.commit();s.execute(UpdateEntity(eid,{'height':3.2}))
    rt=RotateTransaction(d,s,eid,angle_increment=15);rt.update_angle(30);rt.commit();s.undo();s.redo()
    fd,path=tempfile.mkstemp(suffix='.archforge');os.close(fd);d.save(path);q=Document.load(path);os.remove(path)
    assert q.to_dict()==d.to_dict() and abs(math.hypot(q.get(eid).params['x2']-q.get(eid).params['x1'],q.get(eid).params['y2']-q.get(eid).params['y1'])-6)<1e-9 and q.get(eid).params['height']==3.2

def test_incremental_viewport_adapter_updates_and_removes_only_dirty():
    from archforge.core.viewport import IncrementalViewportAdapter
    d=Document();a=box();b=box(5);d.add(a);d.add(b);ad=IncrementalViewportAdapter(d)
    first=ad.consume();assert {r[0] for r in first['updates']}=={a.id,b.id} and not first['removals']
    d.update(a.id,{'width':5});second=ad.consume();assert [r[0] for r in second['updates']]==[a.id]
    d.remove(b.id);third=ad.consume();assert b.id in third['removals']


def test_pointer_controller_wall_live_preview_and_commit():
    from archforge.core.viewport import PointerController,PointerEvent
    d=Document();s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('wall')
    p=c.pointer_down(PointerEvent(0,0));assert p.kind=='wall'
    p=c.pointer_move(PointerEvent(3,4));assert abs(p.hud['length']-5)<1e-9 and len(d.entities)==0
    p=c.pointer_up(PointerEvent(3,4),{'length':10});assert len(d.entities)==1 and p.entity_id in d.entities
    e=d.get(p.entity_id);assert abs(math.hypot(e.params['x2']-e.params['x1'],e.params['y2']-e.params['y1'])-10)<1e-9


def test_pointer_controller_cancel_does_not_mutate_document():
    from archforge.core.viewport import PointerController,PointerEvent
    d=Document();s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('wall');c.pointer_down(PointerEvent(0,0));c.pointer_move(PointerEvent(2,2));c.cancel();assert not d.entities


def test_pointer_controller_move_preview_is_non_destructive_and_one_undo_step():
    from archforge.core.viewport import PointerController,PointerEvent
    d=Document();e=box();d.add(e);d.select([e.id]);d.dirty.clear();s=CommandStack(d);c=PointerController(d,s);c.set_tool('move')
    c.pointer_down(PointerEvent(0,0));p=c.pointer_move(PointerEvent(2,3));assert d.get(e.id).params['x']==0 and p.geometry['entities'][e.id]['x']==2
    c.pointer_up(PointerEvent(2,3));assert d.get(e.id).params['x']==2 and d.get(e.id).params['y']==3
    s.undo();assert d.get(e.id).params['x']==0 and d.get(e.id).params['y']==0


def test_pointer_controller_wall_stretch_preview_and_commit():
    from archforge.core.viewport import PointerController,PointerEvent
    d=Document();e=wall();d.add(e);s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_target(e.id,'endpoint2');c.set_tool('stretch');c.set_target(e.id,'endpoint2')
    c.pointer_down(PointerEvent(4,0));p=c.pointer_move(PointerEvent(7,0));assert d.get(e.id).params['x2']==4 and p.geometry['x2']==7
    c.pointer_up(PointerEvent(7,0));assert d.get(e.id).params['x2']==7


def test_pointer_controller_rotation_preview_shift_disables_angle_snap():
    from archforge.core.viewport import PointerController,PointerEvent
    d=Document();e=box();d.add(e);s=CommandStack(d);c=PointerController(d,s);c.set_tool('rotate');c.set_target(e.id);c.pointer_down(PointerEvent(2,0))
    r=math.radians(22);p=c.pointer_move(PointerEvent(2*math.cos(r),2*math.sin(r)));assert p.hud['angle_deg']==15
    c.cancel();c.set_tool('rotate');c.set_target(e.id);c.pointer_down(PointerEvent(2,0));p=c.pointer_move(PointerEvent(2*math.cos(r),2*math.sin(r),shift=True));assert abs(p.hud['angle_deg']-22)<1e-9


def test_pointer_controller_respects_offset_workplane_for_wall_start():
    from archforge.core.viewport import PointerController,PointerEvent
    d=Document();d.work_plane=WorkPlane(origin=(10,20,3));s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('wall')
    c.pointer_down(PointerEvent(1,2));c.pointer_up(PointerEvent(5,2));e=next(iter(d.entities.values()));assert (e.params['x1'],e.params['y1'],e.params['z'])==(11,22,3)

def test_plan_scene_builds_semantic_primitives_and_handles():
    from archforge.core.plan_scene import build_plan_frame
    d=Document();w=wall();b=box(8,2);p=pod(12);d.add(w);d.add(b);d.add(p);d.select([w.id,b.id,p.id])
    f=build_plan_frame(d);kinds=[x.kind for x in f.primitives]
    assert kinds.count('line')==1 and kinds.count('polygon')==1 and kinds.count('ellipse')==1
    hs={(h.entity_id,h.handle) for h in f.handles};assert (w.id,'endpoint1') in hs and (b.id,'right') in hs and (p.id,'top') in hs


def test_plan_scene_preview_keeps_model_and_preview_separate():
    from archforge.core.viewport import PointerController,PointerEvent
    from archforge.core.plan_scene import build_plan_frame
    d=Document();s=CommandStack(d);c=PointerController(d,s);c.grid=None;c.set_tool('wall');c.pointer_down(PointerEvent(0,0));prev=c.pointer_move(PointerEvent(3,0));f=build_plan_frame(d,prev)
    assert len(d.entities)==0 and len(f.primitives)==1 and f.primitives[0].role=='preview' and abs(f.hud['length']-3)<1e-9


def test_locked_selection_has_no_stretch_handles():
    from archforge.core.plan_scene import build_plan_frame
    d=Document();e=box();e.locked=True;d.add(e);d.select([e.id]);assert not build_plan_frame(d).handles

def test_view_frame_box_projects_to_all_three_axes():
    from archforge.core.view_frame import build_view_frame
    d=Document();e=box();d.add(e)
    xy=build_view_frame(d,'XY').primitives[0];xz=build_view_frame(d,'XZ').primitives[0];yz=build_view_frame(d,'YZ').primitives[0]
    assert xy.kind=='polygon' and xz.kind=='polygon' and yz.kind=='polygon'
    assert min(z for _,z in xz.points)==e.params['z'] and max(z for _,z in xz.points)==e.params['z']+e.params['height']


def test_view_frame_wall_elevation_has_real_height():
    from archforge.core.view_frame import build_view_frame
    d=Document();e=wall();e.params['z']=2;e.params['height']=3.5;d.add(e)
    xz=build_view_frame(d,'XZ').primitives[0]
    zs=[p[1] for p in xz.points];assert min(zs)==2 and max(zs)==5.5


def test_view_frame_end_on_wall_remains_visible_in_elevation():
    from archforge.core.view_frame import build_view_frame
    d=Document();e=wall();e.params.update({'x1':2,'x2':2,'y1':0,'y2':4,'thickness':.2});d.add(e)
    xz=build_view_frame(d,'XZ').primitives[0];xs=[p[0] for p in xz.points]
    assert abs((max(xs)-min(xs))-.2)<1e-9


def test_view_frame_pod_is_hard_floor_upper_ellipse():
    from archforge.core.view_frame import build_view_frame
    d=Document();e=pod();d.add(e)
    xz=build_view_frame(d,'XZ').primitives[0]
    assert xz.kind=='upper_ellipse' and xz.points[0][1]==e.params['floor_level'] and xz.radius_b==e.params['height']


def test_view_frame_rejects_unknown_axis():
    from archforge.core.view_frame import build_view_frame
    d=Document()
    try:build_view_frame(d,'AB');assert False
    except ValueError:pass


def test_vertical_stretch_wall_preserves_base_and_undo():
    from archforge.core.interaction import VerticalStretchTransaction
    d=Document();e=wall();e.params['z']=1.25;d.add(e);s=CommandStack(d)
    tx=VerticalStretchTransaction(d,s,e.id);hud=tx.update(5.0);tx.commit()
    assert d.get(e.id).params['z']==1.25 and abs(d.get(e.id).params['height']-3.75)<1e-9
    assert hud.values['top_z']==5.0
    s.undo();assert d.get(e.id).params['height']==2.7


def test_vertical_stretch_pod_uses_floor_as_fixed_base():
    from archforge.core.interaction import VerticalStretchTransaction
    d=Document();e=pod();e.params['floor_level']=2.0;e.params['height']=3.0;d.add(e);s=CommandStack(d)
    tx=VerticalStretchTransaction(d,s,e.id);tx.update(7.5);tx.commit()
    p=d.get(e.id).params;assert p['floor_level']==2.0 and p['height']==5.5


def test_vertical_stretch_rejects_crossing_base_without_mutation():
    from archforge.core.interaction import VerticalStretchTransaction
    d=Document();e=box();e.params['z']=3.0;d.add(e);s=CommandStack(d);tx=VerticalStretchTransaction(d,s,e.id)
    try:tx.update(2.0);assert False
    except ValueError:pass
    assert d.get(e.id).params['height']==3.0


def test_elevation_top_handle_matches_semantic_top():
    from archforge.core.view_frame import elevation_top_handle
    d=Document();e=pod();e.params['floor_level']=1.5;e.params['height']=4.25;d.add(e)
    hx=elevation_top_handle(d,e.id,'XZ');hy=elevation_top_handle(d,e.id,'YZ')
    assert hx==(e.params['cx'],5.75) and hy==(e.params['cy'],5.75)


def test_view_frame_override_renders_preview_without_model_mutation():
    from archforge.core.view_frame import build_view_frame
    d=Document();e=box();d.add(e);override=dict(e.params);override['height']=9.0
    f=build_view_frame(d,'XZ',{e.id:override});zs=[p[1] for p in f.primitives[0].points]
    assert max(zs)==e.params['z']+9.0 and d.get(e.id).params['height']==3.0

def test_floor_polygon_validation_metrics_and_persistence():
    from archforge.architecture.floors import area,perimeter,centroid
    d=Document();e=Entity('floor',{'points':[(0,0),(4,0),(4,3),(0,3)],'z':1.2,'thickness':.25});d.add(e)
    p=d.get(e.id).params
    assert area(p['points'])==12 and perimeter(p['points'])==14 and centroid(p['points'])==(2,1.5)
    fd,path=tempfile.mkstemp(suffix='.archforge');os.close(fd);d.save(path);q=Document.load(path);os.remove(path);assert q.to_dict()==d.to_dict()


def test_floor_degenerate_polygon_rejected():
    d=Document();e=Entity('floor',{'points':[(0,0),(1,0),(2,0)],'z':0,'thickness':.2})
    try:d.add(e);assert False
    except ValueError:pass


def test_floor_move_and_undo_is_semantic():
    d=Document();e=Entity('floor',{'points':[(0,0),(2,0),(2,2),(0,2)],'z':0,'thickness':.2});d.add(e);s=CommandStack(d)
    s.execute(MoveEntities([e.id],3,4,1));assert d.get(e.id).params['points'][0]==(3.0,4.0) and d.get(e.id).params['z']==1
    s.undo();assert d.get(e.id).params['points'][0]==(0.0,0.0) and d.get(e.id).params['z']==0


def test_floor_snap_vertices_and_midpoints():
    d=Document();e=Entity('floor',{'points':[(0,0),(4,0),(4,2),(0,2)],'z':0,'thickness':.2});d.add(e)
    pts=points_for(d,e.id);assert len([p for p in pts if p.kind=='vertex'])==4 and len([p for p in pts if p.kind=='midpoint'])==4
    assert best_snap(d,2.03,.02,.1,None).kind=='midpoint'


def test_floor_projects_plan_and_elevations():
    from archforge.core.view_frame import build_view_frame
    d=Document();e=Entity('floor',{'points':[(0,0),(5,0),(5,2),(0,2)],'z':3,'thickness':.3});d.add(e)
    xy=build_view_frame(d,'XY').primitives[0];xz=build_view_frame(d,'XZ').primitives[0];yz=build_view_frame(d,'YZ').primitives[0]
    assert xy.kind=='polygon' and len(xy.points)==4
    assert min(z for _,z in xz.points)==3 and max(z for _,z in xz.points)==3.3
    assert min(z for _,z in yz.points)==3 and max(z for _,z in yz.points)==3.3


def test_room_semantic_volume_basis_and_view():
    from archforge.architecture.floors import area
    from archforge.core.view_frame import build_view_frame
    d=Document();e=Entity('room',{'points':[(0,0),(3,0),(3,4),(0,4)],'z':0,'height':2.8});d.add(e)
    assert math.isclose(area(d.get(e.id).params['points'])*d.get(e.id).params['height'],33.6,rel_tol=0,abs_tol=1e-12)
    assert build_view_frame(d,'XZ').primitives[0].points[-1][1]==2.8
