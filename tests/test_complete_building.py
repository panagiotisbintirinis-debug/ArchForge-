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
