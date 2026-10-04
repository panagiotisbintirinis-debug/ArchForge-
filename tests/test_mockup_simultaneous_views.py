import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_simultaneous_2d_3d_shows_both_real_editors_and_can_switch_back():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    window._simultaneous_action.setChecked(True)
    app.processEvents()
    split = window._mockup_center_split
    assert split is not None
    assert window._central_tabs.currentWidget() is split
    assert split.isVisible()
    assert window.plan_view.isVisible()
    assert window.plan_view.viewport().isVisible()
    assert window._mockup_right_tabs.isVisible()

    window._simultaneous_action.setChecked(False)
    app.processEvents()
    central = window._central_tabs
    assert [central.tabText(i) for i in range(central.count())] == ['2D Σχεδίαση', '3D / Structural']
    assert window.plan_view.isVisible()

    window._simultaneous_action.setChecked(True)
    app.processEvents()
    assert window.plan_view.isVisible()
    assert window._mockup_right_tabs.isVisible()

    window._mark_clean()
    window.close()
    app.processEvents()
