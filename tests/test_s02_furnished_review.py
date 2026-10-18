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
    assert len([e for e in doc.entities.values() if e.kind=='library_object'])==22
    assert not any(e.kind=='box' for e in doc.entities.values())
    strips=[e for e in doc.entities.values() if e.kind=='electrical_point' and e.params['point_type']=='led_strip']
    assert len(strips)==8
    assert all(not e.params.get('lumens') and not e.params.get('watts_per_m') for e in strips)
