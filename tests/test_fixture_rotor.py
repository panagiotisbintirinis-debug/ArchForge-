import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX','1')

from PySide6.QtWidgets import QApplication, QDial, QLabel, QDoubleSpinBox, QSlider
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from archforge.ui.main_window import MainWindow
from archforge.core.commands import CommandStack
from archforge.core.model import Document
from tests.test_electrical import _pt


def test_rotor_previews_without_mutating_document_then_commits_one_undo():
    from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
    from archforge.ui.lighting_system import install_lighting_system
    install_rendering_quality_upgrade();install_lighting_system()
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    try:
        doc=Document();stack=CommandStack(doc)
        lamp=_pt(stack,'spot',2,3,aim_tilt_deg=60,aim_azimuth_deg=0)
        other=_pt(stack,'spot',5,3)
        w._replace_project(doc);w.doc.select([lamp.id]);w.refresh_inspector()
        form=w.form.parentWidget()
        rotor=form.findChild(QDial,'aimBearing')
        assert rotor is not None
        assert form.findChild(QDoubleSpinBox,'aimBearing') is None
        before=w.doc.to_dict()
        rotor.setSliderDown(True);rotor.setValue(90)
        assert w.doc.to_dict()==before
        assert w.pbr_view._fixture_control_preview is not None
        spec=next(s for s in w.pbr_view._lighting_payload()['lights'] if s['id']==lamp.id)
        assert spec['target'][0]>spec['position'][0]
        assert form.findChild(QLabel,'aimBearingValue').text()=='90°'
        rotor.setSliderDown(False)
        assert w.doc.get(lamp.id).params['aim_azimuth_deg']==90
        assert w.doc.get(other.id).params==other.params
        assert w.pbr_view._fixture_control_preview is None
        w.stack.undo();assert w.doc.get(lamp.id).params['aim_azimuth_deg']==0
        w.refresh_inspector()
        rotor=w.form.parentWidget().findChild(QDial,'aimBearing')
        rotor.setSliderDown(True);rotor.setValue(180)
        QTest.keyClick(rotor,Qt.Key_Escape)
        assert w.doc.get(lamp.id).params['aim_azimuth_deg']==0
        assert rotor.value()==0 and w.pbr_view._fixture_control_preview is None
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_rotor_mouse_compass():
    from archforge.ui.fixture_controls import CompassDial
    app=QApplication.instance() or QApplication([])
    rotor=CompassDial();rotor.resize(80,80);rotor.show()
    point=QPoint(rotor.width()-6,rotor.height()//2)
    QTest.mousePress(rotor,Qt.LeftButton,Qt.NoModifier,point)
    assert abs(rotor.value()-90)<=1
    QTest.mouseRelease(rotor,Qt.LeftButton,Qt.NoModifier,point)
    assert not rotor.isSliderDown()
    rotor.close()


def test_horizontal_dimmer_previews_and_cancels_without_committing():
    from archforge.ui.rendering_quality_upgrade import install_rendering_quality_upgrade
    from archforge.ui.lighting_system import install_lighting_system
    install_rendering_quality_upgrade();install_lighting_system()
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    try:
        doc=Document();stack=CommandStack(doc);lamp=_pt(stack,'spot',1,2,dim_level=1)
        w._replace_project(doc);w.doc.select([lamp.id]);w.refresh_inspector()
        slider=w.form.parentWidget().findChild(QSlider)
        assert slider.orientation()==Qt.Horizontal
        before=w.doc.to_dict()
        slider.setSliderDown(True);slider.setValue(40)
        assert w.doc.to_dict()==before
        payload=w.pbr_view._lighting_payload()
        assert payload['glow_levels'][lamp.id]==0.4
        assert payload['lights'][0]['dimmer']==0.4
        QTest.keyClick(slider,Qt.Key_Escape)
        assert w.doc.to_dict()==before and slider.value()==100
        assert w.pbr_view._fixture_control_preview is None
        slider.setSliderDown(True);slider.setValue(25);slider.setSliderDown(False)
        assert w.doc.get(lamp.id).params['dim_level']==.25
        w.stack.undo();assert w.doc.get(lamp.id).params['dim_level']==1
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_3d_selection_opens_rotors_for_bound_electrical_fixture_in_architecture(tmp_path,monkeypatch):
    from archforge.library.bundled_lights import seed_lights
    from archforge.library.assets import load_asset
    from archforge.mep.lighting import replace_fixture
    monkeypatch.setenv('ARCHFORGE_DATA',str(tmp_path))
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        r=next(load_asset(aid) for aid in seed_lights() if load_asset(aid)['light_capabilities']['aimable'])
        doc=Document();stack=CommandStack(doc);lamp=_pt(stack,'spot',1,2)
        cmd,_=replace_fixture(doc,lamp.id,'library',r['id']);stack.execute(cmd)
        w._replace_project(doc)
        w.pbr_view._select_entity_from_web(lamp.id);app.processEvents()
        assert w.doc.selection==[lamp.id]
        assert w.form.parentWidget().findChild(QDial,'aimBearing') is not None
    finally:
        w._mark_clean();w.close();app.processEvents()
