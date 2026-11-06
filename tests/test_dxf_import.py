"""Εισαγωγή DXF ως επεξεργάσιμο σχέδιο 2D (κενό 3 της αποτύπωσης, 06/11)."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

ezdxf = pytest.importorskip('ezdxf')

from archforge.core.commands import CommandStack
from archforge.core.model import Document
from archforge.exchange import dxf_import as DI


def _sample(path, units=4):
    d = ezdxf.new('R2010', setup=True)
    d.header['$INSUNITS'] = units                          # 4 = mm
    msp = d.modelspace()
    msp.add_line((0, 0), (4000, 0), dxfattribs={'linetype': 'DASHED', 'lineweight': 35, 'layer': 'A-DETL'})
    msp.add_lwpolyline([(0, 1000, 0, 0, 1), (2000, 1000), (2000, 2000), (0, 2000)], format='xyseb', close=True)  # bulge
    msp.add_circle((3000, 1500), 500)
    msp.add_arc((3000, 1500), 800, 0, 90)
    msp.add_text('ΤΟΜΗ Α-Α', dxfattribs={'height': 250, 'insert': (0, 3000)})
    msp.add_mtext('Σημείωση\\Pδεύτερη', dxfattribs={'char_height': 200, 'insert': (0, 4000)})
    h = msp.add_hatch(color=1); h.set_solid_fill(); h.paths.add_polyline_path([(5000, 0), (6000, 0), (6000, 1000), (5000, 1000)], is_closed=True)
    blk = d.blocks.new('ΠΑΡΑΘΥΡΟ'); blk.add_line((0, 0), (1000, 0)); blk.add_line((0, 100), (1000, 100))
    msp.add_blockref('ΠΑΡΑΘΥΡΟ', (7000, 0), dxfattribs={'xscale': 2.0, 'rotation': 90})
    msp.add_linear_dim(base=(0, -500), p1=(0, 0), p2=(4000, 0)).render()
    d.saveas(path)


def test_every_kind_comes_in_in_metres_with_style_and_what_is_left_is_said(tmp_path):
    path = str(tmp_path / 'detail.dxf'); _sample(path)
    r = DI.read(path)
    assert r['m_per_unit'] == 0.001
    c = r['counts']
    assert c['line'] >= 3 and c['polygon'] >= 2 and c['circle'] == 1 and c['arc'] == 1 and c['text'] == 3
    by = {}
    for e in r['entities']:
        by.setdefault(e.params['shape'], []).append(e.params)
    dashed = next(p for p in by['line'] if p['points'][1] == [4.0, 0.0])
    assert dashed['style'] == 'dashed' and dashed['weight'] == 0.35
    bulged = next(p for p in by['polygon'] if p['hatch'] == 'none')
    assert len(bulged['points']) > 4                                    # the bulge became points on its arc
    assert next(p for p in by['polygon'] if p['hatch'] == 'solid')['points'][0] == pytest.approx([5.0, 0.0])
    t = next(p for p in by['text'] if p['text'] == 'ΤΟΜΗ Α-Α')
    assert t['height'] == pytest.approx(0.25) and t['y'] == pytest.approx(3.25)        # baseline lifted to the top
    assert any(p['text'] == 'Σημείωση δεύτερη' for p in by['text'])
    block = [p for p in by['line'] if p['points'][0][0] == pytest.approx(7.0, abs=0.2)]
    assert len(block) == 2 and math.dist(*block[0]['points']) == pytest.approx(2.0)   # scaled ×2, turned 90°
    # The dimension comes in as what it draws: its lines, arrows and text; its DEFPOINTS are not printed, not counted.
    # (its text is what the file's dimension style writes: «400000» with ezdxf's own style — kept as written)
    assert len(by['text']) == 3 and not r['skipped']
    assert 'δεν διαβάστηκαν' not in DI.report_text(r)


def test_units_override_origin_and_one_undo(tmp_path):
    path = str(tmp_path / 'u.dxf'); _sample(path, units=0)
    assert DI.read(path)['m_per_unit'] == 1.0                             # unknown: metres, unless told
    assert DI.read(path, unit='cm')['m_per_unit'] == 0.01
    moved = DI.read(path, unit='mm', to_origin=True)
    assert moved['bounds'][0] == pytest.approx(0) and moved['bounds'][1] == pytest.approx(0)
    doc = Document(); st = CommandStack(doc)
    cmd, r = DI.import_command(doc, path, 'mm')
    st.execute(cmd)
    n = sum(1 for e in doc.entities.values() if e.kind == 'drafting')
    assert n == len(r['entities']) > 8
    st.undo()
    assert not any(e.kind == 'drafting' for e in doc.entities.values())
    empty = str(tmp_path / 'empty.dxf'); ezdxf.new().saveas(empty)
    with pytest.raises(ValueError):
        DI.import_command(doc, empty)


def test_round_trip_export_then_import(tmp_path):
    """What ArchForge writes as DXF comes back as drawing: the plan of a storey re-read."""
    from archforge.architecture import drafting as DR
    from archforge.core.commands import AddEntity
    from archforge.exchange.dxf import write_storey
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(DR.rectangle((0, 0), (2, 1), hatch='diagonal')))
    st.execute(AddEntity(DR.entity('text', 0.0, x=0, y=3, text='ΑΒΓ', height=0.2)))
    path = str(tmp_path / 'p.dxf')
    write_storey(doc, 'Ισόγειο', 0.0, path)
    r = DI.read(path)
    shapes = {e.params['shape'] for e in r['entities']}
    assert {'polygon', 'text'} <= shapes


def test_the_menu_command(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.exchange_export import import_dxf_drawing
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    try:
        assert w._import_dxf_drawing_action in w._file_import_menu.actions() or w._import_dxf_drawing_action.text()
        path = str(tmp_path / 'm.dxf'); _sample(path)
        r = import_dxf_drawing(w, path, 'mm')
        assert r and sum(1 for e in w.doc.entities.values() if e.kind == 'drafting') == len(r['entities'])
        assert 'DXF ως σχέδιο 2D' in w.statusBar().currentMessage()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
