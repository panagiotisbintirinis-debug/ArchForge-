import pytest

from archforge.core.model import Document,Entity
from archforge.geometry.validated_mesh import ValidatedMeshBackend
from archforge.geometry.fabrication import assess_fabrication
from archforge.geometry.selection import SurfaceHit,BrushSpec,sculpt_modifier_from_hit
from archforge.geometry.solid_validation import IncompleteSolidValidityError


def test_closed_box_requires_exact_solid_validity_before_fabrication_promotion():
 d=Document();e=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});d.add(e)
 with pytest.raises(IncompleteSolidValidityError,match='self-intersections are not proven absent'):
  ValidatedMeshBackend().evaluate(d)


def test_active_unapplied_modifier_blocks_promotion_before_exact_solid_gate():
 d=Document();e=Entity('box',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0});d.add(e)
 m=sculpt_modifier_from_hit(d,SurfaceHit(e.id,'top',(.5,.5,1),(0,0,1)),BrushSpec(.4),'pull',.1);d.add_surface_modifier(m)
 ev=ValidatedMeshBackend().evaluate(d);b=ev.body(e.id)
 assert b.quality!='fabrication_mesh' and not assess_fabrication(ev).ready


def test_open_pod_is_never_promoted_to_fabrication_mesh():
 d=Document();e=Entity('pod',{'cx':0,'cy':0,'floor_level':0,'diameter_x':4,'diameter_y':4,'height':2,'shell_thickness':.1,'rotation':0});d.add(e)
 ev=ValidatedMeshBackend().evaluate(d);b=ev.body(e.id)
 assert b.watertight is False and b.quality!='fabrication_mesh'
 assert not assess_fabrication(ev).ready


def test_closed_wall_with_openings_requires_exact_solid_validity():
 d=Document();wall=Entity('wall',{'x1':0.0,'y1':0.0,'z':0.0,'x2':5.0,'y2':0.0,'height':3.0,'thickness':0.2});d.add(wall)
 d.add(Entity('door',{'offset':1.5,'width':0.9,'height':2.1,'sill':0.0},parent_id=wall.id))
 d.add(Entity('window',{'offset':3.5,'width':1.2,'height':1.0,'sill':1.0},parent_id=wall.id))
 with pytest.raises(IncompleteSolidValidityError,match='BRepCheck_Analyzer'):
  ValidatedMeshBackend().evaluate(d)
