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


def _south_facade_has_surface(meshes,x,z):
    def side(p,a,b):
        return (p[0]-b[0])*(a[1]-b[1])-(a[0]-b[0])*(p[1]-b[1])
    for mesh in meshes:
        for tri in mesh.triangles:
            pts=[mesh.vertices[i] for i in tri]
            if not all(abs(p[1]+.125)<1e-6 for p in pts):continue
            a,b,c=[(p[0],p[2]) for p in pts]
            if abs(side(a,b,c))<1e-10:continue
            d=[side((x,z),a,b),side((x,z),b,c),side((x,z),c,a)]
            if not (min(d)<-1e-8 and max(d)>1e-8):return True
    return False


@pytest.mark.parametrize('spec',SPECS,ids=lambda s:s['id'])
def test_actual_facade_mesh_has_no_open_band_at_upper_floor(spec):
    from types import SimpleNamespace
    from archforge.geometry.mesh import _payload
    loaded=load_project(ROOT/spec['file']);assert loaded.ok
    doc=loaded.doc
    meshes=[_payload(doc,SimpleNamespace(semantic_kind=e.kind,params=e.params,entity_id=e.id,transform=None))
            for e in doc.entities.values() if e.kind in ('wall','floor','room_floor','room_roof')]
    z=0.
    for h in spec['levels'][:-1]:
        z=round(z+h,3)
        for x in (1.,3.,5.,7.):
            # Physical facade triangles, independently of colour/material.
            for k in range(61):
                sample=z-.3+.3*k/60
                assert _south_facade_has_surface(meshes,x,sample),(spec['id'],x,sample)


def test_a_finish_does_not_make_a_real_empty_band_pass_the_mesh_check():
    from types import SimpleNamespace
    from archforge.geometry.mesh import _payload
    from tests.residential_scenarios.facade_finish import finish_facade_joints
    from archforge.core.commands import CommandStack,UpdateEntity
    spec=next(s for s in SPECS if s['id']=='S10')
    d=load_project(ROOT/spec['file']).doc;stack=CommandStack(d)
    stack.execute(UpdateEntity('s10-wall-0-0',{'height':2.8}))
    finish_facade_joints(d,stack)
    meshes=[_payload(d,SimpleNamespace(semantic_kind=e.kind,params=e.params,entity_id=e.id,transform=None))
            for e in d.entities.values() if e.kind in ('wall','floor','room_floor','room_roof')]
    assert not _south_facade_has_surface(meshes,1.,2.86)
