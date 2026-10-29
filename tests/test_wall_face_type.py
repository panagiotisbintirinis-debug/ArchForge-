"""Walls by their face and a later wall type (owner 29/10, from the ArchiCAD 29 tutorial): never on the axis, and
«του δίνεις τον τύπο, το σχέδιο προσαρμόζεται χωρίς να αλλάξουν οι διαστάσεις»."""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def _outer(doc):
    from archforge.core.plan_scene import wall_poche
    pts = [q for outer, _h in wall_poche(doc) for q in outer]
    return (round(min(p[0] for p in pts), 3), round(min(p[1] for p in pts), 3),
            round(max(p[0] for p in pts), 3), round(max(p[1] for p in pts), 3))


def _box(st, t=0.15):
    ids = []
    for a in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0)]:
        w = Entity('wall', dict(x1=a[0], y1=a[1], x2=a[2], y2=a[3], z=0.0, height=2.7, thickness=t))
        st.execute(AddEntity(w)); ids.append(w.id)
    return ids


def test_an_old_outer_wall_keeps_its_outer_face_when_its_type_changes():
    """Walls drawn before the face was kept (on their axes): an outer wall measures outside — the type grows it inwards,
    the joined walls follow, one undo."""
    from archforge.architecture.wall_types import type_change
    doc = Document(); st = CommandStack(doc); ids = _box(st)
    before = _outer(doc)
    for eid in ids:
        st.execute(type_change(doc, eid, 'stone_uninsulated'))
    assert {round(doc.get(i).params['thickness'], 3) for i in ids} == {0.54}
    assert _outer(doc) == before and len(doc.active_room_faces()) == 1
    for _ in ids:
        st.undo()                                                      # one undo per type change
    assert {round(doc.get(i).params['thickness'], 3) for i in ids} == {0.15} and _outer(doc) == before


def test_the_drawn_face_is_kept_and_a_wall_in_line_does_not_move():
    from archforge.architecture.wall_types import type_change
    doc = Document(); st = CommandStack(doc)
    # Two walls in line, drawn by their lower face (ref_side −1 = right of x1→x2 = −y).
    a = Entity('wall', dict(x1=0, y1=0.075, x2=4, y2=0.075, z=0.0, height=2.7, thickness=0.15, ref_side=-1))
    b = Entity('wall', dict(x1=4, y1=0.075, x2=8, y2=0.075, z=0.0, height=2.7, thickness=0.15, ref_side=-1))
    st.execute(AddEntity(a)); st.execute(AddEntity(b))
    st.execute(type_change(doc, a.id, 'stone_uninsulated'))
    p = doc.get(a.id).params
    assert abs(float(p['y1']) - 0.27) < 1e-9 and abs(float(p['y1']) - 0.54 / 2) < 1e-9     # lower face stays at 0
    assert float(doc.get(b.id).params['y1']) == 0.075                                       # the wall in line stays


def test_a_partition_without_a_measured_face_keeps_its_axis():
    from archforge.architecture.wall_types import type_change
    doc = Document(); st = CommandStack(doc); _box(st)
    mid = Entity('wall', dict(x1=5, y1=0, x2=5, y2=8, z=0.0, height=2.7, thickness=0.10))
    st.execute(AddEntity(mid))
    st.execute(type_change(doc, mid.id, 'brick_partition'))
    assert float(doc.get(mid.id).params['x1']) == 5.0


def test_drawn_with_the_mouse_and_typed_afterwards_the_owners_way():
    """The owner's way (rule 29/10): menu tool, clicks a few pixels off the corners, Properties, Ctrl+Z
    (scripts/user_drive/wall_face_check.py)."""
    os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    here = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'user_drive')
    sys.path.insert(0, os.path.abspath(here))
    import wall_face_check
    assert wall_face_check.run() == []
