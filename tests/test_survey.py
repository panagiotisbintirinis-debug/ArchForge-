"""Αποτύπωση από μετρήσεις (owner 24/10: «δέκα διαγώνιες μετρήσεις για ένα δωμάτιο τεσσάρων τοίχων για να βγάλω τα
παράγωνα — ειδικά σε μια νέα αποτύπωση υφισταμένου»)."""
import math

import pytest

from archforge.architecture import survey as S
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity

TRUE = [(0.1, 0.1), (4.9, 0.1), (5.0, 3.9), (0.15, 3.85)]     # the real inner faces: not square


def _room():
    doc = Document(); st = CommandStack(doc)
    pts = [(0, 0), (5, 0), (5, 4), (0, 4)]                    # drawn by eye: a 5 × 4 rectangle on the axes
    for a, b in zip(pts, pts[1:] + pts[:1]):
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                             'height': 2.7, 'thickness': 0.2})))
    face = doc.active_room_faces()[0]
    return doc, st, S.survey_room(doc, face)


def _measured(pairs):
    return [(i, j, math.dist(TRUE[i], TRUE[j])) for i, j in pairs]


SIDES = [(0, 1), (1, 2), (2, 3), (3, 0)]


def test_the_room_is_read_on_its_inner_faces():
    _doc, _st, room = _room()
    assert room['corners'] == 4
    assert [c for q in room['inner'] for c in q] == pytest.approx([0.1, 0.1, 4.9, 0.1, 4.9, 3.9, 0.1, 3.9])


def test_sides_and_diagonals_give_the_out_of_square_room_and_the_walls_follow():
    doc, st, room = _room()
    out = S.solve(room['inner'], _measured(SIDES + [(0, 2), (1, 3)]))
    assert out['rank_ok'] and out['rms'] < 1e-6
    for got, want in zip(out['corners'], TRUE):
        assert got == pytest.approx(want, abs=1e-6)
    st.execute(S.apply_command(doc, room, out['corners']))
    again = S.survey_room(doc, doc.active_room_faces()[0])
    for got, want in zip(again['inner'], TRUE):
        assert got == pytest.approx(want, abs=1e-6)
    st.undo()
    back = S.survey_room(doc, doc.active_room_faces()[0])['inner']
    assert [c for q in back for c in q] == pytest.approx([c for q in room['inner'] for c in q])


def test_sides_alone_do_not_fix_the_shape_and_it_is_said():
    _doc, _st, room = _room()
    out = S.solve(room['inner'], _measured(SIDES))
    assert not out['rank_ok']


def test_a_misread_tape_shows_in_the_residuals():
    _doc, _st, room = _room()
    meas = _measured(SIDES + [(0, 2), (1, 3)])
    meas[1] = (1, 2, meas[1][2] + 0.10)                       # side 2–3 read 10 cm long
    out = S.solve(room['inner'], meas)
    assert out['rms'] > 0.01
    worst = max(out['residuals'], key=lambda r: abs(r[3]))
    assert abs(worst[3]) > 0.01
