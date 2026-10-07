"""Reinforced concrete slab design per room panel (pre-design).

Every room is a panel of the slab above it (its ceiling: the floor of the
storey above, or the roof slab).  Rules (stated so a structural engineer can
check them):

* Spans: the room outline on the wall axes, lx ≤ ly.  An edge shared with
  another room of the same storey is continuous; the others rest on walls
  or beams (simply supported).
* Loads (as the frame analysis): g = 25·h + finishes + partitions (floors)
  or roof finishes (roof); q by occupancy / roof access; pd = 1.35 g + 1.5 q.
* ly/lx > 2: one-way slab spanning lx.  Otherwise two-way, load shared by
  the Marcus method: κx = ε⁴/(1+ε⁴), κy = 1-κx (ε = ly/lx), with the Marcus
  torsion reduction ν = 1 - (5/6)·ε²/(1+ε⁴) on the field moments.
* Moments per strip direction by its edges: both continuous — field pl²/24,
  support pl²/12; one continuous — field pl²/14.2, support pl²/8; none —
  field pl²/8.
* Bending: As = Md/(0.9·d·fyd), d = h - 30 mm; As,min = max(0.26 fctm/fyk,
  0.0013)·d per metre; bars Ø8–Ø12 at ≤ min(2h, 250 mm); distribution steel
  ≥ 20 % of the main.  Thickness: span/depth of the short span by EN 1992-1-1
  eq. 7.16 (K = 1.0 / 1.3 / 1.5 for 0 / 1 / 2 continuous edges, ρ = required
  steel), capped at 40·K.

Status: pre-design for review by a structural engineer.  No punching,
cantilevers, openings in the slab or point loads.
"""
from __future__ import annotations

import math

from archforge.structure.analysis.sections import CONCRETE, FYK, fyd

PROVENANCE = ("Προδιάσταση πλακών: μέθοδος Marcus (κατανομή φορτίου και μείωση στρέψης), συντελεστές ροπών "
              "συνεχείας pl²/8 – /12 – /14,2 – /24, EN 1992-1-1 (As,min, l/d εξ. 7.16) — προς έλεγχο από στατικό μηχανικό")
BARS = (8, 10, 12)
SPACINGS = (0.25, 0.20, 0.175, 0.15, 0.125, 0.10, 0.075)


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def _bars(As_per_m, h):
    """Cheapest Ø/spacing with area ≥ As per metre and spacing ≤ min(2h, 250 mm)."""
    best = None
    for d in BARS:
        a = math.pi * (d / 1000) ** 2 / 4
        for s in SPACINGS:
            if s > min(2 * h, 0.25) + 1e-9:
                continue
            prov = a / s
            if prov >= As_per_m:
                if best is None or prov < best[2]:
                    best = (d, s, prov)
                break
    return best or (12, 0.075, math.pi * 0.012 ** 2 / 4 / 0.075)


def _label(bars):
    d, s, _a = bars
    return f"Ø{d}/{s * 100:g}"


def _moments(p, l, cont):
    """(field, support) moments per metre for a strip of span l with ``cont`` continuous edges (0..2)."""
    if cont >= 2:
        return p * l * l / 24, p * l * l / 12
    if cont == 1:
        return p * l * l / 14.2, p * l * l / 8
    return p * l * l / 8, 0.0


def panels(doc):
    """Slab panels: one per room with a concrete slab above it."""
    from archforge.architecture.roof_need import under_pitched_roof
    from archforge.assistant.understanding import read_drawing
    from archforge.project.brief import get_brief
    brief = get_brief(doc)
    if brief and brief["floor_system"] == "timber":
        return []
    out = []
    reading = read_drawing(doc)
    for k, storey in enumerate(reading["storeys"]):
        top = k == len(reading["storeys"]) - 1 or not reading["storeys"][k + 1]["walls"]
        rooms = storey["rooms"]
        for r in rooms:
            if top and under_pitched_roof(doc, r["polygon"], storey["z"]) and not r.get("joists"):
                ceiling = any(e.kind == "room_ceiling" and e.params.get("room_signature") == r["signature"]
                              for e in doc.entities.values())
                if not ceiling:
                    continue                                # attic under a timber roof without a slab
            out.append((storey, r, top, rooms))
    return out


def design_slabs(doc):
    """``{"panels": [...], "provenance": str, "ok": bool}``."""
    from archforge.structure.analysis.settings import OCCUPANCIES, ROOF_ACCESS, get_settings
    s = get_settings(doc)
    h = float(s["slab_thickness"])
    fck, fctm, _E = CONCRETE[s["concrete"]]
    out = []
    for storey, r, top, rooms in panels(doc):
        xs = [p[0] for p in r["polygon"]]
        ys = [p[1] for p in r["polygon"]]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        wx, wy = x1 - x0, y1 - y0
        # Continuous edges: another room on the same storey along that side.
        def neighbour(side):
            for o in rooms:
                if o is r:
                    continue
                oxs = [p[0] for p in o["polygon"]]
                oys = [p[1] for p in o["polygon"]]
                if side in ("x0", "x1"):
                    edge = x0 if side == "x0" else x1
                    if (abs(max(oxs) - edge) < 0.05 if side == "x0" else abs(min(oxs) - edge) < 0.05) and \
                            min(max(oys), y1) - max(min(oys), y0) > 0.5 * wy:
                        return True
                else:
                    edge = y0 if side == "y0" else y1
                    if (abs(max(oys) - edge) < 0.05 if side == "y0" else abs(min(oys) - edge) < 0.05) and \
                            min(max(oxs), x1) - max(min(oxs), x0) > 0.5 * wx:
                        return True
            return False
        cont_x = neighbour("x0") + neighbour("x1")          # continuity of the strip spanning X
        cont_y = neighbour("y0") + neighbour("y1")
        g = 25.0 * h + (float(s["roof_finishes"]) if top else float(s["finishes"]) + float(s["partitions"]))
        q = ROOF_ACCESS[s["roof_access"]][1] if top else OCCUPANCIES[s["occupancy"]][1]
        pd = 1.35 * g + 1.5 * q
        lx, ly = min(wx, wy), max(wx, wy)
        x_short = wx <= wy
        eps = ly / lx if lx > 0 else 1.0
        d = h - 0.03
        as_min = max(0.26 * fctm / FYK, 0.0013) * d
        if eps > 2.0:
            kind = "μιας διεύθυνσης"
            cont_short = cont_x if x_short else cont_y
            mf, ms = _moments(pd, lx, cont_short)
            m_short, s_short, m_long, s_long = mf, ms, 0.0, 0.0
        else:
            kind = "δύο διευθύνσεων (Marcus)"
            kx = eps ** 4 / (1 + eps ** 4)
            nu = 1 - (5 / 6) * eps ** 2 / (1 + eps ** 4)
            cont_short, cont_long = (cont_x, cont_y) if x_short else (cont_y, cont_x)
            mf, ms = _moments(kx * pd, lx, cont_short)
            m_short, s_short = mf * nu, ms
            mf, ms = _moments((1 - kx) * pd, ly, cont_long)
            m_long, s_long = mf * nu, ms

        def steel(M):
            return max(M / (0.9 * d * fyd() * 1000), as_min) if M > 0 else as_min
        main = _bars(steel(m_short), h)
        long_ = _bars(max(steel(m_long), 0.2 * main[2]), h)
        support = _bars(steel(max(s_short, s_long)), h) if max(s_short, s_long) > 0 else None
        # Span/depth (EN 1992-1-1 eq. 7.16) on the short span: K by its continuity, ρ the steel it needs.
        K = (1.0, 1.3, 1.5)[min(cont_short, 2)]
        rho0 = math.sqrt(fck) * 1e-3
        rho = max(steel(m_short) / d, 1e-6)
        if rho <= rho0:
            ld_lim = K * (11 + 1.5 * math.sqrt(fck) * rho0 / rho + 3.2 * math.sqrt(fck) * (rho0 / rho - 1) ** 1.5)
        else:
            ld_lim = K * (11 + 1.5 * math.sqrt(fck) * rho0 / rho)
        ld_lim = round(min(ld_lim, 40.0 * K), 1)
        ld = lx / d
        ok = ld <= ld_lim
        h_req = math.ceil((lx / ld_lim + 0.03) * 100) / 100
        out.append({"storey": storey["name"], "storey_z": float(storey["z"]), "cx": (x0 + x1) / 2, "cy": (y0 + y1) / 2,
                    "bbox": (x0, y0, x1, y1), "main_bars": main[:2], "dist_bars": long_[:2],
                    "room": r["name"], "signature": r["signature"], "lx": round(lx, 2),
                    "ly": round(ly, 2), "kind": kind, "h": h, "pd": round(pd, 2), "g": round(g, 2), "q": q,
                    "M_short": round(m_short, 2), "M_long": round(m_long, 2), "M_support": round(max(s_short, s_long), 2),
                    "bottom_short": _label(main), "bottom_long": _label(long_),
                    "top_support": _label(support) if support else "—", "short_dir": "x" if x_short else "y",
                    "l_d": round(ld, 1), "l_d_lim": ld_lim, "ok": ok, "h_required": max(h_req, 0.15),
                    "text": f"{r['name']}: πλάκα {h * 100:.0f} cm {kind}, κάτω {_label(main)} ({'x' if x_short else 'y'}) / "
                            f"{_label(long_)} ({'y' if x_short else 'x'})" + (f", άνω στηρίξεις {_label(support)}" if support else "")
                            + ("" if ok else f" ⚠ l/d {ld:.0f} > {ld_lim:.0f}: πάχος ≥ {max(h_req, 0.15) * 100:.0f} cm")})
    # Slab marks Πλ1, Πλ2 … (lowest storey first, then plan reading order) — «Π» is for the footings.
    for i, p in enumerate(sorted(out, key=lambda p: (round(p["storey_z"], 1), -round(p["cy"], 1), round(p["cx"], 1))), 1):
        p["mark"] = f"Πλ{i}"
        p["text"] = f"{p['mark']} " + p["text"]
    # Openings (stair wells) in the panels: the bands that replace the cut reinforcement.
    from archforge.structure.slab_openings import openings_in_slabs
    for p in out:
        p["openings"] = []
    for o in openings_in_slabs(doc, out, h):
        next(p for p in out if p["mark"] == o["slab"])["openings"].append(o)
        if o["warning"]:
            next(p for p in out if p["mark"] == o["slab"])["ok"] = False
    return {"panels": out, "ok": all(p["ok"] for p in out), "provenance": PROVENANCE}


def slabs_html(result):
    rows = "".join(
        f"<tr><td>{p['mark']}</td><td>{p['storey']}</td><td>{p['room']}</td><td>{p['lx']}×{p['ly']}</td><td>{p['kind']}</td><td>{p['h'] * 100:.0f}</td>"
        f"<td>{p['pd']}</td><td>{p['bottom_short']} ({p['short_dir']})</td><td>{p['bottom_long']}</td><td>{p['top_support']}</td>"
        f"<td>{p['l_d']} / {p['l_d_lim']:g}</td><td>{'✓' if p['ok'] else '⚠ ≥ ' + format(p['h_required'] * 100, '.0f') + ' cm'}</td></tr>"
        for p in result["panels"])
    return ("<h3>Πλάκες (οπλισμός ανά φάτνωμα)</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Πλάκα</th><th>Όροφος</th><th>Χώρος</th>"
            "<th>lx×ly (m)</th><th>Λειτουργία</th><th>h (cm)</th><th>pd (kN/m²)</th><th>Κάτω κύριος</th><th>Κάτω δευτ.</th>"
            "<th>Άνω στηρίξεις</th><th>l/d</th><th>Κατάσταση</th></tr>" + rows + "</table>"
            + _openings_html(result) + f"<p><i>{result['provenance']}</i></p>") if result["panels"] else ""


def _openings_html(result):
    from archforge.structure.slab_openings import PROVENANCE as OPEN_PROVENANCE
    ops = [o for p in result["panels"] for o in p.get("openings", ())]
    if not ops:
        return ""
    rows = "".join(
        f"<tr><td>{o['slab']}</td><td>{o['stair']}</td><td>{o['size'][0]:.2f}×{o['size'][1]:.2f}</td>"
        f"<td>{'<br>'.join(b['text'] for b in o['bands']) or 'σε τοίχο/δοκό'}</td><td>{o['corner_bars'] or '—'}</td>"
        f"<td>{'⚠ ' + o['warning'] if o['warning'] else '✓'}</td></tr>" for o in ops)
    return ("<h3>Οπές πλακών (σκάλες): ζώνες ενίσχυσης</h3><table border=1 cellspacing=0 cellpadding=3><tr><th>Πλάκα</th>"
            "<th>Σκάλα</th><th>Οπή (m)</th><th>Ζώνες ενίσχυσης</th><th>Γωνίες</th><th>Κατάσταση</th></tr>" + rows + "</table>"
            f"<p><i>{OPEN_PROVENANCE}</i></p>")
