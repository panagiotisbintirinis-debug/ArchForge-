"""Numerical failure must never be reported as verified contact equilibrium.

Synthetic solver inputs only; no regulatory sizing values are introduced.
"""
import math

import numpy as np
import pytest

from archforge.structure.soil_pressure import contact_pressure


@pytest.mark.parametrize('failure', ['singular', 'nonfinite', 'no_progress'])
def test_unresolved_contact_is_explicit_and_never_stable(monkeypatch, failure):
    def solve(matrix, residual):
        if failure == 'singular':
            raise np.linalg.LinAlgError('Singular matrix')
        if failure == 'nonfinite':
            return np.full(3, np.nan)
        return np.zeros(3)

    monkeypatch.setattr(np.linalg, 'solve', solve)
    result = contact_pressure(300.0, .6, .6, 2.0, 2.0)
    assert result['stable'] is False
    assert result['converged'] is False
    assert result['method'] == 'numerical_failure'
    assert math.isinf(result['sigma_max'])
    assert result['error']


def test_unresolved_near_corner_grid_case_never_claims_equilibrium():
    result = contact_pressure(300.0, .9999, .9999, 2.0, 2.0)
    assert result['stable'] is False
    assert result['converged'] is False
    assert result['method'] == 'numerical_failure'


def test_analysis_reports_unresolved_contact_without_calling_it_overturning(monkeypatch):
    import archforge.structure.soil_pressure as soil
    from archforge.structure.analysis import analyze
    from tests.test_structural_analysis import _building

    def unresolved(*args):
        return {'sigma_max': math.inf, 'sigma_min': 0., 'contact': 0.,
                'method': 'numerical_failure', 'stable': False,
                'converged': False, 'error': 'Synthetic failed solve'}

    monkeypatch.setattr(soil, 'contact_pressure', unresolved)
    doc, _ = _building(storeys=1)
    result = analyze(doc)
    assert result['verified'] is False
    foundation = result['foundation']
    checked = foundation['footings'] + foundation['strips']
    assert checked
    assert all(not s['pressure_ok'] and s['contact_errors']
               for s in checked)
    assert any('ανεπίλυτος' in warning for warning in result['warnings'])
    assert not any('ανατροπή' in warning for warning in result['warnings'])


def test_unresolved_check_does_not_trigger_the_overturning_strip_rule():
    from archforge.structure.foundation import strip_runs
    # Well-separated synthetic pads: the independent overlap rule does not apply.
    footings = [dict(x=x, y=0., B_m=1., seismic_stable=False,
                     seismic_combo='E', contact_errors={'E': 'Unresolved grid'})
                for x in (0., 10.)]
    assert strip_runs(footings, 'auto') == []
    # A demonstrated outside-base resultant still follows the existing rule.
    for footing in footings:
        footing.pop('contact_errors')
    assert strip_runs(footings, 'auto') == [(0, [0, 1])]
