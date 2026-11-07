"""Έλεγχοι ορθότητας των bot (scripts/user_drive/oracles.py, 07/11): σιωπούν σε σωστό έργο, μιλούν σε χαλασμένο."""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.model import Document, Entity  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'user_drive'))
import oracles  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), 'data')


def _box(doc, t=None, wt='brick_double_insulated'):
    if t is None:                                  # 07/11 rule: the thickness its layers give
        from archforge.architecture.wall_types import total_thickness
        t = total_thickness(wt)
    pts = [(0, 0), (6, 0), (6, 4), (0, 4)]
    ids = []
    for a, b in zip(pts, pts[1:] + pts[:1]):
        w = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0, 'height': 2.8,
                            'thickness': t, 'wall_type': wt})
        doc.add(w); ids.append(w.id)
    return ids


def test_a_real_bot_building_passes_every_check():
    doc = Document.load(os.path.join(DATA, 'bot16_three_storey_frame.archforge'))
    assert oracles.audit(doc) == []


def test_heat_load_is_proportional_to_delta_t():
    doc = Document(); _box(doc)
    found, base = oracles.heat_linear(doc)
    assert base['watts'] > 0 and found == []


def test_window_outside_its_wall_is_found():
    doc = Document(); ids = _box(doc)
    a = Entity('window', {'offset': 3.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=ids[0])
    b = Entity('window', {'offset': 1.5, 'width': 1.0, 'height': 1.4, 'sill': 0.9}, parent_id=ids[0])
    doc.add(a); doc.add(b)
    assert oracles.openings_in_host(doc) == []
    a.params['offset'] = 5.8                 # past the wall's end (the program refuses it: the oracle must see it)
    b.params['height'] = 2.2                 # above the wall
    titles = [t for t, *_ in oracles.openings_in_host(doc)]
    assert titles == ['κούφωμα έξω από τον τοίχο του'] * 2


def test_u_from_other_thickness_than_the_wall_is_found():
    from archforge.architecture.wall_types import layers
    doc = Document(); _box(doc, t=0.50)
    d = sum(x[1] for x in layers('brick_double_insulated', doc))
    assert abs(d - 0.50) > 0.015
    assert [t for t, *_ in oracles.wall_u(doc)] == ['U με άλλο πάχος από τον τοίχο']


def test_ifc_round_trip_signature_sees_a_moved_window(tmp_path):
    from archforge.core.commands import CommandStack
    from archforge.exchange.ifc import export_ifc
    from archforge.exchange.ifc_import import import_ifc
    doc = Document(); ids = _box(doc)
    doc.add(Entity('window', {'offset': 3.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=ids[0]))
    export_ifc(doc, str(tmp_path / 'a.ifc'))
    back = Document(); import_ifc(back, CommandStack(back), str(tmp_path / 'a.ifc'))
    assert oracles.ifc_compare(oracles.ifc_signature(doc), oracles.ifc_signature(back)) == []
    w = next(e for e in back.entities.values() if e.kind == 'window')
    w.params['offset'] = float(w.params['offset']) + 0.3
    assert oracles.ifc_compare(oracles.ifc_signature(doc), oracles.ifc_signature(back))


def test_wall_volume_and_the_ifc_file_match_the_3d(tmp_path):
    from archforge.exchange.ifc import export_ifc
    doc = Document.load(os.path.join(DATA, 'bot16_three_storey_frame.archforge'))
    assert oracles.wall_volume(doc) == []
    path = str(tmp_path / 'a.ifc')
    export_ifc(doc, path)
    assert oracles.ifc_file_check(doc, path) == []


def test_wall_volume_sees_a_wall_whose_3d_is_not_its_size():
    doc = Document(); ids = _box(doc)
    assert oracles.wall_volume(doc) == []
    import archforge.exchange.ifc as ifc
    real = ifc._bodies

    def thinner(d):
        out = real(d)
        m = out[ids[0]]
        from archforge.geometry.mesh import MeshPayload
        out[ids[0]] = MeshPayload(tuple((x, y, z * 0.5) for x, y, z in m.vertices), m.triangles, m.triangle_surfaces)
        return out
    ifc._bodies = thinner
    try:
        assert [t for t, *_ in oracles.wall_volume(doc)] == ['όγκος τοίχου']
    finally:
        ifc._bodies = real
