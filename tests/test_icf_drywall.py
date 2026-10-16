"""ICF blocks and plasterboard (suspended ceilings, stud walls): catalogue, entity and the material take-off."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.wall_types import WALL_TYPES, indicative_u, total_thickness
from archforge.core.commands import AddEntity, CommandStack, DeleteEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.construction import drywall as D
from archforge.construction.icf import (BLOCKS, BLOCKS_PER_M2, concrete_per_m2, count_wall, take_off_icf, thickness,
                                        wall_type_of)


def _wall(stack, x1, y1, x2, y2, wall_type, z=0.0, h=3.0, t=None):
    w = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': h,
                        'thickness': t or total_thickness(wall_type), 'wall_type': wall_type}, name='Τ')
    stack.execute(AddEntity(w))
    return w


def _box(stack, w, d, wall_type='generic', t=0.2, h=3.0):
    pts = [(0, 0), (w, 0), (w, d), (0, d)]
    return [_wall(stack, *pts[i], *pts[(i + 1) % 4], wall_type, h=h, t=t) for i in range(4)]


# --- ICF -------------------------------------------------------------------------------------------

def test_icf_catalogue_as_wall_types_without_brand():
    assert BLOCKS_PER_M2 == pytest.approx(1 / 0.48)
    for code, (label, eps, core, _l) in BLOCKS.items():
        t = wall_type_of(code)
        assert t in WALL_TYPES and total_thickness(t) == pytest.approx(thickness(code)) == pytest.approx(2 * eps + core)
        assert label.startswith('ICF EPS') and 'πυρήνας' in label
        assert indicative_u(t) < 0.35                                  # EPS both faces
    assert {round(c, 2) for _l, _e, c, _x in BLOCKS.values()} == {0.15, 0.20, 0.25}
    assert concrete_per_m2('20/75') == (190.0, False) and concrete_per_m2('15/65')[1] is True


def test_icf_wall_10_by_3_with_one_window():
    doc = Document(); st = CommandStack(doc)
    w = _wall(st, 0, 0, 10, 0, wall_type_of('20/75'))
    st.execute(AddEntity(Entity('window', {'offset': 5, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=w.id)))
    r = count_wall(doc, w)
    assert r['net_m2'] == pytest.approx(28.32) and r['courses'] == 8
    assert r['blocks'] == 62                                   # ⌈28.32 / 0.48 × 1.05⌉ = ⌈61.95⌉
    assert r['corner_blocks'] == 0 and r['free_ends'] == 2
    assert r['closures_m'] == pytest.approx(2 * (1.2 + 1.4) + 2 * 3.0)
    assert r['concrete_m3'] == pytest.approx(28.32 * 0.19, abs=0.01)


def test_icf_corners_per_course_and_storey_and_brief():
    from archforge.project.brief import WALL_SYSTEMS, load_bearing_walls, wall_defaults
    from archforge.assistant.suggestions import propose
    doc = Document(); st = CommandStack(doc)
    t = wall_type_of('15/75')
    st.execute(AddEntity(Entity('project_brief', {'wall_system': t})))
    assert wall_defaults(doc) == (t, pytest.approx(0.30)) and load_bearing_walls(doc)
    assert sum(k.startswith('icf_') for k in WALL_SYSTEMS) == len(BLOCKS)
    walls = _box(st, 10, 6, t, t=0.30)
    r = take_off_icf(doc)
    assert r['totals']['corner_blocks'] == 4 * 8 and r['totals']['closures_m'] == 0
    # each corner block stands in for one straight block
    assert r['totals']['blocks'] == sum(w['blocks'] for w in r['walls'])
    assert abs(r['totals']['blocks'] - (96 * BLOCKS_PER_M2 - 32) * 1.05) < 4
    assert set(r['by_storey']) == {0.0}
    keys = {p.key for p in propose(doc)}
    assert 'I-2' in keys
    (s4,) = [p for p in propose(doc) if p.key == 'S-4']
    assert 'ICF' in s4.title and 'κολόνες' in s4.title
    st.execute(UpdateEntity(walls[0].id, {'wall_type': 'generic'}))
    assert take_off_icf(doc)['totals']['corner_blocks'] == 2 * 8          # one leg left at two corners


def test_icf_list_sheet_with_prices(tmp_path):
    import zipfile
    from archforge.construction.icf import icf_list
    from archforge.quantities.materials import all_lists, write_workbook
    doc = Document(); st = CommandStack(doc)
    _box(st, 8, 5, wall_type_of('25/65'), t=0.38)
    rows = icf_list(doc)
    assert any('γωνιακό' in r[0] for r in rows) and any(r[2] is None for r in rows)
    assert 'ICF' in [s[0] for s in all_lists(doc)]
    path = write_workbook(doc, str(tmp_path / 'icf.xlsx'), only=('ICF',))
    with zipfile.ZipFile(path) as z:
        assert 'name="ICF"' in z.read('xl/workbook.xml').decode()


# --- suspended plasterboard ceiling ------------------------------------------------------------------

def _rect(w=5, d=4):
    return [[0, 0], [w, 0], [w, d], [0, d]]


def test_ceiling_4_by_5_take_off():
    doc = Document(); st = CommandStack(doc)
    c = Entity('drywall_ceiling', D.default_params(points=_rect()), name='Ψ')
    st.execute(AddEntity(c))
    r = D.count_ceiling(doc, c)
    assert r['area_m2'] == 20 and r['perimeter_m'] == 18
    assert (r['main_lines'], r['secondary_lines']) == (4, 10)           # CD at 1.00 / 0.50 m
    assert r['cd_m'] == pytest.approx((4 * 5 + 10 * 4) * 1.05) and r['cd_bars'] == 16
    assert r['hangers'] == 24 and r['anchors'] == 24                    # ⌈5 / 0.90⌉ per main
    assert r['cross_connectors'] == 40 and r['extensions'] == 4
    assert r['ud_m'] == pytest.approx(18.9) and r['ud_fixings'] == 29
    assert r['board_m2'] == pytest.approx(22.0) and r['sheets'] == 10
    assert r['screws_25'] == 374 and r['screws_35'] == 0
    assert r['joint_tape_m'] == pytest.approx(28.0) and r['compound_kg'] == pytest.approx(6.0)
    assert r['hanger_type'] == 'nonius'                                 # 20 cm > 12.5 cm
    st.execute(UpdateEntity(c.id, {'layers': 2, 'insulation': 0.05, 'drop': 0.10}))
    r = D.count_ceiling(doc, doc.get(c.id))
    assert r['board_m2'] == pytest.approx(44.0) and r['screws_35'] == 374 and r['insulation_m2'] == pytest.approx(21.0)
    assert r['hanger_type'] == 'direct'


def test_ceiling_l_shape_clips_the_grid():
    doc = Document(); st = CommandStack(doc)
    pts = [[0, 0], [6, 0], [6, 2], [3, 2], [3, 4], [0, 4]]               # 18 m²
    c = Entity('drywall_ceiling', D.default_params(points=pts))
    st.execute(AddEntity(c))
    r = D.count_ceiling(doc, c)
    assert r['area_m2'] == 18
    main_m = r['cd_m'] / 1.05
    assert main_m == pytest.approx(18 / 1.0 + 18 / 0.5)                  # lines clipped to the outline


def test_ceiling_schema_rejects_bad_values():
    doc = Document(); st = CommandStack(doc)
    for bad in ({'board': 'gold'}, {'layers': 3}, {'drop': 0.01}, {'cove': 1, 'cove_depth': 0.5}):
        p = D.default_params(points=_rect()); p.update(bad)
        with pytest.raises(ValueError):
            st.execute(AddEntity(Entity('drywall_ceiling', p)))
    with pytest.raises(ValueError):
        st.execute(AddEntity(Entity('drywall_ceiling', {'level_z': 0.0})))


def _bath(st, doc):
    _box(st, 5.2, 4.2)                                  # net 5.0 × 4.0 inside 20 cm walls
    from archforge.architecture.room_identity import reconcile_room_bindings
    ((face, rid),) = reconcile_room_bindings(doc, z=0.0)
    doc.room_data[face.signature] = {'name': 'Μπάνιο', 'use': 'Μπάνιο'}
    return rid


def _watertight(v, t):
    edges = {}
    for tri in t:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges[(a, b)] = edges.get((a, b), 0) + 1
    return all(edges.get((b, a), 0) == n for (a, b), n in edges.items())


def test_room_ceiling_follows_the_room_proposes_moisture_board_and_round_trips(tmp_path):
    from archforge.core.plan_scene import build_plan_frame
    from archforge.project.persistence import load_project, save_project
    doc = Document(); st = CommandStack(doc)
    rid = _bath(st, doc)
    p = D.default_params(room_id=rid)
    assert D.suggested_board(doc, p) == 'moisture'
    c = Entity('drywall_ceiling', dict(p, board='moisture'), name='Ψευδοροφή Μπάνιο')
    st.execute(AddEntity(c))
    r = D.count_ceiling(doc, c)
    assert r['area_m2'] == pytest.approx(20.0) and r['hangers'] == 24 and r['cross_connectors'] == 40
    assert r['level_m'] == pytest.approx(2.80)
    v, t, _roles = D.ceiling_mesh(doc, c.params)
    zs = [q[2] for q in v]
    assert min(zs) == pytest.approx(2.80) and max(zs) == pytest.approx(2.8125) and _watertight(v, t)
    frame = build_plan_frame(doc)
    assert any(q.role == 'drywall-ceiling' for q in frame.primitives)
    assert any(dict(q.meta).get('text') == 'Ψ/Ο +2,80' for q in frame.primitives)
    st.undo(); assert c.id not in doc.entities
    st.redo(); assert c.id in doc.entities
    path = str(tmp_path / 'c.archforge')
    save_project(doc, path)
    report = load_project(path)
    back = report.doc
    assert not report.skipped
    assert back.get(c.id).params['board'] == 'moisture' and D.count_ceiling(back, back.get(c.id))['area_m2'] == pytest.approx(20.0)
    st.execute(DeleteEntities([c.id])); assert c.id not in doc.entities


def test_cove_ceiling_mesh_has_a_step_and_its_materials():
    doc = Document(); st = CommandStack(doc)
    c = Entity('drywall_ceiling', dict(D.default_params(points=_rect()), cove=1, drop=0.25))
    st.execute(AddEntity(c))
    v, t, roles = D.ceiling_mesh(doc, c.params)
    assert _watertight(v, t) and 'band' in roles
    zs = sorted({round(q[2], 4) for q in v})
    assert zs[0] == pytest.approx(2.70 - 0.25) and zs[-1] == pytest.approx(2.70 - 0.25 + 0.10 + 0.0125)
    r = D.count_ceiling(doc, c)
    assert r['cove_m'] == pytest.approx(2 * (4.4 + 3.4)) and r['cove_board_m2'] == pytest.approx(r['cove_m'] * 0.10)
    from archforge.geometry.mesh import TessellatedPreviewBackend  # noqa: F401  (3D path wired)
    from archforge.geometry.mesh import _payload
    from archforge.geometry.plan import EvaluationNode
    node = EvaluationNode(c.id, 'drywall_ceiling', dict(c.params), None, None, ())
    assert len(_payload(doc, node).triangles) == len(t)


def test_drywall_walls_and_sheet(tmp_path):
    import zipfile
    from archforge.quantities.materials import all_lists, write_workbook
    doc = Document(); st = CommandStack(doc)
    w = _wall(st, 0, 0, 5, 0, 'drywall_100', h=2.8)
    st.execute(AddEntity(Entity('door', {'offset': 2.5, 'width': 0.9, 'height': 2.1}, parent_id=w.id)))
    r = D.count_wall(doc, w)
    assert r['net_m2'] == pytest.approx(14.0 - 1.89)
    assert r['studs'] == 9 + 2                                          # ⌈5 / 0.625⌉ + 1, + 2 at the jambs
    assert r['uw_m'] == pytest.approx((10 - 0.9) * 1.05, abs=0.01)
    assert r['board_m2'] == pytest.approx(2 * 12.11 * 1.10, abs=0.01)
    st.execute(AddEntity(Entity('drywall_ceiling', D.default_params(points=_rect()))))
    sheets = {s[0]: s for s in all_lists(doc)}
    rows = sheets['Γυψοσανίδες'][2]
    assert any('CD 60/27' in d for d, _u, _q in rows) and any('CW 75' in d for d, _u, _q in rows)
    assert any('προς επιβεβαίωση' in n for n in sheets['Γυψοσανίδες'][3])
    path = write_workbook(doc, str(tmp_path / 'g.xlsx'), only=('Γυψοσανίδες',))
    with zipfile.ZipFile(path) as z:
        assert 'Γυψοσανίδες' in z.read('xl/workbook.xml').decode()


def test_window_tools_place_one_undo_and_menus():
    from PySide6.QtWidgets import QApplication
    from archforge.ui import drywall_tools
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow(); window._no_modal_dialogs = True
    try:
        rid = _bath(window.stack, window.doc)
        assert window._drywall_menu.actions() and window._icf_action
        n = len(window.stack.undo_stack) if hasattr(window.stack, 'undo_stack') else None
        c = drywall_tools.place_in_room(window, 2.6, 2.1)
        assert c is not None and c.params['room_id'] == rid and c.params['board'] == 'moisture'
        assert drywall_tools.place_in_room(window, 2.6, 2.1) is None                # already has one
        window.plan_view.drywallCeilingRequested.emit([[6, 0], [8, 0], [8, 2], [6, 2]])
        assert sum(e.kind == 'drywall_ceiling' for e in window.doc.entities.values()) == 2
        window.stack.undo()
        assert sum(e.kind == 'drywall_ceiling' for e in window.doc.entities.values()) == 1
        window.doc.select([c.id]); window.refresh_inspector()
        result = drywall_tools.show_drywall(window)
        assert result['ceilings'] and 'Ψευδοροφές' in window._drywall_view.toPlainText()
        _wall(window.stack, 0, 10, 10, 10, wall_type_of('20/75'))
        assert drywall_tools.show_icf(window)['totals']['blocks'] > 0
        del n
    finally:
        window._mark_clean(); window.close(); app.processEvents()
