"""Wall layers as bands (spec §3 step 4): mitred at corners so insulation is continuous, stopped at a T, cut at
openings — the same bands in plan, section and DXF."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.wall_layer_plan import boundaries, wall_bands
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.core.plan_scene import build_plan_frame


def _room(window=False):
    """A 5 × 4 room of double brick with 5 cm XPS (27 cm) and a 13 cm partition meeting the south wall (T)."""
    doc = Document(); st = CommandStack(doc)
    ids = []
    for a, b in [((0, 0), (5, 0)), ((5, 0), (5, 4)), ((5, 4), (0, 4)), ((0, 4), (0, 0))]:
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.7,
                            'thickness': 0.27, 'wall_type': 'brick_double_insulated'})
        st.execute(AddEntity(e)); ids.append(e.id)
    e = Entity('wall', {'x1': 2.5, 'y1': 0, 'x2': 2.5, 'y2': 4, 'z': 0.0, 'height': 2.7, 'thickness': 0.13,
                        'wall_type': 'brick_partition'})
    st.execute(AddEntity(e)); ids.append(e.id)
    if window:
        st.execute(AddEntity(Entity('window', {'offset': 1.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9},
                                    parent_id=ids[0])))
    return doc, ids


def _insulation(doc, wid):
    [band] = [b for b in wall_bands(doc, doc.get(wid)) if b['insulation']]
    return band


def test_insulation_runs_round_the_corner_unbroken():
    doc, ids = _room()
    south, east = _insulation(doc, ids[0]), _insulation(doc, ids[1])
    (s_out, _), = south['islands']
    (e_out, _), = east['islands']
    # The two insulation bands share their edge on the corner's bisector (5, 0)–(5±, …): same two points.
    shared = {tuple(round(c, 6) for c in p) for p in s_out} & {tuple(round(c, 6) for c in p) for p in e_out}
    assert len(shared) == 2
    for x, y in shared:
        assert x - 5 == pytest.approx(-(y - 0))                                     # on the bisector x−5 = −y
    assert south['hatch'] == 'insulation_rigid' and south['material'] == 'xps'


def test_a_partition_stops_at_the_face_of_the_wall_it_meets():
    doc, ids = _room()
    bands = wall_bands(doc, doc.get(ids[4]))
    ys = [y for b in bands for outer, _h in b['islands'] for _x, y in outer]
    assert min(ys) == pytest.approx(0.135) and max(ys) == pytest.approx(4 - 0.135)


def test_an_opening_cuts_every_layer_and_their_boundaries():
    doc, ids = _room(window=True)
    for band in wall_bands(doc, doc.get(ids[0])):
        assert len(band['islands']) == 2                                            # left and right of the window
    lines = boundaries(doc, doc.get(ids[0]))
    assert len(lines) == 8                                                          # 4 boundaries × 2 pieces
    for pts, _ins in lines:
        xs = sorted(x for x, _y in pts)
        assert xs[1] <= 0.4 + 1e-9 or xs[0] >= 1.6 - 1e-9                           # nothing across the window


def test_plan_draws_one_hatched_band_per_layer():
    doc, ids = _room()
    fills = [p for p in build_plan_frame(doc).primitives if p.role == 'wall-layer-fill' and p.entity_id == ids[0]]
    assert [dict(p.meta)['material'] for p in fills] == ['cement_plaster', 'hollow_brick', 'xps', 'hollow_brick',
                                                         'cement_plaster']
    assert all(dict(p.meta)['hatch'] for p in fills)


def test_section_shows_the_cut_walls_layers():
    from archforge.output.section_cut import cut_section
    doc, ids = _room()
    data = cut_section(doc, {'x1': 1.0, 'y1': -1.0, 'x2': 1.0, 'y2': 5.0, 'flip': 0})
    south = [l for l in data['layers'] if l['id'] == ids[0]]
    assert [l['material'] for l in sorted(south, key=lambda l: min(p[0] for p in l['points']))] == \
        ['cement_plaster', 'hollow_brick', 'xps', 'hollow_brick', 'cement_plaster']
    xps = next(l for l in south if l['material'] == 'xps')
    us = [p[0] for p in xps['points']]; zs = [p[1] for p in xps['points']]
    assert max(us) - min(us) == pytest.approx(0.05, abs=1e-6) and max(zs) - min(zs) == pytest.approx(2.7, abs=1e-6)


def test_dxf_hatches_each_layer_with_its_pattern(tmp_path):
    from ezdxf import recover
    from archforge.exchange.dxf import write_storey
    doc, ids = _room()
    path = tmp_path / 'room.dxf'
    write_storey(doc, 'Ground', 0.0, str(path))
    dxf, auditor = recover.readfile(str(path))
    assert not auditor.errors
    patterns = {h.dxf.pattern_name for h in dxf.modelspace().query('HATCH[layer=="A-WALL-PATT"]')}
    assert {'ANSI31', 'ANSI37', 'AR-SAND'} <= patterns


def test_the_section_view_paints_the_layers(tmp_path):
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.section_view import SectionView
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        doc, ids = _room()
        for e in doc.entities.values():
            w.stack.execute(AddEntity(e.clone()))
        line = Entity('section_line', {'x1': 1.0, 'y1': -1.0, 'x2': 1.0, 'y2': 5.0, 'flip': 0})
        w.stack.execute(AddEntity(line))
        from PySide6.QtCore import QRectF
        view = SectionView(w); view.resize(600, 400); view.show_section(line.id)
        view.fitInView(QRectF(0.6, -0.2, 0.8, 1.0))                                     # the south wall
        assert len(view.data['layers']) == 10                                         # 5 layers × south and north
        image = QImage(600, 400, QImage.Format.Format_RGB32); image.fill(QColor(255, 255, 255))
        painter = QPainter(image); view.render(painter); painter.end()
        blue = sum(1 for x in range(0, 600, 3) for y in range(0, 400, 3)
                   if QColor(image.pixel(x, y)).blue() > QColor(image.pixel(x, y)).red() + 40)
        assert blue > 500                                                                # the XPS layer, light blue
    finally:
        w._mark_clean(); w.close(); app.processEvents()
