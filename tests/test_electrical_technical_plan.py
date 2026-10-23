"""The owner wants the electrical report to work like the hydraulic technical tab."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from archforge.core.commands import AddEntity,UpdateEntity
from archforge.core.model import Document,Entity


def test_board_has_live_technical_plan_conduits_and_existing_wired_front():
    from archforge.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([])
    w=MainWindow()
    try:
        w.stack.execute(AddEntity(Entity('wall',dict(x1=0,y1=0,x2=6,y2=0,z=0,height=2.7,thickness=.2))))
        for typ,x in [('panel',.2),('cooker',3),('cooker',5)]:
            w.stack.execute(AddEntity(Entity('electrical_point',dict(x=x,y=0,z=0,point_type=typ))))
        tab=w._board_tab; r=tab.refresh()
        assert tab.minimumSizeHint().width() <= 1150
        assert tab.technical_plan.doc is w.doc and tab.technical_plan.stack is w.stack
        assert tab.front_view.front is r['front']
        assert tab.conduits.topLevelItemCount()==len(r['conduit_map']['pieces'])
        assert any(tab.pages.tabText(i)=='Σωληνώσεις και καλωδιώσεις' for i in range(tab.pages.count()))
        cid=r['circuits'][0]['id']; assert tab._select_circuit(cid)
        assert tab.technical_plan.doc.selection==w.doc.selection
        assert any(item.data(1) is True for item in tab.technical_plan.scene().items())
        before=w.doc.to_dict(); tab.technical_plan.redraw(); assert w.doc.to_dict()==before
        tab.technical_plan.resize(900,340)
        assert not tab.technical_plan.grab().isNull()
        replacement=Document()
        w._replace_project(replacement)
        tab.refresh()
        assert tab.technical_plan.doc is replacement and tab.technical_plan.stack is w.stack
        assert tab.mark_stale in w.stack.listeners
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_board_wiring_detail_uses_actual_circuit_conductors_and_its_own_neutral_bar():
    from archforge.core.commands import CommandStack
    from archforge.mep.electrical_board import analyse,front
    from archforge.ui.board_front_view import BoardFrontView
    app=QApplication.instance() or QApplication([])
    doc=Document();stack=CommandStack(doc)
    panel=Entity('electrical_point',dict(x=0,y=0,z=0,point_type='panel'))
    stack.execute(AddEntity(panel))
    stack.execute(AddEntity(Entity('electrical_point',dict(x=2,y=0,z=0,point_type='cooker'))))
    r=analyse(doc);cid=r['circuits'][0]['id']
    stack.execute(UpdateEntity(panel.id,{'rcd_groups':{cid:2}}))
    r=analyse(doc);f=front(r)
    output=next(p for p in f['outputs'] if p['circuit']==cid)
    assert output['conductors']==r['circuits'][0]['conductors']
    assert output['neutral_bar']=='N Δ2'
    assert output['point_ids']==r['circuits'][0]['point_ids']
    view=BoardFrontView();view.set_front(f);view.set_circuit(cid)
    assert view.selected_circuit==cid
    view.resize(view.minimumSize());assert not view.grab().isNull()
    view.close();app.processEvents()
