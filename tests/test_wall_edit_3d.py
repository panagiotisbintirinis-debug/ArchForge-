"""Walls worked in the 3D view: 3D events -> the plan's own wall/opening commands (one undo each)."""
import json
import math
import shutil
import subprocess

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.ui.wall_edit_3d import Wall3DEditor, ghost_script, handles_script, metres, opening_script


def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall']


def _brief(stack, **answers):
    e = Entity('project_brief', {'project_type': 'new', 'wall_system': 'brick_double_insulated', 'measure': 'exterior',
                                 'floor_system': 'rc_slab', **answers})
    stack.execute(AddEntity(e))


def _box(stack, x=6.0, y=4.0, t=0.2):
    ids = []
    for s in [(0, 0, x, 0), (x, 0, x, y), (x, y, 0, y), (0, y, 0, 0)]:
        w = Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0, 'height': 2.7, 'thickness': t})
        stack.execute(AddEntity(w)); ids.append(w.id)
    return ids


def test_four_clicks_on_the_floor_draw_a_closed_room_one_undo_per_wall():
    doc = Document(); st = CommandStack(doc)
    ed = Wall3DEditor(doc, st)
    ev = lambda kind, x, y, **k: ed.handle_event(json.dumps({'type': kind, 'x': x, 'y': y, 'pxm': 0.01, **k}))
    g = ev('hover', 0.02, -0.03)
    assert g['marker']['pos'][:2] == pytest.approx([0.0, 0.0]) and not g['drawing']      # grid before the first click
    ev('click', 0.0, 0.0)
    g = ev('hover', 4.97, 0.04)
    assert g['drawing'] and len(g['walls']) == 1
    w = g['walls'][0]
    assert w['thickness'] == pytest.approx(0.15) and w['height'] == pytest.approx(2.7)    # the real wall, not a line
    assert g['label']['text'].startswith('4,97 m') or g['label']['text'].startswith('5,00 m')
    for x, y in [(5.0, 0.0), (5.0, 4.0), (0.0, 4.0)]:
        g = ev('click', x, y)
        assert g['committed'] and g['drawing']                                            # the chain goes on
    g = ev('click', 0.02, 0.01)                                                          # back on the first corner
    assert g['committed'] and not g['drawing']                                            # closed: chain done
    walls = _walls(doc)
    assert len(walls) == 4
    corners = {(round(w.params['x1'], 6), round(w.params['y1'], 6)) for w in walls}
    assert corners == {(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)}
    st.undo()
    assert len(_walls(doc)) == 3                                                          # one wall per undo


def test_double_click_and_finish_end_the_chain_without_a_stray_wall():
    doc = Document(); st = CommandStack(doc)
    ed = Wall3DEditor(doc, st)
    ed.click(0.0, 0.0)
    ed.hover(3.0, 0.0)
    ed.click(3.0, 0.0)                     # first click of the double click: the wall
    g = ed.click(3.0, 0.0)                 # second click on the same point: ignored, no error
    assert g['drawing'] and len(_walls(doc)) == 1
    g = ed.handle_event({'type': 'finish'})
    assert not g['drawing'] and g['walls'] == [] and len(_walls(doc)) == 1
    assert ed.finish()['drawing'] is False


def test_wall_tool_in_3d_uses_the_project_wall_type_and_interior_type():
    doc = Document(); st = CommandStack(doc)
    _brief(st, interior_walls='drywall_double')
    ed = Wall3DEditor(doc, st)
    ed.click(0.0, 0.0)
    g = ed.hover(8.0, 0.0)
    from archforge.project.brief import wall_defaults
    assert g['walls'][0]['thickness'] == pytest.approx(wall_defaults(doc)[1]) and g['walls'][0]['thickness'] > 0.2
    for x, y in [(8.0, 0.0), (8.0, 6.0), (0.0, 6.0), (0.0, 0.0)]:
        ed.click(x, y)
    ed.finish()
    assert all(w.params.get('wall_type') == 'brick_double_insulated' for w in _walls(doc))
    ed.click(4.0, 1.0); ed.click(4.0, 5.0); ed.finish()         # inside the closed room: partition
    inner = [w for w in _walls(doc) if w.params.get('wall_type') == 'drywall_double_125']
    assert len(inner) == 1


def test_walls_follow_the_active_storey():
    doc = Document(); st = CommandStack(doc)
    doc.work_plane.origin = (0.0, 0.0, 3.0)
    ed = Wall3DEditor(doc, st)
    ed.click(0.0, 0.0); ed.click(2.0, 0.0); ed.finish()
    (w,) = _walls(doc)
    assert w.params['z'] == pytest.approx(3.0) and ed.handles_payload()['floor_z'] == pytest.approx(3.0)


def test_snap_radius_follows_the_screen_scale_within_limits():
    ed = Wall3DEditor(Document(), None)
    assert ed._tolerance(0.001) == pytest.approx(0.10)
    assert ed._tolerance(0.02) == pytest.approx(0.24)
    assert ed._tolerance(1.0) == pytest.approx(0.60)
    assert ed._tolerance('x') == pytest.approx(0.10) and ed._tolerance(float('nan')) == pytest.approx(0.10)


def test_handles_only_for_one_selected_wall_and_stale_ids_are_refused():
    doc = Document(); st = CommandStack(doc)
    ids = _box(st)
    ed = Wall3DEditor(doc, st)
    assert ed.handles() == []
    doc.select([ids[0]])
    hs = {h['id']: h for h in ed.handles()}
    assert set(hs) == {'endpoint1', 'endpoint2', 'mid', 'top'}
    assert hs['top']['pos'] == pytest.approx([3.0, 0.0, 2.7]) and hs['mid']['pos'] == pytest.approx([3.0, 0.0, 0.0])
    with pytest.raises(ValueError):
        ed.handle_down('corner', 0, 0)
    doc.select([])
    with pytest.raises(ValueError):
        ed.handle_down('endpoint1', 0, 0)
    assert 'archforgeSetWallHandles' in handles_script(ed.handles_payload())


def test_dragging_an_end_stretches_and_the_joined_wall_follows_in_one_undo():
    doc = Document(); st = CommandStack(doc)
    ids = _box(st)
    ed = Wall3DEditor(doc, st)
    doc.select([ids[0]])                      # (0,0)->(6,0); its end (6,0) joins wall 2
    ed.handle_down('endpoint2', 6.0, 0.0)
    g = ed.handle_move(7.0, 0.0)
    assert len(g['walls']) == 2 and g['label']['text'] == 'Μήκος 7,00 m'
    assert doc.get(ids[0]).params['x2'] == pytest.approx(6.0)        # preview only
    g = ed.handle_up()
    assert g['committed'] == ids[0]
    assert doc.get(ids[0]).params['x2'] == pytest.approx(7.0) and doc.get(ids[1]).params['x1'] == pytest.approx(7.0)
    st.undo()
    assert doc.get(ids[0]).params['x2'] == pytest.approx(6.0) and doc.get(ids[1]).params['x1'] == pytest.approx(6.0)


def test_dragging_the_middle_moves_the_wall_parallel_only():
    doc = Document(); st = CommandStack(doc)
    w = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    st.execute(AddEntity(w))
    ed = Wall3DEditor(doc, st)
    doc.select([w.id])
    ed.handle_down('mid', 2.0, 0.0)
    g = ed.handle_move(3.3, 0.62)             # along the wall is ignored, 5 cm steps across
    assert g['label']['text'] == 'Μετατόπιση 0,60 m'
    ed.handle_up()
    p = doc.get(w.id).params
    assert (p['x1'], p['x2']) == pytest.approx((0.0, 4.0)) and (p['y1'], p['y2']) == pytest.approx((0.6, 0.6))
    st.undo()
    assert doc.get(w.id).params['y1'] == pytest.approx(0.0)
    ed.handle_down('mid', 2.0, 0.0)
    ed.handle_move(2.0, 0.0)
    assert not ed.handle_up().get('committed')      # no move, no undo step


def test_top_handle_sets_height_from_the_camera_ray_in_5cm_steps():
    doc = Document(); st = CommandStack(doc)
    w = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    st.execute(AddEntity(w))
    ed = Wall3DEditor(doc, st)
    doc.select([w.id])
    ed.handle_down('top', 2.0, 0.0)
    # Camera 10 m in front looking straight at (2, 0, 3.12).
    g = ed.handle_move(2.0, 0.0, origin=[2.0, -10.0, 3.12], direction=[0.0, 1.0, 0.0])
    assert g['label']['text'] == 'Ύψος 3,10 m'
    assert ed.handle_up()['committed'] == w.id
    assert doc.get(w.id).params['height'] == pytest.approx(3.10)
    st.undo()
    assert doc.get(w.id).params['height'] == pytest.approx(2.7)


def test_handle_cancel_leaves_the_document_untouched():
    doc = Document(); st = CommandStack(doc)
    ids = _box(st)
    ed = Wall3DEditor(doc, st)
    doc.select([ids[0]])
    before = {i: dict(doc.get(i).params) for i in ids}
    ed.handle_down('endpoint1', 0.0, 0.0)
    ed.handle_move(-2.0, -1.0)
    ed.handle_event({'type': 'handle_cancel'})
    assert {i: dict(doc.get(i).params) for i in ids} == before and not ed.editing


def test_door_ghost_on_a_wall_is_where_the_click_puts_it():
    doc = Document(); st = CommandStack(doc)
    ids = _box(st)
    ed = Wall3DEditor(doc, st)
    g = ed.handle_event({'type': 'opening_hover', 'tool': 'door', 'entity_id': ids[0], 'point': [2.0, 0.05, 1.0]})
    o = g['opening']
    assert o['valid'] and o['offset'] == pytest.approx(2.0)
    assert o['box']['z'] == pytest.approx(0.0) and o['box']['height'] == pytest.approx(2.1)
    assert math.hypot(o['box']['x2'] - o['box']['x1'], o['box']['y2'] - o['box']['y1']) == pytest.approx(0.9)
    assert o['label']['text'].startswith('Πόρτα 0,90 m')
    w = ed.opening_ghost('window', ids[0], [2.0, 0.0])['opening']
    assert w['box']['z'] == pytest.approx(0.9)
    assert ed.opening_ghost('door', 'nope', [0, 0])['opening'] is None
    assert len(doc.entities) == 4                                   # a ghost never adds anything
    assert 'archforgeSetOpeningGhost' in opening_script(g)


def test_events_are_validated_and_scripts_are_json():
    ed = Wall3DEditor(Document(), None)
    with pytest.raises(ValueError):
        ed.handle_event('[1, 2]')
    with pytest.raises(ValueError):
        ed.handle_event({'type': 'explode'})
    s = ghost_script(ed.hover(1.0, 1.0))
    payload = json.loads(s[s.index('(', s.index('archforgeSetWallGhost(')) + 1:-2])
    assert payload['marker']['kind'] in ('grid', 'construction_grid') and payload['floor_z'] == 0.0
    assert metres(3.456) == '3,46 m'


def test_page_carries_the_wall_js_and_it_parses():
    from archforge.ui.pbr_viewport import _PBR_HTML, pbr_page_html
    from archforge.ui.wall_edit_3d_js import wall_edit_3d_js
    html = pbr_page_html()
    assert '__ARCHFORGE_WALL_EDIT_3D__' in _PBR_HTML and '__ARCHFORGE_WALL_EDIT_3D__' not in html
    js = wall_edit_3d_js()
    for name in ('bridge.wallEvent', 'archforgeSetWallGhost', 'archforgeSetWallHandles', 'archforgeSetOpeningGhost',
                 '"handle_down"', '"handle_move"', '"handle_up"', '"opening_hover"', '"finish"'):
        assert name in js
    # The wall listeners come before the page's own, so a wall gesture is seen first.
    assert html.index('wall-handles') < html.index('if (event.button !== 2) hideMarkingMenu();')
    node = shutil.which('node')
    if node is None:
        pytest.skip('node not installed')
    start = html.index('<script type="module">') + len('<script type="module">')
    module = html[start:html.index('</script>', start)]
    proc = subprocess.run([node, '--input-type=module', '--check'], input=module, text=True, capture_output=True)
    assert proc.returncode == 0, proc.stderr


def test_pbr_bridge_has_the_wall_slot():
    from archforge.ui.pbr_viewport import PBRInteractionBridge
    assert hasattr(PBRInteractionBridge, 'wallEvent')
