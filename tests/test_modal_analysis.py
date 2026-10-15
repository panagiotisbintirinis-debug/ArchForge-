"""Modal analysis: eigen-solution against closed forms and identities (no regulatory value involved)."""
import math
import os
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import numpy as np
import pytest

from archforge.structure.analysis.fem import Element, Frame
from archforge.structure.analysis.modal import cqc, modes

E, G, A, J = 30e6, 12.5e6, 0.16, 3.6e-3
FIXED = (True,) * 6


def test_cantilever_with_tip_mass_has_the_closed_form_periods():
    L, m, Iy, Iz = 3.0, 20.0, 2.0e-3, 1.0e-3
    nodes = [(0, 0, 0), (0, 0, L)]
    frame = Frame(nodes, [Element(0, 1, E, G, A, Iy, Iz, J, y_dir=(1, 0, 0))], {0: FIXED})
    model = SimpleNamespace(mass={1: m}, nodes=nodes)
    T, omega, phi, dofs, masses = modes(model, frame)
    # Two sway modes, one per bending stiffness: T = 2π √(m L³ / 3EI).
    expected = sorted([2 * math.pi * math.sqrt(m * L ** 3 / (3 * E * I)) for I in (Iy, Iz)], reverse=True)
    assert list(T) == pytest.approx(expected, rel=1e-9)
    assert np.allclose(phi.T @ np.diag(masses) @ phi, np.eye(2))            # mass-normalised


def test_effective_masses_add_up_to_the_total_over_all_modes():
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.building import build_model
    from archforge.structure.analysis.settings import get_settings
    from tests.test_structural_analysis import _building
    doc, _ = _building(storeys=2)
    model = build_model(doc, get_settings(doc))
    frame = Frame(model.nodes, model.elements, model.supports)
    T, omega, phi, dofs, m = modes(model, frame)
    rx = np.array([1.0 if d % 6 == 0 else 0.0 for d in dofs])
    total = (m * rx).sum()
    assert ((phi.T @ (m * rx)) ** 2).sum() == pytest.approx(total, rel=1e-9)   # completeness of the modes
    # The first period agrees with the lateral force method's Rayleigh estimate of the same frame.
    r = analyze(doc)
    md = r['modal']
    assert md['ok'] and md['target_met'] and md['cum_x'] >= 0.9 and md['cum_y'] >= 0.9
    t_x = next(row['T_s'] for row in md['modes'] if row['dominant'] == 'X')
    assert t_x == pytest.approx(r['seismic']['Ex']['T_s'], rel=0.05)
    assert 0 < md['V_X_cqc_kN'] and 'V_X_lateral_kN' in md


def test_cqc_identities():
    assert cqc([5.0], [10.0]) == pytest.approx(5.0)                             # ρii = 1
    v, w = [3.0, 4.0], [10.0, 100.0]                                            # far apart: → SRSS
    assert cqc(v, w) == pytest.approx(5.0, rel=1e-3)
    assert cqc(v, [10.0, 10.0]) == pytest.approx(7.0)                           # equal ω: full correlation
    assert cqc(v, [10.0, 11.0]) == pytest.approx(cqc(v[::-1], [11.0, 10.0]))    # symmetric


def test_report_lists_the_modes_and_says_design_still_uses_the_lateral_force_method():
    from archforge.core.provenance import VERIFIED, rule
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.report import report_html
    from tests.test_structural_analysis import _building
    html = report_html(analyze(_building(storeys=2)[0]))
    assert 'Ιδιομορφές' in html and 'ισοδύναμη στατική μέθοδο' in html and 'μη επαληθευμένο' in html
    assert rule('structure.modal_mass_target').status != VERIFIED
