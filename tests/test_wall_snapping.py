from archforge.core.model import Document, Entity
from archforge.core.snapping import best_snap
from archforge.core.commands import CommandStack
from archforge.core.interaction import WallDrawTransaction


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
