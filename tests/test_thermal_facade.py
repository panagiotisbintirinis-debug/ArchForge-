"""«Θερμική όψη» (ιδιοκτήτης 05/11: «να φαίνονται οι θερμοκρασίες οπτικά από εξωτερική πλευρά χρωματικά»)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.mep import surface_temperature as S


def _house(doc, st, wall_type='brick_double_insulated'):
    ids = {}
    for name, (a, b) in {'s': ((0, 0), (6, 0)), 'e': ((6, 0), (6, 5)), 'n': ((6, 5), (0, 5)), 'w': ((0, 5), (0, 0))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 2.7, 'thickness': 0.27,
                            'wall_type': wall_type})
        st.execute(AddEntity(e)); ids[name] = e.id
    win = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.2, 'sill': 0.9, 'u_value': 2.8}, parent_id=ids['s'])
    st.execute(AddEntity(win)); ids['win'] = win.id
    return ids


def test_outside_surface_temperature_from_u_and_rse_of_table_3b():
    from archforge.architecture.wall_types import indicative_u
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    r = S.surface_temperatures(doc)
    ti, te = r['theta_i'], r['theta_e']
    u = indicative_u('brick_double_insulated', doc)
    assert r['items'][ids['s']]['theta'] == pytest.approx(te + u * 0.04 * (ti - te), abs=0.01)
    # The window loses more: warmer outside, as a camera sees it.
    assert r['items'][ids['win']]['theta'] == pytest.approx(te + 2.8 * 0.04 * (ti - te), abs=0.01)
    assert r['items'][ids['win']]['theta'] > r['items'][ids['s']]['theta']
    inside = S.surface_temperatures(doc, side='interior')
    assert inside['items'][ids['s']]['theta'] == pytest.approx(ti - u * 0.13 * (ti - te), abs=0.01)
    assert 'Πίν. 3β' in r['source'] and '0,04' in r['source']


def test_palette_legend_and_nothing_guessed_for_walls_without_u():
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st, wall_type='generic')
    v = S.thermal_view(doc)
    assert set(v['unknown']) == {ids['s'], ids['e'], ids['n'], ids['w']}       # no build-up: grey, said
    assert list(v['colors']) == [ids['win']]
    assert v['legend']['max'] - v['legend']['min'] >= S.MIN_SPAN - 1e-9
    assert S.palette(0) == (0, 0, 0) and S.palette(1) == (255, 255, 255)
    st.execute(UpdateEntity(ids['s'], {'wall_type': 'brick_double_insulated'}))
    assert ids['s'] in S.thermal_view(doc)['colors']


def test_the_3d_page_paints_the_facades_and_gives_the_materials_back():
    from archforge.scenarios import click3d
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    doc = Document(); st = CommandStack(doc); ids = _house(doc, st)
    payload = S.thermal_view(doc)
    import json
    result = click3d.run_in_page(doc, """
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    await wait(300);
    window.setThermalView(%s);
    const on = window.__thermalState();
    window.setThermalView(null);
    const off = window.__thermalState();
    return {on, off};
    """ % json.dumps(payload))
    on = dict(result['on']['colors'])
    assert result['on']['on'] and result['on']['legend']
    want = '%02x%02x%02x' % tuple(payload['colors'][ids['s']])
    assert on.get(ids['s']) == want                                          # the wall takes its colour
    assert not result['off']['on'] and not result['off']['legend'] and not result['off']['colors']


def test_view_menu_turns_it_on_in_3d():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); app.processEvents()
    try:
        _house(w.doc, w.stack)
        a = w._thermal_3d_action
        a.setChecked(True); app.processEvents()
        assert w.pbr_view.thermal_side == 'exterior'
        assert 'Θερμική όψη' in w.statusBar().currentMessage()
        a.setChecked(False); app.processEvents()
        assert w.pbr_view.thermal_side is None
    finally:
        w._mark_clean(); w.close(); app.processEvents()
