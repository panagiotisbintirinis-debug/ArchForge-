"""Railings (κάγκελα): balconies, terraces and stairs as one parametric entity."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.railings import (DEFAULT_HEIGHT, MAX_GAP, STAIR_HEIGHT, TYPES, default_params, length,
                                             max_clear_gap, post_positions, railing_mesh, stair_railing_lines,
                                             stair_railings)
from archforge.core.commands import AddEntity, CommandStack, MoveEntities, RotateEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh

SHAPES = {'straight': [[0, 0], [3, 0]], 'L': [[0, 0], [3, 0], [3, 2]], 'U': [[0, 0], [3, 0], [3, 2], [0, 2]]}


def _stair(layout='straight'):
    return {'x': 0.0, 'y': 0.0, 'lower_z': 0.0, 'upper_z': 2.89, 'upper_floor_z': 2.89, 'upper_slab_thickness': 0.0,
            'layout': layout, 'angle_deg': 0.0, 'width': 1.0, 'riser_count': 17, 'riser_height': 0.17,
            'tread_depth': 0.28, 'landing_depth': 1.0, 'turn_direction': 1, 'opening_margin': 0.05}


@pytest.mark.parametrize('kind', list(TYPES))
@pytest.mark.parametrize('shape', list(SHAPES))
def test_every_type_and_shape_is_closed_and_within_its_bounds(kind, shape):
    pts = SHAPES[shape]
    p = default_params(kind, pts)
    Document().add(Entity('railing', p))                      # the schema accepts the defaults
    verts, tris, roles = railing_mesh(p)
    assert validate_mesh(MeshPayload(verts, tris, roles)).watertight
    zs = [v[2] for v in verts]
    assert max(zs) == pytest.approx(DEFAULT_HEIGHT)            # top of the handrail at 1.00 m
    assert min(zs) >= (-0.10 - 1e-9 if kind == 'glass_channel' else -1e-9)   # recessed profile only
    half = 0.15
    for i in (0, 1):
        lo, hi = min(q[i] for q in pts), max(q[i] for q in pts)
        assert lo - half <= min(v[i] for v in verts) and max(v[i] for v in verts) <= hi + half
    assert set(roles) <= {'handrail', 'post', 'infill', 'glass', 'base'}
    if kind.startswith('glass'):
        assert 'glass' in roles


@pytest.mark.parametrize('kind', [k for k, v in TYPES.items() if v['post']])
def test_posts_at_every_end_and_corner_and_never_further_apart_than_allowed(kind):
    pts = SHAPES['U']
    p = default_params(kind, pts, post_spacing=1.2)
    posts = [(x, y) for x, y, *_ in post_positions(p)]
    for q in pts:
        assert any(math.hypot(x - q[0], y - q[1]) < 1e-9 for x, y in posts)
    assert len(posts) == len(set((round(x, 6), round(y, 6)) for x, y in posts))       # no doubled corner posts
    # Along each side the posts are at most post_spacing apart.
    for a, b in zip(pts, pts[1:]):
        on = sorted(math.hypot(x - a[0], y - a[1]) for x, y in posts
                    if abs((b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0])) < 1e-9
                    and min(a[0], b[0]) - 1e-9 <= x <= max(a[0], b[0]) + 1e-9 and min(a[1], b[1]) - 1e-9 <= y <= max(a[1], b[1]) + 1e-9)
        assert max(s1 - s0 for s0, s1 in zip(on, on[1:])) <= 1.2 + 1e-9
    closed = default_params(kind, pts, closed=1)
    assert len(post_positions(closed)) == len(posts) + 1       # the closing side has its own bays, same corner posts


@pytest.mark.parametrize('kind', ['balusters', 'timber', 'bars', 'cable'])
@pytest.mark.parametrize('gap', [0.06, 0.10, 0.11])
def test_clear_gap_of_the_infill_never_exceeds_the_limit(kind, gap):
    for pts in list(SHAPES.values()) + [[[0, 0, 0.17], [2.8, 0, 1.87]]]:
        p = default_params(kind, pts, gap=gap)
        assert 0 < max_clear_gap(p) <= gap + 1e-9 <= MAX_GAP + 1e-9


def test_schema_rejects_what_is_not_a_railing():
    doc = Document()
    good = default_params('balusters', SHAPES['L'])
    for bad in ({'points': [[0, 0]]},                                # fewer than two points
                {'points': [[0, 0], [0.005, 0]]},                    # zero-length side
                {'points': [[0, 0], [2, 0], [0, 0.05]]},             # folds back on itself
                {'height': 0.0}, {'height': -1.0},
                {'gap': 0.15},                                       # a child's head would pass
                {'post_spacing': 2.5},
                {'railing_type': 'spaceship'}, {'handrail': 'twisted'}, {'metal': 'gold'},
                {'closed': 1, 'points': [[0, 0], [1, 0]]},
                {'base_height': 0.9}):
        with pytest.raises(ValueError):
            doc.add(Entity('railing', dict(good, **bad)))
    with pytest.raises(ValueError):
        doc.add(Entity('railing', {'points': [[0, 0], [1, 0]], 'z': 0.0}))     # no type / height
    doc.add(Entity('railing', good))


def test_stair_railing_follows_the_nosing_line_at_90cm():
    sp = _stair('straight')
    (left,), (right,) = stair_railing_lines(sp, 'left'), stair_railing_lines(sp, 'right')
    assert len(left) == 2                                             # one straight slope
    (x0, y0, z0), (x1, y1, z1) = left
    assert (x0, z0) == pytest.approx((0.0, 0.17)) and (x1, z1) == pytest.approx((16 * 0.28, 2.89))
    assert y0 == pytest.approx(0.53) and right[0][1] == pytest.approx(-0.53)
    doc = Document()
    stair = Entity('stair', sp)
    doc.add(stair)
    params = stair_railings(doc, stair)
    assert len(params) == 2 and all(p['height'] == STAIR_HEIGHT for p in params)
    verts, tris, roles = railing_mesh(params[0])
    assert validate_mesh(MeshPayload(verts, tris, roles)).watertight
    # Handrail top 0.90 m above the nosing line all the way up.
    top = max(v[2] for v in verts if v[0] < 0.05)
    assert top == pytest.approx(0.17 + 0.90, abs=0.03)
    assert max(v[2] for v in verts) == pytest.approx(2.89 + 0.90)
    assert length(params[0]) == pytest.approx(math.hypot(16 * 0.28, 2.72))
    # A side along a wall gets no railing.
    doc.add(Entity('wall', {'x1': -0.5, 'y1': 0.65, 'x2': 5.0, 'y2': 0.65, 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    assert len(stair_railings(doc, stair)) == 1


@pytest.mark.parametrize('layout', ['l', 'u'])
def test_turning_stairs_get_one_railing_per_flight_and_side(layout):
    doc = Document()
    stair = Entity('stair', _stair(layout))
    doc.add(stair)
    params = stair_railings(doc, stair)
    assert len(params) == 4
    for p in params:
        doc.add(Entity('railing', p))
        assert validate_mesh(MeshPayload(*railing_mesh(p))).watertight
    tops = sorted(max(float(q[2]) for q in p['points']) for p in params)
    assert tops[-1] == pytest.approx(2.89)
    with pytest.raises(ValueError, match='σπιράλ'):
        stair_railings(doc, Entity('stair', _stair('spiral')))


def test_plan_symbol_on_its_storey_and_scene_materials_per_role():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.materials import MATERIAL_PRESETS
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc)
    glass = Entity('railing', default_params('glass_posts', SHAPES['L']))
    upper = Entity('railing', default_params('balusters', SHAPES['straight'], z=3.0))
    loop = Entity('railing', default_params('cable', SHAPES['U'], closed=1))
    for e in (glass, upper, loop):
        stack.execute(AddEntity(e))
    prims = build_plan_frame(doc).primitives
    mine = [p for p in prims if p.entity_id == glass.id]
    assert [p.kind for p in mine if p.role == 'railing'] == ['polygon']
    assert len([p for p in mine if p.role == 'railing-post']) == len(post_positions(glass.params))
    assert len([p for p in prims if p.entity_id == loop.id and p.role == 'railing']) == 2    # two rings
    assert not any(p.entity_id == upper.id for p in prims)             # another storey
    mid = next(iter(MATERIAL_PRESETS))
    stack.execute(UpdateEntity(glass.id, {'surface_materials': {'handrail': mid}}))
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    parts = {o['render_part'].split(':')[1]: o['material'] for o in objs if o['id'] == glass.id}
    assert set(parts) == {'handrail', 'post', 'glass'}
    assert parts['handrail']['color'] == MATERIAL_PRESETS[mid]['color']
    assert parts['glass']['opacity'] < 1.0 and parts['post']['metalness'] > 0.5          # inox posts


def test_add_undo_redo_move_rotate_and_save_load_round_trip():
    doc = Document(); stack = CommandStack(doc)
    r = Entity('railing', default_params('timber', SHAPES['L']), name='Ξύλινο')
    stack.execute(AddEntity(r))
    stack.execute(UpdateEntity(r.id, {'height': 1.10, 'gap': 0.09}))
    assert doc.get(r.id).params['height'] == pytest.approx(1.10)
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(r.id, {'gap': 0.2}))
    assert doc.get(r.id).params['gap'] == pytest.approx(0.09)
    stack.execute(MoveEntities([r.id], 1.0, 2.0))
    assert doc.get(r.id).params['points'][0][:2] == pytest.approx([1.0, 2.0])
    stack.execute(RotateEntities([r.id], 90.0, pivot=(1.0, 2.0)))
    assert doc.get(r.id).params['points'][1][:2] == pytest.approx([1.0, 5.0])
    for _ in range(3):
        stack.undo()
    assert doc.get(r.id).params['height'] == pytest.approx(DEFAULT_HEIGHT) and doc.get(r.id).params['points'][0] == [0.0, 0.0]
    stack.undo()
    assert r.id not in doc.entities
    stack.redo(); stack.redo()
    saved = doc.to_dict()
    again = Document.from_dict(saved)
    assert again.get(r.id).params == doc.get(r.id).params and again.get(r.id).name == 'Ξύλινο'
    assert railing_mesh(again.get(r.id).params) == railing_mesh(doc.get(r.id).params)


def test_railings_in_the_priced_material_list():
    from archforge.quantities.materials import all_lists, railing_list
    doc = Document()
    doc.add(Entity('railing', default_params('balusters', SHAPES['U'])))
    doc.add(Entity('railing', default_params('balusters', [[10, 0], [12, 0]])))
    doc.add(Entity('railing', default_params('glass_channel', SHAPES['straight'])))
    rows = railing_list(doc)
    assert ('m', 10.0) in [(u, q) for d, u, q in rows if 'κάθετα' in d]
    assert ('m', 3.0) in [(u, q) for d, u, q in rows if 'τζάμι' in d]
    assert 'Κάγκελα' in [s[0] for s in all_lists(doc)]


def test_draft_tool_clicks_corners_and_closes_on_the_first_point():
    from archforge.ui.railing_draft import RailingDraft
    d = RailingDraft()
    d.add(0.0, 0.0); d.add(3.004, 0.2, ortho=True); d.add(3.0, 3.0); d.add(3.0, 3.0)     # last = double click
    assert d.finish() == ([[0.0, 0.0], [3.0, 0.0], [3.0, 3.0]], False)
    assert d.add(0.05, 0.05) is True and d.finish()[1] is True


def test_menu_tool_draws_a_railing_in_one_undo_and_the_library_lists_presets():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        labels = [a.text() for a in window._mockup_railing_menu.actions() if a.text()]
        assert labels[:len(TYPES)] == [v['label'] for v in TYPES.values()] and 'σκάλας' in labels[-1]
        window._mockup_railing_menu.actions()[0].trigger()
        assert window.plan_view.controller.tool == 'railing_balusters'
        n = len(window.stack.done)
        window.plan_view.railingRequested.emit('railing_balusters', [[0.0, 0.0], [3.0, 0.0], [3.0, 2.0]], False)
        rails = [e for e in window.doc.entities.values() if e.kind == 'railing']
        assert len(rails) == 1 and len(window.stack.done) == n + 1
        window.refresh_inspector()          # Greek rows, no crash
        window.stack.undo()
        assert not any(e.kind == 'railing' for e in window.doc.entities.values())
        outline = dict(window._library_outline())
        assert 'Κάγκελα' in dict(outline['Δομικά'])
        window.stack.execute(AddEntity(Entity('stair', _stair('straight'))))
        window._place_site_point('railingstair_balusters', 2.0, 0.0)
        assert sum(e.kind == 'railing' for e in window.doc.entities.values()) == 2
    finally:
        window._mark_clean(); window.close(); app.processEvents()
