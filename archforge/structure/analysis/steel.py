"""Steel member design (EN 1993-1-1): HEB columns, IPE beams.

Columns: cross-section resistance (linear N–M interaction, conservative),
flexural buckling with Lcr = L about both axes (curve b about y-y, c about
z-z for rolled H sections h/b ≤ 1.2), beam-column interaction eq. 6.61/6.62
with the Annex B (method 2) factors for members not susceptible to torsional
deformation, Cm = 0.9.  Beams: plastic bending Wpl,y·fy (top flange held by
the slab: no lateral-torsional buckling), shear Av·fy/√3, deflection
≤ L/250 under G + Q from the frame analysis.  Lightest profile of the table
that passes every combination.  Connections, local buckling of class 3/4
sections, fire and EN 1998-1 capacity design are NOT included.
"""
from __future__ import annotations

import math

from archforge.structure.analysis.sections import GAMMA_M0, GAMMA_M1, HEB, IPE, STEEL_GRADES, profile


def _chi(lam, alpha):
    phi = 0.5 * (1 + alpha * (lam - 0.2) + lam * lam)
    return min(1.0, 1 / (phi + math.sqrt(max(phi * phi - lam * lam, 0.0))))


def check_column(name, L, actions, grade):
    """actions: [(N compression +, My, Mz)] → utilisation dict."""
    p = profile(name)
    fy = STEEL_GRADES[grade] * 1000
    NRk, MyRk, MzRk = p["A"] * fy, p["Wply"] * fy, p["Wplz"] * fy
    lam1 = 93.9 * math.sqrt(235 / (fy / 1000))
    lam_y, lam_z = L / p["iy"] / lam1, L / p["iz"] / lam1
    chi_y, chi_z = _chi(lam_y, 0.34), _chi(lam_z, 0.49)
    util = 0.0
    for N, My, Mz in actions:
        Nc = max(N, 0.0)
        cs = abs(N) / (NRk / GAMMA_M0) + abs(My) / (MyRk / GAMMA_M0) + abs(Mz) / (MzRk / GAMMA_M0)
        ny, nz = Nc / (chi_y * NRk / GAMMA_M1), Nc / (chi_z * NRk / GAMMA_M1)
        kyy = 0.9 * min(1 + (lam_y - 0.2) * ny, 1 + 0.8 * ny)
        kzz = 0.9 * min(1 + (2 * lam_z - 0.6) * nz, 1 + 1.4 * nz)
        kyz, kzy = 0.6 * kzz, 0.6 * kyy
        e61 = ny + kyy * abs(My) / (MyRk / GAMMA_M1) + kyz * abs(Mz) / (MzRk / GAMMA_M1)
        e62 = nz + kzy * abs(My) / (MyRk / GAMMA_M1) + kzz * abs(Mz) / (MzRk / GAMMA_M1)
        util = max(util, cs, e61, e62)
    return {"profile": name, "utilisation": round(util, 2), "ok": util <= 1.0, "chi_y": round(chi_y, 2),
            "chi_z": round(chi_z, 2), "lambda_y": round(lam_y, 2), "lambda_z": round(lam_z, 2)}


def check_beam(name, M, V, deflection, L, grade):
    p = profile(name)
    fy = STEEL_GRADES[grade] * 1000
    MRd = p["Wply"] * fy / GAMMA_M0
    Av = max(p["A"] - 2 * p["b"] * p["tf"] + (p["tw"] + 2 * p["tf"]) * p["tf"], (p["h"] - 2 * p["tf"]) * p["tw"])
    VRd = Av * fy / math.sqrt(3) / GAMMA_M0
    limit = L / 250 if L > 0 else math.inf
    util = max(M / MRd, V / VRd, deflection / limit if limit else 0.0)
    return {"profile": name, "utilisation": round(util, 2), "ok": util <= 1.0, "M_Rd": round(MRd, 1),
            "V_Rd": round(VRd, 1), "deflection_mm": round(deflection * 1000, 1), "deflection_limit_mm": round(limit * 1000, 1)}


def lightest(kind, check):
    """First profile of the table (by weight) for which ``check(name)`` passes."""
    table = HEB if kind == "column" else IPE
    for name in sorted(table, key=lambda n: table[n][-1]):
        r = check(name)
        if r["ok"]:
            return r
    return check(max(table, key=lambda n: table[n][-1]))
