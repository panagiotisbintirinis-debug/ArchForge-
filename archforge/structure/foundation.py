"""Foundation: pad footings with their reinforcement and the tie beams between them.

Rules (stated so a structural engineer can check them):

* Footings: one centric pad under every supported column, B × B from the
  service load G + Q and the allowable soil pressure (+10 % own weight),
  B ≥ 1.0 m in 5 cm steps, h = max(0.50, 0.3·B) — sized in the analysis.
* Footing reinforcement: design load N_Ed ≈ 1.40 · N(G+Q) (the ratio of
  1.35G + 1.5Q to G + Q for usual floors); net pressure σ = N_Ed / B²; the
  cantilever from the column face a = (B − c)/2 gives M = σ·a²/2 per metre;
  d = h − 60 mm; As = M / (0.9·d·fyd), at least 0.26·fctm/fyk·d and
  0.0013·d per metre (EN 1992-1-1 §9.2.1.1); bottom mesh in both directions,
  Ø12–Ø16 at ≤ 200 mm.  Punching and bending in the column zone are for the
  study (listed, not checked).
* Tie beams (EN 1998-5 §5.4.1.2): every footing is tied in both directions
  to its neighbour on the same line (≤ 30 cm off); axial force
  ±k·α·S·N_Ed,max of the two footings, k = 0.3 (ground B) / 0.4 (C) / 0.6 (D)
  (A: 0.3 kept as a minimum), α = ag/g.  Section 25×50 (minimum), steel
  As = N / fyd but at least 4Ø14, stirrups Ø8/200.  Settlement moments and
  the beam's own bending are for the study.
* Levels: tie beams under the ground floor, top at the column base, 50 cm
  deep; footings below them.

Pre-design for review by a structural engineer.
"""
from __future__ import annotations

import math

from archforge.structure.analysis.sections import CONCRETE, FYK, fyd

PROVENANCE = ("Θεμελίωση (προμελέτη): πέδιλα B×B από G+Q και σεδ, οπλισμός πεδίλων από πρόβολο παρειάς (EN 1992-1-1 §9.2.1.1), "
              "συνδετήριες δοκοί EN 1998-5 §5.4.1.2 (±k·α·S·N), 25×50 ≥ 4Ø14, Ø8/20 — χωρίς διάτρηση, καθιζήσεις, "
              "πεδιλοδοκούς/κοιτόστρωση — προς έλεγχο από στατικό μηχανικό")
ULS_RATIO = 1.40
TIE_B, TIE_H = 0.25, 0.50
TIE_K = {"A": 0.3, "B": 0.3, "C": 0.4, "D": 0.6, "E": 0.6}
LINE_TOL = 0.30
BARS = (12, 14, 16)
SPACINGS = (0.20, 0.175, 0.15, 0.125, 0.10)


def _mesh(as_per_m):
    """Lightest Ø/spacing giving As per metre (spacing ≤ 200 mm)."""
    best = None
    for d in BARS:
        a = math.pi * (d / 1000) ** 2 / 4
        for s in SPACINGS:
            if a / s >= as_per_m:
                if best is None or a / s < best[2]:
                    best = (d, s, a / s)
                break
    return best or (16, 0.10, math.pi * 0.016 ** 2 / 4 / 0.10)


def _bars(as_req, minimum=(4, 14)):
    n0, d0 = minimum
    for d in (14, 16, 18, 20):
        a = math.pi * (d / 1000) ** 2 / 4
        n = max(n0 if d == d0 else 4, math.ceil(as_req / a - 1e-12))
        n += n % 2                                    # symmetric top/bottom
        if n <= 8:
            return n, d, n * a
    return 8, 20, 8 * math.pi * 0.02 ** 2 / 4


def design_footings(footings, settings):
    fck, fctm, _E = CONCRETE[settings["concrete"]]
    out = []
    for i, f in enumerate(footings, 1):
        B, h = float(f["B_m"]), float(f["h_m"])
        c = float(f.get("column_m", 0.30))
        n_ed = ULS_RATIO * float(f["N_sls_kN"])
        sigma = n_ed / (B * B)                         # kPa
        a = max((B - c) / 2, 0.0)
        M = sigma * a * a / 2                          # kNm per m
        d = h - 0.06
        as_min = max(0.26 * fctm / FYK, 0.0013) * d
        as_req = max(M / (0.9 * d * fyd() * 1000), as_min)
        dia, s, prov = _mesh(as_req)
        g = dict(f)
        g.update({"name": f"Π{i}", "N_Ed_kN": round(n_ed, 1), "sigma_kPa": round(sigma, 1), "M_kNm_per_m": round(M, 1),
                  "As_cm2_per_m": round(as_req * 1e4, 2), "mesh": f"Ø{dia}/{s * 100:g}", "mesh_d": dia, "mesh_s": s,
                  "concrete_m3": round(B * B * h, 2)})
        out.append(g)
    return out


def tie_beams(footings, settings):
    from archforge.structure.analysis.seismic import SOIL_TYPE1
    from archforge.structure.analysis.settings import IMPORTANCE, ZONES
    alpha = ZONES[settings["seismic_zone"]] * IMPORTANCE[settings["importance"]]
    S = SOIL_TYPE1[settings["soil"]][0]
    k = TIE_K[settings["soil"]]
    pairs = set()
    for i, f in enumerate(footings):
        for axis, other in ((0, 1), (1, 0)):
            best = None
            for j, g in enumerate(footings):
                if j == i or abs(g[("x", "y")[other]] - f[("x", "y")[other]]) > LINE_TOL:
                    continue
                dist = g[("x", "y")[axis]] - f[("x", "y")[axis]]
                if dist > 0.05 and (best is None or dist < best[0]):
                    best = (dist, j)
            if best:
                pairs.add((i, best[1]))
    out = []
    for n, (i, j) in enumerate(sorted(pairs), 1):
        f, g = footings[i], footings[j]
        N = k * alpha * S * max(f["N_Ed_kN"], g["N_Ed_kN"])
        as_req = N / (fyd() * 1000)
        nb, d, prov = _bars(as_req)
        L = math.dist((f["x"], f["y"]), (g["x"], g["y"]))
        out.append({"name": f"ΣΔ{n}", "a": (f["x"], f["y"]), "b": (g["x"], g["y"]), "from": f["name"], "to": g["name"],
                    "z": f.get("z", 0.0), "length_m": round(L, 2), "section": f"{TIE_B * 100:.0f}/{TIE_H * 100:.0f}",
                    "N_kN": round(N, 1), "bars": f"{nb}Ø{d}", "As_cm2": round(prov * 1e4, 2), "stirrups": "Ø8/20",
                    "concrete_m3": round(L * TIE_B * TIE_H, 2)})
    return out


def design_foundation(footings, settings):
    fts = design_footings(footings, settings)
    ties = tie_beams(fts, settings)
    return {"footings": fts, "ties": ties, "provenance": PROVENANCE,
            "concrete_m3": round(sum(f["concrete_m3"] for f in fts) + sum(t["concrete_m3"] for t in ties), 2)}


def levels(footing):
    """(top, bottom) z of a footing: under the tie beams that sit below the column base."""
    top = float(footing.get("z", 0.0)) - TIE_H
    return top, top - float(footing["h_m"])


def foundation_html(fd):
    if not fd or not fd["footings"]:
        return ""
    rows = "".join(
        f"<tr><td>{f['name']}</td><td>{f.get('column', '')}</td><td>{f['x']}, {f['y']}</td><td>{f['N_sls_kN']} / {f['N_Ed_kN']}</td>"
        f"<td>{f['B_m']:.2f}×{f['B_m']:.2f}</td><td>{f['h_m']:.2f}</td><td>{f['sigma_kPa']}</td><td>{f['M_kNm_per_m']}</td>"
        f"<td>{f['mesh']} κάτω, δύο διευθύνσεις</td><td>{f['concrete_m3']}</td></tr>" for f in fd["footings"])
    ties = "".join(
        f"<tr><td>{t['name']}</td><td>{t['from']} – {t['to']}</td><td>{t['length_m']}</td><td>{t['section']}</td>"
        f"<td>±{t['N_kN']}</td><td>{t['bars']} ({t['As_cm2']} cm²)</td><td>{t['stirrups']}</td></tr>" for t in fd["ties"])
    return ("<h3>Θεμελίωση: πέδιλα</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Πέδιλο</th><th>Κολώνα</th>"
            "<th>Θέση</th><th>N G+Q / Ed (kN)</th><th>B×B (m)</th><th>h (m)</th><th>σ (kPa)</th><th>M (kNm/m)</th>"
            "<th>Οπλισμός</th><th>Σκυρόδεμα m³</th></tr>" + rows + "</table>"
            + ("<h3>Συνδετήριες δοκοί</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Δοκός</th><th>Πέδιλα</th>"
               "<th>Μήκος (m)</th><th>Διατομή</th><th>N (kN)</th><th>Διαμήκης</th><th>Συνδετήρες</th></tr>" + ties + "</table>"
               if ties else "")
            + f"<p>Σκυρόδεμα θεμελίωσης: {fd['concrete_m3']} m³</p><p><i>{PROVENANCE}</i></p>")
