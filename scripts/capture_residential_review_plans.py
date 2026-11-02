import os,json,sys
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF,Qt
from archforge.project.persistence import load_project
from archforge.core.model import WorkPlane
from archforge.core.commands import CommandStack
from archforge.ui.plan_view import PlanView
root=Path(__file__).resolve().parents[1];out=root/'docs/scenarios/residential_review/plans';out.mkdir(exist_ok=True)
app=QApplication([]);specs=json.loads((root/'tests/residential_scenarios/manifest.json').read_text())
for s in specs:
 p=root/('docs/scenarios/foundation_review/S01_strip_comparison.archforge' if s['id']=='S01' else 'tests/residential_scenarios/'+s['file']);r=load_project(p);assert r.ok;doc=r.doc
 for i,(level,z) in enumerate(sorted(doc.levels.items(),key=lambda x:x[1])):
  doc.work_plane=WorkPlane(name=level,origin=(0,0,float(z)),u=(1,0,0),v=(0,1,0))
  view=PlanView(doc,CommandStack(doc));view.resize(1100,800);view.show();app.processEvents()
  walls=[e for e in doc.entities.values() if e.kind=='wall' and abs(e.params['z']-z)<.01];xs=[e.params[k] for e in walls for k in ('x1','x2')];ys=[e.params[k] for e in walls for k in ('y1','y2')]
  if xs:view.fitInView(QRectF(min(xs)-2,min(ys)-2,max(xs)-min(xs)+4,max(ys)-min(ys)+4),Qt.AspectRatioMode.KeepAspectRatio)
  app.processEvents();path=out/f"{s['id']}_plan_{i}.png";assert view.grab().save(str(path));view.close();view.deleteLater();app.processEvents()
 print(s['id'],'plans',len(doc.levels),flush=True)
