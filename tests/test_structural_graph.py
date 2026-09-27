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
