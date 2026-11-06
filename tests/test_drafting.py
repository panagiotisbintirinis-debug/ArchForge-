"""Ελεύθερη 2D σχεδίαση (CAD ▸ Σχεδίαση 2D, 06/11): γραμμή, πολυγραμμή, ορθογώνιο, πολύγωνο, κύκλος, τόξο, κείμενο —
ένα στοιχείο ``drafting``, μία αναίρεση, αποθήκευση, κάτοψη, DXF, PDF."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture import drafting as DR
from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document, Entity


def test_shapes_are_checked_measured_and_moved():
    line = DR.entity('line', 0.0, points=[(0, 0), (3, 4)])
    assert DR.length(line.params) == pytest.approx(5.0) and DR.area(line.params) is None
    rect = DR.rectangle((0, 0), (2, 3))
    assert DR.area(rect.params) == pytest.approx(6.0) and DR.length(rect.params) == pytest.approx(10.0)
    circle = DR.entity('circle', 0.0, cx=1, cy=1, r=0.5, hatch='diagonal')
    assert DR.area(circle.params) == pytest.approx(math.pi / 4)
    cx, cy, r, a0, a1 = DR.arc_three_points((1, 0), (0, 1), (-1, 0))          # the upper half circle, counter-clockwise
    assert (cx, cy, r) == pytest.approx((0, 0, 1)) and (a0, a1) == pytest.approx((0, 180))
    cx, cy, r, a0, a1 = DR.arc_three_points((-1, 0), (0, 1), (1, 0))          # same arc drawn the other way
    assert (a0, a1) == pytest.approx((0, 180))
    arc = DR.entity('arc', 0.0, cx=0, cy=0, r=1, a0=0, a1=90)
    assert DR.length(arc.params) == pytest.approx(math.pi / 2)
    assert DR.translated(rect.params, 1, 2)['points'][0] == [1, 2]
    text = DR.entity('text', 0.0, x=1, y=2, text='ΣΗΜΕΙΩΣΗ', height=0.2, angle=30)
    assert 'ΣΗΜΕΙΩΣΗ' in DR.describe(text.params)
    for bad in (lambda: DR.entity('line', 0, points=[(0, 0)]), lambda: DR.entity('line', 0, points=[(0, 0), (0, 0)]),
                lambda: DR.entity('circle', 0, cx=0, cy=0, r=0), lambda: DR.entity('arc', 0, cx=0, cy=0, r=1, a0=10, a1=10),
                lambda: DR.entity('text', 0, x=0, y=0, text='  '), lambda: DR.entity('line', 0, points=[(0, 0), (1, 0)], hatch='solid'),
                lambda: DR.entity('spline', 0), lambda: DR.arc_three_points((0, 0), (1, 1), (2, 2)),
                lambda: DR.rectangle((0, 0), (0, 2))):
        with pytest.raises(ValueError):
            bad()


def test_one_undo_each_move_save_and_load(tmp_path):
    from archforge.project.persistence import load_project, save_project
    doc = Document(); st = CommandStack(doc)
    rect = DR.rectangle((0, 0), (2, 1), hatch='cross', style='dashed', weight=0.5)
    text = DR.entity('text', 0.0, x=0.2, y=0.8, text='Λεπτομέρεια Α', height=0.15)
    st.execute(AddEntity(rect)); st.execute(AddEntity(text))
    st.execute(MoveEntities([rect.id, text.id], 1.0, 0.5))
    assert doc.get(rect.id).params['points'][0] == [1.0, 0.5] and doc.get(text.id).params['x'] == pytest.approx(1.2)
    st.undo()
    assert doc.get(rect.id).params['points'][0] == [0, 0]
    st.undo()
    assert text.id not in doc.entities
    st.redo()
    path = tmp_path / 'd.archforge'
    save_project(doc, str(path))
    loaded = load_project(str(path))
    doc2 = loaded[0] if isinstance(loaded, tuple) else getattr(loaded, 'doc', loaded)
    p = doc2.get(rect.id).params
    assert p['hatch'] == 'cross' and p['style'] == 'dashed' and p['weight'] == 0.5
    assert doc2.get(text.id).params['text'] == 'Λεπτομέρεια Α'
    with pytest.raises(ValueError):
        from archforge.core.commands import UpdateEntity
        st.execute(UpdateEntity(rect.id, {'hatch': 'zebra'}))


def test_plan_frame_layers_and_storeys():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.geometry.plan import NON_GEOMETRY_KINDS
    doc = Document(); st = CommandStack(doc)
    a = DR.entity('line', 0.0, points=[(0, 0), (2, 0)])
    b = DR.entity('circle', 3.0, cx=0, cy=0, r=1)                           # another storey
    t = DR.entity('text', 0.0, x=0, y=1, text='Α', height=0.3)
    for e in (a, b, t):
        st.execute(AddEntity(e))
    roles = {(p.entity_id, p.role, p.kind) for p in build_plan_frame(doc).primitives if p.entity_id in (a.id, b.id, t.id)}
    assert (a.id, 'drafting', 'line') in roles and (t.id, 'drafting-text', 'label') in roles
    assert not any(eid == b.id for eid, _r, _k in roles)                   # only the active storey
    assert 'drafting' in NON_GEOMETRY_KINDS                                 # no 3D, no quantities
    from archforge.core.layers import KIND_LAYERS, LAYERS, ROLE_LAYERS
    assert KIND_LAYERS['drafting'] == 'drafting' and ROLE_LAYERS['drafting-text'] == 'drafting' and 'drafting' in LAYERS


def test_dxf_has_lines_hatches_linetypes_and_text(tmp_path):
    ezdxf = pytest.importorskip('ezdxf')
    from archforge.exchange.dxf import write_storey
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('wall', {'x1': 0, 'y1': 0, 'x2': 4, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': 0.25})))
    st.execute(AddEntity(DR.entity('line', 0.0, points=[(0, 1), (4, 1)], style='dashed', weight=0.35)))
    st.execute(AddEntity(DR.rectangle((0, 2), (1, 3), hatch='diagonal')))
    st.execute(AddEntity(DR.entity('circle', 0.0, cx=2, cy=2.5, r=0.4, hatch='solid')))
    st.execute(AddEntity(DR.entity('text', 0.0, x=0, y=4, text='ΛΕΠΤΟΜΕΡΕΙΑ', height=0.2)))
    path = str(tmp_path / 's.dxf')
    write_storey(doc, 'Ισόγειο', 0.0, path)
    dxf = ezdxf.readfile(path)
    msp = dxf.modelspace()
    lines = [e for e in msp.query('LINE[layer=="A-DETL"]')]
    assert lines and lines[0].dxf.linetype == 'DASHED' and lines[0].dxf.lineweight == 35
    assert msp.query('LWPOLYLINE[layer=="A-DETL"]') and msp.query('CIRCLE[layer=="A-DETL"]')
    assert len(msp.query('HATCH[layer=="A-DETL"]')) == 2
    texts = msp.query('MTEXT[layer=="A-ANNO-TEXT"]')
    assert texts and texts[0].text == 'ΛΕΠΤΟΜΕΡΕΙΑ' and texts[0].dxf.char_height == pytest.approx(0.2)


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1300, 900); w.show(); app.processEvents()
    yield w, app
    w._drafting_tool.cancel(); w._mark_clean(); w.close(); app.processEvents()


def test_the_tool_draws_every_shape_with_one_undo_each(window):
    w, app = window
    t = w._drafting_tool
    assert set(w._drafting_actions) == {'line', 'polyline', 'rectangle', 'polygon', 'circle', 'arc', 'text'}
    count = lambda: sum(1 for e in w.doc.entities.values() if e.kind == 'drafting')
    t.start('line'); t.click(0, 0); t.click(2, 0); t.click(2, 2)          # chained: two lines
    assert count() == 2
    t.start('rectangle'); t.click(3, 0); t.click(5, 1)
    t.start('circle'); t.click(7, 0); t.click(7.5, 0)
    t.start('arc'); t.click(9, 0); t.click(10, 1); t.click(11, 0)
    t.start('polygon'); t.click(0, 3); t.click(1, 3); t.click(1, 4); t.finish()
    t.start('polyline'); t.click(3, 3); t.click(4, 3); t.click(4, 4); t.cancel()    # Esc keeps an open polyline
    t._ask_text(6, 3, 'Σημείωση')
    shapes = sorted(e.params['shape'] for e in w.doc.entities.values() if e.kind == 'drafting')
    assert shapes == ['arc', 'circle', 'line', 'line', 'polygon', 'polygon', 'polyline', 'text']
    circle = next(e for e in w.doc.entities.values() if e.kind == 'drafting' and e.params['shape'] == 'circle')
    assert circle.params['r'] == pytest.approx(0.5)
    n = count()
    w.stack.undo()
    assert count() == n - 1
    w.plan_view.redraw(); app.processEvents()                              # paints without errors (text, hatch)


def test_typed_length_and_angle_and_style_of_the_selection(window):
    w, app = window
    from archforge.ui import drafting_tool as T
    t = w._drafting_tool
    t.start('line'); t.click(0, 0)
    t.typed.update(length='3,5', angle='90')
    assert t.typed_point() == pytest.approx((0.0, 3.5))
    t.cursor = (10, 0); t.typed.update(length='250 cm', angle='')
    assert t.typed_point() == pytest.approx((2.5, 0.0))
    t.cancel()
    t.start('rectangle'); t.click(0, 0); t.click(1, 1); t.cancel()
    rect = next(e for e in w.doc.entities.values() if e.kind == 'drafting')
    w.doc.select([rect.id])
    assert T.edit_selected(w, 'hatch', 'solid') == 1 and w.doc.get(rect.id).params['hatch'] == 'solid'
    assert T.edit_selected(w, 'height', 0.5) == 0                          # not a text: nothing changes
    w.stack.undo()
    assert w.doc.get(rect.id).params['hatch'] == 'none'
    # snap to the end of a drawn shape
    x, y, kind = t.snap(1.02, 0.98, 0.1)
    assert (x, y, kind) == (1, 1, 'corner')


def test_text_reads_at_its_angle_counter_clockwise_and_sits_on_its_point(window):
    """90° = from the point upwards, letters' tops to the left (CAD); 0° = to the right, top of the capitals on the point."""
    from PySide6.QtCore import QPointF
    w, app = window
    view = w.plan_view
    for angle, along in ((0.0, (1, 0)), (90.0, (0, 1))):
        e = DR.entity('text', 0.0, x=2.0, y=1.0, text='ΑΒΓ', height=0.3, angle=angle)
        from archforge.architecture.drafting import primitives
        item = view._drafting_text(primitives(e)[0])
        start, end = item.mapToScene(QPointF(0, 50)), item.mapToScene(QPointF(200, 50))
        d = (end.x() - start.x(), end.y() - start.y())
        assert d[0] * along[0] + d[1] * along[1] > 0 and abs(d[0] * along[1] - d[1] * along[0]) < 1e-6
        if angle == 0.0:
            box = item.mapToScene(item.boundingRect()).boundingRect()
            assert box.left() == pytest.approx(2.0, abs=0.02) and box.top() < 1.0 + 0.1   # the text hangs below the point
        view._scene.removeItem(item)
