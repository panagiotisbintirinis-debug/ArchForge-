"""Σχεδιασμός πισίνας (ιδιοκτήτης 07/11): πρώτα σχεδιάζεις (σχήμα, τομή, μινιατούρα 3D στον χώρο), μετά τοποθετείς —
με πραγματικά κλικ στο παράθυρο και στην κάτοψη, όπως ο άνθρωπος."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    w._no_modal_dialogs = True
    w.plan_view.controller.snap_enabled = False
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 8)), ((10, 8), (0, 8)), ((0, 8), (0, 0))):
        w.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                                  'height': 2.8, 'thickness': 0.25})))
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _menu(w, *path):
    acts = w.menuBar().actions()
    for i, name in enumerate(path):
        a = next(x for x in acts if x.text().replace('&', '') == name)
        if i < len(path) - 1:
            a.menu().aboutToShow.emit(); acts = a.menu().actions()
        else:
            a.trigger()


def _open_new(w):
    _menu(w, 'Διαμόρφωση', 'Περιβάλλων χώρος', 'Πισίνα (σχεδιασμός και τοποθέτηση)…')
    d = w._pool_designer
    QTest.qWaitForWindowExposed(d)
    return d


def _pools(w):
    return [e for e in w.doc.entities.values() if e.kind == 'pool']


def test_designed_first_then_placed_where_the_miniature_shows(window):
    w = window
    d = _open_new(w)
    assert d.params['x'] > 10.0                                   # a new pool starts beside the building, not in it
    assert not _pools(w)                                          # nothing placed while designing
    d.boxes['length'].setValue(10.0)
    d.boxes['depth_deep'].setValue(2.10)
    assert d.section.params['depth_deep'] == pytest.approx(2.10)  # the section follows
    assert '40,0 m²' in d.totals.text()                           # 10 × 4
    # drag in the miniature: the pool goes there (at its rim level)
    m = d.mini
    m.grab()                                                      # painted once (its frame is set)
    target = m._scr(14.0, 3.0, 0.0)
    QTest.mousePress(m, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target.toPoint())
    assert d.params['x'] == pytest.approx(14.0, abs=0.15) and d.params['y'] == pytest.approx(3.0, abs=0.15)
    n = len(w.stack.done)
    QTest.mouseClick(d.place_here, Qt.MouseButton.LeftButton)
    (pool,) = _pools(w)
    assert pool.params['length'] == pytest.approx(10.0) and pool.params['depth_deep'] == pytest.approx(2.10)
    assert pool.params['x'] == pytest.approx(d.params['x'])
    assert any(e.kind == 'electrical_point' and e.params.get('point_type') == 'pool_supply' for e in w.doc.entities.values())
    assert len(w.stack.done) == n + 1                             # one undo
    _menu(w, 'Επεξεργασία', 'Αναίρεση')
    assert not _pools(w)


def test_free_shape_drawn_with_clicks_in_the_designer(window):
    from archforge.site.pool import area
    w = window
    d = _open_new(w)
    QTest.mouseClick(d.mode.button(1), Qt.MouseButton.LeftButton)  # «Ελεύθερο»
    ed = d.editor
    assert ed.drawing
    ed.grab()
    corners = [(-3, -2), (3, -2), (3, 0), (1, 2), (-3, 2)]           # 6 × 4 with a corner cut
    for u, v in corners:
        QTest.mouseClick(ed, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, ed.to_screen(u, v).toPoint())
    QTest.mouseClick(d.close_shape, Qt.MouseButton.LeftButton)
    assert not ed.drawing
    assert len(d.params['outline']) == 5
    assert area(d.params) == pytest.approx(24 - 2, abs=0.05)          # the cut corner: 2 × 2 / 2
    assert d.boxes['length'].value() == pytest.approx(6.0) and d.boxes['width'].value() == pytest.approx(4.0)
    # placed with a click in the plan: it follows the mouse, R turns it, click puts it
    QTest.mouseClick(d.place_click, Qt.MouseButton.LeftButton)
    tool = w._pool_place_tool
    assert tool.params is not None and not _pools(w)
    pv = w.plan_view
    QTest.keyClick(pv, Qt.Key.Key_R)
    assert tool.params['rotation'] == pytest.approx(15.0)
    pos = QPointF(pv.mapFromScene(20.0, 4.0))
    for t, b in ((QMouseEvent.Type.MouseMove, Qt.MouseButton.NoButton), (QMouseEvent.Type.MouseButtonPress, Qt.MouseButton.LeftButton)):
        e = QMouseEvent(t, pos, pv.viewport().mapToGlobal(pos), Qt.MouseButton.LeftButton if b != Qt.MouseButton.NoButton else Qt.MouseButton.NoButton,
                        b, Qt.KeyboardModifier.NoModifier)
        (pv.mouseMoveEvent if t == QMouseEvent.Type.MouseMove else pv.mousePressEvent)(e)
    (pool,) = _pools(w)
    assert pool.params['x'] == pytest.approx(20.0, abs=0.1) and pool.params['y'] == pytest.approx(4.0, abs=0.1)
    assert pool.params['rotation'] == pytest.approx(15.0)
    assert area(pool.params) == pytest.approx(22.0, abs=0.05)
    assert tool.params is None


def test_shape_from_a_closed_line_of_the_2d_drawing(window):
    from archforge.architecture import drafting
    from archforge.site.pool import area, rim
    w = window
    circle = drafting.entity('circle', 0.0, cx=16.0, cy=4.0, r=2.0)
    w.stack.execute(AddEntity(circle))
    d = _open_new(w)
    QTest.mouseClick(d.mode.button(2), Qt.MouseButton.LeftButton)  # «Από σχέδιο 2D»
    assert d.drawings.currentData() == circle.id
    assert area(d.params) == pytest.approx(math.pi * 4, rel=0.02)    # the circle's shape …
    assert d.params['x'] == pytest.approx(16.0, abs=0.01) and d.params['y'] == pytest.approx(4.0, abs=0.01)   # … and place
    QTest.mouseClick(d.place_here, Qt.MouseButton.LeftButton)
    (pool,) = _pools(w)
    assert max(math.dist(q, (16.0, 4.0)) for q in rim(pool.params)) == pytest.approx(2.0, abs=0.01)


def test_an_existing_pool_is_designed_in_the_same_window(window):
    w = window
    w._place_site_point('pool_place', 16.0, 4.0)
    (pool,) = _pools(w)
    from archforge.ui.pool_designer import open_designer
    d = open_designer(w, pool.id)
    d.boxes['depth_shallow'].setValue(0.90)
    d.kind.setCurrentIndex(d.kind.findData('overflow'))
    n = len(w.stack.done)
    QTest.mouseClick(d.apply_button, Qt.MouseButton.LeftButton)
    assert len(w.stack.done) == n + 1
    assert pool.params['depth_shallow'] == pytest.approx(0.90) and pool.params['pool_type'] == 'overflow'
    _menu(w, 'Επεξεργασία', 'Αναίρεση')
    assert pool.params['pool_type'] == 'skimmer'
