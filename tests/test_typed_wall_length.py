"""Μήκος / γωνία με το πληκτρολόγιο την ώρα της σχεδίασης τοίχου (ui/typed_length.py · κριτική v5 Σ1, 04/11).

Πριν: κλικ, «4.20», Enter → κανένας τοίχος και «Τοίχος: ακυρώθηκε». Τώρα: ο τοίχος μπαίνει με αυτό το μήκος.
"""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from archforge.core.commands import CommandStack
from archforge.core.model import Document


@pytest.fixture
def view():
    QApplication.instance() or QApplication([])
    from archforge.ui.plan_view import PlanView
    doc = Document(); stack = CommandStack(doc)
    v = PlanView(doc, stack); v.resize(900, 700); v.show(); QApplication.processEvents()
    v.said = []
    v.statusChanged.connect(v.said.append)
    v.set_tool('wall')
    yield v
    v.close()


def _vp(v, x, y):
    return v.mapFromScene(QPointF(x, y))


def _click(v, x, y):
    p = _vp(v, x, y)
    QTest.mouseMove(v.viewport(), p)
    QTest.mouseClick(v.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, p)
    QApplication.processEvents()


def _type(v, text):
    for ch in text:
        QTest.keyClicks(v, ch)
    QApplication.processEvents()


def _key(v, key):
    QTest.keyClick(v, key); QApplication.processEvents()


def _walls(v):
    return [e.params for e in v.doc.entities.values() if e.kind == 'wall']


def _len(p):
    return math.hypot(p['x2'] - p['x1'], p['y2'] - p['y1'])


def test_wall_tool_says_the_next_step_from_the_start(view):
    assert 'κλικ στο πρώτο σημείο' in view.said[-1] and 'γράψε μήκος' in view.said[-1]


def test_typed_length_toward_the_mouse_makes_the_wall(view):
    _click(view, 0, 0)
    QTest.mouseMove(view.viewport(), _vp(view, 3, 0)); QApplication.processEvents()
    _type(view, '4,20')
    assert view._typed is not None and view._typed.length == '4,20'
    assert 'Μήκος 4,20' in view.said[-1]
    _key(view, Qt.Key.Key_Return)
    walls = _walls(view)
    assert len(walls) == 1
    assert abs(_len(walls[0]) - 4.20) < 1e-6
    assert abs(walls[0]['y2'] - walls[0]['y1']) < 1e-6          # toward the mouse: along x
    assert view._wall_chain_active()                             # continues from its end, like a click
    assert 'μπήκε' in view.said[-1]


def test_units_and_angle_close_a_room(view):
    _click(view, 0, 0)
    for length, angle in (('420 cm', '0'), ('3,6', '90'), ('4200 mm', '180')):
        _type(view, length)
        _key(view, Qt.Key.Key_Tab)
        _type(view, angle)
        _key(view, Qt.Key.Key_Return)
    walls = _walls(view)
    assert len(walls) == 3
    assert [round(_len(p), 6) for p in walls] == [4.2, 3.6, 4.2]
    last = walls[-1]
    assert abs(last['x2']) < 1e-6 and abs(last['y2'] - 3.6) < 1e-6   # 90° = up in the plan


def test_escape_clears_typing_first_then_backspace_edits(view):
    _click(view, 0, 0)
    QTest.mouseMove(view.viewport(), _vp(view, 0, 2)); QApplication.processEvents()
    _type(view, '25')
    _key(view, Qt.Key.Key_Backspace)
    assert view._typed.length == '2'
    _key(view, Qt.Key.Key_Escape)
    assert view._typed is None and view._wall_chain_active()     # the wall in progress is still there
    _type(view, '2')
    _key(view, Qt.Key.Key_Return)
    walls = _walls(view)
    assert len(walls) == 1 and abs(_len(walls[0]) - 2.0) < 1e-6


def test_one_undo_per_typed_wall(view):
    _click(view, 0, 0)
    QTest.mouseMove(view.viewport(), _vp(view, 3, 0)); QApplication.processEvents()
    _type(view, '5'); _key(view, Qt.Key.Key_Return)
    _type(view, '2'); _key(view, Qt.Key.Key_Tab); _type(view, '90'); _key(view, Qt.Key.Key_Return)
    assert len(_walls(view)) == 2
    view.stack.undo()
    assert len(_walls(view)) == 1


def test_enter_without_typing_still_finishes_the_chain(view):
    _click(view, 0, 0)
    _click(view, 4, 0)
    assert len(_walls(view)) == 1 and view._wall_chain_active()
    _key(view, Qt.Key.Key_Return)
    assert not view._wall_chain_active() and len(_walls(view)) == 1


def test_bad_text_says_what_to_do_and_keeps_the_wall_in_progress(view):
    _click(view, 0, 0)
    QTest.mouseMove(view.viewport(), _vp(view, 3, 0)); QApplication.processEvents()
    _type(view, '4,2,1')
    _key(view, Qt.Key.Key_Return)
    assert not _walls(view) and view._wall_chain_active()
    assert 'απόσταση' in view.said[-1]
