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


@pytest.mark.parametrize('name', ['s02_syntheto', 's03_diamerisma'])
def test_scenario_builds_and_passes_the_gate(window, tmp_path, name):
    """Built scenarios (builder.py specs) through the same gate; the slow ones run from scripts/build_scenarios.py."""
    import importlib
    from archforge.scenarios.gate import FAIL, Gate
    m = importlib.import_module(f'archforge.scenarios.{name}')
    s = m.build(window)
    assert all(step.ok for step in s.steps), [st for st in s.steps if not st.ok]
    g = Gate(s, m, str(tmp_path))
    g.run(visual=False)
    fails = [c for c in g.checks if c.status == FAIL and not c.item.startswith(m.OWNER_PENDING)]
    assert not fails, fails
