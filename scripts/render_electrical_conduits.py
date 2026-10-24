"""QA captures of a synthetic wiring fixture; not a construction/electrical study."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QRectF,Qt
from PySide6.QtWidgets import QApplication
from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.ui.main_window import MainWindow


def make_fixture(window):
    window.stack.execute(AddEntity(Entity('wall',dict(x1=0,y1=0,x2=6,y2=0,z=0,height=2.7,thickness=.2))))
    for typ,x,name in [('panel',.2,'Δοκιμή πίνακα'),('cooker',3,'Δοκιμή γραμμής 1'),
                       ('cooker',5,'Δοκιμή γραμμής 2'),('network_rack',.2,'Δοκιμή rack'),('data_outlet',5,'Δοκιμή RJ45')]:
        params=dict(x=x,y=0,z=0,point_type=typ)
        if typ=='panel': params['supply_phases']=1 # synthetic user input, not an engineering recommendation
        window.stack.execute(AddEntity(Entity('electrical_point',params,name=name)))


if __name__=='__main__':
    app=QApplication.instance() or QApplication([])
    folder=Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/media/electrical-conduits')
    folder.mkdir(parents=True,exist_ok=True)
    window=MainWindow()
    try:
        make_fixture(window)
        tab=window._board_tab;tab.refresh()
        tab.resize(1150,1000);tab.show();app.processEvents()
        tab.technical_plan.fitInView(QRectF(-.5,-.65,7,1.6),Qt.AspectRatioMode.KeepAspectRatio)
        tab.technical_plan._update_label_visibility()
        tab.grab().save(str(folder/'electrical_tab.png'))
        tab.technical_plan.setParent(None)
        tab.technical_plan.resize(1200,420);tab.technical_plan.show();app.processEvents()
        tab.technical_plan.fitInView(QRectF(-.5,-.65,7,1.6),Qt.AspectRatioMode.KeepAspectRatio)
        tab.technical_plan._update_label_visibility()
        tab.technical_plan.grab().save(str(folder/'technical_plan.png'))
        tab.front_view.setParent(None)
        tab.front_view.resize(tab.front_view.minimumSize());tab.front_view.show();app.processEvents()
        tab.front_view.grab().save(str(folder/'board_front.png'))
        tab.conduits.setParent(None)
        tab.conduits.resize(1200,300);tab.conduits.show();app.processEvents()
        tab.conduits.grab().save(str(folder/'conduit_schedule.png'))
        print(folder)
    finally:
        for widget in (window._board_tab.technical_plan,window._board_tab.front_view,window._board_tab.conduits):widget.close()
        window._board_tab.close()
        window._mark_clean();window.close();app.processEvents()
