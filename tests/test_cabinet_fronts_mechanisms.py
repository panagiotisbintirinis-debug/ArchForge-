"""Cabinet front styles, handles, mechanisms and corner units (same parametric ``cabinet``)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from collections import Counter

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame
from archforge.kitchen.cabinets import (CORNER_ARM, FRONT, FRONT_STYLES, GAP, HANDLES, MECHANISMS, PANEL_RECESS,
                                        SHAKER_RAIL, TYPES, cabinet_boxes, cabinet_mesh, cabinet_prisms, cabinet_roles,
                                        default_params, footprint, front_counts, mechanisms_for, plan_marks)


# --- Frozen copy of the cabinet before front styles and mechanisms (regression reference) ---------------------
def _legacy_boxes(p):
    C, B, F, G = 0.018, 0.008, 0.019, 0.003
    w, d, h = float(p["width"]), float(p["depth"]), float(p["height"])
    kind = str(p.get("cabinet_type", "base"))
    plinth = min(float(p.get("plinth", 0.0)), h * 0.5)
    doors, drawers, shelves = int(p.get("doors", 0)), int(p.get("drawers", 0)), int(p.get("shelves", 0))
    handle = str(p.get("handle", "bar"))
    parts = []

    def box(role, x0, y0, z0, x1, y1, z1):
        if x1 - x0 > 1e-6 and y1 - y0 > 1e-6 and z1 - z0 > 1e-6:
            parts.append((role, (x0, y0, z0), (x1, y1, z1)))
    x0, x1 = -w / 2, w / 2
    yf, yb = -d / 2, d / 2
    yc = yf + F
    zb, zt = plinth, h
    if plinth > 0:
        box("plinth", x0 + C, yf + 0.05, 0.0, x1 - C, yb - B, plinth)
        box("carcass", x0, yc, 0.0, x0 + C, yb, plinth)
        box("carcass", x1 - C, yc, 0.0, x1, yb, plinth)
    box("carcass", x0, yc, zb, x0 + C, yb, zt)
    box("carcass", x1 - C, yc, zb, x1, yb, zt)
    box("carcass", x0 + C, yc, zb, x1 - C, yb - B, zb + C)
    box("carcass", x0 + C, yc, zt - C, x1 - C, yb - B, zt)
    box("carcass", x0 + C, yb - B, zb + C, x1 - C, yb, zt - C)
    inner0, inner1 = zb + C, zt - C
    drawer_h = 0.16 if doors else (zt - zb) / max(drawers, 1)
    if kind == "wardrobe" or kind == "tall":
        drawer_h = min(drawer_h, 0.25)
    z_split = zt - drawers * drawer_h if doors else zb
    for k in range(drawers):
        top = zt - k * drawer_h
        box("front", x0 + G, yf, top - drawer_h + G, x1 - G, yc, top - G)
        if handle != "none":
            hz = top - drawer_h / 2
            if handle == "bar":
                hw = min(0.16, w * 0.5)
                box("handle", -hw / 2, yf - 0.025, hz - 0.006, hw / 2, yf, hz + 0.006)
            else:
                box("handle", -0.012, yf - 0.025, hz - 0.012, 0.012, yf, hz + 0.012)
    if doors:
        leaf = w / doors
        for k in range(doors):
            lx0, lx1 = x0 + k * leaf + G, x0 + (k + 1) * leaf - G
            box("front", lx0, yf, zb + G, lx1, yc, z_split - G)
            if handle == "none":
                continue
            right_hinge = doors > 1 and k < doors / 2
            hx = lx1 - 0.04 if right_hinge or (doors == 1) else lx0 + 0.04
            if kind == "wall":
                hz0 = zb + 0.05
            elif kind in ("tall", "wardrobe"):
                hz0 = min(1.0, z_split - 0.25)
            else:
                hz0 = z_split - 0.20
            if handle == "bar":
                box("handle", hx - 0.006, yf - 0.025, hz0, hx + 0.006, yf, hz0 + 0.16)
            else:
                box("handle", hx - 0.012, yf - 0.025, hz0 + 0.06, hx + 0.012, yf, hz0 + 0.084)
    top_shelf_zone = z_split - C if doors and drawers else inner1
    for k in range(shelves):
        zs = inner0 + (top_shelf_zone - inner0) * (k + 1) / (shelves + 1)
        if kind == "wardrobe":
            zs = inner1 - 0.30 - k * 0.35
            if zs <= inner0 + 0.2:
                break
        box("shelf", x0 + C, yc + 0.02, zs - C / 2, x1 - C, yb - B, zs + C / 2)
    if kind == "wardrobe":
        zr = inner1 - 0.30 - (0.07 if shelves else 0.0) - 0.05
        box("rail", x0 + C, -0.01, zr - 0.01, x1 - C, 0.01, zr + 0.01)
    if float(p.get("worktop", 0.0)):
        box("worktop", x0, yf - 0.02, h, x1, yb, h + 0.04)
    return parts


OLD_TYPES = ('base', 'drawers', 'sink', 'wall', 'tall', 'wardrobe')


@pytest.mark.parametrize('kind', OLD_TYPES)
def test_defaults_give_exactly_the_old_cabinet(kind):
    for width in (0.4, 0.6, 0.9, 1.2):
        for handle in ('bar', 'knob', 'none'):
            for extra in ({}, {'front_style': 'flat', 'mechanism': 'none'}):
                p = default_params(kind, 1.0, 2.0, rotation=30.0, width=width)
                for key in ('front_style', 'mechanism'):
                    p.pop(key)                                  # a project saved before these parameters
                p.update(handle=handle, **extra)
                assert cabinet_boxes(p) == _legacy_boxes(p)
                assert cabinet_prisms(p) == []
    new = default_params(kind)
    assert (new['front_style'], new['mechanism']) == ('flat', 'none')


# --- Every style and mechanism: closed solids, inside the footprint ------------------------------------------
def _closed_and_inward(verts, tris):
    edges = Counter()
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            edges[e] += 1
    closed = all(n == 1 and edges[(b, a)] == 1 for (a, b), n in edges.items())
    vol = 0.0
    for a, b, c in tris:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = verts[a], verts[b], verts[c]
        vol += x1 * (y2 * z3 - y3 * z2) - x2 * (y1 * z3 - y3 * z1) + x3 * (y1 * z2 - y2 * z1)
    return closed, vol / 6


def _variants():
    for kind in TYPES:
        sizes = {'corner': (0.9, 1.0), 'corner_blind': (1.1, 1.2)}.get(kind, (0.4, 0.6, 0.9))
        for mech in mechanisms_for(kind):
            for style in FRONT_STYLES:
                for width in sizes:
                    yield kind, mech, style, width


@pytest.mark.parametrize('kind,mech,style,width', list(_variants()))
def test_every_style_and_mechanism_is_closed_and_inside_its_footprint(kind, mech, style, width):
    for handle in HANDLES:
        p = default_params(kind, width=width)
        p.update(mechanism=mech, front_style=style, handle=handle)
        verts, tris, roles = cabinet_mesh(p)
        closed, volume = _closed_and_inward(verts, tris)
        assert closed and volume < 0                    # every solid closed, wound like the carcass boxes
        w, d = p['width'], p['depth']
        xs, ys, zs = zip(*verts)
        assert -w / 2 - 1e-9 <= min(xs) and max(xs) <= w / 2 + 1e-9 and max(ys) <= d / 2 + 1e-9
        assert min(ys) >= -d / 2 - 0.0251                 # only handles and the worktop overhang stand proud
        assert min(zs) >= p['z'] - 1e-9
        assert max(zs) <= p['z'] + p['height'] + 0.04 + 1e-9
        assert {'carcass', 'front'} <= set(roles)
        if mech != 'none':
            assert 'mechanism' in roles
        Document().add(Entity('cabinet', p))


def test_front_counts_per_mechanism():
    def counts(kind, **changes):
        return front_counts(dict(default_params(kind), **changes))
    assert counts('base') == {'drawer': 1, 'door': 1}
    assert counts('base', mechanism='cargo', width=0.2) == {'pullout': 1}
    assert counts('sink', mechanism='bin') == {'pullout': 1}
    assert counts('base', mechanism='inner_drawers') == {'drawer': 1, 'door': 1}
    assert counts('wall', mechanism='lift_up') == {'flap': 1}
    assert counts('tall', mechanism='larder', width=0.4) == {'pullout': 1}
    assert counts('corner') == {'door': 2}
    assert counts('corner_blind') == {'blind': 1, 'door': 1}
    assert counts('wall', mechanism='cargo') == {'door': 1}            # a mechanism that does not fit is ignored
    # Inner drawers: three drawer boxes behind the door, five panels each.
    p = dict(default_params('base'), mechanism='inner_drawers')
    assert sum(r == 'mechanism' for r, _lo, _hi in cabinet_boxes(p)) == 15
    assert not any(r == 'shelf' for r, _lo, _hi in cabinet_boxes(p))


def test_shaker_glass_gola_and_edge_fronts():
    flat = default_params('wall')
    shaker = dict(flat, front_style='shaker')
    fronts = [(lo, hi) for r, lo, hi in cabinet_boxes(shaker) if r == 'front']
    assert len(fronts) == 5                                          # frame of four + panel
    panel = max(fronts, key=lambda b: (b[1][0] - b[0][0]) * (b[1][2] - b[0][2]))
    face = min(lo[1] for lo, _hi in fronts)
    assert panel[0][1] - face == pytest.approx(PANEL_RECESS)         # panel 5 mm deeper than the frame
    stile = min(fronts, key=lambda b: b[1][0] - b[0][0])
    assert stile[1][0] - stile[0][0] == pytest.approx(SHAKER_RAIL)
    glass = dict(flat, front_style='glass')
    assert sum(r == 'glass' for r in cabinet_roles(glass)) == 1 and 'glass' in [r for r, *_ in cabinet_boxes(glass)]
    # Gola: no handle sticks out; an aluminium channel sits behind the front plane.
    gola = dict(default_params('drawers'), front_style='gola')
    yf = -gola['depth'] / 2
    channels = [(lo, hi) for r, lo, hi in cabinet_boxes(gola) if r == 'handle']
    assert len(channels) == 3 and all(lo[1] > yf + FRONT - 0.005 for lo, _hi in channels)
    # Edge profile: one per front, along the grip edge.
    edge = dict(default_params('drawers'), handle='edge')
    profiles = [(lo, hi) for r, lo, hi in cabinet_boxes(edge) if r == 'handle']
    assert len(profiles) == 3 and all(hi[0] - lo[0] == pytest.approx(0.6 - 2 * GAP) for lo, hi in profiles)


def test_corner_unit_is_l_shaped_in_plan_with_the_carousel_dashed():
    doc = Document(); stack = CommandStack(doc)
    p = default_params('corner', 2.0, 1.0)
    assert (p['width'], p['depth'], p['mechanism']) == (0.9, 0.9, 'carousel')
    e = Entity('cabinet', p); stack.execute(AddEntity(e))
    outline = footprint(p)
    assert len(outline) == 6
    area = 0.5 * abs(sum(outline[i - 1][0] * outline[i][1] - outline[i][0] * outline[i - 1][1] for i in range(6)))
    free = 0.9 - CORNER_ARM
    assert area == pytest.approx(0.9 * 0.9 - free * free)
    prims = [q for q in build_plan_frame(doc).primitives if q.entity_id == e.id]
    assert any(q.role == 'cabinet' and len(q.points) == 6 for q in prims)
    assert any(q.role == 'cabinet-wall' for q in prims)              # carousel trays: hidden line
    stack.execute(UpdateEntity(e.id, {'mechanism': 'none'}))
    assert plan_marks(doc.get(e.id).params) == []
    assert [r for r, *_ in cabinet_prisms(doc.get(e.id).params)].count('shelf') == 1
    # Blind corner: the half-moon trays mirror with the blind side.
    b = default_params('corner_blind')
    left = plan_marks(b)[0]; right = plan_marks(dict(b, blind_side='right'))[0]
    assert max(x for x, _y in left) == pytest.approx(-min(x for x, _y in right))


def test_schema_accepts_new_choices_and_rejects_unknown():
    doc = Document(); stack = CommandStack(doc)
    e = Entity('cabinet', default_params('base')); stack.execute(AddEntity(e))
    for key, bad in (('front_style', 'baroque'), ('mechanism', 'rocket'), ('handle', 'rope'), ('blind_side', 'up')):
        with pytest.raises(ValueError):
            stack.execute(UpdateEntity(e.id, {key: bad}))
    for key in MECHANISMS:
        stack.execute(UpdateEntity(e.id, {'mechanism': key}))         # accepted; geometry ignores misfits
        cabinet_mesh(doc.get(e.id).params)
    with pytest.raises(ValueError):
        cabinet_mesh(dict(default_params('corner'), width=0.65))      # legs too short
    with pytest.raises(ValueError):
        cabinet_mesh(dict(default_params('corner_blind'), width=0.8))  # no room for the door


def test_style_and_mechanism_changes_undo_redo_and_save_load(tmp_path):
    doc = Document(); stack = CommandStack(doc)
    e = Entity('cabinet', default_params('sink', 1.0, 1.0)); stack.execute(AddEntity(e))
    before = cabinet_mesh(doc.get(e.id).params)
    stack.execute(UpdateEntity(e.id, {'front_style': 'shaker', 'mechanism': 'bin', 'handle': 'edge'}))
    after = cabinet_mesh(doc.get(e.id).params)
    assert after != before
    stack.undo()
    assert cabinet_mesh(doc.get(e.id).params) == before
    stack.redo()
    assert cabinet_mesh(doc.get(e.id).params) == after
    path = tmp_path / 'kitchen.archforge'
    doc.save(str(path))
    loaded = Document.load(str(path))
    assert loaded.get(e.id).params['mechanism'] == 'bin'
    assert cabinet_mesh(loaded.get(e.id).params) == after
    # An old project (no style/mechanism keys) loads and draws as before.
    old = {k: v for k, v in default_params('base', 3.0, 1.0).items() if k not in ('front_style', 'mechanism')}
    o = Entity('cabinet', old); stack.execute(AddEntity(o))
    doc.save(str(path))
    assert cabinet_boxes(Document.load(str(path)).get(o.id).params) == _legacy_boxes(old)


def test_kitchen_list_counts_cabinets_mechanisms_and_handles():
    from archforge.quantities.materials import all_lists, kitchen_list
    doc = Document(); stack = CommandStack(doc)
    for kind, changes in (('base', {}), ('base', {}), ('sink', {'mechanism': 'bin'}), ('corner', {}),
                          ('drawers', {'front_style': 'gola'})):
        stack.execute(AddEntity(Entity('cabinet', dict(default_params(kind), **changes))))
    rows = {desc: (unit, qty) for desc, unit, qty in kitchen_list(doc)}
    assert rows['Ντουλάπι βάσης 60×60×86 cm — πρόσοψη λεία'] == ('τεμ.', 2)
    assert rows['Μηχανισμός: Κάδοι απορριμμάτων συρόμενοι'] == ('τεμ.', 1)
    assert rows['Μηχανισμός: Καρουζέλ 3/4'] == ('τεμ.', 1)
    assert rows['Χερούλι μπάρα'] == ('τεμ.', 2 * 2 + 1 + 1)              # base: drawer + door; sink pull-out; corner
    assert rows['Προφίλ gola αλουμινίου'][0] == 'm' and rows['Προφίλ gola αλουμινίου'][1] == pytest.approx(1.8)
    assert 'Κουζίνα' in [s[0] for s in all_lists(doc)]


def test_3d_scene_has_see_through_glass_and_a_mechanism_part():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    doc = Document(); stack = CommandStack(doc)
    vitrine = Entity('cabinet', dict(default_params('wall', 1.0, 1.0), front_style='glass')); stack.execute(AddEntity(vitrine))
    corner = Entity('cabinet', default_params('corner', 3.0, 1.0)); stack.execute(AddEntity(corner))
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    parts = {o['render_part']: o for o in objs}
    assert parts[f'{vitrine.id}:glass']['material']['opacity'] < 1.0
    assert f'{corner.id}:mechanism' in parts and f'{corner.id}:worktop' in parts


def test_kitchen_items_place_mechanisms_and_inspector_changes_style_with_one_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.core.viewport import PointerEvent
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window.stack.execute(AddEntity(Entity('wall', {'x1': 0.0, 'y1': 0.0, 'z': 0.0, 'x2': 4.0, 'y2': 0.0, 'height': 2.7, 'thickness': 0.2})))
        defs = window._kitchen_defs
        assert {'Γωνιακό Γ 90×90 με καρουζέλ', 'Νεροχύτη με κάδους', 'Ψηλή συρόμενη αποθήκη'} <= set(defs)
        ctl = window.plan_view.controller
        ctl.set_component_definition(defs['Νεροχύτη με κάδους'])
        window._set_active_tool('component')
        ctl.pointer_down(PointerEvent(2.0, 0.5)); ctl.pointer_up(PointerEvent(2.0, 0.5))
        (cab,) = [e for e in window.doc.entities.values() if e.kind == 'cabinet']
        assert cab.params['mechanism'] == 'bin'
        window.doc.select([cab.id]); window.refresh_inspector()
        combos = window._cabinet_choices
        assert [combos['mechanism'].itemText(i) for i in range(combos['mechanism'].count())] == \
            [MECHANISMS[k][0] for k in mechanisms_for('sink')]
        depth = len(window.stack.done)
        combos['front_style'].setCurrentIndex(combos['front_style'].findData('shaker'))
        assert window.doc.get(cab.id).params['front_style'] == 'shaker'
        assert len(window.stack.done) == depth + 1                    # one UpdateEntity = one undo
        window.stack.undo()
        assert window.doc.get(cab.id).params.get('front_style', 'flat') == 'flat'
        dialog = window._open_object_modifier(cab.id)
        dialog.set_param('cabinet_type', 'corner')
        p = window.doc.get(cab.id).params
        assert (p['width'], p['depth'], p['mechanism'], p['doors']) == (0.9, 0.9, 'carousel', 2)
        window.stack.undo()
        assert window.doc.get(cab.id).params['cabinet_type'] == 'sink'
    finally:
        window._mark_clean(); window.close(); app.processEvents()
