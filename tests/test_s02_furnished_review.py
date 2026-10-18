"""S02 editable fixture contracts; these do not certify engineering rules."""
from pathlib import Path
from archforge.project.persistence import load_project
from archforge.architecture.stairs import candidate_from_params, stair_centerline, stair_wall_conflicts
from archforge.mep.electrical import design_circuits, POINT_TYPES
from tests.test_stair_slab_opening import _covered

PATH=Path(__file__).parent/'residential_scenarios/S02_split_level_hillside_house.archforge'


def document():
    result=load_project(PATH)
    assert result.ok,result.message()
    return result.doc


def test_actual_upper_slab_is_open_at_stair_exit_and_retained_away_from_stair():
    doc=document();candidate=candidate_from_params(doc.get('s02-stair-main').params)
    path=stair_centerline(candidate);end=path[-1];previous=path[-2]
    # Last tread, just before the landing boundary; the landing itself stays solid.
    point=tuple(end[i]+.1*(previous[i]-end[i]) for i in (0,1))
    assert not _covered(doc,doc.get('s02-floor-1'),*point)
    assert _covered(doc,doc.get('s02-floor-1'),8.,6.)
    assert not stair_wall_conflicts(doc,candidate)
    assert not stair_wall_conflicts(doc,candidate_from_params(doc.get('s02-stair-annex').params))


def test_every_luminaire_has_a_switch_and_every_switch_has_a_light():
    doc=document();design=design_circuits(doc)
    lights={e.id for e in doc.entities.values() if e.kind=='electrical_point' and POINT_TYPES[e.params['point_type']][1]=='lighting'}
    assert lights <= {eid for link in design['switch_links'] for eid in link['lights']}
    assert all(link['lights'] for link in design['switch_links'])


def test_door_and_window_openings_fit_their_host_walls():
    import math
    doc=document()
    for e in doc.entities.values():
        if e.kind not in ('door','window'):continue
        p=doc.get(e.parent_id).params
        length=math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])
        assert 0 <= e.params['offset']-e.params['width']/2
        assert e.params['offset']+e.params['width']/2 <= length+1e-6,e.id


def test_real_furniture_and_cove_geometry_keep_missing_photometry_explicit():
    doc=document()
    assert len([e for e in doc.entities.values() if e.kind=='library_object'])==26
    assert not any(e.kind=='box' for e in doc.entities.values())
    strips=[e for e in doc.entities.values() if e.kind=='electrical_point' and e.params['point_type']=='led_strip']
    assert len(strips)==8
    assert all(not e.params.get('lumens') and not e.params.get('watts_per_m') for e in strips)


def test_space_is_used_instead_of_a_closed_stair_quarter_and_corridor():
    from archforge.quantities.takeoff import take_off
    d=document();rooms=take_off(d)['rooms']
    assert not any(r['name'] in ('Κλιμακοστάσιο','Διάδρομος') for r in rooms)
    living=next(r for r in rooms if r['storey']=='Ground' and 'Ενιαίος' in r['name'])
    assert living['floor_m2']>45  # previous enclosed living area was under 20 m²
    assert any(e.kind=='cabinet' and e.parent_id=='s02-stair-main' and e.params.get('under_stair') for e in d.entities.values())


def test_opening_has_guards_except_at_the_stair_exit_and_retains_floor_above_low_steps():
    from tests.residential_scenarios.space_economy import opening_guard_lines
    d=document();stair=d.get('s02-stair-main');candidate=candidate_from_params(stair.params)
    guards=[e for e in d.entities.values() if e.id.startswith('s02-stair-main-opening-guard-')]
    assert guards
    actual=[(tuple(a),tuple(b)) for e in guards for a,b in zip(e.params['points'],e.params['points'][1:])]
    assert sorted(actual)==sorted(opening_guard_lines(stair,3.02))
    assert all(e.params['z']==3.2 for e in guards)
    path=stair_centerline(candidate)
    assert _covered(d,d.get('s02-floor-1'),path[0][0]+.15,path[0][1])


def test_pergola_has_no_second_frame_and_rafters_meet_existing_support_elevations():
    import pytest
    d=document()
    pergola=[e for e in d.entities.values() if e.id.startswith('s02-terrace-pergola-')]
    assert pergola and all(e.kind=='structural_beam' and e.name=='Τεγίδα πέργκολας' for e in pergola)
    wall=d.get('s02-wall-1-1').params
    edge=d.get('s02-beamy-1-2').params
    for e in pergola:
        p=e.params
        assert p['x1']==wall['x1']
        assert p['x2']==edge['x1']
        assert p['z']==pytest.approx(wall['z']+wall['height'])
        assert p['z']==pytest.approx(edge['z']+edge['height'])
        assert wall['y1'] <= p['y1']==p['y2'] <= wall['y2']
