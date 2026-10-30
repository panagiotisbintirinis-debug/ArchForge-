"""Owner 30/10 (screenshot: Ιδιότητες over the whole window): «γιατί τα μενού πρέπει να καλύπτουν όλη την οθόνη;» —
the plan / 3D keeps a minimum size whatever a panel is dragged or restored to.  (Offscreen Qt does not reproduce the
owner's screen; this checks the guard and that the layout honours it.)"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


def test_a_panel_dragged_wide_never_covers_the_work_area():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.workspace_layout import MIN_WORK_AREA
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w.resize(1280, 960); w.show()
        for _ in range(3):
            app.processEvents()
        w.resizeDocks([w.dock], [5000], Qt.Orientation.Horizontal)        # as far as a drag can go
        for _ in range(3):
            app.processEvents()
        central = w.centralWidget()
        assert (central.minimumWidth(), central.minimumHeight()) >= MIN_WORK_AREA     # the guard is on
        assert central.isVisible()
        assert central.width() >= MIN_WORK_AREA[0] and central.height() >= MIN_WORK_AREA[1]
    finally:
        w._mark_clean(); w.close(); app.processEvents()
