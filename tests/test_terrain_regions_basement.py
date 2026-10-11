import copy
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')

import pytest
from archforge.core.model import Document, Entity, WorkPlane
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.site.terrain import terrain_height, terrain_mesh, default_terrain_params


def house(z=-3.0):
    doc = Document()
    doc.levels['Basement'] = z
    for a, b in (((0, 0), (6, 0)), ((6, 0), (6, 4)), ((6, 4), (0, 4)), ((0, 4), (0, 0))):
        doc.add(Entity('wall', dict(x1=a[0], y1=a[1], x2=b[0], y2=b[1],
                                  z=z, height=-z, thickness=.2)))
    return doc


def region(points, elevation, region_id='r1'):
    return dict(id=region_id, shape='polygon', points=points, elevation=elevation, transition=5.0)


def test_elevation_is_constant_over_a_whole_shape_with_smooth_transition():
    p = dict(default_terrain_params(Document()), regions=[region([[-6,-2],[-2,-2],[-2,2],[-6,2]], -10.5)])
    assert terrain_height(p, -4, 0) == pytest.approx(-10.5)
    assert terrain_height(p, -2, 0) == pytest.approx(-10.5)
    assert -10.5 < terrain_height(p, -1, 0) < -.15
    assert terrain_height(p, 4, 0) == pytest.approx(-.15)


def test_regions_and_legacy_points_are_persistent_and_one_undo_restores_them():
    doc = Document(); stack = CommandStack(doc)
    e = Entity('terrain', dict(default_terrain_params(doc), points=[[7,7,1.0]]))
    stack.execute(AddEntity(e)); before = copy.deepcopy(doc.to_dict())
    stack.execute(UpdateEntity(e.id, {'regions':[region([[-6,-2],[-2,-2],[-2,2],[-6,2]], -10.5)]}))
    assert Document.from_dict(doc.to_dict()).get(e.id).params == doc.get(e.id).params
    stack.undo(); assert doc.to_dict() == before
    stack.redo(); assert doc.get(e.id).params['points'] == [[7,7,1.0]]


def test_invalid_and_conflicting_overlapping_shapes_are_rejected():
    p = default_terrain_params(Document())
    for points in ([[0,0],[1,1]], [[0,0],[2,2],[0,2],[2,0]]):
        with pytest.raises(ValueError):
            Document().add(Entity('terrain', dict(p, regions=[region(points, 0)])))
    first = region([[0,0],[3,0],[3,3],[0,3]], 0)
    second = region([[2,2],[4,2],[4,4],[2,4]], -10, 'r2')
    with pytest.raises(ValueError):
        Document().add(Entity('terrain', dict(p, regions=[first, second])))
    second['points']=[[3,0],[5,0],[5,3],[3,3]]
    with pytest.raises(ValueError):
        Document().add(Entity('terrain', dict(p, regions=[first, second])))


def test_ground_mesh_stops_at_the_exterior_faces_and_is_closed():
    from archforge.site.terrain import building_exclusions
    doc = house(); p = default_terrain_params(doc)
    v,t,r = terrain_mesh(p, exclusions=building_exclusions(doc))
    assert validate_mesh(MeshPayload(v,t,r)).watertight
    area = 0.
    for tri, role in zip(t,r):
        if role != 'top': continue
        a,b,c = [v[i] for i in tri]
        x,y = sum(q[0] for q in (a,b,c))/3, sum(q[1] for q in (a,b,c))/3
        assert not (-.1+1e-7 < x < 6.1-1e-7 and -.1+1e-7 < y < 4.1-1e-7)
        area += abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
    assert area == pytest.approx(16*14 - 6.2*4.2)


def test_wall_move_rebuilds_the_terrain_in_the_existing_incremental_cache():
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    doc = house(); stack = CommandStack(doc)
    terrain = Entity('terrain', default_terrain_params(doc)); stack.execute(AddEntity(terrain))
    cache = IncrementalEvaluationCache(SculptedPreviewBackend())
    before = cache.sync(doc).body(terrain.id).payload
    wall = next(e for e in doc.entities.values() if e.kind == 'wall')
    stack.execute(UpdateEntity(wall.id, {'y1':-1., 'y2':-1.}))
    after = cache.sync(doc).body(terrain.id).payload
    assert after != before
    stack.undo(); assert cache.sync(doc).body(terrain.id).payload == before


def test_section_includes_real_terrain_and_more_than_nine_metres_relief():
    from archforge.output.section_cut import cut_section
    doc = house()
    p = default_terrain_params(doc)
    p['regions'] = [region([[-5,-4],[11,-4],[11,-1],[-5,-1]], -3., 'front'),
                    region([[-5,5],[11,5],[11,9],[-5,9]], 7., 'rear')]
    doc.add(Entity('terrain', p))
    data = cut_section(doc, dict(x1=3,y1=-5,x2=3,y2=9,flip=0))
    assert any(c['kind'] == 'terrain' and c['loops'] for c in data['cuts'])
    assert data['bounds'][3] - data['bounds'][1] > 9.
    assert any(name == 'Υπόγειο' and z == -3. for z,mark,name in data['levels'])
    marks = [z for u,z in data['terrain_marks']]
    assert max(marks) - min(marks) >= 10.-1e-6


def test_basement_menu_creates_an_active_negative_storey_and_wall_reaches_ground(monkeypatch):
    from PySide6.QtWidgets import QApplication, QInputDialog
    from archforge.ui.main_window import MainWindow
    from archforge.core.viewport import PointerEvent
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    monkeypatch.setattr(QInputDialog, 'getDouble', lambda *a,**k: (3.5, True))
    w._mockup_basement_action.trigger()
    assert w.doc.levels['Basement'] == -3.5
    assert w.doc.work_plane.name == 'Basement'
    assert w._plan_title.text() == 'Κάτοψη - Υπόγειο'
    c = w.plan_view.controller; c.set_tool('wall')
    c.pointer_down(PointerEvent(0.,0.)); c.pointer_move(PointerEvent(4.,0.)); c.pointer_up(PointerEvent(4.,0.))
    wall = next(e for e in w.doc.entities.values() if e.kind == 'wall')
    assert wall.params['z'] == -3.5 and wall.params['height'] == 3.5
    w._undo(); w._undo()
    assert 'Basement' not in w.doc.levels and w.doc.work_plane.origin[2] == 0.
    w._redo(); assert w.doc.work_plane.origin[2] == -3.5
    w._mark_clean(); w.close(); app.processEvents()


def test_area_tool_on_an_upper_storey_keeps_elevation_overlays_visible(monkeypatch):
    from PySide6.QtWidgets import QApplication, QInputDialog
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w.doc.levels['Floor 2'] = 2.7; w.doc.work_plane = WorkPlane(name='Floor 2',origin=(0,0,2.7))
    w._create_terrain()
    monkeypatch.setattr(QInputDialog, 'getDouble', lambda *a,**k: (-10.5, True))
    w._terrain_tools.start('rectangle')
    w._terrain_tools.place_shape([[-6,-2],[-2,-2],[-2,2],[-6,2]], 'rectangle')
    p = w._terrain_entity().params
    assert len(p['regions']) == 1
    w.plan_view.redraw()
    assert any('−10,50' in text.toPlainText() or '-10,50' in text.toPlainText()
               for text in w.plan_view.scene().items() if hasattr(text, 'toPlainText'))
    w._undo(); assert not w._terrain_entity().params.get('regions')
    w._mark_clean(); w.close(); app.processEvents()


@pytest.mark.parametrize('shape', ['circle', 'polygon'])
def test_non_axis_aligned_shapes_produce_a_closed_terrain(shape):
    from archforge.site.elevation_regions import shape_points
    points = (shape_points('circle',(2.3,1.2),(4.5,1.2)) if shape == 'circle' else
              [[-3.8,-3.1],[2.2,-1.7],[1.5,3.7],[-2.2,1.8]])
    p = dict(default_terrain_params(Document()), regions=[dict(region(points,-10.),shape=shape)])
    v,t,r = terrain_mesh(p)
    assert validate_mesh(MeshPayload(v,t,r)).watertight


def test_rotated_building_excavation_is_exact_and_closed():
    from archforge.site.terrain import building_exclusions
    doc = house()
    cosine,sine = math.cos(.43),math.sin(.43)
    for wall in list(doc.entities.values()):
        p = wall.params
        changes = {}
        for i in (1,2):
            x,y = p[f'x{i}'],p[f'y{i}']
            changes.update({f'x{i}':x*cosine-y*sine,f'y{i}':x*sine+y*cosine})
        doc.update(wall.id,changes)
    p = dict(default_terrain_params(doc),x0=-8.,y0=-8.,x1=8.,y1=8.)
    v,t,r = terrain_mesh(p,exclusions=building_exclusions(doc))
    assert validate_mesh(MeshPayload(v,t,r)).watertight
    area = sum(abs((v[b][0]-v[a][0])*(v[c][1]-v[a][1])-
                   (v[b][1]-v[a][1])*(v[c][0]-v[a][0]))/2 for (a,b,c),role in zip(t,r) if role == 'top')
    assert area == pytest.approx(16*16-6.2*4.2,abs=1e-6)


@pytest.fixture
def terrain_window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400,900); w.show(); app.processEvents()
    w.plan_view.centerOn(0,0)
    yield w,app
    w._mark_clean(); w.close(); app.processEvents()


def _drag(w, a, b, app):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    view = w.plan_view; viewport = view.viewport()
    a,b = view.mapFromScene(QPointF(*a)),view.mapFromScene(QPointF(*b))
    QTest.mousePress(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,a)
    QTest.mouseMove(viewport,b)
    QTest.mouseRelease(viewport,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,b)
    app.processEvents()


def test_mouse_creation_move_vertex_height_delete_and_history(terrain_window,monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    w,app = terrain_window
    monkeypatch.setattr(QInputDialog,'getDouble',lambda *a,**k:(-10.5,True))
    w._terrain_tools.start('rectangle')
    _drag(w,(-3,-2),(0,1),app)
    e = w._terrain_entity()
    assert e.params['regions'][0]['points'] == [[-3.,-2.],[0.,-2.],[0.,1.],[-3.,1.]]
    assert len(w.stack.done) == 1
    _drag(w,(-1.5,-.5),(-.5,.5),app)
    assert w._terrain_entity().params['regions'][0]['points'][0] == [-2.,-1.]
    assert len(w.stack.done) == 2
    _drag(w,(-2,-1),(-3,-1),app)
    assert w._terrain_entity().params['regions'][0]['points'][0] == [-3.,-1.]
    assert w._terrain_tools.update_selected('elevation',-11.)
    assert terrain_height(w._terrain_entity().params,-1.,0.) == -11.
    history = len(w.stack.done)
    assert w._terrain_tools.update_selected('elevation',-11.)
    assert len(w.stack.done) == history
    assert w._terrain_tools.delete_selected()
    assert not w._terrain_entity().params['regions']
    w._undo(); assert w._terrain_entity().params['regions'][0]['elevation'] == -11.
    w._undo(); assert w._terrain_entity().params['regions'][0]['elevation'] == -10.5
    w._undo(); w._undo(); w._undo(); assert w._terrain_entity() is None
    for _ in range(5): w._redo()
    assert w._terrain_entity().params['regions'] == []


@pytest.mark.parametrize('shape',['circle','polygon'])
def test_mouse_circle_and_polygon_close_on_first_point(terrain_window,monkeypatch,shape):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QInputDialog
    w,app = terrain_window
    monkeypatch.setattr(QInputDialog,'getDouble',lambda *a,**k:(-9.5,True))
    w._terrain_tools.start(shape)
    if shape == 'circle': _drag(w,(0,0),(2,0),app)
    else:
        for p in [(-2,-2),(2,-2),(0,2),(-2,-2)]:
            QTest.mouseClick(w.plan_view.viewport(),Qt.MouseButton.LeftButton,
                             Qt.KeyboardModifier.NoModifier,w.plan_view.mapFromScene(QPointF(*p)))
        app.processEvents()
    e = w._terrain_entity()
    assert len(w.stack.done) == 1
    assert e.params['regions'][0]['shape'] == shape
    assert terrain_height(e.params,0.,0.) == -9.5


def test_cancelled_mouse_preview_does_not_modify_project(terrain_window):
    from PySide6.QtCore import QPointF,Qt
    from PySide6.QtTest import QTest
    w,app = terrain_window
    before = copy.deepcopy(w.doc.to_dict())
    w._terrain_tools.start('polygon')
    QTest.mouseClick(w.plan_view.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,
                     w.plan_view.mapFromScene(QPointF(0,0)))
    QTest.keyClick(w.plan_view.viewport(),Qt.Key.Key_Escape)
    assert w.doc.to_dict() == before and not w.stack.done
    assert w._terrain_tools.draft is None


def test_moving_a_legacy_point_expands_site_and_preserves_other_points(terrain_window):
    w,app = terrain_window
    e = Entity('terrain',dict(default_terrain_params(w.doc),points=[[0,0,-10.],[3,3,1.]]))
    w.stack.execute(AddEntity(e)); w.plan_view.redraw()
    w._terrain_tools.start('edit')
    _drag(w,(0,0),(1,1),app)
    assert w._terrain_entity().params['points'] == [[1.,1.,-10.],[3.,3.,1.]]
    w._terrain_tools.update_selected('x',25.)
    assert w._terrain_entity().params['x1'] == 25.
    w._undo(); assert w._terrain_entity().params['x1'] == 10.
    w._undo(); assert w._terrain_entity().params['points'] == [[0.,0.,-10.],[3.,3.,1.]]


def test_locked_terrain_refuses_new_shape_without_changing_project_or_history(terrain_window,monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    w,app = terrain_window
    e = Entity('terrain',dict(default_terrain_params(w.doc),points=[[3.,3.,-9.5]]))
    e.locked = True
    w.stack.execute(AddEntity(e))
    before = copy.deepcopy(w.doc.to_dict()); history = len(w.stack.done)
    monkeypatch.setattr(QInputDialog,'getDouble',lambda *a,**k:(-10.5,True))
    w._terrain_tools.start('rectangle')
    assert not w._terrain_tools.place_shape([[0,0],[2,0],[2,2],[0,2]],'rectangle')
    assert w.doc.to_dict() == before and len(w.stack.done) == history
