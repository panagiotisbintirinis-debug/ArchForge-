"""Owner 29/10: «δεν βλέπω το κουμπί της ρύθμισης πουθενά» — the sculpt operation and brush size were only in the hidden
legacy bar and the right-click menu.  Now on the «Γλυπτική ▾» button, bound to the same controls."""


def test_the_sculpt_button_turns_it_on_and_its_menu_sets_operation_and_brush():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        button = w._mockup_sculpt_button
        assert button.text() == 'Γλυπτική' and button.menu() is not None
        button.click()
        assert w.sculpt_action.isChecked() and button.isChecked()
        w._mockup_sculpt_ops['smooth'].trigger()
        assert w.sculpt_operation.currentText() == 'smooth' and w.pbr_view.sculpt_op == 'smooth'
        w._mockup_sculpt_size.setValue(0.75)
        assert w.sculpt_radius.value() == 0.75 and abs(w.pbr_view.sculpt_brush.radius - 0.75) < 1e-9
        w.sculpt_radius.setValue(0.5)                      # the wheel / right-click menu: the button follows
        assert w._mockup_sculpt_size.value() == 0.5
        w.sculpt_operation.setCurrentText('push')
        assert w._mockup_sculpt_ops['push'].isChecked()
        button.click()
        assert not w.sculpt_action.isChecked() and not button.isChecked()
    finally:
        w.hide()
