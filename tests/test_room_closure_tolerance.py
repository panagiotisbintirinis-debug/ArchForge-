"""Owner 22/10: «αν δεν κλείνουν χώροι, κάτι είναι λάθος»; «το πρόβλημα με τα μικρά κενά υπάρχει και στο κανονικό
σχεδιαστικό … δεν κάνει σναπ όπως έπρεπε»; «το πρόβλημα είναι βαθύτερο και το software απλά το αναπαράγει».

A wall is a body of its thickness: one whose body reaches another's closes the room (the graph only — the walls
stay as drawn); a real gap does not.  The plan's snap reach is in screen pixels, at any zoom."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.topology import room_faces
from archforge.core.commands import AddEntities, CommandStack
from archforge.core.model import Document, Entity


def _room(short=0.0, t=0.25):
    doc = Document(); st = CommandStack(doc)
    sides = [(0, 0, 6, 0), (6, 0, 6, 4), (6, 4, 0, 4), (0, 4, 0, short)]      # the last wall stops `short` before the first
    walls = [Entity('wall', {'x1': a, 'y1': b, 'x2': c, 'y2': d, 'z': 0.0, 'height': 2.8, 'thickness': t}) for a, b, c, d in sides]
    st.execute(AddEntities(walls))
    return doc, walls


@pytest.mark.parametrize('short', [0.0, 0.03, 0.12, 0.20])
def test_a_wall_drawn_a_little_short_still_closes_the_room(short):
    doc, walls = _room(short)
    (face,) = room_faces(doc, z=0.0)
    assert len(face.polygon) == 4
    assert doc.get(walls[3].id).params['y2'] == short                        # the wall itself is not changed


def test_a_real_gap_stays_open():
    doc, _walls = _room(0.60)                                                 # 60 cm: a passage, not a slip
    assert room_faces(doc, z=0.0) == []


def test_t_junction_short_of_the_wall_splits_the_room():
    doc, _walls = _room(0.0)
    st = CommandStack(doc)
    st.execute(AddEntities([Entity('wall', {'x1': 3.0, 'y1': 0.04, 'x2': 3.0, 'y2': 3.97, 'z': 0.0, 'height': 2.8, 'thickness': 0.1})]))
    assert len(room_faces(doc, z=0.0)) == 2


def test_plan_snap_reach_is_in_screen_pixels():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        pv = w.plan_view
        pv.resetTransform(); pv.scale(50.0, -50.0)                            # 50 px per metre
        pv.set_snap_pixels(14)
        assert pv.controller.snap_tolerance == pytest.approx(14 / 50)
        pv.scale(4.0, 4.0)                                                     # zoomed in: the same 14 px is less model
        pv._sync_snap_tolerance()
        assert pv.controller.snap_tolerance == pytest.approx(14 / 200)
        assert w._mockup_snap_reach.currentText() == '14 px'
        w._mockup_snap_reach.setCurrentText('30 px')
        assert pv.controller.snap_tolerance == pytest.approx(30 / 200)
    finally:
        w._mark_clean(); w.close(); app.processEvents()
