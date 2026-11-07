"""Θερμικό φορτίο ανά χώρο (07/11): Σ χώρων + «κτίριο» = σύνολο, όρο προς όρο· το κάθε σώμα παίρνει το φορτίο του χώρου του."""
import json
import os

import pytest

from archforge.core.model import Document, Entity
from archforge.mep.room_heat_load import emitter_loads, room_loads

DATA = os.path.join(os.path.dirname(__file__), 'data')


@pytest.mark.parametrize('name', ['bot16_three_storey_frame.archforge', 'owner_111_two_storey.archforge'])
def test_the_rooms_add_up_to_the_building(name):
    path = os.path.join(DATA, name)
    doc = Document.load(path) if 'bot16' in name else Document.from_dict(json.load(open(path, encoding='utf-8')))
    r = room_loads(doc)
    assert len(r['rooms']) >= 5
    n = len(r['rooms'])
    for k, v in r['building'].items():
        assert abs(v) <= 0.5 * n + 1, (k, v)               # each part of the total is rounded to 1 W
    assert sum(x['watts'] for x in r['rooms']) == pytest.approx(r['total']['watts'], abs=n + 6)


def _two_rooms():
    doc = Document()
    doc.add(Entity('design_climate', {'heat_theta_int': 20.0, 'heat_theta_ext_winter': 0.0, 'heat_theta_ext_summer': 28.0,
                                      'heat_air_changes': 0.5, 'heat_u_walls': 0.5, 'heat_u_roof': 0.4, 'heat_u_floor': 0.4}))
    for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 4)), ((8, 4), (0, 4)), ((0, 4), (0, 0)), ((4, 0), (4, 4))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 3.0, 'thickness': 0.25}))
    return doc


def test_a_symmetric_pair_of_rooms_get_the_same_load_and_their_radiators_too():
    doc = _two_rooms()
    r = room_loads(doc)
    a, b = sorted(r['rooms'], key=lambda x: x['polygon'][0][0])
    assert a['watts'] == pytest.approx(b['watts']) and a['area_m2'] == 16.0
    # walls 4 + 4 + 4 m exterior × 3 m × 0,5 × 20; roof and floor 16 m² × 0,4 × 20 each; air 0,34 × 0,5 × 48 × 20
    assert a['parts']['Εξωτερικοί τοίχοι'] == pytest.approx(12 * 3 * 0.5 * 20)
    assert a['parts']['Οροφή / δώμα'] == pytest.approx(16 * 0.4 * 20) == a['parts']['Δάπεδο']
    assert a['parts']['Αερισμός'] == pytest.approx(0.34 * 0.5 * 48 * 20)
    for x, y in ((2, 2), (6, 2), (6.5, 2.5)):
        doc.add(Entity('heating_point', {'x': float(x), 'y': float(y), 'z': 0.0, 'point_type': 'radiator'}))
    loads = sorted(emitter_loads(doc).values())
    assert loads[0] == pytest.approx(loads[1]) == pytest.approx(b['watts'] / 2)   # two in one room share it
    assert loads[2] == pytest.approx(a['watts'])


def _flats_with_stairs():
    """Two flats 4 × 4 either side of a 2 m common stairwell (Κλιμακοστάσιο), one storey, U given everywhere."""
    from archforge.core.commands import SetRoomMetadata
    doc = Document()
    doc.add(Entity('design_climate', {'heat_theta_int': 20.0, 'heat_theta_ext_winter': 0.0, 'heat_theta_ext_summer': 28.0,
                                      'heat_air_changes': 0.5, 'heat_u_walls': 0.5, 'heat_u_roof': 0.4,
                                      'heat_u_floor': 0.4, 'heat_b_unheated': 0.5}))
    for a, b in (((0, 0), (10, 0)), ((10, 0), (10, 4)), ((10, 4), (0, 4)), ((0, 4), (0, 0)), ((4, 0), (4, 4)), ((6, 0), (6, 4))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 3.0, 'thickness': 0.25}))
    faces = {round(sum(p[0] for p in f.polygon) / len(f.polygon)): f for f in doc.active_room_faces(z=0.0)}
    SetRoomMetadata(faces[5].signature, {'name': 'Κλιμακοστάσιο', 'use': 'Κλιμακοστάσιο'}).do(doc)
    SetRoomMetadata(faces[2].signature, {'apartment': 'Α1'}).do(doc)
    SetRoomMetadata(faces[8].signature, {'apartment': 'Α2'}).do(doc)
    return doc


def test_the_common_stairwell_loses_nothing_itself_and_the_flats_lose_towards_it():
    """Owner 07/11: «σε πολυκατοικία με κοινόχρηστες σκάλες οι απώλειες πρέπει να υπολογίζουν και αυτά»."""
    doc = _flats_with_stairs()
    r = room_loads(doc)
    by = {x['apartment']: x for x in r['rooms']}
    stairs = by['Κοινόχρηστα']
    assert not stairs['heated'] and stairs['watts'] == 0                      # outside the heated envelope
    a1 = by['Α1']
    # its own exterior: 4 + 4 + 4 m × 3 m × 0,5 × 20 = 360 W; towards the stairwell: 4 m × 3 m × 0,5 × 0,5 × 20 = 60 W
    assert a1['parts']['Εξωτερικοί τοίχοι'] == pytest.approx(360.0)
    assert a1['parts']['Προς μη θερμαινόμενους'] == pytest.approx(60.0)
    assert a1['watts'] == pytest.approx(by['Α2']['watts'])
    assert r['apartments'] == {'Α1': round(a1['watts']), 'Α2': round(by['Α2']['watts']), 'Κοινόχρηστα': 0}
    total = dict(r['total']['parts'])
    assert total['Προς μη θερμαινόμενους'] == 120
    assert r['total']['volume_m3'] == pytest.approx(2 * 16 * 3.0)           # the stairwell is not heated air
    assert all(abs(v) <= 2 for v in r['building'].values())


def test_b_changes_only_the_part_towards_the_unheated_rooms():
    doc = _flats_with_stairs()
    climate = next(e for e in doc.entities.values() if e.kind == 'design_climate')
    before = dict(room_loads(doc)['total']['parts'])
    climate.params['heat_b_unheated'] = 1.0
    after = dict(room_loads(doc)['total']['parts'])
    assert after['Προς μη θερμαινόμενους'] == 2 * before['Προς μη θερμαινόμενους']
    assert all(after[k] == before[k] for k in before if k != 'Προς μη θερμαινόμενους')


def test_the_apartment_of_a_room_from_its_properties_with_one_undo():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QComboBox
    QApplication.instance() or QApplication([])
    from archforge.core.commands import AddEntity
    from archforge.mep.heat_load import heat_load
    from archforge.ui.main_window import MainWindow
    from archforge.ui.room_panel import show_room
    w = MainWindow()
    try:
        for a, b in (((0, 0), (8, 0)), ((8, 0), (8, 4)), ((8, 4), (0, 4)), ((0, 4), (0, 0)), ((4, 0), (4, 4))):
            w.stack.execute(AddEntity(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                                      'height': 3.0, 'thickness': 0.25})))
        f = sorted(w.doc.active_room_faces(z=0.0), key=lambda f: min(p[0] for p in f.polygon))[0]
        assert set(heat_load(w.doc)['apartments']) == {'Διαμέρισμα Ισόγειο'}  # default: one per storey
        show_room(w, f.signature)
        box = w.findChild(QComboBox, 'roomApartment')
        assert box.currentText().startswith('(αυτόματα: Διαμέρισμα Ισόγειο')
        box.setEditText('Α1'); box.lineEdit().editingFinished.emit()
        assert w.doc.room_metadata(f.signature)['apartment'] == 'Α1'
        assert set(heat_load(w.doc)['apartments']) == {'Α1', 'Διαμέρισμα Ισόγειο'}
        w.stack.undo()
        assert 'apartment' not in w.doc.room_metadata(f.signature)
    finally:
        w._mark_clean(); w.close()
