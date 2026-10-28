"""Owner 18/10 (proposal step 1): «Ολοκλήρωση κτιρίου» — walls and named rooms in, a whole building out, one undo."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.core.commands import SetRoomMetadata
from archforge.geometry.regions import point_in_polygon
from archforge.ui import room_box_tool as T
from archforge.ui.complete_building import complete, plan
from archforge.ui.main_window import MainWindow


@pytest.fixture
def house(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w._no_modal_dialogs = True; app.processEvents()
    w.plan_view.room_size = (10, 8)
    T.click(w, 'room_place', 0, 0)                                          # the house
    for pts in (((0, 0), (3, 0), (1, 2.5)), ((3.15, 0), (6, 0), (4, 2.5))):  # kitchen, bath next to it
        for x, y in pts:
            T.click(w, 'room_box', x, y)
    for x, y, n in ((1, 1, 'Κουζίνα'), (4.5, 1, 'Μπάνιο'), (7, 6, 'Σαλόνι')):
        f = next(f for f in w.doc.active_room_faces() if point_in_polygon(x, y, f.polygon))
        w.stack.execute(SetRoomMetadata(f.signature, {'name': n, 'use': n}))
    from archforge.scenarios.common import Scenario
    s = Scenario('t', 't', w)
    s.opening('door', 1.5, 2.575, 0.9)
    s.opening('door', 4.5, 2.575, 0.8)
    w._place_site_point('heat_boiler', 9.5, 7.5)
    yield w
    w.hide()


def _snapshot(doc):
    return sorted((e.kind, e.id) for e in doc.entities.values())


def test_one_command_completes_the_building_and_one_undo_takes_it_back(house):
    w = house
    from archforge.core import layers as L
    from archforge.ui.layers_panel import set_workspace
    set_workspace(w, 'arch', announce=False)
    states = L.layer_states(w.doc)
    before, n = _snapshot(w.doc), len(w.stack.done)
    report = complete(w)
    assert L.workspace(w.doc) == 'arch' and L.layer_states(w.doc) == states   # the walls are not left locked
    assert all(ok for _l, ok, _note in report), report
    assert len(w.stack.done) == n + 1                                       # ONE undo step
    kinds = {}
    for e in w.doc.entities.values():
        kinds[e.kind] = kinds.get(e.kind, 0) + 1
    assert kinds.get('pitched_roof') and kinds.get('structural_column') and kinds.get('structural_beam')
    assert kinds.get('cabinet', 0) >= 3                                     # the kitchen
    assert any(e.kind == 'electrical_point' and e.params.get('point_type') == 'panel' for e in w.doc.entities.values())
    assert sum(1 for e in w.doc.entities.values() if e.kind == 'heating_point' and e.params.get('point_type') == 'radiator') >= 3
    w.stack.undo()
    assert _snapshot(w.doc) == before
    w.stack.redo()
    assert any(e.kind == 'pitched_roof' for e in w.doc.entities.values())


def test_a_second_run_adds_nothing_twice_and_parts_can_be_left_out(house):
    w = house
    complete(w, keys=['room_points', 'panel'])
    assert not any(e.kind == 'pitched_roof' for e in w.doc.entities.values())   # unticked: not done
    points = sum(1 for e in w.doc.entities.values() if e.kind == 'electrical_point')
    why = {k: why for k, _l, _t, why, _r in plan(w)}
    assert why['panel'] == 'υπάρχει ήδη'
    complete(w, keys=['room_points'])
    assert sum(1 for e in w.doc.entities.values() if e.kind == 'electrical_point') == points


def test_nothing_to_do_without_walls(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        assert all(why for _k, _l, _t, why, _r in plan(w))
        assert complete(w) == [] and not w.stack.done
    finally:
        w.hide()


def test_change_by_numbers_then_update(house):
    """Owner 18/10: «να μικρύνω ένα δωμάτιο ή να αλλάξω γωνία σε ένα τοίχο — πόσο εύκολο;» + «Ενημέρωση»."""
    from archforge.architecture.room_resize import corner_angle, room_size
    from archforge.ui import room_box_tool as T
    w = house
    complete(w)
    kitchen = next(f for f in w.doc.active_room_faces() if point_in_polygon(1, 1, f.polygon))
    (w0, d0), _sides = room_size(w.doc, kitchen)
    assert (w0, d0) == pytest.approx((3.0, 2.5), abs=.01)
    n = len(w.stack.done)
    assert T.resize_at(w, 1, 1, size=(2.6, 2.2)) == (2.6, 2.2)              # smaller kitchen, typed
    assert len(w.stack.done) == n + 1
    kitchen = next(f for f in w.doc.active_room_faces() if point_in_polygon(1, 1, f.polygon))
    assert room_size(w.doc, kitchen)[0] == pytest.approx((2.6, 2.2), abs=.01)
    assert len(w.doc.active_room_faces()) == 3                              # every room still closed
    # The house's east wall to 80° with the wall it starts from: the room stays closed.
    wid = next(e.id for e in w.doc.entities.values() if e.kind == 'wall'
               and abs(float(e.params['x1']) - float(e.params['x2'])) < 1e-6 and float(e.params['x1']) > 9.9)
    before, _ref = corner_angle(w.doc, wid)
    assert before == pytest.approx(90.0, abs=.1)
    assert T.set_wall_angle(w, wid, 80.0) == wid
    assert corner_angle(w.doc, wid)[0] == pytest.approx(80.0, abs=.1)
    assert len(w.doc.active_room_faces()) == 3
    # «Ενημέρωση»: roof and frame made again for the new walls, one undo step.
    old = {e.id for e in w.doc.entities.values() if e.kind in ('pitched_roof', 'structural_column')}
    n = len(w.stack.done)
    report = complete(w, keys=['rebuild'])
    assert all(ok for _l, ok, _n in report), report
    assert len(w.stack.done) == n + 1
    new = {e.id for e in w.doc.entities.values() if e.kind in ('pitched_roof', 'structural_column')}
    assert new and not (new & old)
    assert any(e.kind == 'pitched_roof' for e in w.doc.entities.values())


# -- Audit 27/10 + addendum 01: complete what is missing, keep what the human placed, say what really happened ----------
def _face_at(w, x, y):
    return next(f for f in w.doc.active_room_faces() if point_in_polygon(x, y, f.polygon))


def _points_in(w, face, types):
    return [e for e in w.doc.entities.values() if e.kind == 'electrical_point'
            and e.params.get('point_type') in types and point_in_polygon(float(e.params['x']), float(e.params['y']), face.polygon)]


def test_f02_one_socket_does_not_stop_the_light_and_switch_of_its_room(house):
    w = house
    w._place_site_point('elec_socket', 8.0, 7.6)                           # the human's own socket in the Σαλόνι
    living = _face_at(w, 7, 6)
    complete(w, keys=['room_points'])
    assert _points_in(w, living, ('light',)), 'the room still gets its ceiling light'
    sockets = _points_in(w, living, ('socket',))
    assert len(sockets) == 1 and abs(float(sockets[0].params['x']) - 8.0) < 1e-6     # his socket kept, none added


def test_f03_one_cabinet_does_not_cancel_the_kitchen(house):
    w = house
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.kitchen.cabinets import default_params
    p = default_params('base', width=0.6); p.update(x=2.6, y=0.35, z=0.0, rotation=0.0)
    w.stack.execute(AddEntity(Entity('cabinet', p, name='Ντουλάπι του χρήστη')))
    kitchen = _face_at(w, 1, 1)
    complete(w, keys=['kitchen_bath'])
    inside = [e for e in w.doc.entities.values() if e.kind == 'cabinet'
              and point_in_polygon(float(e.params['x']), float(e.params['y']), kitchen.polygon)]
    assert any(e.params.get('layout_role') == 'sink' for e in inside), 'the kitchen is planned around his cabinet'
    assert any(e.name == 'Ντουλάπι του χρήστη' for e in inside)
    # A finished kitchen is not planned twice.
    n = len(inside)
    complete(w, keys=['kitchen_bath'])
    assert len([e for e in w.doc.entities.values() if e.kind == 'cabinet'
                and point_in_polygon(float(e.params['x']), float(e.params['y']), kitchen.polygon)]) == n


def test_f09_a_roof_elsewhere_does_not_block_the_top_storey_roof(house):
    w = house
    from archforge.ui.complete_building import has_roof
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    # A small canopy at ground level (eave 2.4 m) does not cover a top storey whose walls reach 3 m.
    from archforge.structure.timber_roof import default_params
    canopy = default_params(w.doc)
    canopy.update(x0=10.5, y0=0.0, x1=12.0, y1=2.0, eave_z=2.4, overhang=0.1)
    w.stack.execute(AddEntity(Entity('pitched_roof', canopy)))
    top = max(float(e.params.get('z', 0.0)) for e in w.doc.entities.values() if e.kind == 'wall')
    wall_h = max(float(e.params.get('height', 0.0)) for e in w.doc.entities.values() if e.kind == 'wall')
    if 2.4 >= top + wall_h - 0.3:
        pytest.skip('fixture walls lower than the canopy')
    assert not has_roof(w)
    complete(w, keys=['roof'])
    assert has_roof(w)


def test_f10_a_part_that_added_nothing_is_not_reported_as_done(house):
    w = house
    from archforge.ui.complete_building import SKIPPED
    complete(w, keys=['room_points'])
    report = complete(w, keys=['room_points'])                            # everything already there
    (_label, ok, note), = report
    assert ok and note.startswith(SKIPPED)


def test_f08_no_disabled_coming_soon_entry_in_the_menus(house):
    """RELEASE_PLAN rule 2.7: an entry works or is hidden — never «— έρχονται» greyed out."""
    w = house

    def walk(menu):
        for a in menu.actions():
            if a.menu() is not None:
                yield from walk(a.menu())
            elif not a.isSeparator():
                yield a
    entries = [a for top in w.menuBar().actions() if top.menu() is not None for a in walk(top.menu())]
    assert not [a.text() for a in entries if 'έρχονται' in a.text() or 'έρχεται' in a.text()]


def test_f06_without_a_source_heating_gets_a_connection_point_with_the_suggested_power(house):
    """Owner 28/10: no boiler / heat pump → the step is not refused; a standard connection point with the
    indicative kW goes in (the kind of source: the mechanical engineer), with the emitters, one undo."""
    w = house
    src = next(e for e in w.doc.entities.values() if e.kind == 'heating_point'
               and e.params.get('point_type') in ('boiler', 'heat_pump', 'heat_source'))
    from archforge.core.commands import DeleteEntities
    w.stack.execute(DeleteEntities([src.id]))
    step = next(s for s in plan(w) if s[0] == 'heating')
    assert step[3] is None                                     # not refused any more
    since = len(w.stack.done)
    report = dict((label, note) for label, ok, note in complete(w, ['heating']))
    point = next(e for e in w.doc.entities.values() if e.kind == 'heating_point'
                 and e.params.get('point_type') == 'heat_source')
    assert 'μηχανολόγος' in point.name and point.params['power_w'] > 0
    assert not any(point_in_polygon(point.params['x'], point.params['y'], f.polygon) for f in w.doc.active_room_faces())
    note = next(iter(report.values()))
    assert 'σημείο σύνδεσης' in note and 'Ενδεικτική ισχύς θέρμανσης' in note and 'όχι μελέτη' in note
    assert len(w.stack.done) == since + 1                      # one undo
    w.stack.undo()
    assert point.id not in w.doc.entities
