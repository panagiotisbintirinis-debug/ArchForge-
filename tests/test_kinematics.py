from archforge.core.model import Document, Entity
from archforge.kinematics.model import (
    assembly_parts,
    clamp_joint_value,
    joint_state,
    mechanism_envelope,
)


def part(x=0,y=0,z=0,w=1,d=.2,h=.2,name='Part'):
    return Entity('mechanical_part',{
        'x':x,'y':y,'z':z,'width':w,'depth':d,'height':h,'rotation':0.0
    },name=name)


def revolute(parent,child,value=0,min_value=-90,max_value=90):
    return Entity('mechanical_joint',{
        'joint_type':'revolute','parent_part':parent,'child_part':child,
        'anchor':[0,0,0],'axis':[0,0,1],
        'min_value':min_value,'max_value':max_value,'value':value,
    },name='Hinge')


def test_joint_requires_existing_parts():
    d=Document();a=part();d.add(a)
    j=revolute(a.id,'missing')
    try:d.add(j)
    except ValueError:pass
    else:raise AssertionError('missing child part should be rejected')


def test_revolute_joint_state_preserves_semantics():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);j=revolute(a.id,b.id,value=30);d.add(j)
    state=joint_state(d,j.id)
    assert state['type']=='revolute'
    assert state['rotation_deg']==30
    assert state['axis']==(0.0,0.0,1.0)


def test_prismatic_joint_returns_axis_translation():
    d=Document();a=part();b=part();d.add(a);d.add(b)
    j=Entity('mechanical_joint',{
        'joint_type':'prismatic','parent_part':a.id,'child_part':b.id,
        'anchor':[0,0,0],'axis':[1,0,0],
        'min_value':0.0,'max_value':0.5,'value':0.25,
    });d.add(j)
    assert joint_state(d,j.id)['translation']==(0.25,0.0,0.0)


def test_fixed_joint_cannot_have_motion():
    d=Document();a=part();b=part();d.add(a);d.add(b)
    j=Entity('mechanical_joint',{
        'joint_type':'fixed','parent_part':a.id,'child_part':b.id,
        'anchor':[0,0,0],'axis':[0,0,1],
        'min_value':0.0,'max_value':1.0,'value':0.0,
    })
    try:d.add(j)
    except ValueError:pass
    else:raise AssertionError('fixed joint with nonzero range must fail')


def test_joint_limits_are_enforced_on_document_update():
    d=Document();a=part();b=part();d.add(a);d.add(b);j=revolute(a.id,b.id);d.add(j)
    try:d.update(j.id,{'value':120})
    except ValueError:pass
    else:raise AssertionError('joint value outside limits should fail')
    assert d.get(j.id).params['value']==0


def test_joint_value_can_be_clamped_for_interactive_preview():
    p={'min_value':-20,'max_value':45}
    assert clamp_joint_value(p,-100)==-20
    assert clamp_joint_value(p,100)==45
    assert clamp_joint_value(p,12)==12


def test_assembly_follows_joint_tree():
    d=Document();a=part();b=part(x=1);c=part(x=2)
    for e in (a,b,c):d.add(e)
    j1=revolute(a.id,b.id);j2=revolute(b.id,c.id)
    d.add(j1);d.add(j2)
    assert assembly_parts(d,a.id)==[a.id,b.id,c.id]


def test_mechanism_envelope_includes_all_parts_and_clearance():
    d=Document();a=part(x=0,w=1,d=1,h=1);b=part(x=2,w=1,d=1,h=1)
    d.add(a);d.add(b);d.add(revolute(a.id,b.id))
    lo,hi=mechanism_envelope(d,a.id,clearance=.1)
    assert lo==(-.6,-.6,-.1)
    assert hi==(2.6,.6,1.1)


def test_mount_links_mechanical_part_to_architectural_surface():
    d=Document();wall=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});arm=part()
    d.add(wall);d.add(arm)
    mount=Entity('mechanical_mount',{
        'host_id':wall.id,'part_id':arm.id,'surface_role':'interior',
        'clearance':.02,'embed_depth':.15,
    },name='Hidden arm mount')
    d.add(mount)
    assert mount.id in d.dependencies[wall.id]
    assert mount.id in d.dependencies[arm.id]


def test_deleting_host_removes_dependent_mount_but_not_part():
    d=Document();wall=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});arm=part()
    d.add(wall);d.add(arm)
    mount=Entity('mechanical_mount',{'host_id':wall.id,'part_id':arm.id,'surface_role':'interior','clearance':0,'embed_depth':.1})
    d.add(mount);d.remove(wall.id)
    assert wall.id not in d.entities and mount.id not in d.entities
    assert arm.id in d.entities


def test_deleting_part_removes_referencing_joint_and_mount():
    d=Document();wall=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});a=part();b=part()
    d.add(wall);d.add(a);d.add(b);j=revolute(a.id,b.id);d.add(j)
    m=Entity('mechanical_mount',{'host_id':wall.id,'part_id':a.id,'surface_role':'interior','clearance':0,'embed_depth':.1});d.add(m)
    d.remove(a.id)
    assert a.id not in d.entities and j.id not in d.entities and m.id not in d.entities
    assert b.id in d.entities and wall.id in d.entities


def test_mechanical_entities_roundtrip_even_if_serialized_out_of_order():
    d=Document();wall=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2});a=part();b=part(x=1)
    d.add(wall);d.add(a);d.add(b);j=revolute(a.id,b.id,value=15);d.add(j)
    m=Entity('mechanical_mount',{'host_id':wall.id,'part_id':a.id,'surface_role':'interior','clearance':.01,'embed_depth':.1});d.add(m)
    raw=d.to_dict();raw['entities']=list(reversed(raw['entities']))
    d2=Document.from_dict(raw)
    assert d2.get(j.id).params['value']==15
    assert d2.get(m.id).params['part_id']==a.id


def test_joint_relink_is_not_a_generic_edit():
    d=Document();a=part();b=part();c=part()
    for e in (a,b,c):d.add(e)
    j=revolute(a.id,b.id);d.add(j)
    try:d.update(j.id,{'child_part':c.id})
    except ValueError:pass
    else:raise AssertionError('generic update must not stale dependency graph')
    assert d.get(j.id).params['child_part']==b.id
