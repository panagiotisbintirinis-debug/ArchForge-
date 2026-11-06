"""Bots 06/11: one click redrew the 3D scene twice (change notice + «all views») and also while the 3D tab was not
on screen — 2,5 s per click in a 350-element house. Same state in the same turn: sent once; hidden: on opening."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity


def _view():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.pbr_viewport import PBRViewport
    QApplication.instance() or QApplication([])
    doc = Document(); stack = CommandStack(doc)
    wall = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})
    stack.execute(AddEntity(wall))
    view = PBRViewport(doc, stack)
    sent = []

    class Page:
        def runJavaScript(self, script, *a):
            sent.append(script)

    class Web:
        def page(self):
            return Page()
    view.web_view = Web()
    return view, stack, wall, sent


def test_same_state_same_turn_is_sent_once_and_a_change_is_sent():
    view, stack, wall, sent = _view()
    scenes = lambda: [x for x in sent if 'archforgeSetScene' in x]
    view.redraw(force_full=True); n = len(scenes())
    view.redraw(); view.redraw()
    assert len(scenes()) == n                                 # nothing new: not built again
    stack.execute(UpdateEntity(wall.id, {'height': 3.0}))
    view.redraw()
    assert len(scenes()) == n + 1                             # a change is always sent


def test_hidden_3d_in_a_shown_window_waits_for_activate():
    from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget
    view, stack, wall, sent = _view()
    win = QMainWindow(); tabs = QTabWidget(); plan = QWidget()
    tabs.addTab(plan, 'Κάτοψη'); tabs.addTab(view, '3D'); win.setCentralWidget(tabs); win.show()
    QApplication.processEvents()
    try:
        assert not view.isVisible()
        stack.execute(UpdateEntity(wall.id, {'height': 3.1})); view.redraw()
        assert not [x for x in sent if 'archforgeSetScene' in x]     # not on screen: nothing built
        tabs.setCurrentWidget(view); QApplication.processEvents()
        view.activate()                                       # what opening the 3D tab calls
        scene = [x for x in sent if 'archforgeSetScene' in x]
        assert scene and '3.1' in scene[-1]                   # opened: up to date at once
    finally:
        win.close()
