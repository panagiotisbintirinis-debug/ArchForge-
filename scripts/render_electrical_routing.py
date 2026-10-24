"""Actual UI/scene QA for owner routing choices; synthetic software fixture."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity


def fixture(w):
    for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4)),((0,4),(0,0))]:
        w.stack.execute(AddEntity(Entity('wall', dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],z=0,height=3,thickness=.2))))
    for kind,x,y in [('panel',0,0),('cooker',5,4),('network_rack',0,0),('data_outlet',5,4)]:
        w.stack.execute(AddEntity(Entity('electrical_point',dict(x=x,y=y,z=0,point_type=kind))))
    light=Entity('electrical_point',dict(x=2,y=2,z=0,point_type='light'),name='Δοκιμή φωτιστικού')
    w.stack.execute(AddEntity(light))
    return light.id


def render(folder):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    folder.mkdir(parents=True,exist_ok=True)
    fig=plt.figure(figsize=(18,7),dpi=130)
    try:
        light=fixture(w)
        for i,(mode,label) in enumerate([('floor','Δάπεδο'),('ceiling','Οροφή'),('wall','Περιμετρικά')],1):
            for e in list(w.doc.entities.values()):
                if e.kind=='electrical_point' and e.params['point_type'] not in ('panel','network_rack'):
                    w.stack.execute(UpdateEntity(e.id,{'routing':mode}))
            scene=build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(w.doc),[],doc=w.doc)
            ax=fig.add_subplot(1,3,i,projection='3d')
            for obj in scene['objects']:
                if obj.get('kind') not in ('elec_cable','lv_cable','elec_box'):continue
                polygons=[[obj['vertices'][j] for j in tri] for tri in obj['triangles']]
                ax.add_collection3d(Poly3DCollection(polygons,facecolors=obj['material']['color'],edgecolors='none'))
            for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4)),((0,4),(0,0))]:
                ax.plot([a[0],b[0]],[a[1],b[1]],[0,0],color='#aaaaaa',linewidth=1)
            ax.set(xlim=(-.3,5.3),ylim=(-.3,4.3),zlim=(0,3.2),xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)',title=label)
            ax.set_box_aspect((5.6,4.6,3.2));ax.view_init(elev=23,azim=-55)
            if mode=='ceiling':
                w.doc.select([light]);w.refresh_inspector();w.inspector.resize(560,900)
                app.processEvents();w.inspector.grab().save(str(folder/'inspector.png'))
        fig.suptitle('Δοκιμή λογισμικού: η επιλογή αλλάζει την πραγματική διαδρομή')
        fig.text(.5,.025,'Πραγματικά meshes του ArchForge · ισχυρά και χωριστά ασθενή · συνθετικό τεστ, όχι μελέτη εγκατάστασης.',ha='center',fontsize=10)
        fig.subplots_adjust(left=.01,right=.94,bottom=.15,top=.86,wspace=.2);fig.savefig(folder/'routing_modes.png')
    finally:
        plt.close(fig);w._mark_clean();w.close();app.processEvents()


if __name__=='__main__':
    render(Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/media/electrical-routing'))
