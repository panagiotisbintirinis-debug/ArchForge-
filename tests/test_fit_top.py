"""Owner (2026-10-14): «βάζω ένα ντουλάπι ψηλό κάτω από σκάλα ή στέγη — το ντουλάπι πρέπει να ακολουθεί την
οροφή» · «η κατασκευή είναι ένα για όλα τα αντικείμενα … κανόνες χωρίς να έχουν κανόνες».

One shape mechanism for any object (``top_heights``), one rule that fills it (up to the ceiling).
"""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.stairs import solve_stair_candidates
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.geometry.fit_top import apply_top_heights, ceiling_at, fit_to_ceiling, top_at
from archforge.kitchen.cabinets import cabinet_mesh, default_params


def _stair(stack, structure='slab'):
    p = next(c for c in solve_stair_candidates(0.0, 2.72, (1.0, 1.0), (6.0, 1.0)) if c.layout == 'straight').to_params()
    e = Entity('stair', dict(p, structure=structure)); stack.execute(AddEntity(e))
    return e


def test_a_tall_cupboard_under_a_stair_gets_a_sloped_top_under_its_underside():
    doc = Document(); stack = CommandStack(doc)
    st = _stair(stack)
    cab = Entity('cabinet', default_params('tall', 4.0, 1.0, 0.0, 0.0, 0.8)); stack.execute(AddEntity(cab))
    changes = fit_to_ceiling(doc, cab)
    h = changes['top_heights']
    assert h[1] > h[0] + 0.3 and h[2] > h[3] + 0.3       # higher up the flight (+x)
    stack.execute(UpdateEntity(cab.id, changes))
    q = doc.get(cab.id).params
    for x, y, z in apply_top_heights(q, cabinet_mesh(q)[0]):
        under = ceiling_at(doc, x, y, 0.0)
        assert z <= under + 1e-6                          # nothing pokes through the stair
    stack.undo()
    assert not doc.get(cab.id).params.get('top_heights')


def test_under_a_tiled_roof_and_under_a_plain_slab():
    from archforge.structure.timber_roof import default_params as roof_params
    doc = Document(); stack = CommandStack(doc)
    for (x1, y1), (x2, y2) in (((0, 0), (8, 0)), ((8, 0), (8, 6)), ((8, 6), (0, 6)), ((0, 6), (0, 0))):
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    flat = Entity('cabinet', default_params('tall', 4.0, 3.0, 0.0, 0.0, 0.6)); stack.execute(AddEntity(flat))
    with pytest.raises(ValueError):
        fit_to_ceiling(doc, flat)                         # nothing over it yet
    stack.execute(AddEntity(Entity('pitched_roof', roof_params(doc))))
    eaves = Entity('cabinet', default_params('tall', 0.6, 3.0, 0.0, 90.0, 0.8)); stack.execute(AddEntity(eaves))
    ch = fit_to_ceiling(doc, eaves)
    assert ch['height'] >= 2.0 and (not ch['top_heights'] or max(ch['top_heights']) - min(ch['top_heights']) >= 0)


def test_any_object_can_take_a_top_shape_without_a_type_of_its_own():
    p = dict(x=0.0, y=0.0, z=0.0, width=1.0, depth=0.5, height=2.0, rotation=30.0, top_heights=[1.0, 2.0, 2.0, 1.0])
    assert top_at(p, -0.5, 0.0) == pytest.approx(1.0) and top_at(p, 0.5, 0.0) == pytest.approx(2.0)
    v = apply_top_heights(p, [(0.0, 0.0, 2.0), (0.0, 0.0, 0.0)])
    assert v[0][2] == pytest.approx(1.5) and v[1][2] == 0.0


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def test_from_the_mouse_menu_and_back_to_a_flat_top(window):
    from archforge.ui.marking_menu import build_menu, run
    _stair(window.stack, 'timber')
    cab = Entity('cabinet', default_params('tall', 4.0, 1.0, 0.0, 0.0, 0.8)); window.stack.execute(AddEntity(cab))
    assert 'mm:fit:ceiling' in [e['id'] for e in build_menu(window, 'plan', cab.id)['entries']]
    run(window, 'plan', cab.id, 'mm:fit:ceiling')
    assert window.doc.get(cab.id).params['top_heights']
    assert 'mm:fit:flat' in [e['id'] for e in build_menu(window, 'plan', cab.id)['entries']]
    run(window, 'plan', cab.id, 'mm:fit:flat')
    assert not window.doc.get(cab.id).params['top_heights']


def test_a_cupboard_under_the_landing_stops_under_the_landing():
    """Walk-through 14/10 (owner: «αυτή είναι λάθος»): it went up through the landing to the ceiling."""
    doc = Document(); stack = CommandStack(doc)
    p = next(c for c in solve_stair_candidates(0.0, 2.72, (1.0, 1.0), (4.0, 1.0)) if c.layout == 'l').to_params()
    st = Entity('stair', dict(p, structure='timber')); stack.execute(AddEntity(st))
    from archforge.architecture.stairs import candidate_from_params
    c = candidate_from_params(st.params)
    first = max(1, c.tread_count // 2)
    lx = p['x'] + first * c.tread_depth + c.landing_depth / 2          # under the landing (angle 0)
    cab = Entity('cabinet', default_params('tall', lx, p['y'], 0.0, 0.0, 0.4)); stack.execute(AddEntity(cab))
    cab.params['depth'] = 0.4
    ch = fit_to_ceiling(doc, cab)
    assert max(ch['top_heights'] or [ch['height']]) <= first * c.riser_height - 0.10 + 1e-6
