from archforge.core.model import Document, Entity
from archforge.architecture.topology import build_wall_graph, closed_room_polygons, connected_components, polygon_area, room_metrics


def wall(x1,y1,x2,y2,z=0.0):
    return Entity('wall',{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'z':z,'height':2.7,'thickness':0.15})


def rectangle(doc,x0=0,y0=0,w=4,h=3,z=0):
    for a,b in [((x0,y0),(x0+w,y0)),((x0+w,y0),(x0+w,y0+h)),((x0+w,y0+h),(x0,y0+h)),((x0,y0+h),(x0,y0))]:
        doc.add(wall(*a,*b,z=z))


def test_wall_graph_merges_shared_endpoints():
    d=Document();d.add(wall(0,0,4,0));d.add(wall(4,0,4,3));g=build_wall_graph(d)
    assert len(g.nodes)==3 and len(g.edges)==2


def test_wall_graph_tolerance_merges_near_endpoint():
    d=Document();d.add(wall(0,0,4,0));d.add(wall(4.00001,0,4,3));g=build_wall_graph(d,tolerance=1e-3)
    assert len(g.nodes)==3


def test_connected_components_separates_wall_groups():
    d=Document();d.add(wall(0,0,1,0));d.add(wall(10,0,11,0));g=build_wall_graph(d)
    comps=connected_components(g);assert len(comps)==2


def test_open_chain_has_no_room():
    d=Document();d.add(wall(0,0,4,0));d.add(wall(4,0,4,3));d.add(wall(4,3,0,3))
    assert closed_room_polygons(d)==[]


def test_rectangle_detects_one_room_with_correct_area():
    d=Document();rectangle(d,0,0,4,3);rooms=closed_room_polygons(d)
    assert len(rooms)==1 and abs(polygon_area(rooms[0])-12)<1e-9


def test_room_metrics_rectangle():
    m=room_metrics([(0,0),(4,0),(4,3),(0,3)])
    assert abs(m['area']-12)<1e-9 and abs(m['perimeter']-14)<1e-9 and m['centroid']==(2.0,1.5)


def test_two_rooms_with_shared_wall_are_detected_independently():
    d=Document();
    for a,b in [((0,0),(4,0)),((4,0),(8,0)),((8,0),(8,3)),((8,3),(4,3)),((4,3),(0,3)),((0,3),(0,0)),((4,0),(4,3))]:
        d.add(wall(*a,*b))
    rooms=closed_room_polygons(d);areas=sorted(round(polygon_area(p),6) for p in rooms)
    assert areas==[12.0,12.0]


def test_z_filter_keeps_levels_independent():
    d=Document();rectangle(d,0,0,4,3,z=0);rectangle(d,10,0,2,2,z=3)
    assert len(closed_room_polygons(d,z=0))==1
    assert len(closed_room_polygons(d,z=3))==1


def test_hidden_wall_does_not_close_room():
    d=Document();rectangle(d)
    last=list(d.entities.values())[-1];last.visible=False
    assert closed_room_polygons(d)==[]


def test_plan_frame_contains_non_selectable_derived_room():
    from archforge.core.plan_scene import build_plan_frame
    d=Document();rectangle(d)
    frame=build_plan_frame(d)
    derived=[p for p in frame.primitives if p.role=='derived-room']
    assert len(derived)==1 and derived[0].entity_id==''
    meta=dict(derived[0].meta)
    assert abs(meta['area']-12)<1e-9 and abs(meta['perimeter']-14)<1e-9


def test_derived_room_disappears_when_boundary_is_broken():
    from archforge.core.plan_scene import build_plan_frame
    d=Document();rectangle(d)
    assert any(p.role=='derived-room' for p in build_plan_frame(d).primitives)
    eid=list(d.entities)[-1]
    d.update(eid,{'x2':1.0,'y2':0.5})
    assert not any(p.role=='derived-room' for p in build_plan_frame(d).primitives)
