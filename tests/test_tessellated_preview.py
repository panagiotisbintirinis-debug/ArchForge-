import math
from archforge.core.model import Document,Entity
from archforge.geometry.mesh import TessellatedPreviewBackend


def test_wall_mesh_retains_semantic_surface_per_triangle_and_has_local_resolution():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});d.add(w)
    b=TessellatedPreviewBackend().evaluate(d).body(w.id);m=b.payload
    assert len(m.vertices)>8 and len(m.triangles)>12
    assert len(m.triangles)==len(m.triangle_surfaces)
    assert {'exterior','interior','top','start','end','bottom'}==set(m.triangle_surfaces)
    assert b.quality=='preview-mesh' and b.watertight is None


def test_wall_surface_spacing_is_fine_enough_for_local_brush():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':5,'y2':0,'z':0,'height':3,'thickness':.2});d.add(w)
    m=TessellatedPreviewBackend().evaluate(d).body(w.id).payload
    exterior_vertices={i for ti,t in enumerate(m.triangles) if m.triangle_surfaces[ti]=='exterior' for i in t}
    xs=sorted({round(m.vertices[i][0],6) for i in exterior_vertices})
    zs=sorted({round(m.vertices[i][2],6) for i in exterior_vertices})
    assert max(b-a for a,b in zip(xs,xs[1:]))<=.500001
    assert max(b-a for a,b in zip(zs,zs[1:]))<=.500001


def test_pod_has_no_geometry_below_floor():
    d=Document();p=Entity('pod',{'cx':2,'cy':3,'diameter_x':6,'diameter_y':4,'height':2.5,'floor_level':7});d.add(p)
    m=TessellatedPreviewBackend().evaluate(d).body(p.id).payload
    assert min(v[2] for v in m.vertices)>=7
    assert max(v[2] for v in m.vertices)<=9.5+1e-9
    assert set(m.triangle_surfaces)=={'pod_shell'}


def test_rotated_box_is_real_triangle_geometry_with_catalog_roles():
    d=Document();e=Entity('box',{'x':1,'y':2,'z':3,'width':2,'depth':1,'height':4,'rotation':90});d.add(e)
    m=TessellatedPreviewBackend().evaluate(d).body(e.id).payload
    assert len(m.triangles)==12
    assert set(m.triangle_surfaces)=={'front','right','back','left','top','bottom'}
    xs=[v[0] for v in m.vertices];ys=[v[1] for v in m.vertices]
    assert math.isclose(max(xs)-min(xs),1,abs_tol=1e-8)
    assert math.isclose(max(ys)-min(ys),2,abs_tol=1e-8)


def test_floor_generates_closed_semantic_prism():
    d=Document();f=Entity('floor',{'points':[(0,0),(4,0),(4,3),(0,3)],'z':1,'thickness':.2});d.add(f)
    result=TessellatedPreviewBackend().evaluate(d);m=result.body(f.id).payload
    assert not any(i.entity_id==f.id for i in result.issues)
    assert set(m.triangle_surfaces)=={'top','bottom','edge'}
    assert min(v[2] for v in m.vertices)==1 and max(v[2] for v in m.vertices)==1.2


def test_concave_floor_triangulates_without_fan_crossing():
    d=Document();f=Entity('floor',{'points':[(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)],'z':0,'thickness':.15});d.add(f)
    m=TessellatedPreviewBackend().evaluate(d).body(f.id).payload
    assert len([r for r in m.triangle_surfaces if r=='top'])==4
    assert len([r for r in m.triangle_surfaces if r=='bottom'])==4
    assert len([r for r in m.triangle_surfaces if r=='edge'])==12


def test_mechanical_part_uses_evaluated_transform():
    d=Document();a=Entity('mechanical_part',{'x':0,'y':0,'z':0,'width':1,'depth':1,'height':1,'rotation':0,'role':'link'});d.add(a)
    result=TessellatedPreviewBackend().evaluate(d)
    assert len(result.body(a.id).payload.vertices)==8
    assert set(result.body(a.id).payload.triangle_surfaces)=={'front','right','back','left','top','bottom'}
