"""Structural analysis derived from the Document: frame solver, loads, seismic, RC/steel design, UI."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from archforge.core.commands import AddEntity, CommandStack, UpdateEntity
from archforge.core.model import Document, Entity
from archforge.structure.analysis import analyze, analyze_cached, fresh_result
from archforge.structure.analysis.fem import Element, Frame, internal

H = 3.0


def _building(doc=None, construction='reinforced_concrete', storeys=2, col=0.40, beam=(0.25, 0.50), span_x=5.0):
    """Two-bay × two-bay frame 2·span_x × 8 m, walls on every axis, one room per bay."""
    doc = doc or Document(); st = CommandStack(doc)
    for k in range(1, storeys + 1):
        doc.levels[f'L{k}'] = k * H
    xs, ys, X = (0.0, span_x, 2 * span_x), (0.0, 4.0, 8.0), 2 * span_x
    for k in range(storeys):
        z = k * H
        for x1, y1, x2, y2 in [(0, 0, X, 0), (X, 0, X, 8), (X, 8, 0, 8), (0, 8, 0, 0), (span_x, 0, span_x, 8), (0, 4, X, 4)]:
            st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': z, 'height': H - beam[1], 'thickness': 0.2})))
        for x in xs:
            for y in ys:
                st.execute(AddEntity(Entity('structural_column', {
                    'x': x, 'y': y, 'z': z, 'width': col, 'depth': col, 'height': H, 'rotation': 0.0, 'role': 'structural',
                    'construction': construction, 'section': 'rectangular', 'base_level': 'Ground', 'top_level': 'Unassigned'})))
        top = (k + 1) * H
        for a, b in [((0, y), (X, y)) for y in ys] + [((x, 0), (x, 8)) for x in xs]:
            st.execute(AddEntity(Entity('structural_beam', {
                'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': top - beam[1], 'width': beam[0], 'height': beam[1],
                'role': 'structural', 'construction': construction, 'section': 'rectangular', 'level': 'Ground' if k == 0 else 'L1'})))
    return doc, st


# --------------------------------------------------------------- solver
def test_frame_solver_matches_textbook_cases():
    E, G = 30e6, 12.5e6
    b, h, L, n, q = 0.25, 0.5, 6.0, 6, 10.0
    nodes = [(i * L / n, 0, 3) for i in range(n + 1)]
    els = [Element(i, i + 1, E, G, b * h, b * h ** 3 / 12, h * b ** 3 / 12, 1e-3) for i in range(n)]
    fr = Frame(nodes, els, {0: (True, True, True, True, False, False), n: (False, True, True, False, False, False)})
    U, F, R = fr.solve({i: (0, 0, -q * L / n * (0.5 if i in (0, n) else 1), 0, 0, 0) for i in range(n + 1)})
    assert internal(F[2])[1][4] == pytest.approx(q * L ** 2 / 8)                      # sagging +, wL²/8
    assert R[0][2] + R[n][2] == pytest.approx(q * L)
    col = Frame([(0, 0, 0), (0, 0, 3)], [Element(0, 1, E, G, .16, .4 ** 4 / 12, .4 ** 4 / 12, .02, y_dir=(1, 0, 0))], {0: (True,) * 6})
    _U, F, _R = col.solve({1: (10, 0, -100, 0, 0, 0)})
    start, _end = internal(F[0])
    assert start[0] == pytest.approx(-100) and abs(start[5]) == pytest.approx(30)        # N, base moment H·h


def test_mechanism_is_detected():
    with pytest.raises(np.linalg.LinAlgError):
        Frame([(0, 0, 0), (5, 0, 0)], [Element(0, 1, 30e6, 12.5e6, .1, 1e-3, 1e-3, 1e-4)],
              {0: (True, True, True, False, False, False), 1: (False, True, True, False, False, False)})


# --------------------------------------------------------------- RC sections
def test_rc_beam_bending_matches_hand_calculation():
    from archforge.structure.analysis.rc import design_beam
    from archforge.structure.analysis.settings import DEFAULTS
    r = design_beam(0.25, 0.50, 150.0, 0.0, 50.0, 5.0, dict(DEFAULTS))
    # μ = 150/(0.25·0.45²·16.67·1000) = 0.178 → ω = 0.197 → As = 8.52 cm²
    assert r['bottom']['As_req_cm2'] == pytest.approx(8.52, abs=0.05)
    assert (r['bottom']['n'], r['bottom']['d']) == (3, 20) and r['ok']
    assert r['stirrups']['s_crit'] <= 0.125


def test_rc_column_capacity_is_physical():
    from archforge.structure.analysis.rc import column_capacity
    My, Mz, NRd, n = column_capacity(0.40, 0.40, 3, 3, 16, 0.0, 'C25/30')
    assert n == 8 and My == pytest.approx(Mz, rel=1e-6)
    # Hand check (stress block 0.8x, εcu 3.5 ‰, 3+2+3 Ø16): equilibrium at x ≈ 6.0 cm → MRd ≈ 115.9 kNm
    # (the two middle bars also yield in tension).
    assert My == pytest.approx(115.9, abs=0.5)
    assert NRd == pytest.approx((0.16 * 25 / 1.5 + 8 * math.pi * 0.016 ** 2 / 4 * 500 / 1.15) * 1000)
    My_n, _mz, _nrd, _n = column_capacity(0.40, 0.40, 3, 3, 16, 800.0, 'C25/30')
    assert My_n > My                                            # moderate compression raises the moment capacity


# --------------------------------------------------------------- building
def test_two_storey_rc_building_loads_seismic_and_design():
    doc, _st = _building()
    r = analyze(doc)
    assert r['error'] is None and r['ok']
    from archforge.structure.analysis.building import build_model
    from archforge.structure.analysis.settings import get_settings
    m = build_model(doc, get_settings(doc))
    G = -sum(v[2] for v in m.loads['G'].values())
    Q = -sum(v[2] for v in m.loads['Q'].values())
    # Slabs (7.0 floor + 6.5 roof)·80 + walls 3.6·2.5·54 + beams 3.125·108 + columns 4·3·18
    assert G == pytest.approx((7.0 + 6.5) * 80 + 3.6 * 2.5 * 54 + 3.125 * 108 + 0.16 * 25 * 3 * 18, rel=1e-6)
    assert Q == pytest.approx(2 * 80 * 2.0, rel=1e-6)
    s = r['seismic']
    assert s['q'] == pytest.approx(3.9) and 0.2 < s['Ex']['T_s'] < 0.8
    assert s['Ex']['Fb_kN'] == pytest.approx(s['Ex']['Sd_ms2'] * float(s['mass_t']) * s['Ex']['lambda'], rel=1e-3)
    names = sorted(e['name'] for e in r['members'].values())
    assert len(names) == 18 + 12 and 'Κ1' in names and 'Δ1' in names
    beam = next(e for e in r['members'].values() if e['kind'] == 'beam')
    assert 'κάτω' in beam['text'] and 'Ø' in beam['text'] and 'bottom' in beam and 'stirrups' in beam
    col = next(e for e in r['members'].values() if e['kind'] == 'column')
    assert col['bars']['rho'] >= 1.0 and col['nu_d'] <= 0.65
    assert len(r['footings']) == 9 and all(f['B_m'] >= 1.0 for f in r['footings'])
    assert 'μηχανικού' in r['provenance']


def test_higher_seismic_zone_increases_base_shear():
    doc, st = _building()
    low = analyze(doc)['seismic']['Ex']['Fb_kN']
    st.execute(AddEntity(Entity('structural_design', {'seismic_zone': '3'})))
    high = analyze(doc)['seismic']['Ex']['Fb_kN']
    assert high / low == pytest.approx(0.36 / 0.16, rel=0.02)


def test_undersized_beam_fails_and_the_proposal_fixes_it_keeping_the_slab_level():
    doc, st = _building(storeys=1, beam=(0.20, 0.30), span_x=7.0)
    r = analyze(doc)
    failing = [e for e in r['members'].values() if not e['ok'] and e['kind'] == 'beam']
    assert failing and 'proposal' in failing[0]
    e = failing[0]
    before = doc.get(e['id']).params
    st.execute(UpdateEntity(e['id'], e['proposal']))
    after = doc.get(e['id']).params
    assert after['z'] + after['height'] == pytest.approx(before['z'] + before['height'])      # top stays at the slab
    assert after['height'] > before['height']
    again = analyze(doc)['members'][e['id']]
    assert again['utilisation'] < e['utilisation']


def test_steel_building_gets_rolled_profiles():
    doc, st = _building(construction='steel', storeys=1)
    r = analyze(doc)
    cols = [e for e in r['members'].values() if e['kind'] == 'column']
    beams = [e for e in r['members'].values() if e['kind'] == 'beam']
    assert all(e['profile'].startswith('HEB') for e in cols) and all(e['profile'].startswith('IPE') for e in beams)
    assert all(e['utilisation'] <= 1.0 for e in cols + beams)
    assert r['settings']['system'] == 'steel' and r['seismic']['q'] == 4.0
    prop = beams[0]['proposal']
    st.execute(UpdateEntity(beams[0]['id'], prop))
    assert doc.get(beams[0]['id']).params['profile'] == prop['profile']


def test_beams_without_columns_report_instead_of_crashing():
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('structural_beam', {'x1': 0, 'y1': 0, 'x2': 5, 'y2': 0, 'z': 2.5, 'width': .25, 'height': .5,
                                                     'role': 'structural', 'construction': 'reinforced_concrete',
                                                     'section': 'rectangular', 'level': 'Ground'})))
    r = analyze(doc)
    assert not r['ok'] and r['error']


def test_bad_profile_or_settings_are_rejected():
    doc, st = _building(storeys=1)
    col = next(e for e in doc.entities.values() if e.kind == 'structural_column')
    with pytest.raises(ValueError):
        st.execute(UpdateEntity(col.id, {'profile': 'HEB999'}))
    with pytest.raises(ValueError):
        st.execute(AddEntity(Entity('structural_design', {'soil': 'Z'})))


# --------------------------------------------------------------- assistant + UI
def test_assistant_runs_the_analysis_and_proposes_fixes():
    from archforge.assistant.suggestions import apply, propose
    doc, st = _building(storeys=1, beam=(0.20, 0.30), span_x=7.0)
    run = next(p for p in propose(doc) if p.key == 'S-0')
    apply(st, run)
    assert fresh_result(doc) is not None
    fixes = [p for p in propose(doc) if p.key.startswith('S-1') and p.actionable]
    assert fixes
    apply(st, fixes[0])
    assert fresh_result(doc) is None                       # the structure changed → analysis is stale again
    assert any(p.key == 'S-0' for p in propose(doc))
    st.undo()
    assert fresh_result(doc) is not None


def test_plan_shows_results_only_when_fresh():
    from archforge.core.plan_scene import build_plan_frame
    doc, st = _building(storeys=1)
    assert 'structural-label' not in [p.role for p in build_plan_frame(doc).primitives]
    analyze_cached(doc)
    labels = [dict(p.meta)['text'] for p in build_plan_frame(doc).primitives if p.role == 'structural-label']
    assert any(t.startswith('Κ') and 'Ø' in t for t in labels) and any(t.startswith('Δ') for t in labels)


def test_structural_menu_report_and_settings():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        texts = [a.text() for a in window._structure_menu.actions()]
        assert 'Στατική ανάλυση φέροντος οργανισμού…' in texts and 'Στοιχεία κτιρίου για στατική…' in texts
        _building(window.doc, storeys=1)
        window._apply_structural_settings({'seismic_zone': '2', 'occupancy': 'office'})
        window._no_modal_dialogs = True
        result = window._show_structural_analysis()
        html = window._structural_report.toHtml()
        assert result['settings']['seismic_zone'] == '2' and 'Δοκοί' in html and 'Υποστυλώματα' in html and 'Πέδιλα' in html
        window.stack.undo()                                 # settings are an ordinary undoable command
        from archforge.structure.analysis.settings import design_entity
        assert design_entity(window.doc) is None
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_reading_counts_columns_and_beams_per_storey():
    from archforge.assistant.understanding import describe, read_drawing
    doc, _st = _building(storeys=2)
    storeys = read_drawing(doc)['storeys']
    assert [len(s['columns']) for s in storeys[:2]] == [9, 9] and [len(s['beams']) for s in storeys[:2]] == [6, 6]
    assert '9 κολώνες, 6 δοκοί' in describe(read_drawing(doc))
