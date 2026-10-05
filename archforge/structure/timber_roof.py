"""Timber pitched roof with tiles: geometry and rafter pre-sizing from loads.

One ``pitched_roof`` entity holds the intent (footprint, eave height, form,
pitch, overhang, rafter spacing, tiles, snow zone, altitude).  Members are
derived: wall plates, ridge, hips, rafters at spacing (jack rafters cut by
hips), tile battens, and the tiled surface.

Rafter PRE-SIZING (written out so a structural engineer can check it):

* Rafter = simply supported beam over its horizontal span (wall plate to
  ridge/hip), loads per horizontal metre at the rafter spacing.
* Permanent load g (on the slope): tiles 0.55 + battens 0.05 + build-up
  (boarding 0.12, foils 0.02, insulation by type and thickness), converted to
  plan by dividing by cos(pitch).
* Snow (EN 1991-1-3): s = μ1 · s_k with μ1 = 0.8 for 0–30°, 0.8·(60−α)/30 for
  30–60°, 0 above.  s_k = s_k,0 · [1 + (A/917)²] with s_k,0 by Greek snow
  zone I 0.4, II 0.8, III 1.7 kN/m² (values to be confirmed against the
  National Annex by the engineer).  Wind and point loads are NOT included.
* ULS (EN 1990): q = 1.35 g + 1.5 s.  Bending: σ = M/W ≤ f_m,d = k_mod · f_m,k / γ_M
  with C24 f_m,k = 24 MPa, k_mod = 0.9 (snow, service class 1-2), γ_M = 1.3.
* SLS: instantaneous deflection 5 q L⁴ / (384 E I) ≤ L/300 with
  characteristic g + s and E_0,mean = 11 000 MPa.
* The smallest standard section from SECTIONS that passes both is chosen.

Status: pre-dimensioning for review by a structural engineer.  Not a full
EC5 design (no shear, bearing, connections, creep, wind or seismic action).
"""
from __future__ import annotations

import math

PROVENANCE = ("Προδιάσταση ψαλιδιών: ΕΝ 1990/1991-1-3/1995-1-1 (C24, k_mod 0,9, γ_M 1,3, βέλος L/300), "
              "μόνιμα 0,80 kN/m², χιόνι ανά ζώνη — χωρίς άνεμο/σεισμό/συνδέσεις, προς έλεγχο από στατικό μηχανικό")
FORMS = {"gable": "Δίρριχτη", "hip": "Τετράρριχτη", "shed": "Μονόρριχτη"}
TILES = {"roman": ("Κεραμίδι ρωμαϊκού τύπου", 0.33, "#b5532d"), "french": ("Κεραμίδι γαλλικού τύπου", 0.34, "#a8492a"),
         "flat": ("Κεραμίδι επίπεδο", 0.30, "#7b3a24")}
SNOW_SK0 = {1: 0.4, 2: 0.8, 3: 1.7}           # kN/m² at sea level, Greek zones I-III (confirm with NA)
G_ROOF = 0.80                                   # kN/m² on slope without insulation (kept for reference)
# Build-up above the rafters, bottom to top (Greek practice for a ventilated tiled roof).
# name, thickness (m, normal to the slope), weight kN/m², λ W/mK (None = not counted in U)
BOARDING = ("Ταμπλάς (σανίδωμα)", 0.022, 0.12, 0.13)
VAPOUR = ("Φράγμα υδρατμών", 0.002, 0.01, None)
MEMBRANE = ("Διαπνέουσα αδιάβροχη μεμβράνη", 0.002, 0.01, None)
INSULATIONS = {  # name, λ, weight kN/m³
    "xps": ("Εξηλασμένη πολυστερίνη (XPS)", 0.034, 0.35),
    "rockwool": ("Πετροβάμβακας υψηλής πυκνότητας", 0.037, 1.0),
    "none": ("Χωρίς θερμομόνωση", None, 0.0),
}
TILE_WEIGHT, BATTENS_WEIGHT = 0.55, 0.05
RSI_ROOF, RSE_VENTILATED = 0.10, 0.10           # ISO 6946: upward flow; ventilated layer above the membrane
F_MK, K_MOD, GAMMA_M, E_MEAN = 24.0, 0.9, 1.3, 11000.0   # C24 (MPa)
SECTIONS = [(0.06, 0.12), (0.06, 0.14), (0.08, 0.14), (0.08, 0.16), (0.08, 0.18), (0.10, 0.20),
            (0.10, 0.22), (0.12, 0.24), (0.12, 0.26), (0.14, 0.28)]
PLATE, RIDGE = (0.10, 0.10), (0.10, 0.20)      # wall plate, ridge beam (b, h) m
BATTEN = (0.05, 0.03)
TILE_THICK = 0.03


# ------------------------------------------------------------------ loads
def build_up(p):
    """Layers above the rafters, bottom to top: ``[(name, thickness, weight, λ, role)]``."""
    kind = str(p.get("insulation", "xps"))
    t = float(p.get("insulation_thickness", 0.08)) if kind != "none" else 0.0
    name, lam, density = INSULATIONS[kind]
    layers = [(*BOARDING, "boarding"), (*VAPOUR, "vapour_barrier")]
    if t > 0:
        layers.append((name, t, density * t, lam, "insulation"))
    layers.append((*MEMBRANE, "membrane"))
    return layers


def dead_load(p):
    """Permanent load on the slope, kN/m²: tiles, battens and the build-up."""
    return TILE_WEIGHT + BATTENS_WEIGHT + sum(w for _n, _t, w, _l, _r in build_up(p))


def indicative_u(p):
    """Indicative U of the roof (W/m²K): build-up below the ventilated layer only."""
    r = RSI_ROOF + RSE_VENTILATED + sum(t / lam for _n, t, _w, lam, _r in build_up(p) if lam)
    return 1.0 / r


def snow_load(params):
    pitch = float(params["pitch"])
    mu = 0.8 if pitch <= 30 else (0.8 * (60 - pitch) / 30 if pitch < 60 else 0.0)
    sk = SNOW_SK0[int(params.get("snow_zone", 2))] * (1 + (float(params.get("altitude", 0.0)) / 917.0) ** 2)
    return mu * sk, sk, mu


def rafter_span(params):
    """Horizontal span of the longest rafter (wall plate to ridge), metres."""
    w = abs(float(params["x1"]) - float(params["x0"]))
    d = abs(float(params["y1"]) - float(params["y0"]))
    short = min(w, d)
    return short if params.get("roof_form") == "shed" else short / 2


def size_rafter(params):
    """Pre-size rafters; returns a report dict (see module docstring)."""
    alpha = math.radians(float(params["pitch"]))
    spacing = float(params["rafter_spacing"])
    L = rafter_span(params)
    s, sk, mu = snow_load(params)
    g_slope = dead_load(params)
    g_plan = g_slope / math.cos(alpha)                      # kN/m² per plan area
    q_uls = (1.35 * g_plan + 1.5 * s) * spacing           # kN/m along the plan span
    q_sls = (g_plan + s) * spacing
    f_md = K_MOD * F_MK / GAMMA_M                          # MPa
    m_ed = q_uls * L ** 2 / 8.0                             # kNm
    chosen = None
    for b, h in SECTIONS:
        w_mod = b * h ** 2 / 6.0                            # m³
        i_mod = b * h ** 3 / 12.0                           # m⁴
        sigma = m_ed / w_mod / 1000.0                       # MPa
        # Deflection along the slope length with the load component normal to it.
        l_slope = L / math.cos(alpha)
        q_n = q_sls * math.cos(alpha) ** 2                  # kN/m normal to the rafter, per slope length
        defl = 5 * q_n * l_slope ** 4 / (384 * E_MEAN * 1000 * i_mod)
        limit = l_slope / 300.0
        if sigma <= f_md and defl <= limit:
            chosen = {"b": b, "h": h, "sigma_mpa": round(sigma, 2), "f_md_mpa": round(f_md, 2),
                      "utilisation": round(sigma / f_md, 2), "deflection_mm": round(defl * 1000, 1),
                      "deflection_limit_mm": round(limit * 1000, 1)}
            break
    return {"span_m": round(L, 2), "spacing_m": spacing, "g_kn_m2": round(g_slope, 2), "snow_kn_m2": round(s, 2),
            "sk_kn_m2": round(sk, 2), "mu1": round(mu, 2), "q_uls_kn_m": round(q_uls, 2), "m_ed_knm": round(m_ed, 2),
            "section": chosen, "ok": chosen is not None, "provenance": PROVENANCE}


def rafter_section(params):
    r = size_rafter(params)
    return (r["section"]["b"], r["section"]["h"]) if r["section"] else SECTIONS[-1]


# --------------------------------------------------------------- geometry
def _frame(p):
    x0, x1 = sorted((float(p["x0"]), float(p["x1"])))
    y0, y1 = sorted((float(p["y0"]), float(p["y1"])))
    return x0, y0, x1, y1


def planes(p):
    """Roof planes in plan: ``[(polygon_xy, eave_a, eave_b, uphill_unit)]``.

    Polygons include the overhang.  The eave edge is ``eave_a -> eave_b``
    (at eave height before the overhang drop) and ``uphill`` points to the
    ridge.  Heights follow z = eave_z + distance_from_wall_line * tan(pitch).
    """
    x0, y0, x1, y1 = _frame(p)
    o = float(p.get("overhang", 0.5))
    form = p.get("roof_form", "gable")
    along_x = (x1 - x0) >= (y1 - y0)
    X0, Y0, X1, Y1 = x0 - o, y0 - o, x1 + o, y1 + o
    if form == "shed":
        if along_x:
            return [([(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)], (x0, y0), (x1, y0), (0.0, 1.0))]
        return [([(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)], (x0, y1), (x0, y0), (1.0, 0.0))]
    if along_x:
        ym = (y0 + y1) / 2
        half = (y1 - y0) / 2
        if form == "hip":
            rx0, rx1 = x0 + half, x1 - half
            if rx1 < rx0:
                rx0 = rx1 = (x0 + x1) / 2
            return [([(X0, Y0), (X1, Y0), (rx1, ym), (rx0, ym)], (x0, y0), (x1, y0), (0.0, 1.0)),
                    ([(X1, Y1), (X0, Y1), (rx0, ym), (rx1, ym)], (x1, y1), (x0, y1), (0.0, -1.0)),
                    ([(X0, Y1), (X0, Y0), (rx0, ym)], (x0, y1), (x0, y0), (1.0, 0.0)),
                    ([(X1, Y0), (X1, Y1), (rx1, ym)], (x1, y0), (x1, y1), (-1.0, 0.0))]
        return [([(X0, Y0), (X1, Y0), (X1, ym), (X0, ym)], (x0, y0), (x1, y0), (0.0, 1.0)),
                ([(X1, Y1), (X0, Y1), (X0, ym), (X1, ym)], (x1, y1), (x0, y1), (0.0, -1.0))]
    # Ridge along Y: rotate the same logic.
    q = dict(p, x0=y0, x1=y1, y0=x0, y1=x1)
    out = []
    for poly, ea, eb, up in planes(q):
        out.append(([(y, x) for x, y in poly][::-1], (eb[1], eb[0]), (ea[1], ea[0]), (up[1], up[0])))
    return out


def height_at(p, plane, x, y):
    _poly, ea, eb, up = plane
    d = (x - ea[0]) * up[0] + (y - ea[1]) * up[1]          # distance uphill from the wall line
    return float(p["eave_z"]) + d * math.tan(math.radians(float(p["pitch"])))


def ridge_z(p):
    return float(p["eave_z"]) + rafter_span(p) * math.tan(math.radians(float(p["pitch"])))


def _clip_line(poly, origin, direction):
    """Parameter interval of the line origin + t*direction inside the convex polygon."""
    t0, t1 = -1e9, 1e9
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    sign = 1.0 if area > 0 else -1.0
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        nx, ny = -(by - ay) * sign, (bx - ax) * sign           # inward normal
        num = (origin[0] - ax) * nx + (origin[1] - ay) * ny
        den = direction[0] * nx + direction[1] * ny
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        t = -num / den
        if den > 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    return (t0, t1) if t1 - t0 > 1e-6 else None


def members(p):
    """Derived members ``[(role, a_xyz, b_xyz, (b, h))]`` with a/b on the member's top axis."""
    out = []
    pitch = math.radians(float(p["pitch"]))
    rb, rh = rafter_section(p)
    spacing = float(p["rafter_spacing"])
    x0, y0, x1, y1 = _frame(p)
    ez = float(p["eave_z"])
    # Wall plates along the eaves (under the rafters).
    roof_planes = planes(p)

    def under_roof(x, y):
        # Lowest roof plane over the wall line: eaves stay at eave_z, the high
        # wall of a shed roof and the sloping side walls follow the roof.
        return min(height_at(p, plane, x, y) for plane in roof_planes)
    for a, b in (((x0, y0), (x1, y0)), ((x1, y1), (x0, y1)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))):
        out.append(("plate", (a[0], a[1], under_roof(*a)), (b[0], b[1], under_roof(*b)), PLATE))
    for plane in planes(p):
        poly, ea, eb, up = plane
        ex, ey = eb[0] - ea[0], eb[1] - ea[1]
        length = math.hypot(ex, ey)
        ux, uy = ex / length, ey / length
        # Spread over the eave plus the overhang at both ends (barge rafters carry the verge).
        o = float(p.get("overhang", 0.5))
        run = length + 2 * o
        count = max(2, int(math.ceil(run / spacing)) + 1)
        for k in range(count):
            s = -o + run * k / (count - 1)
            origin = (ea[0] + ux * s, ea[1] + uy * s)
            seg = _clip_line(poly, origin, up)
            if seg is None:
                continue
            t0, t1 = seg
            a = (origin[0] + up[0] * t0, origin[1] + up[1] * t0)
            b = (origin[0] + up[0] * t1, origin[1] + up[1] * t1)
            out.append(("rafter", (*a, height_at(p, plane, *a)), (*b, height_at(p, plane, *b)), (rb, rh)))
    form = p.get("roof_form", "gable")
    if form != "shed":
        along_x = (x1 - x0) >= (y1 - y0)
        half = ((y1 - y0) if along_x else (x1 - x0)) / 2
        rz = ridge_z(p)
        o = float(p.get("overhang", 0.5))
        if along_x:
            ym = (y0 + y1) / 2
            ra, rb_ = ((x0 + half, ym), (x1 - half, ym)) if form == "hip" else ((x0 - o, ym), (x1 + o, ym))
        else:
            xm = (x0 + x1) / 2
            ra, rb_ = ((xm, y0 + half), (xm, y1 - half)) if form == "hip" else ((xm, y0 - o), (xm, y1 + o))
        if math.dist(ra, rb_) > 1e-6:
            out.append(("ridge", (*ra, rz), (*rb_, rz), RIDGE))
        if form == "hip":
            corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
            for c in corners:
                end = min((ra, rb_), key=lambda r: math.dist(r, c))
                out.append(("hip", (c[0], c[1], ez), (end[0], end[1], rz), (rb, rh + 0.04)))
    # Battens at the tile gauge across each plane.
    gauge = TILES[p.get("tile", "roman")][1]
    for plane in planes(p):
        poly, ea, eb, up = plane
        ex, ey = eb[0] - ea[0], eb[1] - ea[1]
        length = math.hypot(ex, ey)
        ux, uy = ex / length, ey / length
        for k in range(0, 60):
            d = -float(p.get("overhang", 0.5)) + 0.05 + k * gauge * math.cos(pitch)
            origin = (ea[0] + up[0] * d, ea[1] + up[1] * d)
            seg = _clip_line(poly, origin, (ux, uy))
            if seg is None:
                if k > 2:
                    break
                continue
            t0, t1 = seg
            a = (origin[0] + ux * t0, origin[1] + uy * t0)
            b = (origin[0] + ux * t1, origin[1] + uy * t1)
            out.append(("batten", (*a, height_at(p, plane, *a) + 0.0), (*b, height_at(p, plane, *b)), BATTEN))
    return out


def _beam(a, b, size, top_offset_normal=None):
    """Box along a->b with its top face on the a-b axis (members hang below)."""
    bw, bh = size
    d = [b[i] - a[i] for i in range(3)]
    length = math.sqrt(sum(c * c for c in d))
    if length < 1e-9:
        return [], []
    u = [c / length for c in d]
    side = [-u[1], u[0], 0.0]
    sn = math.hypot(side[0], side[1])
    side = [1.0, 0.0, 0.0] if sn < 1e-9 else [c / sn for c in side]
    down = [u[1] * side[2] - u[2] * side[1], u[2] * side[0] - u[0] * side[2], u[0] * side[1] - u[1] * side[0]]
    if down[2] > 0:
        down = [-c for c in down]
    verts = []
    for base in (a, b):
        for sx in (-bw / 2, bw / 2):
            for dz in (0.0, bh):
                verts.append(tuple(base[i] + side[i] * sx + down[i] * dz for i in range(3)))
    quads = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    return verts, [t for q0, q1, q2, q3 in quads for t in ((q0, q1, q2), (q0, q2, q3))]


def roof_mesh(p):
    """World (vertices, triangles, roles): members, build-up layers and tiles."""
    verts, tris, roles = [], [], []
    cos_a = math.cos(math.radians(float(p["pitch"])))

    def add(v, t, role):
        base = len(verts)
        verts.extend(v)
        tris.extend(tuple(base + i for i in tri) for tri in t)
        roles.extend(role for _ in t)

    def slab(plane, z_from, z_to, role):
        poly = plane[0]
        top = [(x, y, height_at(p, plane, x, y) + z_to) for x, y in poly]
        bot = [(x, y, height_at(p, plane, x, y) + z_from) for x, y in poly]
        n = len(poly)
        t = [(0, i, i + 1) for i in range(1, n - 1)] + [(n, n + i + 1, n + i) for i in range(1, n - 1)]
        for i in range(n):
            j = (i + 1) % n
            t += [(i, j, n + j), (i, n + j, n + i)]
        add(top + bot, t, role)

    # Vertical lifts of each layer above the rafter top (thickness / cos α).
    stack = 0.0
    layer_spans = []
    for _name, thick, _w, _lam, role in build_up(p):
        shown = max(thick, 0.004) / cos_a           # foils drawn 4 mm so they stay visible
        layer_spans.append((role, stack, stack + shown))
        stack += shown
    counter = 0.03 / cos_a                           # counter battens over the membrane (ventilation)
    batten_base = stack + counter
    for role, a, b, size in members(p):
        if role == "batten":
            a = (a[0], a[1], a[2] + batten_base + BATTEN[1])
            b = (b[0], b[1], b[2] + batten_base + BATTEN[1])
        v, t = _beam(a, b, size)
        add(v, t, role)
        if role == "rafter":                         # counter batten on top of the build-up
            v, t = _beam((a[0], a[1], a[2] + batten_base), (b[0], b[1], b[2] + batten_base), (0.05, 0.03))
            add(v, t, "counter_batten")
    for plane in planes(p):
        for role, z0, z1 in layer_spans:
            slab(plane, z0, z1, role)
        tiles_base = batten_base + BATTEN[1]
        slab(plane, tiles_base, tiles_base + TILE_THICK, "tiles")
    return tuple(verts), tuple(tris), tuple(roles)


def default_params(doc, level_name=None):
    """A gable roof over the outer footprint of the active storey's walls."""
    z = float(doc.work_plane.origin[2])
    walls = [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0)) - z) < 0.05]
    if not walls:
        raise ValueError("δεν υπάρχουν τοίχοι στον ενεργό όροφο")
    xs = [float(w.params[k]) for w in walls for k in ("x1", "x2")]
    ys = [float(w.params[k]) for w in walls for k in ("y1", "y2")]
    t = max(float(w.params["thickness"]) for w in walls) / 2
    height = max(float(w.params["height"]) for w in walls)
    return {"x0": min(xs) - t, "y0": min(ys) - t, "x1": max(xs) + t, "y1": max(ys) + t,
            "eave_z": z + height, "pitch": 25.0, "overhang": 0.50, "rafter_spacing": 0.60,
            "roof_form": "gable", "tile": "roman", "snow_zone": 2, "altitude": 0.0,
            "insulation": "xps", "insulation_thickness": 0.08}
