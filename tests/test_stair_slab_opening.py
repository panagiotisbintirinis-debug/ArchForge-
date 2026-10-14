"""Owner (2026-10-14): the slab over a stair must be open wherever there is not enough height to walk
under it — and only there: in small houses the upper space is used, and under the stair go cupboards.

Walk-through / UX report: the plate the Assistant puts over the ground floor (2.70–2.90) was not cut by
the stair at all (only slabs at the storey level were), so the stair ran into concrete.
"""
import copy
from types import SimpleNamespace

import pytest

import archforge.architecture.storey_slabs as S
from archforge.core.commands import AddEntity, CommandStack, CreateFloorLevel, SetWorkPlane
from archforge.core.interaction import StairPlaceTransaction
from archforge.core.model import Document, Entity
from archforge.geometry.mesh import _payload


def _walls(stack, z):
    for (x1, y1), (x2, y2) in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0))):
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z,
                                                'height': 2.7, 'thickness': 0.2})))


def _covered(doc, e, x, y):
    m = _payload(doc, SimpleNamespace(semantic_kind=e.kind, params=e.params, entity_id=e.id, transform=None))
    V = m.vertices; top = max(v[2] for v in V)
    def side(p, a, b):
        return (p[0] - b[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (p[1] - b[1])
    for t in m.triangles:
        a, b, c = (V[i] for i in t)
        if all(abs(v[2] - top) < 1e-6 for v in (a, b, c)):
            d = (side((x, y), a, b), side((x, y), b, c), side((x, y), c, a))
            if not (min(d) < 0 < max(d)):
                return True
    return False


@pytest.fixture
def house():
    doc = Document(); stack = CommandStack(doc)
    _walls(stack, 0.0); _walls(stack, 3.0)
    plane = copy.deepcopy(doc.work_plane)
    stack.execute(CreateFloorLevel('Floor 2', 3.0)); stack.execute(SetWorkPlane(plane))
    tx = StairPlaceTransaction(doc, stack, (1.0, 1.5), layout='straight')
    tx.update(9.0, 1.5)
    stair = doc.get(tx.commit()).params
    assert stair['layout'] == 'straight' and abs(stair['angle_deg']) < 1e-6
    stack.execute(S.missing_storey_slabs_command(doc))
    return doc, stair


def test_every_slab_the_stair_passes_is_open_over_its_upper_part(house):
    doc, st = house
    run = (st['riser_count'] - 1) * st['tread_depth']
    x_top = st['x'] + run - 0.3                       # last steps: a person's head is in the slab
    between = [e for e in doc.entities.values() if e.kind in ('room_floor', 'room_roof')
               and e.params.get('scope') == 'storey' and float(e.params['level_z']) in (0.0, 3.0)
               and not (e.kind == 'room_floor' and float(e.params['level_z']) == 0.0)
               and not (e.kind == 'room_roof' and float(e.params['level_z']) == 3.0)]
    assert len(between) == 2                          # ground «plate over» and upper floor slab
    for slab in between:
        assert not _covered(doc, slab, x_top, st['y']), slab.kind


def test_the_slab_stays_where_there_is_headroom_under_it(house):
    doc, st = house
    x_low = st['x'] + 0.3                            # first steps: more than 2 m under the slab
    for slab in (e for e in doc.entities.values() if e.kind in ('room_floor', 'room_roof') and e.params.get('scope') == 'storey'):
        assert _covered(doc, slab, x_low, st['y']), (slab.kind, slab.params['level_z'])
