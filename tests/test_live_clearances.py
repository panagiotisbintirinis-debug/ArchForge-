"""Owner 15/10: «επιμήκυνση και μετακίνηση: εάν κρατάμε πατημένο το ποντίκι σε οτιδήποτε το κάνουμε να
μετακινηθεί … δεν χρειάζεσαι κουμπί … αλλά χρειάζεσαι και άμεση αναγνώριση: το μεγάλωσα 2 πόντους, το μετακίνησα 20,
πόσο έχω μέχρι απέναντι»."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.wall_dims import object_clearances
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _room(doc, st):
    for x1, y1, x2, y2 in [(0, 0, 5, 0), (5, 0, 5, 4), (5, 4, 0, 4), (0, 4, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                                             'height': 2.7, 'thickness': 0.2})))


def test_clearances_from_each_side_to_the_wall_faces():
    doc = Document(); st = CommandStack(doc); _room(doc, st)
    c = {x['side']: round(x['value'], 3) for x in
         object_clearances(doc, {'x': 1.0, 'y': 1.0, 'width': .6, 'depth': .6, 'rotation': 0, 'z': 0})}
    assert c == {'left': 0.6, 'right': 3.6, 'front': 0.6, 'back': 2.6}
    turned = {x['side']: round(x['value'], 3) for x in
              object_clearances(doc, {'x': 1.0, 'y': 1.0, 'width': .6, 'depth': .6, 'rotation': 90, 'z': 0})}
    assert sorted(turned.values()) == sorted(c.values())


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _texts(tool):
    return [i.toPlainText().strip() for i, _s in getattr(tool, '_labels', [])]


def test_dragging_an_object_shows_how_far_it_moved_and_its_distances(window):
    from PySide6.QtWidgets import QGraphicsTextItem
    from archforge.core.viewport import PointerEvent
    _room(window.doc, window.stack)
    cab = Entity('cabinet', {'x': 1.0, 'y': 1.0, 'z': 0.0, 'width': .6, 'depth': .6, 'height': .86,
                             'rotation': 0.0, 'cabinet_type': 'base'})
    window.stack.execute(AddEntity(cab)); window.doc.select([cab.id])
    view = window.plan_view
    view.redraw()
    texts = lambda: {i.toPlainText().strip() for i in view.scene().items() if isinstance(i, QGraphicsTextItem)}
    assert {'0,60', '3,60', '2,60'} <= texts()                     # selected: its distances to the walls
    c = view.controller
    c.set_tool('move'); c.set_target(cab.id, None)
    c.pointer_down(PointerEvent(1.0, 1.0)); c.pointer_move(PointerEvent(1.2, 1.0))
    view.redraw()
    t = texts()
    assert 'Μετακίνηση 20 cm' in t and '0,80' in t and '3,40' in t     # live while dragging
    c.cancel()


def test_object_mouse_menu_has_no_move_or_stretch_buttons(window):
    from archforge.ui.marking_menu import build_menu
    _room(window.doc, window.stack)
    wall = next(iter(window.doc.entities))
    ids = [e['id'] for e in build_menu(window, 'plan', wall)['entries']]
    assert 'move' not in ids and 'stretch' not in ids and 'properties' in ids and 'delete' in ids
