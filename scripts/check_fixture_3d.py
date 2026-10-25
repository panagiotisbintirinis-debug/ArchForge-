"""Synthetic UI check on the Windows runner: real WebGL, double-click, rotors and dimming.

All dimensions/values here are test fixtures, not installation or photometry advice.
Run in a desktop Qt session (not QT_QPA_PLATFORM=offscreen).
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDial, QSlider

from archforge.ui.app import MainWindow
from archforge.ui import pbr_viewport
from archforge.core.commands import AddEntity
from archforge.core.model import Document, Entity
from archforge.library.bundled_lights import seed_lights
from archforge.library.assets import load_asset
from archforge.mep.lighting import replace_fixture


def main():
    app=QApplication.instance() or QApplication([])
    # Test-only access to the actual embedded renderer, no separate rendering implementation.
    probe='''
window.__fixtureQA = () => ({ready:true,on:archLightRoot.visible,
  aim:archLightRoot.children.filter(x=>x.isSpotLight).map(x=>[...x.position.toArray(),...x.target.position.toArray()]),
  parts:modelRoot.children.filter(x=>x.userData.kind === 'electrical_point').length});
window.__fixturePick = function(eid) {
  const ray=new THREE.Raycaster(), v=new THREE.Vector3();
  for (const mesh of modelRoot.children.filter(m=>m.userData.entityId===eid)) {
    const pos=mesh.geometry.getAttribute('position'), ix=mesh.geometry.index;
    for(let i=0;i<(ix?ix.count:pos.count);i+=3) {
      v.set(0,0,0);
      for(let k=0;k<3;k++)v.add(new THREE.Vector3().fromBufferAttribute(pos,ix?ix.getX(i+k):i+k));
      v.multiplyScalar(1/3).project(camera);if(Math.abs(v.x)>1||Math.abs(v.y)>1)continue;
      ray.setFromCamera(new THREE.Vector2(v.x,v.y),camera);
      const hit=ray.intersectObjects(modelRoot.children,false)[0];
      if(hit&&hit.object.userData.entityId===eid)return [(v.x+1)*renderer.domElement.clientWidth/2,
         (1-v.y)*renderer.domElement.clientHeight/2];
    }
  }
  return null;
};
'''
    anchor='requestAnimationFrame(animate);\n</script>'
    assert anchor in pbr_viewport._PBR_HTML
    pbr_viewport._PBR_HTML=pbr_viewport._PBR_HTML.replace(anchor,probe+anchor,1)
    w=MainWindow();w.resize(1400,1000);w.show()
    try:
        w._seed_core_library()
        from archforge.library.assets import list_assets
        records=[load_asset(r['id']) for r in list_assets() if r.get('lit')]
        projector=next(r for r in records if r.get('light_capabilities',{}).get('aimable'))
        doc=Document();floor=Entity('box',dict(x=0,y=0,z=-.1,width=6,depth=6,height=.1,rotation=0))
        doc.add(floor)
        lamp=Entity('electrical_point',dict(x=0,y=0,z=0,point_type='spot',power_w=0,
                    mount_height=1.2,light_on=1,dim_level=1,aim_tilt_deg=45,aim_azimuth_deg=0))
        doc.add(lamp);w._replace_project(doc)
        cmd,_=replace_fixture(w.doc,lamp.id,'library',projector['id']);w.stack.execute(cmd)
        w._central_tabs.setCurrentIndex(1);w._mockup_right_tabs.setCurrentWidget(w.pbr_view)
        w.pbr_view.activate()
        assert w.pbr_view.web_view is not None,'Qt WebEngine is unavailable'

        def js(source):
            values=[];w.pbr_view.web_view.page().runJavaScript(source,lambda x:values.append(x))
            until=time.monotonic()+5
            while not values and time.monotonic()<until:QTest.qWait(25)
            return values[0] if values else None

        deadline=time.monotonic()+60
        while not js('Boolean(window.__fixtureQA)') and time.monotonic()<deadline:QTest.qWait(100)
        assert js('Boolean(window.__fixtureQA)'),'The real WebGL page did not initialize'
        w.pbr_view.set_lighting_mode('night');QTest.qWait(1000)
        state=json.loads(js('JSON.stringify(window.__fixtureQA())'))
        assert state['parts'] and state['aim'] and state['on'],state
        pick=json.loads(js('JSON.stringify(window.__fixturePick('+json.dumps(lamp.id)+'))'))
        assert pick,'Could not locate a visible triangle of the actual fixture'
        target=w.pbr_view.web_view.focusProxy() or w.pbr_view.web_view
        point=target.mapFrom(w.pbr_view.web_view,QPoint(round(pick[0]),round(pick[1])))
        QTest.mouseDClick(target,Qt.LeftButton,Qt.NoModifier,point)
        QTest.qWait(250)
        assert w.doc.selection==[lamp.id],'Double-click did not select the native electrical fixture'
        rotor=w.form.parentWidget().findChild(QDial,'aimBearing')
        assert rotor is not None,'The selected 3D fixture has no rotation control'
        before=w.doc.to_dict()
        rotor.setSliderDown(True);rotor.setValue(90);QTest.qWait(400)
        assert w.doc.to_dict()==before,'A live rotor preview changed the project'
        steered=json.loads(js('JSON.stringify(window.__fixtureQA())'))
        assert steered['aim']!=state['aim'],'The actual Three.js beam did not turn'
        rotor.setSliderDown(False);QTest.qWait(250)
        assert w.doc.get(lamp.id).params['aim_azimuth_deg']==90
        slider=w.form.parentWidget().findChild(QSlider)
        assert slider is not None and slider.orientation()==Qt.Horizontal
        bright=w.pbr_view.web_view.grab().toImage()
        slider.setSliderDown(True);slider.setValue(0);QTest.qWait(700)
        dark=w.pbr_view.web_view.grab().toImage()
        assert not json.loads(js('JSON.stringify(window.__fixtureQA())'))['aim'],'Dimmed fixture still emits light'
        assert bright!=dark,'Rendered pixels did not change when dimmed to zero'
        assert w.doc.get(lamp.id).params['dim_level']==1,'The dimmer preview changed the project'
        slider.setSliderDown(False);QTest.qWait(200)
        assert w.doc.get(lamp.id).params['dim_level']==0
        w.stack.undo();assert w.doc.get(lamp.id).params['dim_level']==1
        w.stack.undo();assert w.doc.get(lamp.id).params['aim_azimuth_deg']==0
        print('PASS: real WebGL fixture, double-click properties, live rotor, visible dimming and one Undo per gesture')
    finally:
        w._mark_clean();w.close();app.processEvents()


if __name__=='__main__':main()
