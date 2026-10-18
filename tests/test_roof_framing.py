"""Roof tool (owner 18/10): layers view, framing view with market sections, cutting list with codes and cuts."""
import pytest

from archforge.structure.roof_framing import MARKET, cutting_list, framing, layers, ridge_design


def _roof(form='hip', w=12.0, d=8.0, pitch=25.0):
    return {'x0': 0.0, 'y0': 0.0, 'x1': w, 'y1': d, 'eave_z': 2.7, 'pitch': pitch, 'roof_form': form, 'rafter_spacing': 0.6,
            'overhang': 0.5, 'tile': 'roman', 'insulation': 'xps', 'insulation_thickness': 0.08, 'snow_zone': 2, 'altitude': 0.0}


def test_every_piece_has_a_market_section_a_code_and_its_cuts():
    f = framing(_roof('hip'))
    roles = {q['role'] for q in f['pieces']}
    assert {'ridge', 'rafter', 'jack', 'hip', 'plate'} <= roles
    for q in f['pieces']:
        assert q['section'] in MARKET[{'jack': 'rafter'}.get(q['role'], q['role'])]
        assert q['order_m'] >= q['net_m'] + 0.15 and q['cuts']
    codes = [q['code'] for q in f['pieces']]
    assert len(codes) == len(set(codes)) and 'Κ-1' in codes and 'Ψ-01' in codes and 'Γ-1' in codes
    jack = next(q for q in f['pieces'] if q['role'] == 'jack')
    assert 'διπλή λοξή' in jack['cuts'][0]
    rafter = next(q for q in f['pieces'] if q['role'] == 'rafter')
    assert '25°' in rafter['cuts'][0] and 'σαμάρι' in rafter['cuts'][1]
    hip = next(q for q in f['pieces'] if q['role'] == 'hip')
    assert hip['section'][1] >= rafter['section'][1] + 0.04 - 1e-9


def test_rafter_section_grows_with_the_span_within_the_market_list():
    small = framing(_roof('gable', 12.0, 5.6))['rafter']['section']
    large = framing(_roof('gable', 12.0, 9.6))['rafter']['section']
    assert (small['b'], small['h']) in MARKET['rafter'] and (large['b'], large['h']) in MARKET['rafter']
    assert large['h'] > small['h']


def test_a_long_ridge_gets_posts_where_no_market_section_spans_it():
    short = ridge_design(_roof('gable'), 3.0)
    long = ridge_design(_roof('gable'), 14.0)
    assert short['posts'] == 0 and long['posts'] >= 1 and long['ok']
    gable = framing(_roof('gable', 16.0, 8.0))
    posts = [q for q in gable['pieces'] if q['role'] == 'post']
    assert len(posts) == gable['ridge']['posts'] and all(q['section'] in MARKET['post'] for q in posts)


def test_cutting_list_groups_identical_pieces_and_gives_the_volume_to_order():
    c = cutting_list(_roof('hip'))
    assert sum(r['count'] for r in c['rows']) == len(framing(_roof('hip'))['pieces'])
    assert all(round(r['order_m'] * 100) % 5 == 0 for r in c['rows'])      # order lengths to 5 cm
    assert c['volume_total_m3'] > 0 and c['battens_m'] > 0 and c['counter_battens_m'] > 0
    assert c['slope_area_m2'] == pytest.approx((13.0 * 9.0) / __import__('math').cos(__import__('math').radians(25)), rel=0.02)


def test_layers_view_gives_the_build_up_g_and_u():
    v = layers(_roof())
    roles = [r[4] for r in v['rows']]
    assert roles == ['boarding', 'vapour_barrier', 'insulation', 'membrane', 'counter_batten', 'batten', 'tiles']
    assert v['g_kn_m2'] > 0.6 and 0 < v['u_w_m2k'] < 1.0


def test_roof_menu_shows_only_timber_and_the_cutting_list_reaches_the_quote():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.quantities.materials import all_lists
    from archforge.ui import roof_tool
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._no_modal_dialogs = True
        for x1, y1, x2, y2 in ((0, 0, 12, 0), (12, 0, 12, 8), (12, 8, 0, 8), (0, 8, 0, 0)):
            window.stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.25})))
        window._create_pitched_roof('hip')
        ((lv, cl),) = roof_tool.show(window)
        assert lv['rows'] and cl['rows'] and cl['volume_total_m3'] > 0
        window._roof_layers_action.setChecked(False); window._roof_tiles_layer_action.setChecked(False)
        assert {'roof_layers', 'roof_tiles'} <= set(window.pbr_view.hidden_layers) and 'roof_structure' not in window.pbr_view.hidden_layers
        sheets = {name: rows for name, _t, rows, _n in all_lists(window.doc)}
        assert any('Ψαλίδι' in r[0] for r in sheets['Ξυλεία στέγης'])
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_a_section_changed_by_hand_is_rechecked_and_flagged_when_it_fails():
    """Owner 18/10: «εργαλείο αλλαγής της διατομής αν κριθεί αναγκαίο και επανέλεγχος με τα νέα δεδομένα»."""
    from archforge.structure.roof_framing import checks
    p = _roof('gable', 12.0, 8.0)
    assert all(ok for _t, ok in checks(p))                                  # automatic: everything passes
    small = dict(p, rafter_section=[0.065, 0.13])                           # too small for a 4 m span
    texts = {t.split(' ')[0]: ok for t, ok in checks(small)}
    assert texts['Ψαλίδια'] is False and framing(small)['rafter']['section']['b'] == 0.065
    bigger = dict(p, rafter_section=[0.10, 0.20])
    assert dict((t.split(' ')[0], ok) for t, ok in checks(bigger))['Ψαλίδια'] is True
    no_posts = dict(p, ridge_section=[0.14, 0.24], ridge_posts=0)           # 13 m ridge on its ends only
    assert dict((t.split(' ')[0], ok) for t, ok in checks(no_posts))['Κορφιάς'] is False
    back = dict(no_posts, ridge_section=[], ridge_posts=-1)                 # «Αυτόματα» again
    assert dict((t.split(' ')[0], ok) for t, ok in checks(back))['Κορφιάς'] is True


def test_properties_panel_changes_the_section_with_one_undo():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        window._no_modal_dialogs = True
        for x1, y1, x2, y2 in ((0, 0, 12, 0), (12, 0, 12, 8), (12, 8, 0, 8), (0, 8, 0, 0)):
            window.stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.25})))
        roof = window._create_pitched_roof('gable')
        failing = window._set_roof_section(roof.id, 'rafter_section', [0.065, 0.13])
        assert failing and 'Ψαλίδια' in failing[0]
        window.doc.select([roof.id]); window.refresh_inspector()
        window.stack.undo()
        assert not window.doc.get(roof.id).params.get('rafter_section')
    finally:
        window._mark_clean(); window.close(); app.processEvents()
