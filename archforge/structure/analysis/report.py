"""HTML report of the structural analysis (shown in the app, printable)."""
from __future__ import annotations

from html import escape

from archforge.structure.analysis.settings import IMPORTANCE, OCCUPANCIES, ROOF_ACCESS, ZONES


def _pct(v):
    return f"{min(float(v), 9.99):.0%}"


def _status(e):
    return "✓" if e.get("ok", True) else "⚠ " + escape("; ".join(e.get("checks", [])) or "ανεπαρκές")


def report_html(r):
    s = r["settings"]
    out = ["<h2>Στατική ανάλυση φέροντος οργανισμού — προμελέτη</h2>"]
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
    if r.get("foundation"):
        from archforge.structure.foundation import foundation_html
        out.append(foundation_html(r["foundation"]))
    if r.get("slabs"):
        from archforge.structure.slabs import slabs_html
        out.append(slabs_html(r["slabs"]))
    if r.get("warnings"):
        out.append("<h3>Παρατηρήσεις</h3><ul>" + "".join(f"<li>{escape(w)}</li>" for w in r["warnings"]) + "</ul>")
    out.append(f"<p><i>{escape(r['provenance'])}</i></p>")
    return "\n".join(out)
