"""Project questions at the start (new/renovation, walls, dimensions, floors), phases and take-off."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.project.brief import get_brief, load_bearing_walls, wall_defaults


def _brief(stack, **answers):
    e = Entity('project_brief', {'project_type': 'new', 'wall_system': 'brick_double_insulated', 'measure': 'exterior',
                                 'floor_system': 'rc_slab', **answers})
    stack.execute(AddEntity(e))
    return e


def _box(stack, x=10.0, y=10.0, t=0.5, extra=()):
    ids = []
    for s in [(0, 0, x, 0), (x, 0, x, y), (x, y, 0, y), (0, y, 0, 0), *extra]:
        w = Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0, 'height': 2.7, 'thickness': t})
        stack.execute(AddEntity(w)); ids.append(w.id)
    return ids


def test_answers_live_in_the_document_and_set_the_wall_tool():
    doc = Document(); st = CommandStack(doc)
    assert get_brief(doc) is None and wall_defaults(doc) == (None, 0.15)
    _brief(st, wall_system='stone_bearing')
    assert wall_defaults(doc) == ('stone_uninsulated', pytest.approx(0.54))
    assert load_bearing_walls(doc)
    with pytest.raises(ValueError):
        st.execute(AddEntity(Entity('project_brief', {'project_type': 'castle'})))


def test_stone_bearing_walls_need_no_columns_and_the_assistant_says_why():
    from archforge.assistant.suggestions import propose
    from archforge.structure.layout import propose_frame
    doc = Document(); st = CommandStack(doc)
    assert any(p.key == 'B-0' for p in propose(doc))                       # questions first
    _brief(st, wall_system='stone_bearing'); _box(st)
    assert propose_frame(doc)[0] == []
    keys = [p.key for p in propose(doc)]
    assert 'S-4' in keys and 'S-3' not in keys and 'B-0' not in keys


def test_renovation_existing_columns_cannot_move():
    doc = Document(); st = CommandStack(doc)
    _brief(st, project_type='renovation', measure='interior')
    col = Entity('structural_column', {'x': 0, 'y': 0, 'z': 0, 'width': .4, 'depth': .4, 'height': 3, 'rotation': 0,
                                       'role': 'structural', 'construction': 'reinforced_concrete', 'section': 'rectangular',
                                       'base_level': 'Ground', 'top_level': 'Unassigned', 'phase': 'existing'})
    st.execute(AddEntity(col))
    with pytest.raises(ValueError, match='υφιστάμενο'):
        st.execute(MoveEntities([col.id], 1.0, 0.0))
    with pytest.raises(ValueError):
        st.execute(UpdateEntity(col.id, {'phase': 'old'}))


def test_take_off_per_room_net_of_wall_thickness_openings_and_wet_tiles():
    """10×10 on the outside with 50 cm stone → 9×9 inside (the owner's example)."""
    from archforge.quantities.takeoff import take_off, to_csv
    doc = Document(); st = CommandStack(doc)
    # Axes 9.5 × 9.5 so the outside is exactly 10 × 10 with 50 cm walls.
    ids = _box(st, x=9.5, y=9.5, t=0.5)
    r = take_off(doc)
    room = r['rooms'][0]
    assert room['floor_m2'] == pytest.approx(81.0) and room['perimeter_m'] == pytest.approx(36.0)
    assert room['walls_m2'] == pytest.approx(36.0 * 2.7)
    st.execute(AddEntity(Entity('door', {'offset': 2.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=ids[0])))
    st.execute(AddEntity(Entity('window', {'offset': 6.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=ids[0])))
    room = take_off(doc)['rooms'][0]
    assert room['openings_m2'] == pytest.approx(0.9 * 2.1 + 1.2 * 1.4)
    assert room['skirting_m'] == pytest.approx(36.0 - 0.9)
    # A WC: wall tiles to 2.10 m, minus the openings below 2.10 m.
    st.execute(AddEntity(Entity('plumbing_point', {'x': 1.0, 'y': 1.0, 'z': 0.0, 'point_type': 'wc'})))
    wc = take_off(doc)['rooms'][0]
    below = 0.9 * 2.1 + 1.2 * (2.1 - 0.9)
    assert wc['wall_tiles_m2'] == pytest.approx(36.0 * 2.1 - below) and wc['skirting_m'] == 0.0
    assert wc['paint_walls_m2'] == pytest.approx(wc['walls_m2'] - wc['wall_tiles_m2'])
    # Demolition of a wall marked in a renovation.
    st.execute(UpdateEntity(ids[1], {'phase': 'demolish'}))
    demo = take_off(doc)['demolition']
    assert demo['count'] == 1 and demo['walls_m2'] == pytest.approx(9.5 * 2.7, abs=0.01) and demo['walls_m3'] == pytest.approx(9.5 * 2.7 * 0.5, abs=0.01)
    assert 'Πλακάκια τοίχου m²' in to_csv(take_off(doc)).splitlines()[0]


def test_new_project_asks_and_menus_exist():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        assert w._brief_action.text() == 'Στοιχεία έργου (ερωτήσεις)…'
        assert [a.text() for a in w._renovation_menu.actions()][0].startswith('Όλα τα σχεδιασμένα')
        w._apply_project_brief({'project_type': 'renovation', 'wall_system': 'stone_bearing', 'measure': 'interior',
                                'floor_system': 'timber'})
        top = w.project_tree.topLevelItem(0).child(0).text(0)
        assert top.startswith('Στοιχεία έργου · Ανακαίνιση · Πέτρινοι φέροντες')
        ids = _box(w.stack)
        assert w._set_phase(list(w.doc.entities), 'existing') == len(ids)
        w._no_modal_dialogs = True
        result = w._show_takeoff()
        assert result['rooms'] and 'Επιμέτρηση εργασιών' in w._takeoff_view.toHtml()
        w.stack.undo()                                                   # phases undo in one step
        assert all(w.doc.get(i).params.get('phase', 'new') == 'new' for i in ids)
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_interior_walls_question_drywall_brick_or_bearing_min_25():
    from archforge.project.brief import INTERIOR_WALLS, QUESTIONS, interior_wall_defaults
    assert 'interior_walls' in [q[0] for q in QUESTIONS]
    assert {'drywall_single', 'drywall_double', 'brick_plaster', 'bearing'} <= set(INTERIOR_WALLS)
    doc = Document(); st = CommandStack(doc)
    assert interior_wall_defaults(doc) is None
    e = _brief(st)                                                     # older briefs: brick with plaster
    assert interior_wall_defaults(doc) == ('brick_partition', pytest.approx(0.13), False)
    for key, (wtype, thick, bearing) in {'drywall_single': ('drywall_100', 0.10, False),
                                         'drywall_double': ('drywall_double_125', 0.125, False),
                                         'bearing': ('bearing_interior_25', 0.29, True)}.items():
        st.execute(UpdateEntity(e.id, {'interior_walls': key}))
        t, th, b = interior_wall_defaults(doc)
        assert (t, b) == (wtype, bearing) and th == pytest.approx(thick)
        assert not b or th >= 0.25
    with pytest.raises(ValueError):
        st.execute(UpdateEntity(e.id, {'interior_walls': 'cardboard'}))


def _draw_wall(doc, stack, a, b):
    from archforge.core.viewport import PointerController, PointerEvent
    c = PointerController(doc, stack); c.snap_enabled = False; c.tool = 'wall'
    c.pointer_down(PointerEvent(*a)); c.pointer_move(PointerEvent(*b)); c.pointer_up(PointerEvent(*b))
    return [w for w in doc.entities.values() if w.kind == 'wall'][-1]


def test_a_wall_drawn_inside_a_closed_space_takes_the_interior_type_in_one_undo():
    doc = Document(); st = CommandStack(doc)
    _brief(st, interior_walls='drywall_double')
    _box(st, 8.0, 6.0, t=0.35)
    w = _draw_wall(doc, st, (4.0, 0.5), (4.0, 5.5))
    assert w.params['wall_type'] == 'drywall_double_125' and w.params['thickness'] == pytest.approx(0.125)
    st.undo()
    assert w.id not in doc.entities                                    # wall and its type: one step
    outside = _draw_wall(doc, st, (9.0, 0.0), (12.0, 0.0))             # outside the shell: exterior system
    assert outside.params.get('wall_type') == 'brick_double_insulated'


def test_bearing_interior_walls_under_25cm_get_an_assistant_fix():
    from archforge.assistant.suggestions import apply, propose
    doc = Document(); st = CommandStack(doc)
    _brief(st, interior_walls='bearing')
    ids = _box(st, 8.0, 6.0, t=0.35, extra=[(4, 0, 4, 6)])
    st.execute(UpdateEntity(ids[-1], {'thickness': 0.15}))
    (p,) = [p for p in propose(doc) if p.key == 'W-1']
    assert p.targets == (ids[-1],)
    apply(st, p)
    assert doc.get(ids[-1]).params['thickness'] == pytest.approx(0.29) and doc.get(ids[-1]).params['load_bearing']
    assert not [p for p in propose(doc) if p.key == 'W-1']
    assert doc.get(ids[0]).params['thickness'] == pytest.approx(0.35)  # the shell is not touched


def test_wall_answers_are_editable_typed_type_with_thickness():
    from archforge.project.brief import custom_answer, interior_wall_defaults, parse_custom
    assert parse_custom('γυψοσανίδα 15 cm') == ('γυψοσανίδα 15 cm', 0.15)
    assert parse_custom('τσιμεντόλιθος 0,30') == ('τσιμεντόλιθος 0,30', 0.30)
    assert custom_answer('κάτι χωρίς πάχος') is None
    doc = Document(); st = CommandStack(doc)
    _brief(st, wall_system='custom', wall_system_text='τσιμεντόλιθος 30 cm', wall_system_thickness=0.30,
           interior_walls='custom', interior_walls_text='γυψοσανίδα 15', interior_walls_thickness=0.15)
    assert wall_defaults(doc) == ('generic', pytest.approx(0.30))
    assert interior_wall_defaults(doc) == ('generic', pytest.approx(0.15), False)
    assert get_brief(doc)['interior_walls_text'] == 'γυψοσανίδα 15'


def test_brief_dialog_lists_are_editable_and_typed_text_becomes_custom():
    from PySide6.QtWidgets import QApplication, QComboBox
    from archforge.project.brief import QUESTIONS
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        combos = {}
        for key, _q, options in QUESTIONS:
            c = QComboBox(); c.setEditable(key in ('wall_system', 'interior_walls'))
            for value, label in options.items():
                c.addItem(label[0] if isinstance(label, tuple) else label, value)
            combos[key] = c
        combos['interior_walls'].setEditText('Γυψοσανίδα 15 cm με ορυκτοβάμβακα')
        answers = window._brief_answers(combos)
        assert answers['interior_walls'] == 'custom' and answers['interior_walls_thickness'] == pytest.approx(0.15)
        assert answers['wall_system'] == combos['wall_system'].currentData()
        window._apply_project_brief(answers)
        from archforge.project.brief import interior_wall_defaults
        assert interior_wall_defaults(window.doc)[1] == pytest.approx(0.15)
    finally:
        window._mark_clean(); window.close(); app.processEvents()
