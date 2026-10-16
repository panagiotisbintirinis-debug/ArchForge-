"""Insulation per surface: areas from the drawing, the designer's choice, quantities and prices (owner 15/10)."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.construction.insulation import quantity_rows, spec, surfaces
from tests.test_electrical import _house


def test_exterior_walls_net_of_openings_and_nothing_chosen_by_the_program():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    wall = next(e for e in doc.entities.values() if e.kind == 'wall' and e.params['y1'] == 0 and e.params['y2'] == 0)
    stack.execute(AddEntity(Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=wall.id)))
    walls = [s for s in surfaces(doc) if s['category'] == 'exterior_wall']
    assert len(walls) == 4                                                    # the partition is not exterior
    south = next(s for s in walls if s['element'] == wall.id)
    assert south['area'] == pytest.approx(8.0 * 2.7 - 1.2 * 1.4)
    assert all(s['thermal'] is None and s['thickness'] is None for s in walls)  # no hidden default
    rows = quantity_rows(doc)
    assert rows[0][3]['code'] == 'insulation.thermal.exterior_wall.unset' and 'δεν επιλέχθηκε' in rows[0][0]


def test_choice_per_category_and_element_build_ups():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    stack.execute(AddEntity(Entity('insulation_spec', {'categories': {'exterior_wall': {'thermal': 'graphite_eps', 'thickness': 0.10}}})))
    walls = [s for s in surfaces(doc) if s['category'] == 'exterior_wall']
    assert all((s['thermal'], s['thickness']) == ('graphite_eps', 0.10) for s in walls)
    # A wall type with its own insulation layer keeps it (the element's build-up wins).
    w = walls[0]['element']
    stack.execute(UpdateEntity(w, {'wall_type': 'brick_double_insulated'}))
    own = next(s for s in surfaces(doc) if s['element'] == w)
    assert own['source'] == 'element' and own['thickness'] == pytest.approx(0.05)
    codes = {r[3]['code']: r[2] for r in quantity_rows(doc)}
    assert 'insulation.thermal.exterior_wall.graphite_eps.100mm' in codes
    with pytest.raises(ValueError):
        stack.execute(UpdateEntity(doc.entities[next(i for i, e in doc.entities.items() if e.kind == 'insulation_spec')].id,
                                   {'categories': {'exterior_wall': {'thermal': 'straw'}}}))


def test_tiled_roof_slope_area_and_its_own_insulation():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    stack.execute(AddEntity(Entity('pitched_roof', {'x0': 0.0, 'y0': 0.0, 'x1': 8.0, 'y1': 6.0, 'eave_z': 2.7, 'pitch': 30.0,
                                                    'overhang': 0.5, 'insulation': 'xps', 'insulation_thickness': 0.08})))
    roof = next(s for s in surfaces(doc) if s['category'] == 'pitched_roof')
    assert roof['area'] == pytest.approx(9.0 * 7.0 / math.cos(math.radians(30)), abs=0.01)
    assert (roof['thermal'], roof['thickness'], roof['source']) == ('xps', 0.08, 'element')
    assert roof['waterproofing'] is None                                      # system to be chosen
    assert any(r[3]['code'] == 'waterproofing.pitched_roof.unset' for r in quantity_rows(doc))


def test_insulation_tab_shows_every_surface_and_saves_the_choice_with_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui import insulation_tab
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        tab = insulation_tab.show(window)
        assert window._central_tabs.currentWidget() is tab and window.view is window.plan_view
        cats = [tab.spec.item(i, 0).text() for i in range(tab.spec.rowCount())]
        assert any(c.startswith('Εξωτερικοί τοίχοι') for c in cats)
        assert tab.table.rowCount() >= 4
        tab.set_choice('exterior_wall', 'thermal', 'rockwool'); app.processEvents(); tab.refresh()
        assert all(tab.spec.cellWidget(i, 0) is None for i in range(tab.spec.rowCount()))   # no stale widgets
        assert spec(window.doc)['exterior_wall']['thermal'] == 'rockwool'
        window._undo()
        assert spec(window.doc)['exterior_wall']['thermal'] is None
        from archforge.quantities.materials import all_lists
        assert 'Μονώσεις' in [s[0] for s in all_lists(window.doc)]
    finally:
        window._mark_clean(); window.close(); app.processEvents()
