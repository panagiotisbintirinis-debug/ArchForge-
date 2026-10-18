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
    for pts in (((0, 0), (3, 0), (1, 2.5)), ((3.1, 0), (6, 0), (4, 2.5))):  # kitchen and bath inside it
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
    before, n = _snapshot(w.doc), len(w.stack.done)
    report = complete(w)
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
