"""Dimensions drive the walls (owner 24/10: «οι τοίχοι πρέπει να ακολουθούν τις διαστάσεις, καθώς το χέρι και το μάτι
δεν είναι κανόνας — ακόμα και εάν το δόντι στον τοίχο είναι 5 πόντους σε ένα μπάνιο»)."""
import math

import pytest

from archforge.architecture import dimensions as D
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity

T = 0.2


def _wall(st, a, b):
    st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7,
                                         'thickness': T})))



def _doc(pts):
    doc = Document(); st = CommandStack(doc)
    for a, b in zip(pts, pts[1:] + pts[:1]):
        _wall(st, a, b)
    st.execute(D.set_auto(doc, 0.0, exterior=True))
    return doc, st


def _dim(doc, value, n):
    return min((d for d in D.storey_dimensions(doc, 0.0) if d['kind'] == 'exterior' and d['n'] == n),
               key=lambda d: abs(d['value'] - value))


def test_typing_a_facade_length_moves_the_wall_at_its_end():
    doc, st = _doc([(0, 0), (0, 3), (5, 3), (5, 0)])          # 5 × 3 on the axes → 5,20 × 3,20 outside
    d = _dim(doc, 5.2, (0.0, -1.0))
    assert d['value'] == pytest.approx(5.2)
    wid, cmd = D.drive(doc, 0.0, d, 5.5)
    st.execute(cmd)
    assert _dim(doc, 5.5, (0.0, -1.0))['value'] == pytest.approx(5.5)
    xs = sorted({round(float(e.params[k]), 6) for e in doc.entities.values() if e.kind == 'wall' for k in ('x1', 'x2')})
    assert xs == [0.0, 5.3]                                    # one wall moved 30 cm, its neighbours stretched
    st.undo()
    assert _dim(doc, 5.2, (0.0, -1.0))['value'] == pytest.approx(5.2)


def test_a_5_cm_tooth_in_a_bathroom_wall_is_set_by_its_dimension():
    # The south side steps 5 cm out half way: the step's own face is dimensioned, and typing 0,10 makes it 10 cm.
    doc, st = _doc([(0, 0), (0, 3), (4, 3), (4, -0.05), (2, -0.05), (2, 0)])
    tooth = min((d for d in D.storey_dimensions(doc, 0.0) if d['kind'] == 'exterior'), key=lambda d: d['value'])
    assert tooth['value'] == pytest.approx(0.05)
    wid, cmd = D.drive(doc, 0.0, tooth, 0.10)
    st.execute(cmd)
    tooth = min((d for d in D.storey_dimensions(doc, 0.0) if d['kind'] == 'exterior'), key=lambda d: d['value'])
    assert tooth['value'] == pytest.approx(0.10)


def test_a_dimension_not_ending_on_a_wall_face_is_refused_in_greek():
    doc, st = _doc([(0, 0), (0, 3), (5, 3), (5, 0)])
    with pytest.raises(ValueError, match='παρειά τοίχου'):
        D.drive(doc, 0.0, {'a': (20.0, 20.0), 'b': (21.0, 20.0), 'value': 1.0}, 2.0)
