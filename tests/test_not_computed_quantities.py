"""Λίστα εργασιών Α3 Β (ποσότητες): a measurement that fails is said with the quote, never a silent 0.

Before: ``except Exception: inner = 0.0`` — the interior plaster disappeared from the quote and the total
looked complete.
"""
import pytest

from archforge.core import notices
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.quantities import quote as quote_mod


def _house():
    doc = Document()
    stack = CommandStack(doc)
    pts = [(0, 0), (6, 0), (6, 5), (0, 5), (0, 0)]
    for a, b in zip(pts, pts[1:]):
        stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0,
                                                'height': 2.8, 'thickness': .25})))
    return doc


def test_a_failed_take_off_is_said_in_the_quote(monkeypatch):
    doc = _house()
    assert quote_mod.quote(doc)['not_computed'] == []

    import sys
    from archforge.quantities import takeoff
    real = takeoff.take_off

    def broken(_doc, *a, **k):                       # fails only for the plaster list, as one failure would
        if sys._getframe(1).f_code.co_name == 'plaster_list':
            raise RuntimeError('room topology')
        return real(_doc, *a, **k)
    monkeypatch.setattr(takeoff, 'take_off', broken)
    q = quote_mod.quote(doc)
    assert any('Σοβάς εσωτερικός' in m and 'room topology' in m for m in q['not_computed'])


def test_collecting_gathers_each_notice_once_and_only_inside():
    with notices.collecting() as found:
        notices.not_computed('x', 'Κάτι')
        notices.not_computed('x', 'Κάτι')
        with notices.collecting() as inner:
            notices.not_computed('y', 'Άλλο', 'e1', ValueError('bad'))
    notices.not_computed('z', 'Έξω')
    assert [i.code for i in found] == ['x', 'y']
    assert inner[0].message == 'Άλλο (ValueError: bad)' and inner[0].entity_id == 'e1'
    assert notices.recent()[-1].code == 'z'


def test_geometry_issues_are_the_same_record():
    from archforge.geometry.backend import GeometryIssue
    assert GeometryIssue is notices.Issue


def test_unknown_upper_storey_adds_or_removes_no_roof(monkeypatch):
    """Before: rooms above unreadable → coverage 0 → a roof proposed under the upper storey, silently."""
    from archforge.architecture import roof_need
    doc = _house()
    doc.levels['Όροφος'] = 3.0
    CommandStack(doc).execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 3.0,
                                                       'height': 2.8, 'thickness': .25})))
    real = Document.active_room_faces

    def upper_fails(self, z=None, tolerance=1e-5):
        if z is not None and z > 0.5:
            raise RuntimeError('upper topology')
        return real(self, z=z, tolerance=tolerance)
    monkeypatch.setattr(Document, 'active_room_faces', upper_fails)
    with notices.collecting() as found:
        plan = roof_need.roof_plan(doc)
    assert plan['add'] == [] and plan['remove'] == []
    assert any(i.code == 'roof.coverage' and 'upper topology' in i.message for i in found)


def test_the_window_says_what_an_edit_could_not_compute():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import Command
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    notices.not_computed('before', 'Πριν από το παράθυρο')      # not this window's
    w = MainWindow()
    w._no_modal_dialogs = True

    class Measures(Command):
        def do(self, doc):
            notices.not_computed('x', 'Εμβαδόν χώρου')
        def undo(self, doc):
            pass
    w.stack.execute(Measures())
    app.processEvents()
    assert w.statusBar().currentMessage() == 'Δεν υπολογίστηκε: Εμβαδόν χώρου'


def test_nested_empty_collections_close_cleanly():
    with notices.collecting() as outer:
        with notices.collecting() as inner:
            pass
        notices.not_computed('late', 'Μετά')
    assert inner == [] and [i.code for i in outer] == ['late']
    assert notices._collectors == []
