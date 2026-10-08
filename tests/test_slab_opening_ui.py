"""Slab openings with the mouse in the real window (SL1): drag, polygon clicks, right click on a room, railing."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.ui.slab_tools import SlabDraft


def test_draft_rectangle_drag_and_polygon_clicks():
    d = SlabDraft()
    d.down(1, 1); d.move(3, 2.5)
    assert d.label() == '2,00 × 1,50 m · 3,00 m²'
    assert d.up(3, 2.5) == [(1, 1), (3, 1), (3, 2.5), (1, 2.5)]
    for x, y in ((0, 0), (2, 0), (1, 2)):
        d.down(x, y)
        assert d.up(x, y) is None
    d.down(0.05, 0.05)
    assert d.up(0.05, 0.05) == [(0, 0), (2, 0), (1, 2)]                   # click on the first corner closes


@pytest.fixture
def window():
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show()
    for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 6)), ((8, 6), (0, 6)), ((0, 6), (0, 0)), ((4, 0), (4, 6))):
        w.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                                  'height': 3.0, 'thickness': 0.25})))
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def test_auto_floor_is_one_storey_slab_and_opening_drawn_by_drag(window):
    w, app = window
    slab = w._create_auto_floors()
    assert [e.id for e in w.doc.entities.values() if e.kind == 'room_floor'] == [slab.id]
    assert [a.text() for a in w._slab_opening_actions][0] == 'Οπή πλάκας / αίθριο (σχεδίαση)'
    w._slab_opening_actions[0].trigger()
    vp = w.plan_view.viewport()
    a, b = w.plan_view.mapFromScene(QPointF(5, 1)), w.plan_view.mapFromScene(QPointF(7, 3))
    QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
    for k in range(1, 6):
        QTest.mouseMove(vp, a + (b - a) * k / 5)
    QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b)
    app.processEvents()
    holes = [e for e in w.doc.entities.values() if e.kind == 'slab_opening']
    assert len(holes) == 1 and w.doc.selection == [holes[0].id]
    from archforge.architecture.rooms import room_slab_geometry
    assert room_slab_geometry(w.doc, slab)['area'] == pytest.approx(48 - 4, abs=0.2)
    labels = [w.form.itemAt(i).widget().text() for i in range(w.form.count())
              if isinstance(w.form.itemAt(i).widget(), QLabel)]
    assert 'Χρήση' in labels and 'Κόβει' in labels
    w._undo()
    assert not [e for e in w.doc.entities.values() if e.kind == 'slab_opening']


def test_right_click_room_becomes_atrium_and_railing_in_one_click(window):
    w, _app = window
    w._create_flat_roofs()
    from archforge.ui.marking_menu import build_menu, run
    ids = [e['id'] for e in build_menu(w, 'plan')['entries']]
    assert 'mm:slab:atrium' in ids and 'mm:slab:inner_balcony' in ids
    run(w, 'plan', None, 'mm:slab:atrium', (2.0, 3.0))
    (atrium,) = [e for e in w.doc.entities.values() if e.kind == 'slab_opening']
    assert atrium.params['room_id'] and atrium.params['cuts'] == 'both'
    assert 'mm:slab:railing' in [e['id'] for e in build_menu(w, 'plan', atrium.id)['entries']]
    run(w, 'plan', atrium.id, 'mm:slab:railing', None)
    railing = [e for e in w.doc.entities.values() if e.kind == 'railing']
    assert len(railing) == 1 and railing[0].params['closed'] == 1 and railing[0].params['height'] == 1.0
    w.doc.select([atrium.id]); w._delete_selection()
    assert atrium.id not in w.doc.entities


def test_slab_opening_command_is_in_the_construction_menu_of_the_real_window():
    """Regression: the Κατασκευή entry was silently dropped (PySide wrapper lifetime)."""
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        menus = {m.title().replace('&', '') for a in window._slab_opening_actions for m in a.associatedObjects()
                 if hasattr(m, 'title')}
        assert 'Κατασκευή' in menus and 'Αυτόματα' in menus
    finally:
        window._mark_clean(); window.close(); app.processEvents()
