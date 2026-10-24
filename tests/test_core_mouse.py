"""Owner 23/10, drawing with the mouse: «τα εργαλεία συνεχίζουν να δουλεύουν συνέχεια, πρέπει να πατήσω επιλογή» ·
«βάλε σαν επιλογή γενικά το διπλό κλικ» · «το κουμπί Del βάλε το να δουλεύει παντού» · «σχεδιάζονται ουσιαστικά με
μια μεσοκάθετο μέσα στο πάχος του τοίχου, σαν να έχεις το λεπτό μολύβι» · «αφαιρώντας μικρό τοίχο ο διπλανός άλλαξε
γωνία» (Delete in the wall tool took back the last wall drawn, not the one under the mouse)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 950); w.show(); app.processEvents()
    w.plan_view.fitInView(-2, -2, 14, 12); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def _move(view, x, y):
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    p = QPointF(view.mapFromScene(QPointF(x, y)))
    QApplication.sendEvent(view.viewport(), QMouseEvent(QEvent.Type.MouseMove, p, view.viewport().mapToGlobal(p),
                                                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                                                        Qt.KeyboardModifier.NoModifier))


def _click(view, app, x, y):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    _move(view, x, y)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, view.mapFromScene(*(x, y)))
    app.processEvents()


def _walls(w):
    return {e.id: e.params for e in w.doc.entities.values() if e.kind == 'wall'}


def test_closing_an_outline_or_esc_or_a_double_click_ends_the_tool(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    w, app = window
    v = w.plan_view
    w._set_active_tool('wall')
    for p in [(0, 0), (6, 0), (6, 5), (0, 5), (0, 0)]:
        _click(v, app, *p)
    assert len(_walls(w)) == 4 and v.controller.tool == 'select'            # outline closed → Επιλογή
    # Esc: with nothing half done it ends the tool (the window's Esc shortcut used to swallow it).
    w._set_active_tool('door')
    w.activateWindow(); v.setFocus()
    w._escape_shortcut.activated.emit(); app.processEvents()
    assert v.controller.tool == 'select'
    # A double click in any tool: Επιλογή.
    w._set_active_tool('window')
    QTest.mouseDClick(v.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, v.mapFromScene(3, 8))
    app.processEvents()
    assert v.controller.tool == 'select'
    # A wall chain ended by a double click keeps its walls and gives way to Επιλογή.
    w._set_active_tool('wall')
    _click(v, app, 0, 8); _click(v, app, 4, 8)
    QTest.mouseDClick(v.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, v.mapFromScene(4, 8))
    app.processEvents()
    assert v.controller.tool == 'select' and len(_walls(w)) == 5


def test_delete_while_drawing_removes_the_wall_under_the_mouse(window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    w, app = window
    v = w.plan_view
    w._set_active_tool('wall')
    for p in [(0, 8), (4, 8), (4, 8.6), (8, 8.6)]:
        _click(v, app, *p)
    walls = _walls(w)
    short = next(k for k, p in walls.items() if abs(p['x1'] - p['x2']) < 1e-6)
    neighbours = {k: dict(p) for k, p in walls.items() if k != short}
    _move(v, 4.0, 8.3)
    QTest.keyClick(v.viewport(), Qt.Key.Key_Delete); app.processEvents()
    after = _walls(w)
    assert short not in after
    assert {k: (p['x1'], p['y1'], p['x2'], p['y2']) for k, p in after.items()} == \
        {k: (p['x1'], p['y1'], p['x2'], p['y2']) for k, p in neighbours.items()}      # the neighbours keep their angle


def test_the_wall_being_drawn_shows_its_body_not_a_line(window):
    from archforge.core.plan_scene import preview_primitives
    from archforge.core.viewport import PreviewState
    prims = preview_primitives(PreviewState('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0, 'thickness': 0.25}, {}))
    kinds = [(p.kind, dict(p.meta).get('semantic')) for p in prims if p.role == 'preview']
    assert ('polygon', 'wall-body-preview') in kinds and not any(k == 'line' for k, _ in kinds)
