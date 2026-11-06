"""Owner 06/11: «στη σκάλα δεν εμφανιζόταν το ghost … σε σχήμα Π να μπορείς να θέτεις τα επιμέρους μήκη».

The plan ghost follows the cursor with the stair tool (as in 3D), a click places exactly what it shows, R turns
it, Tab changes its type, + / − move steps between the two flights of a Γ / Π — and the split is a stair param
(``first_flight``) that the treads, the railings, the opening and the «Σκάλα» window all follow."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.railings import stair_railing_lines
from archforge.architecture.stairs import candidate_from_params, first_treads, stair_footprint, stair_treads
from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity, WorkPlane, validate_params
from archforge.core.viewport import PointerController, PointerEvent


def _ctrl():
    doc = Document()
    doc.levels = {'Ground': 0.0, 'Floor 2': 2.7}
    doc.work_plane = WorkPlane(name='Ground', origin=(0.0, 0.0, 0.0))
    stack = CommandStack(doc); ctrl = PointerController(doc, stack); ctrl.set_tool('stair')
    return doc, stack, ctrl


def _u_params(first=0):
    from archforge.architecture.stairs import solve_stair_candidates
    c = next(c for c in solve_stair_candidates(0.0, 2.7, (0.0, 0.0), (2.5, 0.0)) if c.layout == 'u')
    p = c.to_params()
    if first:
        p['first_flight'] = first
    return p


def test_first_treads_kept_inside_the_stair():
    assert first_treads(15) == 7 and first_treads(15, 10) == 10
    assert first_treads(15, 99) == 14 and first_treads(15, 0) == 7 and first_treads(1, 5) == 1


def test_split_moves_the_treads_landing_and_railings():
    half, ten = _u_params(), _u_params(10)
    n = candidate_from_params(half).tread_count
    assert candidate_from_params(ten).first_treads == 10 and n - 10 >= 1
    validate_params('stair', ten)                                       # a stored param, checked
    t_half, land_half = stair_treads(candidate_from_params(half))
    t_ten, land_ten = stair_treads(candidate_from_params(ten))
    assert len(t_half) == len(t_ten) == n
    assert land_half[0][0] == n // 2 - 1 and land_ten[0][0] == 9             # the landing after the 10th step
    assert stair_footprint(candidate_from_params(ten)) != stair_footprint(candidate_from_params(half))
    side = 'left'
    lens = [len(stair_railing_lines(ten, s)) for s in ('left', 'right')]
    assert lens == [2, 2]
    first_line = stair_railing_lines(ten, side)[0]
    assert first_line[-1][2] == pytest.approx(10 * float(ten['riser_height']))     # 1st flight ends at step 10


def test_ghost_follows_the_cursor_and_a_click_places_it():
    doc, stack, ctrl = _ctrl()
    pv = ctrl.stair_hover(1.02, 1.03)
    assert pv.kind == 'stair' and ctrl.active is None and ctrl.stair_ghost is not None
    assert pv.geometry['chosen']['x'] == pytest.approx(1.0) and pv.geometry['chosen']['y'] == pytest.approx(1.05)
    assert not [e for e in doc.entities.values() if e.kind == 'stair']            # a ghost only
    shown = dict(pv.geometry['chosen'])
    ctrl.pointer_move(PointerEvent(1.0, 1.05)); ctrl.pointer_down(PointerEvent(1.0, 1.05))
    ev = PointerEvent(1.0, 1.05); ev.click = True
    ctrl.pointer_up(ev)
    stairs = [e for e in doc.entities.values() if e.kind == 'stair']
    assert len(stairs) == 1
    for k in ('layout', 'x', 'y', 'angle_deg', 'riser_count'):
        assert stairs[0].params[k] == pytest.approx(shown[k]) if isinstance(shown[k], float) else stairs[0].params[k] == shown[k]
    stack.undo()
    assert not [e for e in doc.entities.values() if e.kind == 'stair']


def test_r_turns_tab_changes_type_plus_minus_move_steps_between_flights():
    doc, stack, ctrl = _ctrl()
    ctrl.stair_hover(1.0, 1.0)
    a0 = ctrl.preview.geometry['chosen']['angle_deg']
    assert ctrl.stair_rotate()
    assert ctrl.preview.geometry['chosen']['angle_deg'] == pytest.approx((a0 + 90) % 360 if a0 + 90 < 360 else a0 - 270)
    for _ in range(4):                                                  # Tab until a Π
        if ctrl.preview.geometry['chosen']['layout'] == 'u':
            break
        ctrl.cycle_option(1)
    assert ctrl.preview.geometry['chosen']['layout'] == 'u'
    a, b = ctrl.preview.geometry['flights']
    assert ctrl.stair_shift(+1) and ctrl.preview.geometry['flights'] == [a + 1, b - 1]
    ctrl.stair_hover(1.5, 1.0)                                          # moving keeps the type and the split
    assert ctrl.preview.geometry['chosen']['layout'] == 'u' and ctrl.preview.geometry['flights'] == [a + 1, b - 1]
    assert ctrl.preview.geometry['chosen']['first_flight'] == a + 1
    ctrl.pointer_down(PointerEvent(1.5, 1.0)); ev = PointerEvent(1.5, 1.0); ev.click = True; ctrl.pointer_up(ev)
    st = next(e for e in doc.entities.values() if e.kind == 'stair')
    assert st.params['layout'] == 'u' and st.params['first_flight'] == a + 1
    while ctrl.stair_shift(+1):                                        # never past n − 1
        pass


def test_stair_window_sets_the_flights_with_one_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.stair_dialog import StairDialog
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w.doc.levels['Floor 2'] = 2.7
        st = Entity('stair', dict(_u_params(), railing='auto'))
        from archforge.core.commands import AddEntity
        w.stack.execute(AddEntity(st))
        d = StairDialog(w, st.id)
        n = candidate_from_params(st.params).tread_count
        assert d.first_flight.isEnabled() and d.first_flight.value() == n // 2
        d.first_flight.setValue(n - 3); app.processEvents()
        assert 'σκάλ' in d.flights_label.text() or 'm' in d.flights_label.text()
        d.apply()
        assert w.doc.get(st.id).params['first_flight'] == n - 3
        w._undo()
        assert w.doc.get(st.id).params.get('first_flight', 0) in (0, n // 2)
    finally:
        w._mark_clean(); w.close()
