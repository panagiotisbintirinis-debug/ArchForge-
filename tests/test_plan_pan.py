"""Owner: «παρατεταμένο αριστερό κλικ να γίνει pan, να μπορώ να μετακινώ το σχέδιο»."""
import os
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.core.model import Document
from archforge.ui.plan_view import PlanView


def _view():
    app = QApplication.instance() or QApplication([])
    d = Document(); view = PlanView(d, CommandStack(d)); view.resize(800, 600); view.show(); app.processEvents()
    return app, d, view


def _wait(app, ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents(); time.sleep(.01)


def _scroll(view):
    return view.horizontalScrollBar().value(), view.verticalScrollBar().value()


def _drag(app, view, button, a, b, hold_ms=0):
    vp = view.viewport()
    QTest.mousePress(vp, button, Qt.KeyboardModifier.NoModifier, a)
    _wait(app, hold_ms)
    for k in range(1, 6):
        QTest.mouseMove(vp, a + (b - a) * k / 5); app.processEvents()
    QTest.mouseRelease(vp, button, Qt.KeyboardModifier.NoModifier, b); app.processEvents()


def test_long_left_press_then_drag_pans_and_draws_nothing():
    app, d, view = _view()
    view.controller.set_tool('wall')
    before = _scroll(view)
    _drag(app, view, Qt.MouseButton.LeftButton, QPoint(400, 300), QPoint(250, 200), hold_ms=view.LONG_PRESS_MS + 150)
    assert _scroll(view) != before
    assert not [e for e in d.entities.values() if e.kind == 'wall']
    assert view.controller.active is None and getattr(view, '_panning', None) is None
    view.close()


def test_a_normal_drag_still_draws_a_wall():
    app, d, view = _view()
    view.controller.set_tool('wall')
    a = view.mapFromScene(QPointF(0, 0)); b = view.mapFromScene(QPointF(3, 0))
    _drag(app, view, Qt.MouseButton.LeftButton, a, b)
    _wait(app, view.LONG_PRESS_MS + 100)           # a late timer must not undo the finished wall
    assert len([e for e in d.entities.values() if e.kind == 'wall']) == 1
    view.close()


def test_middle_button_drag_pans():
    app, d, view = _view()
    before = _scroll(view)
    _drag(app, view, Qt.MouseButton.MiddleButton, QPoint(400, 300), QPoint(300, 380))
    assert _scroll(view) != before
    view.close()
