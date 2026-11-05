"""«Θερμομονώσεις» (mockup v2, ιδιοκτήτης 05/11): σήμερα και πρόταση στην ίδια κλίμακα, από τον υπολογισμό 3Δ αγωγής."""
import numpy as np
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import facade_thermal as F
from archforge.mep import thermal_compare as C


def _wall():
    doc = Document(); st = CommandStack(doc)
    w = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.27,
                        'wall_type': 'brick_double_insulated'})
    st.execute(AddEntity(w))
    st.execute(AddEntity(Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.4, 'depth': 0.4,
                                                      'height': 3.0, 'rotation': 0.0, 'role': 'structural',
                                                      'construction': 'reinforced_concrete', 'base_level': 'Ground'})))
    st.execute(AddEntity(Entity('window', {'offset': 0.8, 'width': 1.2, 'height': 1.2, 'sill': 0.9, 'u_value': 2.8},
                                parent_id=w.id)))
    return doc, w


def _etics(doc, base):
    return [F.layer(doc, 'cement_plaster', 0.01, 'finish'), F.layer(doc, 'eps', 0.08, 'insulation')] + base


def test_today_and_proposal_share_one_scale_and_the_proposal_loses_less():
    doc, w = _wall()
    today = F.facade(doc, w.id)
    r = C.compare(doc, w.id, layers=_etics(doc, today['layers']), opening_u=1.4)
    both = np.concatenate([r['today']['theta'].ravel(), r['proposal']['theta'].ravel()])
    assert r['lo'] == pytest.approx(both.min()) and r['hi'] == pytest.approx(both.max())
    w_now, w_p = r['watts']
    assert w_p < w_now / 2 and r['reduction'] == pytest.approx((w_p - w_now) / w_now) and r['reduction'] < -0.5
    rows = {x['kind']: x for x in r['rows']}
    assert set(rows) == {0, 1, 2}
    assert rows[1]['theta'] > rows[0]['theta']                          # the uninsulated frame is warmer outside
    assert rows[1]['theta_proposal'] < rows[1]['theta']                 # ETICS hides it
    assert rows[2]['u'] == pytest.approx(2.8) and rows[2]['u_proposal'] == pytest.approx(1.4)
    for x in r['rows']:
        assert 0.0 <= x['pos'] <= 1.0 and x['colour'].startswith('#') and len(x['colour']) == 7
    # nothing in the project changed: the wall computes as before
    assert np.allclose(F.facade(doc, w.id)['theta'], today['theta'])


def test_a_fixed_scale_like_the_photo_and_the_inside_side():
    doc, w = _wall()
    r = C.compare(doc, w.id, scale=(0.0, 10.0))
    assert (r['lo'], r['hi']) == (0.0, 10.0) and r['proposal'] is None and r['reduction'] is None
    inside = C.compare(doc, w.id, side='interior')
    rows = {x['kind']: x for x in inside['rows']}
    assert rows[1]['theta'] < rows[0]['theta']                          # from inside the frame is the cold spot
    with pytest.raises(ValueError):
        C.compare(doc, w.id, scale=(5.0, 5.0))
    with pytest.raises(ValueError):
        C.compare(doc, w.id, side='sideways')


def test_palettes_including_the_owners_five_points_and_the_approximations():
    th = np.linspace(0, 1, 5).reshape(1, 5)
    five = C.to_rgb(th, 0, 1, 'five_point')[0]
    assert [tuple(c) for c in five] == [(4, 4, 8), (0, 0, 255), (0xD3, 0x30, 0), (0xF0, 0x88, 0), (255, 255, 0x80)]
    assert tuple(C.to_rgb(th, 0, 1, 'gray')[0, -1]) == (255, 255, 255)
    for key in ('rainbow_hc', 'arctic'):
        assert 'προσέγγιση' in C.PALETTES[key][0] and C.PALETTES[key][2] == 'DESIGN_DEFAULT'
        assert C.to_rgb(th, 0, 1, key).shape == (1, 5, 3)


def test_zone_palette_in_celsius_with_fahrenheit_converted_on_import():
    zones = C.zones_in_celsius(C.parse_zones('; 32; #0000FF\n32; 50; #00FF00\n50; ; #FF0000'), unit='F')
    assert zones[0][1] == pytest.approx(0.0) and zones[1][1] == pytest.approx(10.0)
    rgb = C.to_rgb(np.array([[-5.0, 4.0, 12.0]]), 0, 1, C.ZONES, zones)[0]
    assert [tuple(c) for c in rgb] == [(0, 0, 255), (0, 255, 0), (255, 0, 0)]
    with pytest.raises(ValueError):
        C.parse_zones('1; 2')
    with pytest.raises(ValueError):
        C.zones_in_celsius([])


def test_the_junction_profile_falls_smoothly_from_the_frame_into_the_masonry():
    doc, w = _wall()
    prof = C.junction_profile(F.facade(doc, w.id))
    th = prof['theta']
    assert th[0] > th[-1] + 0.5 and all(b <= a + 1e-9 for a, b in zip(th, th[1:]))
    assert 0 < prof['edge'] < prof['s'][-1]


# ------------------------------------------------------------------ the tab in the program
import os  # noqa: E402

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def _box(doc, st):
    ids = {}
    for name, (a, b) in {'s': ((0, 0), (6, 0)), 'e': ((6, 0), (6, 5)), 'n': ((6, 5), (0, 5)), 'w': ((0, 5), (0, 0))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 2.7, 'thickness': 0.27,
                            'wall_type': 'brick_double_insulated'})
        st.execute(AddEntity(e)); ids[name] = e.id
    st.execute(AddEntity(Entity('structural_column', {'x': 3.0, 'y': 0.0, 'z': 0.0, 'width': 0.4, 'depth': 0.4,
                                                      'height': 2.7, 'rotation': 0.0, 'role': 'structural',
                                                      'construction': 'reinforced_concrete', 'base_level': 'Ground'})))
    return ids


def test_the_tab_shows_today_and_the_proposal_and_never_changes_the_project(window):
    from archforge.ui import thermal_facade_tab as T
    w, app = window
    ids = _box(w.doc, w.stack)
    tab = T.show(w, ids['s'])
    assert w._central_tabs.currentWidget() is tab and tab.wall_id() == ids['s']
    assert tab.facade_combo.count() == 4 and tab.today_img.pixmap() is not None
    assert tab.result['proposal'] is None and tab.w_prop.text() == '—'
    before = dict(w.doc.get(ids['s']).params)
    undo_depth = len(w.stack.done)
    from archforge.architecture.wall_assemblies import layer_specs
    specs = [{'material': 'eps', 'thickness': 0.08, 'role': 'insulation'}] + layer_specs(w.doc, 'brick_double_insulated')
    r = tab.set_proposal_layers(specs)
    assert r['proposal'] is not None and r['reduction'] < 0 and tab.w_red.text().endswith('%')
    assert tab.prop_layers.rowCount() == len(specs) and tab.coords.rowCount() == 2
    assert dict(w.doc.get(ids['s']).params) == before
    assert len(w.stack.done) == undo_depth
    # palette, side and a fixed scale like the photo
    tab.palette_combo.setCurrentIndex(tab.palette_combo.findData('five_point'))
    tab.side_combo.setCurrentIndex(1)
    tab.scale_combo.setCurrentIndex(1); tab._scale_chosen(1)
    assert tab.result['side'] == 'interior' and tab.min_spin.isEnabled()
    # the proposal belongs to the façade: another wall starts without one
    tab.facade_combo.setCurrentIndex(tab.facade_combo.findData(ids['n'])); tab.recompute()
    assert tab.result['proposal'] is None
    tab.clear_proposal()
    # the proposal dialog is the +/− tool of the wall dialog, and Save does not touch the project
    dlg = T.ProposalLayersDialog(w, 'brick_double_insulated', specs)
    assert len(dlg.layer_specs()) == len(specs) and not dlg.type_combo.isVisible()
    dlg.add_layer('eps', 'outside'); dlg.accept()
    assert len(dlg.result_specs) == len(specs)                 # the new 0 cm layer is dropped
    assert dict(w.doc.get(ids['s']).params) == before
