"""Synthetic geometry fixtures: these diameters are arithmetic inputs, not products."""
import pytest


def test_geometric_fill_uses_insulated_outside_diameter_and_conduit_inside():
    from archforge.mep.conduit_fill import geometric_fill
    assert geometric_fill(10, {2: 6}) == pytest.approx(.24)
    assert geometric_fill(10, {2: 8}) == pytest.approx(.32)
    assert geometric_fill(20, {2: 8}) == pytest.approx(.08)
    assert geometric_fill(10, {2: 3, 3: 2}) == pytest.approx(.30)
    with pytest.raises(ValueError): geometric_fill(0, {2: 3})


def test_adding_diameter_avoids_unnecessary_second_and_third_pipe():
    from archforge.mep.conduit_fill import allocate
    # A circuit stays together: each synthetic circuit is three insulated wires.
    lines={f'C{i}': {3.:3} for i in range(3)}
    options={10:10.,20:18.}  # synthetic label -> actual bore; not manufacturer data
    small=allocate(lines,options,limit=.30,max_dn=10)
    assert len(small['pipes'])==3 and not small['unsupported']
    large=allocate(lines,options,limit=.30,max_dn=20)
    assert len(large['pipes'])==1 and large['pipes'][0]['dn']==20
    for result in (small,large):
        assert sorted(cid for p in result['pipes'] for cid in p['lines'])==sorted(lines)
        assert all(p['lines'] and p['fill']<=.30+1e-12 for p in result['pipes'])


def test_no_overfilled_pipe_and_no_splitting_one_circuits_conductors():
    from archforge.mep.conduit_fill import allocate
    result=allocate({'big':{8.:3},'ok':{2.:3}},{10:10.},limit=.30,max_dn=10)
    assert result['unsupported']==['big']
    assert [cid for p in result['pipes'] for cid in p['lines']]==['ok']
    assert all(p['fill']<=.30 for p in result['pipes'])


def test_catalog_has_sources_and_missing_wire_size_is_not_guessed():
    from archforge.mep.conduit_fill import CONDUIT_PROFILES,wire_bundle,DEFAULT_LIMIT
    assert DEFAULT_LIMIT==.30  # explicit owner choice, not a verified code clause
    for profile in CONDUIT_PROFILES.values():
        assert profile['source'].startswith('https://')
        assert all(0<inside<dn for dn,inside in profile['bores'].items())
    assert wire_bundle({99.:3}) is None


@pytest.mark.parametrize('loads,max_dn,expected',[(2,32,2),(2,40,1),(3,32,3),(3,50,1)])
def test_map_pipe_count_and_contents_change_with_actual_bore(loads,max_dn,expected):
    from archforge.core.commands import AddEntity,CommandStack
    from archforge.core.model import Document,Entity
    from archforge.mep.conduits import conduit_map
    doc=Document();stack=CommandStack(doc)
    stack.execute(AddEntity(Entity('wall',dict(x1=0,y1=0,x2=6,y2=0,z=0,height=3,thickness=.2))))
    stack.execute(AddEntity(Entity('electrical_point',dict(x=0,y=0,z=0,point_type='panel',
        conduit_fill_limit=.30,conduit_max_dn=max_dn,conduit_profile='conflex'))))
    for _ in range(loads):
        stack.execute(AddEntity(Entity('electrical_point',dict(x=5,y=0,z=0,point_type='cooker'))))
    m=conduit_map(doc)
    middle=[p for p in m['pieces'] if any(min(a[0],b[0])<2.5<max(a[0],b[0]) and abs(a[2]-b[2])<1e-9
        for a,b in zip(p['points'],p['points'][1:]))]
    assert sum(p['count'] for p in middle)==expected
    assert len([line for p in middle for line in p['line_ids']])==loads
    assert all(p['count']==1 and p['fill']<=.30+1e-12 and p['fill_limit']==.30 for p in m['pieces'])
    assert all(p['fill']==pytest.approx(sum(n*d*d for d,n in p['diameters'].items())/p['inner_mm']**2)
        for p in m['pieces'])
    assert sum(m['by_size'].values())==pytest.approx(sum(p['length_m'] for p in m['pieces']),abs=.02)
    # Parallel pipes continuing together do not require a box at every grid node.
    assert all(x in (0,5) for x,y,z in m['split_boxes'])


def test_dali_conduit_includes_the_actual_two_bus_conductors():
    from archforge.core.commands import AddEntity,CommandStack
    from archforge.core.model import Document,Entity
    from archforge.mep.conduits import conduit_map
    doc=Document();st=CommandStack(doc)
    for typ,x in [('panel',0),('light',3)]:
        params=dict(x=x,y=0,z=0,point_type=typ)
        if typ=='light':params['dimming']='dali2'
        st.execute(AddEntity(Entity('electrical_point',params)))
    pieces=conduit_map(doc)['pieces']
    assert pieces and all(sum(p['wire_counts'].values())==5 for p in pieces)


def test_board_limit_and_diameter_are_real_undoable_project_settings():
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity
    from archforge.core.model import Document,Entity
    from archforge.ui.main_window import MainWindow
    app=QApplication.instance() or QApplication([]);w=MainWindow()
    try:
        w.stack.execute(AddEntity(Entity('wall',dict(x1=0,y1=0,x2=6,y2=0,z=0,height=3,thickness=.2))))
        for typ,x in [('panel',0),('cooker',5),('cooker',5)]:
            w.stack.execute(AddEntity(Entity('electrical_point',dict(x=x,y=0,z=0,point_type=typ))))
        tab=w._board_tab;tab.refresh()
        assert tab.minimumSizeHint().width()<=1150
        assert tab.pipe_fill.value()==30
        assert tab.result['conduit_map']['conduits']==2
        index=tab.pipe_max.findData(40)
        tab.pipe_max.setCurrentIndex(index);tab.pipe_max.activated.emit(index)
        assert tab.result['conduit_map']['conduits']==1
        pid=tab.result['settings']['panel']
        assert w.doc.get(pid).params['conduit_max_dn']==40
        saved=Document.from_dict(w.doc.to_dict())
        from archforge.mep.conduits import conduit_map
        assert conduit_map(saved)['conduits']==1
        w.stack.undo();tab.refresh();assert tab.result['conduit_map']['conduits']==2
        headers=[tab.conduits.headerItem().text(i) for i in range(tab.conduits.columnCount())]
        assert 'Πλήρωση / όριο' in headers and 'Ø εσωτ.' in headers
        assert 'αντικατάσταση' in tab.pipe_note.text()
        assert 'αλλαγές διεύθυνσης' in tab.conduits.topLevelItem(0).toolTip(7)
        before=w.doc.to_dict();tab.technical_plan.redraw();assert w.doc.to_dict()==before
    finally:
        w._mark_clean();w.close();app.processEvents()


def test_invalid_project_limit_is_rejected_without_changing_the_document():
    from archforge.core.model import Entity,Document
    from archforge.core.commands import AddEntity,CommandStack
    doc=Document();stack=CommandStack(doc);before=doc.to_dict()
    for value in (0,1,-.2,1.1):
        with pytest.raises(ValueError):
            stack.execute(AddEntity(Entity('electrical_point',dict(x=0,y=0,z=0,point_type='panel',conduit_fill_limit=value))))
        assert doc.to_dict()==before


def test_pulling_review_reports_route_geometry_without_certifying_replacement():
    from archforge.mep.conduits import pulling_review
    # Synthetic route: collinear router vertices do not add bends; a 3D turn does.
    r=pulling_review([(0,0,0),(1,0,0),(1,0,0),(2,0,0),(2,1,0),(2,1,1)])
    assert r['length_m']==pytest.approx(4)
    assert r['turn_angles_deg']==pytest.approx([90,90])
    assert r['total_turn_deg']==pytest.approx(180)
    assert r['replacement_status']=='ENGINEER_REVIEW'
    assert r['bend_radii_m'] is None and r['accessibility_verified'] is False
    assert 'αντικατάσταση' in r['summary']


def test_low_fill_straight_conduit_still_needs_pulling_and_access_review():
    from archforge.core.commands import AddEntity,CommandStack
    from archforge.core.model import Document,Entity
    from archforge.mep.conduits import conduit_map
    doc=Document();st=CommandStack(doc)
    for typ,x in [('panel',0),('socket',3)]:
        st.execute(AddEntity(Entity('electrical_point',dict(x=x,y=0,z=0,point_type=typ))))
    m=conduit_map(doc)
    assert m['pieces'] and len(m['review'])==len(m['pieces'])
    for p in m['pieces']:
        assert p['fill']<p['fill_limit']
        assert p['pulling']['replacement_status']=='ENGINEER_REVIEW'
        assert p['pulling']['length_m']==pytest.approx(sum(__import__('math').dist(a,b)
            for a,b in zip(p['points'],p['points'][1:])))
        assert p['pulling']['summary'] in m['review']
