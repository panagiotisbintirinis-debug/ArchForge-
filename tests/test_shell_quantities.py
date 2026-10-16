"""Shell quantities in the unit each trade prices by — geometry only, pieces only from the user's data sheet."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.construction import shell
from tests.test_electrical import _house


def _doc():
    doc = Document(); stack = CommandStack(doc); _house(stack)
    return doc, stack


def test_masonry_m2_per_wall_type_net_of_openings_and_bricks_only_from_the_data_sheet():
    doc, stack = _doc()
    wall = next(e for e in doc.entities.values() if e.kind == 'wall' and e.params['y1'] == 0 and e.params['y2'] == 0)
    stack.execute(AddEntity(Entity('door', {'offset': 1.0, 'width': 0.9, 'height': 2.1, 'sill': 0.0}, parent_id=wall.id)))
    rows = {m['code']: (d, q) for d, _u, q, m in shell.masonry_list(doc)}
    total = 2 * 8 * 2.7 + 3 * 6 * 2.7 - 0.9 * 2.1
    assert rows['masonry.generic'][1] == pytest.approx(total, abs=0.01)
    assert 'masonry.generic.pieces' not in rows                                    # no typical bricks per m²
    stack.execute(AddEntity(Entity('construction_spec', {'pieces_per_m2': {'generic': 33.0}})))
    rows = {m['code']: q for _d, _u, q, m in shell.masonry_list(doc)}
    assert rows['masonry.generic.pieces'] == math.ceil(total * 33.0)
    # Plasterboard walls are measured by their own list, not as masonry.
    stack.execute(UpdateEntity(wall.id, {'wall_type': 'drywall_100'}))
    assert shell.masonry_list(doc)[0][2] == pytest.approx(total - (8 * 2.7 - 0.9 * 2.1), abs=0.01)


def test_plaster_tiled_roof_and_joinery():
    doc, stack = _doc()
    wall = next(e for e in doc.entities.values() if e.kind == 'wall' and e.params['y1'] == 0 and e.params['y2'] == 0)
    stack.execute(AddEntity(Entity('window', {'offset': 2.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=wall.id)))
    stack.execute(AddEntity(Entity('window', {'offset': 5.0, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=wall.id)))
    plaster = {m['code']: q for _d, _u, q, m in shell.plaster_list(doc)}
    assert plaster['plaster.exterior'] == pytest.approx(2 * (8 + 6) * 2.7 - 2 * 1.2 * 1.4, abs=0.01)
    stack.execute(AddEntity(Entity('pitched_roof', {'x0': 0.0, 'y0': 0.0, 'x1': 8.0, 'y1': 6.0, 'eave_z': 2.7, 'pitch': 25.0,
                                                    'overhang': 0.4, 'tile': 'roman'})))
    roof = shell.roof_list(doc)
    assert roof[0][2] == pytest.approx(8.8 * 6.8 / math.cos(math.radians(25)), abs=0.01) and len(roof) == 1
    joinery = shell.joinery_list(doc)
    assert len(joinery) == 1 and joinery[0][2] == 2 and joinery[0][0].startswith('Παράθυρο') and '1,20×1,40' in joinery[0][0]


def test_slab_concrete_from_area_times_model_thickness():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        window._create_auto_floors()
        rows = shell.slab_concrete_list(window.doc)
        floors = next(r for r in rows if r[3]['code'] == 'concrete.slab.room_floor')
        from archforge.ui.project_outline import slab_info
        expect = sum(slab_info(window.doc, e)['area'] * slab_info(window.doc, e)['thickness']
                     for e in window.doc.entities.values() if e.kind == 'room_floor')
        assert floors[2] == pytest.approx(expect, abs=0.01) and expect > 0
        assert rows[-1][2] is None and 'στατική' in rows[-1][0]
        from archforge.quantities.materials import all_lists
        names = [s[0] for s in all_lists(window.doc)]
        assert {'Τοιχοποιίες', 'Πλάκες', 'Σοβατίσματα'} <= set(names)
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_pieces_per_m2_entered_in_the_masonry_card_with_undo():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui import trades_tab
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        tab = trades_tab.show(window, 'Τοιχοποιίες')
        tab.set_pieces('generic', 33.0); app.processEvents()
        assert any(m['code'] == 'masonry.generic.pieces' for _d, _u, _q, m in shell.masonry_list(window.doc))
        window._undo()
        assert not any(m['code'] == 'masonry.generic.pieces' for _d, _u, _q, m in shell.masonry_list(window.doc))
    finally:
        window._mark_clean(); window.close(); app.processEvents()
