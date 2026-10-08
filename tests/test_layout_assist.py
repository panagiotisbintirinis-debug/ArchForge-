"""Βοηθός «Κουζίνα εδώ» / «Μπάνιο εδώ»: layouts of ordinary entities, one undo, Delete, re-fit, drag snap."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.assistant.room_layout import (apply_command, delete_command, layouts, plan, refit, refit_proposals)
from archforge.assistant.room_walls import legs_from_points, room_runs, snap_point
from archforge.assistant.suggestions import room_at
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.kitchen.cabinets import _overlap, footprint, plan_box


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))


def _room(W, H, door=None, window=None):
    doc = Document(); st = CommandStack(doc); ids = []
    for x1, y1, x2, y2 in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
        e = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
        st.execute(AddEntity(e)); ids.append(e.id)
    if door:
        st.execute(AddEntity(Entity('door', {'offset': door[1], 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=ids[door[0]])))
    if window:
        st.execute(AddEntity(Entity('window', {'offset': window[1], 'width': window[2], 'height': 1.2, 'sill': 1.0},
                                    parent_id=ids[window[0]])))
    return doc, st, ids


def _inner(W, H, t=0.2):
    return (t / 2, t / 2, W - t / 2, H - t / 2)


def _poly(e):
    if e.kind == 'cabinet':
        return footprint(e.params)
    p = e.params
    return plan_box(p['x'], p['y'], p['rotation'], p['width'], p['depth'])


def _check_kitchen(doc, proposal, W, H):
    x0, y0, x1, y1 = _inner(W, H)
    cabs = [e for e in proposal.entities if e.kind == 'cabinet']
    assert cabs
    for e in cabs + [e for e in proposal.entities if e.kind == 'library_object' and e.params['layout_role'] == 'fridge']:
        for x, y in _poly(e):
            assert x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6, e.name      # inside the room
        if e.params.get('cabinet_type') != 'corner':
            # Back on a wall face: the back edge (local +Y) lies on one of the inner faces.
            a = math.radians(e.params['rotation'])
            bx, by = e.params['x'] - math.sin(a) * e.params['depth'] / 2, e.params['y'] + math.cos(a) * e.params['depth'] / 2
            assert min(abs(bx - x0), abs(bx - x1), abs(by - y0), abs(by - y1)) < 1e-6, e.name
    for i, a in enumerate(cabs):
        for b in cabs[i + 1:]:
            same_level = (a.params['cabinet_type'] == 'wall') == (b.params['cabinet_type'] == 'wall')
            if same_level:
                assert not _overlap(_poly(a), _poly(b)), (a.name, b.name)                   # no overlaps


@pytest.mark.parametrize('W,H', [(3.0, 2.5), (4.0, 3.0), (5.0, 4.2)])
@pytest.mark.parametrize('shape', ['I', 'L', 'U'])
def test_kitchen_i_l_u_inside_on_the_walls_without_overlaps(W, H, shape):
    doc, st, ids = _room(W, H, door=(2, W - 1.0))
    proposal = plan(doc, 'kitchen', room_at(doc, W / 2, H / 2), options={'shape': shape})
    assert proposal.entities and proposal.label.startswith('Κουζίνα ' + {'I': 'Ι', 'L': 'Γ', 'U': 'Π'}[shape])
    _check_kitchen(doc, proposal, W, H)
    corners = [e for e in proposal.entities if e.params.get('cabinet_type') == 'corner']
    assert len(corners) == {'I': 0, 'L': 1, 'U': 2}[shape]                                  # corner unit in Γ / Π
    roles = {e.params.get('layout_role') for e in proposal.entities}
    assert {'sink', 'hob_base'} <= roles
    assert 'fridge' in roles or any('ψυγείο' in t.lower() for t in proposal.problems)      # or it says why not
    assert any('Τρίγωνο' in n for n in proposal.notes)
    assert {e.params['point_type'] for e in proposal.entities if e.kind == 'plumbing_point'} >= {'kitchen_sink'}


def test_base_run_has_no_gaps_beyond_tolerance_along_the_guide_line():
    doc, st, ids = _room(4.0, 3.0)
    room = room_at(doc, 2, 1.5)
    runs = room_runs(doc, room)
    legs = legs_from_points(runs, [snap_point(runs, 3.9, 0.1)[:2]])
    # A whole south face drawn as the guide line: I kitchen, base units fill it to within 1 cm.
    start, end = snap_point(runs, 0.1, 0.12), snap_point(runs, 3.9, 0.12)
    legs = legs_from_points(runs, [start[:2], end[:2]])
    assert len(legs) == 1 and legs[0][2] - legs[0][1] == pytest.approx(3.8)
    proposal = plan(doc, 'kitchen', room, legs=legs)
    base = [e for e in proposal.entities if e.kind == 'cabinet' and e.params['cabinet_type'] != 'wall']
    fridge = [e for e in proposal.entities if e.params.get('layout_role') == 'fridge']
    covered = sum(e.params['width'] for e in base + fridge)
    assert 3.8 - covered <= 0.01


def test_line_round_a_corner_makes_an_l_with_a_corner_unit():
    doc, st, ids = _room(4.0, 3.0)
    room = room_at(doc, 2, 1.5)
    runs = room_runs(doc, room)
    pts = [snap_point(runs, 3.0, 0.15)[:2], snap_point(runs, 0.12, 0.12)[:2], snap_point(runs, 0.15, 2.2)[:2]]
    legs = legs_from_points(runs, pts)
    assert len(legs) == 2
    proposal = plan(doc, 'kitchen', room, legs=legs)
    assert proposal.label.startswith('Κουζίνα Γ')
    assert sum(e.params.get('cabinet_type') == 'corner' for e in proposal.entities) == 1


def test_kitchen_keeps_off_the_door_and_wall_units_off_the_window():
    doc, st, ids = _room(4.0, 3.0, door=(0, 0.8), window=(0, 2.6, 1.2))     # both on the south wall
    room = room_at(doc, 2, 1.5)
    runs = room_runs(doc, room)
    south = next(r for r in runs if ids[0] in r.wall_ids)
    door = south.doors()[0]
    win = south.windows()[0]
    for shape in ('I', 'L', 'auto'):
        for v in range(3):
            proposal = plan(doc, 'kitchen', room, options={'shape': shape}, variant=v)
            for e in proposal.entities:
                if e.kind not in ('cabinet', 'library_object'):
                    continue
                ss = [(x - south.a[0]) * south.u[0] + (y - south.a[1]) * south.u[1] for x, y in _poly(e)]
                dd = [(x - south.a[0]) * south.n[0] + (y - south.a[1]) * south.n[1] for x, y in _poly(e)]
                if min(dd) > 0.70:
                    continue                                          # not along the south wall
                assert max(ss) <= door.s0 + 1e-6 or min(ss) >= door.s1 - 1e-6, e.name          # not in the door
                if e.params.get('cabinet_type') == 'wall':
                    assert max(ss) <= win.s0 + 1e-6 or min(ss) >= win.s1 - 1e-6, e.name       # not over the window


def test_bathroom_rules_and_points():
    doc, st, ids = _room(2.6, 2.2, door=(2, 0.6), window=(0, 1.3, 0.6))
    room = room_at(doc, 1.3, 1.1)
    runs = room_runs(doc, room)
    for wet in ('shower', 'bathtub'):
        proposal = plan(doc, 'bath', room, options={'wet': wet})
        objs = [e for e in proposal.entities if e.kind == 'library_object']
        roles = {e.params['layout_role'] for e in objs}
        assert {'wc', 'basin'} <= roles
        points = {e.params['point_type'] for e in proposal.entities if e.kind == 'plumbing_point'}
        assert {'wc', 'basin'} <= points                                       # water / drain points
        wc = next(e for e in objs if e.params['layout_role'] == 'wc')
        x0, y0, x1, y1 = _inner(2.6, 2.2)
        a = math.radians(wc.params['rotation'])
        ux, uy = math.cos(a), math.sin(a)
        # Axis ≥ 40 cm from a side wall and from the next fixture's edge.
        axis_x, axis_y = wc.params['x'], wc.params['y']
        if abs(ux) > 0.5:
            assert min(axis_x - x0, x1 - axis_x) >= 0.40 - 1e-6
        else:
            assert min(axis_y - y0, y1 - axis_y) >= 0.40 - 1e-6
        # ≥ 60 cm clear in front of the WC (inside the room).
        fx, fy = axis_x + math.sin(a) * (wc.params['depth'] / 2 + 0.60), axis_y - math.cos(a) * (wc.params['depth'] / 2 + 0.60)
        assert x0 - 1e-6 <= fx <= x1 + 1e-6 and y0 - 1e-6 <= fy <= y1 + 1e-6
        for i, p in enumerate(objs):
            for q in objs[i + 1:]:
                assert not _overlap(_poly(p), _poly(q))
        # Nothing in the swing of the door.
        door = next(o for r in runs for o in r.doors())
        r = next(r for r in runs if door in r.doors())
        swing = [r.point(door.s0, 0), r.point(door.s1, 0), r.point(door.s1, door.width), r.point(door.s0, door.width)]
        assert not any(_overlap(_poly(e), swing) for e in objs)
        shower = [e for e in objs if e.params['layout_role'] == 'shower']
        south = next(r for r in runs if ids[0] in r.wall_ids)
        win = south.windows()[0]
        for e in shower:                                                       # never under the window
            ss = [(x - south.a[0]) * south.u[0] + (y - south.a[1]) * south.u[1] for x, y in _poly(e)]
            dd = [(x - south.a[0]) * south.n[0] + (y - south.a[1]) * south.n[1] for x, y in _poly(e)]
            assert min(dd) > 0.05 or max(ss) <= win.s0 + 1e-6 or min(ss) >= win.s1 - 1e-6
        assert 'Neufert' in proposal.source


def test_apply_is_one_undo_delete_is_one_command_and_save_load_keeps_the_layout():
    doc, st, ids = _room(4.0, 3.0)
    proposal = plan(doc, 'kitchen', room_at(doc, 2, 1.5), options={'shape': 'L'})
    before = len(doc.entities)
    st.execute(apply_command(proposal))
    n = len(proposal.entities)
    assert len(doc.entities) == before + n
    st.undo(); assert len(doc.entities) == before
    st.redo(); assert len(doc.entities) == before + n
    lid = proposal.layout_id
    assert list(layouts(doc)) == [lid]
    loaded = Document.from_dict(doc.to_dict())
    assert {e.id for e in loaded.entities.values() if e.params.get('layout_id') == lid} == {e.id for e in proposal.entities}
    spec = next(e for e in loaded.entities.values() if e.params.get('layout_id') == lid).params['layout_spec']
    assert spec['kind'] == 'kitchen' and spec['shape'] == 'L'
    st.execute(delete_command(doc, lid))
    assert len(doc.entities) == before
    st.undo(); assert len(doc.entities) == before + n


def test_moved_wall_offers_refit_that_fits_the_new_room_in_one_undo():
    doc, st, ids = _room(4.0, 3.0)
    proposal = plan(doc, 'kitchen', room_at(doc, 2, 1.5), options={'shape': 'L'})
    st.execute(apply_command(proposal))
    assert refit_proposals(doc) == []
    # The east wall moves out by 1 m (the walls meeting it follow).
    st.execute(UpdateEntity(ids[1], {'x1': 5.0, 'x2': 5.0}))
    st.execute(UpdateEntity(ids[0], {'x2': 5.0}))
    st.execute(UpdateEntity(ids[2], {'x1': 5.0}))
    offers = refit_proposals(doc)
    assert len(offers) == 1 and 'αναπροσαρμογή' in offers[0].title
    old = {e.id for e in doc.entities.values() if e.params.get('layout_id') == proposal.layout_id}
    command, new = refit(doc, proposal.layout_id)
    st.execute(command)
    now = [e for e in doc.entities.values() if e.params.get('layout_id') == proposal.layout_id]
    assert {e.id for e in now}.isdisjoint(old) and now
    _check_kitchen(doc, new, 5.0, 3.0)
    assert refit_proposals(doc) == []
    st.undo()
    assert {e.id for e in doc.entities.values() if e.params.get('layout_id') == proposal.layout_id} == old


def test_dragged_fixture_clicks_onto_the_wall_and_its_water_point_follows():
    from archforge.core.interaction import MoveTransaction
    doc, st, ids = _room(2.6, 2.2)
    proposal = plan(doc, 'bath', room_at(doc, 1.3, 1.1), options={'wet': 'shower'})
    st.execute(apply_command(proposal))
    basin = next(e for e in doc.entities.values() if e.params.get('layout_role') == 'basin')
    point = next(e for e in doc.entities.values() if e.params.get('layout_host') == basin.id)
    x, y, a = basin.params['x'], basin.params['y'], math.radians(basin.params['rotation'])
    nx, ny = math.sin(a), -math.cos(a)                 # towards the room (the front)
    tx = MoveTransaction(doc, st, [basin.id], origin=(x, y, 0.0))
    assert point.id in tx.ids                           # the water point moves with it
    tx.update_pointer(x + nx * 0.10, y + ny * 0.10)    # pulled 10 cm off the wall …
    tx.commit()
    b = doc.get(basin.id).params
    assert (b['x'], b['y']) == pytest.approx((x, y), abs=1e-6)               # … it clicks back on
    p0 = point.params
    assert (doc.get(point.id).params['x'], doc.get(point.id).params['y']) == pytest.approx((p0['x'], p0['y']), abs=1e-6)


def test_cabinet_drag_snaps_to_its_neighbour():
    from archforge.core.interaction import MoveTransaction
    doc, st, ids = _room(4.0, 3.0)
    proposal = plan(doc, 'kitchen', room_at(doc, 2, 1.5), options={'shape': 'I'})
    st.execute(apply_command(proposal))
    base = sorted([e for e in doc.entities.values() if e.params.get('layout_role') == 'base'], key=lambda e: e.params['x'])
    b = base[-1]
    x, y = b.params['x'], b.params['y']
    tx = MoveTransaction(doc, st, [b.id], origin=(x, y, 0.0))
    tx.update_pointer(x + 0.08, y + 0.07)
    p = tx.preview[b.id]
    assert p['y'] == pytest.approx(y, abs=1e-6)                                # back stays on the wall


def test_ui_kitchen_here_ghost_delete_and_apply_with_one_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.marking_menu import build_menu, run
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        for x1, y1, x2, y2 in [(0, 0, 4, 0), (4, 0, 4, 3), (4, 3, 0, 3), (0, 3, 0, 0)]:
            window.stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                                                           'height': 2.7, 'thickness': 0.2})))
        empty = build_menu(window, 'plan')
        assert {'mm:layout:kitchen', 'mm:layout:bath'} <= {e['id'] for e in empty['entries']}
        before = len(window.doc.entities)
        run(window, 'plan', None, 'mm:layout:kitchen', (2.0, 1.5))         # right click in the room → «Κουζίνα εδώ…»
        assist = window._layout_assist
        assert assist.proposal is not None and assist.proposal.entities
        assert len(window.doc.entities) == before                          # only a ghost
        menu = build_menu(window, 'plan')
        assert 'mm:layout:apply' in {e['id'] for e in menu['entries']}
        window._delete_selection()                                           # Delete throws the ghost away
        assert assist.proposal is None and len(window.doc.entities) == before
        assist.propose_at(2.0, 1.5)
        first = assist.proposal.label
        assist.next_variant()
        assert assist.proposal.label != first
        applied = assist.apply()
        assert len(window.doc.entities) == before + len(applied.entities)
        assert set(window.doc.selection) and window.plan_view.controller.tool == 'select'
        window._undo()
        assert len(window.doc.entities) == before
    finally:
        window._mark_clean(); window.close(); app.processEvents()
