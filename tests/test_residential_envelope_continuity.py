"""Delivered review fixtures: walls meet actual floors/eaves without empty bands.

This is a geometry contract, not an engineering thickness or sizing rule.
S01 has its own canonical-slab checks; S02-S10 currently carry polygon floors.
"""
import json
from pathlib import Path
import pytest
from archforge.project.persistence import load_project
from tests.residential_scenarios.generate_projects import build_project

ROOT = Path(__file__).parent / 'residential_scenarios'
SPECS = json.loads((ROOT/'manifest.json').read_text())[1:]


def assert_continuous(data, spec):
    prefix=spec['id'].lower()
    entities={e['id']:e for e in data['entities']}
    roof=entities[prefix+'-roof']['params']
    levels=[0.0]
    for h in spec['levels'][:-1]: levels.append(round(levels[-1]+h,3))
    for k,z in enumerate(levels):
        if k+1<len(levels):
            floor=entities[f'{prefix}-floor-{k+1}'];fp=floor['params']
            target=(fp['level_z']+fp.get('offset_z',0)-fp['thickness'] if floor['kind']=='room_floor' else fp['z'])
        else:target=roof['eave_z']
        ids=[f'{prefix}-wall-{k}-{j}' for j in range(4)]
        ids += [eid for eid,e in entities.items() if e['kind']=='wall' and eid.startswith(prefix+'-part-') and e['params']['z']==z]
        for eid in ids:
            p=entities[eid]['params']
            assert p['z']+p['height']==pytest.approx(target), f'{eid}: empty wall/floor or wall/eave band'


@pytest.mark.parametrize('spec',SPECS,ids=lambda s:s['id'])
def test_delivered_fixture_has_no_empty_storey_band(spec):
    loaded=load_project(ROOT/spec['file']);assert loaded.ok,loaded.message()
    assert_continuous(loaded.doc.to_dict(),spec)


@pytest.mark.parametrize('spec',SPECS,ids=lambda s:s['id'])
def test_generator_does_not_reintroduce_empty_storey_band(spec):
    assert_continuous(build_project(spec),spec)

@pytest.mark.parametrize('spec',SPECS,ids=lambda s:s['id'])
def test_floor_plate_reaches_external_wall_faces(spec):
    loaded=load_project(ROOT/spec['file']);assert loaded.ok
    doc=loaded.doc;prefix=spec['id'].lower()
    for k in range(spec['storeys']):
        floor=doc.get(f'{prefix}-floor-{k}')
        if floor.kind=='room_floor':
            from archforge.architecture.rooms import room_slab_geometry
            points=room_slab_geometry(doc,floor)['points']
        else:points=floor.params['points']
        walls=[doc.get(f'{prefix}-wall-{k}-{j}').params for j in range(4)]
        xs=[p[a] for p in walls for a in ('x1','x2')];ys=[p[a] for p in walls for a in ('y1','y2')]
        half=max(p['thickness'] for p in walls)/2
        assert min(q[0] for q in points)<=min(xs)-half+1e-6
        assert max(q[0] for q in points)>=max(xs)+half-1e-6
        assert min(q[1] for q in points)<=min(ys)-half+1e-6
        assert max(q[1] for q in points)>=max(ys)+half-1e-6
