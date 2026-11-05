"""Εξωτερικοί τοίχοι από τους χώρους (05/11): η ακτίνα έχανε τους τοίχους μιας εσοχής και έπαιρνε κομμάτια στον κήπο.

owner_111: δύο τοίχοι του ισογείου στην εισέχουσα γωνία του Γ λείπαν από απώλειες, θερμογέφυρες, κέλυφος.
"""
import os

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep.ventilation import exterior_walls

OWNER = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


def _wall(st, a, b):
    e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 2.7, 'thickness': 0.2})
    st.execute(AddEntity(e))
    return e


def test_a_narrow_courtyard_notch_and_a_garden_stub():
    """A U-shaped house (notch 2 m wide, 4 m deep, open to the north) and a short wall in the garden."""
    doc = Document(); st = CommandStack(doc)
    pts = [(0, 0), (10, 0), (10, 8), (6, 8), (6, 4), (4, 4), (4, 8), (0, 8)]
    ring = [_wall(st, pts[k], pts[(k + 1) % len(pts)]) for k in range(len(pts))]
    stub = _wall(st, (14, 2), (14, 3))
    ext = {w.id: n for w, n in exterior_walls(doc, 0.0)}
    assert set(ext) == {w.id for w in ring}                  # every wall of the outline, notch included
    assert stub.id not in ext                                # no room on either side: not envelope
    notch_bottom = ring[4]                                   # (6,4)→(4,4): open to the north (+y)
    assert ext[notch_bottom.id][1] > 0.99
    side_left, side_right = ring[5], ring[3]                 # (4,4)→(4,8) faces +x · (6,8)→(6,4) faces −x
    assert ext[side_left.id][0] > 0.99 and ext[side_right.id][0] < -0.99


def test_a_storey_without_closed_rooms_keeps_the_ray_test():
    doc = Document(); st = CommandStack(doc)
    w = _wall(st, (0, 0), (5, 0))
    assert [x.id for x, _n in exterior_walls(doc, 0.0)] == []          # free on both sides, as before
    _wall(st, (5, 0), (5, 4)); _wall(st, (5, 4), (0, 4))                # three sides, not closed
    assert w.id in {x.id for x, _n in exterior_walls(doc, 0.0)}         # open plan: the ray decides, as before


def test_owner_111_ground_floor_envelope_is_complete():
    from archforge.project.persistence import load_project
    doc = load_project(OWNER).doc
    ext = exterior_walls(doc, 0.0)
    key = lambda w: tuple(round(float(w.params[k]), 2) for k in ('x1', 'y1', 'x2', 'y2'))
    found = {key(w) for w, _n in ext}
    assert (1.04, -3.42, -1.8, -3.42) in found and (1.04, -5.62, -4.2, -5.62) in found
    assert not any(abs(k[0] - 6.57) < 0.01 for k in found)             # the 5 cm stub outside the house
    assert len(ext) == 17
