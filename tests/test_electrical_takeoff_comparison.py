"""Owner #150: one electrical quantity/price path, read-only alternatives."""
import copy
import math
import pytest
from archforge.core.commands import CommandStack, UpdateEntity
from archforge.core.model import Document
from tests.test_electrical_board import _flat


def test_preview_and_apply_share_state_with_one_undo_and_persistence():
    from archforge.mep.electrical_takeoff import routing_preview, apply_routing, takeoff
    from archforge.mep.electrical import route_cables
    doc=Document(); stack=CommandStack(doc); _flat(stack)
    before=copy.deepcopy(doc.to_dict()); n=len(stack.done)
    floor=routing_preview(doc,'floor'); ceiling=routing_preview(doc,'ceiling','superflex_plus')
    assert doc.to_dict()==before and len(stack.done)==n
    assert route_cables(floor)['runs']!=route_cables(ceiling)['runs']
    apply_routing(doc,stack,'ceiling','superflex_plus')
    assert len(stack.done)==n+1 and doc.to_dict()==ceiling.to_dict()
    assert takeoff(Document.from_dict(doc.to_dict()))==takeoff(ceiling)
    stack.undo(); assert doc.to_dict()==before
    stack.redo(); assert doc.to_dict()==ceiling.to_dict()


def test_boxes_group_by_explicit_model_without_invented_sizes():
    from archforge.mep.electrical_takeoff import box_inventory, measured_rows
    doc=Document(); stack=CommandStack(doc); panel=_flat(stack)
    boxes=box_inventory(doc)
    assert boxes and all(not b['spec'] for b in boxes)
    assert len({b['key'] for b in boxes})==len(boxes)
    stack.execute(UpdateEntity(panel.id,{
        'electrical_box_defaults': {k:'Owner fixture model A' for k in ('junction','floor','pull','lv')},
        'electrical_box_specs': {boxes[0]['key']:'Owner fixture model B'}}))
    rows=[r for r in measured_rows(doc) if r[3]['code'].startswith('electrical.box.')]
    assert sum(r[2] for r in rows)==len(boxes)
    assert any('model B' in r[0] and r[2]==1 for r in rows)
    assert all(r[3]['specified'] for r in rows)
    assert box_inventory(Document.from_dict(doc.to_dict()))==box_inventory(doc)
    stack.undo(); assert all(not b['spec'] for b in box_inventory(doc))


def test_split_nodes_do_not_duplicate_existing_power_box_and_lv_stays_separate(monkeypatch):
    from archforge.mep import electrical,conduits,low_voltage
    from archforge.mep.electrical_takeoff import box_inventory
    monkeypatch.setattr(electrical,'route_cables_cached',lambda d:{'boxes':[(1,2,3,'junction','C1')]})
    monkeypatch.setattr(conduits,'conduit_map',lambda d:{'split_boxes':[(1,2,3),(4,5,6)]})
    monkeypatch.setattr(low_voltage,'route_low_voltage_cached',lambda d:{'boxes':[(1,2,3,'lv','D1')]})
    nodes=box_inventory(Document())
    assert len(nodes)==3 and sum(x['kind']=='lv' for x in nodes)==1


def test_quantities_use_shared_quote_and_conserve_pipe_polyline_lengths():
    from archforge.mep.electrical_takeoff import takeoff
    from archforge.mep.conduits import conduit_map
    from archforge.quantities.materials import electrical_list
    from archforge.quantities.quote import costed
    doc=Document(); stack=CommandStack(doc); _flat(stack)
    data=takeoff(doc)
    assert data['rows']==costed(doc,'Ηλεκτρολογικά',electrical_list(doc))
    assert not data['complete'] and data['total'] is None and data['missing']
    pipes=[r for r in data['rows'] if r['code'].startswith('electrical.conduit.')]
    assert all('.conflex.' in r['code'] or '.geonflex.' in r['code'] for r in pipes)
    expected=sum(math.dist(a,b)*p['count'] for p in conduit_map(doc)['pieces'] for a,b in zip(p['points'],p['points'][1:]))
    assert sum(r['quantity'] for r in pipes)==pytest.approx(expected,abs=.01*len(pipes))
    assert any('H07V-' in r['description'] for r in data['rows'] if r['code'].startswith('electrical.cable.'))


def test_complete_amount_needs_specs_quantities_and_both_prices_not_compliance():
    from archforge.mep.electrical_takeoff import takeoff
    from archforge.mep.project_pricebook import set_project_prices
    from archforge.mep.trade_costing import PriceEntry
    doc=Document(); stack=CommandStack(doc); panel=_flat(stack)
    stack.execute(UpdateEntity(panel.id,{
        'electrical_box_defaults':{k:'Owner fixture model' for k in ('junction','floor','pull','lv')},
        'electrical_item_specs':{'electrical.rcd':'Owner study RCD','electrical.panel_enclosure':'Owner study enclosure'},
        'electrical_quantity_inputs':{'electrical.rcd':2,'electrical.panel_enclosure':1}}))
    rows=takeoff(doc)['rows']
    set_project_prices(stack,doc,{r['code']:PriceEntry(material_unit_price=1,labour_unit_price=0) for r in rows})
    result=takeoff(doc)
    assert result['complete'] and result['total']==result['known_subtotal']
    assert result['engineering_status']=='ENGINEER_REVIEW'
    assert result==takeoff(Document.from_dict(doc.to_dict()))
    stack.undo(); assert takeoff(doc)['total'] is None


def test_edit_one_price_preserves_other_effective_component(monkeypatch):
    from archforge.mep.electrical_takeoff import edit_price
    from archforge.mep.project_pricebook import effective_prices
    from archforge.quantities import price_book
    doc=Document(); stack=CommandStack(doc); _flat(stack)
    monkeypatch.setattr(price_book,'load',lambda:{'fixture':{'material':3,'labour':4}})
    before=copy.deepcopy(doc.to_dict())
    edit_price(doc,stack,'fixture','material',5)
    assert effective_prices(doc)['fixture'].labour_unit_price==4
    stack.undo(); assert doc.to_dict()==before
    for v in (-1,float('nan'),float('inf')):
        with pytest.raises(ValueError): edit_price(doc,stack,'fixture','material',v)


@pytest.mark.parametrize('field,value',[
    ('electrical_box_defaults',{'junction':['bad']}),('electrical_box_defaults',{'bogus':'bad'}),
    ('electrical_quantity_inputs',{'electrical.rcd':-1}),('electrical_quantity_inputs',{'electrical.rcd':float('nan')})])
def test_study_input_validation_is_atomic(field,value):
    doc=Document(); stack=CommandStack(doc); panel=_flat(stack); before=copy.deepcopy(doc.to_dict())
    with pytest.raises(ValueError): stack.execute(UpdateEntity(panel.id,{field:value}))
    assert doc.to_dict()==before


def test_menu_opens_analysis_with_plan_and_preview_never_changes_document():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([]); w=MainWindow()
    try:
        _flat(w.stack)
        actions=[a for a in w._mockup_electrical_menu.actions() if 'Ανάλυση' in a.text()]
        assert len(actions)==1
        actions[0].trigger(); tab=w._board_tab; page=tab.takeoff_page
        assert w._central_tabs.currentWidget() is tab and tab.pages.currentWidget() is page
        assert page.table.rowCount()>0
        before=copy.deepcopy(w.doc.to_dict()); n=len(w.stack.done)
        page.mode.setCurrentIndex(page.mode.findData('ceiling'))
        assert w.doc.to_dict()==before and len(w.stack.done)==n
        assert tab.technical_plan.doc is page.preview_doc
        page.apply.click(); assert w.doc.to_dict()==page.preview_doc.to_dict()
        w.stack.undo(); assert w.doc.to_dict()==before
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_explicit_extra_materials_can_differ_by_passage_and_survive_save_undo():
    from archforge.mep.electrical_takeoff import routing_preview,takeoff
    doc=Document();stack=CommandStack(doc);panel=_flat(stack)
    before=copy.deepcopy(doc.to_dict())
    extra=[{'id':'fixture-floor','description':'Owner floor quotation item','unit':'τεμ.','quantity':7,'mode':'floor'},
           {'id':'fixture-ceiling','description':'Owner ceiling quotation item','unit':'τεμ.','quantity':3,'mode':'ceiling'}]
    stack.execute(UpdateEntity(panel.id,{'electrical_extra_items':extra}))
    for mode,identity,qty in [('floor','fixture-floor',7),('ceiling','fixture-ceiling',3)]:
        preview=routing_preview(doc,mode)
        rows=[r for r in takeoff(preview)['rows'] if r['code'].startswith('electrical.extra.')]
        assert len(rows)==1 and rows[0]['code']=='electrical.extra.'+identity and rows[0]['quantity']==qty
        assert takeoff(preview)==takeoff(Document.from_dict(preview.to_dict()))
    stack.undo();assert doc.to_dict()==before


def test_price_dialog_comparison_and_csv_keep_shared_prices_and_partial_labels(monkeypatch,tmp_path):
    from PySide6.QtWidgets import QApplication,QInputDialog
    from archforge.ui.main_window import MainWindow
    from archforge.mep.project_pricebook import effective_prices
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        _flat(w.stack)
        action=next(a for a in w._mockup_electrical_menu.actions() if 'Ανάλυση' in a.text());action.trigger()
        tab=w._board_tab;page=tab.takeoff_page;page.calculate_comparison()
        row=next(i for i,x in enumerate(page.row_data) if x['code'].startswith('electrical.conduit.'))
        code=page.row_data[row]['code'];before=copy.deepcopy(w.doc.to_dict())
        monkeypatch.setattr(QInputDialog,'getText',lambda *a,**kw:('2,50',True))
        page.table.cellDoubleClicked.emit(row,3)
        assert effective_prices(w.doc)[code].material_unit_price==2.5
        assert page.comparison and 'Μερικό' in page.compare_summary.text()
        text=page.export_csv(str(tmp_path/'electrical.csv'))
        exported=(tmp_path/'electrical.csv').read_text(encoding='utf-8-sig')
        assert text and 'ΕΚΚΡΕΜΕΙ' in exported and 'Δάπεδο' in exported and 'Οροφή' in exported
        w.stack.undo();assert w.doc.to_dict()==before
        page.mode.setCurrentIndex(page.mode.findData('floor'))
        tab.pages.setCurrentWidget(tab.circuits)
        assert tab.technical_plan.doc is w.doc
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_locked_layers_allow_read_only_preview_but_refuse_actual_apply():
    from archforge.mep.electrical_takeoff import routing_preview,apply_routing
    from archforge.core.layers import set_layer_state,LayerLockedError
    doc=Document();stack=CommandStack(doc);_flat(stack)
    set_layer_state(doc,'electrical',locked=True)
    before=copy.deepcopy(doc.to_dict());preview=routing_preview(doc,'floor')
    assert preview.to_dict()!=before and doc.to_dict()==before
    with pytest.raises(LayerLockedError):apply_routing(doc,stack,'floor')
    assert doc.to_dict()==before


def test_analysis_does_not_create_persistent_room_ids_as_a_query_side_effect():
    from archforge.mep.electrical_takeoff import takeoff
    doc=Document();stack=CommandStack(doc);_flat(stack);before=copy.deepcopy(doc.to_dict())
    takeoff(doc)
    assert doc.to_dict()==before


def test_technical_plan_fit_uses_drawing_geometry_not_infinite_rulers():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPointF
    from archforge.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        _flat(w.stack);w._electrical_analysis_action.trigger();tab=w._board_tab
        tab.resize(1200,1000);tab.show();app.processEvents();view=tab.technical_plan
        view.fit_content()
        assert view.viewport().rect().contains(view.mapFromScene(QPointF(0,0)))
        assert view.viewport().rect().contains(view.mapFromScene(QPointF(8,6)))
        assert view.mapToScene(view.viewport().rect()).boundingRect().width()<10*8
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_split_box_uses_the_conduit_maps_existing_coordinate_normalisation(monkeypatch):
    from archforge.mep import electrical,conduits,low_voltage
    from archforge.mep.electrical_takeoff import box_inventory
    monkeypatch.setattr(electrical,'route_cables_cached',lambda d:{'boxes':[(1.23456,2,3,'junction','C1')]})
    monkeypatch.setattr(conduits,'conduit_map',lambda d:{'split_boxes':[(1.235,2,3)]})
    monkeypatch.setattr(low_voltage,'route_low_voltage_cached',lambda d:{'boxes':[]})
    boxes=box_inventory(Document())
    assert len(boxes)==1 and boxes[0]['split']


def test_analysis_fits_the_owners_1280_by_960_screen():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        _flat(w.stack);w._electrical_analysis_action.trigger();w.resize(1280,960);w.show();app.processEvents()
        assert w.width()<=1280 and w.height()<=960
        assert w._board_tab.takeoff_page.table.viewport().height()>0
    finally:
        w._mark_clean();w.close();app.processEvents()
