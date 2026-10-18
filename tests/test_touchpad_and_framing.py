"""Owner 18/10 (laptop): «το σχέδιο δεν είναι κεντραρισμένο, δεν μπορώ να το μετακινήσω» — an opened project starts
framed; two fingers on a touchpad move the plan, a mouse wheel and Ctrl + scroll zoom."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from archforge.ui.main_window import MainWindow


def _wheel(plan, angle, pixel=QPoint(), mods=Qt.KeyboardModifier.NoModifier):
    pos = QPointF(plan.viewport().rect().center())
    return QWheelEvent(pos, QPointF(plan.viewport().mapToGlobal(pos.toPoint())), pixel, angle,
                       Qt.MouseButton.NoButton, mods, Qt.ScrollPhase.NoScrollPhase, False)


def test_opened_sample_is_framed_and_touchpad_pans(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    try:
        samples = os.path.normpath(w.samples_dir())
        assert w._open_checked(os.path.join(samples, sorted(n for n in os.listdir(samples) if n.startswith('S01_') and n.endswith('.archforge'))[0]))
        for _ in range(5):
            app.processEvents()
        plan = w.plan_view
        rect = None
        for item in plan._entity_items:
            r = item.sceneBoundingRect()
            rect = r if rect is None else rect.united(r)
        visible = plan.mapToScene(plan.viewport().rect()).boundingRect()
        assert visible.contains(rect.center())                        # the house is in view after opening

        before_scale = plan.transform().m11()
        h, v = plan.horizontalScrollBar().value(), plan.verticalScrollBar().value()
        plan.wheelEvent(_wheel(plan, QPoint(0, -40), QPoint(-30, -40)))          # touchpad: pixel deltas → pan
        assert plan.transform().m11() == before_scale
        assert (plan.horizontalScrollBar().value(), plan.verticalScrollBar().value()) == (h + 30, v + 40)
        plan.wheelEvent(_wheel(plan, QPoint(0, 120)))                              # mouse wheel notch → zoom
        assert plan.transform().m11() > before_scale
        z = plan.transform().m11()
        plan.wheelEvent(_wheel(plan, QPoint(0, -40), QPoint(0, -40), Qt.KeyboardModifier.ControlModifier))
        assert plan.transform().m11() < z                                         # Ctrl + scroll (pinch) → zoom
    finally:
        w.hide()
