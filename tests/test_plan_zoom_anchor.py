"""Owner (Windows): «το σχέδιο φεύγει προς τα αριστερά κάθε φορά που κάνω ζουμ».

The wheel zooms about the mouse: the drawing point under the cursor stays under it,
zooming in and out, also after the view redraws (the scene rect used to follow the
visible area and pulled the drawing back to the centre).
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _wheel(view, pos, up):
    vp = view.viewport()
    ev = QWheelEvent(QPointF(pos), QPointF(vp.mapToGlobal(pos)), QPoint(), QPoint(0, 120 if up else -120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(vp, ev)
    view.redraw()
    QApplication.processEvents()


def test_wheel_zoom_keeps_the_point_under_the_mouse():
    from archforge.ui.plan_view import PlanView
    app = QApplication.instance() or QApplication([])
    d = Document(); stack = CommandStack(d)
    stack.execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 8, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': .2})))
    view = PlanView(d, stack); view.resize(900, 700); view.show(); app.processEvents()
    for pos in (QPoint(150, 200), QPoint(700, 500), QPoint(450, 350)):
        for up in (True, True, True, False, False, False, False, False, True):
            before = view.mapToScene(pos)
            _wheel(view, pos, up)
            after = view.mapToScene(pos)
            assert abs(after.x() - before.x()) < 0.05 and abs(after.y() - before.y()) < 0.05, (pos, up, before, after)
    view.close()
