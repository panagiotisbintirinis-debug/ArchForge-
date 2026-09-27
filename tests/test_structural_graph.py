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
    assert beam.params['level']=='Floor 2'
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
