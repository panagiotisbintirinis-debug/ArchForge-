"""Modal response spectrum analysis of the frame (report; the member design still uses the lateral force method).

* Masses: the lumped seismic masses at the nodes (G + ψ2·Q, ``building.py``),
  each acting in the two horizontal directions.  No rigid diaphragm is imposed:
  the torsional inertia comes from where the masses sit in plan.
* Eigenproblem: static condensation onto the mass degrees of freedom through the
  frame's own flexibility F (exact for a lumped-mass model):
  (M^½ F M^½) v = (1/ω²) v, φ = M^-½ v, so φᵀMφ = 1.
* Effective mass in direction r: (φᵀ M r)², torsional about the centre of mass
  with r = (−(y − yc), x − xc); shown as a share of the total (translational)
  or of the polar mass moment (torsional).
* Modal base shear Vn = Meff,n · Sd(Tn) with the design spectrum of
  ``seismic.py``; combined by SRSS and by CQC (Der Kiureghian's correlation with
  ``DAMPING``, the damping the spectrum already assumes, η = 1).
* The modes are listed until the cumulative effective mass reaches
  ``MASS_TARGET`` in both directions — a value from the owner's sample study,
  UNVERIFIED (``structure.modal_mass_target``).
"""
from __future__ import annotations

import math

import numpy as np

from archforge.structure.analysis.seismic import behaviour_factor, design_spectrum, storeys
from archforge.structure.analysis.settings import IMPORTANCE, ZONES

MASS_TARGET = 0.90
DAMPING = 0.05
MIN_MODES = 3


def cqc(values, omegas, zeta=DAMPING):
    """√(Σi Σj ρij vi vj) with ρij = 8ζ²(1+r) r^1.5 / ((1−r²)² + 4ζ² r (1+r)²), r = ωj/ωi."""
    v = np.asarray(values, float)
    w = np.asarray(omegas, float)
    r = w[None, :] / w[:, None]
    rho = 8 * zeta ** 2 * (1 + r) * r ** 1.5 / ((1 - r ** 2) ** 2 + 4 * zeta ** 2 * r * (1 + r) ** 2)
    return float(math.sqrt(max(v @ rho @ v, 0.0)))


def modes(model, frame):
    """All modes of the lumped-mass model, longest period first: (T, ω, φ, dofs, masses) or None."""
    nodes = [n for n in sorted(model.mass) if model.mass[n] > 0]
    dofs = [6 * n + ax for n in nodes for ax in (0, 1)]
    if not dofs:
        return None
    F = frame.flexibility(dofs)
    if F is None:
        return None
    m = np.array([model.mass[n] for n in nodes for _ax in (0, 1)], float)
    sq = np.sqrt(m)
    lam, v = np.linalg.eigh(sq[:, None] * F * sq[None, :])
    order = np.argsort(lam)[::-1]
    lam, v = lam[order], v[:, order]
    keep = lam > 1e-14
    lam, v = lam[keep], v[:, keep]
    phi = v / sq[:, None]
    omega = 1 / np.sqrt(lam)
    return 2 * math.pi / omega, omega, phi, dofs, m


def modal_analysis(model, frame, settings, lateral=None):
    res = modes(model, frame)
    if res is None:
        return {"ok": False}
    T, omega, phi, dofs, m = res
    nodes = [d // 6 for d in dofs]
    ax = np.array([d % 6 for d in dofs])
    xy = np.array([model.nodes[n][:2] for n in nodes], float)
    rx, ry = (ax == 0).astype(float), (ax == 1).astype(float)
    total = float(m[ax == 0].sum())
    c = (m * rx) @ xy / total
    rt = np.where(ax == 0, -(xy[:, 1] - c[1]), xy[:, 0] - c[0])
    polar = float((m * rt * rt).sum())
    Lx, Ly, Lt = (phi.T @ (m * rx)), (phi.T @ (m * ry)), (phi.T @ (m * rt))
    mx, my, mt = Lx ** 2 / total, Ly ** 2 / total, (Lt ** 2 / polar if polar > 0 else 0 * Lt)
    ag = ZONES[settings["seismic_zone"]] * IMPORTANCE[settings["importance"]] * 9.81
    q = behaviour_factor(settings, max(len(storeys(model)), 1))
    Sd = np.array([design_spectrum(t, ag, settings["soil"], q) for t in T])
    rows, cum_x, cum_y = [], 0.0, 0.0
    for i in range(len(T)):
        cum_x += mx[i]
        cum_y += my[i]
        dominant = max((("X", mx[i]), ("Y", my[i]), ("θ", mt[i])), key=lambda p: p[1])[0]
        rows.append({"mode": i + 1, "T_s": round(float(T[i]), 3), "omega": round(float(omega[i]), 2),
                     "mx": round(float(mx[i]), 4), "my": round(float(my[i]), 4), "mt": round(float(mt[i]), 4),
                     "Sd_ms2": round(float(Sd[i]), 3), "dominant": dominant})
        if i + 1 >= MIN_MODES and cum_x >= MASS_TARGET and cum_y >= MASS_TARGET:
            break
    n = len(rows)
    out = {"ok": True, "modes": rows, "n_modes": n, "mass_t": round(total, 1),
           "cum_x": round(float(mx[:n].sum()), 4), "cum_y": round(float(my[:n].sum()), 4), "cum_t": round(float(mt[:n].sum()), 4),
           "target": MASS_TARGET, "q": q}
    out["target_met"] = out["cum_x"] >= MASS_TARGET and out["cum_y"] >= MASS_TARGET
    for d, meff in (("X", mx), ("Y", my)):
        V = meff[:n] * total * Sd[:n]
        out[f"V_{d}_srss_kN"] = round(float(math.sqrt((V ** 2).sum())), 1)
        out[f"V_{d}_cqc_kN"] = round(cqc(V, omega[:n]), 1)
        key = {"X": "Ex", "Y": "Ey"}[d]
        if lateral and key in lateral:
            out[f"V_{d}_lateral_kN"] = float(lateral[key]["Fb_kN"])
    return out


def _signed_cqc(V, omega):
    """Per column of V (modes × components): CQC magnitude with the sign of the dominant mode."""
    V = np.asarray(V, float)
    w = np.asarray(omega, float)
    r = w[None, :] / w[:, None]
    rho = 8 * DAMPING ** 2 * (1 + r) * r ** 1.5 / ((1 - r ** 2) ** 2 + 4 * DAMPING ** 2 * r * (1 + r) ** 2)
    mag = np.sqrt(np.maximum(np.sum((rho @ V) * V, axis=0), 0.0))
    dom = np.argmax(np.abs(V), axis=0)
    sign = np.sign(V[dom, np.arange(V.shape[1])])
    sign[sign == 0] = 1.0
    return mag * sign


def modal_cases(model, frame, settings, n_modes):
    """Design seismic cases from the modal response: {"Ex"/"Ey": (U, element forces, reactions)} plus drift.

    Each mode is solved as a static load case (fn = Γn·Sd(Tn)·M·φn); every displacement,
    end force and reaction component is combined by CQC and given the sign of the mode
    that dominates it (structure.modal_design).  Inter-storey drift is combined per storey.
    """
    res = modes(model, frame)
    if res is None:
        return None
    T, omega, phi, dofs, m = res
    T, omega, phi = T[:n_modes], omega[:n_modes], phi[:, :n_modes]
    ax = np.array([d % 6 for d in dofs])
    ag = ZONES[settings["seismic_zone"]] * IMPORTANCE[settings["importance"]] * 9.81
    levels = storeys(model)
    q = behaviour_factor(settings, max(len(levels), 1))
    Sd = np.array([design_spectrum(t, ag, settings["soil"], q) for t in T])
    nu = 0.5 if settings["importance"] in ("1", "2") else 0.4
    out, drift = {}, {}
    for name, a in (("Ex", 0), ("Ey", 1)):
        gamma = phi.T @ (m * (ax == a))
        Us, Fs, Rs, D = [], [], [], []
        for k in range(len(T)):
            f = m * phi[:, k] * gamma[k] * Sd[k]
            loads = {}
            for dof, v in zip(dofs, f):
                loads.setdefault(dof // 6, np.zeros(6))[dof % 6] += v
            U, F, R = frame.solve(loads)
            Us.append(U.ravel()); Fs.append(np.concatenate(F) if F else np.zeros(0)); Rs.append(R.ravel())
            prev_z, prev_d, d_k = model.base_z, 0.0, []
            for z, ids in levels:
                dl = float(np.mean([U[i][a] for i in ids]))
                d_k.append((dl - prev_d) / (z - prev_z) if z > prev_z else 0.0)
                prev_z, prev_d = z, dl
            D.append(d_k)
        U = _signed_cqc(Us, omega).reshape(-1, 6)
        Fc = _signed_cqc(Fs, omega)
        F = [Fc[12 * i:12 * i + 12] for i in range(len(frame.elements))]
        R = _signed_cqc(Rs, omega).reshape(-1, 6)
        ratio = float(np.max(np.abs(_signed_cqc(D, omega)))) * q * nu if levels else 0.0
        out[name] = (U, F, R)
        drift[name] = {"drift_ratio": round(ratio, 5), "drift_ok": ratio <= 0.005}
    return out, drift
