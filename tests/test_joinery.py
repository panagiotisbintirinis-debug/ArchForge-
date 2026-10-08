"""Κουφώματα (WORKLOG L8): τύποι πόρτας/παραθύρου, 3D μέσα στο άνοιγμα, σύμβολο κάτοψης με φορά."""
import math
from types import SimpleNamespace

import pytest

from archforge.architecture import joinery
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity, validate_params
from archforge.core.plan_scene import build_plan_frame
from archforge.geometry.mesh_validation import validate_mesh
from archforge.rendering.fixtures import opening_fixture_parts

T = 0.25


def _doc(kind, width, height, sill, params, wall=None):
    doc = Document(); stack = CommandStack(doc)
    w = Entity('wall', wall or {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': T})
    stack.execute(AddEntity(w))
    L = math.hypot(w.params['x2'] - w.params['x1'], w.params['y2'] - w.params['y1'])
    e = Entity(kind, dict(offset=L / 2, width=width, height=height, sill=sill, **params), parent_id=w.id)
    stack.execute(AddEntity(e))
    return doc, stack, w, e


CASES = [(key, kind, w, h, sill, params) for key, kind, _n, w, h, sill, params in joinery.PRESETS] + [
    ('door_right_out', 'door', 0.9, 2.1, 0.0, {'opening_type': 'interior_flush', 'hinge': 'right', 'swing': 'out'}),
    ('door_double', 'door', 1.4, 2.1, 0.0, {'opening_type': 'interior_panel', 'leaves': 2}),
    ('window_bars', 'window', 1.8, 1.6, 0.8, {'opening_type': 'tilt_turn', 'bars_v': 1, 'bars_h': 2}),
    ('pocket_right', 'door', 0.9, 2.1, 0.0, {'opening_type': 'pocket', 'hinge': 'right'}),
    ('single_shutter', 'window', 0.7, 1.0, 1.0, {'opening_type': 'casement', 'shading': 'shutters'}),
]


@pytest.mark.parametrize('key,kind,width,height,sill,params', CASES, ids=[c[0] for c in CASES])
def test_every_type_gives_closed_meshes_inside_the_wall_opening(key, kind, width, height, sill, params):
    doc, _stack, _w, e = _doc(kind, width, height, sill, params)
    parts = opening_fixture_parts(doc, e)
    roles = {k.split('_', 1)[1] for k, _v, _t in parts}
    assert {'frame', 'handle'} <= roles or params['opening_type'] == 'fixed'
    u0, u1 = 3.0 - width / 2, 3.0 + width / 2
    for key_, verts, tris in parts:
        assert validate_mesh(SimpleNamespace(vertices=verts, triangles=tris)).watertight, key_
        xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
        if key_.endswith('_shading') and params.get('shading') == 'shutters':
            # Ανοιχτά παντζούρια: πάνω στην εξωτερική όψη, δίπλα στο άνοιγμα.
            ws = width if width <= 0.8 else width / 2          # ένα ή δύο φύλλα παντζουριού
            assert min(xs) >= u0 - ws - 1e-9 and max(xs) <= u1 + ws + 1e-9
            assert max(ys) <= -T / 2 + 1e-9 and min(ys) >= -T / 2 - joinery.SHUTTER_D - 1e-9
        else:
            assert min(xs) >= u0 - 1e-9 and max(xs) <= u1 + 1e-9, key_
            assert max(abs(y) for y in ys) <= T / 2 + 0.05, key_      # ποδιά/χερούλια προεξέχουν λίγο
        assert min(zs) >= sill - 1e-9 and max(zs) <= sill + height + 1e-9, key_


@pytest.mark.parametrize('kind,width,params,leaves', [
    ('window', 0.8, {'opening_type': 'casement'}, 1),
    ('window', 1.2, {'opening_type': 'casement'}, 2),
    ('window', 1.2, {'opening_type': 'tilt_turn', 'leaves': 1}, 1),
    ('window', 1.6, {'opening_type': 'sliding'}, 2),
    ('window', 2.4, {'opening_type': 'sliding', 'leaves': 3}, 3),
    ('window', 1.0, {'opening_type': 'fixed'}, 0),
    ('window', 0.8, {'opening_type': 'hopper'}, 1),
    ('door', 1.4, {'opening_type': 'balcony_casement'}, 2),
    ('door', 2.0, {'opening_type': 'balcony_sliding'}, 2),
    ('door', 0.8, {'opening_type': 'interior_flush'}, 1),
    ('door', 1.4, {'opening_type': 'interior_flush', 'leaves': 2}, 2),
    ('door', 1.2, {'opening_type': 'folding'}, 2),
    ('door', 2.4, {'opening_type': 'folding'}, 4),
])
def test_leaf_count(kind, width, params, leaves):
    height, sill = (1.4, 0.9) if kind == 'window' else (2.2, 0.0)
    doc, _s, _w, e = _doc(kind, width, height, sill, params)
    assert joinery.leaf_count(kind, e.params) == leaves
    parts = dict((k, (v, t)) for k, v, t in opening_fixture_parts(doc, e))
    typ = params['opening_type']
    if typ in joinery.GLAZED:
        # Ένα τζάμι ανά φύλλο (το σταθερό: ένα τζάμι στην κάσα).
        glass = parts[f'{kind}_glass'][0]
        assert len(glass) // 8 == max(leaves, 1)
    elif typ in ('interior_flush', 'folding'):
        assert len(parts['door_leaf'][0]) // 8 == leaves


def _symbol_points(doc, e):
    from archforge.architecture.joinery import plan_symbol_world
    return plan_symbol_world(doc, e)


def _arc(doc, e):
    """Σημεία του τόξου (η μακρύτερη «thin» πολυγραμμή)."""
    arcs = [pts for style, pts in _symbol_points(doc, e) if style == 'thin' and len(pts) > 4]
    assert arcs
    return arcs


@pytest.mark.parametrize('hinge,swing,hinge_x,side', [
    # Μόνος τοίχος κατά +x: «μέσα» = +y. Αριστερά/δεξιά κοιτάζοντας από την πλευρά που ανοίγει.
    ('left', 'in', 3.41, 1), ('right', 'in', 2.59, 1), ('left', 'out', 2.59, -1), ('right', 'out', 3.41, -1),
])
def test_door_arc_on_the_right_side_for_hinge_and_swing(hinge, swing, hinge_x, side):
    doc, _s, _w, e = _doc('door', 0.9, 2.1, 0.0, {'opening_type': 'interior_flush', 'hinge': hinge, 'swing': swing})
    (arc,) = _arc(doc, e)
    assert all(side * y >= T / 2 - 1e-9 for _x, y in arc)
    # Το τόξο ξεκινά από το ανοιχτό φύλλο στον μεντεσέ.
    leaf = [pts for style, pts in _symbol_points(doc, e) if style == 'solid' and len(pts) == 2
            and abs(pts[0][1] - pts[1][1]) > 0.5]
    assert len(leaf) == 1 and abs(leaf[0][0][0] - hinge_x) < 0.03
    assert max(abs(y) for _x, y in arc) == pytest.approx(T / 2 + 0.9 - 2 * joinery.JAMB, abs=1e-6)


def test_window_arcs_and_inside_follows_the_room():
    # Κλειστό τετράγωνο 4×4 με τοίχους CCW: το εσωτερικό είναι αριστερά (+n) κάθε τοίχου —
    # ο νότιος τοίχος σχεδιάζεται ανάποδα ώστε το «μέσα» του να είναι το -n.
    doc = Document(); stack = CommandStack(doc)
    walls = [(4, 0, 0, 0), (4, 0, 4, 4), (4, 4, 0, 4), (0, 4, 0, 0)]
    ids = []
    for x1, y1, x2, y2 in walls:
        w = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0, 'height': 2.7, 'thickness': T})
        stack.execute(AddEntity(w)); ids.append(w.id)
    south = doc.get(ids[0])
    assert joinery.inside_sign(doc, south) == -1           # μέσα = +y, ενώ n = -y
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9,
                            'opening_type': 'casement'}, parent_id=south.id)
    stack.execute(AddEntity(win))
    arcs = _arc(doc, win)
    assert len(arcs) == 2                                    # δίφυλλο: δύο τόξα
    assert all(y > 0 for arc in arcs for _x, y in arc)       # προς το δωμάτιο
    stack.execute(UpdateEntity(win.id, {'swing': 'out'}))
    assert all(y < 0 for arc in _arc(doc, doc.get(win.id)) for _x, y in arc)
    door = Entity('door', {'offset': 2.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0, 'opening_type': 'security'},
                  parent_id=ids[2])
    stack.execute(AddEntity(door))
    assert all(y < 4 for arc in _arc(doc, door) for _x, y in arc)   # η εξώπορτα ανοίγει προς τα μέσα


def test_sliding_pocket_and_folding_symbols():
    doc, _s, _w, e = _doc('window', 1.6, 1.2, 0.9, {'opening_type': 'sliding'})
    sym = _symbol_points(doc, e)
    tracks = [pts for style, pts in sym if style == 'solid' and abs(pts[0][1] - pts[-1][1]) < 1e-9
              and abs(abs(pts[0][1]) - joinery.TRACK) < 1e-9]
    assert len(tracks) == 2 and {round(p[0][1], 3) for p in tracks} == {-joinery.TRACK, joinery.TRACK}
    assert not [pts for style, pts in sym if len(pts) > 4]   # κανένα τόξο στα συρόμενα
    # Χωνευτή: η θήκη μέσα στον τοίχο (διακεκομμένη), στην πλευρά που μαζεύει.
    for hinge, sign in (('left', 1), ('right', -1)):
        doc, _s, _w, e = _doc('door', 0.8, 2.1, 0.0, {'opening_type': 'pocket', 'hinge': hinge})
        pocket = [pts for style, pts in _symbol_points(doc, e) if style == 'dashed']
        xs = [x for pts in pocket for x, _y in pts]; ys = [y for pts in pocket for _x, y in pts]
        assert pocket and all(abs(y) < T / 2 for y in ys)
        assert (min(xs) >= 3.4 - 1e-9) if sign > 0 else (max(xs) <= 2.6 + 1e-9)
    # Η θήκη πρέπει να χωρά στον τοίχο, στην πλευρά που μαζεύει.
    doc, stack, w, _e = _doc('door', 0.8, 2.1, 0.0, {'opening_type': 'pocket'})
    near = Entity('door', {'offset': 0.6, 'width': 0.8, 'height': 2.1, 'sill': 0.0, 'opening_type': 'pocket',
                           'hinge': 'left'}, parent_id=w.id)
    stack.execute(AddEntity(near))
    assert joinery.pocket_fits(doc, doc.get(near.id))
    stack.execute(UpdateEntity(near.id, {'hinge': 'right'}))
    assert not joinery.pocket_fits(doc, doc.get(near.id))
    short = Document(); s2 = CommandStack(short)
    sw = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 1.2, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': T})
    s2.execute(AddEntity(sw))
    with pytest.raises(ValueError):
        s2.execute(AddEntity(Entity('door', {'offset': 0.6, 'width': 0.8, 'height': 2.1, 'sill': 0.0,
                                             'opening_type': 'pocket'}, parent_id=sw.id)))
    doc, _s, _w, e = _doc('door', 1.2, 2.1, 0.0, {'opening_type': 'folding'})
    zigzag = [pts for style, pts in _symbol_points(doc, e) if style == 'solid' and len(pts) == 3]
    assert zigzag


def test_plan_frame_draws_the_symbol_with_the_door_id():
    doc, _s, _w, e = _doc('door', 0.9, 2.1, 0.0, {'opening_type': 'interior_flush'})
    prims = [p for p in build_plan_frame(doc).primitives if p.role.startswith('opening-symbol')]
    assert prims and all(p.entity_id == e.id for p in prims)


def test_default_regression_untyped_openings_stay_as_before():
    for params in ({}, {'opening_type': 'basic'}):
        doc, _s, _w, win = _doc('window', 1.2, 1.2, 0.9, params)
        assert {k for k, _v, _t in opening_fixture_parts(doc, win)} == {'window_frame', 'window_glass'}
        doc2, _s, _w, door = _doc('door', 0.9, 2.1, 0.0, params)
        assert {k for k, _v, _t in opening_fixture_parts(doc2, door)} == {'door_frame', 'door_leaf'}
        assert not [p for p in build_plan_frame(doc).primitives if p.role.startswith('opening-symbol')]
        assert joinery.plan_symbol_world(doc2, door) == []
    # Ίδια γεωμετρία με πριν, κορυφή προς κορυφή.
    doc, _s, _w, win = _doc('window', 2.0, 1.2, 0.9, {})
    glass = [v for k, v, _t in opening_fixture_parts(doc, win) if k == 'window_glass']
    assert len(glass[0]) == 16


def test_schema_accepts_and_rejects():
    ok = validate_params('door', {'offset': 1, 'width': .9, 'height': 2.1, 'sill': 0, 'opening_type': 'security',
                                  'hinge': 'right', 'swing': 'out', 'finish': 'wood_walnut'})
    assert ok['opening_type'] == 'security'
    assert validate_params('window', {'leaves': 2.0, 'bars_h': '1'})['bars_h'] == 1
    for bad in ({'hinge': 'up'}, {'swing': 'sideways'}, {'opening_type': 'garage'}, {'leaves': 12},
                {'shading': 'awning'}, {'transom': -0.1}, {'finish': 'gold'}):
        with pytest.raises(ValueError):
            validate_params('window', bad)
    doc, stack, w, _e = _doc('window', 1.2, 1.4, 0.9, {'opening_type': 'casement'})
    # Τύπος πόρτας σε παράθυρο, λάθος πλήθος φύλλων, φεγγίτης που δεν χωρά: απορρίπτονται.
    for bad in ({'opening_type': 'security'}, {'leaves': 5}, {'transom': 1.2}):
        with pytest.raises(ValueError):
            stack.execute(AddEntity(Entity('window', {'offset': 1.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9,
                                                       'opening_type': 'casement', **bad}, parent_id=w.id)))
    with pytest.raises(ValueError):
        stack.execute(AddEntity(Entity('door', {'offset': 1.0, 'width': .9, 'height': 2.1, 'sill': 0.0,
                                                 'opening_type': 'security', 'leaves': 2}, parent_id=w.id)))


def test_type_change_is_one_undo_and_survives_save_load(tmp_path):
    doc, stack, _w, e = _doc('window', 1.2, 1.58, 0.9, {})
    stack.execute(UpdateEntity(e.id, {'opening_type': 'tilt_turn', 'leaves': 0, 'shading': 'roller',
                                      'hinge': 'right', 'finish': 'pvc_white', 'bars_v': 1}))
    typed = {k for k, _v, _t in opening_fixture_parts(doc, doc.get(e.id))}
    assert 'window_shading' in typed and 'window_leaf' in typed
    stack.undo()
    assert 'opening_type' not in doc.get(e.id).params
    assert {k for k, _v, _t in opening_fixture_parts(doc, doc.get(e.id))} == {'window_frame', 'window_glass'}
    stack.redo()
    assert doc.get(e.id).params['opening_type'] == 'tilt_turn'
    path = tmp_path / 'joinery.archforge'
    doc.save(str(path))
    loaded = Document.load(str(path))
    p = loaded.get(e.id).params
    assert (p['opening_type'], p['shading'], p['hinge'], p['finish'], p['bars_v']) == ('tilt_turn', 'roller', 'right', 'pvc_white', 1)
    assert [k for k, _v, _t in opening_fixture_parts(loaded, loaded.get(e.id))] == \
        [k for k, _v, _t in opening_fixture_parts(doc, doc.get(e.id))]
    assert joinery.plan_symbol_world(loaded, loaded.get(e.id)) == joinery.plan_symbol_world(doc, doc.get(e.id))


def test_render_uses_finish_per_role_and_palette_override():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc, stack, _w, e = _doc('window', 1.2, 1.4, 0.9, {'opening_type': 'casement', 'finish': 'pvc_white'})

    def mats():
        objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
        return {o['render_part'].split(':')[1]: o['material'] for o in objs if o['id'] == e.id}
    m = mats()
    assert m['window_frame']['color'] == joinery.FINISHES['pvc_white'][1]
    assert m['window_glass']['opacity'] < 0.5
    stack.execute(UpdateEntity(e.id, {'surface_materials': {'frame': 'wood_oak'}}))
    m = mats()
    assert m['window_frame'].get('material_id') == 'wood_oak'
    assert m['window_leaf']['color'] == joinery.FINISHES['pvc_white'][1]


def test_preset_placement_through_the_pointer_controller():
    from archforge.core.viewport import PointerController, PointerEvent
    doc = Document(); stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': T})))
    c = PointerController(doc, stack); c.set_tool('door')
    c.opening_preset = joinery.preset('d_security')
    c.pointer_down(PointerEvent(3.0, 0)); r = c.pointer_up(PointerEvent(3.0, 0))
    e = doc.get(r.entity_id)
    assert (e.params['width'], e.params['height'], e.params['opening_type']) == (0.9, 2.15, 'security')
    assert e.name == 'Εξώπορτα θωρακισμένη 90×215'
    c.set_tool('door')                                   # άλλο εργαλείο/νέα επιλογή: χωρίς preset
    assert c.opening_preset is None
