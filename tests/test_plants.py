import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.site.plants import plant_base_z, plant_mesh
from archforge.site.terrain import default_terrain_params


def _tree(**kw):
    p = {'x': 3.0, 'y': 2.0, 'z': 0.0, 'height': 4.0, 'canopy': 3.0, 'species': 'tree'}
    p.update(kw)
    return Entity('plant', p, name='Δέντρο')


def test_plant_stands_on_the_terrain_and_follows_it():
    doc = Document(); stack = CommandStack(doc)
    terrain = Entity('terrain', dict(default_terrain_params(doc), slope_x=10.0))
    stack.execute(AddEntity(terrain))
    tree = _tree(); stack.execute(AddEntity(tree))
    expected = -0.15 + 0.10 * (3.0 - (-10.0))
    assert plant_base_z(doc, tree.params) == pytest.approx(expected)
    stack.execute(UpdateEntity(terrain.id, {'slope_x': 0.0}))
    assert plant_base_z(doc, doc.get(tree.id).params) == pytest.approx(-0.15)
    assert tree.id in doc.dirty


def test_plant_mesh_is_closed_with_bark_and_foliage():
    for species in ('tree', 'shrub'):
        verts, tris, roles = plant_mesh(_tree(species=species).params, 0.0)
        assert set(roles) == {'trunk', 'canopy'}
        # Two closed parts (trunk prism + crown); each edge used twice.
        assert validate_mesh(MeshPayload(verts, tris, roles)).watertight
        assert max(v[2] for v in verts) == pytest.approx(4.0)


def test_plant_rejects_unknown_species():
    with pytest.raises(ValueError):
        Document().add(_tree(species='cactus'))


def test_plant_renders_as_bark_and_foliage_parts():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload

    doc = Document(); doc.add(_tree())
    objs = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)['objects']
    assert sorted(o['render_part'].split(':')[1] for o in objs if o['kind'] == 'plant') == ['canopy', 'trunk']


def test_terrain_menu_places_trees_and_shrubs_by_clicking():
    from PySide6.QtWidgets import QApplication
    from archforge.core.plan_scene import build_plan_frame
    from archforge.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    next(a for a in window._mockup_terrain_menu.actions() if a.text() == 'Φυτό: Δέντρο').trigger()
    window.plan_view.sitePointRequested.emit(window.plan_view.controller.tool, 5.0, 5.0)
    next(a for a in window._mockup_terrain_menu.actions() if a.text() == 'Φυτό: Θάμνος').trigger()
    window.plan_view.sitePointRequested.emit(window.plan_view.controller.tool, 7.0, 5.0)
    plants = sorted((e.params['species'], e.params['x']) for e in window.doc.entities.values() if e.kind == 'plant')
    assert plants == [('shrub', 7.0), ('tree', 5.0)]
    assert len([p for p in build_plan_frame(window.doc).primitives if p.role == 'plant']) == 2
    window._undo()
    assert len([e for e in window.doc.entities.values() if e.kind == 'plant']) == 1
    window._mark_clean(); window.close(); app.processEvents()
