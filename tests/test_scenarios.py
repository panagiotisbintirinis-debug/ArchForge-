"""Every scenario builds through the UI's transactions without a failed step and survives save/load."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w._no_modal_dialogs = True
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def test_scenario_01_house(window, tmp_path):
    from archforge.scenarios import s01_monokatoikia as m
    s = m.build(window)
    assert all(step.ok for step in s.steps), [st for st in s.steps if not st.ok]
    m.checks(s)
    s.check_save_load(str(tmp_path / 's01.archforge'))
    by = {c.action: c for c in s.checks}
    assert by['Χώροι που αναγνωρίστηκαν από τους τοίχους'].ok
    assert by['Κουφώματα στο έργο'].ok and by['Στέγη'].ok
    assert by['Αποθήκευση και ξανά άνοιγμα: ίδιες οντότητες και παράμετροι'].ok
    # Open finding (owner decision pending): plan labels show axis areas, not net areas.
    assert not by['Εμβαδά χώρων = καθαρά εμβαδά ανάμεσα στις παρειές'].ok
