"""HTML report of the structural analysis (shown in the app, printable)."""
from __future__ import annotations

from html import escape

from archforge.structure.analysis.settings import IMPORTANCE, OCCUPANCIES, ROOF_ACCESS, ZONES
from archforge.structure.rules import STATUS_BANNER, unverified_lines


def _pct(v):
    return f"{min(float(v), 9.99):.0%}"


def _status(e):
    return "✓" if e.get("ok", True) else "⚠ " + escape("; ".join(e.get("checks", [])) or "ανεπαρκές")


def report_html(r):
    s = r["settings"]
    out = ["<h2>Στατική ανάλυση φέροντος οργανισμού — προμελέτη</h2>",
           f"<p style='color:#c0392b'><b>⚠ {escape(STATUS_BANNER)}</b></p>"]
    if r.get("error"):
        out.append(f"<p><b>⚠ {escape(r['error'])}</b></p>")
    out.append(f"<p><b>{escape(r['system_label'])}</b> · {escape(OCCUPANCIES[s['occupancy']][0])} · "
               f"{escape(ROOF_ACCESS[s['roof_access']][0])} · {escape(s['concrete'])} / B500C · {escape(s['steel_grade'])}<br>"
               f"Σεισμική ζώνη {'I' * int(s['seismic_zone'])} (agR {ZONES[s['seismic_zone']]:.2f} g), έδαφος {escape(s['soil'])}, "
               f"σπουδαιότητα Σ{s['importance']} (γI {IMPORTANCE[s['importance']]}) · πλάκα {float(s['slab_thickness']) * 100:.0f} cm, "
               f"επικαλύψεις {s['finishes']} kN/m², διαχωριστικά {s['partitions']} kN/m², σ<sub>εδ</sub> {s['soil_pressure']:.0f} kPa</p>")
    q = r.get("seismic") or {}
    if q.get("ok"):
        rows = "".join(
            f"<tr><td>{d}</td><td>{q[d]['T_s']:.3f}</td><td>{q[d]['Sd_ms2']:.3f}</td><td>{q[d]['lambda']:g}</td>"
            f"<td>{q[d]['Fb_kN']:.1f}</td><td>{q[d]['drift_ratio'] * 1000:.2f} ‰ {'✓' if q[d]['drift_ok'] else '⚠ > 5 ‰'}</td></tr>"
            for d in ("Ex", "Ey") if d in q)
        out.append(f"<h3>Σεισμός (EN 1998-1, ισοδύναμη στατική)</h3><p>Μάζα {float(q['mass_t']):.1f} t · ύψος {q['H_m']} m · "
                   f"q = {q['q']:.2f} · ag = {q['ag_ms2']} m/s² · T(Ct·H<sup>¾</sup>) = {q['T_ct_s']} s</p>"
                   "<table border=1 cellspacing=0 cellpadding=3><tr><th>Διεύθυνση</th><th>T₁ Rayleigh (s)</th>"
                   "<th>Sd (m/s²)</th><th>λ</th><th>Fb (kN)</th><th>Σχετική μετακίνηση ν·dr/h</th></tr>" + rows + "</table>")
    md = r.get("modal") or {}
    if md.get("ok"):
        rows = "".join(
            f"<tr><td>{m['mode']}</td><td>{m['T_s']:.3f}</td><td>{m['omega']:.2f}</td><td>{m['mx']:.1%}</td>"
            f"<td>{m['my']:.1%}</td><td>{m['mt']:.1%}</td><td>{m['Sd_ms2']:.3f}</td><td>{m['dominant']}</td></tr>" for m in md["modes"])
        cmp = " · ".join(
            f"V<sub>{d}</sub> SRSS {md[f'V_{d}_srss_kN']} / CQC {md[f'V_{d}_cqc_kN']} kN"
            + (f" (ισοδύναμη στατική {md[f'V_{d}_lateral_kN']})" if f"V_{d}_lateral_kN" in md else "") for d in ("X", "Y"))
        out.append("<h3>Ιδιομορφές (φασματική ανάλυση) — ενημερωτικά</h3>"
                   "<p><i>Η διαστασιολόγηση των μελών χρησιμοποιεί ακόμη την ισοδύναμη στατική μέθοδο. "
                   f"Κριτήριο {md['target']:.0%} συμμετοχής μάζας: από το δείγμα τεύχους του ιδιοκτήτη, μη επαληθευμένο.</i></p>"
                   "<table border=1 cellspacing=0 cellpadding=3><tr><th>Ιδιομορφή</th><th>T (s)</th><th>ω (rad/s)</th>"
                   "<th>M<sub>x</sub></th><th>M<sub>y</sub></th><th>M<sub>θ</sub></th><th>Sd (m/s²)</th><th>Κυρίαρχη</th></tr>"
                   + rows + f"<tr><td colspan=3><b>Σύνολο {md['n_modes']} ιδιομορφών</b></td><td>{md['cum_x']:.1%}</td>"
                   f"<td>{md['cum_y']:.1%}</td><td>{md['cum_t']:.1%}</td><td colspan=2>"
                   f"{'✓' if md['target_met'] else '⚠ < ' + format(md['target'], '.0%')}</td></tr></table>"
                   f"<p>Τέμνουσα βάσης: {cmp}</p>")
    members = list(r.get("members", {}).values())
    beams = [e for e in members if e["kind"] == "beam"]
    cols = [e for e in members if e["kind"] == "column"]
    if beams:
        out.append("<h3>Δοκοί</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Δοκός</th><th>Διατομή</th>"
                   "<th>Άνοιγμα</th><th>M+ / M− (kNm)</th><th>V (kN)</th><th>Κάτω</th><th>Άνω</th><th>Συνδετήρες</th>"
                   "<th>Αξιοποίηση</th><th>Κατάσταση</th></tr>")
        for e in beams:
            if e["material"] == "steel":
                bottom = top = st = "—"
            else:
                bottom = f"{e['bottom']['n']}Ø{e['bottom']['d']} ({e['bottom']['As_cm2']} cm²)" if "bottom" in e else "—"
                top = f"{e['top']['n']}Ø{e['top']['d']} ({e['top']['As_cm2']} cm²)" if "top" in e else "—"
                st = (f"Ø{e['stirrups']['d']}/{e['stirrups']['s_crit'] * 100:.1f} κρίσιμη {e['stirrups']['l_crit']:.2f} m, "
                      f"Ø{e['stirrups']['d']}/{e['stirrups']['s'] * 100:.1f}") if "stirrups" in e else "—"
            out.append(f"<tr><td>{e['name']}</td><td>{escape(e.get('section', ''))}</td><td>{e.get('span_m', e['length_m'])} m</td>"
                       f"<td>{e['M_sag']} / {e['M_hog']}</td><td>{e['V']}</td><td>{bottom}</td><td>{top}</td><td>{st}</td>"
                       f"<td>{_pct(e.get('utilisation', 0))}</td><td>{_status(e)}</td></tr>")
        out.append("</table>")
    if cols:
        out.append("<h3>Υποστυλώματα</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Κολώνα</th><th>Διατομή</th>"
                   "<th>Ύψος</th><th>N max (kN)</th><th>νd</th><th>Διαμήκης</th><th>Συνδετήρες</th><th>Αξιοποίηση</th>"
                   "<th>Κατάσταση</th></tr>")
        for e in cols:
            if e["material"] == "steel":
                bars = f"λ̄y {e.get('lambda_y', '')} / λ̄z {e.get('lambda_z', '')}"
                st, nu = "—", "—"
            else:
                bars = f"{e['bars']['n']}Ø{e['bars']['d']} (ρ {e['bars']['rho']:.2f} %)" if "bars" in e else "—"
                st = (f"Ø{e['stirrups']['d']}/{e['stirrups']['s_crit'] * 100:.1f} κρίσιμη {e['stirrups']['l_crit']:.2f} m, "
                      f"Ø{e['stirrups']['d']}/{e['stirrups']['s'] * 100:.1f}") if "stirrups" in e else "—"
                nu = f"{e.get('nu_d', 0):.2f}"
            out.append(f"<tr><td>{e['name']}</td><td>{escape(e.get('section', ''))}</td><td>{e['length_m']} m</td>"
                       f"<td>{e['N_max']}</td><td>{nu}</td><td>{bars}</td><td>{st}</td><td>{_pct(e.get('utilisation', 0))}</td>"
                       f"<td>{_status(e)}</td></tr>")
        out.append("</table>")
    if beams or cols:
        out.append("<p><i>Κρίσιμες περιοχές: δοκοί l<sub>cr</sub> = h από κάθε στήριξη· κολόνες l<sub>cr</sub> = max(h<sub>c</sub>, L/6, 0,45 m) "
                   "πάνω και κάτω (L = ύψος μέλους, όχι καθαρό ύψος — προς την ασφαλή πλευρά). Συνδετήρες κλειστοί· "
                   "άγκιστρα 135° μήκους 10Ø κατά το δείγμα τεύχους του ιδιοκτήτη — μη επαληθευμένα, όχι οδηγία κατασκευής.</i></p>")
    if r.get("capacity_joints"):
        from archforge.structure.analysis.capacity import FACTOR
        rows = "".join(
            f"<tr><td>{escape(j['joint'])}{' (κορυφή)' if j['top'] else ''}</td><td>{j['axis']}</td>"
            f"<td>{escape(', '.join(j['beams']))}</td><td>{j['sum_MRb']}</td><td>{escape(', '.join(j['columns']))}</td>"
            f"<td>{j['sum_MRc']}</td><td>{j['ratio']:.2f} {'✓' if j['meets'] else '⚠'}</td></tr>" for j in r["capacity_joints"])
        out.append(f"<h3>Ικανοτικός έλεγχος κόμβων ΣM<sub>Rc</sub> / ΣM<sub>Rb</sub></h3>"
                   f"<p><i>Σύγκριση με {FACTOR:.2f}: τιμή από το δείγμα τεύχους του ιδιοκτήτη, μη επαληθευμένη με το κείμενο "
                   "του κανονισμού — ενημερωτικό, δεν αλλάζει την επάρκεια των μελών. Εξαιρέσεις του κανονισμού (π.χ. κορυφή) "
                   "δεν εφαρμόζονται.</i></p><table border=1 cellspacing=0 cellpadding=3><tr><th>Κόμβος</th><th>Διεύθυνση</th>"
                   "<th>Δοκοί</th><th>ΣM<sub>Rb</sub> (kNm)</th><th>Κολόνες</th><th>ΣM<sub>Rc</sub> (kNm)</th><th>Λόγος</th></tr>"
                   + rows + "</table>")
    if r.get("foundation"):
        from archforge.structure.foundation import foundation_html
        out.append(foundation_html(r["foundation"]))
    if r.get("slabs"):
        from archforge.structure.slabs import slabs_html
        out.append(slabs_html(r["slabs"]))
    if r.get("warnings"):
        out.append("<h3>Παρατηρήσεις</h3><ul>" + "".join(f"<li>{escape(w)}</li>" for w in r["warnings"]) + "</ul>")
    out.append(f"<p><i>{escape(r['provenance'])}</i></p>")
    out.append("<h3>Κατάσταση κανόνων και τιμών του υπολογισμού</h3><ul>"
               + "".join(f"<li>{escape(line)}</li>" for line in unverified_lines()) + "</ul>")
    return "\n".join(out)
