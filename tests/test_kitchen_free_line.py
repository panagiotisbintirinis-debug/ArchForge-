"""Owner 15/10: «ο σχεδιασμός της κουζίνας δεν χρειάζεται να είναι σε γωνία ή Π· πρέπει απλά να μου δίνει
ελεύθερο σχέδιο όπως εγώ θέλω και αυτός να προσαρμόζεται σε αυτό»."""
import itertools
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.kitchen.cabinet_run import plan_path, plan_run, replan


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA_DIR', str(tmp_path))


def _room(doc, st, W=5.0, H=4.0):
    for x1, y1, x2, y2 in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                                             'height': 2.7, 'thickness': 0.2})))


def _box(e):
    q = e.params
    r = math.radians(q['rotation']); c, s = math.cos(r), math.sin(r)
    w, d = q['width'] / 2, q['depth'] / 2
    xs = [q['x'] + c * dx - s * dy for dx in (-w, w) for dy in (-d, d)]
    ys = [q['y'] + s * dx + c * dy for dx in (-w, w) for dy in (-d, d)]
    return min(xs), min(ys), max(xs), max(ys)


def _base(entities):
    return [e for e in entities if e.kind == 'cabinet' and (e.params.get('run_seg') or {}).get('layer') == 'base']


def _no_overlap(entities):
    for a, b in itertools.combinations(_base(entities), 2):
        A, B = _box(a), _box(b)
        assert not (min(A[2], B[2]) - max(A[0], B[0]) > 0.02 and min(A[3], B[3]) - max(A[1], B[1]) > 0.02), \
            (a.name, b.name)


def test_a_line_along_two_walls_turns_the_corner_without_overlap_and_is_one_undo():
    doc = Document(); st = CommandStack(doc); _room(doc, st)
    prop = plan_path(doc, [(1.0, 0.1), (4.9, 0.1), (4.9, 3.0)])
    assert len(prop.spec['run_ids']) == 2 and not prop.problems
    roles = [e.params['run_role'] for e in prop.entities]
    assert 'corner' in roles and roles.count('sink') == 1 and roles.count('hob') == 1   # one of each per kitchen
    _no_overlap(prop.entities)
    n = len(doc.entities)
    st.execute(prop.command())
    assert len(doc.entities) > n
    st.undo()
    assert len(doc.entities) == n


def test_one_straight_piece_on_a_wall_is_the_same_as_the_old_run():
    doc = Document(); st = CommandStack(doc); _room(doc, st)
    a = plan_path(doc, [(1.0, 0.1), (4.0, 0.1)])
    b = plan_run(doc, 1.0, 0.1, 4.0, 0.1)
    widths = lambda p: sorted(round(e.params['width'], 2) for e in _base(p.entities))
    assert widths(a) == widths(b)


def test_away_from_walls_it_is_a_free_island_on_the_chosen_side_without_wall_units():
    doc = Document(); st = CommandStack(doc); _room(doc, st, 6.0, 5.0)
    left = plan_path(doc, [(1.5, 2.5), (4.5, 2.5)])
    assert left.entities and all((e.params.get('run_seg') or {}).get('layer') != 'wall' for e in left.entities)
    assert all(e.params['y'] > 2.5 for e in _base(left.entities))           # left of the drawing direction
    right = plan_path(doc, [(1.5, 2.5), (4.5, 2.5)], flip=True)
    assert all(e.params['y'] < 2.5 for e in _base(right.entities))
    # Stored with its own frame, so «άλλο πλάτος» can plan it again with no wall behind it.
    st.execute(left.command())
    spec = _base(doc.entities.values())[0].params['run_spec']
    assert spec['pick']['free'] and replan(doc, spec) is not None


def test_a_peninsula_from_a_wall_run_starts_beside_it():
    doc = Document(); st = CommandStack(doc); _room(doc, st, 6.0, 5.0)
    prop = plan_path(doc, [(0.5, 0.1), (3.5, 0.1), (3.5, 2.6)])           # along the wall, then out into the room
    assert len(prop.spec['run_ids']) == 2
    _no_overlap(prop.entities)


def test_drawn_with_the_mouse_click_click_double_click_then_enter():
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.marking_menu import run
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _room(window.doc, window.stack)
        before = len(window.doc.entities)
        run(window, 'plan', None, 'mm:krun:start')
        tool = window._cabinet_run
        view = window.plan_view
        view.resize(900, 700); view.fitInView(QRectF(-1, -1, 7, 6))
        click = lambda x, y: QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton,
                                              Qt.KeyboardModifier.NoModifier, view.mapFromScene(QPointF(x, y)))
        click(1.0, 0.15)
        click(4.85, 0.12)                     # near the corner: lands on the wall face
        assert tool.proposal is not None and len(window.doc.entities) == before
        QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                          view.mapFromScene(QPointF(4.88, 3.0)))
        app.processEvents()
        assert tool.proposal is not None and len(tool.proposal.spec['run_ids']) == 2 and not tool.points
        QTest.keyClick(view.viewport(), Qt.Key.Key_Return)
        app.processEvents()
        assert tool.proposal is None and len(window.doc.entities) - before > 10
        window._undo()
        assert len(window.doc.entities) == before                          # one undo
        # Backspace takes back the last point while drawing.
        click(1.0, 0.15); click(3.0, 0.15); click(3.0, 2.0)
        assert len(tool.points) == 3
        QTest.keyClick(view.viewport(), Qt.Key.Key_Backspace)
        assert len(tool.points) == 2 and tool.proposal is not None
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_points_straighten_to_right_angles_unless_shift():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        tool = window._cabinet_run
        tool.points = [(1.0, 1.0)]
        assert tool.point_at(3.0, 1.2) == (3.0, 1.0)
        assert tool.point_at(3.0, 1.2, free=True) == (3.0, 1.2)
    finally:
        window._mark_clean(); window.close(); app.processEvents()
