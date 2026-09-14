from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceRef, SurfaceModifier, ordered_modifiers


def wall():
    return Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':2.7,'thickness':0.2})


def test_surface_modifier_targets_any_semantic_surface_role():
    d=Document();w=wall();d.add(w)
    m=SurfaceModifier(SurfaceRef(w.id,'exterior',{'uv_center':[.5,.7],'radius':.2}),'pull',{'amount':.35},name='Rain hood')
    mid=d.add_surface_modifier(m)
    assert d.surface_modifiers[mid].target.surface_role=='exterior'
    assert d.surface_modifiers[mid].params['amount']==.35


def test_ceiling_surface_can_receive_sculpt_modifier():
    d=Document();r=Entity('room',{'points':[(0,0),(4,0),(4,3),(0,3)],'z':0,'height':2.8});d.add(r)
    m=SurfaceModifier(SurfaceRef(r.id,'ceiling',{'uv_center':[.5,.5],'radius':.25}),'recess',{'amount':.12})
    d.add_surface_modifier(m)
    assert ordered_modifiers(d,r.id)[0].target.surface_role=='ceiling'


def test_pod_junction_can_be_deformed_without_destroying_semantics():
    d=Document();p=Entity('pod',{'cx':0,'cy':0,'floor_level':0,'diameter_x':5,'diameter_y':4,'height':2.5,'shell_thickness':.12,'rotation':0});d.add(p)
    m=SurfaceModifier(SurfaceRef(p.id,'junction',{'junction_key':'podA-podB','mask':'patch-1'}),'inflate',{'amount':.2})
    d.add_surface_modifier(m)
    assert d.get(p.id).kind=='pod'
    assert d.surface_modifiers[m.id].target.surface_role=='junction'


def test_modifier_persistence_roundtrip():
    d=Document();w=wall();d.add(w)
    m=SurfaceModifier(SurfaceRef(w.id,'exterior',{'mask':'brush-7'}),'pull',{'amount':.4},order=3)
    d.add_surface_modifier(m)
    loaded=Document.from_dict(d.to_dict())
    # Surface modifiers require format 6 or newer; later project features may advance it.
    assert loaded.to_dict()['format']>=6
    restored=loaded.surface_modifiers[m.id]
    assert restored.target.owner_id==w.id
    assert restored.target.subregion['mask']=='brush-7'
    assert restored.params['amount']==.4


def test_delete_owner_removes_surface_modifiers():
    d=Document();w=wall();d.add(w)
    m=SurfaceModifier(SurfaceRef(w.id,'exterior'),'pull',{'amount':.2});d.add_surface_modifier(m)
    d.remove(w.id)
    assert m.id not in d.surface_modifiers


def test_invalid_owner_is_rejected():
    d=Document()
    m=SurfaceModifier(SurfaceRef('missing','exterior'),'pull',{'amount':.2})
    try:d.add_surface_modifier(m)
    except ValueError:pass
    else:raise AssertionError('missing owner must be rejected')


def test_modifier_order_is_explicit_and_stable():
    d=Document();w=wall();d.add(w)
    b=SurfaceModifier(SurfaceRef(w.id,'exterior'),'smooth',{},order=20)
    a=SurfaceModifier(SurfaceRef(w.id,'exterior'),'pull',{'amount':.1},order=10)
    d.add_surface_modifier(b);d.add_surface_modifier(a)
    assert [m.id for m in ordered_modifiers(d,w.id)]==[a.id,b.id]


def test_modifier_can_be_disabled_non_destructively():
    d=Document();w=wall();d.add(w)
    m=SurfaceModifier(SurfaceRef(w.id,'exterior'),'pull',{'amount':.2});d.add_surface_modifier(m)
    d.update_surface_modifier(m.id,enabled=False)
    assert d.surface_modifiers[m.id].enabled is False
    assert d.get(w.id).params['x2']==4.0
