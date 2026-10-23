"""Owner 23/10: «μεζούρα / αυτόματη τοποθέτηση διαστάσεων όταν το επιλέξουμε, εξωτερικά και εσωτερικά»."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture import dimensions as D
from archforge.core.commands import AddEntity, CommandStack, DeleteEntities, UpdateEntity
from archforge.core.model import Document, Entity


def _house(doc, st, walls=None):
    """10 × 8 m (axes), 25 cm walls, a partition at x = 6; a 1,20 window in the south wall at 2,00 from its start."""
    ids = {}
    walls = walls or {'s': (0, 0, 10, 0), 'e': (10, 0, 10, 8), 'n': (10, 8, 0, 8), 'w': (0, 8, 0, 0), 'mid': (6, 0, 6, 8)}
    for name, (x1, y1, x2, y2) in walls.items():
        e = Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.25})
        st.execute(AddEntity(e)); ids[name] = e.id
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=ids['s'])
    st.execute(AddEntity(win)); ids['win'] = win.id
    return ids


def _values(dims, kind=None):
    return sorted(round(d['value'], 3) for d in dims if kind is None or d['kind'] == kind)


def test_exterior_chain_through_the_window_then_the_whole_facade():
    doc = Document(); st = CommandStack(doc); _house(doc, st)
    st.execute(D.set_auto(doc, 0.0, exterior=True))
    dims = D.storey_dimensions(doc, 0.0)
    south = [d for d in dims if d['n'] == pytest.approx((0.0, -1.0))]
    # Outer face from corner to corner (10 + 2 × 0,125), the window's jambs 1,40 / 2,60 from the axis start.
    assert _values(south) == [1.2, 1.525, 7.525, 10.25]
    whole = max(south, key=lambda d: d['value'])
    assert whole['offset'] > min(d['offset'] for d in south)            # the façade line sits past the chain
    assert all(abs(d['a'][1] + 0.125) < 1e-9 for d in south)           # measured on the outer face
    # The other three façades: one dimension each (no openings); a rectangle needs no overall line.
    assert _values(dims) == sorted([1.2, 1.525, 7.525, 10.25, 10.25, 8.25, 8.25])
    assert not [d for d in dims if d['kind'] == 'interior']


def test_interior_clear_sizes_of_every_room_face_to_face_once():
    doc = Document(); st = CommandStack(doc); _house(doc, st)
    st.execute(D.set_auto(doc, 0.0, interior=True))
    dims = D.storey_dimensions(doc, 0.0)
    assert _values(dims, 'interior') == [3.75, 5.75, 7.75, 7.75]
    assert not [d for d in dims if d['kind'] == 'exterior']


def test_numbers_follow_the_walls_and_the_setting_is_one_undo():
    from archforge.architecture.wall_edit import MoveWall
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    st.execute(D.set_auto(doc, 0.0, exterior=True, interior=True))
    st.execute(MoveWall(ids['mid'], 0.5))                            # half a metre, one way or the other
    inner = _values(D.storey_dimensions(doc, 0.0), 'interior')
    assert inner.count(7.75) == 2
    assert sorted(v for v in inner if v != 7.75) in ([3.25, 6.25], [4.25, 5.25])
    st.undo()
    assert _values(D.storey_dimensions(doc, 0.0), 'interior') == [3.75, 5.75, 7.75, 7.75]
    st.execute(D.set_auto(doc, 0.0, interior=False))
    assert not [d for d in D.storey_dimensions(doc, 0.0) if d['kind'] == 'interior']
    st.undo()
    assert [d for d in D.storey_dimensions(doc, 0.0) if d['kind'] == 'interior']
    st.undo()                                                        # the set itself
    assert D.settings(doc, 0.0) is None and D.storey_dimensions(doc, 0.0) == []


def test_l_shaped_storey_gets_the_overall_size_where_a_facade_does_not_span_it():
    doc = Document(); st = CommandStack(doc)
    _house(doc, st, {'s': (0, 0, 10, 0), 'e': (10, 0, 10, 4), 'n1': (10, 4, 6, 4), 'e2': (6, 4, 6, 8),
                     'n': (6, 8, 0, 8), 'w': (0, 8, 0, 0), 'mid': (6, 0, 6, 4)})
    st.execute(D.set_auto(doc, 0.0, exterior=True))
    dims = D.storey_dimensions(doc, 0.0)
    north = [d for d in dims if d['n'] == pytest.approx((0.0, 1.0))]
    east = [d for d in dims if d['n'] == pytest.approx((1.0, 0.0))]
    assert 10.25 in _values(north) and 6.25 in _values(north)          # overall + the upper wing's façade
    assert 8.25 in _values(east) and 4.25 in _values(east)
    overall = max(north, key=lambda d: d['value'])
    assert overall['offset'] == pytest.approx(D.TIER[2])


def test_tape_dimension_snaps_to_wall_faces_and_saves():
    doc = Document(); st = CommandStack(doc); _house(doc, st)
    # Near the inner corner of the south-west room: the faces' corner, not the axes' crossing.
    x, y, kind = D.tape_snap(doc, 0.16, 0.10, 0.1)
    assert kind == 'corner' and (x, y) == pytest.approx((0.125, 0.125))
    x2, y2, kind2 = D.tape_snap(doc, 5.90, 3.0, 0.1)
    assert kind2 == 'face' and x2 == pytest.approx(5.875)
    off = D.tape_offset((x, y), (x2, y), 3.0, 1.0)
    e = D.tape_entity((x, y), (x2, y), 0.0, off)
    st.execute(AddEntity(e))
    (d,) = D.storey_dimensions(doc, 0.0)
    assert d['value'] == pytest.approx(5.75) and d['kind'] == 'manual' and d['entity_id'] == e.id
    g = D.drawing(d)
    assert g['line'][0][1] == pytest.approx(1.0) and g['angle'] == pytest.approx(0.0)
    back = Document.from_dict(doc.to_dict())
    assert [round(q['value'], 3) for q in D.storey_dimensions(back, 0.0)] == [5.75]
    st.execute(DeleteEntities([e.id]))
    assert D.storey_dimensions(doc, 0.0) == []
    st.undo()
    assert len(D.storey_dimensions(doc, 0.0)) == 1
    with pytest.raises(ValueError):
        D.tape_entity((1, 1), (1, 1.001), 0.0)


def test_plan_draws_them_on_the_dimensions_layer_of_the_active_storey_only():
    from archforge.core import layers as L
    from archforge.core.plan_scene import build_plan_frame
    doc = Document(); st = CommandStack(doc); _house(doc, st)
    st.execute(D.set_auto(doc, 0.0, exterior=True))
    st.execute(AddEntity(D.tape_entity((0, 0), (0, 3), 3.0)))           # another storey
    frame = build_plan_frame(doc)
    labels = [p for p in frame.primitives if p.role == 'dimension-label']
    assert sorted(dict(p.meta)['text'] for p in labels) == sorted(D.fmt(v) for v in (1.2, 1.525, 7.525, 10.25, 10.25, 8.25, 8.25))
    assert all(L.primitive_layer(doc, p) == 'dimensions' for p in frame.primitives if p.role.startswith('dimension'))
    # The set is one entity: hidden → nothing drawn.
    s = D.settings(doc, 0.0)
    st.execute(UpdateEntity(s.id, {'exterior': 0}))
    assert not [p for p in build_plan_frame(doc).primitives if p.role == 'dimension-label']


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 950); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def test_cad_menu_toggles_and_the_tape_places_one_dimension_with_the_mouse(window):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    w, app = window
    _house(w.doc, w.stack)
    acts = w._dimension_actions
    assert acts['exterior'] in w._cad_menu.actions() or any(
        acts['exterior'] in m.actions() for m in w._main_submenus)
    acts['exterior'].trigger(); app.processEvents()
    assert D.settings(w.doc, 0.0).params['exterior'] == 1
    assert [p for p in w.plan_view._entity_items.values() if p == D.settings(w.doc, 0.0).id]
    acts['interior'].trigger(); app.processEvents()
    assert D.settings(w.doc, 0.0).params['interior'] == 1
    w.stack.undo(); assert D.settings(w.doc, 0.0).params['interior'] == 0

    view = w.plan_view
    view.fitInView(-1, -1, 12, 10); app.processEvents()
    pos = lambda x, y: view.mapFromScene(QPointF(x, y))
    w._tape_tool.start()
    for x, y in ((0.13, 4.0), (5.87, 4.0), (3.0, 5.0)):
        QTest.mouseMove(view.viewport(), pos(x, y)); app.processEvents()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos(x, y))
        app.processEvents()
    (dim,) = [e for e in w.doc.entities.values() if e.kind == 'dimension']
    assert D.manual(dim)['value'] == pytest.approx(5.75, abs=0.02)        # face to face, pulled onto the faces
    assert abs(float(dim.params['offset'])) == pytest.approx(1.0, abs=0.1)
    QTest.keyClick(view.viewport(), Qt.Key.Key_Escape); app.processEvents()
    assert not w._tape_tool.active
    w.stack.undo()
    assert not [e for e in w.doc.entities.values() if e.kind == 'dimension']


def test_pdf_prints_the_same_chains(tmp_path):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from archforge.output import pdf
    doc = Document(); st = CommandStack(doc); _house(doc, st)
    st.execute(D.set_auto(doc, 0.0, exterior=True, interior=True))
    calls = []
    real = pdf._dimension
    pdf._dimension = lambda sh, P1, P2, off_dir, off_mm, value, to_mm: (calls.append(round(value, 3)),
                                                                          real(sh, P1, P2, off_dir, off_mm, value, to_mm))
    try:
        out = tmp_path / 'plan.pdf'
        pdf.export_pdf(doc, str(out), include=("plans",))
    finally:
        pdf._dimension = real
    assert out.exists() and out.stat().st_size > 1000
    assert sorted(calls) == sorted([1.2, 1.525, 7.525, 10.25, 10.25, 8.25, 8.25, 3.75, 5.75, 7.75, 7.75])
