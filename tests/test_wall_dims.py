"""Owner 15/10: «εμφανείς διαστάσεις με επιλογή και δυνατότητα μετακίνησης τοίχου με διπλό κλικ»."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.wall_dims import offset_for, wall_dims
from archforge.architecture.wall_edit import MoveWall
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _house(doc, st):
    ids = {}
    for name, (x1, y1, x2, y2) in {'s': (0, 0, 10, 0), 'e': (10, 0, 10, 8), 'n': (10, 8, 0, 8), 'w': (0, 8, 0, 0),
                                   'mid': (6, 0, 6, 8)}.items():
        e = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.25})
        st.execute(AddEntity(e)); ids[name] = e.id
    return ids


def test_length_and_clear_distances_to_the_facing_walls():
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    d = wall_dims(doc, ids['mid'])
    assert abs(d['length']['value'] - 8.0) < 1e-9
    clears = sorted(round(s['clear'], 3) for s in d['sides'])
    assert clears == [3.75, 5.75]                                   # face to face, both rooms
    assert {s['neighbour'] for s in d['sides']} == {ids['w'], ids['e']}
    # Live while moving: the same numbers with the wall shifted.
    moved = sorted(round(s['clear'], 3) for s in wall_dims(doc, ids['mid'], 0.5)['sides'])
    assert moved == [3.25, 6.25]


def test_typing_a_distance_moves_the_wall_with_what_is_joined_in_one_undo():
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    side = next(s['side'] for s in wall_dims(doc, ids['mid'])['sides'] if s['neighbour'] == ids['e'])
    st.execute(MoveWall(ids['mid'], offset_for(doc, ids['mid'], side, 3.0)))
    after = {s['neighbour']: round(s['clear'], 3) for s in wall_dims(doc, ids['mid'])['sides']}
    assert after == {ids['e']: 3.0, ids['w']: 6.5}
    st.undo()
    assert abs(float(doc.get(ids['mid']).params['x1']) - 6.0) < 1e-9


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 950); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def test_click_selects_the_wall_with_its_distances_then_press_and_drag_moves_it(window):
    """Owner 15/10 «εμφανείς διαστάσεις με επιλογή» · 24/10 (as in Home Designer / ArchiCAD): a click selects (its
    distances show), pressing and dragging the wall moves it — it never follows the mouse."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    w, app = window
    ids = _house(w.doc, w.stack)
    view = w.plan_view
    view.fitInView(QRectF(-1, -1, 12, 10)); w.snap_action.setChecked(True); view.set_grid_step(0.10)
    vp = view.viewport()
    at = lambda x, y: view.mapFromScene(QPointF(x, y))
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.0, 3.0)); app.processEvents()
    assert w.doc.selection == [ids['mid']]                               # one click: selected
    tool = w._wall_dims
    assert tool.moving is None
    view.redraw()
    assert sorted(item.toPlainText().strip() for item, _side in tool._labels) == ['3,75', '5,75', '8,00']
    n_before = len(w.stack.done)
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.0, 3.0))
    for x in (6.1, 6.3, 6.5):
        QTest.mouseMove(vp, at(x, 3.0)); app.processEvents()
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.5, 3.0)); app.processEvents()
    assert abs(float(w.doc.get(ids['mid']).params['x1']) - 6.5) < 0.051 and len(w.stack.done) == n_before + 1
    w._undo()
    assert abs(float(w.doc.get(ids['mid']).params['x1']) - 6.0) < 1e-6


def test_one_click_on_a_distance_types_the_value(window, monkeypatch):
    """Owner 24/10, as in Home Designer: «click on the dimension string itself, enter the desired dimension»."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QInputDialog
    w, app = window
    ids = _house(w.doc, w.stack)
    view = w.plan_view
    view.fitInView(QRectF(-1, -1, 12, 10))
    w.doc.select([ids['mid']]); view.redraw()
    tool = w._wall_dims
    item = next(i for i, side in tool._labels if i.toPlainText().strip() == '3,75')
    monkeypatch.setattr(QInputDialog, 'getDouble', staticmethod(lambda *a, **k: (3.0, True)))
    pos = view.mapFromScene(item.pos())                         # the label's top-left, then into the text
    pos.setX(pos.x() + 12); pos.setY(pos.y() + 8)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    app.processEvents()
    after = {s['neighbour']: round(s['clear'], 3) for s in wall_dims(w.doc, ids['mid'])['sides']}
    assert after[ids['e']] == 3.0


def test_press_and_drag_on_a_wall_not_yet_selected_moves_it_in_one_gesture(window):
    """Owner 24/10: «click and drag the wall» — no click first to select it."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    w, app = window
    ids = _house(w.doc, w.stack)
    view = w.plan_view
    view.fitInView(QRectF(-1, -1, 12, 10)); w.snap_action.setChecked(True); view.set_grid_step(0.10)
    vp = view.viewport(); at = lambda x, y: view.mapFromScene(QPointF(x, y))
    w.doc.select([]); view.redraw()
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.0, 3.0))
    for x in (6.1, 6.3, 6.5):
        QTest.mouseMove(vp, at(x, 3.0)); app.processEvents()
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.5, 3.0)); app.processEvents()
    assert abs(float(w.doc.get(ids['mid']).params['x1']) - 6.5) < 0.051
