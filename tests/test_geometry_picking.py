from archforge.core.model import Document, Entity
from archforge.geometry.mesh import TessellatedPreviewBackend
from archforge.geometry.picking import raycast_evaluation, raycast_mesh


def test_wall_pick_resolves_to_semantic_exterior_surface():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});d.add(w)
    evaluation=TessellatedPreviewBackend().evaluate(d)
    hit=raycast_evaluation(d,evaluation,(2,-2,1.5),(0,1,0))
    assert hit is not None
    assert hit.owner_id==w.id
    assert hit.surface_role in ('exterior','interior')
    assert hit.uv is None


def test_nearest_surface_wins_across_multiple_entities():
    d=Document()
    a=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});d.add(a)
    b=Entity('box',{'x':0,'y':3,'z':0,'width':1,'depth':1,'height':1,'rotation':0});d.add(b)
    hit=raycast_evaluation(d,TessellatedPreviewBackend().evaluate(d),(0.5,-2,.5),(0,1,0))
    assert hit is not None and hit.owner_id==a.id
    assert hit.surface_role=='front'


def test_non_deformable_wall_bottom_is_not_returned_as_sculpt_target():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':2,'y2':0,'z':0,'height':2,'thickness':.2});d.add(w)
    hit=raycast_evaluation(d,TessellatedPreviewBackend().evaluate(d),(1,0,-2),(0,0,1))
    assert hit is None


def test_raw_raycast_keeps_triangle_only_transiently():
    d=Document();e=Entity('box',{'x':0,'y':0,'z':0,'width':2,'depth':2,'height':2,'rotation':0});d.add(e)
    body=TessellatedPreviewBackend().evaluate(d).body(e.id)
    raw=raycast_mesh(e.id,body.payload,(1,1,5),(0,0,-1))
    assert raw is not None
    assert raw.surface_role=='top'
    assert isinstance(raw.triangle_index,int)
