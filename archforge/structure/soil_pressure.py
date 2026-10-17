"""Contact pressure under a rigid rectangular footing (statics, no tension in the soil).

The footing is B (along x) × L (along y); the resultant of the vertical load N
sits at the eccentricity (ex, ey) from the centre.  Pressure is taken linear in
plan (rigid footing), and the soil cannot pull:

* resultant in the kern, |6ex/B| + |6ey/L| ≤ 1: full contact,
  σ = N/(B·L) · (1 ± 6ex/B ± 6ey/L);
* one eccentricity only, outside the kern: contact over 3·(B/2 − e),
  σmax = 2N / (3·L·(B/2 − e));
* both eccentricities outside the kern: the linear pressure plane over the
  compressed part is solved numerically (equilibrium of force and both
  moments on a fine grid);
* resultant outside the footing: no equilibrium (the footing overturns).

These follow from equilibrium alone; whether a pressure is acceptable (the
allowable σ, how much of the base may lift) is the geotechnical engineer's.
"""
from __future__ import annotations

import math

import numpy as np

GRID = 160          # cells per side for the numerical case


def contact_pressure(N, ex, ey, B, L):
    """→ {"sigma_max", "sigma_min" (kPa), "contact" (share of the base in compression), "method", "stable"}."""
    N, ex, ey, B, L = float(N), abs(float(ex)), abs(float(ey)), float(B), float(L)
    A = B * L
    if N <= 0 or A <= 0:
        return {"sigma_max": 0.0, "sigma_min": 0.0, "contact": 0.0, "method": "none", "stable": N <= 0}
    if ex >= B / 2 or ey >= L / 2:
        return {"sigma_max": math.inf, "sigma_min": 0.0, "contact": 0.0, "method": "overturning", "stable": False}
    kx, ky = 6 * ex / B, 6 * ey / L
    if kx + ky <= 1 + 1e-12:
        return {"sigma_max": N / A * (1 + kx + ky), "sigma_min": N / A * (1 - kx - ky), "contact": 1.0,
                "method": "kern", "stable": True}
    if ey < 1e-12 or ex < 1e-12:
        e, b, l = (ex, B, L) if ey < 1e-12 else (ey, L, B)
        c = 3 * (b / 2 - e)
        return {"sigma_max": 2 * N / (3 * l * (b / 2 - e)), "sigma_min": 0.0, "contact": c / b,
                "method": "partial", "stable": True}
    return _numerical(N, ex, ey, B, L)


def _numerical(N, ex, ey, B, L):
    def unresolved(reason):
        # A failed grid solve is not proof of physical overturning. It also
        # cannot be used as a successful equilibrium/pressure check.
        return {"sigma_max": math.inf, "sigma_min": 0.0, "contact": 0.0,
                "method": "numerical_failure", "stable": False,
                "converged": False, "error": reason}

    xs = (np.arange(GRID) + 0.5) / GRID * B - B / 2
    ys = (np.arange(GRID) + 0.5) / GRID * L - L / 2
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    X, Y = X.ravel(), Y.ravel()
    dA = B * L / GRID ** 2
    target = np.array([N, N * ex, N * ey])
    # Start from the full-contact plane.
    p = np.array([N / (B * L), 12 * N * ex / (B ** 3 * L), 12 * N * ey / (B * L ** 3)])
    converged = False
    for _ in range(200):
        s = p[0] + p[1] * X + p[2] * Y
        if not np.isfinite(s).all():
            return unresolved("Non-finite contact-pressure iterate")
        on = s > 0
        if not on.any():
            return unresolved("No active contact cells in the numerical solve")
        x, y, sv = X[on], Y[on], s[on]
        r = np.array([sv.sum(), (sv * x).sum(), (sv * y).sum()]) * dA - target
        if np.max(np.abs(r) / np.array([N, N * B, N * L])) < 1e-9:
            converged = True
            break
        Jm = np.array([[on.sum(), x.sum(), y.sum()],
                       [x.sum(), (x * x).sum(), (x * y).sum()],
                       [y.sum(), (x * y).sum(), (y * y).sum()]], float) * dA
        try:
            step = np.linalg.solve(Jm, r)
        except np.linalg.LinAlgError:
            return unresolved("Singular contact-pressure Jacobian")
        if not np.isfinite(step).all():
            return unresolved("Non-finite contact-pressure correction")
        p = p - step
    if not converged:
        return unresolved("Contact-pressure iteration limit reached without equilibrium")
    s = p[0] + p[1] * X + p[2] * Y
    on = s > 0
    # The corner of the compressed side carries the peak (exact for the plane).
    smax = p[0] + abs(p[1]) * B / 2 + abs(p[2]) * L / 2
    return {"sigma_max": float(smax), "sigma_min": 0.0, "contact": float(on.mean()),
            "method": "numerical", "stable": True, "converged": True}


def eccentricity(N, Mx, My, Hx, Hy, h):
    """(ex, ey) at the footing underside from the support reactions at the column base.

    ``Mx``, ``My``: reaction moments about global x / y (kNm); ``Hx``, ``Hy``: horizontal reactions (kN);
    ``h``: footing depth (m) — the base shear adds H·h at the underside.
    """
    if N <= 0:
        return 0.0, 0.0
    return -(My + Hx * h) / N, (Mx - Hy * h) / N
