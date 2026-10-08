"""Stair plan symbol (Greek drafting practice): lower storey cut at ~1,10 m with «ΑΝ»,
upper storey opening + visible steps with «ΚΑΤ»; same layout as the 3D steps."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.stairs import (PLAN_CUT_HEIGHT, candidate_from_params, solve_stair_candidates,
                                           stair_cut_index, stair_plan_symbol, stair_treads)
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity, WorkPlane
from archforge.core.plan_scene import build_plan_frame
from archforge.geometry.mesh import _stair_mesh

LAYOUTS = [('straight', 1)] + [(layout, turn) for layout in ('l', 'u', 'spiral') for turn in (1, -1)]


def _candidate(layout, turn, angle=0.0):
    import math
    a = math.radians(angle)
    return next(c for c in solve_stair_candidates(0.0, 3.0, (1.0, 2.0), (1.0 + 4 * math.cos(a), 2.0 + 4 * math.sin(a)), width=1.0)
                if c.layout == layout and c.turn_direction == turn)


@pytest.mark.parametrize('layout,turn', LAYOUTS)
def test_lower_storey_cut_dashed_above_and_up_arrow(layout, turn):
    c = _candidate(layout, turn)
    lines, labels = stair_plan_symbol(c, 'lower')
    styles = [s for s, _ in lines]
    k = stair_cut_index(c)
    assert k * c.riser_height <= PLAN_CUT_HEIGHT + 1e-9 < (k + 1) * c.riser_height
    assert styles.count('cut') == 1 and 'arrow' in styles and 'walk' in styles and 'walk-hidden' in styles
    assert styles.count('tread') - (1 if layout == 'spiral' else 0) == k            # (spiral: + the newel)
    assert styles.count('hidden') >= c.tread_count - k
    assert 'opening' not in styles
    assert [t for t, _p, kind in labels if kind == 'direction'] == ['ΑΝ']


@pytest.mark.parametrize('layout,turn', LAYOUTS)
def test_upper_storey_opening_visible_steps_and_down_arrow(layout, turn):
    c = _candidate(layout, turn)
    lines, labels = stair_plan_symbol(c, 'upper')
    styles = [s for s, _ in lines]
    k = stair_cut_index(c)
    assert 'opening' in styles and 'arrow' in styles
    assert 'cut' not in styles and 'hidden' not in styles and 'walk-hidden' not in styles
    visible = styles.count('tread') - (1 if layout == 'spiral' else 0)
    assert 0 < visible <= c.tread_count - k
    assert [t for t, _p, kind in labels if kind == 'direction'] == ['ΚΑΤ']


@pytest.mark.parametrize('layout,turn', LAYOUTS)
def test_numbers_are_optional(layout, turn):
    c = _candidate(layout, turn)
    assert not [t for t, _p, kind in stair_plan_symbol(c, 'lower')[1] if kind == 'number']
    numbers = [t for t, _p, kind in stair_plan_symbol(c, 'lower', numbers=True)[1] if kind == 'number']
    assert numbers == [str(i + 1) for i in range(c.tread_count)]


@pytest.mark.parametrize('layout,turn', [q for q in LAYOUTS if q[0] != 'spiral'])
def test_plan_treads_are_the_3d_treads(layout, turn):
    c = _candidate(layout, turn, angle=30.0)
    mesh = _stair_mesh(c.to_params())
    tops = {(round(x, 6), round(y, 6), round(z, 6)) for x, y, z in mesh.vertices}
    treads, landings = stair_treads(c)
    assert len(treads) == c.tread_count
    for i, quad in treads:
        z = round(c.lower_z + (i + 1) * c.riser_height, 6)
        for x, y in quad:
            assert (round(x, 6), round(y, 6), z) in tops, (layout, i)
    for after, poly in landings:
        z = round(c.lower_z + (after + 1) * c.riser_height, 6)
        for x, y in poly:
            assert (round(x, 6), round(y, 6), z) in tops, (layout, 'landing')


def test_turning_stairs_flights_do_not_overlap_their_landing():
    for layout in ('l', 'u'):
        c = _candidate(layout, 1)
        treads, landings = stair_treads(c)
        (_a, land), = landings
        lx = sorted({round(p[0], 6) for p in land}); ly = sorted({round(p[1], 6) for p in land})
        for i, quad in treads:
            cx = sum(p[0] for p in quad) / 4; cy = sum(p[1] for p in quad) / 4
            assert not (lx[0] + 1e-6 < cx < lx[-1] - 1e-6 and ly[0] + 1e-6 < cy < ly[-1] - 1e-6), (layout, i)


def _doc_with_stair(layout='u'):
    doc = Document(); st = CommandStack(doc); doc.levels = {'Ισόγειο': 0.0, 'Όροφος 1': 3.0, 'Όροφος 2': 6.0}
    for z in (0.0, 3.0, 6.0):
        for x1, y1, x2, y2 in [(-2, -2, 8, -2), (8, -2, 8, 6), (8, 6, -2, 6), (-2, 6, -2, -2)]:
            st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': 2.7, 'thickness': .2})))
    stair = Entity('stair', _candidate(layout, 1).to_params())
    st.execute(AddEntity(stair))
    return doc, st, stair


@pytest.mark.parametrize('layout', ['straight', 'l', 'u', 'spiral'])
def test_plan_frame_draws_lower_and_upper_storey_once(layout):
    doc, _st, stair = _doc_with_stair(layout)
    for z, view, word in ((0.0, 'lower', 'ΑΝ'), (3.0, 'upper', 'ΚΑΤ')):
        doc.work_plane = WorkPlane(origin=(0.0, 0.0, z))
        prims = build_plan_frame(doc).primitives
        mine = [p for p in prims if p.entity_id == stair.id]
        assert sum(p.role == 'stair' for p in mine) == 1                       # one pick area, no duplicate outline
        assert {dict(p.meta).get('view') for p in mine if p.role.startswith('stair-') and p.kind == 'polyline'} == {view}
        assert [dict(p.meta)['text'] for p in mine if p.role == 'stair-label'] == [word]
        assert ('stair-cut' in {p.role for p in mine}) == (view == 'lower')
        assert ('stair-opening' in {p.role for p in mine}) == (view == 'upper')
        # The faint storey-below reference adds no copy of the stair.
        assert not [p for p in prims if p.role == 'floor-underlay' and p.entity_id]
    doc.work_plane = WorkPlane(origin=(0.0, 0.0, 6.0))
    assert not [p for p in build_plan_frame(doc).primitives if p.entity_id == stair.id]


def test_plan_numbers_setting_undo_and_round_trip():
    doc, st, stair = _doc_with_stair('straight')
    st.execute(UpdateEntity(stair.id, {'plan_numbers': 1}))
    doc.work_plane = WorkPlane(origin=(0.0, 0.0, 0.0))
    labels = [dict(p.meta)['text'] for p in build_plan_frame(doc).primitives if p.role == 'stair-label']
    assert 'ΑΝ' in labels and '1' in labels
    again = Document.from_dict(doc.to_dict())
    assert again.get(stair.id).params['plan_numbers'] == 1
    st.undo()
    assert not doc.get(stair.id).params.get('plan_numbers')
    with pytest.raises(ValueError):
        st.execute(UpdateEntity(stair.id, {'plan_numbers': 'όχι'}))
