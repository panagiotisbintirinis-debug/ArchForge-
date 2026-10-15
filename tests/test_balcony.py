"""Owner (2026-10-14): «πλήρες διώροφο … μπαλκόνια» — a balcony slab drawn outside the walls, with its railing."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.balcony import THICKNESS, balcony_entities
from archforge.core.commands import AddEntities, AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _box(stack, z, w=10.0, d=8.0):
    pts = [(0, 0), (w, 0), (w, d), (0, d)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z,
                                                'height': 2.7, 'thickness': 0.25})))


def test_balcony_slab_top_is_the_storey_and_railing_skips_the_wall_side():
    doc = Document(); stack = CommandStack(doc)
    _box(stack, 3.0)
    slab, *railings = balcony_entities(doc, [(2, 0), (6, 0), (6, -1.5), (2, -1.5)], level_z=3.0)
    assert slab.kind == 'floor'
    assert slab.params['z'] + slab.params['thickness'] == pytest.approx(3.0)
    assert slab.params['thickness'] == pytest.approx(THICKNESS)
    from archforge.architecture.stairs import discover_building_levels
    stack.execute(AddEntities([slab]))
    # Reported in the walk-through: the tree showed a phantom «2ος όροφος (+2.82 m)» for the slab.
    assert [round(i['elevation'], 3) for i in discover_building_levels(doc)] == [0.0, 3.0]
    from archforge.ui.project_outline import entity_level, _levels
    doc.levels['1ος'] = 3.0
    assert entity_level(doc, doc.get(slab.id)) == '1ος'          # under its storey in the tree, not the one below
    stack.undo()
    assert len(railings) == 1
    r = railings[0].params
    assert r['z'] == pytest.approx(3.0) and r['closed'] == 0 and r['height'] >= 1.0
    # The three free sides, in order; not the side against the wall (y = 0).
    assert [tuple(map(float, q[:2])) for q in r['points']] == [(6, 0), (6, -1.5), (2, -1.5), (2, 0)]
    stack.execute(AddEntities([slab, *railings]))
    assert {e.kind for e in doc.entities.values()} >= {'floor', 'railing'}
    stack.undo()
    assert not any(e.kind in ('floor', 'railing') for e in doc.entities.values())


def test_free_standing_balcony_or_terrace_gets_a_closed_railing_and_other_storeys_walls_do_not_count():
    doc = Document(); stack = CommandStack(doc)
    _box(stack, 0.0)                                   # walls of the storey BELOW do not hold the balcony side
    slab, railing = balcony_entities(doc, [(2, 0), (6, 0), (6, -1.5), (2, -1.5)], level_z=3.0)
    assert railing.params['closed'] == 1 and len(railing.params['points']) == 4


def test_side_along_a_wall_split_by_an_inner_wall_still_has_no_railing():
    """Walk-through 14/10: the 1st-floor south wall was two walls (inner wall at x=5) -> closed railing."""
    doc = Document(); stack = CommandStack(doc)
    for x1, x2 in ((0, 5), (5, 10)):
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': 0, 'x2': x2, 'y2': 0, 'z': 3.0, 'height': 2.7, 'thickness': 0.25})))
    _slab, railing = balcony_entities(doc, [(1, 0), (9, 0), (9, -1.5), (1, -1.5)], level_z=3.0)
    assert railing.params['closed'] == 0 and len(railing.params['points']) == 4


def test_too_small_outline_is_refused():
    with pytest.raises(ValueError):
        balcony_entities(Document(), [(0, 0), (0.1, 0), (0.1, 0.1)], level_z=0.0)


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def test_drawn_in_the_plan_from_the_menus_and_undone_in_one_step(window):
    from archforge.ui import slab_tools
    from archforge.ui.marking_menu import all_ids, build_menu
    _box(window.stack, 0.0)
    menu = build_menu(window, 'plan')
    assert 'mm:slab:balcony' in all_ids(menu['entries'])          # «Πλάκα ▸» in the mouse menu
    texts = [a.text() for a in window._slab_opening_actions]
    assert any('Μπαλκόνι' in t for t in texts)
    slab_tools.start_balcony_tool(window)
    assert window.plan_view.controller.tool == 'balcony'
    before = len(window.doc.entities)
    window.plan_view.finish_slab_opening([[2, 0], [6, 0], [6, -1.5], [2, -1.5]])
    kinds = sorted(e.kind for e in list(window.doc.entities.values())[before:])
    assert kinds == ['floor', 'railing']
    window._undo()
    assert len(window.doc.entities) == before


def _right_click(window, x, y):
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QContextMenuEvent
    view = window.plan_view; view.redraw()
    pos = view.mapFromScene(QPointF(x, y))
    view.hide_marking_menu()
    view.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, view.viewport().mapToGlobal(pos)))
    return view._marking_menu.menu


def test_mouse_menu_inside_a_balcony_is_not_its_railing_and_titles_are_greek(window):
    """Walk-through 14/10: right click inside the balcony said «railing: …» (the open railing took the whole area)."""
    from archforge.ui import slab_tools
    _box(window.stack, 0.0)
    window.resize(1400, 900); window.show(); window.plan_view.centerOn(5, 0)
    slab_tools.place_balcony(window, [[2, 0], [6, 0], [6, -1.5], [2, -1.5]])
    window.plan_view.controller.set_tool('select')
    inside = _right_click(window, 4, -0.7)
    assert 'railing' not in inside['center'] and inside['center'].startswith('Πλάκα')
    on_rail = _right_click(window, 4, -1.5)
    assert on_rail['center'].startswith('Κάγκελ')
    wall = _right_click(window, 1, 0)
    assert wall['center'].count('Τοίχος') == 1


def test_room_choices_only_when_the_right_click_is_inside_a_room(window):
    from archforge.ui.marking_menu import all_ids, build_menu
    _box(window.stack, 0.0)
    ids = lambda m: set(all_ids(m['entries']))
    outside, inside = build_menu(window, 'plan', xy=(5, -3)), build_menu(window, 'plan', xy=(5, 4))
    # (no «Κουζίνα εδώ» any more: the kitchen is drawn freely — owner 15/10)
    room_only = {'mm:layout:bath', 'mm:roofroom:tiled', 'mm:slab:atrium', 'mm:drywall:room'}
    assert room_only <= ids(inside) and not room_only & ids(outside)
    assert {'mm:slab:balcony', 'mm:slab:draw'} <= ids(outside)
