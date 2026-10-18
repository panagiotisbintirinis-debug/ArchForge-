"""Our three-storey urban layout; geometry/interaction contracts, not a study."""
import pytest
from pathlib import Path
from archforge.project.persistence import load_project
from archforge.architecture.stairs import candidate_from_params,stair_centerline,stair_wall_conflicts
from archforge.mep.electrical import design_circuits,POINT_TYPES
from tests.test_stair_slab_opening import _covered

PATH=Path(__file__).parent/'residential_scenarios/S03_three_storey_urban_residence.archforge'


def document():
    r=load_project(PATH);assert r.ok,r.message();return r.doc


@pytest.mark.parametrize('index',[0,1])
def test_both_floors_have_actual_stair_openings_guards_and_storage(index):
    d=document();sid=f's03-stair-{index}';c=candidate_from_params(d.get(sid).params)
    path=stair_centerline(c);end=path[-1];prev=path[-2]
    p=tuple(end[i]+.1*(prev[i]-end[i]) for i in (0,1))
    assert not _covered(d,d.get(f's03-floor-{index+1}'),*p)
    assert _covered(d,d.get(f's03-floor-{index+1}'),end[0]-.1,end[1])
    assert not stair_wall_conflicts(d,c)
    children=[d.get(i) for i in d.children.get(sid,())]
    assert any(e.kind=='cabinet' and e.params.get('under_stair') for e in children)
    assert any('-opening-guard-' in e.id for e in children)


def test_rooms_are_distinct_uses_with_setback_terrace_not_three_duplicate_kitchens():
    d=document()
    assert d.get('s03-wall-2-2').params['y1']==7.
    assert d.get('s03-wall-1-2').params['y1']==9.
    assert all(e.params['z']==3. for e in d.entities.values() if e.kind=='cabinet' and not e.params.get('under_stair'))
    assert len([e for e in d.entities.values() if e.kind=='library_object'])>=30
    assert not any(e.kind=='box' for e in d.entities.values())
    assert d.get('s03-north-terrace-rail').params['z']==6.
    assert not any(e.kind=='structural_column' and e.params.get('role')=='pergola' for e in d.entities.values())


def test_every_luminaire_has_a_control_and_openings_fit_their_walls():
    import math
    d=document();circuits=design_circuits(d)
    lights={e.id for e in d.entities.values() if e.kind=='electrical_point' and POINT_TYPES[e.params['point_type']][1]=='lighting'}
    assert lights <= {i for link in circuits['switch_links'] for i in link['lights']}
    for e in d.entities.values():
        if e.kind not in ('door','window'):continue
        p=d.get(e.parent_id).params;L=math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])
        assert e.params['offset']-e.params['width']/2>=0
        assert e.params['offset']+e.params['width']/2<=L+1e-6


def test_upper_furniture_stands_on_retained_floor_not_over_the_stair_hole():
    import math
    d=document();floor=d.get('s03-floor-2')
    for e in d.entities.values():
        p=e.params
        if e.kind!='library_object' or p['z']!=6.:continue
        w,h=p['width'],p['depth'];angle=math.radians(p.get('rotation',0));c,s=math.cos(angle),math.sin(angle)
        for x,y in ((-w/2,-h/2),(-w/2,h/2),(w/2,-h/2),(w/2,h/2)):
            assert _covered(d,floor,p['x']+x*c-y*s,p['y']+x*s+y*c),e.name
