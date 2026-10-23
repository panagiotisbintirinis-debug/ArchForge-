"""HANDOFF 22/10: «τομή αυτόματα στη θέση της (σημάδι T.01/A2.2) και επαλήθευση στάθμεων/εδάφους με την τομή».

The cut line is the section mark written at both ends on the plan; the section sheet (no levels written, only
dimensions — the owner's «NEW VILLA SECTION») is fitted on the pool's water and the walls of the model on that
line, looking the way the drawing looks; the heights the drawing gives the walls are checked against the model."""
import pytest

from archforge.core.model import Document, Entity
from archforge.project import drawing_set as D
from archforge.project import section_fit as F


def _villa():
    """Walls across a north–south line at y = 4, 9, 13 (rooms), a pool 3 m across between y = 0 and 3."""
    doc = Document()
    for y, h in ((4.0, 3.0), (9.0, 3.0), (13.0, 3.0)):
        doc.add(Entity("wall", {"x1": -3.0, "y1": y, "x2": 3.0, "y2": y, "z": 0.0, "height": h, "thickness": 0.3}))
    doc.add(Entity("pool", {"x": 0.0, "y": 1.5, "z": 0.0, "length": 6.0, "width": 3.0, "rotation": 0.0,
                            "pool_type": "skimmer"}))
    return doc


def _section(offset=(5.0, 2.0)):
    """The drawing (metres at its scale): looking so that the uphill (larger y) is on the right; u = y + 1 here
    (the line starts at y = −1); its floor at 2.0 on the page, the walls 3.70 high to the slab top."""
    ox, oy = offset
    segs = []
    for y in (4.0, 9.0, 13.0):
        for face in (y - 0.15, y + 0.15):
            u = face + 1.0
            segs.append((u + ox, oy, u + ox, oy + 3.7))
    segs += [(0.3 + ox, oy + 1.0, 0.3 + ox, oy + 1.4)]          # a short stroke (stone hatch) is not a wall
    water = [[(1.0 + ox, oy - 1.5), (4.0 + ox, oy - 1.5), (4.0 + ox, oy - 0.1), (1.0 + ox, oy - 0.1)],
             [(7.0 + ox, oy + 3.0), (9.0 + ox, oy + 3.0), (9.0 + ox, oy + 3.05), (7.0 + ox, oy + 3.05)]]   # glazing
    return D.Sheet("s.pdf", kind="section", building="NEW VILLA", scale=50, segments=segs, water=water)


def test_the_cut_line_is_the_mark_written_at_both_ends():
    plan = D.Sheet("p.pdf", kind="plan", building="NEW VILLA", scale=50,
                   anchors=[("MT.01", 0, 15), ("MT.01", 0, -1), ("MA2.2", 0.25, 15), ("MA2.2", 0.25, -1), ("L+114.00", 3, 3)])
    other = D.Sheet("o.pdf", kind="plan", building="OLD VILLA", scale=50, anchors=[("MB.01", 0, 0), ("MB.01", 9, 0)])
    placed = {0: (D.Similarity(1.0, 0.0, (10.0, 0.0), 0, 0.0), ""), 1: (D.Similarity(1.0, 0.0, (0.0, 0.0), 0, 0.0), "")}
    lines = F.cut_lines([plan, other], placed, building="NEW VILLA")
    assert [(k, a, b) for k, a, b, _i in lines] == [("T.01", (10.0, 15.0), (10.0, -1.0))]   # not A2.2 beside it


def test_the_section_lands_on_the_pool_and_looks_the_way_the_drawing_does():
    doc = _villa()
    found = F.fit(_section(), doc, ((0.0, 15.0), (0.0, -1.0)))
    assert found["how"] == "νερό πισίνας" and found["flip"] == 1          # A at the south end: uphill on the right
    assert (found["x"], found["y"]) == pytest.approx((-5.0, -2.0))        # the drawing's floor on ±0,00
    assert found["matched"] == found["faces"] == 6
    assert [h[1:] for h in found["heights"]] == [(3.0, 3.7)] * 3
    assert "3,00 m στο μοντέλο, 3,70 m στην τομή" in F.report(found, "Τομή T.01")


def test_without_a_pool_the_walls_place_it():
    doc = _villa()
    doc.remove(next(e.id for e in doc.entities.values() if e.kind == "pool"))
    found = F.fit(_section((2.0, 7.0)), doc, ((0.0, 15.0), (0.0, -1.0)))
    assert found["how"] == "τοίχοι" and found["flip"] == 1
    assert (found["x"], found["y"]) == pytest.approx((-2.0, -7.0))


def test_nothing_on_the_line_nothing_guessed():
    assert F.fit(_section(), Document(), ((0.0, 15.0), (0.0, -1.0))) is None
    assert "2 κλικ" in F.report(None)


def test_the_roof_slab_is_read_between_the_walls():
    """NEW VILLA: ceiling 2,90, slab 3,40–3,60 (the dimensions 2,90 / 0,50 / 0,20), green-roof layers to 3,70."""
    walls = [(3.85, 4.15, 0.0, 3.0), (8.85, 9.15, 0.0, 3.0), (12.85, 13.15, 0.0, 3.0)]
    segs = [(4.2, y, 8.8, y) for y in (0.0, 2.9, 3.4, 3.6, 3.7)] + [(9.2, y, 12.8, y) for y in (0.0, 2.9, 3.4, 3.6, 3.7)]
    segs += [(4.2, 3.2, 5.0, 3.2)]                                     # a short line (a beam's end) is not the slab
    sheet = D.Sheet("s.pdf", kind="section", scale=50, segments=segs)
    slab = F.roof_slab(sheet, {"x": 0.0, "y": 0.0}, walls)
    assert slab == {"bottom": 3.4, "top": 3.6, "thickness": 0.2, "ceiling": 2.9}
    assert F.roof_slab(sheet, None, walls) is None


def test_the_ground_line_of_the_section():
    """Sloping lines are the ground (and the soil over a buried roof); level lines are floors, steep ones walls."""
    segs = [(0.0, 0.0, 4.0, 1.0), (4.0, 1.0, 8.0, 3.0), (0.0, -1.0, 8.0, -1.0), (5.0, 0.0, 5.0, 3.0)]
    sheet = D.Sheet("s.pdf", kind="section", scale=50, segments=segs)
    prof = F.ground_profile(sheet, {"x": 1.0, "y": -0.5}, step=2.0)
    assert prof == [(1.0, -0.5), (3.0, 0.0), (5.0, 0.5), (7.0, 1.5), (9.0, 2.5)]
    flat = lambda x, y: 0.0                                             # the model's ground: level at ±0,00
    off = F.ground_check(prof, ((0.0, 0.0), (10.0, 0.0)), 0, flat)
    assert off == [(7.0, 9.0, 2.5, 0.0)]          # one stretch, the farthest the drawing is off
    assert "στα 7–9 m η τομή έως +2,50, το μοντέλο +0,00" in F.ground_text(off)


def test_auto_place_button_in_the_section_tab():
    """The section tab's «Αυτόματη θέση»: the same fit as the drawing set, for a section line a person drew and
    the engineer's section put under it by hand — placed, turned, one undo."""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QPushButton
    from archforge.core.commands import AddEntity
    from archforge.ui.main_window import MainWindow
    from archforge.ui import section_view as SV
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        for e in _villa().entities.values():
            if e.kind == "wall":
                w.stack.execute(AddEntity(Entity("wall", dict(e.params))))
        line = Entity("section_line", {"x1": 0.0, "y1": 15.0, "x2": 0.0, "y2": -1.0, "flip": 0}, name="Τομή Α-Α")
        w.stack.execute(AddEntity(line))
        segs = [list(s) for s in _section((2.0, 7.0)).segments]
        under = Entity("underlay", {"source": "dxf", "path": "s.dxf", "page": 0, "x": 0.0, "y": 0.0, "z": 0.0, "u0": 0.0,
                                    "v0": 0.0, "m_per_unit": 1.0, "rotation": 0.0, "opacity": 0.6, "unit": "m",
                                    "segments": segs, "section_id": line.id}, name="Υπόβαθρο τομής")
        w.stack.execute(AddEntity(under))
        SV.open_section(w, line.id)
        assert any(b.text() == "Αυτόματη θέση" for b in w._section_panel.findChildren(QPushButton))
        found = SV.auto_place_section(w, line.id)
        assert found["how"] == "τοίχοι" and w.doc.get(line.id).params["flip"] == 1
        assert (w.doc.get(under.id).params["x"], w.doc.get(under.id).params["y"]) == pytest.approx((-2.0, -7.0))
        w.stack.undo()
        assert w.doc.get(under.id).params["x"] == 0.0 and w.doc.get(line.id).params["flip"] == 0
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_the_pool_in_a_section_with_its_levels():
    """Owner 23/10: «το εργαλείο πισίνας πρέπει να έχει και τομές για τα υψομετρικά της» — the line across a pool:
    rim, water (10 cm under a skimmer's coping), the bottom sloping from the shallow to the deep end; an L is
    met piece by piece."""
    from archforge.output.section_cut import pool_cuts
    doc = Document()
    doc.add(Entity("pool", {"x": 0.0, "y": 0.0, "z": 17.65, "length": 8.0, "width": 4.0, "rotation": 0.0,
                            "depth_shallow": 1.1, "depth_deep": 1.8, "pool_type": "skimmer"}))
    doc.add(Entity("terrain", {"x0": -10.0, "y0": -10.0, "x1": 10.0, "y1": 10.0, "elevation": 0.0, "slope_x": 0.0,
                               "slope_y": 0.0, "thickness": 0.5, "altitude_ref": 114.0}))
    (c,) = pool_cuts(doc, {"x1": -7.0, "y1": 0.0, "x2": 7.0, "y2": 0.0, "flip": 0})
    assert (c["u0"], c["u1"]) == pytest.approx((3.0, 11.0), abs=0.06)
    assert c["rim"] == pytest.approx(17.65) and c["water"] == pytest.approx(17.55) and c["altitude_ref"] == 114.0
    assert c["bottom"][0][1] == pytest.approx(17.65 - 1.1, abs=0.02) and c["bottom"][-1][1] == pytest.approx(17.65 - 1.8, abs=0.02)
    assert pool_cuts(doc, {"x1": -7.0, "y1": 5.0, "x2": 7.0, "y2": 5.0, "flip": 0}) == []      # the line misses it


def test_pool_section_button():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QPushButton
    from archforge.ui.main_window import MainWindow
    from archforge.ui import section_view as SV
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w._no_modal_dialogs = True
        w._place_site_point('pool_place', 0.0, 0.0)
        (pool,) = [e for e in w.doc.entities.values() if e.kind == 'pool']
        w.doc.select([pool.id]); w.refresh_inspector()
        assert any(b.text().startswith('Τομή πισίνας') for b in w.findChildren(QPushButton))
        line = SV.pool_section(w, pool.id)
        assert line is not None and w._section_panel.view.data["pools"]
        w.stack.undo()
        assert line.id not in w.doc.entities
    finally:
        w._mark_clean(); w.close(); app.processEvents()
