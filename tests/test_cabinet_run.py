"""«Γραμμή ντουλαπιών» (K4): a wall filled with standard cabinets, filler, worktop, one undo, re-flow."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.kitchen import cabinet_run as cr
from archforge.kitchen.cabinets import _overlap, cabinet_mesh, footprint


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))


def _room(W, H, door=None, window=None):
    """Room of 0.20 walls on the axes 0..W, 0..H (inside faces at 0.10 and W-0.10)."""
    doc = Document(); st = CommandStack(doc); ids = []
    for x1, y1, x2, y2 in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
        e = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
        st.execute(AddEntity(e)); ids.append(e.id)
    if door:
        st.execute(AddEntity(Entity('door', {'offset': door[1], 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=ids[door[0]])))
    if window:
        st.execute(AddEntity(Entity('window', {'offset': window[1], 'width': window[2], 'height': 1.2, 'sill': window[3] if len(window) > 3 else 1.0},
                                    parent_id=ids[window[0]])))
    return doc, st, ids


def _apply(doc, st, prop):
    assert prop.entities, prop.problems
    st.execute(prop.command())
    return prop


def _pieces(doc, run_id, layer):
    out = []
    for e in cr.run_members(doc, run_id):
        p = e.params
        if p['run_seg']['layer'] != layer:
            continue
        s, _d = cr.frame_coords(p['run_seg']['frame'], p['x'], p['y'])
        out.append((round(s - p['width'] / 2, 4), round(s + p['width'] / 2, 4), p['cabinet_type'], e))
    return sorted(out, key=lambda t: t[0])


def _contiguous(pieces):
    for a, b in zip(pieces, pieces[1:]):
        assert abs(a[1] - b[0]) < 1e-6, (a[:3], b[:3])


def test_fill_widths_uses_standard_sizes_and_a_small_filler():
    assert cr.exact_widths(3.60) == [0.6] * 6
    widths, filler = cr.fill_widths(3.63)
    assert sum(widths) == pytest.approx(3.60) and filler == pytest.approx(0.03)
    assert all(w in cr.STANDARD_WIDTHS for w in widths)
    widths, filler = cr.fill_widths(3.60, min_filler=0.03)          # against a wall: at least 3 cm
    assert filler >= 0.03 - 1e-9 and filler < 0.30
    for L in [x / 100 for x in range(80, 700, 7)]:
        widths, filler = cr.fill_widths(L)
        assert 0 <= filler < cr.STANDARD_WIDTHS[0], L                  # never a gap a cabinet would fill
        assert sum(widths) + filler == pytest.approx(L)


def test_exact_stretch_of_a_wall_is_filled_without_filler():
    doc, st, _ids = _room(5.2, 3.0)
    # Two clicks on the bottom face (y = 0.10): from s = 0.80 to s = 4.40 → 3,60 m, free ends.
    prop = cr.plan_run(doc, 0.90, 0.10, 4.50, 0.10, {'sink': False, 'hob': False, 'wall_units': False})
    _apply(doc, st, prop)
    base = _pieces(doc, prop.run_id, 'base')
    assert [p[2] for p in base] == ['base'] * 6
    assert all(float(p[3].params['width']) == pytest.approx(0.60) for p in base)
    assert base[0][0] == pytest.approx(0.80) and base[-1][1] == pytest.approx(4.40)
    _contiguous(base)


def test_whole_wall_leftover_goes_to_one_filler_at_the_corner_end():
    doc, st, _ids = _room(4.0, 3.0)                       # inner face 3,80 m between two walls
    prop = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15, options={'sink': False, 'hob': False}))
    base = _pieces(doc, prop.run_id, 'base')
    _contiguous(base)
    assert base[0][0] == pytest.approx(0.0) and base[-1][1] == pytest.approx(3.80)
    fillers = [p for p in base if p[2] == 'filler']
    assert len(fillers) == 1 and fillers[0] in (base[0], base[-1])        # at an end (a corner), not in the middle
    w = float(fillers[0][3].params['width'])
    assert cr.WALL_FILLER - 1e-9 <= w < 0.30
    assert all(float(p[3].params['width']) in cr.STANDARD_WIDTHS for p in base if p[2] != 'filler')
    # Worktop at ≈ 90 cm, base 60 deep, wall units 35 deep from 1,45.
    g = cr.run_geometry(doc)
    (top,) = g['worktops']
    assert top[1] == pytest.approx(0.0) and top[2] == pytest.approx(3.80)
    assert top[5] == pytest.approx(0.86) and top[6] == pytest.approx(0.90)
    walls = _pieces(doc, prop.run_id, 'wall')
    assert walls and all(p[3].params['z'] == pytest.approx(1.45) and p[3].params['depth'] == pytest.approx(0.35) for p in walls)


def test_window_no_wall_units_in_front_and_sink_under_it():
    doc, st, _ids = _room(4.0, 3.0, window=(0, 2.0, 1.2))          # window centred at x = 2.0 (s 1.30..2.50)
    prop = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15))
    walls = _pieces(doc, prop.run_id, 'wall')
    for s0, s1, _t, _e in walls:
        assert s1 <= 1.30 - 0.05 + 1e-6 or s0 >= 2.50 + 0.05 - 1e-6, (s0, s1)
    sink = [p for p in _pieces(doc, prop.run_id, 'base') if p[3].params['run_role'] == 'sink']
    assert len(sink) == 1 and abs((sink[0][0] + sink[0][1]) / 2 - 1.90) <= 0.05 + 1e-6
    assert any('παράθυρο' in n for n in prop.notes)


def test_low_window_stops_the_base_run():
    doc, st, _ids = _room(4.0, 3.0, window=(0, 2.0, 1.0, 0.60))       # sill 60 cm, under the worktop
    prop = _apply(doc, st, cr.plan_run(doc, 0.6, 0.15, options={'sink': False, 'hob': False}))
    for s0, s1, _t, _e in _pieces(doc, prop.run_id, 'base'):
        assert s1 <= 1.40 + 1e-6 or s0 >= 2.40 - 1e-6


def test_door_splits_the_run_and_nothing_crosses_it():
    doc, st, _ids = _room(5.0, 3.0, door=(0, 2.5))                   # door s 1.95..2.85 on the bottom face
    prop = _apply(doc, st, cr.plan_run(doc, 1.0, 0.15, options={'sink': False, 'hob': False}))
    for layer in ('base', 'wall'):
        pieces = _pieces(doc, prop.run_id, layer)
        assert any(p[1] <= 1.95 for p in pieces) and any(p[0] >= 2.85 for p in pieces)
        for s0, s1, _t, _e in pieces:
            assert s1 <= 1.95 - cr.DOOR_MARGIN + 1e-6 or s0 >= 2.85 + cr.DOOR_MARGIN - 1e-6, (layer, s0, s1)
    assert len(cr.run_geometry(doc)['worktops']) == 2               # two worktops, one each side


def test_l_corner_with_an_existing_run_gets_a_blind_corner_and_no_overlaps():
    doc, st, _ids = _room(4.0, 3.0, window=(0, 1.5, 1.0))
    first = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15))                  # bottom wall: sink + hob
    second = _apply(doc, st, cr.plan_run(doc, 3.85, 1.5))                 # right wall, meets it at the corner
    assert first.run_id != second.run_id and second.replace_ids         # the first run re-planned …
    blind = [e for e in cr.run_members(doc, first.run_id) if e.params['cabinet_type'] == 'corner_blind']
    assert len(blind) == 1 and blind[0].params['blind_side'] == 'left'   # … with a blind unit in the corner
    b0, b1 = cr._iv(blind[0], blind[0].params['run_seg']['frame'])
    assert b1 == pytest.approx(3.80)
    right = _pieces(doc, second.run_id, 'base')
    assert right[0][0] == pytest.approx(0.60) and right[0][2] == 'filler'     # beside it, a filler of ≥ 5 cm
    assert float(right[0][3].params['width']) >= cr.RUN_FILLER - 1e-9
    cabs = [e for e in doc.entities.values() if e.kind == 'cabinet']
    for i, a in enumerate(cabs):
        for b in cabs[i + 1:]:
            if (a.params['run_seg']['layer'] == b.params['run_seg']['layer']):
                assert not _overlap(footprint(a.params), footprint(b.params)), (a.name, b.name)
    roles = [e.params['run_role'] for e in cabs]
    assert roles.count('sink') == 1 and roles.count('hob') == 1          # one sink, one hob for the kitchen
    # Inside the room.
    for e in cabs:
        for x, y in footprint(e.params):
            assert 0.1 - 1e-6 <= x <= 3.9 + 1e-6 and 0.1 - 1e-6 <= y <= 2.9 + 1e-6


def test_l_corner_unit_option():
    doc, st, _ids = _room(4.0, 3.0)
    prop = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15, options={'corner': 'L', 'sink': False, 'hob': False}))
    corner = [e for e in cr.run_members(doc, prop.run_id) if e.params['cabinet_type'] == 'corner']
    assert len(corner) == 1
    xs = [x for x, _y in footprint(corner[0].params)]; ys = [y for _x, y in footprint(corner[0].params)]
    assert max(xs) == pytest.approx(3.90) and min(ys) == pytest.approx(0.10)       # in the corner
    second = _apply(doc, st, cr.plan_run(doc, 3.85, 1.5, options={'sink': False, 'hob': False}))
    right = _pieces(doc, second.run_id, 'base')
    assert right[0][0] >= 0.90 - 1e-6                                  # the right wall starts after the L leg
    assert cr.run_geometry(doc)['corner_tops']


def test_worktop_cut_outs_for_sink_and_hob_with_clearances():
    doc, st, _ids = _room(4.5, 3.0)
    prop = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15, options={'wall_units': False}))
    g = cr.run_geometry(doc)
    (top,) = g['worktops']
    holes = top[8]
    assert sorted(h[0] for h in holes) == ['hob', 'sink']
    depth = cr.BASE_DEPTH + cr.WORKTOP_OVERHANG
    for kind, h0, h1, d0, d1 in holes:
        assert d0 >= cr.CUT_MARGIN - 1e-9 and depth - d1 >= cr.CUT_MARGIN - 1e-9     # from the wall and the front
        assert h0 - top[1] >= 0.30 - 1e-9 and top[2] - h1 >= 0.30 - 1e-9           # not at the corner
    sink = next(h for h in holes if h[0] == 'sink'); hob = next(h for h in holes if h[0] == 'hob')
    gap = max(hob[1] - sink[2], sink[1] - hob[2])
    assert gap >= cr.SINK_HOB - 1e-6
    # Strips around the holes cover exactly the worktop minus the holes.
    area = sum((b - a) * (d1 - d0) for a, b, d0, d1 in cr.worktop_boxes(top))
    hole_area = sum((h1 - h0) * (d1 - d0) for _k, h0, h1, d0, d1 in holes)
    assert area == pytest.approx((top[2] - top[1]) * depth - hole_area)
    roles = [r for r, _pts, _c in cr.plan_primitives(doc)]
    assert roles.count('worktop-cutout') == 2 and 'hob-symbol' in roles and 'sink-symbol' in roles


def test_sink_and_hob_where_the_user_says():
    doc, st, _ids = _room(5.0, 3.0)
    prop = cr.plan_run(doc, 2.0, 0.15, options={'sink_xy': [4.0, 0.4], 'hob_xy': [1.2, 0.4]})
    roles = {e.params['run_role']: cr.frame_coords(e.params['run_seg']['frame'], e.params['x'], e.params['y'])[0]
             for e in prop.entities}
    assert abs(roles['sink'] - 3.90) <= 0.05 + 1e-6
    assert abs(roles['hob'] - 1.10) <= 0.05 + 1e-6


def test_undo_restores_everything_and_redo_brings_it_back():
    doc, st, _ids = _room(4.0, 3.0, window=(0, 1.5, 1.0))
    st.execute(cr.plan_run(doc, 2.0, 0.15).command())
    before = doc.to_dict()
    n0 = len(doc.entities)
    st.execute(cr.plan_run(doc, 3.85, 1.5).command())          # also re-plans the first run (blind corner)
    assert len(doc.entities) > n0
    st.undo()
    key = lambda d: sorted(d['entities'], key=lambda e: e['id'])
    assert key(doc.to_dict()) == key(before)
    st.undo()
    assert not any(e.kind == 'cabinet' for e in doc.entities.values())
    assert cr.run_geometry(doc)['worktops'] == []
    st.redo(); st.redo()
    assert len({e.params['run_id'] for e in doc.entities.values() if e.kind == 'cabinet'}) == 2


def test_width_change_reflows_the_filler_and_is_one_undo():
    doc, st, _ids = _room(4.0, 3.0)
    prop = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15, options={'sink': False, 'hob': False, 'wall_units': False}))
    base = _pieces(doc, prop.run_id, 'base')
    total = base[-1][1] - base[0][0]
    target = next(p[3] for p in base if p[2] == 'base' and float(p[3].params['width']) == pytest.approx(0.60))
    st.execute(cr.reflow_width(doc, target.id, 0.45))
    after = _pieces(doc, prop.run_id, 'base')
    _contiguous(after)
    assert after[-1][1] - after[0][0] == pytest.approx(total)          # the run still fills the wall
    assert doc.get(target.id).params['width'] == pytest.approx(0.45)
    fillers = [p for p in after if p[2] == 'filler']
    assert len(fillers) == 1 and float(fillers[0][3].params['width']) < 0.30
    # A wider cabinet: the others step down / the filler shrinks, still exactly the wall.
    st.execute(cr.reflow_width(doc, target.id, 0.90))
    after = _pieces(doc, prop.run_id, 'base')
    _contiguous(after)
    assert after[-1][1] - after[0][0] == pytest.approx(total)
    st.undo(); st.undo()
    assert [round(float(p[3].params['width']), 3) for p in _pieces(doc, prop.run_id, 'base')] == \
        [round(float(p[3].params['width']), 3) for p in base]


def test_delete_updates_the_derived_worktop():
    doc, st, _ids = _room(4.0, 3.0)
    prop = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15, options={'sink': False, 'hob': False, 'wall_units': False}))
    from archforge.core.commands import DeleteEntities
    base = _pieces(doc, prop.run_id, 'base')
    st.execute(DeleteEntities([base[-1][3].id, base[-2][3].id]))      # the two at the end
    (top,) = cr.run_geometry(doc)['worktops']
    assert top[2] == pytest.approx(base[-3][1])
    st.execute(DeleteEntities([e.id for e in cr.run_members(doc, prop.run_id)]))
    assert cr.run_geometry(doc)['worktops'] == [] and cr.scene_objects(doc) == []


def test_filler_and_run_cabinets_build_closed_meshes_without_own_worktop():
    doc, st, _ids = _room(4.0, 3.0)
    prop = cr.plan_run(doc, 2.0, 0.15, options={'cornice': True})
    for e in prop.entities:
        verts, tris, roles = cabinet_mesh(e.params)
        assert tris
        if e.params['cabinet_type'] != 'corner':
            assert 'worktop' not in roles and 'plinth' not in roles      # the run derives them


def test_plan_and_3d_show_the_derived_parts_and_quantities_list_them():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.quantities.materials import kitchen_list
    from archforge.rendering.scene import build_pbr_scene_payload
    doc, st, _ids = _room(4.0, 3.0, window=(0, 1.5, 1.0))
    _apply(doc, st, cr.plan_run(doc, 2.0, 0.15, options={'cornice': True}))
    _apply(doc, st, cr.plan_run(doc, 3.85, 1.5))
    roles = {p.role for p in build_plan_frame(doc).primitives}
    assert {'worktop', 'worktop-cutout', 'sink-symbol', 'hob-symbol', 'cabinet', 'cabinet-wall'} <= roles
    objs = cr.scene_objects(doc)
    parts = {o['render_part'] for o in objs}
    assert {'run:worktop0', 'run:plinth', 'run:sinks', 'run:hobs', 'run:hoods', 'run:cornice0'} <= parts
    top = next(o for o in objs if o['render_part'] == 'run:worktop0')
    assert top['material']['material_id'] == 'marble_thassos' and top['material']['pattern']['joint'] == 0.0
    for o in objs:
        n = len(o['vertices'])
        assert all(0 <= i < n for t in o['triangles'] for i in t)
    rows = {d: (u, q) for d, u, q in kitchen_list(doc)}
    top_rows = [r for d, r in rows.items() if d.startswith('Πάγκος κουζίνας')]
    assert top_rows and top_rows[0][0] == 'm' and top_rows[0][1] > 5.0
    assert rows['Κοπή πάγκου για νεροχύτη'] == ('τεμ.', 1) and rows['Κοπή πάγκου για εστία'] == ('τεμ.', 1)
    assert any(d.startswith('Ντουλάπι βάσης 60×60×86') for d in rows)          # count by width
    assert any(d.startswith('Συμπλήρωμα') for d in rows)
    payload = build_pbr_scene_payload(_evaluate(doc), [], doc=doc)
    assert any(o.get('kind') == 'kitchen_run' and o.get('layer') == 'kitchen' for o in payload['objects'])
    assert any(o.get('kind') == 'cabinet' for o in payload['objects'])


def _evaluate(doc):
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    return IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)


def test_kitchen_layer_hides_the_derived_parts():
    from archforge.core.layers import apply_to_scene_objects, primitive_layer
    from archforge.core.plan_scene import build_plan_frame
    doc, st, _ids = _room(4.0, 3.0)
    _apply(doc, st, cr.plan_run(doc, 2.0, 0.15))
    frame = build_plan_frame(doc, layers=False)
    assert all(primitive_layer(doc, p) == 'kitchen' for p in frame.primitives if p.role in ('worktop', 'hob-symbol'))


def test_open_wall_without_a_room():
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 3.0, 'y2': 0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    prop = _apply(doc, st, cr.plan_run(doc, 1.5, 0.3, options={'sink': False, 'hob': False}))
    for e in cr.run_members(doc, prop.run_id):
        assert min(y for _x, y in footprint(e.params)) >= 0.10 - 1e-6       # on the side that was clicked


def test_l_corner_the_other_way_round_blind_at_the_start():
    doc, st, _ids = _room(4.0, 3.0)
    first = _apply(doc, st, cr.plan_run(doc, 3.85, 1.5))                  # right wall first (starts at the corner)
    second = _apply(doc, st, cr.plan_run(doc, 2.0, 0.15))                 # then the bottom wall, ending there
    blind = [e for e in cr.run_members(doc, first.run_id) if e.params['cabinet_type'] == 'corner_blind']
    assert len(blind) == 1 and blind[0].params['blind_side'] == 'right'
    b0, _b1 = cr._iv(blind[0], blind[0].params['run_seg']['frame'])
    assert b0 == pytest.approx(0.0)
    bottom = _pieces(doc, second.run_id, 'base')
    assert bottom[-1][1] == pytest.approx(3.80 - 0.60) and bottom[-1][2] == 'filler'
    cabs = [e for e in doc.entities.values() if e.kind == 'cabinet' and e.params['run_seg']['layer'] == 'base']
    for i, a in enumerate(cabs):
        for b in cabs[i + 1:]:
            assert not _overlap(footprint(a.params), footprint(b.params)), (a.name, b.name)


def test_ui_mouse_double_click_ghost_enter_menu_width_and_undo():
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.marking_menu import build_menu, run
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        for x1, y1, x2, y2 in [(0, 0, 4, 0), (4, 0, 4, 3), (4, 3, 0, 3), (0, 3, 0, 0)]:
            window.stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                                                           'height': 2.7, 'thickness': 0.2})))
        before = len(window.doc.entities)
        assert 'mm:krun:start' in {e['id'] for e in build_menu(window, 'plan')['entries']}
        run(window, 'plan', None, 'mm:krun:start')
        tool = window._cabinet_run
        assert window.plan_view.controller.tool == 'layout_cabinet_run'
        view = window.plan_view
        view.resize(900, 700); view.fitInView(QRectF(-1, -1, 6, 5))
        pos = view.mapFromScene(QPointF(2.0, 0.2))
        QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
        app.processEvents()
        assert tool.proposal is not None and len(window.doc.entities) == before     # a ghost only
        assert 'mm:krun:apply' in {e['id'] for e in build_menu(window, 'plan')['entries']}
        run(window, 'plan', None, 'mm:krun:sink_here', (3.0, 0.4))
        sink = next(e for e in tool.proposal.entities if e.params['run_role'] == 'sink')
        assert abs(sink.params['x'] - 3.0) <= 0.06
        QTest.keyClick(view.viewport(), Qt.Key.Key_Return)
        app.processEvents()
        assert tool.proposal is None and len(window.doc.entities) - before > 10
        cab = next(e for e in window.doc.entities.values() if e.kind == 'cabinet' and e.params.get('run_role') == 'cabinet'
                   and e.params['run_seg']['layer'] == 'base')
        ids = {e['id'] for e in build_menu(window, 'plan', cab.id)['entries']}
        assert {'mm:krun:width_45', 'mm:krun:delete_run'} <= ids
        run(window, 'plan', cab.id, 'mm:krun:width_45')
        assert window.doc.get(cab.id).params['width'] == pytest.approx(0.45)
        window._undo()                                                       # the width change
        window._undo()                                                       # the whole run
        assert len(window.doc.entities) == before
    finally:
        window._mark_clean(); window.close(); app.processEvents()
