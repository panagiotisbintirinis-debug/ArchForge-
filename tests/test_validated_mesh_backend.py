from archforge.core.model import Document,Entity
from archforge.geometry.validated_mesh import ValidatedMeshBackend
from archforge.geometry.fabrication import assess_fabrication
from archforge.geometry.selection import SurfaceHit,BrushSpec,sculpt_modifier_from_hit

def test_closed_box_can_be_proven_fabrication_mesh():
 d=Document();e=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});d.add(e)
 b=ValidatedMeshBackend().evaluate(d).body(e.id)
 assert b.watertight is True and b.manifold is True and b.quality=='fabrication_mesh'
 assert assess_fabrication(ValidatedMeshBackend().evaluate(d)).ready

def test_active_unapplied_modifier_blocks_promotion_even_if_base_is_closed():
 d=Document();e=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});d.add(e)
 m=sculpt_modifier_from_hit(d,SurfaceHit(e.id,'top',(.5,.5,1),(0,0,1)),BrushSpec(.4),'pull',.1);d.add_surface_modifier(m)
 ev=ValidatedMeshBackend().evaluate(d);b=ev.body(e.id)
 assert b.quality!='fabrication_mesh' and not assess_fabrication(ev).ready

def test_open_pod_is_never_promoted_to_fabrication_mesh():
 d=Document();e=Entity('pod',{'cx':0,'cy':0,'floor_level':0,'diameter_x':4,'diameter_y':4,'height':2,'shell_thickness':.1,'rotation':0});d.add(e)
 ev=ValidatedMeshBackend().evaluate(d);b=ev.body(e.id)
 assert b.watertight is False and b.quality!='fabrication_mesh'
 assert not assess_fabrication(ev).ready

def test_wall_with_door_and_window_can_be_promoted_as_one_closed_host_mesh():
 d=Document();wall=Entity('wall',{'x1':0.0,'y1':0.0,'z':0.0,'x2':5.0,'y2':0.0,'height':3.0,'thickness':0.2});d.add(wall)
 d.add(Entity('door',{'offset':1.5,'width':0.9,'height':2.1,'sill':0.0},parent_id=wall.id))
 d.add(Entity('window',{'offset':3.5,'width':1.2,'height':1.0,'sill':1.0},parent_id=wall.id))
 ev=ValidatedMeshBackend().evaluate(d);body=ev.body(wall.id)
 assert body.watertight is True and body.manifold is True
 assert body.quality=='fabrication_mesh'
 assert 'opening_reveal' in set(body.payload.triangle_surfaces)
 assert assess_fabrication(ev,[wall.id]).ready
