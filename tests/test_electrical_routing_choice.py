"""Owner: floor, ceiling or perimeter must change routes, not just the picture."""
import math
import pytest
from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.mep.electrical import route_cables, routing_of, _ceiling, WALL_RUN_Z, mount_z


def fixture():
    doc=Document(); stack=CommandStack(doc)
    for a,b in [((0,0),(5,0)),((5,0),(5,4)),((5,4),(0,4)),((0,4),(0,0))]:
        stack.execute(AddEntity(Entity('wall',dict(x1=a[0],y1=a[1],x2=b[0],y2=b[1],z=0,height=3,thickness=.2))))
    def point(typ,x,y,**kw):
        e=Entity('electrical_point',dict(x=x,y=y,z=0,point_type=typ,**kw));stack.execute(AddEntity(e));return e
    return doc,stack,point


@pytest.mark.parametrize('kind',['socket','light'])
def test_explicit_choice_changes_real_power_routes_and_survives_undo_save(kind):
    from archforge.mep.electrical_board import analyse
    doc,stack,point=fixture();point('panel',0,0);e=point(kind,5,4)
    snapshots={};lengths={}
    for mode,z in [('wall',WALL_RUN_Z),('floor',.05),('ceiling',_ceiling(doc,0))]:
        stack.execute(UpdateEntity(e.id,{'routing':mode}))
        assert routing_of(doc,doc.get(e.id))==mode
        r=route_cables(doc)
        runs=[(a,b) for a,b,g,c in r['runs'] if g!='switch']
        assert runs and any(abs(a[2]-z)<1e-6 and abs(b[2]-z)<1e-6 and math.dist(a[:2],b[:2])>1e-6 for a,b in runs)
        if kind=='socket' or mode=='ceiling':
            assert all(abs(a[2]-z)<1e-6 for a,b in runs if math.dist(a[:2],b[:2])>1e-6)
        assert any(math.dist(p,(5,4,mount_z(doc,e.params)))<1e-6 for a,b in runs for p in (a,b))
        snapshots[mode]=r['runs'];lengths[mode]=analyse(doc)['circuits'][0]['conduit_m']
    assert len(set(lengths.values()))>1
    restored=Document.from_dict(doc.to_dict())
    assert route_cables(restored)['runs']==snapshots['ceiling']
    stack.undo();assert route_cables(doc)['runs']==snapshots['floor']


def test_switch_leg_uses_choice_and_board_counts_the_identical_segments():
    from archforge.mep.electrical_board import _switch_runs
    doc,stack,point=fixture();point('panel',0,0);point('light',4,3)
    sw=point('switch',0,2)
    for mode in ('floor','ceiling','wall'):
        stack.execute(UpdateEntity(sw.id,{'routing':mode}))
        wiring=route_cables(doc)
        actual=[(a,b) for a,b,g,c in wiring['runs'] if g=='switch']
        counted=[(a,b) for a,b,sid in _switch_runs(doc,wiring,{e.id:e for e in doc.entities.values() if e.kind=='electrical_point'})]
        assert actual==counted
        z={'floor':.05,'wall':WALL_RUN_Z,'ceiling':_ceiling(doc,0)}[mode]
        assert any(abs(a[2]-z)<1e-6 and abs(b[2]-z)<1e-6 and math.dist(a,b)>1e-6 for a,b in actual)


@pytest.mark.parametrize('kind',['data_outlet','wifi_ap','tv_outlet'])
def test_low_voltage_choice_changes_actual_route_and_cable_quantity(kind):
    from archforge.mep.low_voltage import route_low_voltage,LV_RUN_RISE
    doc,stack,point=fixture();point('network_rack',0,0);e=point(kind,5,4)
    lengths=[]
    for mode,base in [('wall',WALL_RUN_Z),('floor',.05),('ceiling',_ceiling(doc,0))]:
        stack.execute(UpdateEntity(e.id,{'routing':mode}))
        r=route_low_voltage(doc);z=base+LV_RUN_RISE
        assert any(abs(a[2]-z)<1e-6 and math.dist(a[:2],b[:2])>1e-6 for a,b,*_ in r['runs'])
        if kind!='wifi_ap' or mode=='ceiling':
            assert all(abs(a[2]-z)<1e-6 for a,b,*_ in r['runs'] if math.dist(a[:2],b[:2])>1e-6)
        lengths.append(r['outlets'][0]['cable_m'])
    assert len(set(lengths))>1


def test_knx_bus_respects_destination_choice():
    from archforge.mep.knx import bus_chain
    from archforge.mep.low_voltage import LV_RUN_RISE
    doc,stack,point=fixture();panel=point('panel',0,0);sw=point('switch',5,4)
    for mode,base in [('wall',WALL_RUN_Z),('floor',.05),('ceiling',_ceiling(doc,0))]:
        stack.execute(UpdateEntity(sw.id,{'routing':mode}))
        order,runs,length,farthest=bus_chain(doc,doc.get(panel.id),[doc.get(sw.id)]);z=base+LV_RUN_RISE
        assert all(abs(a[2]-z)<1e-6 and abs(b[2]-z)<1e-6 for a,b in runs if math.dist(a[:2],b[:2])>1e-6)
        assert length==round(sum(math.dist(a,b) for a,b in runs),2)


def test_inspector_exposes_all_modes_for_lights_and_manual_choice_is_undoable():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        e=Entity('electrical_point',dict(x=1,y=1,z=0,point_type='light'))
        w.stack.execute(AddEntity(e));w.doc.select([e.id]);w.refresh_inspector()
        fields={}
        for i in range(w.form.rowCount()):
            label=w.form.itemAt(i,w.form.ItemRole.LabelRole)
            if label and hasattr(label.widget(),'text'):
                field=w.form.itemAt(i,w.form.ItemRole.FieldRole)
                fields[label.widget().text()]=field.widget() if field else None
        combo=fields['Όδευση']
        assert {combo.itemData(i) for i in range(combo.count())}=={'auto','floor','ceiling','wall'}
        combo.setCurrentIndex(combo.findData('ceiling'))
        assert w.doc.get(e.id).params['routing']=='ceiling'
        w.stack.undo();assert w.doc.get(e.id).params.get('routing','auto')=='auto'
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_switch_conduit_identity_survives_every_grid_segment():
    from archforge.mep.conduits import conduit_map
    doc,stack,point=fixture();point('panel',0,0);point('light',4,3)
    sw=point('switch',0,2,routing='floor')
    pieces=conduit_map(doc)['pieces']
    lines={line for piece in pieces for line in piece['line_ids'] if line.startswith('switch:')}
    assert lines=={f'switch:{sw.id}'}


def test_automatic_grid_terminal_does_not_gain_tiny_extra_bends():
    from archforge.mep.conduits import conduit_map
    doc,stack,point=fixture();point('panel',0,0);point('cooker',4.93,3.93)
    assert not conduit_map(doc)['warnings']
