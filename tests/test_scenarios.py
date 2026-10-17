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


def test_scenario_01_quality_gate(window, tmp_path):
    """S01 through the quality gate (docs/scenarios/QUALITY_GATE.md): every check PASS or N/A, except the
    items waiting on the owner (S01_REPORT.md lists them)."""
    from archforge.scenarios import s01_monokatoikia as m
    from archforge.scenarios.gate import FAIL, Gate
    s = m.build(window)
    assert all(step.ok for step in s.steps), [st for st in s.steps if not st.ok]
    g = Gate(s, m, str(tmp_path))
    g.run(visual=False)
    fails = [c for c in g.checks if c.status == FAIL and not c.item.startswith(m.OWNER_PENDING)]
    assert not fails, fails


def test_scenario_02_complex(window, tmp_path):
    from archforge.scenarios import s02_syntheto as m
    s = m.build(window)
    assert all(step.ok for step in s.steps), [st for st in s.steps if not st.ok]
    m.checks(s)
    s.check_save_load(str(tmp_path / 's02.archforge'))
    assert all(c.ok for c in s.checks), [c for c in s.checks if not c.ok]
