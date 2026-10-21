"""Owner 21/10: «ανέβασα ένα PDF αλλά δεν το ανοίγει ως κτίριο» — walls proposed from the engineer's drawing."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.architecture.walls_from_lines import find_walls


def _house_lines(t=0.30, p=0.10):
    """A 10 × 8 m house (outer faces), walls t thick, a partition at x = 6, floor hatching, a dimension line."""
    L = []
    def rect(x0, y0, x1, y1):
        L.extend([(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)])
    rect(0, 0, 10, 8)                       # outer faces
    rect(t, t, 10 - t, 8 - t)               # inner faces
    L += [(6 - p / 2, t, 6 - p / 2, 8 - t), (6 + p / 2, t, 6 + p / 2, 8 - t)]        # partition
    L += [(0.5 + 0.2 * k, 1.0, 0.5 + 0.2 * k, 3.0) for k in range(20)]               # hatching (tiles)
    L += [(0, -1.0, 10, -1.0), (0, -1.2, 0, -0.8), (10, -1.2, 10, -0.8)]             # dimension line
    return L


def test_pairs_become_walls_and_patterns_do_not():
    walls = find_walls(_house_lines())
    thick = sorted(round(t, 2) for _a, _b, t in walls)
    assert thick.count(0.30) == 4 and thick.count(0.10) == 1, walls
    assert len(walls) == 5                                         # no wall out of the hatching or the dimension
    # Axes halfway between the faces; corners meet.
    xs = sorted({round(c, 3) for a, b, t in walls if t > .2 for c in (a[0], b[0])})
    assert xs[0] == pytest.approx(.15) and xs[-1] == pytest.approx(9.85)
    part = next(w for w in walls if abs(w[2] - .1) < 1e-6)
    assert {round(part[0][1], 2), round(part[1][1], 2)} == {.15, 7.85}             # T junctions on both axes


def test_pdf_from_cad_to_walls_in_one_undo(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    from PySide6.QtCore import QLineF, QMarginsF, QSizeF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter, QPen
    pdf = str(tmp_path / 'plan.pdf')
    w = QPdfWriter(pdf)
    w.setPageLayout(QPageLayout(QPageSize(QSizeF(420, 297), QPageSize.Unit.Millimeter), QPageLayout.Orientation.Portrait,
                                QMarginsF(0, 0, 0, 0)))
    w.setResolution(72)                                            # 1 painter unit = 1 PDF point
    painter = QPainter(w)
    painter.setPen(QPen())
    k = 1000.0 / 50 / (25.4 / 72)                                  # 1:50 → points per metre
    h = w.height()
    for x1, y1, x2, y2 in _house_lines():
        painter.drawLine(QLineF(50 + x1 * k, h - (100 + y1 * k), 50 + x2 * k, h - (100 + y2 * k)))
    painter.end()

    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.project.underlay import pdf_params
    from archforge.ui import walls_from_underlay as W
    from archforge.ui.main_window import MainWindow
    win = MainWindow()
    try:
        win.stack.execute(AddEntity(Entity('underlay', pdf_params(pdf, 0, 50, (w.width(), h)), name='plan.pdf')))
        n = len(win.stack.done)
        made = W.run(win, ask=False)
        assert made and len(made) == 5
        assert len(win.stack.done) == n + 1                       # one undo for all of them
        assert sorted(win.doc.selection) == sorted(e.id for e in made)
        assert len(win.doc.active_room_faces()) == 2              # two rooms, closed
        win.stack.undo()
        assert not [e for e in win.doc.entities.values() if e.kind == 'wall']
    finally:
        win.hide()
