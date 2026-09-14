from archforge.core.model import Document, Entity
from archforge.kinematics.motion import sampled_joint_states, sampled_motion_envelope
from archforge.kinematics.integration import cavity_modifier_for_mount


def part(x=0,y=0,z=0,w=.2,d=.2,h=.2):
    return Entity('mechanical_part',{'x':x,'y':y,'z':z,'width':w,'depth':d,'height':h,'rotation':0.0})


def joint(parent,child,lo=0,hi=90,value=0):
    return Entity('mechanical_joint',{
        'joint_type':'revolute','parent_part':parent,'child_part':child,
        'anchor':[0,0,0],'axis':[0,0,1],
        'min_value':lo,'max_value':hi,'value':value,
    })


def test_sampled_states_include_range_endpoints():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);j=joint(a.id,b.id,lo=-30,hi=60,value=10);d.add(j)
    states=sampled_joint_states(d,a.id,samples_per_joint=3)
    values=[s[j.id] for s in states]
    assert -30 in values and 60 in values and 10 in values


def test_motion_envelope_covers_both_hinge_extremes():
    d=Document();a=part();b=part(x=1,w=.4,d=.2);d.add(a);d.add(b);j=joint(a.id,b.id,0,90,0);d.add(j)
    lo,hi=sampled_motion_envelope(d,a.id,samples_per_joint=5)
    assert hi[0] > 1.1
    assert hi[1] > 1.1
    assert lo[0] < 0


def test_motion_envelope_does_not_mutate_joint_value():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);j=joint(a.id,b.id,-90,90,17);d.add(j)
    sampled_motion_envelope(d,a.id,samples_per_joint=5)
    assert d.get(j.id).params['value']==17


def test_state_limit_prevents_combinatorial_explosion():
    d=Document();parts=[part(x=i) for i in range(4)]
    for p in parts:d.add(p)
    for a,b in zip(parts,parts[1:]):d.add(joint(a.id,b.id,-90,90,0))
    try:sampled_motion_envelope(d,parts[0].id,samples_per_joint=5,max_states=20)
    except ValueError as exc:assert 'states' in str(exc)
    else:raise AssertionError('state limit must protect interactive evaluation')


def test_clearance_expands_motion_envelope():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);d.add(joint(a.id,b.id))
    lo0,hi0=sampled_motion_envelope(d,a.id,clearance=0)
    lo1,hi1=sampled_motion_envelope(d,a.id,clearance=.05)
    assert abs((lo0[0]-.05)-lo1[0])<1e-9
    assert abs((hi0[2]+.05)-hi1[2])<1e-9


def test_embedded_cavity_defaults_to_sampled_motion_envelope():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.3});a=part();b=part(x=1)
    d.add(w);d.add(a);d.add(b);d.add(joint(a.id,b.id,0,90,0))
    m=Entity('mechanical_mount',{'host_id':w.id,'part_id':a.id,'surface_role':'interior','clearance':.02,'embed_depth':.2});d.add(m)
    mod=cavity_modifier_for_mount(d,m.id,samples_per_joint=5)
    assert mod.params['envelope_mode']=='sampled_motion'
    assert mod.params['samples_per_joint']==5
    assert mod.target.subregion['envelope_max'][1] > 1.0


def test_rest_pose_cavity_remains_available_for_static_designs():
    d=Document();w=Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.3});a=part();d.add(w);d.add(a)
    m=Entity('mechanical_mount',{'host_id':w.id,'part_id':a.id,'surface_role':'interior','clearance':0,'embed_depth':.2});d.add(m)
    mod=cavity_modifier_for_mount(d,m.id,include_motion=False)
    assert mod.params['envelope_mode']=='rest_pose'
    assert mod.params['samples_per_joint']==0
