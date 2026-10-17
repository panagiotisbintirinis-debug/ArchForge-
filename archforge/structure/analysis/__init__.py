"""Structural analysis of the building's frame, derived from the Document.

``analyze(doc)`` reads columns, beams, slabs (rooms), walls and the building
data, solves the 3D frame for G, Q and the seismic actions, combines them
(EN 1990: 1.35G + 1.5Q; G + ψ2Q + E with the EN 1998-1 directional
combination) and designs every member: RC reinforcement and section checks,
or the lightest adequate steel profile.  Pad footings are pre-sized from the
service reactions and the allowable soil pressure.

Status: pre-design for review by a licensed structural engineer.  It does not
replace the structural study required for a building permit.
"""
from __future__ import annotations

import math

import numpy as np

from archforge.structure.rules import STATUS_BANNER

PROVENANCE = (STATUS_BANNER + " " + "Προμελέτη φέροντος οργανισμού: EN 1990/1991-1-1, EN 1992-1-1, EN 1993-1-1, EN 1998-1 "
              "με Ελληνικό Εθνικό Προσάρτημα (ζώνες 0,16/0,24/0,36 g), ισοδύναμη στατική μέθοδος, ΚΠΜ — "
              "χωρίς ικανοτικό σχεδιασμό, κόμβους, θεμελίωση σε βάθος, πυροπροστασία· "
              "δεν αντικαθιστά τη στατική μελέτη αδειοδοτημένου μηχανικού")


MAX_PROFILE_ROUNDS = 6      # steel: analyse → choose profiles → analyse again, until nothing changes


def _combos(psi2):
    combos = [("ULS", {"G": 1.35, "Q": 1.5}, False)]
    for ex, ey in ((1.0, 0.3), (0.3, 1.0)):
        for sx in (1, -1):
            for sy in (1, -1):
                combos.append((f"E({'+' if sx > 0 else '−'}{ex:g}Ex{'+' if sy > 0 else '−'}{ey:g}Ey)",
                               {"G": 1.0, "Q": psi2, "Ex": sx * ex, "Ey": sy * ey}, True))
    return combos


def _member_actions(model, member, case_forces, combos, report):
    """Per combination, internal actions along the member: [(combo, s, N, Vy, Vz, My, Mz, seismic)]."""
    from archforge.structure.analysis.fem import internal
    from archforge.structure.analysis.seismic import torsion_factor
    mid = tuple((a + b) / 2 for a, b in zip(member.p1, member.p2))
    delta = {c: torsion_factor(report, mid, c) for c in ("Ex", "Ey")}
    rows = []
    for name, factors, seismic in combos:
        s = 0.0
        for k in member.elements:
            el = model.elements[k]
            L = math.dist(model.nodes[el.n1], model.nodes[el.n2])
            ends = [np.zeros(6), np.zeros(6)]
            for case, f in factors.items():
                if case not in case_forces:
                    continue
                st, en = internal(case_forces[case][k])
                w = f * delta.get(case, 1.0)
                ends[0] += w * np.asarray(st)
                ends[1] += w * np.asarray(en)
            rows.append((name, s, *ends[0][[0, 1, 2, 4, 5]], seismic))
            rows.append((name, s + L, *ends[1][[0, 1, 2, 4, 5]], seismic))
            s += L
    return rows


def _span_info(model, member):
    """Longest span between column supports along a beam, and whether it is a cantilever."""
    col_nodes = {n for m in model.members.values() if m.kind == "column"
                 for k in m.elements for n in (model.elements[k].n1, model.elements[k].n2)}
    other_beam_nodes = {n for m in model.members.values() if m.kind == "beam" and m.id != member.id
                        for k in m.elements for n in (model.elements[k].n1, model.elements[k].n2)}
    seq = [model.elements[member.elements[0]].n1] + [model.elements[k].n2 for k in member.elements]
    pos, s = [0.0], 0.0
    for a, b in zip(seq, seq[1:]):
        s += math.dist(model.nodes[a], model.nodes[b])
        pos.append(s)
    supported = [p for n, p in zip(seq, pos) if n in col_nodes or n in other_beam_nodes]
    if not supported:
        return s, False
    free_start = seq[0] not in col_nodes and seq[0] not in other_beam_nodes
    free_end = seq[-1] not in col_nodes and seq[-1] not in other_beam_nodes
    gaps = [b - a for a, b in zip(supported, supported[1:])]
    cant = max(supported[0] if free_start else 0.0, s - supported[-1] if free_end else 0.0)
    if cant > max(gaps, default=0.0):
        return cant, True
    return max(gaps, default=s), False


def wall_axis(doc, m):
    """'b' or 'h': the side of column ``m`` that runs along the wall it stands in, else None.

    A column inside a wall grows along the wall (a wall-like column stays plastered over),
    never across it."""
    import math as _m
    x, y, z = m.p1
    ux, uy = m.y_dir[0], m.y_dir[1]            # direction of the width (b)
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - z) > 0.05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = _m.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        wx, wy = (x2 - x1) / L, (y2 - y1) / L
        t = (x - x1) * wx + (y - y1) * wy
        if t < -0.05 or t > L + 0.05 or abs(-(x - x1) * wy + (y - y1) * wx) > float(p.get("thickness", 0.2)) / 2 + 0.02:
            continue
        along_b = abs(ux * wx + uy * wy) > 0.7
        across = m.h if along_b else m.b
        if across <= float(p.get("thickness", 0.2)) + 0.02:
            return "b" if along_b else "h"
    return None


MAX_WALL_COLUMN = 1.50      # m: longest side of a column grown along its wall


def _resize_rc(member, settings, design_fn, kind, axis=None):
    """Smallest larger RC section that passes with the same actions (proposal).

    ``axis`` ('b' | 'h', columns only): grow that side alone first — a longer column
    in the wall line instead of a fatter one; then square growth as before."""
    b, h = member.b, member.h
    if kind == "column" and axis in ("b", "h"):
        for step in range(1, 40):
            nb = round(b + 0.05 * step, 2) if axis == "b" else max(b, 0.25)
            nh = round(h + 0.05 * step, 2) if axis == "h" else max(h, 0.25)
            if max(nb, nh) > MAX_WALL_COLUMN + 1e-9:
                break
            if design_fn(nb, nh)["ok"]:
                return round(nb, 2), round(nh, 2)
    for step in range(1, 30):
        if kind == "beam":
            nb = max(b, 0.25) + (0.05 * (step // 6))
            nh = round(h + 0.05 * step, 2)
        else:
            nb = nh = round(max(b, h) + 0.05 * step, 2)
            nb, nh = round(max(b + 0.05 * step, nb), 2), round(max(h + 0.05 * step, nh), 2)
        r = design_fn(nb, nh)
        if r["ok"]:
            return round(nb, 2), round(nh, 2)
        if max(nb, nh) > 1.2:
            break
    return None


def analyze(doc):
    from archforge.structure.analysis.building import build_model
    from archforge.structure.analysis.fem import Frame
    from archforge.structure.analysis.rc import design_beam, design_column
    from archforge.structure.analysis.seismic import lateral_cases
    from archforge.structure.analysis.settings import OCCUPANCIES, SYSTEMS, get_settings
    from archforge.structure.analysis.steel import check_beam, check_column, lightest

    settings = get_settings(doc)
    result = {"ok": True, "members": {}, "footings": [], "warnings": [], "seismic": {}, "settings": settings,
              "provenance": PROVENANCE, "verified": False, "error": None, "system_label": SYSTEMS[settings["system"]]}
    overrides = {}
    for attempt in range(MAX_PROFILE_ROUNDS):
        model = build_model(doc, settings)
        for mid, prof in overrides.items():
            if mid in model.members:
                model.members[mid].profile = prof
        if overrides:
            from archforge.structure.analysis.building import element_props
            for m in model.members.values():
                props, _w = element_props(m, settings)
                for k in m.elements:
                    for key, v in props.items():
                        setattr(model.elements[k], key, v)
        result["warnings"] = list(model.warnings) + list(model.excluded)
        if not model.members:
            result["ok"] = False
            result["error"] = "Δεν υπάρχουν φέροντα υποστυλώματα/δοκοί για ανάλυση"
            return result
        if not model.supports:
            result["ok"] = False
            result["error"] = "Δεν βρέθηκαν στηρίξεις (βάσεις κολωνών)"
            return result
        try:
            frame = Frame(model.nodes, model.elements, model.supports, model.diaphragms)
        except np.linalg.LinAlgError:
            result["ok"] = False
            result["error"] = "Ασταθής φορέας (μηχανισμός): έλεγξε συνδέσεις δοκών–κολωνών και στηρίξεις"
            return result
        case_forces, case_disp = {}, {}
        for case in ("G", "Q"):
            U, F, _R = frame.solve(model.loads[case])
            case_forces[case], case_disp[case] = F, U
        seismic_cases, seismic_report = lateral_cases(model, frame, settings)
        for case, loads in seismic_cases.items():
            U, F, _R = frame.solve(loads)
            case_forces[case], case_disp[case] = F, U
        modal, seismic_reactions = None, None
        if seismic_cases:
            from archforge.structure.analysis.modal import modal_analysis, modal_cases
            modal = modal_analysis(model, frame, settings, seismic_report)
            seismic_report["method"] = "lateral"
            if settings.get("seismic_method") == "modal" and modal.get("ok"):
                mc = modal_cases(model, frame, settings, modal["n_modes"])
                if mc:
                    cases, drift = mc
                    seismic_reactions = {}
                    for case, (U, F, R) in cases.items():
                        case_forces[case], case_disp[case], seismic_reactions[case] = F, U, R
                        seismic_report[case].update(drift[case])
                    seismic_report["method"] = "modal"
        psi2 = OCCUPANCIES[settings["occupancy"]][2]
        combos = _combos(psi2) if seismic_cases else _combos(psi2)[:1]
        # Steel: pick profiles, then analyse once more with them.
        new = {}
        designs = {}
        for m in model.members.values():
            rows = _member_actions(model, m, case_forces, combos, seismic_report)
            designs[m.id] = rows
            if m.material != "steel":
                continue
            if m.kind == "column":
                acts = [(-r[2], r[5], r[6]) for r in rows]
                res = lightest("column", lambda n: check_column(n, m.length, acts, settings["steel_grade"]))
            else:
                M = max(abs(r[5]) for r in rows)
                V = max(abs(r[4]) for r in rows)
                span, _c = _span_info(model, m)
                d0 = _beam_deflection(model, m, case_disp)
                from archforge.structure.analysis.sections import profile as prof_of
                I0 = prof_of(m.profile)["Iy"]
                res = lightest("beam", lambda n: check_beam(n, M, V, d0 * I0 / prof_of(n)["Iy"], span, settings["steel_grade"]))
            if res["profile"] != m.profile:
                from archforge.structure.analysis.sections import profile as prof_of
                # After the first choice a profile only grows: the redistribution of a stiffer frame
                # may ask for more, never for less, so the rounds converge.
                if m.id in overrides and prof_of(res["profile"])["weight"] <= prof_of(m.profile)["weight"]:
                    continue
                new[m.id] = res["profile"]
        if not new or attempt == MAX_PROFILE_ROUNDS - 1:
            break
        overrides.update(new)
    result["seismic"] = seismic_report
    # Design every member with the final forces.
    for m in model.members.values():
        rows = designs[m.id]
        entry = {"id": m.id, "name": m.name, "kind": m.kind, "material": m.material, "length_m": round(m.length, 2),
                 "b": m.b, "h": m.h, "combos": combo_table(rows), "diagram": envelope(rows)}
        source = doc.entities.get(m.id)
        rebar = (source.params.get("rebar") if source is not None else None) or None
        if m.kind == "beam":
            M_sag = max(0.0, max(r[5] for r in rows))
            M_hog = max(0.0, max(-r[5] for r in rows))
            V = max(abs(r[4]) for r in rows)
            span, cant = _span_info(model, m)
            entry.update({"M_sag": round(M_sag, 1), "M_hog": round(M_hog, 1), "V": round(V, 1), "span_m": round(span, 2)})
            entry["inputs"] = {"M_sag": M_sag, "M_hog": M_hog, "V": V, "span": span, "cantilever": cant}
            if m.material == "rc":
                d = design_beam(m.b, m.h, M_sag, M_hog, V, span, settings, cant, rebar=rebar)
                entry.update(d)
                entry["section"] = f"{m.b * 100:.0f}/{m.h * 100:.0f}"
                if not d["ok"]:
                    size = _resize_rc(m, settings, lambda b, h: design_beam(b, h, M_sag, M_hog, V, span, settings, cant), "beam")
                    if size:
                        top = m.p1[2]
                        entry["proposal"] = {"width": size[0], "height": size[1], "z": round(top - size[1], 4)}
            else:
                from archforge.structure.analysis.sections import profile as prof_of
                d0 = _beam_deflection(model, m, case_disp)
                r = check_beam(m.profile, max(M_sag, M_hog), V, d0, span, settings["steel_grade"])
                entry.update(r)
                entry["section"] = m.profile
                p = prof_of(m.profile)
                entry["proposal"] = _steel_proposal(doc, m, p)
        else:
            acts = [(-r[2], r[5], r[6]) for r in rows]
            seis = [(-r[2], r[5], r[6]) for r in rows if r[7]]
            V = max(math.hypot(r[3], r[4]) for r in rows)
            entry.update({"N_max": round(max(a[0] for a in acts), 1), "V": round(V, 1)})
            entry["inputs"] = {"L": m.length, "actions": acts, "V": V, "seismic": seis}
            if m.material == "rc":
                d = design_column(m.b, m.h, m.length, acts, V, settings, seis, rebar=rebar)
                entry.update(d)
                entry["section"] = f"{m.b * 100:.0f}/{m.h * 100:.0f}"
                if not d["ok"]:
                    size = _resize_rc(m, settings, lambda b, h: design_column(b, h, m.length, acts, V, settings, seis), "column",
                                      wall_axis(doc, m))
                    if size:
                        entry["proposal"] = {"width": size[0], "depth": size[1]}
            else:
                from archforge.structure.analysis.sections import profile as prof_of
                r = check_column(m.profile, m.length, acts, settings["steel_grade"])
                entry.update(r)
                entry["section"] = m.profile
                entry["proposal"] = _steel_proposal(doc, m, prof_of(m.profile))
        if entry.get("proposal") is None:
            entry.pop("proposal", None)
        entry["text"] = describe_member(entry)
        result["members"][m.id] = entry
        if not entry.get("ok", True):
            result["ok"] = False
    if seismic_cases:
        result["modal"] = modal
        from archforge.structure.analysis.capacity import joint_checks, joint_review_warnings
        result["capacity_joints"] = joint_checks(model, result["members"], designs, settings)
        result["warnings"].extend(joint_review_warnings(result["capacity_joints"]))
    result["footings"] = _footings(model, frame, settings, seismic_cases, combos, seismic_reactions)
    for f in result["footings"]:
        if not f["pressure_ok"]:
            result["warnings"].append(f"Πέδιλο κάτω από {f['column'] or 'κολόνα'}: σmax G+Q {f['sigma_max_sls_kPa']} kPa > σεδ "
                                      f"ακόμη και με B = {f['B_m']} m — θέλει άλλη θεμελίωση (μηχανικός)")
        if f.get("seismic_stable") is False:
            result["warnings"].append(f"Πέδιλο κάτω από {f['column'] or 'κολόνα'}: στον συνδυασμό {f['seismic_combo']} "
                                      "η συνισταμένη βγαίνει έξω από το πέδιλο (ανατροπή) — έλεγχος από μηχανικό")
    from archforge.structure.foundation import design_foundation
    result["foundation"] = design_foundation(result["footings"], settings)
    from archforge.structure.slabs import design_slabs
    result["slabs"] = design_slabs(doc)
    return result


def combo_table(rows):
    """Per load combination, the largest internal actions along the member:
    [{"combo", "seismic", "N", "V", "My", "Mz"}] (kN, kNm; N compression +, extreme with sign)."""
    out = {}
    for name, _s, N, Vy, Vz, My, Mz, seismic in rows:
        e = out.setdefault(name, {"combo": name, "seismic": bool(seismic), "N": 0.0, "V": 0.0, "My": 0.0, "Mz": 0.0})
        for key, v in (("N", -N), ("My", My), ("Mz", Mz)):
            if abs(v) > abs(e[key]):
                e[key] = float(v)
        e["V"] = max(e["V"], float(math.hypot(Vy, Vz)))
    return [{k: (round(v, 1) if isinstance(v, float) else v) for k, v in e.items()} for e in out.values()]


def envelope(rows):
    """Envelope over every combination along the member: [(s m, My min, My max, V max)] (kNm, kN)."""
    pts = {}
    for _name, s, _N, Vy, Vz, My, _Mz, _seismic in rows:
        k = round(s, 3)
        lo, hi, v = pts.get(k, (math.inf, -math.inf, 0.0))
        pts[k] = (min(lo, My), max(hi, My), max(v, abs(Vz), abs(Vy)))
    return [(k, round(float(lo), 1), round(float(hi), 1), round(float(v), 1)) for k, (lo, hi, v) in sorted(pts.items())]


def _steel_proposal(doc, m, p):
    """Record the designed profile (and its outer size) in the Document when it differs."""
    e = doc.entities.get(m.id)
    if e is None:
        return None
    if str(e.params.get("profile", "")) == m.profile:
        return None
    if m.kind == "column":
        return {"profile": m.profile, "width": round(p["b"], 3), "depth": round(p["h"], 3)}
    return {"profile": m.profile, "width": round(p["b"], 3), "height": round(p["h"], 3), "z": round(m.p1[2] - p["h"], 4)}


def _beam_deflection(model, m, case_disp):
    """Largest vertical deflection relative to the chord under G + Q (m)."""
    seq = [model.elements[m.elements[0]].n1] + [model.elements[k].n2 for k in m.elements]
    w = [float(case_disp["G"][n][2] + case_disp["Q"][n][2]) for n in seq]
    pos = [0.0]
    for a, b in zip(seq, seq[1:]):
        pos.append(pos[-1] + math.dist(model.nodes[a], model.nodes[b]))
    L = pos[-1] or 1.0
    return max(abs(wi - (w[0] + (w[-1] - w[0]) * p / L)) for wi, p in zip(w, pos))


def _footings(model, frame, settings, seismic_cases=None, combos=(), seismic_reactions=None):
    """Pads sized so that σmax under G + Q (with the base moments and shears) stays within σεδ.

    The seismic combinations' contact pressure is reported, not judged: its limit is the
    geotechnical engineer's (structure.footing_contact_pressure).
    """
    from archforge.structure.soil_pressure import contact_pressure, eccentricity
    R = {}
    for case in ("G", "Q"):
        R[case] = frame.solve(model.loads[case])[2]
    for case, loads in (seismic_cases or {}).items():
        R[case] = frame.solve(loads)[2]
    R.update(seismic_reactions or {})                 # modal design: the combined reactions
    out = []
    sigma = float(settings["soil_pressure"])

    def pressure(r, B, h):
        # +10 % footing weight, centric: it adds to N but not to the moments.
        N = 1.1 * float(r[2])
        ex, ey = eccentricity(N, float(r[3]), float(r[4]), float(r[0]), float(r[1]), h)
        return contact_pressure(N, ex, ey, B, B), ex, ey

    for n in sorted(model.supports):
        sls = R["G"][n] + R["Q"][n]
        N = float(sls[2])
        if N <= 0:
            continue
        B = max(1.0, math.ceil(math.sqrt(1.1 * N / sigma) / 0.05) * 0.05)
        while True:
            h = max(0.5, 0.3 * B)
            cp, ex, ey = pressure(sls, B, h)
            if (cp["stable"] and cp["sigma_max"] <= sigma + 1e-9) or B >= 6.0:
                break
            B = round(B + 0.05, 2)
        seismic = None
        for name, factors, is_seismic in combos:
            if not is_seismic or not all(c in R for c in factors):
                continue
            r = sum(f * R[c][n] for c, f in factors.items())
            cps, _ex, _ey = pressure(r, B, h)
            if seismic is None or cps["sigma_max"] > seismic[1]["sigma_max"]:
                seismic = (name, cps)
        col = next((m for m in model.members.values() if m.kind == "column"
                    and math.dist(m.p1, model.nodes[n]) < 0.05), None)
        f = {"node": n, "x": round(model.nodes[n][0], 2), "y": round(model.nodes[n][1], 2),
             "z": round(model.nodes[n][2], 3), "column": col.name if col else "", "column_id": col.id if col else "",
             "column_m": round(max(col.b, col.h), 3) if col else 0.30,
             "N_sls_kN": round(N, 1), "B_m": round(B, 2), "h_m": round(h, 2),
             "e_x_m": round(ex, 3), "e_y_m": round(ey, 3), "sigma_max_sls_kPa": round(cp["sigma_max"], 1),
             "sigma_min_sls_kPa": round(cp["sigma_min"], 1), "contact_sls": round(cp["contact"], 3),
             "pressure_ok": bool(cp["stable"] and cp["sigma_max"] <= sigma + 1e-9)}
        if seismic:
            name, cps = seismic
            f.update({"seismic_combo": name, "sigma_max_seismic_kPa": round(cps["sigma_max"], 1) if cps["stable"] else None,
                      "contact_seismic": round(cps["contact"], 3), "seismic_stable": bool(cps["stable"])})
        out.append(f)
    return out


def describe_member(e):
    """One line in Greek: section, reinforcement / profile, utilisation."""
    head = f"{e['name']} {e.get('section', '')}"
    if e["material"] == "steel":
        body = f"{e.get('profile', '')} · αξιοποίηση {e.get('utilisation', 0):.0%}"
    elif e["kind"] == "beam":
        parts = []
        if "bottom" in e:
            parts.append(f"κάτω {e['bottom']['n']}Ø{e['bottom']['d']}")
        if "top" in e:
            parts.append(f"άνω {e['top']['n']}Ø{e['top']['d']}")
        if "stirrups" in e:
            st = e["stirrups"]
            parts.append(f"συνδ. Ø{st['d']}/{st['s_crit'] * 100:.1f} (κρίσιμη {st['l_crit']:.2f} m), Ø{st['d']}/{st['s'] * 100:.1f}")
        body = ", ".join(parts) + f" · αξιοποίηση {e.get('utilisation', 0):.0%}"
    else:
        parts = []
        if "bars" in e:
            parts.append(f"{e['bars']['n']}Ø{e['bars']['d']} (ρ {e['bars']['rho']:.2f} %)")
        if "stirrups" in e:
            st = e["stirrups"]
            parts.append(f"συνδ. Ø{st['d']}/{st['s_crit'] * 100:.1f} (κρίσιμη {st['l_crit']:.2f} m), Ø{st['d']}/{st['s'] * 100:.1f}")
        body = ", ".join(parts) + f" · νd {e.get('nu_d', 0):.2f} · αξιοποίηση {min(e.get('utilisation', 0), 9.99):.0%}"
    flag = "" if e.get("ok", True) else " ⚠ " + "; ".join(e.get("checks", []))
    return f"{head}: {body}{flag}"


_CACHE = {"key": None, "value": None}


def analysis_key(doc):
    items = []
    for e in doc.entities.values():
        if e.kind in ("structural_column", "structural_beam", "structural_support", "wall", "structural_design"):
            items.append((e.kind, e.id, e.parent_id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    return (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
            tuple(sorted((k, str(v)) for k, v in getattr(doc, "room_data", {}).items())))


def has_structure(doc):
    return any(e.kind in ("structural_column", "structural_beam") for e in doc.entities.values())


def fresh_result(doc):
    """The last analysis if the structure has not changed since, else None (never computes)."""
    return _CACHE["value"] if _CACHE["key"] == analysis_key(doc) else None


def last_result(doc):
    """The last analysis made for this project, even if the structure changed since (its footings stay
    on the drawing until the next run); None if never analysed or another project."""
    value = _CACHE["value"]
    if value is None or _CACHE["key"] is None:
        return None
    members = value.get("members", {})
    if members and not any(mid in doc.entities for mid in members):
        return None
    return value


def analyze_cached(doc):
    key = analysis_key(doc)
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, analyze(doc)
    return _CACHE["value"]
