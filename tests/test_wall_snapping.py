import pytest
from archforge.core.model import Document, Entity
from archforge.core.snapping import best_snap
from archforge.core.commands import CommandStack
from archforge.core.interaction import WallDrawTransaction
from archforge.core.viewport import PointerController, PointerEvent


def wall(x1,y1,x2,y2):
    return Entity('wall',{'x1':x1,'y1':y1,'x2':x2,'y2':y2,'z':0.0,'height':2.7,'thickness':0.15})


def test_best_snap_projects_to_wall_interior():
    d=Document();w=wall(0,0,10,0);d.add(w)
    s=best_snap(d,3.2,0.08,0.15,grid=None)
    assert s is not None and s.kind=='wall' and s.entity_id==w.id
    assert abs(s.x-3.2)<1e-9 and abs(s.y)<1e-9


def test_explicit_wall_midpoint_beats_projection_snap():
    d=Document();w=wall(0,0,10,0);d.add(w)
    s=best_snap(d,5.03,0.02,0.15,grid=None)
    assert s is not None and s.kind=='midpoint'
    assert (s.x,s.y)==(5.0,0.0)


def test_projection_outside_tolerance_is_ignored():
    d=Document();d.add(wall(0,0,10,0))
    assert best_snap(d,3,0.3,0.1,grid=None) is None


def test_wall_draw_transaction_can_finish_as_t_junction():
    d=Document();host=wall(0,0,10,0);d.add(host);stack=CommandStack(d)
    tx=WallDrawTransaction(d,stack,(3,3),grid=None,snap_tol=0.2)
    hud=tx.update(3.05,0.08)
    # Reported: reaching the opposite wall tilted the new one off 90°. It stops on the wall axis, still at 90°.
    assert tx.end==pytest.approx((3.0,0.0)) and hud.values['angle_locked']==1.0
    eid=tx.commit();p=d.get(eid).params
    assert abs(p['y2'])<1e-9 and abs(p['x2']-3.0)<1e-9
    d2=Document();d2.add(wall(0,0,10,0))
    free=WallDrawTransaction(d2,CommandStack(d2),(3,3),grid=None,snap_tol=0.2,angle_enabled=False)
    free.update(3.05,0.08)
    assert free.end==pytest.approx((3.05,0.0))                      # Shift (no angle): free T-junction


def test_wall_end_near_a_corner_closes_onto_it_even_off_the_angle():
    d=Document();stack=CommandStack(d)
    for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4))]:
        d.add(wall(*a,*b))
    tx=WallDrawTransaction(d,stack,(0,4),grid=None,snap_tol=0.1)
    tx.update(0.18,0.2)                                               # 18–20 cm off the start corner
    assert tx.end==(0.0,0.0) and tx.last_snap.kind=='endpoint'


def test_far_from_corners_the_angle_holds_while_passing_other_walls():
    d=Document();stack=CommandStack(d);d.add(wall(0,0,10,0));d.add(wall(4,-2,4,6))
    tx=WallDrawTransaction(d,stack,(0,3),grid=None,snap_tol=0.15)
    tx.update(4.1,3.12)                                               # on the crossing wall, a little off
    assert tx.end==pytest.approx((4.0,3.0))                           # stops on its axis, still horizontal
    tx.update(7.0,3.1)
    assert tx.end[1]==pytest.approx(3.0)


def test_wall_projection_respects_exclusion():
    d=Document();host=wall(0,0,10,0);d.add(host)
    s=best_snap(d,3,0.05,0.1,grid=None,exclude={host.id})
    assert s is None



def test_construction_grid_is_soft_not_global_quantization():
    d=Document()
    # With a 10 cm construction step, a point 3 cm away from the nearest node
    # must remain free because grid capture is only 20% of the step.
    assert best_snap(d,0.03,0.00,0.10,grid=0.10) is None
    s=best_snap(d,0.011,0.008,0.10,grid=0.10)
    assert s is not None
    assert s.kind=='construction_grid'
    assert (s.x,s.y)==(0.0,0.0)


def test_wall_draw_relative_90_uses_host_wall_direction():
    d=Document()
    host=wall(0,0,4,4)
    d.add(host)
    stack=CommandStack(d)
    controller=PointerController(d,stack)
    controller.grid=None
    controller.set_tool('wall')
    controller.set_wall_angle_increment(90)
    controller.set_wall_angle_reference('relative')

    controller.pointer_down(PointerEvent(2.0,2.0))
    preview=controller.pointer_move(PointerEvent(2.0,5.0))

    # Host wall is 45°. Relative 90° therefore allows 45°/135°/... guides,
    # rather than forcing global horizontal/vertical.
    angle=preview.hud['angle_deg'] % 180.0
    assert abs(angle-135.0)<1e-6 or abs(angle-45.0)<1e-6


def test_wall_draw_global_90_ignores_host_wall_direction():
    d=Document()
    host=wall(0,0,4,4)
    d.add(host)
    stack=CommandStack(d)
    controller=PointerController(d,stack)
    controller.grid=None
    controller.set_tool('wall')
    controller.set_wall_angle_increment(90)
    controller.set_wall_angle_reference('global')

    controller.pointer_down(PointerEvent(2.0,2.0))
    preview=controller.pointer_move(PointerEvent(2.2,5.0))

    angle=preview.hud['angle_deg'] % 180.0
    assert abs(angle-90.0)<1e-6 or abs(angle)<1e-6


def test_geometry_endpoint_wins_over_angle_constraint():
    d=Document()
    host=wall(0,0,4,0)
    target=wall(3,2,3,4)
    d.add(host);d.add(target)
    stack=CommandStack(d)
    tx=WallDrawTransaction(
        d,stack,(0,0),grid=None,snap_tol=0.20,
        snap_enabled=True,angle_increment=90,reference_angle_deg=0,
    )
    tx.update(3.04,2.03)

    assert tx.last_snap is not None
    assert tx.last_snap.kind=='endpoint'
    assert tx.end==(3.0,2.0)


def test_wall_intersection_snap_beats_projection():
    d=Document()
    a=wall(-5,0,5,0)
    b=wall(0,-5,0,5)
    d.add(a);d.add(b)
    s=best_snap(d,0.04,0.03,0.15,grid=None)

    assert s is not None
    assert s.kind=='intersection'
    assert abs(s.x)<1e-9 and abs(s.y)<1e-9


def test_wall_draw_rejects_accidental_tiny_segment():
    d=Document()
    stack=CommandStack(d)
    tx=WallDrawTransaction(
        d,stack,(0.0,0.0),
        grid=None,
        snap_enabled=False,
        angle_enabled=False,
        min_length=0.05,
    )
    tx.update(0.024,0.0)

    import pytest
    with pytest.raises(ValueError, match='πολύ κοντός'):
        tx.commit()

    assert not d.entities


def test_wall_draw_accepts_normal_short_architectural_segment():
    d=Document()
    stack=CommandStack(d)
    tx=WallDrawTransaction(
        d,stack,(0.0,0.0),
        grid=None,
        snap_enabled=False,
        angle_enabled=False,
        min_length=0.05,
    )
    tx.update(0.08,0.0)

    eid=tx.commit()
    assert eid in d.entities
    p=d.get(eid).params
    assert abs(float(p['x2'])-0.08)<1e-9


def test_structural_column_center_and_beam_endpoints_are_snap_points():
    d=Document()
    column=Entity(
        'structural_column',
        {
            'x':2.0,'y':3.0,'z':0.0,'width':0.30,'depth':0.30,'height':2.70,
            'rotation':0.0,'role':'structural','construction':'reinforced_concrete',
            'section':'rectangular','base_level':'Ground','top_level':'Unassigned',
        },
    )
    beam=Entity(
        'structural_beam',
        {
            'x1':2.0,'y1':3.0,'x2':5.0,'y2':3.0,'z':2.40,
            'width':0.20,'height':0.30,'role':'structural','construction':'steel',
            'section':'rectangular','level':'Ground',
        },
    )
    d.add(column);d.add(beam)

    center=best_snap(d,2.02,3.01,0.10,grid=None)
    assert center is not None
    assert center.entity_id in {column.id,beam.id}
    assert center.kind in {'center','endpoint'}
    assert abs(center.x-2.0)<1e-9 and abs(center.y-3.0)<1e-9

    endpoint=best_snap(d,5.03,3.01,0.10,grid=None)
    assert endpoint is not None
    assert endpoint.entity_id==beam.id
    assert endpoint.kind=='endpoint'


def test_upper_storey_wall_snaps_to_the_corner_of_the_wall_below():
    from archforge.core.model import Document, Entity, WorkPlane
    from archforge.core.snapping import best_snap

    doc = Document()
    doc.levels['Floor 2'] = 2.7
    doc.add(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0,
                            'height': 2.7, 'thickness': 0.2}))
    doc.work_plane = WorkPlane(name='Floor 2', origin=(0.0, 0.0, 2.7))
    sp = best_snap(doc, 3.96, 0.04, 0.10, 0.10)
    assert (sp.x, sp.y, sp.z, sp.kind) == (4.0, 0.0, 2.7, 'underlay_endpoint')
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    assert best_snap(doc, 3.96, 0.04, 0.10, 0.10).kind == 'endpoint'


def test_magnets_pull_lightly_to_90_45_15_and_leave_other_angles_free():
    from archforge.core.interaction import MAGNET
    d=Document();stack=CommandStack(d)
    import math
    def end_angle(px,py):
        tx=WallDrawTransaction(d,stack,(0,0),grid=None,angle_increment=MAGNET)
        hud=tx.update(px,py);return hud.values['angle_deg'],hud.values['magnet']
    a,m=end_angle(math.cos(math.radians(87.5))*4,math.sin(math.radians(87.5))*4)
    assert a==pytest.approx(90.0) and m==90.0                           # 2.5° off: pulled to 90°
    a,m=end_angle(math.cos(math.radians(43.0))*4,math.sin(math.radians(43.0))*4)
    assert a==pytest.approx(45.0) and m==45.0
    a,m=end_angle(math.cos(math.radians(67.3))*4,math.sin(math.radians(67.3))*4)
    assert a==pytest.approx(67.0) and m==0.0                            # free, whole degrees
    a,m=end_angle(math.cos(math.radians(41.2))*4,math.sin(math.radians(41.2))*4)
    assert a==pytest.approx(41.0) and m==0.0


def test_corner_mark_tells_the_angle_to_the_previous_wall():
    from archforge.core.interaction import MAGNET
    from archforge.core.plan_scene import preview_primitives
    from archforge.core.viewport import PreviewState
    import math
    d=Document();stack=CommandStack(d);d.add(wall(0,0,5,0))
    tx=WallDrawTransaction(d,stack,(5,0),grid=None,angle_increment=MAGNET)
    hud=tx.update(5+3*math.cos(math.radians(113)),3*math.sin(math.radians(113)))
    assert hud.values['corner_deg']==pytest.approx(67.0)               # 180 − 113
    prims=preview_primitives(PreviewState('wall',{'x1':5,'y1':0,'x2':tx.end[0],'y2':tx.end[1],'z':0},hud.values))
    labels=[dict(p.meta)['text'] for p in prims if p.role=='angle-label']
    assert labels==['67°'] and any(p.role=='angle-arc' for p in prims)
    hud=tx.update(5,3.1)
    assert hud.values['corner_deg']==pytest.approx(90.0) and hud.values['magnet']==90.0


def test_magnet_is_the_default_wall_angle_mode():
    from archforge.core.viewport import PointerController
    d=Document();c=PointerController(d,CommandStack(d))
    assert c.wall_angle_increment=='magnet'
