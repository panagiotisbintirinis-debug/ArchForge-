"""Conduit map (owner 18/10): conduits from the cable lines and their destinations, sized by the owner's fill table."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep.conduits import conduit_map, fill, size_for


def test_owner_fill_table_and_one_size_up_after_two_bends():
    assert size_for({1.5: 3}, 0) == 16                     # one lighting line L N PE
    assert size_for({2.5: 3}, 0) == 20                     # one socket line 3×2,5 (Φ16 takes 2)
    assert size_for({2.5: 6}, 0) == 25 and size_for({2.5: 6}, 2) == 25
    assert size_for({2.5: 6}, 3) == 32                     # > 2 bends without a box → one size up
    assert size_for({10.0: 3}, 0) == 32                    # cooker 3×10 like NYM-J 3×10
    assert size_for({1.5: 3, 2.5: 3}, 0) == 25             # mixed: 3/5 + 3/3 > 1 in Φ20
    assert fill(20, {1.5: 3, 2.5: 3}) > 1 and fill(25, {1.5: 3, 2.5: 3}) <= 1
    assert size_for({2.5: 30}, 0) is None                  # more than Φ32 holds: another conduit
    assert size_for({2.5: 3}, 0, outdoor=True) == 50       # in the ground: double wall ≥ Φ50


def _house(stack):
    for x1, y1, x2, y2 in ((0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0), (4, 0, 4, 6)):
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))


def _pt(stack, kind, x, y):
    stack.execute(AddEntity(Entity('electrical_point', {'x': x, 'y': y, 'z': 0.0, 'point_type': kind})))


def test_map_shares_conduits_within_the_table_and_boxes_where_they_part():
    doc = Document(); st = CommandStack(doc); _house(st)
    _pt(st, 'panel', 0.15, 3.0)
    for x, y in ((0.15, 1.0), (0.15, 5.0), (3.85, 1.0), (4.15, 1.0), (7.85, 3.0), (7.85, 5.0), (2.0, 5.85), (6.0, 5.85)):
        _pt(st, 'socket', x, y)
    _pt(st, 'cooker', 7.85, 1.0)
    for x, y in ((2.0, 3.0), (6.0, 3.0)):
        _pt(st, 'light', x, y)
    m = conduit_map(doc)
    assert m['pieces'] and all(p['fill'] <= 1 + 1e-9 for p in m['pieces']) and not m['warnings']
    assert set(m['by_size']) <= {16, 20, 25, 32}
    shared = [p for p in m['pieces'] if len(p['lines']) > 1]
    assert shared                                                     # lines going the same way share a conduit
    assert m['split_boxes']                                           # and part in a box
    cooker = [p for p in m['pieces'] if any(c for c in p['lines']) and '3×10' in p['conductors']]
    assert cooker and all(p['dn'] == 32 for p in cooker)
    from archforge.quantities.materials import electrical_list
    names = [r[0] for r in electrical_list(doc)]
    assert any('Φ32' in n for n in names) and any('Φ20' in n for n in names) and any('χωρισμού' in n or 'χωρισμός' in n for n in names)
