import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_view_menu_controls_real_status_bar_and_tools_toolbar_visibility():
    _app()
    window = MainWindow()
    window.show()
    QApplication.processEvents()

    menus = {action.text().replace('&', ''): action.menu() for action in window.menuBar().actions()}
    assert 'View' in menus
    assert window.status_bar_action.isCheckable()
    assert window.tools_toolbar_action.isCheckable()
    assert window.status_bar_action.isChecked() == window.statusBar().isVisible()
    assert window.tools_toolbar_action.isChecked() == window.tools_toolbar.isVisible()

    # Verify the menu contents while the QMenu wrapper is definitely live. Some
    # offscreen PySide6 builds invalidate a retained QMenu wrapper after visibility
    # changes even though the actual menu/action ownership remains correct.
    labels = {action.text() for action in menus['View'].actions()}
    assert labels == {'Status Bar', 'Tools Toolbar'}

    window.status_bar_action.trigger()
    window.tools_toolbar_action.trigger()
    QApplication.processEvents()
    assert not window.statusBar().isVisible()
    assert not window.tools_toolbar.isVisible()
    assert not window.status_bar_action.isChecked()
    assert not window.tools_toolbar_action.isChecked()

    window.status_bar_action.trigger()
    window.tools_toolbar_action.trigger()
    QApplication.processEvents()
    assert window.statusBar().isVisible()
    assert window.tools_toolbar.isVisible()
    assert window.status_bar_action.isChecked()
    assert window.tools_toolbar_action.isChecked()

    window.close()
