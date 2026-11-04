"""Synthetic terrain fixtures: exact model constraints, not real survey data."""
import copy

import pytest

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.site.terrain import terrain_height_at, terrain_heights, terrain_mesh


def fixture():
    doc = Document()
    ground = Entity('terrain', dict(x0=0., y0=0., x1=10., y1=10., elevation=0.,
                                   slope_x=10., slope_y=0., thickness=1., points=[[1., 2., 2.]],
                                   blend_radius=3., altitude_ref=100.))
    doc.add(ground)
    section = Entity('section_line', dict(x1=-2., y1=2., x2=12., y2=2., flip=0))
    doc.add(section)
    return doc, ground.id, section.id


def test_profile_clips_to_site_and_distinguishes_samples_from_survey():
    from archforge.site.terrain_profiles import profile
    doc, tid, sid = fixture()
    data = profile(doc, tid, sid, samples=21)
    assert data['range'] == pytest.approx((2., 12.))
    assert data['survey'][0]['station'] == pytest.approx(3.)
    assert data['survey'][0]['z'] == 2.
    assert data['altitude_ref'] == 100.
    for row in data['samples']:
        assert row['z'] == pytest.approx(terrain_height_at(doc, row['x'], row['y']))
    doc.update(sid, {'flip': 1})
    assert profile(doc, tid, sid)['survey'][0]['station'] == pytest.approx(11.)


def test_design_edit_preserves_survey_and_propagates_to_every_section_undo_reload():
    from archforge.site.terrain_profiles import edit_control, profile
    doc, tid, sid = fixture()
    other = Entity('section_line', dict(x1=5., y1=0., x2=5., y2=10., flip=0))
    doc.add(other)
    stack = CommandStack(doc)
    before = copy.deepcopy(doc.to_dict())
    points = copy.deepcopy(doc.get(tid).params['points'])
    stack.execute(edit_control(doc, tid, sid, station=7., z=4.))
    assert len(stack.done) == 1
    assert doc.get(tid).params['points'] == points
    assert terrain_height_at(doc, 1., 2.) == 2.
    assert terrain_height_at(doc, 5., 2.) == pytest.approx(4.)
    assert profile(doc, tid, other.id)['controls'][0]['station'] == pytest.approx(2.)
    restored = Document.from_dict(doc.to_dict())
    assert terrain_height_at(restored, 5., 2.) == pytest.approx(4.)
    stack.undo()
    assert doc.to_dict() == before
    stack.redo()
    control = doc.get(tid).params['profile_controls'][0]
    stack.execute(edit_control(doc, tid, sid, 7., 5., control_id=control['id']))
    assert len(doc.get(tid).params['profile_controls']) == 1
    assert terrain_height_at(doc, 5., 2.) == pytest.approx(5.)
    snapshot = copy.deepcopy(doc.to_dict())
    count = len(stack.done)
    stack.execute(edit_control(doc,tid,sid,7.,5.,control_id=control['id']))
    assert len(stack.done)==count and doc.to_dict()==snapshot


def test_conflicts_outside_site_and_locked_terrain_are_rejected_before_changes():
    from archforge.site.terrain_profiles import edit_control
    doc, tid, sid = fixture()
    before = copy.deepcopy(doc.to_dict())
    for station, z in [(3., 9.), (0., 9.), (7., float('nan'))]:
        with pytest.raises(ValueError):
            edit_control(doc, tid, sid, station, z)
        assert doc.to_dict() == before
    doc.get(tid).locked = True
    with pytest.raises(PermissionError):
        edit_control(doc, tid, sid, 7., 9.)


def test_profile_controls_are_validated_and_mesh_contains_the_exact_design_node():
    from archforge.site.terrain_profiles import edit_control
    doc, tid, sid = fixture()
    CommandStack(doc).execute(edit_control(doc, tid, sid, 7.13, 4.))
    p = doc.get(tid).params
    verts, tris, roles = terrain_mesh(p)
    assert any(abs(x-5.13)<1e-8 and abs(y-2)<1e-8 and abs(z-4)<1e-8 for x,y,z in verts)
    from archforge.geometry.mesh import MeshPayload
    from archforge.geometry.mesh_validation import validate_mesh
    assert validate_mesh(MeshPayload(verts,tris,roles)).watertight
    assert terrain_heights(p, [(1.,2.), (5.13,2.)]) == pytest.approx([2.,4.])
    with pytest.raises(ValueError):
        doc.update(tid, {'profile_controls': [{'id':'bad','x':5.,'y':2.,'z':float('inf')}]})


def test_protected_sources_include_terrace_levels_and_off_line_survey_points():
    from archforge.site.terrain_profiles import edit_control
    doc, tid, sid = fixture()
    doc.update(tid, {'levels': [[2., 7., 6.]]})
    anchors = [(1.,2.), (2.,7.)]
    before = [terrain_height_at(doc,x,y) for x,y in anchors]
    CommandStack(doc).execute(edit_control(doc, tid, sid, 7., 4.))
    assert [terrain_height_at(doc,x,y) for x,y in anchors] == pytest.approx(before)


def test_numeric_grade_is_derived_from_a_preceding_record_not_an_invented_datum():
    from archforge.site.terrain_profiles import edit_grade
    doc,tid,sid = fixture()
    stack = CommandStack(doc)
    stack.execute(edit_grade(doc,tid,sid,7.,25.))
    assert terrain_height_at(doc,5.,2.) == pytest.approx(3.)  # 2 + 4 * .25
    assert terrain_height_at(doc,1.,2.) == 2.
    with pytest.raises(ValueError,match='preceding'):
        edit_grade(doc,tid,sid,2.5,5.)


def test_control_nearly_on_a_mesh_line_does_not_create_zero_area_faces_or_a_survey_cross_grid():
    from archforge.site.terrain_profiles import grid
    from archforge.geometry.mesh import MeshPayload
    from archforge.geometry.mesh_validation import validate_mesh
    params = dict(x0=0.,y0=0.,x1=1.,y1=1.,elevation=0.,thickness=1.,
                  profile_controls=[dict(id='design',x=.5+1e-14,y=.6,z=1.)])
    assert validate_mesh(MeshPayload(*terrain_mesh(params,cell=.5))).watertight
    params['points'] = [[i/1000.,i/2000.,0.] for i in range(400)]
    xs,ys = grid(params,10,10)
    assert len(xs)<=12 and len(ys)<=12


def test_profile_dialog_numeric_edit_drag_cancel_undo_and_many_sections(monkeypatch,tmp_path):
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QMainWindow
    from archforge.ui.terrain_profile import TerrainProfileDialog
    from archforge.output.section_cut import next_section_name
    app = QApplication.instance() or QApplication([])
    doc,tid,sid = fixture()
    for i in range(40):
        doc.add(Entity('section_line',dict(x1=0.,y1=0.,x2=10.,y2=10.,flip=0),name=next_section_name(doc)))
    w = QMainWindow(); w.doc = doc; w.stack = CommandStack(doc)
    draws=[]; w._redraw_views=lambda **kwargs: draws.append(kwargs)
    editor = TerrainProfileDialog(w,sid)
    editor.show(); app.processEvents()
    assert editor.sections.count() == 41
    editor.table.selectRow(0)
    assert not editor.apply.isEnabled() and not editor.delete.isEnabled()
    editor.distance.setValue(7.); editor.elevation.setValue(4.); editor.add.click()
    assert len(w.stack.done)==1 and terrain_height_at(doc,5.,2.)==pytest.approx(4.)
    assert len(doc.get(tid).params['points'])==1
    editor.refresh(fit=True); app.processEvents()
    start = editor.plot.mapFromScene(QPointF(7.,4.))
    end = editor.plot.mapFromScene(QPointF(8.,5.))
    before=copy.deepcopy(doc.to_dict())
    QTest.mousePress(editor.plot.viewport(),Qt.MouseButton.LeftButton,pos=start)
    QTest.mouseMove(editor.plot.viewport(),end)
    assert doc.to_dict()==before                          # preview owns no model state
    QTest.keyClick(editor.plot,Qt.Key.Key_Escape)
    assert doc.to_dict()==before and len(w.stack.done)==1
    QTest.mousePress(editor.plot.viewport(),Qt.MouseButton.LeftButton,pos=start)
    QTest.mouseMove(editor.plot.viewport(),end)
    QTest.mouseRelease(editor.plot.viewport(),Qt.MouseButton.LeftButton,pos=end)
    assert len(w.stack.done)==2
    assert len(doc.get(tid).params['profile_controls'])==1
    assert draws
    w.stack.undo()
    assert doc.to_dict()==before
    editor.close(); QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
    assert editor._listener not in w.stack.listeners
    w.close()


def test_existing_section_button_opens_editor_and_updates_3d_and_section_from_the_same_terrain():
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.section_view import open_section
    from archforge.core.commands import AddEntity
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    doc,tid,sid = fixture()
    for entity in doc.entities.values(): w.stack.execute(AddEntity(entity))
    open_section(w,sid)
    w._section_panel.terrain_profile.click()
    editor = w._terrain_profile_dialog
    assert editor.isVisible()
    before = len(w.stack.done)
    assert editor.commit(7.,4.)
    assert len(w.stack.done)==before+1
    evaluation = w.pbr_view._evaluation_cache.sync(w.doc)
    from archforge.rendering.scene import build_pbr_scene_payload
    payload = build_pbr_scene_payload(evaluation,[],doc=w.doc)
    obj = next(o for o in payload['objects'] if o['kind']=='terrain')
    assert any(abs(v[0]-5.)<1e-7 and abs(v[1]-2.)<1e-7 and abs(v[2]-4.)<1e-7 for v in obj['vertices'])
    w._section_panel.refresh()
    assert any(abs(z-4.)<1e-5 for _u,z in w._section_panel.view.data['terrain_marks'])
    w.stack.undo()
    assert not w.doc.get(tid).params.get('profile_controls')
    editor.close(); w._mark_clean(); w.close(); app.processEvents()
