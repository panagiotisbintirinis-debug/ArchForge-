from archforge.core.model import Document, Entity

# Semantic wall-opening tests.
def test_opening_requires_wall_host():
    d=Document()
    import pytest
    with pytest.raises(ValueError):d.add(Entity('window',{'offset':1,'width':1,'height':1,'sill':1}))

def test_window_attaches_to_wall_and_tracks_dependency():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':.2});d.add(w);o=Entity('window',{'offset':2.5,'width':1.2,'height':1.1,'sill':.9},parent_id=w.id);d.add(o);assert o.id in d.children[w.id];assert o.id in d.dependencies[w.id]

def test_opening_rejects_out_of_wall_width():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':3,'y2':0,'height':3,'thickness':.2});d.add(w);import pytest
    with pytest.raises(ValueError):d.add(Entity('door',{'offset':.2,'width':1,'height':2.1,'sill':0},parent_id=w.id))

def test_door_requires_zero_sill():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':3,'y2':0,'height':3,'thickness':.2});d.add(w);import pytest
    with pytest.raises(ValueError):d.add(Entity('door',{'offset':1.5,'width':.9,'height':2.1,'sill':.1},parent_id=w.id))

def test_wall_cannot_shrink_through_opening():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':.2});d.add(w);o=Entity('window',{'offset':4.0,'width':1,'height':1,'sill':1},parent_id=w.id);d.add(o);import pytest
    with pytest.raises(ValueError):d.update(w.id,{'x2':4.2})

def test_opening_plan_and_elevation_primitives():
    from archforge.core.plan_scene import entity_primitive
    from archforge.core.view_frame import entity_view_primitives
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':.2});d.add(w);o=Entity('window',{'offset':2.5,'width':1,'height':1.2,'sill':.8},parent_id=w.id);d.add(o)
    pp=entity_primitive(d,o.id);assert pp.role=='opening' and pp.points==((2.0,0.0),(3.0,0.0));ep=entity_view_primitives(d,o.id,'XZ')[0];assert ep.role=='opening' and ep.points==((2.0,.8),(3.0,.8),(3.0,2.0),(2.0,2.0))

def test_opening_persists_roundtrip():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'z':0,'x2':5,'y2':0,'height':3,'thickness':.2});d.add(w);o=Entity('door',{'offset':2.5,'width':.9,'height':2.1,'sill':0},parent_id=w.id);d.add(o);d2=Document.from_dict(d.to_dict());assert d2.get(o.id).parent_id==w.id;assert o.id in d2.children[w.id];assert o.id in d2.dependencies[w.id]
