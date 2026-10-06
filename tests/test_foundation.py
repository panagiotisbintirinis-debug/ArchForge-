"""Columns, beams and footings in one command: footing reinforcement, tie beams, plan/3D/tree."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.structure.analysis import analyze, analyze_cached
from archforge.structure.analysis.sections import fyd
from archforge.structure.design_all import design_structure, summary
from archforge.structure.foundation import TIE_K, design_footings, levels, tie_beams
from tests.test_structural_analysis import _building

SETTINGS = {'concrete': 'C25/30', 'seismic_zone': '1', 'importance': '2', 'soil': 'B'}


def test_footing_reinforcement_matches_a_hand_calculation():
    (f,) = design_footings([{'x': 0, 'y': 0, 'N_sls_kN': 500.0, 'B_m': 1.6, 'h_m': 0.5, 'column_m': 0.4}], SETTINGS)
    sigma = 1.4 * 500 / 1.6 ** 2
    M = sigma * 0.6 ** 2 / 2
    assert f['sigma_kPa'] == pytest.approx(sigma, abs=0.1) and f['M_kNm_per_m'] == pytest.approx(M, abs=0.1)
    As = M / (0.9 * 0.44 * fyd() * 1000)
    assert f['As_cm2_per_m'] == pytest.approx(max(As, 0.26 * 2.6 / 500 * 0.44) * 1e4, abs=0.01)
    d, s = f['mesh_d'], f['mesh_s']
    assert math.pi * (d / 1000) ** 2 / 4 / s >= As and s <= 0.20 and f['name'] == 'Π1'


def test_tie_beams_link_every_footing_in_both_directions_with_the_ec8_force():
    grid = [{'x': x, 'y': y, 'N_sls_kN': 300.0, 'B_m': 1.4, 'h_m': 0.5} for x in (0, 5, 10) for y in (0, 4, 8)]
    fts = design_footings(grid, SETTINGS)
    ties = tie_beams(fts, SETTINGS)
    assert len(ties) == 12                                       # 3×3 grid: 6 along x, 6 along y
    N = TIE_K['B'] * 0.16 * 1.0 * 1.2 * 1.4 * 300
    assert all(t['N_kN'] == pytest.approx(N, abs=0.1) for t in ties)
    assert all(t['bars'] == '4Ø14' and t['section'] == '25/50' for t in ties)   # minimum governs here
    linked = {t['from'] for t in ties} | {t['to'] for t in ties}
    assert linked == {f['name'] for f in fts}


def test_analysis_result_carries_the_foundation_under_the_base():
    doc, _st = _building(storeys=1)
    r = analyze(doc)
    fd = r['foundation']
    assert len(fd['footings']) == 9 and len(fd['ties']) == 12
    assert all(f['column'].startswith('Κ') and f['column_id'] in doc.entities for f in fd['footings'])
    top, bottom = levels(fd['footings'][0])
    assert top == pytest.approx(-0.5) and bottom < top
    assert fd['concrete_m3'] > 0 and 'EN 1998-5' in fd['provenance']


def _shell(stack, w=10.0, d=8.0):
    for x1, y1, x2, y2 in [(0, 0, w, 0), (w, 0, w, d), (w, d, 0, d), (0, d, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 3.0, 'thickness': 0.25})))


def test_one_command_from_walls_to_columns_beams_and_footings_in_one_undo():
    doc = Document(); st = CommandStack(doc); _shell(st)
    out = design_structure(doc, st)
    r = out['result']
    assert out['added']['columns'] > 0 and r and not r.get('error')
    assert len(r['foundation']['footings']) == out['added']['columns']
    assert 'πέδιλα' in summary(out)
    st.undo()
    assert not any(e.kind in ('structural_column', 'structural_beam') for e in doc.entities.values())
    assert sum(e.kind == 'wall' for e in doc.entities.values()) == 4


def test_undersized_members_are_resized_until_they_pass():
    doc, st = _building(storeys=1, beam=(0.20, 0.30), span_x=7.0)
    assert any(not e['ok'] for e in analyze(doc)['members'].values())
    out = design_structure(doc, st)
    assert out['resized'] and out['rounds'] >= 2
    assert all(e['ok'] for e in out['result']['members'].values())


def test_load_bearing_walls_need_no_frame():
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('project_brief', {'wall_system': 'stone_bearing'})))
    _shell(st)
    out = design_structure(doc, st)
    assert out['bearing_walls'] and 'χωρίς κολόνες' in summary(out)
    assert not any(e.kind == 'structural_column' for e in doc.entities.values())


def test_footings_show_in_plan_3d_tree_and_report():
    from archforge.core.plan_scene import build_plan_frame
    from archforge.geometry.incremental import IncrementalEvaluationCache
    from archforge.geometry.sculpt import SculptedPreviewBackend
    from archforge.rendering.scene import build_pbr_scene_payload
    from archforge.structure.analysis.report import report_html
    from archforge.ui.project_outline import project_outline
    doc, _st = _building(storeys=1)
    r = analyze_cached(doc)
    roles = [p.role for p in build_plan_frame(doc).primitives]
    assert roles.count('footing') == 9 and roles.count('tie-beam') == 24
    payload = build_pbr_scene_payload(IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc), [], doc=doc)
    (fnd,) = [o for o in payload['objects'] if o.get('layer') == 'foundation']
    assert min(v[2] for v in fnd['vertices']) < -0.9
    html = report_html(r)
    assert 'Συνδετήριες δοκοί' in html and 'Π1' in html

    def labels(nodes):
        for n in nodes:
            yield n['label']
            yield from labels(n['children'])
    assert any(l.startswith('Θεμελίωση (9 πέδιλα, 12 συνδετήριες)') for l in labels([project_outline(doc)]))


def test_frame_and_foundation_concrete_go_into_the_priced_list():
    from archforge.quantities.materials import all_lists, structure_list
    doc, _st = _building(storeys=1)
    analyze_cached(doc)
    rows = {r[0]: r for r in structure_list(doc)}
    assert rows['Σκυρόδεμα κολονών'][2] == pytest.approx(9 * 0.4 * 0.4 * 3.0, abs=0.01)
    assert rows['Σκυρόδεμα πεδίλων'][2] > 0 and rows['Σκυρόδεμα συνδετήριων δοκών'][2] > 0
    assert 'Φέρων' in [s[0] for s in all_lists(doc)]
