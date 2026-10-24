"""Actual Qt and scene QA, synthetic coincident loads; not an installation study."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def render(folder):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QRectF,Qt
    from archforge.ui.main_window import MainWindow
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    app=QApplication.instance() or QApplication([]);w=MainWindow();folder.mkdir(parents=True,exist_ok=True)
    fig=plt.figure(figsize=(13,6),dpi=140)
    try:
        w.stack.execute(AddEntity(Entity('wall',dict(x1=0,y1=0,x2=6,y2=0,z=0,height=3,thickness=.2))))
        for typ,x in [('panel',0),('cooker',5),('cooker',5)]:
            params=dict(x=x,y=0,z=0,point_type=typ)
            if typ=='panel':params.update(conduit_fill_limit=.30,conduit_max_dn=32,conduit_profile='conflex')
            w.stack.execute(AddEntity(Entity('electrical_point',params,name='Συνθετική δοκιμή '+typ)))
        tab=w._board_tab;tab.refresh();tab.pages.setCurrentWidget(tab.conduits)
        tab.resize(1150,950);tab.show();app.processEvents()
        for i,maximum in enumerate((32,40),1):
            index=tab.pipe_max.findData(maximum);tab.pipe_max.setCurrentIndex(index);tab.pipe_max.activated.emit(index)
            app.processEvents()
            tab.technical_plan.fitInView(QRectF(-.4,-.7,6,1.7),Qt.AspectRatioMode.KeepAspectRatio)
            tab.technical_plan._update_label_visibility()
            tab.grab().save(str(folder/f'board_max_{maximum}.png'))
            result=tab.result['conduit_map']
            scene=build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(w.doc),[],doc=w.doc)
            ax=fig.add_subplot(1,2,i,projection='3d')
            for obj in scene['objects']:
                if obj.get('kind') not in ('elec_cable','elec_box'):continue
                polygons=[[obj['vertices'][j] for j in tri] for tri in obj['triangles']]
                ax.add_collection3d(Poly3DCollection(polygons,facecolors=obj['material']['color'],edgecolors='none'))
            ax.set(xlim=(-.2,5.5),ylim=(-.2,.6),zlim=(0,2.7),xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)')
            ax.set_yticks([0,.3,.6]);ax.set_box_aspect((5.7,.8,2.7));ax.view_init(elev=23,azim=-58)
            fills=sorted({round(p['fill']*100,1) for p in result['pieces']})
            text=' / '.join(f'{p:g}%' for p in fills)
            ax.set_title(f"Μέγιστο Φ{maximum}: σωληνώσεις {result['conduits']}\nπλήρωση {text} / όριο 30%",pad=15)
        fig.suptitle('Ίδιες δύο γραμμές · διαφορετική επιτρεπόμενη διάμετρος')
        fig.text(.5,.035,'Πραγματικά meshes ArchForge · συνθετική δοκιμή · ονομαστικές διαστάσεις προϊόντων, όχι έγκριση εγκατάστασης.',ha='center',fontsize=9)
        fig.subplots_adjust(left=.03,right=.94,top=.80,bottom=.13,wspace=.18)
        fig.savefig(folder/'diameter_and_count.png')
    finally:
        plt.close(fig);w._mark_clean();w.close();app.processEvents()


if __name__=='__main__':
    render(Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/media/conduit-fill'))
