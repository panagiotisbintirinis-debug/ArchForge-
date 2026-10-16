"""RC shear walls (τοιχία): a column entity flagged ``wall``, wide-column model with rigid arms."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from test_structural_analysis import H, _building


def _wall(st, x=2.5, y=0.0, length=2.0, rotation=0.0, z=0.0):
    e = Entity('structural_column', {'x': x, 'y': y, 'z': z, 'width': length, 'depth': 0.25, 'height': H,
                                     'rotation': rotation, 'role': 'structural', 'construction': 'reinforced_concrete',
                                     'section': 'rectangular', 'base_level': 'Ground', 'top_level': 'Unassigned', 'wall': True})
    st.execute(AddEntity(e))
    return e


def test_wall_is_tied_to_the_beam_nodes_in_its_footprint_by_rigid_arms():
    from archforge.structure.analysis.building import build_model
    from archforge.structure.analysis.settings import get_settings
    doc, st = _building(storeys=1)
    w = _wall(st)
    m = build_model(doc, get_settings(doc))
    assert m.members[w.id].wall
    arms = [e for e in m.elements if e.tag == 'rigid:' + w.id]
    assert arms
    top = m.elements[m.members[w.id].elements[-1]].n2
    for e in arms:
        assert e.n1 == top
        x, y, z = m.nodes[e.n2]
        assert abs(x - 2.5) <= 1.0 + 0.15 and abs(y) <= 0.125 + 0.15 and z == pytest.approx(m.nodes[top][2])


def test_wall_stiffens_its_direction_and_carries_most_of_that_shear():
    from archforge.structure.analysis import analyze
    doc, st = _building(storeys=1)
    before = analyze(doc)
    w = _wall(st)
    r = analyze(doc)
    tx = lambda res: min(m['T_s'] for m in res['modal']['modes'] if m['dominant'] == 'X')
    assert tx(r) < 0.6 * tx(before)                                       # much stiffer along the wall
    cols = [e for e in r['members'].values() if e['kind'] == 'column']
    wall = r['members'][w.id]
    assert wall['V'] > max(e['V'] for e in cols if e['id'] != w.id)        # the wall attracts the shear


def test_wall_design_skips_column_only_rules_and_says_what_is_not_checked():
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.rc import WALL_NOTE, design_column
    from archforge.structure.analysis.report import report_html
    from archforge.structure.analysis.settings import DEFAULTS
    from archforge.core.provenance import VERIFIED, rule
    s = dict(DEFAULTS)
    acts = [(800.0, 10.0, 300.0)]                                        # in-plane bending: Mz (lever along the 2 m length)
    as_column = design_column(2.0, 0.25, 3.0, acts, 100.0, s, acts)
    as_wall = design_column(2.0, 0.25, 3.0, acts, 100.0, s, acts, wall=True)
    assert as_wall['ok'] and as_wall['wall'] and as_wall['notes'] == [WALL_NOTE]
    assert not any('25 cm' in c or '1–4 %' in c or '0,65' in c for c in as_wall['checks'])
    assert as_wall['bars']['rho'] < 1.0 and as_wall['utilisation'] <= 1.0
    assert as_column.get('bars') is None or as_column['bars']['rho'] >= 1.0  # the column rules would ask ρ ≥ 1 %
    doc, st = _building(storeys=1)
    w = _wall(st)
    r = analyze(doc)
    assert r['members'][w.id]['wall'] and not any(j['x'] == 2.5 and j['y'] == 0.0 for j in r['capacity_joints'])
    html = report_html(r)
    assert '(τοιχίο)' in html and 'δεν γίνεται' in html
    assert rule('structure.wall_model').status != VERIFIED


def test_wall_preset_places_a_wall_through_the_shared_transaction():
    from archforge.core.commands import CommandStack
    from archforge.core.interaction import StructuralColumnPlaceTransaction
    from archforge.core.model import Document
    doc = Document(); st = CommandStack(doc)
    t = StructuralColumnPlaceTransaction(doc, st, 1.0, 1.0, z=0.0, height=3.0, width=2.0, depth=0.25, wall=True,
                                         snap_enabled=False)
    eid = t.commit()
    p = doc.get(eid).params
    assert p['wall'] is True and p['width'] == 2.0 and p['depth'] == 0.25
    st.undo()
    assert eid not in doc.entities
    plain = StructuralColumnPlaceTransaction(doc, st, 1.0, 1.0, z=0.0, height=3.0, snap_enabled=False).commit()
    assert 'wall' not in doc.get(plain).params
