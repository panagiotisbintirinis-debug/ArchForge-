"""Owner 25/10: «το πρόγραμμα για δοκιμές φωτισμού σε νυχτερινό δεν το είδα ποτέ στην πράξη — πού είναι;»

The night mode of ui/lighting_system.py had no command: «Ήλιος & ουρανός ▸ Νύχτα» turns it on, an hour turns it off.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

from PySide6.QtWidgets import QApplication


def test_night_is_in_the_sun_menu_and_an_hour_brings_the_day_back():
    app = QApplication.instance() or QApplication([])
    import archforge.ui.app  # noqa: F401  (installs the lighting system, as the program does)
    from archforge.ui.main_window import MainWindow
    w = MainWindow()
    app.processEvents()
    night = w._mockup_night_action
    assert night.text().startswith('Νύχτα') and night in w._mockup_sun_menu.actions()
    night.trigger()
    assert w.pbr_view._architectural_lighting_mode == 'night'
    noon = next(a for a in w._mockup_sun_menu.actions() if a.text().startswith('Μεσημέρι'))
    noon.trigger()
    assert w.pbr_view._architectural_lighting_mode == 'day'
