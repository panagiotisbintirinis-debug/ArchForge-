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
    assert tx.end==(3.05,0.0)
    eid=tx.commit();p=d.get(eid).params
    assert abs(p['y2'])<1e-9 and abs(p['x2']-3.05)<1e-9


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
    with pytest.raises(ValueError, match='too short'):
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
