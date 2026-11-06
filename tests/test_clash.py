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
