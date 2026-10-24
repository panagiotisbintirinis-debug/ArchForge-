"""Actual Qt QA for #150. Synthetic software fixture; no market/study figures."""
import os
import sys
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX','1')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def render(folder):
    import copy
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication,QDialogButtonBox,QLabel,QLineEdit,QComboBox
    from archforge.ui.main_window import MainWindow
    from archforge.core.model import Document,Entity
    from archforge.core.commands import AddEntities,UpdateEntity
    from archforge.mep import electrical_takeoff as E
    from archforge.mep.project_pricebook import set_project_prices
    from archforge.mep.trade_costing import PriceEntry
    app=QApplication.instance() or QApplication([]);w=MainWindow();folder.mkdir(parents=True,exist_ok=True)
    try:
        entities=[]
        for a,b in [((0,0),(6,0)),((6,0),(6,4)),((6,4),(0,4)),((0,4),(0,0))]:
            entities.append(Entity('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],z=0,height=3,thickness=.2)))
        for typ,x,y in [('panel',.3,2),('socket',.3,1),('socket',5.7,3),('light',2,2),('switch',.3,1.8),
                        ('cooker',5.7,1),('kitchen_socket',3,2),('network_rack',.3,2.5),('data_outlet',5.7,2.5)]:
            entities.append(Entity('electrical_point',dict(point_type=typ,x=x,y=y,z=0),name='Συνθετική δοκιμή '+typ))
        w.stack.execute(AddEntities(entities));panel=E.panel(w.doc)
        w.stack.execute(UpdateEntity(panel.id,{
            'electrical_box_defaults':{k:'Μοντέλο δοκιμής Α' for k in E.BOX_LABELS},
            'electrical_item_specs':{k:'Προδιαγραφή δοκιμής — όχι πραγματική μελέτη' for k in E.STUDY_ITEMS},
            'electrical_quantity_inputs':{'electrical.rcd':2,'electrical.panel_enclosure':1}}))
        w._electrical_analysis_action.trigger();tab=w._board_tab;page=tab.takeoff_page
        tab.setParent(None);tab.resize(1320,1120)
        banner=QLabel('ΣΥΝΘΕΤΙΚΗ ΔΟΚΙΜΗ ΛΟΓΙΣΜΙΚΟΥ · μοντέλα και τιμές δοκιμής, όχι προσφορά ή μελέτη εγκατάστασης')
        banner.setWordWrap(True);banner.setStyleSheet('background:#fff3cd;color:#614800;padding:6px;font-weight:600')
        tab.layout().insertWidget(0,banner);tab.show();app.processEvents()
        # Real modal form, entered through Qt controls; one persistent owner item.
        def extra_form():
            dialog=app.activeModalWidget();fields=dialog.findChildren(QLineEdit)
            for field,text in zip(fields,['Δοκιμαστικό πρόσθετο Α — όχι πραγματικό υλικό','τεμ.','3']):field.setText(text)
            combo=dialog.findChild(QComboBox);combo.setCurrentIndex(combo.findData('floor'))
            QTest.mouseClick(dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok),Qt.MouseButton.LeftButton)
        QTimer.singleShot(0,extra_form);page._edit_extra();app.processEvents()
        assert len(E.panel(w.doc).params['electrical_extra_items'])==1
        page.profiles['ceiling'].setCurrentIndex(page.profiles['ceiling'].findData('superflex_plus'))
        comparison=E.compare_routing(w.doc,{'ceiling':'superflex_plus'})
        prices={x['code']:PriceEntry(material_unit_price=1,labour_unit_price=0)
                for data in comparison.values() for x in data['rows']}
        prices.update({x['code']:PriceEntry(material_unit_price=1,labour_unit_price=0) for x in E.takeoff(w.doc)['rows']})
        set_project_prices(w.stack,w.doc,prices)
        # Actual price modal with Enter. The dialog returns before table regeneration.
        row=next(i for i,x in enumerate(page.row_data) if x['code'].startswith('electrical.conduit.'))
        def price_form():
            dialog=app.activeModalWidget();field=dialog.findChild(QLineEdit);field.setText('2,50');QTest.keyClick(field,Qt.Key.Key_Return)
        before=copy.deepcopy(w.doc.to_dict());QTimer.singleShot(0,price_form);page.table.cellDoubleClicked.emit(row,3)
        app.processEvents();w.stack.undo();assert w.doc.to_dict()==before
        page.mode.setCurrentIndex(page.mode.findData('floor'));app.processEvents()
        tab.technical_plan.fit_content()
        page.tabs.setCurrentIndex(0);app.processEvents();tab.grab().save(str(folder/'quantities.png'))
        page.tabs.setCurrentIndex(1);app.processEvents();tab.grab().save(str(folder/'boxes.png'))
        page.tabs.setCurrentIndex(2);page.calculate_comparison();app.processEvents()
        assert page.comparison['floor']['complete'] and page.comparison['ceiling']['complete']
        tab.grab().save(str(folder/'comparison.png'))
        # Preview -> real button -> authoritative state -> undo, then save/load.
        page.mode.setCurrentIndex(page.mode.findData('ceiling'));before=copy.deepcopy(w.doc.to_dict())
        QTest.mouseClick(page.apply,Qt.MouseButton.LeftButton);app.processEvents()
        assert w.doc.to_dict()==page.preview_doc.to_dict()
        assert E.takeoff(Document.from_dict(w.doc.to_dict()))==E.takeoff(w.doc)
        w.stack.undo();assert w.doc.to_dict()==before
        print('Qt price/extra dialogs, comparison, apply/undo and save/load passed. Screenshots:',folder)
    finally:
        tab=getattr(w,'_board_tab',None)
        if tab:tab.hide()
        w._mark_clean();w.close();app.processEvents()


if __name__=='__main__':
    render(Path(sys.argv[1]) if len(sys.argv)>1 else Path('docs/media/electrical-takeoff'))
