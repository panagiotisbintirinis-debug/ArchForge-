"""Owner (2026-10-14): «δάπεδα πρέπει να είναι αυτόματα — μια περίμετρος τοίχων έχει δάπεδο, δεν χρειάζεται να
την ζητήσω» · «εκτός αν είναι φράχτης — αλλά και αυτός πρέπει να έχει τερέν»."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document
from archforge.core.viewport import PointerController, PointerEvent


def _draw(c, pts):
    c.set_tool('wall')
    for x, y in pts:
        c.pointer_down(PointerEvent(x, y)); c.pointer_up(PointerEvent(x, y))


def _floors(doc):
    return [e for e in doc.entities.values() if e.kind == 'room_floor' and e.params.get('scope') == 'storey']


def test_closing_an_outline_gives_the_storey_its_floor_in_the_same_undo():
    doc = Document(); stack = CommandStack(doc)
    c = PointerController(doc, stack); c.auto_floors = True
    _draw(c, [(0, 0), (6, 0), (6, 4)])
    assert not _floors(doc)                           # not closed yet
    for x, y in ((0, 4), (0, 0)):
        c.pointer_down(PointerEvent(x, y)); c.pointer_up(PointerEvent(x, y))
    assert len(_floors(doc)) == 1
    stack.undo()                                      # the closing wall and the floor go together
    assert not _floors(doc) and len([e for e in doc.entities.values() if e.kind == 'wall']) == 3


def test_a_second_room_uses_the_same_storey_floor_and_a_fence_keeps_the_ground():
    from archforge.architecture.storey_slabs import storey_faces
    doc = Document(); stack = CommandStack(doc)
    c = PointerController(doc, stack); c.auto_floors = True
    _draw(c, [(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)])
    c.cancel()
    _draw(c, [(6, 0), (9, 0), (9, 4), (6, 4)])
    c.cancel()
    assert len(_floors(doc)) == 1 and len(storey_faces(doc, 'room_floor', 0.0)) == 2
    # A garden wall 1.0 m high closing a yard: no slab there.
    doc2 = Document(); stack2 = CommandStack(doc2)
    c2 = PointerController(doc2, stack2); c2.auto_floors = True
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    for (x1, y1), (x2, y2) in (((20, 0), (30, 0)), ((30, 0), (30, 8)), ((30, 8), (20, 8)), ((20, 8), (20, 0))):
        stack2.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 1.0, 'thickness': 0.2})))
    from archforge.architecture.storey_slabs import auto_floor_command
    assert auto_floor_command(doc2, 0.0) is None and not storey_faces(doc2, 'room_floor', 0.0)


def test_without_the_window_switch_nothing_is_added():
    doc = Document(); stack = CommandStack(doc)
    c = PointerController(doc, stack)
    _draw(c, [(0, 0), (6, 0), (6, 4), (0, 4), (0, 0)])
    assert not _floors(doc)


def test_the_window_turns_it_on():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        assert w.plan_view.controller.auto_floors is True
    finally:
        w._mark_clean(); w.close(); app.processEvents()
