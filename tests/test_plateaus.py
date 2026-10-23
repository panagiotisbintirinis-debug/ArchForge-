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


def test_terrace_levels_are_held_by_the_walls():
    """Terrace levels (a drawing's F.L.) need no closed outline: each is flat as far as it «sees»; the ground
    steps at the wall between two terraces and slopes through a gap in it.  Survey points keep their blend."""
    from archforge.site.terrain import barriers, terrain_height_at, terrain_mesh, building_exclusions
    from archforge.geometry.mesh_validation import validate_mesh
    from archforge.geometry.mesh import MeshPayload
    doc = Document(); stack = CommandStack(doc)
    # A retaining wall along x = 10, open between y = 6 and 8 (a stair).
    for s in [(10, -2, 10, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0,
                                                'height': 2.0, 'thickness': 0.3})))
    t = Entity('terrain', {"x0": 0.0, "y0": -2.0, "x1": 20.0, "y1": 10.0, "elevation": 0.0, "slope_x": 0.0,
                           "slope_y": 0.0, "thickness": 0.5, "levels": [[5.0, 2.0, 1.0], [15.0, 2.0, 3.0]]})
    stack.execute(AddEntity(t))
    assert terrain_height_at(doc, 3.0, 0.0) == pytest.approx(1.0)                  # flat on its terrace
    assert terrain_height_at(doc, 9.7, 2.0) == pytest.approx(1.0, abs=0.01)         # up to the wall …
    assert terrain_height_at(doc, 10.3, 2.0) == pytest.approx(3.0, abs=0.01)        # … and the next level behind it
    gap = terrain_height_at(doc, 10.0, 7.0)
    assert 1.2 < gap < 2.8                                                          # through the stair: a slope
    v, tr, r = terrain_mesh(t.params, exclusions=building_exclusions(doc), walls=barriers(doc))
    assert validate_mesh(MeshPayload(v, tr, r)).watertight


def test_a_retaining_wall_stands_from_the_lower_ground_to_the_higher():
    from archforge.site.retaining import fit, fit_command
    doc = Document(); stack = CommandStack(doc)
    wall = Entity('wall', {'x1': 10, 'y1': -2, 'x2': 10, 'y2': 6, 'z': 0.0, 'height': 1.0, 'thickness': 0.3})
    stack.execute(AddEntity(wall))
    stack.execute(AddEntity(Entity('terrain', {"x0": 0.0, "y0": -2.0, "x1": 20.0, "y1": 10.0, "elevation": 0.0,
                                               "slope_x": 0.0, "slope_y": 0.0, "thickness": 0.5,
                                               "levels": [[5.0, 2.0, 1.0], [15.0, 2.0, 3.0]]})))
    assert fit(doc, wall) == {"z": pytest.approx(1.0, abs=0.01), "height": pytest.approx(2.0, abs=0.02)}
    command, n = fit_command(doc, [wall])
    stack.execute(command)
    assert n == 1 and doc.get(wall.id).params['z'] == pytest.approx(1.0, abs=0.01)
    stack.undo()
    assert doc.get(wall.id).params['z'] == 0.0


def test_level_tool_and_retaining_fit_in_the_window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        wall = Entity('wall', {'x1': 10, 'y1': -2, 'x2': 10, 'y2': 6, 'z': 0.0, 'height': 1.0, 'thickness': 0.3})
        w.stack.execute(AddEntity(wall))
        tool = w._terrain_tools
        texts = [a.text() for a in w._terrain_regions_menu.actions()]
        assert any(t.startswith('Στάθμη πλατώματος') for t in texts) and any(t.startswith('Τοιχία: ύψος') for t in texts)
        tool.start('level')
        assert tool.place_level(5.0, 2.0, z=1.0) and tool.place_level(15.0, 2.0, z=3.0)
        assert w._terrain_entity().params['levels'] == [[5.0, 2.0, 1.0], [15.0, 2.0, 3.0]]
        w.doc.select([wall.id])
        assert tool.fit_retaining() == 1
        assert w.doc.get(wall.id).params['height'] == pytest.approx(2.0, abs=0.02)
        w.stack.undo(); w.stack.undo()
        assert w._terrain_entity().params['levels'] == [[5.0, 2.0, 1.0]]
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_a_green_roof_is_under_the_ground():
    """Υπόσκαφο: over a green roof the ground is not cut and lies at least on its soil; the soil the section draws
    over the roof runs over the building's walls, while the terrace below its front stays held by them."""
    from archforge.architecture.storey_slabs import storey_slab_command
    from archforge.core.commands import UpdateEntity
    from archforge.site.terrain import barriers, building_exclusions, green_roofs, terrain_height_at, terrain_mesh
    doc = Document(); stack = CommandStack(doc)
    for s in [(0, 0, 10, 0), (10, 0, 10, 8), (10, 8, 0, 8), (0, 8, 0, 0), (5, 0, 5, 8)]:          # two rooms, 3,40 high
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0,
                                                'height': 3.4, 'thickness': 0.3})))
    command, roof = storey_slab_command(doc, 'room_roof', 0.0, 'Ground', thickness=0.2)
    stack.execute(command)
    t = Entity('terrain', {"x0": -10.0, "y0": -10.0, "x1": 20.0, "y1": 20.0, "elevation": 0.0, "slope_x": 0.0,
                           "slope_y": 0.0, "thickness": 0.5,
                           "levels": [[5.0, -3.0, 0.0], [5.0, 12.0, 4.6], [2.5, 4.0, 3.9]]})   # front terrace, bank, soil
    stack.execute(AddEntity(t))
    assert not green_roofs(doc) and terrain_height_at(doc, 7.5, 4.0) == pytest.approx(0.0)   # walled in: the plane
    stack.execute(UpdateEntity(roof.id, {'green': 1, 'soil': 0.1}))
    (outline, lowest), = green_roofs(doc)
    assert lowest == pytest.approx(3.7)
    assert terrain_height_at(doc, 2.5, 4.0) == pytest.approx(3.9, abs=0.01)                     # the soil, as drawn
    assert terrain_height_at(doc, 7.5, 4.0) > 3.7                                               # … over the middle wall
    assert terrain_height_at(doc, 5.0, -1.0) == pytest.approx(0.0, abs=0.05)                    # the terrace in front
    v, tr, r = terrain_mesh(t.params, exclusions=building_exclusions(doc), walls=barriers(doc), floors=green_roofs(doc))
    tops = [v[i] for tri, role in zip(tr, r) if role == 'top' for i in tri]
    assert any(1 < x < 9 and 1 < y < 7 for x, y, _z in tops)                                    # the roof is covered
    assert all(z >= 3.7 - 1e-6 for x, y, z in tops if 0.5 < x < 9.5 and 0.5 < y < 7.5)
