"""Footing contact pressure with eccentricity (statics; no regulatory value involved)."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.structure.soil_pressure import contact_pressure, eccentricity


def test_kern_and_partial_contact_closed_forms():
    N, B, L = 600.0, 2.0, 1.5
    r = contact_pressure(N, 0.0, 0.0, B, L)
    assert r['sigma_max'] == pytest.approx(N / (B * L)) and r['contact'] == 1.0
    r = contact_pressure(N, 0.2, 0.1, B, L)                     # 6·0.2/2 + 6·0.1/1.5 = 1.0: edge of the kern
    assert r['method'] == 'kern' and r['sigma_min'] == pytest.approx(0.0, abs=1e-9)
    assert r['sigma_max'] == pytest.approx(2 * N / (B * L))
    r = contact_pressure(N, 0.6, 0.0, B, L)                     # outside the kern, one direction
    assert r['method'] == 'partial'
    assert r['sigma_max'] == pytest.approx(2 * N / (3 * L * (B / 2 - 0.6)))
    assert r['contact'] == pytest.approx(3 * (B / 2 - 0.6) / B)
    assert contact_pressure(N, 1.0, 0.0, B, L)['stable'] is False          # resultant at the edge: overturns


def test_numerical_solution_agrees_with_the_closed_forms():
    from archforge.structure.soil_pressure import _numerical
    N, B, L = 500.0, 2.0, 2.0
    # Inside the kern the numerical plane must equal the linear formula.
    assert _numerical(N, 0.15, 0.1, B, L)['sigma_max'] == pytest.approx(N / (B * L) * (1 + 0.45 + 0.3), rel=2e-3)
    # Outside the kern in one direction it must match the partial-contact formula.
    assert _numerical(N, 0.5, 1e-6, B, L)['sigma_max'] == pytest.approx(2 * N / (3 * L * (B / 2 - 0.5)), rel=5e-3)
    # Biaxial outside the kern: equilibrium holds and the peak exceeds both one-way cases.
    r = contact_pressure(N, 0.4, 0.4, B, L)
    assert r['method'] == 'numerical' and 0 < r['contact'] < 1
    assert r['sigma_max'] > contact_pressure(N, 0.4, 0.0, B, L)['sigma_max']


def test_eccentricity_follows_the_push():
    # Column pushed in +x at its top: the base reaction is −H and the reaction moment −H·Hc about y,
    # so the resultant moves to +x by H·(Hc + h)/N.
    N, H, Hc, h = 400.0, 20.0, 3.0, 0.5
    ex, ey = eccentricity(N, 0.0, -H * Hc, -H, 0.0, h)
    assert ex == pytest.approx(H * (Hc + h) / N) and ey == pytest.approx(0.0)
    ex, ey = eccentricity(N, H * Hc, 0.0, 0.0, -H, h)          # pushed in +y
    assert ey == pytest.approx(H * (Hc + h) / N) and ex == pytest.approx(0.0)


def test_analysis_reports_and_sizes_pads_by_contact_pressure():
    from archforge.structure.analysis import analyze
    from archforge.structure.analysis.report import report_html
    from tests.test_structural_analysis import _building
    doc, _ = _building(storeys=2)
    r = analyze(doc)
    sigma = float(r['settings']['soil_pressure'])
    assert len(r['footings']) == 9
    for f in r['footings']:
        assert f['pressure_ok'] and f['sigma_max_sls_kPa'] <= sigma + 1e-6
        # Never smaller than the centric size, and the reported peak is at least the mean pressure.
        assert f['B_m'] >= math.sqrt(1.1 * f['N_sls_kN'] / sigma) - 0.05
        assert f['sigma_max_sls_kPa'] >= 1.1 * f['N_sls_kN'] / f['B_m'] ** 2 - 0.1
        assert 'seismic_combo' in f and f['seismic_combo'].startswith('E(')
    # Corner pads see the frame's base moments: some eccentricity, and the seismic peak above the service one.
    assert any(abs(f['e_x_m']) + abs(f['e_y_m']) > 0.001 for f in r['footings'])
    assert any(f['seismic_stable'] is False or f['sigma_max_seismic_kPa'] > f['sigma_max_sls_kPa'] for f in r['footings'])
    html = report_html(r)
    assert 'σ<sub>max</sub> G+Q' in html and 'σ<sub>max</sub> σεισμού' in html


def test_low_allowable_pressure_grows_the_pad_and_warns_past_the_limit():
    from archforge.core.commands import AddEntity, CommandStack
    from archforge.core.model import Entity
    from archforge.structure.analysis import analyze
    from tests.test_structural_analysis import _building
    doc, st = _building(storeys=1)
    base = {f['node']: f['B_m'] for f in analyze(doc)['footings']}
    st.execute(AddEntity(Entity('structural_design', {'soil_pressure': 60.0})))
    r = analyze(doc)
    assert all(f['B_m'] >= base[f['node']] for f in r['footings'])
    assert all(f['sigma_max_sls_kPa'] <= 60.0 + 1e-6 for f in r['footings'] if f['pressure_ok'])


def test_pad_reinforcement_uses_the_net_peak_pressure_when_the_pad_has_eccentricity():
    from archforge.structure.foundation import design_footings
    settings = {'concrete': 'C25/30'}
    base = {'x': 0, 'y': 0, 'N_sls_kN': 500.0, 'B_m': 1.8, 'h_m': 0.55, 'column_m': 0.4}
    (centric,) = design_footings([dict(base)], settings)
    (same,) = design_footings([dict(base, e_x_m=0.0, e_y_m=0.0)], settings)
    assert same['sigma_kPa'] == pytest.approx(centric['sigma_kPa']) and same['mesh'] == centric['mesh']
    (ecc,) = design_footings([dict(base, e_x_m=0.10, e_y_m=0.05)], settings)
    n_ed = 1.40 * 500.0
    expected = contact_pressure(n_ed, 0.11, 0.055, 1.8, 1.8)['sigma_max']
    assert ecc['sigma_kPa'] == pytest.approx(expected, abs=0.1) and ecc['sigma_kPa'] > centric['sigma_kPa']
    a = (1.8 - 0.4) / 2
    assert ecc['M_kNm_per_m'] == pytest.approx(expected * a * a / 2, abs=0.1)
    assert ecc['As_cm2_per_m'] >= centric['As_cm2_per_m']
