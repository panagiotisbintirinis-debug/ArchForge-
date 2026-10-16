"""Structural pre-design: every rule has a status, no result passes as verified (owner 15/10).

The second half checks the frame solver against closed-form results of linear
Euler–Bernoulli beam theory (derived from the stiffness equations, no
regulatory value involved).  That checks the solver's mechanics only — not the
loads, factors or code checks built on it.
"""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from archforge.core.provenance import VERIFIED, rule, rules
from archforge.structure.analysis.fem import Element, Frame, internal
from archforge.structure.rules import SAMPLE_MATCHES, STATUS_BANNER, structural_rules, unverified_lines


def test_no_structural_rule_is_verified_and_all_are_listed():
    found = structural_rules()
    assert len(found) >= 30 and found == rules('structure.')
    assert all(r.status != VERIFIED for r in found)
    assert len(unverified_lines()) == len(found)
    # The sample study the owner sent is corroboration, never verification.
    for rid in SAMPLE_MATCHES:
        assert 'FESPA' in rule(rid).note and rule(rid).status != VERIFIED
    assert 'όχι επαλήθευση' in rule('structure.seismic_zones').note


def test_hidden_geotechnical_default_is_flagged_for_the_owner():
    r = rule('structure.soil_pressure_default')
    assert r.status != VERIFIED and 'γεωτεχνική' in r.note


def test_every_structural_output_carries_the_not_for_design_banner():
    import archforge.structure.analysis as A
    import archforge.structure.foundation as F
    import archforge.structure.joists as J
    import archforge.structure.slab_openings as O
    import archforge.structure.slabs as S
    import archforge.structure.timber_roof as T
    for mod in (A, F, J, O, S, T):
        assert mod.PROVENANCE.startswith(STATUS_BANNER), mod.__name__
    assert 'ΟΧΙ ΓΙΑ ΜΕΛΕΤΗ' in STATUS_BANNER


def test_report_shows_the_banner_and_the_status_of_every_rule():
    from html import escape
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.report import report_html
    from tests.test_structural_analysis import _building
    doc, _ = _building(storeys=1)
    r = analyze(doc)
    assert r['verified'] is False
    html = report_html(r)
    assert html.index(escape(STATUS_BANNER)) < html.index('<h3>')
    for line in unverified_lines():
        assert escape(line) in html


# --- Solver mechanics against closed-form beam theory ------------------------------------------

E, G, A, I, J = 30e6, 12.5e6, 0.08, 1.2e-3, 2.0e-3      # kN/m², m², m⁴ (any consistent values)


def _beam(n, L):
    nodes = [(L * i / n, 0.0, 0.0) for i in range(n + 1)]
    return nodes, [Element(i, i + 1, E, G, A, I, I, J) for i in range(n)]


FIXED = (True,) * 6


def test_cantilever_tip_load_and_moment():
    L, P, M = 4.0, 10.0, 7.0
    nodes, els = _beam(4, L)
    f = Frame(nodes, els, {0: FIXED})
    U, forces, R = f.solve({4: (0, 0, -P, 0, 0, 0)})
    assert U[4][2] == pytest.approx(-P * L ** 3 / (3 * E * I), rel=1e-9)        # δ = PL³/3EI
    assert abs(U[4][4]) == pytest.approx(P * L ** 2 / (2 * E * I), rel=1e-9)    # θ = PL²/2EI
    start, _ = internal(forces[0])
    assert abs(start[4]) == pytest.approx(P * L, rel=1e-9)                     # M at the root = PL
    assert R[0][2] == pytest.approx(P, rel=1e-9)
    U, _, _ = f.solve({4: (0, 0, 0, 0, M, 0)})
    assert abs(U[4][2]) == pytest.approx(M * L ** 2 / (2 * E * I), rel=1e-9)    # δ = ML²/2EI


def test_simply_supported_and_fixed_fixed_midspan_load():
    L, P = 6.0, 12.0
    nodes, els = _beam(2, L)
    pin = (True, True, True, True, False, False)
    roller = (False, True, True, False, False, False)
    U, forces, R = Frame(nodes, els, {0: pin, 2: roller}).solve({1: (0, 0, -P, 0, 0, 0)})
    assert U[1][2] == pytest.approx(-P * L ** 3 / (48 * E * I), rel=1e-9)       # δ = PL³/48EI
    _, end = internal(forces[0])
    assert abs(end[4]) == pytest.approx(P * L / 4, rel=1e-9)                     # M = PL/4
    assert R[0][2] == pytest.approx(P / 2) and R[2][2] == pytest.approx(P / 2)
    U, forces, _ = Frame(nodes, els, {0: FIXED, 2: FIXED}).solve({1: (0, 0, -P, 0, 0, 0)})
    assert U[1][2] == pytest.approx(-P * L ** 3 / (192 * E * I), rel=1e-9)      # δ = PL³/192EI
    start, end = internal(forces[0])
    assert abs(start[4]) == pytest.approx(P * L / 8, rel=1e-9) and abs(end[4]) == pytest.approx(P * L / 8, rel=1e-9)


def test_axial_and_torsion():
    L, N, T = 3.0, 50.0, 4.0
    nodes, els = _beam(3, L)
    U, forces, _ = Frame(nodes, els, {0: FIXED}).solve({3: (N, 0, 0, T, 0, 0)})
    assert U[3][0] == pytest.approx(N * L / (E * A), rel=1e-9)                   # Δ = NL/EA
    assert U[3][3] == pytest.approx(T * L / (G * J), rel=1e-9)                   # φ = TL/GJ
    assert internal(forces[1])[0][0] == pytest.approx(N)                         # tension positive


def test_vertical_element_and_rotated_beam_give_the_same_answers():
    L, P = 3.0, 5.0
    # Column fixed at the base, horizontal tip load: δ = PL³/3EI about either axis.
    f = Frame([(0, 0, 0), (0, 0, L)], [Element(0, 1, E, G, A, I, 2 * I, J, y_dir=(1, 0, 0))], {0: FIXED})
    U, _, _ = f.solve({1: (P, 0, 0, 0, 0, 0)})
    Ux = U[1][0]
    U, _, _ = f.solve({1: (0, P, 0, 0, 0, 0)})
    assert sorted([abs(Ux), abs(U[1][1])]) == pytest.approx(sorted([P * L ** 3 / (3 * E * I), P * L ** 3 / (6 * E * I)]), rel=1e-9)
    # A cantilever along a 30° plan direction behaves like one along X.
    c, s = np.cos(np.radians(30)), np.sin(np.radians(30))
    f = Frame([(0, 0, 0), (L * c, L * s, 0)], [Element(0, 1, E, G, A, I, I, J)], {0: FIXED})
    U, _, _ = f.solve({1: (0, 0, -P, 0, 0, 0)})
    assert U[1][2] == pytest.approx(-P * L ** 3 / (3 * E * I), rel=1e-9)


def test_portal_frame_sway_matches_slope_deflection():
    """Fixed-base portal, rigid joints, horizontal load H at beam level.

    Slope-deflection, same EI everywhere, members axially rigid; unknowns θ = θB = θC
    (antisymmetric sway) and Δ.  Column BA: M_BA = 4EIθ/h − 6EIΔ/h², M_AB = 2EIθ/h − 6EIΔ/h²;
    beam BC with θC = θB: M_BC = 6EIθ/b.  Joint B: M_BA + M_BC = 0.  Storey shear of the two
    columns: 2·(12EIΔ/h³ − 6EIθ/h²) = H.
    """
    h, b, H = 3.0, 5.0, 10.0
    EI = E * I
    Ksys = np.array([[4 * EI / h + 6 * EI / b, -6 * EI / h ** 2],
                     [-12 * EI / h ** 2, 24 * EI / h ** 3]])
    theta, delta = np.linalg.solve(Ksys, [0.0, H])
    big = 1e6                                                   # axially rigid members
    nodes = [(0, 0, 0), (0, 0, h), (b, 0, h), (b, 0, 0)]
    els = [Element(0, 1, E, G, A * big, I, I, J, y_dir=(0, 1, 0)), Element(1, 2, E, G, A * big, I, I, J),
           Element(3, 2, E, G, A * big, I, I, J, y_dir=(0, 1, 0))]
    U, _, _ = Frame(nodes, els, {0: FIXED, 3: FIXED}).solve({1: (H, 0, 0, 0, 0, 0)})
    assert U[1][0] == pytest.approx(delta, rel=1e-4) and U[2][0] == pytest.approx(delta, rel=1e-4)
    assert abs(U[1][4]) == pytest.approx(abs(theta), rel=1e-4)


# --- Strong column – weak beam ratio (informative, UNVERIFIED factor) -------------------------

def test_joint_ratio_is_reported_from_the_designed_bars_and_never_fails_a_member():
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.capacity import FACTOR
    from archforge.structure.analysis.rc import column_capacity
    from tests.test_structural_analysis import _building
    assert rule('structure.capacity_joints').status != VERIFIED and FACTOR == 1.30
    doc, _ = _building(storeys=2)
    r = analyze(doc)
    joints = r['capacity_joints']
    assert joints and {j['axis'] for j in joints} == {'X', 'Y'}
    by_name = {e['name']: e for e in r['members'].values()}
    # A corner joint by hand: one beam ends there, so ΣMRb = the larger of its top / bottom MRd.
    j = next(j for j in joints if j['x'] in (0.0, 10.0) and j['y'] in (0.0, 8.0) and not j['top'])
    (name,) = j['beams']
    beam = by_name[name]
    assert j['sum_MRb'] == pytest.approx(max(beam['top']['MRd'], beam['bottom']['MRd']), abs=0.1)
    # Where a continuous beam passes through an edge joint, both sides count: hogging one side + sagging the other.
    j = next(j for j in joints if j['axis'] == 'X' and j['x'] == 5.0 and j['y'] == 0.0 and not j['top'])
    beam = by_name[j['beams'][0]]
    assert len(j['beams']) == 1
    assert j['sum_MRb'] == pytest.approx(beam['top']['MRd'] + beam['bottom']['MRd'], abs=0.1)
    assert j['ratio'] == pytest.approx(j['sum_MRc'] / j['sum_MRb'], abs=0.01)
    assert j['meets'] == (j['ratio'] >= FACTOR)
    # A joint below the factor is flagged in the report only: member adequacy is unchanged.
    flagged = [j for j in joints if not j['meets']]
    for j in flagged:
        assert all(by_name[c].get('ok', True) or by_name[c].get('checks') for c in j['columns'])
    from archforge.structure.analysis.report import report_html
    html = report_html(r)
    assert 'ΣM<sub>Rc</sub> / ΣM<sub>Rb</sub>' in html and 'μη επαληθευμένη' in html


def test_bigger_columns_raise_the_joint_ratio():
    from archforge.structure.analysis import analyze
    from tests.test_structural_analysis import _building
    small = {(j['x'], j['y'], j['z'], j['axis']): j['ratio'] for j in analyze(_building(storeys=2, col=0.35)[0])['capacity_joints']}
    big = {(j['x'], j['y'], j['z'], j['axis']): j['ratio'] for j in analyze(_building(storeys=2, col=0.50)[0])['capacity_joints']}
    common = set(small) & set(big)
    assert common and sum(big[k] > small[k] for k in common) > len(common) / 2


def test_critical_zones_and_hooks_are_stated_but_not_verified():
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.report import report_html
    from tests.test_structural_analysis import _building
    for rid in ('structure.critical_zones', 'structure.stirrup_hooks'):
        assert rule(rid).status != VERIFIED
    r = analyze(_building(storeys=1)[0])
    col = next(e for e in r['members'].values() if e['kind'] == 'column')
    assert col['stirrups']['l_crit'] == pytest.approx(max(max(col['b'], col['h']), col['length_m'] / 6, 0.45), abs=0.01)
    html = report_html(r)
    assert 'Κρίσιμες περιοχές' in html and '135°' in html and 'μη επαληθευμένα' in html


# --- Rigid diaphragms (floor slabs) ---------------------------------------------------------

def _columns(xy, h=3.0, I=(1.2e-3, 1.2e-3)):
    nodes, els, sup = [], [], {}
    for x, y in xy:
        b = len(nodes)
        nodes += [(x, y, 0.0), (x, y, h)]
        els.append(Element(b, b + 1, E, G, A, I[0], I[1], J, y_dir=(1, 0, 0)))
        sup[b] = FIXED
    return nodes, els, sup


def test_diaphragm_makes_separate_columns_share_the_load_by_stiffness():
    h, H = 3.0, 30.0
    nodes, els, sup = _columns([(0, 0), (5, 0)], h, I=(1.2e-3, 1.2e-3))
    els[1] = Element(2, 3, E, G, A, 2.4e-3, 2.4e-3, J, y_dir=(1, 0, 0))       # second column twice as stiff
    free = Frame(nodes, els, sup)
    U, _, _ = free.solve({1: (H, 0, 0, 0, 0, 0)})
    assert U[3][0] == pytest.approx(0.0, abs=1e-12)                             # nothing ties them
    tied = Frame(nodes, els, sup, diaphragms=[[1, 3]])
    U, _, R = tied.solve({1: (H, 0, 0, 0, 0, 0)})
    k1, k2 = 3 * E * 1.2e-3 / h ** 3, 3 * E * 2.4e-3 / h ** 3
    assert U[1][0] == pytest.approx(U[3][0], rel=1e-9)
    assert U[1][0] == pytest.approx(H / (k1 + k2), rel=1e-9)                     # parallel springs
    assert -R[0][0] == pytest.approx(H * k1 / (k1 + k2), rel=1e-9) and -R[2][0] == pytest.approx(H * k2 / (k1 + k2), rel=1e-9)


def test_eccentric_load_twists_the_diaphragm_and_stays_in_equilibrium():
    h, H = 3.0, 40.0
    nodes, els, sup = _columns([(0, 0), (6, 0), (0, 4), (6, 4)], h)
    tops = [1, 3, 5, 7]
    f = Frame(nodes, els, sup, diaphragms=[tops])
    U, _, R = f.solve({5: (H, 0, 0, 0, 0, 0)})                                  # load on the y = 4 side
    assert U[5][5] == pytest.approx(U[1][5], rel=1e-9) and abs(U[1][5]) > 0       # one rotation for the slab
    assert U[5][0] > U[1][0]                                                      # the loaded side moves more
    base = [0, 2, 4, 6]
    assert sum(R[b][0] for b in base) == pytest.approx(-H, rel=1e-9)              # Σ Fx
    # Σ Mz about the origin: reactions balance the load's H·4 m lever.
    mz = sum(R[b][5] + nodes[b][0] * R[b][1] - nodes[b][1] * R[b][0] for b in base)
    assert mz == pytest.approx(H * 4.0, rel=1e-6)
    # Rigid in plane: the distance between two slab corners does not change.
    p = [np.add(nodes[n][:2], U[n][:2]) for n in (1, 7)]
    assert np.linalg.norm(p[1] - p[0]) == pytest.approx(math.hypot(6, 4), rel=1e-4)
