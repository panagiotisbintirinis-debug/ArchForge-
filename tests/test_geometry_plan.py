from archforge.core.model import Document, Entity
from archforge.core.modifiers import SurfaceRef, SurfaceModifier
from archforge.geometry.plan import build_evaluation_plan, fabrication_candidates


def wall():
    return Entity('wall',{'x1':0,'y1':0,'x2':4,'y2':0,'z':0,'height':3,'thickness':.2})


def part(x=0,y=0,z=0):
    return Entity('mechanical_part',{'x':x,'y':y,'z':z,'width':.4,'depth':.2,'height':.2,'rotation':0})


def joint(parent,child,value=0):
    return Entity('mechanical_joint',{
        'joint_type':'revolute','parent_part':parent,'child_part':child,
        'anchor':[0,0,0],'axis':[0,0,1],
        'min_value':-90,'max_value':90,'value':value,
    })


def test_plan_keeps_semantic_wall_and_ordered_sculpt_stack():
    d=Document();w=wall();d.add(w)
    b=SurfaceModifier(SurfaceRef(w.id,'exterior'),'smooth',{},order=20)
    a=SurfaceModifier(SurfaceRef(w.id,'exterior'),'pull',{'amount':.2},order=10)
    d.add_surface_modifier(b);d.add_surface_modifier(a)
    plan=build_evaluation_plan(d);node=plan.node(w.id)
    assert node.semantic_kind=='wall'
    assert [m['operation'] for m in node.modifiers]==['pull','smooth']
    assert d.get(w.id).params['x2']==4.0


def test_relationship_entities_are_not_geometry_nodes():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);j=joint(a.id,b.id);d.add(j)
    plan=build_evaluation_plan(d)
    assert plan.node(j.id).role=='relationship'
    assert j.id not in {n.entity_id for n in plan.geometry_nodes()}


def test_mechanical_transform_is_evaluated_without_editing_part():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);j=joint(a.id,b.id,value=90);d.add(j)
    before=b.params.copy();plan=build_evaluation_plan(d);m=plan.node(b.id).transform
    assert m is not None
    assert abs(m[0][3])<1e-9 and abs(m[1][3]-1)<1e-9
    assert d.get(b.id).params==before


def test_joint_value_override_changes_plan_only():
    d=Document();a=part();b=part(x=1);d.add(a);d.add(b);j=joint(a.id,b.id,value=0);d.add(j)
    plan=build_evaluation_plan(d,{j.id:90});m=plan.node(b.id).transform
    assert abs(m[1][3]-1)<1e-9
    assert d.get(j.id).params['value']==0
    assert plan.joint_values[j.id]==90


def test_mechanism_cavity_modifier_stays_on_architectural_host():
    from archforge.kinematics.integration import ensure_mount_cavity
    d=Document();w=wall();a=part(x=1);d.add(w);d.add(a)
    mount=Entity('mechanical_mount',{'host_id':w.id,'part_id':a.id,'surface_role':'interior','clearance':.02,'embed_depth':.1});d.add(mount)
    mid=ensure_mount_cavity(d,mount.id)
    plan=build_evaluation_plan(d);node=plan.node(w.id)
    linked=[m for m in node.modifiers if m['id']==mid]
    assert len(linked)==1
    assert linked[0]['operation']=='cut'
    assert linked[0]['params']['mode']=='mechanism_clearance'


def test_fabrication_candidates_exclude_relationships_and_rooms():
    d=Document();w=wall();a=part();d.add(w);d.add(a)
    room=Entity('room',{'points':[(0,0),(4,0),(4,3),(0,3)],'z':0,'height':3});d.add(room)
    m=Entity('mechanical_mount',{'host_id':w.id,'part_id':a.id,'surface_role':'interior','clearance':0,'embed_depth':.1});d.add(m)
    ids={n.entity_id for n in fabrication_candidates(build_evaluation_plan(d))}
    assert w.id in ids and a.id in ids
    assert room.id not in ids and m.id not in ids


def test_fabrication_candidate_does_not_claim_printability():
    d=Document();w=wall();d.add(w)
    candidates=fabrication_candidates(build_evaluation_plan(d))
    assert candidates[0].semantic_kind=='wall'
    assert not hasattr(candidates[0],'watertight')


def test_invalid_multiple_parent_mechanism_fails_plan_compile():
    d=Document();a=part();b=part();c=part()
    for e in (a,b,c):d.add(e)
    d.add(joint(a.id,c.id));d.add(joint(b.id,c.id))
    try:build_evaluation_plan(d)
    except ValueError as exc:assert 'multiple incoming' in str(exc)
    else:raise AssertionError('ambiguous mechanism must fail before geometry backend')
