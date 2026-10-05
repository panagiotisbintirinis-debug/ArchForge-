"""Timber ceiling / floor joists over a room: layout and pre-sizing, derived.

The Document stores only the intent: the room outline (``points``), the
storey (``z``), the nominal spacing, the direction and the use.  Positions,
section and checks are DERIVED, so moving a wall or changing the spacing
re-designs the joists at once.

Rules (stated so a structural engineer can check them):

* Joists span the SHORT direction of the room (``direction`` = 'auto'), or
  the one the user forces ('x' / 'y').  Span L = room outline across that
  direction (wall axes: slightly conservative).
* Division: the length across the joists is divided into equal bays not
  larger than the nominal spacing; the first and last joists sit 5 cm off the
  wall axes.  Each joist is clipped to the room outline.
* Loads (EN 1991-1-1, recommended values, to be confirmed with the Greek
  National Annex):
  - 'ceiling' (non-accessible attic ceiling, category H): g = 0.30 kN/m²
    (plasterboard 2×12.5 mm + insulation) + self-weight, q = 0.40 kN/m²;
  - 'floor' (dwelling, category A): g = 0.70 kN/m² (boarding, finishes,
    ceiling below) + self-weight, q = 2.00 kN/m².
* Checks (EN 1995-1-1, C24, service class 1, k_mod 0.8, γ_M 1.3): bending
  σ ≤ f_m,d, shear τ ≤ f_v,d (k_cr 0.67), instantaneous deflection
  ≤ L/300 under g + q.  Smallest section from the list that passes.

Status: pre-dimensioning for review by a structural engineer.  No creep,
vibration, bearing, connections, fire or seismic checks.
"""
from __future__ import annotations

import math

PROVENANCE = ("Προδιάσταση δοκίδων: EN 1991-1-1 (συνιστώμενες τιμές, κατ. H ταβάνι 0,40 / κατ. A πάτωμα 2,00 kN/m²), "
              "EN 1995-1-1 C24 (k_mod 0,8, γ_M 1,3, κάμψη, διάτμηση, βέλος L/300) — χωρίς ερπυσμό/ταλάντωση/σεισμό, "
              "προς έλεγχο από στατικό μηχανικό")
USES = {"ceiling": ("Ταβάνι (μη βατό, κατ. H)", 0.30, 0.40), "floor": ("Πάτωμα κατοικίας (κατ. A)", 0.70, 2.00)}
DIRECTIONS = ("auto", "x", "y")
F_MK, F_VK, E_MEAN, DENSITY = 24.0, 4.0, 11000.0, 4.2      # C24: MPa, MPa, MPa, kN/m³
K_MOD, GAMMA_M, K_CR = 0.8, 1.3, 0.67
SECTIONS = [(0.05, 0.10), (0.05, 0.12), (0.06, 0.14), (0.06, 0.16), (0.08, 0.16), (0.08, 0.18),
            (0.08, 0.20), (0.10, 0.22), (0.10, 0.24), (0.12, 0.26), (0.12, 0.28)]
EDGE = 0.05
MAX_TIMBER_LENGTH = 6.0      # usual commercial length of sawn C24 joists (m)


def _bbox(points):
    xs = [float(p[0]) for p in points]
    ys = [float(p[1]) for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def span_direction(params):
    """'x' when the joists run along X (they span the X dimension), else 'y'."""
    choice = str(params.get("direction", "auto"))
    if choice in ("x", "y"):
        return choice
    x0, y0, x1, y1 = _bbox(params["points"])
    return "x" if (x1 - x0) <= (y1 - y0) else "y"


def span(params):
    x0, y0, x1, y1 = _bbox(params["points"])
    return (x1 - x0) if span_direction(params) == "x" else (y1 - y0)


def check_section(b, h, L, spacing, use):
    """Bending, shear and deflection of one section: dict with utilisations."""
    _label, g_finish, q = USES[use]
    g = g_finish * spacing + DENSITY * b * h                 # kN/m
    qk = q * spacing
    q_uls = 1.35 * g + 1.5 * qk
    m_ed, v_ed = q_uls * L ** 2 / 8.0, q_uls * L / 2.0
    f_md, f_vd = K_MOD * F_MK / GAMMA_M, K_MOD * F_VK / GAMMA_M
    sigma = m_ed / (b * h ** 2 / 6.0) / 1000.0
    tau = 1.5 * v_ed / (K_CR * b * h) / 1000.0
    defl = 5 * (g + qk) * L ** 4 / (384 * E_MEAN * 1000 * b * h ** 3 / 12.0)
    limit = L / 300.0
    out = {"b": b, "h": h, "q_uls_kn_m": round(q_uls, 2), "m_ed_knm": round(m_ed, 2),
           "sigma_mpa": round(sigma, 2), "f_md_mpa": round(f_md, 2), "tau_mpa": round(tau, 2), "f_vd_mpa": round(f_vd, 2),
           "deflection_mm": round(defl * 1000, 1), "deflection_limit_mm": round(limit * 1000, 1)}
    out["utilisation"] = round(max(sigma / f_md, tau / f_vd, defl / limit), 2)
    out["ok"] = out["utilisation"] <= 1.0
    return out


def size_joists(params):
    """Smallest passing section for the stored spacing; report dict."""
    use = str(params.get("usage", "ceiling"))
    L = span(params)
    spacing = layout_spacing(params)
    chosen = next((c for c in (check_section(b, h, L, spacing, use) for b, h in SECTIONS) if c["ok"]), None)
    if L > MAX_TIMBER_LENGTH:
        chosen = None                         # no single sawn joist that long: practical limit
    report = {"span_m": round(L, 2), "spacing_m": round(spacing, 3), "use": use, "use_label": USES[use][0],
              "direction": span_direction(params), "count": len(positions(params)), "section": chosen,
              "ok": chosen is not None, "provenance": PROVENANCE}
    if chosen is None:
        # Technical proposals when no listed section carries the span.
        report["proposals"] = _proposals(L, use)
    return report


def _proposals(L, use):
    out = []
    if L > MAX_TIMBER_LENGTH:
        out.append(f"Άνοιγμα {L:.2f} m > {MAX_TIMBER_LENGTH:g} m (μήκη ξυλείας εμπορίου): ενδιάμεση δοκός ή στήριξη")
    for s in (0.40, 0.30):
        c = next((c for c in (check_section(b, h, L, s, use) for b, h in SECTIONS) if c["ok"]), None)
        if c:
            out.append(f"Απόσταση αξόνων {s * 100:.0f} cm με διατομή {c['b'] * 100:.0f}/{c['h'] * 100:.0f}")
            break
    half = next((c for c in (check_section(b, h, L / 2, 0.50, use) for b, h in SECTIONS) if c["ok"]), None)
    if half:
        out.append(f"Ενδιάμεση δοκός στο μέσο (άνοιγμα {L / 2:.2f} m): δοκίδες {half['b'] * 100:.0f}/{half['h'] * 100:.0f} ανά 50 cm")
    out.append("Πολύστρωτη ξυλεία (GL24h) ή μεταλλικές δοκοί")
    return out


def layout_spacing(params):
    """Actual spacing after dividing into equal bays not larger than the nominal one."""
    width = _cross_width(params)
    nominal = float(params.get("spacing", 0.50))
    bays = max(1, math.ceil((width - 2 * EDGE) / nominal - 1e-9))
    return (width - 2 * EDGE) / bays


def _cross_width(params):
    x0, y0, x1, y1 = _bbox(params["points"])
    return (y1 - y0) if span_direction(params) == "x" else (x1 - x0)


def _clip(poly, horizontal, c):
    """Intervals of the line (y = c if horizontal else x = c) inside the polygon."""
    hits = []
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if horizontal:
            if (ay > c) != (by > c):
                hits.append(ax + (c - ay) * (bx - ax) / (by - ay))
        elif (ax > c) != (bx > c):
            hits.append(ay + (c - ax) * (by - ay) / (bx - ax))
    hits.sort()
    return [(hits[k], hits[k + 1]) for k in range(0, len(hits) - 1, 2)]


def positions(params):
    """Joist axes in plan: ``[((x1, y1), (x2, y2))]``."""
    poly = [(float(p[0]), float(p[1])) for p in params["points"]]
    x0, y0, x1, y1 = _bbox(poly)
    along_x = span_direction(params) == "x"
    start = (y0 if along_x else x0) + EDGE
    step = layout_spacing(params)
    count = int(round((_cross_width(params) - 2 * EDGE) / step)) + 1
    out = []
    for k in range(count):
        c = start + k * step
        # Nudge off vertices so the clipping is unambiguous.
        for a, b in _clip(poly, along_x, c + 1e-7):
            out.append(((a, c), (b, c)) if along_x else ((c, a), (c, b)))
    return out


def top_z(doc, params):
    """Joists bear on the walls: their top is the top of the storey's walls."""
    z = float(params["z"])
    heights = [float(w.params.get("height", 0.0)) for w in doc.entities.values()
               if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - z) < 0.05]
    return z + (max(heights) if heights else 2.70)


def joists_mesh(doc, params):
    """One box per joist at its derived section (render)."""
    rep = size_joists(params)
    b, h = (rep["section"]["b"], rep["section"]["h"]) if rep["section"] else SECTIONS[-1]
    top = top_z(doc, params)
    verts, tris, roles = [], [], []
    quads = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    for (ax, ay), (bx, by) in positions(params):
        if abs(ay - by) < 1e-9:
            xs, ys = (min(ax, bx), max(ax, bx)), (ay - b / 2, ay + b / 2)
        else:
            xs, ys = (ax - b / 2, ax + b / 2), (min(ay, by), max(ay, by))
        base = len(verts)
        verts += [(x, y, z) for x in xs for y in ys for z in (top - h, top)]
        for q in quads:
            tris += [(base + q[0], base + q[1], base + q[2]), (base + q[0], base + q[2], base + q[3])]
            roles += ["joist", "joist"]
    return tuple(verts), tuple(tris), tuple(roles)
