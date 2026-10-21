"""Owner 21/10: «σχεδιάζοντας πέτρινο σπίτι, οι τοίχοι σχεδιάζονται από τη μέση του τοίχου και όχι από κάποια άκρη» ·
«όταν ρωτάει από πού μετράμε, ο τοίχος να συνδέεται ανάλογα» — walls drawn by a face, click-click as the human does."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.core.viewport import PointerEvent
from archforge.ui.main_window import MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); app.processEvents()
    yield w
    w.hide()


def _brief(w, measure, thickness=0.6):
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.project.brief import DEFAULTS
    answers = dict(DEFAULTS)
    answers['measure'] = measure
    answers['exterior_walls'] = 'custom'; answers['exterior_walls_text'] = 'πέτρα 60'
    answers['exterior_walls_thickness'] = thickness
    w.stack.execute(AddEntity(Entity('project_brief', answers, name='Στοιχεία έργου')))


def _click_outline(w, pts):
    c = w.plan_view.controller
    c.set_tool('wall')
    for x, y in pts + [pts[0]]:
        ev = PointerEvent(x, y)
        c.pointer_down(ev); c.pointer_move(ev); c.pointer_up(ev)
    c.finish_wall_chain()


def _outline_box(doc):
    """(min x, min y, max x, max y) of the walls' outer faces and of their inner faces."""
    xs, ys = [], []
    walls = [e.params for e in doc.entities.values() if e.kind == 'wall']
    for p in walls:
        h = float(p['thickness']) / 2
        for k in ('1', '2'):
            xs += [float(p['x' + k]) - h, float(p['x' + k]) + h]
            ys += [float(p['y' + k]) - h, float(p['y' + k]) + h]
    return min(xs), min(ys), max(xs), max(ys), len(walls)


RECT = [(0, 0), (10, 0), (10, 8), (0, 8)]


@pytest.mark.parametrize('pts', [RECT, RECT[::-1]], ids=['counter-clockwise', 'clockwise'])
def test_measured_outside_the_drawn_lines_are_the_outer_faces(window, pts):
    _brief(window, 'exterior')
    _click_outline(window, pts)
    x0, y0, x1, y1, n = _outline_box(window.doc)
    assert n == 4
    assert (x0, y0, x1, y1) == pytest.approx((0, 0, 10, 8), abs=1e-6)      # 10 × 8 outside, as drawn
    faces = window.doc.active_room_faces()
    assert len(faces) == 1
    h = float(next(e for e in window.doc.entities.values() if e.kind == 'wall').params['thickness']) / 2
    xs = [q[0] for q in faces[0].polygon]; ys = [q[1] for q in faces[0].polygon]
    assert (min(xs), max(xs), min(ys), max(ys)) == pytest.approx((h, 10 - h, h, 8 - h), abs=1e-6)   # axes half in


def test_measured_inside_the_drawn_lines_are_the_inner_faces(window):
    _brief(window, 'interior')
    _click_outline(window, RECT[::-1])
    x0, y0, x1, y1, _n = _outline_box(window.doc)
    t = float(next(e for e in window.doc.entities.values() if e.kind == 'wall').params['thickness'])
    assert (x0, y0, x1, y1) == pytest.approx((-t, -t, 10 + t, 8 + t), abs=1e-6)  # 10 × 8 inside


def test_without_a_brief_the_line_is_the_axis_and_f_flips_it(window):
    _click_outline(window, RECT)
    assert _outline_box(window.doc)[:4] == pytest.approx((-.075, -.075, 10.075, 8.075), abs=.05)  # axis, as before
    window.stack.undo(); window.stack.undo(); window.stack.undo(); window.stack.undo()
    c = window.plan_view.controller
    assert c.flip_wall_face() == 'left'
    _click_outline(window, RECT)                         # body on the left of a counter-clockwise outline: inside
    x0, y0, x1, y1, n = _outline_box(window.doc)
    assert n == 4 and (x0, y0, x1, y1) == pytest.approx((0, 0, 10, 8), abs=1e-6)


def test_each_wall_is_one_undo_step(window):
    _brief(window, 'exterior')
    n = len(window.stack.done)
    _click_outline(window, RECT)
    assert len(window.stack.done) - n == 4
