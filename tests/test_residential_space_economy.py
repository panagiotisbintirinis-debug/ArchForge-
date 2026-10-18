"""Owner-requested review changes: occupied space, storage and landing safety geometry."""
import pytest
from archforge.project.persistence import load_project
from archforge.architecture.stairs import candidate_from_params,stair_centerline,stair_wall_conflicts
from archforge.quantities.takeoff import take_off
from tests.test_stair_slab_opening import _covered
from tests.residential_scenarios.space_economy import opening_guard_lines

CASES=[('docs/scenarios/residential_review/S01_details/S01_space_economy.archforge','s01-stair','s01-room_floor-3',2.82),
 ('tests/residential_scenarios/S02_split_level_hillside_house.archforge','s02-stair-main','s02-floor-1',3.02)]


@pytest.mark.parametrize('path,sid,floor,underside',CASES)
def test_stair_is_not_a_closed_quarter_of_the_house(path,sid,floor,underside):
    loaded=load_project(path);assert loaded.ok;d=loaded.doc
    assert not any(r['name'] in ('Κλιμακοστάσιο','Διάδρομος') for r in take_off(d)['rooms'])
    c=candidate_from_params(d.get(sid).params)
    assert not stair_wall_conflicts(d,c)
    # The exit has usable floor all the way to the west approach; no hole or
    # upper guard across the last tread. This does not certify a legal width.
    end=stair_centerline(c)[-1]
    assert end[0]>.125+c.width
    assert _covered(d,d.get(floor),end[0]-.1,end[1])
    assert not _covered(d,d.get(floor),end[0]+.15,end[1])
    start=stair_centerline(c)[0]
    assert _covered(d,d.get(floor),start[0]+.1,start[1])
    objects=[e for e in d.entities.values() if e.parent_id==sid and e.kind=='cabinet' and e.params.get('under_stair')]
    assert objects and all(e.params['height_end']>e.params['height'] for e in objects)
    rails=[e for e in d.entities.values() if e.id.startswith(sid+'-opening-guard-')]
    assert rails and sum(len(e.params['points'])-1 for e in rails)==len(opening_guard_lines(d.get(sid),underside))
    assert all(e.params['z']==c.upper_z for e in rails)
