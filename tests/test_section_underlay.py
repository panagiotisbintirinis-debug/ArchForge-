"""Owner 21/10: «έχω τη NEW VILLA SECTION 1:50 και δεν μπορώ να την εισαγάγω» — the engineer's section as an
underlay of a section tab: placed with two clicks (its ±0,00 on ours), calibrated on a known height, levels read
with the mouse; never drawn in the plan, never moved by a plan move, one undo per step."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document, Entity
from archforge.project import underlay as U

# A section in mm: ground at y = 1000, first slab 3000 higher, a 12 m wide building.
SECTION_DXF = "\n".join([
    "0", "SECTION", "2", "ENTITIES",
    "0", "LINE", "8", "GROUND", "10", "0.0", "20", "1000.0", "11", "14000.0", "21", "1000.0",
    "0", "LINE", "8", "SLAB", "10", "1000.0", "20", "4000.0", "11", "13000.0", "21", "4000.0",
    "0", "ENDSEC", "0", "EOF", ""])


def test_section_underlay_is_kept_apart_from_the_plan_ones():
    doc = Document(); stack = CommandStack(doc)
    plan = Entity('underlay', U.dxf_params('plan.dxf', SECTION_DXF, 'mm'), name='Κάτοψη')
    cut = Entity('underlay', U.for_section(U.dxf_params('cut.dxf', SECTION_DXF, 'mm', z=3.0), 'sec-1'), name='Τομή')
    stack.execute(AddEntity(plan)); stack.execute(AddEntity(cut))
    assert cut.params['z'] == 0.0 and cut.params['section_id'] == 'sec-1'
    assert [e.id for e in U.underlays(doc)] == [plan.id] and [e.id for e in U.underlays(doc, z=0.0)] == [plan.id]
    assert [e.id for e in U.section_underlays(doc, 'sec-1')] == [cut.id] and not U.section_underlays(doc, 'other')
    # A plan move never drags the section's drawing (its x, y are the section's u, z).
    stack.execute(MoveEntities([plan.id, cut.id], 1.0, 1.0))
    assert doc.get(cut.id).params['x'] == 0.0 and doc.get(plan.id).params['x'] == 1.0
    again = Document.from_dict(doc.to_dict())
    assert again.get(cut.id).params['section_id'] == 'sec-1'


def test_placing_moves_the_clicked_point_onto_the_target():
    p = U.for_section(U.dxf_params('cut.dxf', SECTION_DXF, 'mm'), 's')
    ground = U.to_model(p, 1000.0, 1000.0)                    # the drawing's ±0,00 at the building's left edge
    p.update(U.moved(p, ground, (0.0, 0.0)))
    assert U.to_model(p, 1000.0, 1000.0) == pytest.approx((0.0, 0.0))
    assert U.to_model(p, 1000.0, 4000.0) == pytest.approx((0.0, 3.0))   # its first slab reads +3,00


def test_section_tab_imports_places_calibrates_and_reads_levels(tmp_path):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication, QGraphicsPathItem, QPushButton
    from archforge.ui.main_window import MainWindow
    from archforge.ui import section_view, underlay_tools
    from tests.test_section_cut import _house
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        _house(w.doc, w.stack)
        w._apply_view_line('section', -1.0, 3.0, 11.0, 3.0)
        sid = next(e.id for e in w.doc.entities.values() if e.kind == 'section_line')
        panel = w._section_panel
        assert 'Υπόβαθρο τομής…' in {b.text() for b in panel.findChildren(QPushButton)}
        path = tmp_path / 'section.dxf'; path.write_text(SECTION_DXF)
        before = len(w.stack.done)
        e = section_view.import_section_underlay(w, sid, path=str(path), unit='mm')
        assert len(w.stack.done) == before + 1 and w.doc.get(e.id).params['section_id'] == sid
        drawn = [i for i in panel.view.scene().items() if isinstance(i, QGraphicsPathItem) and i.zValue() == -60]
        assert len(drawn) == 1                                                   # in the section …
        w.plan_view.redraw()
        assert not [i for i in w.plan_view.scene().items() if isinstance(i, QGraphicsPathItem) and i.zValue() == -60]  # … not the plan
        # Import goes straight to placing: the drawing's ground at its left edge → ArchForge's ±0,00 at u = 1.
        assert w._underlay_calibration['mode'] == 'place' and panel.view._picking()
        p = w.doc.get(e.id).params
        underlay_tools.calibration_click(w, *U.to_model(p, 1000.0, 1000.0))
        underlay_tools.calibration_click(w, 1.0, 0.0)
        p = w.doc.get(e.id).params
        assert U.to_model(p, 1000.0, 4000.0) == pytest.approx((1.0, 3.0)) and w._underlay_calibration is None
        # Calibration on the storey height: the drawing says 3,00 but it is really 3,20.
        underlay_tools.start_calibration(w, e.id)
        assert panel.view._picking()['mode'] == 'calibrate'
        underlay_tools.calibration_click(w, 1.0, 0.0)
        underlay_tools.calibration_click(w, 1.0, 3.0, real=3.2)
        p = w.doc.get(e.id).params
        assert U.to_model(p, 1000.0, 4000.0) == pytest.approx((1.0, 3.2))
        w._undo()
        assert U.to_model(w.doc.get(e.id).params, 1000.0, 4000.0) == pytest.approx((1.0, 3.0))
        # Esc stops a placing in progress; the level under the mouse reads like a level mark.
        underlay_tools.start_placing(w, e.id)
        panel.view.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier))
        assert w._underlay_calibration is None
        assert section_view.level_readout(4.15, 3.2) == 'Υψόμετρο +3,20 · 4,15 m κατά μήκος της τομής'
        assert section_view.level_readout(0.0, 0.0).startswith('Υψόμετρο ±0,00')
        # Its properties offer the placing again and name the section.
        w.doc.select([e.id]); w.refresh_inspector()
        assert 'Τοποθέτηση στην τομή (2 κλικ)' in {b.text() for b in w.inspector.findChildren(QPushButton)}
    finally:
        w._underlay_calibration = None
        w._mark_clean(); w.close(); app.processEvents()


def test_pdf_section_underlay_renders_in_the_section(tmp_path):
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
    from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem
    from archforge.ui.main_window import MainWindow
    from archforge.ui import section_view
    from tests.test_section_cut import _house
    app = QApplication.instance() or QApplication([])
    pdf = tmp_path / 'section.pdf'
    writer = QPdfWriter(str(pdf))
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A3), QPageLayout.Orientation.Landscape, QMarginsF()))
    painter = QPainter(writer); painter.drawLine(100, 2000, 4000, 2000); painter.end()
    w = MainWindow()
    try:
        _house(w.doc, w.stack)
        w._apply_view_line('section', -1.0, 3.0, 11.0, 3.0)
        sid = next(e.id for e in w.doc.entities.values() if e.kind == 'section_line')
        e = section_view.import_section_underlay(w, sid, path=str(pdf), scale=50, page=0)
        p = w.doc.get(e.id).params
        assert p['source'] == 'pdf' and p['section_id'] == sid
        items = [i for i in w._section_panel.view.scene().items() if isinstance(i, QGraphicsPixmapItem)]
        assert len(items) == 1
        assert items[0].sceneBoundingRect().width() == pytest.approx(p['page_w'] * 0.0254 / 72 * 50, rel=0.02)   # A3 at 1:50 ≈ 21 m
    finally:
        w._underlay_calibration = None
        w._mark_clean(); w.close(); app.processEvents()
