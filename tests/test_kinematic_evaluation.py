from math import isclose

from archforge.core.model import Document, Entity
from archforge.kinematics.evaluation import (
    evaluate_assembly,
    evaluated_mechanism_envelope,
    joint_delta_matrix,
    transform_point,
)


def part(x=0,y=0,z=0,w=.4,d=.2,h=.2,rotation=0):
    return Entity('mechanical_part',{'x':x,'y':y,'z':z,'width':w,'depth':d,'height':h,'rotation':rotation})


def joint(parent,child,jtype='revolute',anchor=(0,0,0),axis=(0,0,1),value=0,lo=-180,hi=180):
    return Entity('mechanical_joint',{
        'joint_type':jtype,'parent_part':parent,'child_part':child,
        'anchor':list(anchor),'axis':list(axis),'min_value':lo,'max_value':hi,'value':value,
    })


def close3(a,b,tol=1e-9):
    return all(isclose(a[i],b[i],abs_tol=tol) for i in range(3))


def test_revolute_delta_rotates_about_anchor():
    p={'joint_type':'revolute','anchor':[1,0,0],'axis':[0,0,1],'min_value':-180,'max_value':180,'value':90}
    m=joint_delta_matrix(p)
    assert close3(transform_point(m,(2,0,0)),(1,1,0))
    assert close3(transform_point(m,(1,0,0)),(1,0,0))


def test_prismatic_delta_translates_along_normalized_axis():
    p={'joint_type':'prismatic','anchor':[0,0,0],'axis':[2,0,0],'min_value':0,'max_value':2,'value':.5}
    m=joint_delta_matrix(p)
    assert close3(transform_point(m,(1,2,3)),(1.5,2,3))


def test_single_hinge_moves_child_without_mutating_source_pose():
    d=Document();root=part();child=part(x=1);d.add(root);d.add(child);j=joint(root.id,child.id,value=90);d.add(j)
    before=child.params.copy();ev=evaluate_assembly(d,root.id)
    assert close3(transform_point(ev[child.id].matrix,(0,0,0)),(0,1,0))
    assert d.get(child.id).params==before


def test_joint_override_is_preview_only():
    d=Document();root=part();child=part(x=1);d.add(root);d.add(child);j=joint(root.id,child.id,value=0);d.add(j)
    ev=evaluate_assembly(d,root.id,{j.id:90})
    assert close3(transform_point(ev[child.id].matrix,(0,0,0)),(0,1,0))
    assert d.get(j.id).params['value']==0


def test_descendant_inherits_parent_joint_motion():
    d=Document();a=part();b=part(x=1);c=part(x=2)
    for e in (a,b,c):d.add(e)
    j1=joint(a.id,b.id,value=90,anchor=(0,0,0));j2=joint(b.id,c.id,value=0,anchor=(1,0,0))
    d.add(j1);d.add(j2);ev=evaluate_assembly(d,a.id)
    assert close3(transform_point(ev[c.id].matrix,(0,0,0)),(0,2,0))


def test_two_hinges_compose_in_order():
    d=Document();a=part();b=part(x=1);c=part(x=2)
    for e in (a,b,c):d.add(e)
    j1=joint(a.id,b.id,value=90,anchor=(0,0,0));j2=joint(b.id,c.id,value=90,anchor=(1,0,0))
    d.add(j1);d.add(j2);ev=evaluate_assembly(d,a.id)
    assert close3(transform_point(ev[c.id].matrix,(0,0,0)),(-1,1,0))


def test_evaluated_envelope_changes_with_joint_preview():
    d=Document();a=part(w=.2,d=.2);b=part(x=1,w=.4,d=.2)
    d.add(a);d.add(b);j=joint(a.id,b.id,value=0);d.add(j)
    lo0,hi0=evaluated_mechanism_envelope(d,a.id,{j.id:0})
    lo1,hi1=evaluated_mechanism_envelope(d,a.id,{j.id:90})
    assert hi0[0]>hi1[0]
    assert hi1[1]>hi0[1]


def test_clearance_expands_evaluated_envelope():
    d=Document();a=part();d.add(a)
    lo0,hi0=evaluated_mechanism_envelope(d,a.id,clearance=0)
    lo1,hi1=evaluated_mechanism_envelope(d,a.id,clearance=.1)
    assert isclose(lo1[0],lo0[0]-.1) and isclose(hi1[2],hi0[2]+.1)


def test_multiple_incoming_joints_are_rejected_by_evaluator():
    d=Document();a=part();b=part();c=part()
    for e in (a,b,c):d.add(e)
    d.add(joint(a.id,c.id));d.add(joint(b.id,c.id))
    try:evaluate_assembly(d,a.id)
    except ValueError as exc:assert 'multiple incoming' in str(exc)
    else:raise AssertionError('ambiguous kinematic parent must fail')


def test_cycle_is_rejected_by_evaluator():
    d=Document();a=part();b=part()
    d.add(a);d.add(b);d.add(joint(a.id,b.id));d.add(joint(b.id,a.id))
    try:evaluate_assembly(d,a.id)
    except ValueError as exc:assert 'cycle' in str(exc)
    else:raise AssertionError('kinematic cycle must fail')


def test_non_root_part_with_incoming_joint_cannot_be_evaluated_as_root():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);d.add(joint(a.id,b.id))
    try:evaluate_assembly(d,b.id)
    except ValueError as exc:assert 'incoming joint' in str(exc)
    else:raise AssertionError('subpart root should be explicit only after detaching')
