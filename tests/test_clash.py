"""Έλεγχος συγκρούσεων (κενό 2 της αποτύπωσης, 06/11): Η/Μ ↔ φέρων, κούφωμα ↔ φέρων, έπιπλο ↔ δομικό, σημείο ↔ κολόνα."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.coordination import clash as C
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity

OWNER = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


def _frame():
    doc = Document(); st = CommandStack(doc)
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.25})
    st.execute(AddEntity(wall))
    col = Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.4, 'depth': 0.4, 'height': 3.0, 'rotation': 0.0,
                                       'role': 'structural', 'construction': 'reinforced_concrete', 'base_level': 'Ground'}, name='Κ1')
    beam = Entity('structural_beam', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 2.5, 'width': 0.25, 'height': 0.5,
                                      'role': 'structural', 'construction': 'reinforced_concrete', 'level': 'Ground',
                                      'section': 'rectangular'}, name='Δ1')
    st.execute(AddEntity(col)); st.execute(AddEntity(beam))
    return doc, st, wall, col, beam


def test_geometry_segment_and_boxes():
    box = C.Box('b', 'structural_beam', 0, 0, 1.0, 0.1, 0.0, 2.5, 3.0)
    inside, at = C.segment_in_box((0, -1, 2.7), (0, 1, 2.7), box)               # straight across the beam
    assert inside == pytest.approx(0.2) and at == pytest.approx((0, 0, 2.7))
    assert C.segment_in_box((0, -1, 2.0), (0, 1, 2.0), box)[0] == 0            # under it
    assert C.segment_in_box((0, -1, 2.48), (0, 1, 2.48), box, 0.025)[0] > 0    # the pipe's radius reaches it
    turned = C.Box('c', 'structural_column', 0, 0, 0.2, 0.2, 0.7853981634, 0, 3)
    assert C.box_overlap(turned, C.Box('o', 'window', 0.3, 0, 0.1, 0.1, 0, 1, 2)) > 0
    assert C.box_overlap(turned, C.Box('o', 'window', 0.5, 0, 0.1, 0.1, 0, 1, 2)) == 0


def test_beam_in_a_window_column_in_a_door_furniture_and_points():
    doc, st, wall, col, beam = _frame()
    win = Entity('window', {'offset': 1.2, 'width': 1.0, 'height': 1.4, 'sill': 1.2}, parent_id=wall.id)   # top 2,60 > 2,50
    door = Entity('door', {'offset': 3.3, 'width': 0.9, 'height': 2.1}, parent_id=wall.id)                  # 2,85…3,75: the column
    sofa = Entity('library_object', {'x': 3.0, 'y': 0.4, 'z': 0.0, 'width': 0.8, 'depth': 0.6, 'height': 0.8, 'rotation': 0.0})
    socket = Entity('electrical_point', {'x': 3.05, 'y': 0.0, 'z': 0.0, 'point_type': 'socket'})
    for e in (win, door, sofa, socket):
        st.execute(AddEntity(e))
    found = C.find(doc)
    pairs = {(c.a_id, c.b_id) for c in found}
    assert (win.id, beam.id) in pairs and (door.id, col.id) in pairs and (sofa.id, col.id) in pairs
    assert (socket.id, col.id) in pairs
    assert next(c for c in found if c.a_id == win.id and c.b_id == beam.id).depth == pytest.approx(0.10)
    # Fixes clear them: the window lower, the door away from the column.
    st.execute(UpdateEntity(win.id, {'sill': 1.0}))
    st.execute(UpdateEntity(door.id, {'offset': 5.0}))
    pairs = {(c.a_id, c.b_id) for c in C.find(doc)}
    assert (win.id, beam.id) not in pairs and (door.id, col.id) not in pairs


def test_networks_through_the_frame_one_clash_per_member(monkeypatch):
    doc, st, wall, col, beam = _frame()
    segs = [('cold', (0.5, -1, 2.7), (0.5, 1, 2.7), 0.02),      # through the beam
            ('cold', (1.5, -1, 2.7), (1.5, 1, 2.7), 0.02),      # again: same member, summed
            ('supply', (2.0, 0, 1.0), (4.0, 0, 1.0), 0.02),     # along the wall, through the column
            ('drainage', (0, 2, 0.1), (6, 2, 0.1), 0.11)]       # clear of everything
    monkeypatch.setattr(C, 'network_segments', lambda d: segs)
    found = [c for c in C.find(doc) if c.group == 'Η/Μ ↔ φέρων']
    assert {(c.a_kind, c.b_id) for c in found} == {('network:cold', beam.id), ('network:supply', col.id)}
    cold = next(c for c in found if c.a_kind == 'network:cold')
    assert '2 διελεύσεις' in cold.note and cold.depth == pytest.approx(2 * (0.25 + 0.02), abs=0.01)


def test_the_owner_project_and_the_list_tab():
    from archforge.project.persistence import load_project
    from archforge.quantities import schedules as S
    r = load_project(OWNER); doc = r[0] if isinstance(r, tuple) else getattr(r, 'doc', r)
    data = S.clashes(doc)
    assert data['rows'] and all(row['ids'] for row in data['rows'])
    groups = {row['group'] for row in data['rows']}
    assert groups <= {'Η/Μ ↔ φέρων', 'Κούφωμα ↔ φέρων', 'Αντικείμενο ↔ δομικό', 'Σημείο Η/Μ ↔ κολόνα'}
    # one row per network and member: no repeated pair
    keys = [(row['a'], tuple(row['ids'])) for row in data['rows'] if row['group'] == 'Η/Μ ↔ φέρων']
    assert len(keys) == len(set(keys))
    assert 'clashes' in S.LISTS and S.clashes(doc)['title'] in S.html(doc, ['clashes'])


def test_the_menu_opens_the_clash_list_and_a_row_selects_both(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    try:
        doc, st = w.doc, w.stack
        wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.25})
        st.execute(AddEntity(wall))
        col = Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.4, 'depth': 0.4, 'height': 3.0,
                                           'rotation': 0.0, 'role': 'structural', 'construction': 'reinforced_concrete',
                                           'base_level': 'Ground'}, name='Κ1')
        st.execute(AddEntity(col))
        door = Entity('door', {'offset': 3.3, 'width': 0.9, 'height': 2.1}, parent_id=wall.id)
        st.execute(AddEntity(door))
        w._clash_action.trigger(); app.processEvents()
        tab = w._lists_tab
        assert w._central_tabs.currentWidget() is tab and tab.key == 'clashes'
        row = next(i for i, r in enumerate(tab.data['rows']) if door.id in r['ids'])
        tab.table.selectRow(row); app.processEvents()
        assert set(w.doc.selection) == {door.id, col.id}
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_cast_in_conduits_are_work_before_the_pour_not_clashes(monkeypatch):
    """Ιδιοκτήτης 06/11: «μπορεί να γίνει προσωλήνωση… σωληνώσεις στα μπετά»."""
    from archforge.quantities import schedules as S
    doc, st, wall, col, beam = _frame()
    panel = Entity('electrical_point', {'x': 0.5, 'y': 0.0, 'z': 0.0, 'point_type': 'panel', 'cast_in_concrete': 1})
    st.execute(AddEntity(panel))
    segs = [('electrical', (2.0, 0, 2.35), (2.2, 0, 2.35), 0.02), ('electrical', (2.2, 0, 2.35), (2.4, 0, 2.35), 0.02),
            ('electrical', (2.4, 0, 2.35), (4.0, 0, 2.35), 0.02),           # one conduit, three grid pieces: 1 crossing
            ('electrical', (3.0, -1, 2.7), (3.0, 1, 2.7), 0.02),            # across the beam (and the column top)
            ('cold', (0.5, -1, 2.7), (0.5, 1, 2.7), 0.02)]                  # water through the beam: still a clash
    monkeypatch.setattr(C, 'network_segments', lambda d: segs)
    groups = {(c.a_kind, c.b_id) for c in C.find(doc)}
    assert ('network:cold', beam.id) in groups and not any(k == 'network:electrical' for k, _b in groups)
    rows = {r['ids'][0]: r for r in S.cast_in(doc)['rows']}
    assert rows[col.id]['passes'] == 2 and rows[beam.id]['passes'] >= 1
    assert C.crossings([(0, 0, 0), (0.2, 0, 0), (0.4, 0, 0), (2, 0, 0)]) and len(C.crossings([(0, 0, 0), (0.2, 0, 0), (2, 0, 0)])) == 2
    st.execute(UpdateEntity(panel.id, {'cast_in_concrete': 0}))           # the project says no: clashes again
    assert any(c.a_kind == 'network:electrical' for c in C.find(doc))
    assert S.cast_in(doc)['title'].startswith('Διελεύσεις προς έγκριση') and 'στατικός' in S.cast_in(doc)['check'][0]


def test_distribution_from_the_ceiling():
    """Ιδιοκτήτης 06/11: «σε άλλες χώρες… διανομή από το ταβάνι»."""
    from archforge.mep.electrical import route_cables
    from archforge.mep.electrical_routes import mode_of
    doc = Document(); st = CommandStack(doc)
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 5)), ((6, 5), (0, 5)), ((0, 5), (0, 0))):
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3.0, 'thickness': 0.25})))
    panel = Entity('electrical_point', {'x': 0.2, 'y': 2.0, 'z': 0.0, 'point_type': 'panel'})
    socket = Entity('electrical_point', {'x': 5.8, 'y': 3.0, 'z': 0.0, 'point_type': 'socket'})
    island = Entity('electrical_point', {'x': 3.0, 'y': 2.5, 'z': 0.0, 'point_type': 'socket'})
    for e in (panel, socket, island):
        st.execute(AddEntity(e))
    assert mode_of(doc, socket) == 'wall' and mode_of(doc, island) == 'floor'
    walls_z = {round(a[2], 2) for a, b, _g, _c in route_cables(doc)['runs'] if abs(a[2] - b[2]) < 1e-9}
    st.execute(UpdateEntity(panel.id, {'distribution': 'ceiling'}))
    assert mode_of(doc, socket) == 'ceiling' and mode_of(doc, island) == 'floor'   # the island keeps its floor feed
    ceil_z = {round(a[2], 2) for a, b, _g, _c in route_cables(doc)['runs'] if abs(a[2] - b[2]) < 1e-9}
    assert 2.35 in walls_z and 2.35 not in ceil_z and max(ceil_z) > 2.35
    with pytest.raises(ValueError):
        st.execute(UpdateEntity(panel.id, {'distribution': 'roof'}))


def test_routes_go_round_a_column_in_the_floor_not_through_it_nor_in_the_air():
    """Κείμενο ιδιοκτήτη 06/11: «στην τοιχοποιία… μέσα από το τούβλο· στη συνάντηση με το μπετόν στρίβει… στο δάπεδο
    10–20 cm από τη βάση της κολόνας»."""
    from archforge.mep.electrical import route_cables
    from archforge.mep.electrical_routes import COLUMN_CLEARANCE
    doc = Document(); st = CommandStack(doc)
    for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 5)), ((8, 5), (0, 5)), ((0, 5), (0, 0))):
        st.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 3.0, 'thickness': 0.25})))
    col = Entity('structural_column', {'x': 4.0, 'y': 0.0, 'z': 0.0, 'width': 0.4, 'depth': 0.4, 'height': 3.0, 'rotation': 0.0,
                                       'role': 'structural', 'construction': 'reinforced_concrete', 'base_level': 'Ground'})
    st.execute(AddEntity(col))
    st.execute(AddEntity(Entity('electrical_point', {'x': 1.0, 'y': 0.2, 'z': 0.0, 'point_type': 'panel'})))
    st.execute(AddEntity(Entity('electrical_point', {'x': 7.0, 'y': 0.2, 'z': 0.0, 'point_type': 'socket'})))
    box = next(b for b in C.structure(doc) if b.eid == col.id)
    runs = route_cables(doc)['runs']
    assert not any(C.segment_in_box(a, b, box, 0.01)[0] > C.TOLERANCE for a, b, _g, _c in runs)
    # every horizontal run is in a wall (the brick) or down in the floor screed — none hanging in the room
    walls = [C._wall(e) for e in C._visible(doc, 'wall')]
    for a, b, _g, _c in runs:
        if abs(a[2] - b[2]) > 1e-9:
            continue
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        in_brick = any(abs(w.local(*mid)[0]) <= w.hu + 0.15 and abs(w.local(*mid)[1]) <= w.hv + 0.11 for w in walls)
        assert in_brick or a[2] < 0.2
        if a[2] < 0.2:                                   # in the floor: clear of the column by its clearance
            u, v = box.local(*mid)
            assert abs(u) > box.hu + COLUMN_CLEARANCE - 0.11 or abs(v) > box.hv + COLUMN_CLEARANCE - 0.11
    assert any(a[2] < 0.2 for a, b, _g, _c in runs)      # it did go down to pass the column


def test_cached_routing_is_redone_when_the_frame_changes():
    """Bots 06/11: the cache key of the cable routing had no columns / beams — a column added after the cables
    left the old runs through it."""
    from archforge.core.model import Document, Entity
    from archforge.mep.electrical import route_cables_cached
    doc = Document()
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 5)), ((6, 5), (0, 5)), ((0, 5), (0, 0))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7, 'thickness': 0.2}))
    doc.add(Entity('electrical_point', {'point_type': 'panel', 'x': 0.1, 'y': 1.0, 'z': 0.0}))
    doc.add(Entity('electrical_point', {'point_type': 'socket', 'x': 5.9, 'y': 1.0, 'z': 0.0}))
    first = route_cables_cached(doc)
    assert route_cables_cached(doc) is first
    doc.add(Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.3, 'depth': 0.3, 'height': 2.7,
                                         'rotation': 0.0, 'role': 'structural', 'construction': 'reinforced_concrete',
                                         'base_level': 'Ground'}))
    assert route_cables_cached(doc) is not first
