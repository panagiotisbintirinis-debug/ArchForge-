"""Owner 29/10 (Windows): «πάτησα τους τοίχους, δεν βλέπω να ανοίγει κάτι μενού» — the new buttons had gone into the
old ribbon that Διάταξη 2 hides.  They must be in the tool groups the human sees."""


def test_wall_sculpt_and_brush_are_in_the_visible_tool_groups():
    from PySide6.QtWidgets import QApplication, QToolButton
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w.resize(1600, 900); w.show(); app.processEvents()
        wall = w._layout2_wall_button
        assert wall.isVisible() and wall.text() == 'Τοίχος'
        assert wall.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup
        assert wall.menu() is w._mockup_wall_button.menu()
        wall.click(); app.processEvents()
        assert w.plan_view.controller.tool == 'wall'                     # a click still draws walls
        sculpt = w._layout2_sculpt_button
        assert sculpt.menu() is w._mockup_sculpt_button.menu()
        assert sculpt.popupMode() == QToolButton.ToolButtonPopupMode.MenuButtonPopup
        sculpt.click(); app.processEvents()
        assert w.sculpt_action.isChecked() and sculpt.isChecked()
        sculpt.click(); app.processEvents()
        assert not w.sculpt_action.isChecked()
        assert w._layout2_brush_button.defaultAction() is w._mockup_brush_action
    finally:
        w._mark_clean(); w.close(); app.processEvents()
