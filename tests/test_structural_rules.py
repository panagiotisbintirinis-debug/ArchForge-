"""Structural pre-design: every rule has a status, no result passes as verified (owner 15/10).

The second half checks the frame solver against closed-form results of linear
Euler–Bernoulli beam theory (derived from the stiffness equations, no
regulatory value involved).  That checks the solver's mechanics only — not the
loads, factors or code checks built on it.
"""
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
