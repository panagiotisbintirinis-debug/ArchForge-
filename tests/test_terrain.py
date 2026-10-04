import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.site.terrain import default_terrain_params, terrain_height_at, terrain_mesh


def _house():
    doc = Document()
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 4)), ((6, 4), (0, 4)), ((0, 4), (0, 0))):
        doc.add(Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': 0.0,
                                'height': 2.7, 'thickness': 0.2}))
    return doc


def test_default_site_surrounds_the_house_just_below_ground_floor():
    doc = _house()
    p = default_terrain_params(doc)
    assert (p['x0'], p['y0'], p['x1'], p['y1']) == (-5.0, -5.0, 11.0, 9.0)
    assert p['elevation'] == -0.15
    stack = CommandStack(doc)
    stack.execute(AddEntity(Entity('terrain', p, name='Έδαφος')))
    assert terrain_height_at(doc, 3.0, 2.0) == pytest.approx(-0.15)
    assert terrain_height_at(doc, 50.0, 2.0) is None


def test_sloped_terrain_height_and_undo():
    doc = _house()
    stack = CommandStack(doc)
    terrain = Entity('terrain', default_terrain_params(doc), name='Έδαφος')
    stack.execute(AddEntity(terrain))
    stack.execute(UpdateEntity(terrain.id, {'slope_x': 10.0}))
    # 10 % over the 3 m from x0 = -5 to x = -2.
    assert terrain_height_at(doc, -2.0, 0.0) == pytest.approx(-0.15 + 0.3)
    stack.undo()
    assert terrain_height_at(doc, -2.0, 0.0) == pytest.approx(-0.15)


def test_terrain_mesh_is_a_closed_solid_following_the_grade():
    p = dict(default_terrain_params(_house()), slope_x=5.0, slope_y=-3.0)
    verts, tris, roles = terrain_mesh(p)
    assert validate_mesh(MeshPayload(verts, tris, roles)).watertight
    assert max(v[2] for v in verts) == pytest.approx(-0.15 + 0.05 * 16 + 0)


def test_terrain_rejects_an_empty_extent():
    doc = Document()
    with pytest.raises(ValueError):
        doc.add(Entity('terrain', {'x0': 1.0, 'y0': 0.0, 'x1': 1.0, 'y1': 4.0,
                                   'elevation': 0.0, 'slope_x': 0.0, 'slope_y': 0.0, 'thickness': 0.5}))


def test_terrain_appears_in_the_3d_scene_and_survives_save_load():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload

    doc = _house()
    doc.add(Entity('terrain', default_terrain_params(doc), name='Έδαφος'))
    payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)
    assert any(o['kind'] == 'terrain' for o in payload['objects'])
    restored = Document.from_dict(doc.to_dict())
    assert [e.kind for e in restored.entities.values()].count('terrain') == 1


def test_terrain_outline_is_on_the_ground_plan_only():
    from archforge.core.model import WorkPlane
    from archforge.core.plan_scene import build_plan_frame

    doc = _house()
    terrain = Entity('terrain', default_terrain_params(doc), name='Έδαφος')
    doc.add(terrain)
    doc.levels['Floor 2'] = 2.7
    ground = [p for p in build_plan_frame(doc).primitives if p.entity_id == terrain.id]
    assert len(ground) == 1 and ground[0].kind == 'polyline' and len(ground[0].points) == 5
    doc.work_plane = WorkPlane(name='Floor 2', origin=(0.0, 0.0, 2.7))
    assert not [p for p in build_plan_frame(doc).primitives if p.entity_id == terrain.id]


def _two_levels_with_terrain(slope_x=0.0):
    doc = _house()
    doc.levels['Floor 2'] = 2.7
    doc.add(Entity('terrain', dict(default_terrain_params(doc), slope_x=slope_x), name='Έδαφος'))
    return doc


def test_external_stair_starts_on_the_terrain_and_inside_stair_on_the_floor():
    from archforge.core.interaction import StairPlaceTransaction

    doc = _two_levels_with_terrain(slope_x=-2.0)
    stack = CommandStack(doc)
    outside = StairPlaceTransaction(doc, stack, (8.0, 1.0))
    expected = -0.15 + (-2.0 / 100.0) * (8.0 - (-5.0))
    assert outside.lower_z == pytest.approx(expected)
    outside.update(8.0, 5.0)
    stair = doc.get(outside.commit())
    assert stair.params['lower_z'] == pytest.approx(expected)
    assert stair.params['riser_count'] * stair.params['riser_height'] == pytest.approx(stair.params['upper_z'] - expected)

    inside = StairPlaceTransaction(doc, stack, (1.0, 1.0))
    assert inside.lower_z == 0.0


def test_terrain_button_creates_one_site_and_is_undoable():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    for e in _house().entities.values():
        window.stack.execute(AddEntity(Entity('wall', dict(e.params))))
    window._mockup_terrain_action.trigger()
    window._mockup_terrain_action.trigger()
    terrains = [e for e in window.doc.entities.values() if e.kind == 'terrain']
    assert len(terrains) == 1 and window.doc.selection == [terrains[0].id]
    window._undo()
    assert not [e for e in window.doc.entities.values() if e.kind == 'terrain']
    window._mark_clean(); window.close(); app.processEvents()


def test_elevation_points_shape_the_ground_locally_and_exactly():
    doc = _house()
    stack = CommandStack(doc)
    terrain = Entity('terrain', default_terrain_params(doc), name='Έδαφος')
    stack.execute(AddEntity(terrain))
    stack.execute(UpdateEntity(terrain.id, {'points': [[-3.0, 2.0, 1.2]]}))
    assert terrain_height_at(doc, -3.0, 2.0) == pytest.approx(1.2)
    near = terrain_height_at(doc, -2.0, 2.0)
    assert -0.15 < near < 1.2
    assert terrain_height_at(doc, 9.0, 2.0) == pytest.approx(-0.15)   # beyond 6 m
    verts, tris, roles = terrain_mesh(doc.get(terrain.id).params)
    assert validate_mesh(MeshPayload(verts, tris, roles)).watertight
    assert max(v[2] for v in verts) == pytest.approx(1.2, abs=0.05)
    stack.undo()
    assert terrain_height_at(doc, -3.0, 2.0) == pytest.approx(-0.15)


def test_bad_elevation_point_is_rejected():
    doc = _house()
    with pytest.raises(ValueError):
        doc.add(Entity('terrain', dict(default_terrain_params(doc), points=[[1.0, 2.0]])))


def test_terrain_menu_and_clicking_elevation_points_in_the_plan(monkeypatch):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from PySide6.QtWidgets import QApplication, QInputDialog
    from archforge.core.plan_scene import build_plan_frame
    from archforge.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    labels = [a.text() for a in window._mockup_terrain_menu.actions() if a.text()]
    assert labels == ['Δημιουργία εδάφους', 'Προδιαγραφές εδάφους…', 'Διαγραφή εδάφους', 'Υψομετρικά σημεία']
    next(a for a in window._mockup_terrain_menu.actions() if a.text() == 'Υψομετρικά σημεία').trigger()
    assert window.plan_view.controller.tool == 'terrain_point'
    monkeypatch.setattr(QInputDialog, 'getDouble', lambda *a, **k: (0.8, True))
    window.plan_view.sitePointRequested.emit('terrain_point', 2.0, 3.0)
    terrain = window._terrain_entity()
    assert terrain is not None
    assert terrain.params['points'] == [[2.0, 3.0, 0.8]]
    frame = build_plan_frame(window.doc)
    assert any(p.role == 'terrain-label' and dict(p.meta)['text'] == '+0.80' for p in frame.primitives)
    window._undo()
    assert not window._terrain_entity().params.get('points')
    next(a for a in window._mockup_terrain_menu.actions() if a.text() == 'Διαγραφή εδάφους').trigger()
    assert window._terrain_entity() is None
    window._mark_clean(); window.close(); app.processEvents()
