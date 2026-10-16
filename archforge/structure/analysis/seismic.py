"""Seismic action: EN 1998-1 lateral force method with the Greek National Annex.

* Zones (ag,R): Z1 0.16 g, Z2 0.24 g, Z3 0.36 g; ag = γI·ag,R.
* Type 1 elastic spectrum parameters per ground type (EN 1998-1 Πίν. 3.2).
* Behaviour factor (DCM, regular in elevation): RC frames q = 3.0·αu/α1
  (αu/α1 = 1.1 one storey, 1.3 multi-storey); steel moment frames
  q = 4.0 (EN 1998-1 §6.3.2 DCM; αu/α1 not taken into account).
* Period: Rayleigh quotient from the frame's own displacements under the
  height-proportional force pattern (EN 1998-1 §4.3.3.2.2(5)); Ct·H^¾ is
  reported alongside.
* Fb = Sd(T1)·m·λ (λ = 0.85 when T1 ≤ 2TC and more than two storeys),
  distributed as Fi = Fb·zi·mi / Σzj·mj, each storey's force spread over its
  nodes in proportion to their mass.
* Accidental torsion: member effects × δ = 1 + 0.6·x/Le (§4.3.3.2.4).
* Combination: Edx "+" 0.3 Edy and 0.3 Edx "+" Edy (§4.3.3.5.1).
"""
from __future__ import annotations

import math

import numpy as np

from archforge.structure.analysis.settings import IMPORTANCE, ZONES

SOIL_TYPE1 = {"A": (1.0, 0.15, 0.4, 2.0), "B": (1.2, 0.15, 0.5, 2.0), "C": (1.15, 0.20, 0.6, 2.0),
              "D": (1.35, 0.20, 0.8, 2.0), "E": (1.4, 0.15, 0.5, 2.0)}
BETA = 0.2


def behaviour_factor(settings, storeys):
    if settings["system"] == "steel":
        return 4.0
    return 3.0 * (1.1 if storeys <= 1 else 1.3)


def design_spectrum(T, ag, soil, q):
    S, TB, TC, TD = SOIL_TYPE1[soil]
    if T <= TB:
        v = ag * S * (2 / 3 + T / TB * (2.5 / q - 2 / 3))
    elif T <= TC:
        v = ag * S * 2.5 / q
    elif T <= TD:
        v = max(ag * S * 2.5 / q * TC / T, BETA * ag)
    else:
        v = max(ag * S * 2.5 / q * TC * TD / T ** 2, BETA * ag)
    return v


def storeys(model):
    """[(z, [node ids])] of the mass levels above the base, bottom to top."""
    groups = {}
    for nid, m in model.mass.items():
        if m <= 0:
            continue
        z = model.nodes[nid][2]
        key = next((k for k in groups if abs(k - z) <= 0.30), round(z, 2))
        groups.setdefault(key, []).append(nid)
    return sorted((z, ids) for z, ids in groups.items() if z > model.base_z + 0.30)


def lateral_cases(model, frame, settings):
    """Unit-pattern analyses → scaled Ex / Ey nodal load cases plus the seismic report."""
    levels = storeys(model)
    report = {"ok": bool(levels)}
    if not levels:
        return {}, report
    ag = ZONES[settings["seismic_zone"]] * IMPORTANCE[settings["importance"]] * 9.81
    q = behaviour_factor(settings, len(levels))
    total_mass = sum(model.mass.values())
    H = levels[-1][0] - model.base_z
    report.update({"ag_ms2": round(ag, 3), "q": q, "mass_t": round(total_mass, 1), "H_m": round(H, 2),
                   "T_ct_s": round((0.085 if settings["system"] == "steel" else 0.075) * H ** 0.75, 3)})
    cases = {}
    for axis, name in ((0, "Ex"), (1, "Ey")):
        weights = {z: sum(model.mass[n] for n in ids) * (z - model.base_z) for z, ids in levels}
        total_w = sum(weights.values())
        pattern = {}
        for z, ids in levels:
            level_mass = sum(model.mass[n] for n in ids)
            for n in ids:
                vec = np.zeros(6)
                vec[axis] = weights[z] / total_w * model.mass[n] / level_mass
                pattern[n] = vec
        U, _f, _r = frame.solve(pattern)
        num = sum(model.mass[n] * U[n][axis] ** 2 for n in model.mass)
        den = sum(pattern[n][axis] * U[n][axis] for n in pattern) * 9.81 / 9.81
        # Rayleigh: T = 2π √(Σ m d² / Σ F d) with F in kN, m in t → consistent (kN = t·m/s²).
        T = 2 * math.pi * math.sqrt(max(num, 1e-12) / max(den, 1e-12))
        S, TB, TC, TD = SOIL_TYPE1[settings["soil"]]
        lam = 0.85 if (T <= 2 * TC and len(levels) > 2) else 1.0
        Sd = design_spectrum(T, ag, settings["soil"], q)
        Fb = Sd * total_mass * lam
        cases[name] = {n: v * Fb for n, v in pattern.items()}
        # Inter-storey drift under the design forces: ds = q·de (§4.3.4), limit ν·dr ≤ 0.005 h.
        nu = 0.5 if settings["importance"] in ("1", "2") else 0.4
        prev_z, prev_d, drift = model.base_z, 0.0, 0.0
        for z, ids in levels:
            d = q * Fb * float(np.mean([U[n][axis] for n in ids]))
            h = z - prev_z
            drift = max(drift, nu * abs(d - prev_d) / h if h > 0 else 0.0)
            prev_z, prev_d = z, d
        report[name] = {"T_s": round(T, 3), "Sd_ms2": round(Sd, 3), "lambda": lam, "Fb_kN": round(Fb, 1),
                        "drift_ratio": round(drift, 5), "drift_ok": drift <= 0.005}
    # Accidental eccentricity amplification per plan position.
    xs = [model.nodes[n][0] for n in model.mass]
    ys = [model.nodes[n][1] for n in model.mass]
    m = [model.mass[n] for n in model.mass]
    cx, cy = np.average(xs, weights=m), np.average(ys, weights=m)
    report["centre"] = (float(cx), float(cy))
    report["Le"] = (max(xs) - min(xs) or 1.0, max(ys) - min(ys) or 1.0)
    return cases, report


def torsion_factor(report, point, case):
    """δ for a member at plan ``point`` under seismic ``case`` ('Ex' or 'Ey')."""
    if "centre" not in report:
        return 1.0
    cx, cy = report["centre"]
    Lx, Ly = report["Le"]
    if case == "Ex":                       # force along X: eccentricity measured along Y
        return 1 + 0.6 * abs(point[1] - cy) / Ly
    return 1 + 0.6 * abs(point[0] - cx) / Lx
