"""The engineer's drawing (PDF / DXF) as an underlay: placement, calibration, persistence, plan, menu."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.project import underlay as U

DXF = "\n".join([
    "0", "SECTION", "2", "ENTITIES",
    "0", "LINE", "8", "WALLS", "10", "1000.0", "20", "2000.0", "11", "9000.0", "21", "2000.0",
    "0", "LWPOLYLINE", "8", "WALLS", "70", "1",
    "10", "1000.0", "20", "2000.0", "10", "9000.0", "20", "2000.0", "10", "9000.0", "20", "8000.0",
    "0", "CIRCLE", "8", "COLUMNS", "10", "5000.0", "20", "5000.0", "40", "200.0",
    "0", "ENDSEC", "0", "EOF", ""])


def test_dxf_lines_units_and_placement():
    found = U.parse_dxf_segments(DXF)
    assert found['layers']['WALLS'] == 1 + 3 and found['layers']['COLUMNS'] == U.ARC_SEGMENTS
    w, h = U.dxf_size_m(DXF, 'mm')
    assert (round(w, 2), round(h, 2)) == (8.0, 6.0) and U.dxf_size_m(DXF, 'cm')[0] == pytest.approx(80.0)
    p = U.dxf_params('plan.dxf', DXF, 'mm')
    segs = U.model_segments(p)
    assert segs[0] == pytest.approx((0.0, 0.0, 8.0, 0.0))                     # lower-left at the origin, metres


def test_calibration_keeps_the_first_point_and_fixes_the_scale():
    p = U.dxf_params('plan.dxf', DXF, 'mm')
    p.update(U.calibrated(p, (0.0, 0.0), (8.0, 0.0), 8.4))                     # the 8 m line is really 8.40 m
    a = U.to_model(p, 1000.0, 2000.0)
    b = U.to_model(p, 9000.0, 2000.0)
    assert a == pytest.approx((0.0, 0.0)) and math.dist(a, b) == pytest.approx(8.4)
    with pytest.raises(ValueError):
        U.calibrated(p, (1.0, 1.0), (1.0, 1.0), 2.0)


def test_pdf_scale_from_the_title_block():
    p = U.pdf_params('plan.pdf', 0, 50, (842.0, 595.0))                       # A4 landscape at 1:50
    # one inch on paper (72 PDF points, ISO 32000) = 25.4 mm → × 50 in reality
    assert U.to_model(p, 72.0, 0.0)[0] == pytest.approx(0.0254 * 50)


def test_underlay_is_saved_undoable_movable_and_drawn_only_on_its_storey():
    from archforge.core.plan_scene import build_plan_frame
    doc = Document(); stack = CommandStack(doc)
    e = Entity('underlay', U.dxf_params('plan.dxf', DXF, 'mm'), name='Υπόβαθρο')
    stack.execute(AddEntity(e))
    stack.execute(MoveEntities([e.id], 2.0, 1.0))
    assert U.model_segments(doc.get(e.id).params)[0][:2] == pytest.approx((2.0, 1.0))
    stack.undo()
    again = Document.from_dict(doc.to_dict())
    assert again.get(e.id).kind == 'underlay' and len(again.get(e.id).params['segments']) == len(e.params['segments'])
    assert not [p for p in build_plan_frame(doc).primitives if p.entity_id == e.id]   # not design geometry
    assert U.underlays(doc, z=0.0) and not U.underlays(doc, z=3.0)
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(e.id, {'source': 'dwg'}))


def test_strip_moves_with_both_ends():
    from tests.test_electrical import _pt
    doc = Document(); stack = CommandStack(doc)
    strip = _pt(stack, 'led_strip', 1.0, 1.0, x2=3.0, y2=1.0)
    stack.execute(MoveEntities([strip.id], 0.5, 2.0))
    p = doc.get(strip.id).params
    assert (p['x'], p['y'], p['x2'], p['y2']) == (1.5, 3.0, 3.5, 3.0)


def test_import_dxf_from_the_menu_then_calibrate_with_two_clicks(tmp_path):
    from PySide6.QtWidgets import QApplication, QGraphicsPathItem
    from archforge.ui.main_window import MainWindow
    from archforge.ui import underlay_tools
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        assert window._import_underlay_action in window._file_import_menu.actions()
        path = tmp_path / 'plan.dxf'; path.write_text(DXF)
        e = underlay_tools.import_drawing(window, str(path), unit='mm')
        assert window.doc.get(e.id).params['z'] == 0.0
        window.plan_view.redraw()
        paths = [i for i in window.plan_view.scene().items() if isinstance(i, QGraphicsPathItem) and i.zValue() == -60]
        assert paths and all(i not in window.plan_view._entity_items for i in paths)          # never takes a click
        underlay_tools.start_calibration(window, e.id)
        assert window.plan_view.controller.tool == 'underlay_calibrate'
        window.plan_view.sitePointRequested.emit('underlay_calibrate', 0.0, 0.0)
        underlay_tools.calibration_click(window, 8.0, 0.0, real=8.4)
        assert window.doc.get(e.id).params['m_per_unit'] == pytest.approx(0.001 * 8.4 / 8.0)
        window._undo()
        assert window.doc.get(e.id).params['m_per_unit'] == pytest.approx(0.001)
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_pdf_underlay_renders_a_real_page(tmp_path):
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
    from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
    from archforge.ui.main_window import MainWindow
    from archforge.ui import underlay_tools
    app = QApplication.instance() or QApplication([])
    pdf = tmp_path / 'plan.pdf'
    w = QPdfWriter(str(pdf))
    w.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF()))
    painter = QPainter(w); painter.drawLine(100, 100, 2000, 100); painter.end()
    window = MainWindow()
    try:
        e = underlay_tools.import_drawing(window, str(pdf), scale=50, page=0)
        p = window.doc.get(e.id).params
        assert p['source'] == 'pdf' and p['page_w'] == pytest.approx(842, abs=1) and p['scale_denominator'] == 50
        window.plan_view.redraw()
        items = [i for i in window.plan_view.scene().items() if isinstance(i, QGraphicsPixmapItem)]
        assert items
        r = items[0].sceneBoundingRect()
        assert r.width() == pytest.approx(p['page_w'] * 0.0254 / 72 * 50, rel=0.02)    # ≈ 14,85 m at 1:50
        assert r.left() == pytest.approx(0.0, abs=0.05) and r.top() == pytest.approx(0.0, abs=0.05)
    finally:
        window._mark_clean(); window.close(); app.processEvents()
