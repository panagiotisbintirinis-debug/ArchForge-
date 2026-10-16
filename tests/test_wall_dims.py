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


def test_select_shows_distances_double_click_moves_with_the_mouse(window):
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    w, app = window
    ids = _house(w.doc, w.stack)
    view = w.plan_view
    view.fitInView(QRectF(-1, -1, 12, 10)); w.snap_action.setChecked(True); view.set_grid_step(0.10)
    w.doc.select([ids['mid']]); view.redraw()
    tool = w._wall_dims
    texts = sorted(item.toPlainText().strip() for item, _side in tool._labels)
    assert texts == ['3,75', '5,75', '8,00']
    vp = view.viewport()
    at = lambda x, y: view.mapFromScene(QPointF(x, y))
    QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.0, 3.0))
    app.processEvents()
    assert tool.moving is not None and tool.moving['eid'] == ids['mid']
    QTest.mouseMove(vp, at(6.53, 3.0)); app.processEvents()
    assert abs(tool.moving['offset'] - 0.5) < 1e-9                       # on the 10 cm grid
    n_before = len(w.stack.done)
    QTest.mouseClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.53, 3.0))
    app.processEvents()
    assert tool.moving is None and abs(float(w.doc.get(ids['mid']).params['x1']) - 6.5) < 1e-6
    assert len(w.stack.done) == n_before + 1
    w._undo()
    assert abs(float(w.doc.get(ids['mid']).params['x1']) - 6.0) < 1e-6
    # Esc cancels a move without changing anything.
    QTest.mouseDClick(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at(6.0, 3.0))
    QTest.mouseMove(vp, at(7.0, 3.0))
    QTest.keyClick(vp, Qt.Key.Key_Escape); app.processEvents()
    assert tool.moving is None and abs(float(w.doc.get(ids['mid']).params['x1']) - 6.0) < 1e-6


def test_double_click_on_a_distance_types_the_value(window, monkeypatch):
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
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos)
    app.processEvents()
    after = {s['neighbour']: round(s['clear'], 3) for s in wall_dims(w.doc, ids['mid'])['sides']}
    assert after[ids['e']] == 3.0
