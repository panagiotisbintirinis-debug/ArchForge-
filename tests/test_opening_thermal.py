"""Θερμικά στοιχεία κουφώματος (ιδιοκτήτης 05/11): «αλλάζει το κούφωμα, αλλάζει και η θερμική απεικόνιση» · «κάθε
κούφωμα… και θερμικά στοιχεία — θα πάρω στοιχεία από τις εταιρείες»."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.mep import facade_thermal as F
from archforge.mep import opening_thermal as O
from archforge.quantities import schedules as S

MAKER = {'uf': 1.3, 'ug': 1.1, 'psi_g': 0.08, 'frame_width': 0.10}


def _wall_with_window(**window):
    doc = Document(); st = CommandStack(doc)
    w = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 3.0, 'thickness': 0.27,
                        'wall_type': 'brick_double_insulated'})
    st.execute(AddEntity(w))
    o = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9, **window}, parent_id=w.id)
    st.execute(AddEntity(o))
    return doc, st, w, o


def test_uw_from_the_makers_parts_by_en_iso_10077_1():
    # 1,20 × 1,40, frame 10 cm: Ag = 1,0 × 1,2 = 1,20 · Af = 0,48 · lg = 4,4 m
    expect = (1.20 * 1.1 + 0.48 * 1.3 + 4.4 * 0.08) / 1.68
    assert O.uw_10077(1.2, 1.4, 0.10, 1.3, 1.1, 0.08) == pytest.approx(expect)
    doc, _st, _w, o = _wall_with_window(**MAKER)
    assert O.uw(doc, o) == (pytest.approx(expect), O.SOURCE_10077)
    doc, _st, _w, o = _wall_with_window(u_value=1.5, **MAKER)
    assert O.uw(doc, o) == (1.5, O.SOURCE_DECLARED)                  # the declared Uw wins
    with pytest.raises(ValueError):
        O.uw_10077(0.5, 1.0, 0.3, 1, 1, 0)                              # no glass left


def test_the_list_edits_the_window_with_one_undo_and_checks_the_numbers():
    doc, st, _w, o = _wall_with_window()
    for key, text in (('uf', '1,3'), ('ug', '1,1'), ('psi_g', '0,08'), ('frame_width', '10'), ('g_value', '0,6'),
                      ('maker', 'Σειρά Χ, φύλλο 2026')):
        st.execute(O.set_command(doc, o.id, key, text))
    o = doc.get(o.id)
    assert o.params['frame_width'] == pytest.approx(0.10) and o.params['maker'] == 'Σειρά Χ, φύλλο 2026'
    row = next(r for r in S.openings(doc)['rows'] if r['ids'] == [o.id])
    assert row['frame_width'] == 10.0 and row['uw_from'] == O.SOURCE_10077 and row['uw_used'] == pytest.approx(
        O.uw(doc, o)[0], abs=0.01)
    assert {'uf', 'ug', 'psi_g', 'frame_width', 'g_value', 'maker'} <= set(S.openings(doc)['editable'])
    st.undo()
    o = doc.get(o.id)
    assert o.params.get('maker') is None and o.params['g_value'] == 0.6
    for key, text in (('ug', '12'), ('frame_width', '80'), ('g_value', '1,5')):
        with pytest.raises(ValueError):
            O.set_command(doc, o.id, key, text)


def test_the_picture_shows_frame_spacer_and_glass_and_follows_the_window():
    doc, st, w, o = _wall_with_window()
    from archforge.mep.heat_load import assumptions
    if assumptions(doc)['heat_u_openings'] is None:
        from archforge.core.commands import UpdateEntity
        st.execute(UpdateEntity(o.id, {'u_value': 2.8}))
    before = F.facade(doc, w.id)
    from archforge.core.commands import UpdateEntity
    st.execute(UpdateEntity(o.id, {'u_value': None, **MAKER}))
    after = F.facade(doc, w.id)
    o = doc.get(o.id)
    th = after['theta']
    r0, c0 = int(round((3.0 - 0.9 - 1.4) / F.H)), int(round(2.0 / F.H))        # top-left cell of the window
    frame, edge, glass = th[r0 + 3, c0], th[r0 + 3, c0 + 2], th[r0 + 14, c0 + 12]
    assert edge > glass + 0.05                                               # the spacer's warm line outside
    assert not np.allclose(before['theta'], th)                              # the window changed → the picture
    assert after['u']['window'] == pytest.approx(O.uw(doc, o)[0])
    assert frame != pytest.approx(glass, abs=1e-3)


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def test_editing_the_window_in_the_list_redraws_the_thermal_tab(window):
    from archforge.ui import live_lists, thermal_facade_tab as T
    w, app = window
    ids = {}
    for name, (a, b) in {'s': ((0, 0), (6, 0)), 'e': ((6, 0), (6, 5)), 'n': ((6, 5), (0, 5)), 'w': ((0, 5), (0, 0))}.items():
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0, 'height': 2.7, 'thickness': 0.27,
                            'wall_type': 'brick_double_insulated'})
        w.stack.execute(AddEntity(e)); ids[name] = e.id
    o = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9, 'u_value': 2.8}, parent_id=ids['s'])
    w.stack.execute(AddEntity(o))
    tab = T.show(w, ids['s'])
    before = tab.result['today']['theta'].copy()
    rows_before = {x['kind']: x for x in tab.result['rows']}
    lists = live_lists.show(w, 'openings') and w._lists_tab
    row = next(r for r, d in enumerate(lists.data['rows']) if d['ids'] == [o.id])
    col = [k for k, _l in lists.data['columns']].index('uw')
    lists.table.item(row, col).setText('1,2'); app.processEvents()
    assert w.doc.get(o.id).params['u_value'] == 1.2
    T.show(w, ids['s'])
    rows_after = {x['kind']: x for x in tab.result['rows']}
    assert rows_after[2]['u'] == pytest.approx(1.2) and rows_after[2]['theta'] < rows_before[2]['theta']
    assert not np.allclose(before, tab.result['today']['theta'])


def test_frame_ranges_of_table_10_need_the_makers_uf_and_check_it():
    """ΤΟΤΕΕ 20701-2/2021 Πίν. 10: μεταλλικό με θερμοδιακοπή 1,0–4,0, PVC πολυθαλαμικό 1,0–2,0 → Uf του κατασκευαστή."""
    doc, st, _w, o = _wall_with_window()
    st.execute(O.set_command(doc, o.id, 'frame_material', 'pvc_multi'))
    st.execute(O.set_command(doc, o.id, 'glazing', '2|le05|4-16-4|argon'))
    o = doc.get(o.id)
    assert o.params['frame_material'] == 'pvc_multi' and o.params['glazing'] == '2|le05|4-16-4|argon'
    assert any('γράψτε το Uf του κατασκευαστή' in c for c in S.openings(doc)['check'])   # a range: never picked
    st.execute(O.set_command(doc, o.id, 'uf', '3,5'))
    data = S.openings(doc)
    row = next(r for r in data['rows'] if r['ids'] == [o.id])
    assert row['frame_material'].startswith('Συνθετικό πλαίσιο: PVC πολυθαλαμικό')
    assert any('Uf 3,5 έξω από το 1–2 του Πίν. 10' in c for c in data['check'])
    assert data['editable']['frame_material'][0] == 'choice'
    st.execute(O.set_command(doc, o.id, 'uf', '1,3'))
    assert not any('Πίν. 10' in c for c in S.openings(doc)['check'])
    with pytest.raises(ValueError):
        O.set_command(doc, o.id, 'frame_material', 'τιτάνιο')
    with pytest.raises(ValueError):
        st.execute(__import__('archforge.core.commands', fromlist=['UpdateEntity']).UpdateEntity(
            o.id, {'frame_material': 'titanium'}))


def test_the_list_offers_the_frame_material_as_a_drop_down_with_undo(window):
    from archforge.ui import live_lists
    w, app = window
    wall = Entity('wall', {'x1': 0, 'y1': 0, 'x2': 6, 'y2': 0, 'z': 0, 'height': 2.7, 'thickness': 0.27})
    w.stack.execute(AddEntity(wall))
    o = Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=wall.id)
    w.stack.execute(AddEntity(o))
    lists = live_lists.show(w, 'openings') and w._lists_tab
    col = [k for k, _l in lists.data['columns']].index('frame_material')
    box = lists.table.cellWidget(0, col)
    i = box.findData('metal_break')
    box.setCurrentIndex(i); box.activated.emit(i); app.processEvents()
    assert w.doc.get(o.id).params['frame_material'] == 'metal_break'
    w.stack.undo()
    assert w.doc.get(o.id).params.get('frame_material') is None


def test_the_schedule_has_typology_equipment_glazing_and_requirements_like_a_professional_table():
    """Πίνακας ανάλυσης κουφωμάτων (ιδιοκτήτης 05/11): τυπολογία, Π × Υ, υαλοπίνακες, ρολό / σίτα, ενεργειακοί δείκτες."""
    doc, st, _w, o = _wall_with_window(u_value=2.0)
    for key, value in (('typology', 'tilt_turn'), ('shading', 'Ρολό (κουτί πάνω)'), ('roller_drive', 'electric'),
                       ('screen', 'pleated'), ('safety_glass', 'laminated'),
                       ('glazing_build', '4 Clear + 16 Ar + 4 Low-E'), ('uw_required', '1,8')):
        st.execute(S.set_opening_command(doc, o.id, key, value))
    o = doc.get(o.id)
    assert o.params['opening_type'] == 'tilt_turn' and o.params['shading'] == 'roller'
    data = S.openings(doc)
    row = next(r for r in data['rows'] if r['ids'] == [o.id])
    assert row['typology'] == 'Ανοιγοανακλινόμενο' and row['shading'] == 'Ρολό (κουτί πάνω)'
    assert row['roller_drive'] == 'Ηλεκτρικό' and row['screen'] == 'Σίτα πλισέ'
    assert row['safety_glass'].startswith('Laminated') and row['glazing_build'] == '4 Clear + 16 Ar + 4 Low-E'
    assert any('Uw 2,00 > απαίτηση 1,80' in c for c in data['check'])
    keys = [k for k, _l in data['columns']]
    assert keys.index('typology') < keys.index('width') < keys.index('glazing') < keys.index('screen') < keys.index('uw')
    # a window type cannot be a door type, and one undo takes back one change
    with pytest.raises(ValueError):
        S.set_opening_command(doc, o.id, 'typology', 'security')
    st.undo()
    assert doc.get(o.id).params.get('uw_required') is None


def test_uw_above_the_zone_limit_of_table_5a_is_said():
    from archforge.mep.design_climate import zone
    from archforge.mep.totee_20701_2_2021 import u_max
    doc, _st, _w, o = _wall_with_window(u_value=2.7)
    z = zone(doc)
    notes = O.requirement_notes(doc, o)
    assert z == 'Β' and u_max('opening', z) == 2.60 and u_max('opening', z, renovation=True) == 3.00
    assert any('Umax 2,60' in n and 'Πίν. 5α (νέο κτίριο)' in n for n in notes)   # new building by default
