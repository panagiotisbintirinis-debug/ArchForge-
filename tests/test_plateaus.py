"""Owner 22/10: «εάν ό,τι εργαλεία ή ρύθμιση λείπει, την φτιάχνουμε στην πηγή» — the masterplan's terraces
(«+137.10m [F.L.]» parking, «+134.90» garden …) held by retaining walls.  A plateau is one click inside the area
the walls close; neighbouring plateaus at other levels step behind the wall between them."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.geometry.regions import signed_area
from archforge.site import plateaus as P
from archforge.site.terrain import terrain_height


def _terraces(doc, stack):
    """Two terraces side by side: 0–10 and 10–20 along x, 8 deep, retaining walls 30 cm on their axes."""
    for s in [(0, 0, 20, 0), (20, 0, 20, 8), (20, 8, 0, 8), (0, 8, 0, 0), (10, 0, 10, 8)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0,
                                                'height': 1.0, 'thickness': 0.3})))


def test_the_area_around_a_click_up_to_the_wall_faces():
    doc = Document(); stack = CommandStack(doc); _terraces(doc, stack)
    poly, z = P.area_at(doc, 5.0, 4.0)
    assert z == 0.0 and abs(signed_area(poly)) == pytest.approx(9.7 * 7.7)       # inside the faces, not the axes
    assert P.area_at(doc, 30.0, 4.0) is None                                      # outside every closed area


def test_neighbouring_plateaus_step_behind_the_wall():
    doc = Document(); stack = CommandStack(doc); _terraces(doc, stack)
    terrain = {"x0": -5.0, "y0": -5.0, "x1": 25.0, "y1": 13.0, "elevation": 0.0, "slope_x": 10.0, "slope_y": 0.0, "thickness": 0.5}
    low = P.region(P.area_at(doc, 5.0, 4.0)[0], 1.20, "a")
    high = P.region(P.area_at(doc, 15.0, 4.0)[0], 3.00, "b")
    t = P.with_plateau(P.with_plateau(terrain, low), high)                    # a wall's thickness apart: allowed
    assert terrain_height(t, 5.0, 4.0) == pytest.approx(1.20) and terrain_height(t, 15.0, 4.0) == pytest.approx(3.00)
    assert terrain_height(t, 9.84, 4.0) == pytest.approx(1.20) and terrain_height(t, 10.16, 4.0) == pytest.approx(3.00)
    # Clicked again at another level: the new word about that ground replaces the old one.
    t = P.with_plateau(t, P.region(P.area_at(doc, 5.0, 4.0)[0], 1.50, "c"))
    assert [r["id"] for r in t["regions"]] == ["b", "c"] and terrain_height(t, 5.0, 4.0) == pytest.approx(1.50)


def test_the_plateau_tool_in_the_window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        _terraces(w.doc, w.stack)
        tool = w._terrain_tools
        assert any(a.text().startswith('Πλάτωμα') for a in w._terrain_regions_menu.actions())
        tool.start('pick')
        assert tool.place_plateau(5.0, 4.0, z=1.2) and tool.place_plateau(15.0, 4.0, z=3.0)
        terrain = w._terrain_entity()
        assert sorted(r['elevation'] for r in terrain.params['regions']) == [1.2, 3.0]
        assert not tool.place_plateau(30.0, 4.0, z=1.0)                          # nothing closed there: told, not guessed
        w.stack.undo()
        assert [r['elevation'] for r in w._terrain_entity().params['regions']] == [1.2]
    finally:
        w._mark_clean(); w.close(); app.processEvents()
