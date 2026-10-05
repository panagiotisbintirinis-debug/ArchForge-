"""Reinforced concrete design of beams and columns (EN 1992-1-1, EN 1998-1 DCM).

Beams: bending with the rectangular stress block (λ 0.8, η 1, εcu 3.5 ‰),
no compression steel (μ ≤ 0.295, else the section is too small);
As,min = max(0.26 fctm/fyk, 0.0013)·b·d and 0.5 fctm/fyk (EN 1998-1
§5.4.3.1.2), As,max = 4 %; bottom steel at supports ≥ 50 % of top; bars in
one layer with clear spacing ≥ max(Ø, 20 mm).  Shear with Ø8 two-leg
stirrups, cotθ = 1, VRd,max check; spacing ≤ min(0.75d, 300 mm) and, in the
critical regions (length h), ≤ min(h/4, 24Ø_w, 225 mm, 8Ø_L).  Deflection by
the span/depth rule (EN 1992-1-1 §7.4.2, K = 1.3 continuous span, 0.4
cantilever).  Capacity-design shear (EN 1998-1 §5.4.2.2) is NOT included.

Columns: N–M interaction by strain compatibility (bars on the perimeter),
biaxial bending by the Bresler criterion (EN 1992-1-1 §5.8.9), minimum
eccentricity max(h/30, 20 mm), slenderness with l0 = L and nominal-curvature
second-order moments when λ > λlim; EN 1998-1 DCM: νd ≤ 0.65, ρ 1 – 4 %, at
least one intermediate bar per side, bar distance ≤ 200 mm, stirrups in the
critical regions ≤ min(b0/2, 175 mm, 8Ø_L).
"""
from __future__ import annotations

import math

from archforge.structure.analysis.sections import BARS, CONCRETE, ES, FYK, bar_area, fcd, fyd

COVER = 0.035          # to the stirrup outer face + stirrup (m), bar centre = COVER + Ø/2
STIRRUP = 8
ASW = 2 * bar_area(STIRRUP)
MU_LIM = 0.295


def _bars_for(As, b, max_n=12, min_d=12):
    """Cheapest one-layer bar group with area ≥ As fitting in width b: (n, Ø, area) or None."""
    best = None
    for d in BARS:
        if d < min_d:
            continue
        for n in range(2, max_n + 1):
            clear = (b - 2 * COVER - n * d / 1000) / (n - 1)
            if clear < max(d / 1000, 0.02):
                break
            a = n * bar_area(d)
            if a >= As:
                if best is None or (a, n) < (best[2], best[0]):
                    best = (n, d, a)
                break
    return best


def _round_s(s):
    return max(0.05, math.floor(s / 0.025 + 1e-9) * 0.025)


def design_beam(b, h, M_sag, M_hog, V, span, settings, cantilever=False):
    cls = settings["concrete"]
    fck, fctm, _E = CONCRETE[cls]
    f_cd, f_yd = fcd(cls), fyd()
    d = h - 0.05
    out = {"b": b, "h": h, "d": round(d, 3), "M_sag": round(M_sag, 1), "M_hog": round(M_hog, 1), "V": round(V, 1),
           "checks": [], "ok": True}
    as_min = max(0.26 * fctm / FYK, 0.0013, 0.5 * fctm / FYK) * b * d
    as_max = 0.04 * b * h
    req = {}
    for side, M in (("bottom", M_sag), ("top", M_hog)):
        mu = M / (b * d * d * f_cd * 1000) if M > 0 else 0.0
        if mu > MU_LIM:
            out["ok"] = False
            out["checks"].append(f"Κάμψη ({'άνοιγμα' if side == 'bottom' else 'στήριξη'}): μ = {mu:.3f} > {MU_LIM} — μικρή διατομή")
            req[side] = None
            continue
        omega = 1 - math.sqrt(1 - 2 * mu)
        req[side] = max(omega * b * d * f_cd / f_yd, as_min)
    if req.get("top") and req.get("bottom") is not None:
        req["bottom"] = max(req["bottom"], 0.5 * req["top"])       # EN 1998-1 §5.4.3.1.2(4)
    for side in ("bottom", "top"):
        if req.get(side) is None:
            continue
        bars = _bars_for(req[side], b)
        if bars is None or bars[2] > as_max:
            out["ok"] = False
            out["checks"].append(f"Οπλισμός {'κάτω' if side == 'bottom' else 'άνω'} δεν χωρά σε μία στρώση — φαρδύτερη/ψηλότερη διατομή")
            continue
        out[side] = {"n": bars[0], "d": bars[1], "As_cm2": round(bars[2] * 1e4, 2), "As_req_cm2": round(req[side] * 1e4, 2)}
    # Shear.
    z = 0.9 * d
    nu1 = 0.6 * (1 - fck / 250)
    v_max = b * z * nu1 * f_cd * 1000 / 2                               # cotθ = 1
    if V > v_max:
        out["ok"] = False
        out["checks"].append(f"Διάτμηση: V = {V:.0f} > VRd,max = {v_max:.0f} kN — μεγαλύτερη διατομή")
    else:
        s_shear = ASW * z * f_yd * 1000 / V if V > 0 else 1.0
        rho_w_min = 0.08 * math.sqrt(fck) / FYK
        dl = min((out[s]["d"] for s in ("bottom", "top") if s in out), default=12)
        s_gen = _round_s(min(s_shear, 0.75 * d, 0.30, ASW / (rho_w_min * b)))
        s_crit = _round_s(min(s_shear, h / 4, 24 * STIRRUP / 1000, 0.225, 8 * dl / 1000))
        out["stirrups"] = {"d": STIRRUP, "s": s_gen, "s_crit": s_crit, "l_crit": round(h, 2)}
    # Deflection (span/depth).
    side = "top" if cantilever else "bottom"
    if side in out and span > 0:
        rho0 = math.sqrt(fck) * 1e-3
        rho = max(out[side]["As_cm2"] / 1e4 / (b * d), 1e-6)
        K = 0.4 if cantilever else 1.3
        if rho <= rho0:
            ld = K * (11 + 1.5 * math.sqrt(fck) * rho0 / rho + 3.2 * math.sqrt(fck) * (rho0 / rho - 1) ** 1.5)
        else:
            ld = K * (11 + 1.5 * math.sqrt(fck) * rho0 / rho)
        ratio = min(1.5, out[side]["As_cm2"] / max(out[side]["As_req_cm2"], 1e-9))
        ld *= ratio
        out["l_d"], out["l_d_lim"] = round(span / d, 1), round(ld, 1)
        if span / d > ld:
            out["ok"] = False
            out["checks"].append(f"Βέλος: l/d = {span / d:.1f} > {ld:.1f} — μεγαλύτερο ύψος")
    utils = []
    for side, M in (("bottom", M_sag), ("top", M_hog)):
        if side in out and M > 0:
            mu = M / (b * d * d * f_cd * 1000)
            utils.append(mu / MU_LIM)
    if V > 0:
        utils.append(V / v_max)
    if "l_d" in out:
        utils.append(out["l_d"] / out["l_d_lim"])
    out["utilisation"] = round(max(utils, default=0.0), 2)
    return out


# ------------------------------------------------------------------ columns
def _layout(b, h, nb, nh, d):
    """Bar coordinates (y along b, z along h) from the centre, nb bars per b-face, nh per h-face."""
    c = COVER + d / 2000
    ys = [-b / 2 + c + (b - 2 * c) * i / (nb - 1) for i in range(nb)]
    zs = [-h / 2 + c + (h - 2 * c) * i / (nh - 1) for i in range(nh)]
    pts = {(y, -h / 2 + c) for y in ys} | {(y, h / 2 - c) for y in ys} | {(-b / 2 + c, z) for z in zs} | {(b / 2 - c, z) for z in zs}
    return sorted(pts)


def _uniaxial(N, B, H, depths, area, f_cd, f_yd):
    """MRd about one axis for compression N (kN, + compression): bars at ``depths`` from the top fibre."""
    def forces(x):
        if x <= H:
            eps = [0.0035 * (x - di) / x for di in depths]
            block = 0.8 * x
        else:
            eps = [0.002 * (x - di) / (x - 3 * H / 7) for di in depths]
            block = H
        block = min(block, H)
        Fc = block * B * f_cd * 1000
        Fs = [area * max(-f_yd, min(f_yd, ES * e)) * 1000 for e in eps]
        n = Fc + sum(Fs)
        m = Fc * (H / 2 - block / 2) + sum(f * (H / 2 - di) for f, di in zip(Fs, depths))
        return n, m
    lo, hi = 1e-4, 50 * H
    n_lo, _ = forces(lo)
    n_hi, _ = forces(hi)
    if N > n_hi or N < n_lo:
        return 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if forces(mid)[0] < N:
            lo = mid
        else:
            hi = mid
    return abs(forces((lo + hi) / 2)[1])


def column_capacity(b, h, nb, nh, d, N, cls):
    f_cd, f_yd = fcd(cls), fyd()
    bars = _layout(b, h, nb, nh, d)
    a = bar_area(d)
    # My: bending about local y → lever along local z (depth h); Mz: lever along b.
    My = _uniaxial(N, b, h, [h / 2 - z for _y, z in bars], a, f_cd, f_yd)
    Mz = _uniaxial(N, h, b, [b / 2 - y for y, _z in bars], a, f_cd, f_yd)
    NRd = (b * h * f_cd + len(bars) * a * f_yd) * 1000
    return My, Mz, NRd, len(bars)


def _bresler(N, My, Mz, MRy, MRz, NRd):
    if MRy <= 0 or MRz <= 0:
        return math.inf
    r = N / NRd if NRd > 0 else 1.0
    if r <= 0.1:
        a = 1.0
    elif r <= 0.7:
        a = 1.0 + (r - 0.1) / 0.6 * 0.5
    else:
        a = min(2.0, 1.5 + (r - 0.7) / 0.3 * 0.5)
    return (abs(My) / MRy) ** a + (abs(Mz) / MRz) ** a


def design_column(b, h, L, actions, V, settings, seismic_actions=()):
    """actions: [(N compression +, My, Mz)] for every combination and end."""
    cls = settings["concrete"]
    fck, _fctm, _E = CONCRETE[cls]
    f_cd, f_yd = fcd(cls), fyd()
    Ac = b * h
    out = {"b": b, "h": h, "checks": [], "ok": True}
    if min(b, h) < 0.25:
        out["checks"].append("Ελάχιστη διάσταση < 25 cm (EN 1998-1 / συνήθης πρακτική)")
        out["ok"] = False
    nu_d = max((N for N, _y, _z in seismic_actions), default=0.0) / (Ac * f_cd * 1000)
    out["nu_d"] = round(nu_d, 2)
    if nu_d > 0.65:
        out["ok"] = False
        out["checks"].append(f"νd = {nu_d:.2f} > 0,65 (EN 1998-1 ΚΠΜ) — μεγαλύτερη διατομή")
    # Design moments with minimum eccentricity and slenderness.
    design = []
    for N, My, Mz in actions:
        Nc = max(N, 0.0)
        e0y, e0z = max(h / 30, 0.02), max(b / 30, 0.02)
        My_d, Mz_d = max(abs(My), Nc * e0y), max(abs(Mz), Nc * e0z)
        n = Nc / (Ac * f_cd * 1000) if Nc > 0 else 0
        for dim, key in ((h, "y"), (b, "z")):
            lam = L / (dim / math.sqrt(12))
            lam_lim = 10.78 / math.sqrt(n) if n > 0 else math.inf
            if lam > lam_lim:
                d_eff = dim - 0.05
                e2 = f_yd / (ES * 0.45 * d_eff) * L ** 2 / 10
                if key == "y":
                    My_d += Nc * e2
                else:
                    Mz_d += Nc * e2
                out["slender"] = True
        design.append((N, My_d, Mz_d))
    out["N_max"] = round(max((a[0] for a in actions), default=0.0), 1)
    out["My_max"] = round(max((a[1] for a in design), default=0.0), 1)
    out["Mz_max"] = round(max((a[2] for a in design), default=0.0), 1)
    candidates = []
    for d in BARS[1:]:
        c = COVER + d / 2000
        for nb in range(3, 8):
            for nh in range(3, 8):
                gb, gh = (b - 2 * c) / (nb - 1), (h - 2 * c) / (nh - 1)
                if gb > 0.20 or gh > 0.20 or min(gb, gh) - d / 1000 < max(d / 1000, 0.02):
                    continue
                As = (2 * nb + 2 * nh - 4) * bar_area(d)
                if 0.01 <= As / Ac <= 0.04:
                    candidates.append((As, nb + nh, nb, nh, d))
    chosen = None
    # Cheapest layout first; the first one that carries every combination wins.
    worst = sorted(design, key=lambda a: -(abs(a[1]) + abs(a[2]) + 0.05 * abs(a[0])))
    for As, _n, nb, nh, d in sorted(candidates):
        util = 0.0
        for N, My_d, Mz_d in worst:
            MRy, MRz, NRd, _c = column_capacity(b, h, nb, nh, d, N, cls)
            util = max(util, _bresler(N, My_d, Mz_d, MRy, MRz, NRd), N / NRd if NRd else 0)
            if util > 1.0:
                break
        if util <= 1.0:
            chosen = (nb, nh, d, As, util)
            break
    if chosen is None:
        out["ok"] = False
        out["checks"].append("Καμία διάταξη οπλισμού (ρ ≤ 4 %) δεν επαρκεί — μεγαλύτερη διατομή")
        out["utilisation"] = 9.99
        return out
    nb, nh, d, As, util = chosen
    out["bars"] = {"n": 2 * nb + 2 * nh - 4, "d": d, "nb": nb, "nh": nh, "As_cm2": round(As * 1e4, 2),
                   "rho": round(As / Ac * 100, 2)}
    # Stirrups: shear and confinement spacing.
    dmin = d
    z = 0.9 * (max(b, h) - 0.05)
    s_shear = ASW * z * f_yd * 1000 / V if V > 0 else 1.0
    s_gen = _round_s(min(s_shear, 20 * dmin / 1000, min(b, h), 0.40))
    b0 = min(b, h) - 2 * COVER
    s_crit = _round_s(min(s_shear, b0 / 2, 0.175, 8 * dmin / 1000))
    out["stirrups"] = {"d": STIRRUP, "s": s_gen, "s_crit": s_crit, "l_crit": round(max(max(b, h), L / 6, 0.45), 2)}
    out["utilisation"] = round(max(util, nu_d / 0.65 if seismic_actions else 0.0), 2)
    return out
