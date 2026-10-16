"""Owner: «Η τομή δεν δουλεύει» and «στο Κουκλόσπιτο η αυτόματη στέγη δεν φεύγει».

Section: the line dragged in the plan is the cut line itself; the drawing cuts walls, slabs, the
stair and the roof (closed hatched loops), shows what is behind, and marks the storey levels.
Doll House: every kind of roof/ceiling is hidden and the storeys above the active one are cut off.
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, CreateRoomFloors, CreateRoomRoofs
from archforge.core.model import Document, Entity
from archforge.output.section_cut import cut_section, frame, next_section_name, plan_symbol


def _house(doc=None, st=None):
    if doc is None:
        doc = Document(); st = CommandStack(doc)
    doc.levels['Floor 2'] = 3.0
    walls = []
    for z in (0.0, 3.0):
        for s in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8)]:
            e = Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': z, 'height': 2.8, 'thickness': 0.25})
            st.execute(AddEntity(e)); walls.append(e.id)
    st.execute(AddEntity(Entity('window', {'offset': 2.0, 'width': 1.4, 'height': 1.4, 'sill': 0.9}, parent_id=walls[0])))
    st.execute(AddEntity(Entity('stair', {'x': 1.0, 'y': 5.5, 'lower_z': 0.0, 'upper_z': 3.0, 'upper_floor_z': 3.0,
                                          'upper_slab_thickness': 0.0, 'layout': 'straight', 'angle_deg': 0.0, 'width': 1.0,
                                          'riser_count': 17, 'riser_height': 3.0 / 17, 'tread_depth': 0.28, 'landing_depth': 1.0,
                                          'turn_direction': 1, 'opening_margin': 0.05})))
    st.execute(CreateRoomFloors([f.signature for z in (0.0, 3.0) for f in doc.active_room_faces(z=z)]))
    st.execute(CreateRoomRoofs([f.signature for f in doc.active_room_faces(z=3.0)]))
    from archforge.structure.timber_roof import auto_roofs
    for params, _reason in auto_roofs(doc):
        st.execute(AddEntity(Entity('pitched_roof', params, name='Κεραμοσκεπή')))
    return doc, st, walls


def test_line_is_the_cut_and_the_view_is_square_to_it():
    (ox, oy), along, normal, length = frame({'x1': 0, 'y1': 3, 'x2': 10, 'y2': 3})
    assert (ox, oy) == (0, 3) and along == (1, 0) and normal == (0, 1) and length == 10   # looks north, A left
    _o, along, normal, _l = frame({'x1': 0, 'y1': 3, 'x2': 10, 'y2': 3, 'flip': 1})
    assert normal == (0, -1) and along == (-1, 0)                                         # turned round
    sym = plan_symbol({'x1': 0, 'y1': 3, 'x2': 10, 'y2': 3}, 'Α')
    assert [a[1] for a in sym['arrows']] == [(0, 3.6), (10, 3.6)] and [t for t, _ in sym['labels']] == ['Α', 'Α']
    with pytest.raises(ValueError):
        frame({'x1': 1, 'y1': 1, 'x2': 1, 'y2': 1})


def test_section_cuts_walls_slabs_stair_roof_into_closed_loops():
    doc, _st, walls = _house()
    data = cut_section(doc, {'x1': -1, 'y1': 2.0, 'x2': 11, 'y2': 2.0})    # across the house, through the window
    kinds = {c['kind'] for c in data['cuts'] if c['loops']}
    assert {'wall', 'room_floor', 'pitched_roof'} <= kinds
    cut_walls = [c for c in data['cuts'] if c['kind'] == 'wall' and c['loops']]
    assert {c['id'] for c in cut_walls} >= {walls[1], walls[3], walls[4]}            # east, west, partition at x=5
    # The west wall of the ground floor: about 25 cm × 2.8 m.
    west = [l for c in cut_walls if c['id'] == walls[3] for l in c['loops']][0]
    us, zs = [p[0] for p in west], [p[1] for p in west]
    assert 0.2 < max(us) - min(us) < 0.35 and 2.7 < max(zs) - min(zs) < 2.9
    # Behind the cut: the elevation (incl. the stair at y 5.5), drawn far to near.
    assert data['faces'] and data['faces'][0]['depth'] >= data['faces'][-1]['depth']
    assert any(f['kind'] == 'stair' for f in data['faces'])
    assert [m for _z, m, _n in data['levels']] == ['±0,00', '+3,00']
    u0, z0, u1, z1 = data['bounds']
    assert u0 < 1.2 and u1 > 10.5 and z1 > 6.0                                       # the roof is above the two storeys


def test_through_the_window_the_wall_is_cut_below_and_above():
    doc, _st, walls = _house()
    data = cut_section(doc, {'x1': 2.35, 'y1': -1, 'x2': 2.35, 'y2': 9})               # square to the south wall, mid-window
    south = [c for c in data['cuts'] if c['id'] == walls[0]]
    assert south and len(south[0]['loops']) == 2                                     # parapet under the sill + lintel
    window = [c for c in data['cuts'] if c['kind'] == 'window']
    assert window


def test_section_line_round_trip_and_name():
    doc, st, _w = _house()
    assert next_section_name(doc) == 'Τομή Α-Α'
    e = Entity('section_line', {'x1': 0, 'y1': 3, 'x2': 10, 'y2': 3, 'flip': 0}, name=next_section_name(doc))
    st.execute(AddEntity(e))
    assert next_section_name(doc) == 'Τομή Β-Β'
    st.undo(); assert e.id not in doc.entities
    st.redo(); assert e.id in doc.entities
    import tempfile
    path = os.path.join(tempfile.mkdtemp(), 'section.json')
    doc.save(path)
    back = Document.load(path)
    assert back.get(e.id).kind == 'section_line' and back.get(e.id).name == 'Τομή Α-Α'
    # No mesh of its own: the section line never shows in 3D or in the cut.
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    ev = IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
    assert e.id not in {b.entity_id for b in ev.bodies}
    # Plan: the cut line, two arrows and two letters.
    from archforge.core.plan_scene import build_plan_frame
    prims = [p for p in build_plan_frame(doc).primitives if p.entity_id == e.id]
    assert sum(p.role == 'section-line' for p in prims) == 1 and sum(p.role == 'section-label' for p in prims) == 2


def test_dollhouse_hides_every_roof_and_cuts_above_the_active_storey():
    from archforge.ui import pbr_viewport as pv
    for kind in ('room_roof', 'room_ceiling', 'pitched_roof', 'drywall_ceiling', 'ceiling_joists'):
        assert kind in pv.DOLLHOUSE_HIDDEN_KINDS and f'"{kind}"' in pv._PBR_HTML
    assert 'window.setDollhouseCut' in pv._PBR_HTML
    doc, _st, _w = _house()
    assert abs(pv.dollhouse_cut_z(doc) - 2.82) < 1e-6                                # ground storey active
    from archforge.core.model import WorkPlane
    doc.work_plane = WorkPlane(origin=(0.0, 0.0, 3.0))
    assert abs(pv.dollhouse_cut_z(doc) - 5.82) < 1e-6


def test_window_drag_makes_one_section_with_its_drawing_and_esc_cancels():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication, QPushButton
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        _house(w.doc, w.stack)
        w._start_view_line_tool('section')
        assert w.plan_view.controller.tool == 'view_section'
        # Esc while dragging: nothing is added.
        w.plan_view.begin_view_line(-1, 3); w.plan_view.move_view_line(5, 3)
        w.plan_view.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        assert getattr(w.plan_view, '_view_drag', None) is None
        assert not any(e.kind == 'section_line' for e in w.doc.entities.values())
        # The drag is the cut line: one entity, one undo step, its drawing in a «Τομή Α-Α» tab.
        before = len(w.stack.done)
        w._apply_view_line('section', -1.0, 3.0, 11.0, 3.0)
        lines = [e for e in w.doc.entities.values() if e.kind == 'section_line']
        assert len(lines) == 1 and lines[0].name == 'Τομή Α-Α' and len(w.stack.done) == before + 1
        panel = w._section_panel
        assert w._central_tabs.currentWidget() is panel
        assert w._central_tabs.tabText(w._central_tabs.indexOf(panel)) == 'Τομή Α-Α'
        assert panel.view.data and any(c['kind'] == 'wall' and c['loops'] for c in panel.view.data['cuts'])
        assert {'Άνοιγμα τομής', 'Αντιστροφή κατεύθυνσης', 'Τομή στο 3D'} <= {b.text() for b in w.inspector.findChildren(QPushButton)}
        w.stack.undo()
        assert not any(e.kind == 'section_line' for e in w.doc.entities.values())
    finally:
        w._mark_clean(); w.close(); app.processEvents()
