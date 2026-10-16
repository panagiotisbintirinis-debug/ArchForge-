import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.site.paths import LIFT, path_mesh, path_outline
from archforge.site.terrain import default_terrain_params


def _path(**kw):
    p = {'x1': -5.0, 'y1': 0.0, 'x2': 5.0, 'y2': 0.0, 'z': 0.0, 'width': 1.5,
         'thickness': 0.12, 'style': 'sidewalk'}
    p.update(kw)
    return Entity('site_path', p, name='Πεζοδρόμιο')


def test_path_drapes_on_a_sloped_terrain_and_is_closed():
    doc = Document(); stack = CommandStack(doc)
    terrain = Entity('terrain', dict(default_terrain_params(doc), slope_x=5.0))
    stack.execute(AddEntity(terrain))
    path = _path(); stack.execute(AddEntity(path))
    verts, tris, roles = path_mesh(doc, path.params)
    assert validate_mesh(MeshPayload(verts, tris, roles)).watertight
    from archforge.site.terrain import terrain_height_at
    assert max(v[2] for v in verts) == pytest.approx(terrain_height_at(doc, 5.0, 0.75) + LIFT)
    stack.execute(UpdateEntity(terrain.id, {'slope_x': 0.0}))
    assert path.id in doc.dirty


def test_path_outline_and_validation():
    assert path_outline(_path().params) == ((-5.0, 0.75), (5.0, 0.75), (5.0, -0.75), (-5.0, -0.75))
    with pytest.raises(ValueError):
        Document().add(_path(style='highway'))


def test_terrain_menu_drags_road_sidewalk_and_path():
    from PySide6.QtWidgets import QApplication
    from archforge.core.plan_scene import build_plan_frame
    from archforge.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    menu = window._mockup_terrain_menu
    for label, (x1, y1, x2, y2) in (('Δρόμος', (0, -8, 20, -8)), ('Πεζοδρόμιο', (0, -5, 20, -5)), ('Μονοπάτι', (2, -4, 2, 0))):
        next(a for a in menu.actions() if a.text() == label).trigger()
        plan = window.plan_view
        plan.begin_view_line(x1, y1); plan.move_view_line(x2, y2); plan.end_view_line(x2, y2)
    styles = sorted((e.params['style'], e.params['width']) for e in window.doc.entities.values() if e.kind == 'site_path')
    assert styles == [('path', 1.0), ('road', 3.5), ('sidewalk', 1.5)]
    assert len([p for p in build_plan_frame(window.doc).primitives if p.role == 'site-path']) == 3
    # A click without a drag creates nothing.
    window.plan_view.begin_view_line(9, 9); window.plan_view.end_view_line(9.05, 9)
    assert len([e for e in window.doc.entities.values() if e.kind == 'site_path']) == 3
    window._mark_clean(); window.close(); app.processEvents()
