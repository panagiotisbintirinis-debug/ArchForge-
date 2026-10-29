"""Owner 29/10: «στο κουμπί τοίχος να ανοίγει ένα μενού για καμπύλο, διάφανο, αλλά και το είδος του τοίχου».

«Τοίχος ▾»: click draws as before; ▾ chooses what the next walls are — a wall type (its layers and total thickness)
or glass — at creation, one undo per wall."""
import pytest


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w.hide()


def _draw(w, a, b):
    from archforge.core.viewport import PointerEvent
    c = w.plan_view.controller
    c.pointer_down(PointerEvent(*a)); c.pointer_move(PointerEvent(*b)); c.pointer_up(PointerEvent(*b))
    if c.active is not None:
        c.finish_wall_chain()
    return [e for e in w.doc.entities.values() if e.kind == 'wall']


def test_the_wall_button_draws_and_its_menu_lists_the_types(window):
    from archforge.architecture.wall_types import WALL_TYPES
    w = window
    button = w._mockup_wall_button
    assert button.text() == 'Τοίχος' and button.menu() is not None
    button.click()
    assert w.plan_view.controller.tool == 'wall'
    keys = set(w._mockup_wall_choices)
    assert {None, 'glass'} <= keys and set(WALL_TYPES) - {'generic'} <= keys
    assert not w._mockup_wall_curved.isEnabled()          # said plainly: not yet


def test_a_type_chosen_in_the_menu_is_the_new_walls_type_and_thickness(window):
    from archforge.architecture.wall_types import total_thickness
    w = window
    w._mockup_wall_choices['brick_double_insulated'].trigger()
    walls = _draw(w, (0.0, 0.0), (4.0, 0.0))
    assert walls, 'no wall drawn'
    wall = walls[-1]
    assert wall.params['wall_type'] == 'brick_double_insulated'
    assert wall.params['thickness'] == pytest.approx(total_thickness('brick_double_insulated'))


def test_a_glass_wall_is_drawn_with_the_clear_glass_material(window):
    from archforge.architecture.wall_types import GLASS_WALL
    w = window
    w._mockup_wall_choices['glass'].trigger()
    before = len(w.stack.done)
    wall = _draw(w, (0.0, 2.0), (3.0, 2.0))[-1]
    assert wall.params['material_id'] == 'glass_clear' and wall.params['wall_kind'] == 'glass'
    assert wall.params['thickness'] == pytest.approx(GLASS_WALL['thickness'])
    assert len(w.stack.done) == before + 1                 # the glass is part of the wall's one undo step
    w.stack.undo()
    assert wall.id not in w.doc.entities
