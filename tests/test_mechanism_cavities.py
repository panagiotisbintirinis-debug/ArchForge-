from archforge.core.model import Document, Entity
from archforge.kinematics.integration import cavity_modifier_for_mount, ensure_mount_cavity


def wall():
    return Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.25})


def part(x=1.0,y=0.0,z=1.0,w=.5,d=.2,h=.5):
    return Entity('mechanical_part',{'x':x,'y':y,'z':z,'width':w,'depth':d,'height':h,'rotation':0.0})


def mount(doc,host,root):
    m=Entity('mechanical_mount',{
        'host_id':host.id,'part_id':root.id,'surface_role':'interior',
        'clearance':.02,'embed_depth':.18,
    },name='Retractable arm bay')
    doc.add(m);return m


def test_cavity_request_targets_host_surface_without_destroying_wall_semantics():
    d=Document();w=wall();a=part();d.add(w);d.add(a);m=mount(d,w,a)
    mod=cavity_modifier_for_mount(d,m.id)
    assert mod.target.owner_id==w.id
    assert mod.target.surface_role=='interior'
    assert mod.operation=='cut'
    assert mod.params['mode']=='mechanism_clearance'
    assert d.get(w.id).kind=='wall'


def test_cavity_contains_mechanism_envelope_and_mount_identity():
    d=Document();w=wall();a=part();d.add(w);d.add(a);m=mount(d,w,a)
    mod=cavity_modifier_for_mount(d,m.id)
    region=mod.target.subregion
    assert region['selector']=='mechanism_cavity'
    assert region['mount_id']==m.id
    assert region['envelope_min'][0] < a.params['x']
    assert region['envelope_max'][0] > a.params['x']


def test_ensure_mount_cavity_is_idempotent():
    d=Document();w=wall();a=part();d.add(w);d.add(a);m=mount(d,w,a)
    first=ensure_mount_cavity(d,m.id)
    second=ensure_mount_cavity(d,m.id)
    assert first==second
    linked=[x for x in d.surface_modifiers.values() if x.params.get('mount_id')==m.id]
    assert len(linked)==1


def test_cavity_refreshes_when_mechanism_dimensions_change():
    d=Document();w=wall();a=part(w=.4);d.add(w);d.add(a);m=mount(d,w,a)
    mid=ensure_mount_cavity(d,m.id)
    before=d.surface_modifiers[mid].target.subregion['envelope_max'][0]
    d.update(a.id,{'width':1.2})
    same=ensure_mount_cavity(d,m.id)
    after=d.surface_modifiers[mid].target.subregion['envelope_max'][0]
    assert same==mid and after>before


def test_extra_clearance_expands_cavity():
    d=Document();w=wall();a=part();d.add(w);d.add(a);m=mount(d,w,a)
    a0=cavity_modifier_for_mount(d,m.id,extra_clearance=0.0)
    a1=cavity_modifier_for_mount(d,m.id,extra_clearance=.1)
    lo0=a0.target.subregion['envelope_min'];lo1=a1.target.subregion['envelope_min']
    hi0=a0.target.subregion['envelope_max'];hi1=a1.target.subregion['envelope_max']
    assert lo1[0]<lo0[0] and hi1[0]>hi0[0]


def test_negative_extra_clearance_rejected():
    d=Document();w=wall();a=part();d.add(w);d.add(a);m=mount(d,w,a)
    try:cavity_modifier_for_mount(d,m.id,extra_clearance=-.01)
    except ValueError:pass
    else:raise AssertionError('negative extra clearance must fail')


def test_cavity_modifier_persists_with_project():
    d=Document();w=wall();a=part();d.add(w);d.add(a);m=mount(d,w,a);mid=ensure_mount_cavity(d,m.id)
    d2=Document.from_dict(d.to_dict())
    restored=d2.surface_modifiers[mid]
    assert restored.params['mount_id']==m.id
    assert restored.target.owner_id==w.id
