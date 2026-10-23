"""Static QA view of actual scene meshes, not a building/electrical study."""
import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from types import SimpleNamespace
from archforge.core.model import Document
from archforge.core.commands import CommandStack
from archforge.geometry.incremental import IncrementalEvaluationCache
from archforge.geometry.sculpt import SculptedPreviewBackend
from archforge.rendering.scene import build_pbr_scene_payload
from scripts.render_electrical_conduits import make_fixture


def render(path):
    doc=Document();make_fixture(SimpleNamespace(stack=CommandStack(doc)))
    scene=build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc),[],doc=doc)
    fig=plt.figure(figsize=(12,7),dpi=150)
    ax=fig.add_subplot(111,projection='3d')
    for obj in scene['objects']:
        if obj.get('kind') not in ('elec_cable','lv_cable','elec_box'):continue
        vertices=obj['vertices']
        polygons=[[vertices[i] for i in tri] for tri in obj['triangles']]
        ax.add_collection3d(Poly3DCollection(polygons,facecolors=obj['material']['color'],edgecolors='none'))
    ax.set(xlim=(-.2,5.6),ylim=(-.15,.55),zlim=(.1,2.7),xlabel='X (m)',ylabel='Y (m)',zlabel='Z (m)')
    ax.set_box_aspect((5.8,.7,2.6));ax.view_init(elev=22,azim=-58)
    ax.set_yticks([0,.25,.5])
    ax.set_title('Δοκιμή λογισμικού: δύο σωληνώσεις ισχυρών και ασθενή επάνω',pad=24)
    fig.text(.5,.025,'Γεωμετρία από το 3D του ArchForge · σχηματικός διαχωρισμός σειρών, όχι συντεταγμένες εγκατάστασης.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,1));path.parent.mkdir(parents=True,exist_ok=True);fig.savefig(path);plt.close(fig)


if __name__=='__main__':
    path=Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/media/electrical-conduits/conduits_3d.png')
    render(path);print(path)
