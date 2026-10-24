"""Conduit map (owner 18/10): conduits from the cable lines and their destinations, sized from sourced diameters and the owner-selected 30% project limit."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep.conduits import conduit_map, fill, size_for


def test_geometric_fill_and_owner_selected_thirty_percent_limit():
    # Owner 24/10 replaced the old relative-capacity table with geometric fill.
    # Nexans H07V-U 1.5 has nominal OD 3.2; CONFLEX DN16 has min bore 10.1.
    assert fill(16, {1.5:3}) == __import__('pytest').approx(3*3.2**2/10.1**2)
    assert fill(16, {1.5:3}) > .30
    assert size_for({1.5:3},0)==20
    assert size_for({2.5:3},0)==20
    assert size_for({2.5:6},0)==25 and size_for({2.5:6},3)==25
    # Bends require a separate pulling review, not an empty extra conduit.
    assert size_for({10.0:3},0)==32
    assert size_for({1.5:3,2.5:3},0)==25
    assert fill(20,{1.5:3,2.5:3})>.30 and fill(25,{1.5:3,2.5:3})<=.30
    assert size_for({2.5:30},0) is None  # exceeds the existing default maximum DN32
    assert size_for({2.5:3},0,outdoor=True)==50


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
    assert m['pieces'] and all(p['fill'] <= p['fill_limit'] + 1e-9 for p in m['pieces']) and not m['warnings']
    assert set(m['by_size']) <= {16, 20, 25, 32}
    shared = [p for p in m['pieces'] if len(p['lines']) > 1]
    assert shared                                                     # lines going the same way share a conduit
    assert m['split_boxes']                                           # and part in a box
    cooker = [p for p in m['pieces'] if any(c for c in p['lines']) and '3×10' in p['conductors']]
    assert cooker and all(p['dn'] == 32 for p in cooker)
    from archforge.quantities.materials import electrical_list
    names = [r[0] for r in electrical_list(doc)]
    assert any('Φ32' in n for n in names) and any('Φ20' in n for n in names) and any('χωρισμού' in n or 'χωρισμός' in n for n in names)
