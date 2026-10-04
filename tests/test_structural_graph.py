from archforge.core.model import Document, Entity
from archforge.structure.graph import build_structural_graph


def _column(entity_id='col', role='structural'):
    return Entity(
        'structural_column',
        {
            'x':0.0,'y':0.0,'z':0.0,
            'width':0.30,'depth':0.30,'height':3.0,'rotation':0.0,
            'role':role,'construction':'reinforced_concrete','section':'rectangular',
            'base_level':'Ground','top_level':'Floor 2',
        },
        id=entity_id,
    )


def _beam(entity_id='beam', role='structural'):
    return Entity(
        'structural_beam',
        {
            'x1':0.0,'y1':0.0,'x2':4.0,'y2':0.0,
            'z':2.70,'width':0.20,'height':0.30,
            'role':role,'construction':'steel','section':'rectangular','level':'Ground',
        },
        id=entity_id,
    )


def test_column_top_and_beam_end_share_one_derived_node():
    doc=Document()
    column=_column()
    beam=_beam()
    doc.add(column);doc.add(beam)

    graph=build_structural_graph(doc)

    assert len(graph.members)==2
    assert len(graph.nodes)==3

    cm=graph.member(column.id)
    bm=graph.member(beam.id)
    assert cm.end_node==bm.start_node
    assert graph.nodes[cm.end_node].point==(0.0,0.0,3.0)
    assert graph.degree(cm.end_node)==2


def test_pergola_members_do_not_enter_structural_analysis_graph():
    doc=Document()
    doc.add(_column('structural-col','structural'))
    doc.add(_beam('pergola-beam','pergola'))

    graph=build_structural_graph(doc)

    assert {m.entity_id for m in graph.members}=={'structural-col'}


def test_structural_graph_is_rederived_after_manual_geometry_edit():
    doc=Document()
    beam=_beam()
    doc.add(beam)

    before=build_structural_graph(doc)
    assert before.nodes[1].point==(4.0,0.0,3.0)

    doc.update(beam.id,{'x2':5.0})
    after=build_structural_graph(doc)

    assert after.nodes[1].point==(5.0,0.0,3.0)


def test_structural_entities_persist_role_construction_and_levels():
    doc=Document()
    doc.levels={'Ground':0.0,'Floor 2':3.0}
    col=_column('persist-col','pergola')
    beam=_beam('persist-beam','architectural')
    beam.params['level']='Floor 2'
    beam.params['z']=2.70
    beam.params['construction']='timber'
    doc.add(col);doc.add(beam)

    restored=Document.from_dict(doc.to_dict())

    rc=restored.get(col.id)
    rb=restored.get(beam.id)
    assert rc.params['role']=='pergola'
    assert rc.params['construction']=='reinforced_concrete'
    assert rc.params['base_level']=='Ground'
    assert rc.params['top_level']=='Floor 2'
    assert rb.params['role']=='architectural'
    assert rb.params['construction']=='timber'
    assert rb.params['level']=='Floor 2'


def test_beam_placement_binds_top_face_to_next_level():
    from archforge.core.commands import CommandStack
    from archforge.core.viewport import PointerController, PointerEvent

    doc=Document()
    doc.levels={'Ground':0.0,'Floor 2':2.70}
    doc.work_plane.name='Ground'
    doc.work_plane.origin=(0.0,0.0,0.0)
    stack=CommandStack(doc)
    controller=PointerController(doc,stack)
    controller.grid=None
    controller.set_tool('structural_beam')

    controller.pointer_down(PointerEvent(0.0,0.0))
    result=controller.pointer_up(PointerEvent(4.0,0.0))
    beam=doc.get(result.entity_id)

    assert beam.kind=='structural_beam'
    # The beam sits physically under the next level, but belongs to the storey
    # it was authored from so it stays visible in that storey's plan.
    assert beam.params['level']=='Ground'
    assert abs(float(beam.params['z'])-2.40)<1e-9
    assert abs(float(beam.params['z'])+float(beam.params['height'])-2.70)<1e-9


def test_level_bound_structural_members_reject_vertical_move_but_allow_xy():
    import pytest
    from archforge.core.commands import CommandStack, MoveEntities

    doc=Document()
    col=_column('move-col')
    beam=_beam('move-beam')
    doc.add(col);doc.add(beam)
    stack=CommandStack(doc)

    stack.execute(MoveEntities([col.id,beam.id],1.0,2.0,0.0))
    assert doc.get(col.id).params['x']==1.0
    assert doc.get(col.id).params['y']==2.0
    assert doc.get(beam.id).params['x1']==1.0
    assert doc.get(beam.id).params['y1']==2.0

    with pytest.raises(ValueError, match='level-driven'):
        stack.execute(MoveEntities([col.id],0.0,0.0,0.25))

    assert doc.get(col.id).params['z']==0.0


def test_support_is_authoritative_child_but_maps_to_current_derived_node():
    doc=Document()
    col=_column('support-col')
    beam=_beam('support-beam')
    doc.add(col);doc.add(beam)

    support=Entity(
        'structural_support',
        {'member_end':'start','support_type':'fixed'},
        id='support-1',
        parent_id=col.id,
    )
    doc.add(support)

    assert support.id in doc.children[col.id]
    assert support.id in doc.dependencies[col.id]

    graph=build_structural_graph(doc)
    assert len(graph.supports)==1
    gs=graph.supports[0]
    assert gs.entity_id==support.id
    assert gs.member_entity_id==col.id
    assert gs.support_type=='fixed'
    assert graph.nodes[gs.node_index].point==(0.0,0.0,0.0)

    # Move the authoritative member. The support follows the newly derived node;
    # it does not retain a stale node index or world coordinate.
    doc.update(col.id,{'x':1.0,'y':2.0})
    graph2=build_structural_graph(doc)
    gs2=graph2.supports[0]
    assert graph2.nodes[gs2.node_index].point==(1.0,2.0,0.0)


def test_duplicate_support_on_same_member_end_is_rejected():
    import pytest
    doc=Document()
    col=_column('dup-support-col')
    doc.add(col)
    doc.add(Entity(
        'structural_support',
        {'member_end':'start','support_type':'pinned'},
        parent_id=col.id,
    ))

    with pytest.raises(ValueError, match='already has a support'):
        doc.add(Entity(
            'structural_support',
            {'member_end':'start','support_type':'roller'},
            parent_id=col.id,
        ))


def test_support_roundtrip_and_member_delete_cascade():
    doc=Document()
    beam=_beam('cascade-beam')
    doc.add(beam)
    support=Entity(
        'structural_support',
        {'member_end':'end','support_type':'roller'},
        parent_id=beam.id,
    )
    doc.add(support)

    restored=Document.from_dict(doc.to_dict())
    rs=restored.get(support.id)
    assert rs.parent_id==beam.id
    assert rs.params=={'member_end':'end','support_type':'roller'}

    restored.remove(beam.id)
    assert beam.id not in restored.entities
    assert support.id not in restored.entities


def test_structural_load_is_authoritative_input_and_enters_graph():
    doc=Document()
    beam=_beam('load-beam')
    doc.add(beam)
    load=Entity(
        'structural_load',
        {
            'load_type':'point',
            'magnitude':12.5,
            'direction':[0.0,0.0,-1.0],
            'position':0.25,
            'load_case':'User Load',
            'unit':'kN',
            'source':'User input',
        },
        id='load-1',
        parent_id=beam.id,
    )
    doc.add(load)

    graph=build_structural_graph(doc)
    assert len(graph.loads)==1
    g=graph.loads[0]
    assert g.entity_id==load.id
    assert g.member_entity_id==beam.id
    assert g.magnitude==12.5
    assert g.direction==(0.0,0.0,-1.0)
    assert g.position==0.25
    assert g.load_case=='User Load'
    assert g.unit=='kN'
    assert g.source=='User input'


def test_structural_load_roundtrip_preserves_provenance():
    doc=Document()
    beam=_beam('load-persist-beam')
    doc.add(beam)
    load=Entity(
        'structural_load',
        {
            'load_type':'distributed',
            'magnitude':4.0,
            'direction':[0.0,0.0,-1.0],
            'position':0.5,
            'load_case':'Roof Live',
            'unit':'kN/m',
            'source':'User input',
        },
        id='load-persist',
        parent_id=beam.id,
    )
    doc.add(load)

    restored=Document.from_dict(doc.to_dict())
    r=restored.get(load.id)
    assert r.parent_id==beam.id
    assert r.params['load_case']=='Roof Live'
    assert r.params['unit']=='kN/m'
    assert r.params['source']=='User input'


def test_member_role_cannot_leave_structural_while_support_or_load_attached():
    import pytest
    doc=Document()
    beam=_beam('guard-beam')
    doc.add(beam)
    doc.add(Entity(
        'structural_support',
        {'member_end':'start','support_type':'fixed'},
        parent_id=beam.id,
    ))
    with pytest.raises(ValueError, match='remove structural supports/loads'):
        doc.update(beam.id,{'role':'pergola'})

    doc2=Document()
    beam2=_beam('guard-load-beam')
    doc2.add(beam2)
    doc2.add(Entity(
        'structural_load',
        {
            'load_type':'point','magnitude':1.0,
            'direction':[0.0,0.0,-1.0],'position':0.5,
            'load_case':'User Load','unit':'kN','source':'User input',
        },
        parent_id=beam2.id,
    ))
    with pytest.raises(ValueError, match='remove structural supports/loads'):
        doc2.update(beam2.id,{'role':'architectural'})


def test_structural_view_shares_authoritative_document_with_other_views():
    from archforge.ui.main_window import MainWindow
    window=MainWindow()
    assert window.structural_view.doc is window.doc
    assert window.plan_view.doc is window.doc
    assert window.pbr_view.doc is window.doc
    assert window.structural_view.stack is window.stack
    window.close()
