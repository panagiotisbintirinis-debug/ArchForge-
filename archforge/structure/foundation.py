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
* Strip footings (πεδιλοδοκοί, inverted T): by the setting «Θεμελίωση» —
  *auto*: where two neighbouring pads on one line come closer than 0.50 m
  (or overlap) they become one strip; *strips*: every line of columns is a
  strip (grid); *pads*: never.  Each column's load goes to its strip (half
  to each when it sits on two).  Flange width B = 1.1·ΣN(G+Q) / (σεδ·L),
  ≥ 0.80 m in 5 cm steps, over the length L = first-to-last column + 0.50 m
  each end.  Web bw = max(0.40, column + 0.10), H = max(0.80, l_max/8);
  flange hf = max(0.30, 0.10 + a/2), a = (B − bw)/2.  Flange: transverse
  bars from the cantilever M = σEd·a²/2 (as the pads), distribution Ø10/20.
  Web as a continuous beam under the upward net pressure q = 1.40·ΣN/L:
  M = q·l_max²/10 top and bottom (span / support), As ≥ 0.26·fctm/fyk·bw·d,
  ≥ 4Ø16 each face; shear V = 0.6·q·l_max with stirrups (cot θ = 2.5)
  Ø8/Ø10 at ≤ 150 mm; skin bars 2Ø12 per side when H ≥ 0.70 m.
  Tie beams along a strip are not needed (the strip is the tie).
* Levels: tie beams under the ground floor, top at the column base, 50 cm
  deep; footings below them; strips with their web top at the column base.

Pre-design for review by a structural engineer.
"""
from __future__ import annotations

import math

from archforge.structure.analysis.sections import CONCRETE, FYK, fyd

PROVENANCE = ("Θεμελίωση (προμελέτη): πέδιλα B×B από G+Q και σεδ, οπλισμός πεδίλων από πρόβολο παρειάς (EN 1992-1-1 §9.2.1.1), "
              "συνδετήριες δοκοί EN 1998-5 §5.4.1.2 (±k·α·S·N), 25×50 ≥ 4Ø14, Ø8/20· πεδιλοδοκοί ανεστραμμένου Τ: πέλμα από ΣN/(σεδ·L), "
              "κορμός ως συνεχής δοκός q·l²/10, συνδετήρες cotθ=2,5 — χωρίς διάτρηση, καθιζήσεις, ελαστική έδραση, "
              "κοιτόστρωση — προς έλεγχο από στατικό μηχανικό")
FOUNDATION_TYPES = {"auto": "Αυτόματα: πέδιλα, πεδιλοδοκοί όπου πλησιάζουν", "pads": "Μεμονωμένα πέδιλα με συνδετήριες",
                    "strips": "Πεδιλοδοκοί σε όλους τους άξονες (εσχάρα)"}
STRIP_GAP = 0.50
STRIP_END = 0.50
STRIP_MIN_B = 0.80
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
    # Π1, Π2 … in plan reading order (top-to-bottom, left-to-right), like the columns Κ1, Κ2 … above them.
    footings = sorted(footings, key=lambda f: (-round(float(f["y"]), 1), round(float(f["x"]), 1)))
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
        out.append({"name": f"ΣΔ{n}", "pair": (i, j), "a": (f["x"], f["y"]), "b": (g["x"], g["y"]), "from": f["name"], "to": g["name"],
                    "z": f.get("z", 0.0), "length_m": round(L, 2), "section": f"{TIE_B * 100:.0f}/{TIE_H * 100:.0f}",
                    "N_kN": round(N, 1), "bars": f"{nb}Ø{d}", "As_cm2": round(prov * 1e4, 2), "stirrups": "Ø8/20",
                    "concrete_m3": round(L * TIE_B * TIE_H, 2)})
    return out


def _lines(fts):
    """Lines of footings: ``[(axis, [indices sorted along the line])]`` — axis 0 runs along x, 1 along y."""
    out = []
    for axis in (0, 1):
        key, along = ("y", "x") if axis == 0 else ("x", "y")
        groups = []
        for i in sorted(range(len(fts)), key=lambda i: fts[i][key]):
            if groups and abs(fts[i][key] - fts[groups[-1][0]][key]) <= LINE_TOL:
                groups[-1].append(i)
            else:
                groups.append([i])
        for g in groups:
            if len(g) >= 2:
                out.append((axis, sorted(g, key=lambda i: fts[i][along])))
    return out


def strip_runs(fts, mode):
    """``[(axis, [i, j, …])]`` — runs of footings that become one strip footing."""
    if mode == "pads":
        return []
    runs = []
    for axis, idx in _lines(fts):
        along = "x" if axis == 0 else "y"
        run = [idx[0]]
        for a, b in zip(idx, idx[1:]):
            gap = (fts[b][along] - fts[a][along]) - fts[a]["B_m"] / 2 - fts[b]["B_m"] / 2
            if mode == "strips" or gap < STRIP_GAP:
                run.append(b)
            else:
                if len(run) >= 2:
                    runs.append((axis, run))
                run = [b]
        if len(run) >= 2:
            runs.append((axis, run))
    return runs


def _round_up(v, step=0.05):
    return math.ceil(v / step - 1e-9) * step


def _strip_bars(as_req):
    for d in (16, 18, 20, 22, 25):
        a = math.pi * (d / 1000) ** 2 / 4
        n = max(4, math.ceil(as_req / a - 1e-12))
        if n <= 8:
            return n, d, n * a
    return 8, 25, 8 * math.pi * 0.025 ** 2 / 4


def _stirrups(v_kn, d):
    need = v_kn / (0.9 * d * fyd() * 1000 * 2.5)               # Asw/s (m²/m), cot θ = 2.5
    for dia, s in ((8, 0.15), (10, 0.15), (10, 0.10), (12, 0.10)):
        if 2 * math.pi * (dia / 1000) ** 2 / 4 / s >= need:
            return f"Ø{dia}/{s * 100:g}"
    return "Ø12/10 ⚠"


def design_strips(fts, runs, settings):
    fck, fctm, _E = CONCRETE[settings["concrete"]]
    sigma_allow = float(settings["soil_pressure"])
    share = {}
    for _axis, run in runs:
        for i in run:
            share[i] = share.get(i, 0) + 1
    out = []
    for n, (axis, run) in enumerate(runs, 1):
        along = "x" if axis == 0 else "y"
        cross = "y" if axis == 0 else "x"
        pos = [fts[i][along] for i in run]
        line = sum(fts[i][cross] for i in run) / len(run)
        L = pos[-1] - pos[0] + 2 * STRIP_END
        spans = [b - a for a, b in zip(pos, pos[1:])]
        l_max = max(spans)
        N = sum(float(fts[i]["N_sls_kN"]) / share[i] for i in run)
        n_ed = ULS_RATIO * N
        B = max(STRIP_MIN_B, _round_up(1.1 * N / (sigma_allow * L)))
        col = max(float(fts[i].get("column_m", 0.30)) for i in run)
        bw = max(0.40, _round_up(col + 0.10))
        B = max(B, bw + 0.20)
        a = (B - bw) / 2
        hf = max(0.30, _round_up(0.10 + a / 2))
        H = max(0.80, _round_up(l_max / 8), hf + 0.30)
        sigma_ed = n_ed / (B * L)
        M_t = sigma_ed * a * a / 2
        d_f = hf - 0.06
        as_min_f = max(0.26 * fctm / FYK, 0.0013) * d_f
        dia, s, _p = _mesh(max(M_t / (0.9 * d_f * fyd() * 1000), as_min_f))
        q = n_ed / L
        M = q * l_max ** 2 / 10
        d = H - 0.06
        as_req = max(M / (0.9 * d * fyd() * 1000), max(0.26 * fctm / FYK, 0.0013) * bw * d)
        nb, db, prov = _strip_bars(as_req)
        V = 0.6 * q * l_max
        a_pt = (pos[0] - STRIP_END, line) if axis == 0 else (line, pos[0] - STRIP_END)
        b_pt = (pos[-1] + STRIP_END, line) if axis == 0 else (line, pos[-1] + STRIP_END)
        cols = [fts[i].get("column", "") for i in run]
        out.append({"name": f"ΠΔ{n}", "axis": "x" if axis == 0 else "y", "a": a_pt, "b": b_pt, "members": run,
                    "z": float(fts[run[0]].get("z", 0.0)), "columns": cols,
                    "column_xy": [(fts[i]["x"], fts[i]["y"]) for i in run], "length_m": round(L, 2), "l_max_m": round(l_max, 2),
                    "N_sls_kN": round(N, 1), "N_Ed_kN": round(n_ed, 1), "sigma_kPa": round(N * 1.1 / (B * L), 1),
                    "B_m": round(B, 2), "hf_m": round(hf, 2), "bw_m": round(bw, 2), "H_m": round(H, 2),
                    "flange_mesh": f"Ø{dia}/{s * 100:g}", "flange_dist": "Ø10/20",
                    "M_kNm": round(M, 1), "bars_top": f"{nb}Ø{db}", "bars_bottom": f"{nb}Ø{db}", "As_cm2": round(prov * 1e4, 2),
                    "V_kN": round(V, 1), "stirrups": _stirrups(V, d), "skin": "2×2Ø12" if H >= 0.70 else "—",
                    "section": f"Τ {B * 100:.0f}/{hf * 100:.0f} · {bw * 100:.0f}/{H * 100:.0f}",
                    "concrete_m3": round(L * (B * hf + bw * (H - hf)), 2)})
    return out


def design_foundation(footings, settings):
    fts = design_footings(footings, settings)
    runs = strip_runs(fts, str(settings.get("foundation_type", "auto")))
    strips = design_strips(fts, runs, settings)
    in_strip = {}
    for s in strips:
        for i in s["members"]:
            in_strip.setdefault(i, s["name"])
    # Pads left on their own keep Π1, Π2 … in reading order; footings inside a strip take its name for the ties.
    k = 0
    for i, f in enumerate(fts):
        if i in in_strip:
            f["name"] = in_strip[i]
        else:
            k += 1
            f["name"] = f"Π{k}"
    covered = {frozenset((a, b)) for s in strips for a, b in zip(s["members"], s["members"][1:])}
    ties = [t for t in tie_beams(fts, settings) if frozenset(t["pair"]) not in covered]
    for n, t in enumerate(ties, 1):
        t["name"] = f"ΣΔ{n}"
    pads = [f for i, f in enumerate(fts) if i not in in_strip]
    return {"footings": pads, "ties": ties, "strips": strips, "provenance": PROVENANCE,
            "type": str(settings.get("foundation_type", "auto")),
            "concrete_m3": round(sum(f["concrete_m3"] for f in pads) + sum(t["concrete_m3"] for t in ties)
                                 + sum(s["concrete_m3"] for s in strips), 2)}


def levels(footing):
    """(top, bottom) z of a footing: under the tie beams that sit below the column base."""
    top = float(footing.get("z", 0.0)) - TIE_H
    return top, top - float(footing["h_m"])


def foundation_html(fd):
    if not fd or not (fd["footings"] or fd.get("strips")):
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
            + _strips_html(fd)
            + f"<p>Σκυρόδεμα θεμελίωσης: {fd['concrete_m3']} m³</p><p><i>{PROVENANCE}</i></p>")


def _strips_html(fd):
    if not fd.get("strips"):
        return ""
    rows = "".join(
        f"<tr><td>{s['name']}</td><td>{'–'.join(s['columns'])}</td><td>{s['length_m']}</td><td>{s['section']}</td>"
        f"<td>{s['sigma_kPa']}</td><td>{s['flange_mesh']} + {s['flange_dist']}</td><td>{s['bars_top']} / {s['bars_bottom']}</td>"
        f"<td>{s['stirrups']}</td><td>{s['skin']}</td><td>{s['concrete_m3']}</td></tr>" for s in fd["strips"])
    return ("<h3>Πεδιλοδοκοί (ανεστραμμένο Τ: πέλμα B/hf · κορμός bw/H)</h3><table border=1 cellspacing=0 cellpadding=3>"
            "<tr><th>Πεδιλοδοκός</th><th>Κολόνες</th><th>L (m)</th><th>Διατομή (cm)</th><th>σ (kPa)</th><th>Πέλμα</th>"
            "<th>Κορμός άνω / κάτω</th><th>Συνδετήρες</th><th>Πλευρικά</th><th>m³</th></tr>" + rows + "</table>")
