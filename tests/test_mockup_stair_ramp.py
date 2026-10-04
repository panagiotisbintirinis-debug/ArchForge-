import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton

from archforge.core.viewport import PointerEvent
from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def _window():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()
    return app, window


def _close(app, window):
    window._mark_clean()
    window.close()
    app.processEvents()


def test_ribbon_has_one_stair_ramp_button_with_both_tools():
    app, window = _window()
    buttons = [b for b in window.findChildren(QToolButton) if b.text() == 'Σκάλα / Ράμπα' and b.isVisible()]
    assert len(buttons) == 1
    labels = [a.text() for a in buttons[0].menu().actions()]
    assert labels == ['Σκάλα', 'Ράμπα']
    _close(app, window)


def test_stair_without_upper_floor_offers_to_create_it_and_then_places(monkeypatch):
    app, window = _window()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.Yes)
    window._set_active_tool('stair')

    assert window.doc.levels.get('Floor 2') == 2.70
    # The human keeps drawing from the storey they were on.
    assert abs(float(window.doc.work_plane.origin[2])) < 1e-9
    assert window.plan_view.controller.tool == 'stair'

    controller = window.plan_view.controller
    controller.pointer_down(PointerEvent(1.0, 1.0))
    controller.pointer_move(PointerEvent(5.0, 1.0))
    result = controller.pointer_up(PointerEvent(5.0, 1.0))
    stair = window.doc.get(result.entity_id)
    assert stair.kind == 'stair'
    assert stair.params['upper_z'] >= 2.70 - 1e-9
    _close(app, window)


def test_ramp_without_upper_floor_can_be_declined(monkeypatch):
    app, window = _window()
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.StandardButton.No)
    window._set_active_tool('ramp')
    assert set(window.doc.levels) == {'Ground'}
    assert window.plan_view.controller.tool != 'ramp'
    _close(app, window)
