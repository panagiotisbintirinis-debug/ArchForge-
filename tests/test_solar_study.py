"""Ηλιασμός και σκίαση κουφωμάτων (κενό 5 της αποτύπωσης, 06/11)."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.site import solar_study as SS


def test_sun_and_north():
    v = SS.sun_vector(12.0, 6, 38.0, 0.0)                     # solar noon, June: the sun in the south, high
    assert v[1] < 0 and abs(v[0]) < 1e-6 and math.degrees(math.asin(v[2])) == pytest.approx(90 - 38 + 23.1, abs=0.6)
    turned = SS.sun_vector(12.0, 6, 38.0, 90.0)              # true north = plan +x: the south sun on −x
    assert turned[0] < -0.2 and abs(turned[1]) < 1e-6        # cos 75° ≈ 0,26 of it is horizontal
    assert SS.sun_vector(0.0, 6, 38.0, 0.0) is None           # night
    assert SS.facing((0, -1)) == 'Ν' and SS.facing((1, 0)) == 'Α' and SS.facing((0, -1), 90.0) == 'Α'   # north on the plan's right: down is east


def test_ray_blocking():
    tri = (np.array([[0.0, 0.0, 1.0]]), np.array([[2.0, 0.0, 0.0]]), np.array([[0.0, 2.0, 0.0]]))
    out = SS.blocked(np.array([[0.5, 0.5, 0.0], [5.0, 5.0, 0.0], [0.5, 0.5, 2.0]]), (0, 0, 1), tri)
    assert list(out) == [True, False, False]                  # below it, beside it, above it


def _box_house(overhang=False):
    doc = Document(); st = CommandStack(doc)
    ids = {}
    for name, (a, b) in {'s': ((0, 0), (6, 0)), 'e': ((6, 0), (6, 5)), 'n': ((6, 5), (0, 5)), 'w': ((0, 5), (0, 0))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 2.8, 'thickness': 0.25})
        st.execute(AddEntity(e)); ids[name] = e.id
    south = Entity('window', {'offset': 3.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=ids['s'])
    north = Entity('window', {'offset': 3.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9}, parent_id=ids['n'])
    st.execute(AddEntity(south)); st.execute(AddEntity(north))
    if overhang:     # a deep slab over the south façade (a balcony above)
        st.execute(AddEntity(Entity('box', {'x': 3.0, 'y': -1.0, 'z': 2.3, 'width': 6.0, 'depth': 2.0, 'height': 0.2, 'rotation': 0})))
    return doc, south, north


def test_south_gets_the_winter_sun_north_none_and_an_overhang_shades_summer():
    doc, south, north = _box_house()
    dec = {r['id']: r for r in SS.study(doc, 12)['rows']}
    assert dec[south.id]['facing'] == 'Ν' and dec[south.id]['sun_h'] > 8 and dec[north.id]['sun_h'] == 0
    doc2, south2, _n = _box_house(overhang=True)
    jun_open = {r['id']: r for r in SS.study(doc, 6)['rows']}[south.id]
    jun_shaded = {r['id']: r for r in SS.study(doc2, 6)['rows']}[south2.id]
    dec_shaded = {r['id']: r for r in SS.study(doc2, 12)['rows']}[south2.id]
    assert jun_shaded['sun_h'] < jun_open['sun_h'] / 2                       # the high summer sun is cut off
    assert dec_shaded['sun_h'] > 0.6 * dec[south.id]['sun_h']                # the low winter sun still comes in
    assert jun_shaded['shaded_pct'] > 50


def test_site_is_kept_in_the_project_with_one_undo():
    doc = Document(); st = CommandStack(doc)
    assert SS.site(doc)['assumed']
    st.execute(SS.set_site_command(doc, 40.6, 15))
    s = SS.site(doc)
    assert (s['latitude'], s['north_deg'], s['assumed']) == (40.6, 15.0, [])
    st.undo()
    assert 'σταθμός' in SS.site(doc)['latitude_from']          # back to the design temperatures' station (ΤΟΤΕΕ 20701-3)
    with pytest.raises(ValueError):
        SS.set_site_command(doc, 80, 0)


def test_the_dialog(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.show(); app.processEvents()
    try:
        doc = w.doc
        for e in _box_house()[0].entities.values():
            w.stack.execute(AddEntity(Entity(e.kind, dict(e.params), parent_id=e.parent_id, name=e.name, id=e.id)))
        w._solar_action.trigger(); app.processEvents()
        dlg = w._solar_dialog
        r = dlg.run()
        assert dlg.table.rowCount() == len(r['rows']) == 2 and 'Ν:' in dlg.summary.text()
        dlg.table.selectRow(0); app.processEvents()
        assert w.doc.selection
        dlg.close()
    finally:
        w._mark_clean(); w.close(); app.processEvents()
