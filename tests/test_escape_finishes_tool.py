"""Walk-through 14/10: Esc cancelled the wall in progress, but a second Esc left the Wall tool on."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _esc(view):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    view.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))


def test_first_esc_cancels_the_segment_second_esc_returns_to_select(window):
    from archforge.core.viewport import PointerEvent
    plan = window.plan_view
    window._set_active_tool('wall')
    plan.controller.pointer_down(PointerEvent(0.0, 0.0))
    assert plan.controller.active is not None
    _esc(plan)
    assert plan.controller.active is None and plan.controller.tool == 'wall'     # still drawing walls
    _esc(plan)
    assert plan.controller.tool == 'select'


def test_esc_with_a_drawing_tool_and_nothing_started_selects(window):
    from archforge.ui import slab_tools
    slab_tools.start_balcony_tool(window)
    _esc(window.plan_view)
    assert window.plan_view.controller.tool == 'select'
