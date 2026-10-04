import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtWidgets import QApplication

from archforge.ui.main_window import MainWindow


def _app():
    return QApplication.instance() or QApplication([])


def test_mockup_menus_carry_real_file_edit_and_view_commands():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    menus = window._mockup_menus
    file_actions = menus['Αρχείο'].actions()
    for action in (window.new_action, window.open_action, window.save_action, window.export_stl_action):
        assert action in file_actions
    edit_actions = menus['Επεξεργασία'].actions()
    for action in (window.undo_action, window.redo_action, window.delete_action):
        assert action in edit_actions

    # Shortcuts stay live although the legacy toolbars that also hold these
    # actions are hidden behind the approved ribbon.
    for action in (window.save_action, window.open_action, window.undo_action, window.redo_action):
        assert action in window.actions()

    assert window.view_menu is menus['Προβολή']
    labels = {action.text() for action in window.view_menu.actions()}
    assert {'Γραμμή κατάστασης', 'Παράθυρα'} <= labels


def test_view_menu_controls_real_status_bar_visibility():
    app = _app()
    window = MainWindow()
    window.show()
    app.processEvents()

    assert window.status_bar_action.isCheckable()
    assert window.status_bar_action.isChecked() == window.statusBar().isVisible()

    window.status_bar_action.trigger()
    app.processEvents()
    assert not window.statusBar().isVisible()
    assert not window.status_bar_action.isChecked()

    window.status_bar_action.trigger()
    app.processEvents()
    assert window.statusBar().isVisible()
    assert window.status_bar_action.isChecked()

    window.close()
    app.processEvents()
