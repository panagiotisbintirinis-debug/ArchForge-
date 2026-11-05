"""Θερμική εικόνα μιας όψης με τα υλικά της: τοιχοποιία, κολόνες, δοκοί / σενάζ, κουφώματα — όπως τη δείχνει η θερμοκάμερα.

Ιδιοκτήτης 05/11: «εάν ένας τοίχος είναι αμόνωτος, οι κολόνες, πλάκες, σενάζ έχουν άλλο χρωματισμό… η παλέτα από μπλε
έως κόκκινο αλλά μπλεντ… τελείως διαφορετική επεξεργασία βάσει υλικών και λ».

Μοντέλο (σταθερή κατάσταση, ψευδο-2Δ), ανά κελί h × h της όψης:

* **Διαμέσου του τοίχου** (1Δ, EN ISO 6946): αγωγιμότητα από τον αέρα μέσα ως την εξωτερική επιφάνεια
  g = 1 / (Rsi + Σ d/λ) του δομικού στοιχείου που βρίσκεται εκεί — τοιχοποιία με τη σύνθεσή της, ή φέρων (κολόνα / δοκός)
  όπου ο πυρήνας της σύνθεσης (από την πρώτη ως την τελευταία φέρουσα στρώση, μαζί με ό,τι μόνωση υπάρχει ανάμεσα)
  γίνεται οπλισμένο σκυρόδεμα· ό,τι είναι έξω από τον πυρήνα (π.χ. εξωτερική θερμομόνωση, σοβάς) μένει και καλύπτει το
  φέροντα. Κούφωμα: g από το Uw του.
* **Προς τα έξω**: he = 1/Rse (ΤΟΤΕΕ 20701-2 Πίν. 3β: 25 W/m²K).
* **Πλάγια**, στο επίπεδο της όψης: η στρώση έξω από την εξωτερικότερη θερμομόνωση (σοβάς, εξωτερικό φύλλο, μπετόν)
  άγει θερμότητα παράλληλα με λ·d — γι' αυτό τα όρια κολόνας / τούβλου «σβήνουν» μαλακά, όπως στη φωτογραφία, και
  πίσω από εξωτερική θερμομόνωση (λεπτός σοβάς) σχεδόν δεν φαίνονται.

Ισορροπία κάθε κελιού: λd ∇²θ + g (θi − θ) + he (θe − θ) = 0 (πεπερασμένες διαφορές, μηδενική ροή στα όρια της όψης).
Χωρίς πλάγια αγωγή το αποτέλεσμα είναι ακριβώς το 1Δ θse = θe + U·Rse·ΔT.

Δεν περιλαμβάνει: ακτινοβολία ουρανού, ήλιο, άνεμο, υγρασία, θερμοχωρητικότητα, τρισδιάστατες γωνίες. Είναι ό,τι
δίνουν οι στρώσεις και τα λ — σύγκριση με τη φωτογραφία δείχνει πού η κατασκευή διαφέρει από τη μελέτη.
"""
from __future__ import annotations

import math

import numpy as np

H = 0.05                                     # m, cell of the façade grid (DESIGN_DEFAULT)
OPENING_LATERAL = 0.01                       # W/K, λ·d across a frame / glass (small: a window is its own surface)


def layer(doc, material_id, thickness, role=None):
    """One layer ``(material id, d, λ, role)`` from the registry (the project's data-sheet λ apply)."""
    from archforge.construction.building_materials import material
    m = material(material_id, doc)
    return (material_id, float(thickness), float(m.conductivity), role or m.role)


def _layers(doc, wall_type):
    """``[(material id, d, λ, role)]`` exterior first (``wall_assemblies.layer_specs`` + the registry's λ)."""
    from archforge.architecture.wall_assemblies import layer_specs
    from archforge.construction.building_materials import material
    out = []
    for spec in layer_specs(doc, wall_type):
        m = material(spec["material"], doc)
        if m is None or not m.conductivity or float(spec["thickness"]) <= 0:
            continue
        out.append((spec["material"], float(spec["thickness"]), float(m.conductivity), spec.get("role") or m.role))
    return out


def frame_layers(doc, layers, depth=None):
    """The build-up where a column / beam sits in the wall: the core (first … last structural layer, with what lies
    between) becomes reinforced concrete of the same thickness; the layers outside the core stay."""
    from archforge.construction.building_materials import material
    idx = [i for i, l in enumerate(layers) if l[3] == "structure"]
    if not idx:
        return list(layers)
    a, b = idx[0], idx[-1]
    core = sum(l[1] for l in layers[a:b + 1]) if depth is None else float(depth)
    rc = material("reinforced_concrete", doc)
    return list(layers[:a]) + [("reinforced_concrete", core, float(rc.conductivity), "structure")] + list(layers[b + 1:])


def _conductances(layers, rsi):
    """``(g, λd)``: interior air → exterior surface, and the lateral conductance of the layers outside the insulation."""
    r = rsi + sum(d / lam for _m, d, lam, _r in layers)
    outer = []
    for l in layers:                          # exterior first: everything before the first insulation layer
        if l[3] == "insulation":
            break
        outer.append(l)
    if len(outer) == len(layers):             # no insulation: the outer half of the wall spreads heat sideways
        half, acc, outer = sum(l[1] for l in layers) / 2, 0.0, []
        for m, d, lam, role in layers:
            take = min(d, max(0.0, half - acc))
            if take > 0:
                outer.append((m, take, lam, role))
            acc += d
    return 1.0 / r, sum(lam * d for _m, d, lam, _r in outer)


def _on_wall(wall, x, y, extra=0.0):
    p = wall.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    s = ((x - x1) * (x2 - x1) + (y - y1) * (y2 - y1)) / L
    d = abs((x2 - x1) * (y1 - y) - (x1 - x) * (y2 - y1)) / L
    return s, d <= float(p["thickness"]) / 2 + extra + 1e-6


def facade(doc, wall_id, wall_type=None, theta_i=None, theta_e=None, layers=None, opening_u=None):
    """The exterior surface temperature field of one wall: ``{"theta": 2D array (rows = z from the top),
    "extent": (length, height), "regions": [...], "u": {region kind: U}, "theta_i", "theta_e"}``.

    ``wall_type`` / ``layers`` (``[(material id, d, λ, role)]`` exterior first) override the wall's build-up and
    ``opening_u`` the Uw of its doors / windows — a proposal («με την πρόταση»), nothing in the project changes."""
    from archforge.mep.heat_load import assumptions
    from archforge.mep.totee_20701_2 import TABLE_3B
    wall = doc.get(wall_id)
    p = wall.params
    a = assumptions(doc)
    ti = a["heat_theta_int"] if theta_i is None else float(theta_i)
    te = a["heat_theta_ext_winter"] if theta_e is None else float(theta_e)
    rsi, rse = TABLE_3B["wall_exterior"]
    he = 1.0 / rse
    key = wall_type or p.get("wall_type", "generic")
    base = list(layers) if layers is not None else _layers(doc, key)
    if not base:
        raise ValueError("ο τοίχος δεν έχει σύνθεση: χωρίς στρώσεις και λ δεν υπάρχει θερμική εικόνα")
    length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
    height = float(p["height"])
    z0 = float(p.get("z", 0.0))
    nx, nz = max(2, round(length / H)), max(2, round(height / H))
    g0, k0 = _conductances(base, rsi)
    g = np.full((nz, nx), g0)
    k = np.full((nz, nx), k0)
    kind = np.zeros((nz, nx), dtype=np.int8)        # 0 masonry, 1 frame, 2 opening
    regions, u = [], {"masonry": 1.0 / (1.0 / g0 + rse)}

    def cells(s0, s1, za, zb):
        i0, i1 = max(0, int(round(s0 / H))), min(nx, int(round(s1 / H)))
        r0, r1 = max(0, int(round((height - zb) / H))), min(nz, int(round((height - za) / H)))
        return slice(r0, r1), slice(i0, i1)

    def frame(s0, s1, za, zb, depth, label, eid):
        fl = frame_layers(doc, base, None)
        gf, kf = _conductances(fl, rsi)
        rr, cc = cells(s0, s1, za, zb)
        g[rr, cc], k[rr, cc], kind[rr, cc] = gf, kf, 1
        u[label] = 1.0 / (1.0 / gf + rse)
        regions.append({"kind": label, "id": eid, "s": (round(s0, 3), round(s1, 3)), "z": (round(za, 3), round(zb, 3))})

    for e in doc.entities.values():
        if e.kind == "structural_column" and abs(float(e.params.get("z", 0.0)) - z0) < 0.05:
            s, on = _on_wall(wall, float(e.params["x"]), float(e.params["y"]), float(e.params.get("depth", 0.3)) / 2)
            w = float(e.params.get("width", 0.4))
            if on and -w / 2 < s < length + w / 2:
                frame(s - w / 2, s + w / 2, 0.0, min(height, float(e.params.get("height", height))),
                      e.params.get("depth"), "column", e.id)
        elif e.kind == "structural_beam":
            bz = float(e.params.get("z", 0.0)) - z0
            if not (-0.01 <= bz < height):
                continue
            s1, on1 = _on_wall(wall, float(e.params["x1"]), float(e.params["y1"]), float(e.params.get("width", 0.25)) / 2)
            s2, on2 = _on_wall(wall, float(e.params["x2"]), float(e.params["y2"]), float(e.params.get("width", 0.25)) / 2)
            if on1 and on2:
                lo, hi = max(0.0, min(s1, s2)), min(length, max(s1, s2))
                if hi > lo:
                    frame(lo, hi, bz, min(height, bz + float(e.params.get("height", 0.5))), None, "beam", e.id)
    for o in doc.entities.values():
        if o.kind not in ("window", "door") or o.parent_id != wall.id:
            continue
        uw = opening_u or o.params.get("u_value") or a["heat_u_openings"]
        s0 = float(o.params.get("offset", 0.0))
        za = float(o.params.get("sill", 0.0)) if o.kind == "window" else 0.0
        rr, cc = cells(s0, s0 + float(o.params.get("width", 1.0)), za, za + float(o.params.get("height", 1.0)))
        if uw is None:
            kind[rr, cc] = 2
            g[rr, cc] = 1.0 / (1.0 / g0 + 0.0)          # unknown Uw: left as wall, said below
            regions.append({"kind": "opening_no_u", "id": o.id})
            continue
        g[rr, cc], k[rr, cc], kind[rr, cc] = 1.0 / max(1e-6, 1.0 / float(uw) - rse), OPENING_LATERAL, 2
        u[o.kind] = float(uw)
        regions.append({"kind": o.kind, "id": o.id})
    theta = _solve(g, k, he, ti, te)
    # What leaves the façade: he·(θse − θe) over every cell (the lateral flow stays inside the wall).
    watts = float(np.sum(he * (theta - te)) * H * H)
    return {"theta": theta, "watts": watts, "layers": base, "extent": (length, height), "regions": regions, "u": u, "kind": kind,
            "theta_i": ti, "theta_e": te, "wall_type": key, "one_d": te + u["masonry"] * rse * (ti - te)}


def _solve(g, k, he, ti, te, tol=1e-5, max_iter=20000):
    """λd ∇²θ + g (θi − θ) + he (θe − θ) = 0 on the grid (Jacobi, zero flux at the edges)."""
    kk = k / (H * H)
    # Lateral conductance between neighbours: harmonic mean (a crisp joint between two materials).
    def link(a, b):
        return 2 * a * b / np.maximum(a + b, 1e-12)
    kx = link(kk[:, :-1], kk[:, 1:])
    ky = link(kk[:-1, :], kk[1:, :])
    diag = g + he
    diag = diag.copy()
    diag[:, :-1] += kx; diag[:, 1:] += kx
    diag[:-1, :] += ky; diag[1:, :] += ky
    rhs = g * ti + he * te
    theta = (g * ti + he * te) / (g + he)              # the 1D answer as the start
    for _ in range(max_iter):
        nb = np.zeros_like(theta)
        nb[:, :-1] += kx * theta[:, 1:]; nb[:, 1:] += kx * theta[:, :-1]
        nb[:-1, :] += ky * theta[1:, :]; nb[1:, :] += ky * theta[:-1, :]
        new = (rhs + nb) / diag
        if np.max(np.abs(new - theta)) < tol:
            return new
        theta = new
    return theta


PALETTES = {
    "iron": ((0.00, (0, 0, 0)), (0.15, (32, 0, 96)), (0.32, (120, 0, 140)), (0.50, (190, 30, 110)),
             (0.66, (230, 80, 30)), (0.80, (250, 160, 0)), (0.92, (255, 230, 60)), (1.00, (255, 255, 255))),
    # «από μπλε έως κόκκινο, μπλεντ» (ιδιοκτήτης 05/11): rainbow of the cameras
    "rainbow": ((0.00, (20, 20, 140)), (0.20, (0, 90, 255)), (0.40, (0, 210, 230)), (0.55, (60, 220, 80)),
                (0.72, (250, 230, 30)), (0.86, (255, 130, 0)), (1.00, (220, 20, 20))),
}


def to_rgb(theta, lo, hi, palette="iron"):
    """``(rows, cols, 3)`` uint8 of a temperature field on the palette between ``lo`` and ``hi``."""
    stops = PALETTES[palette]
    t = np.clip((np.asarray(theta) - lo) / max(1e-9, hi - lo), 0.0, 1.0)
    out = np.zeros(t.shape + (3,), dtype=float)
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        m = (t >= t0) & (t <= t1)
        f = (t[m] - t0) / max(1e-9, t1 - t0)
        for ch in range(3):
            out[..., ch][m] = c0[ch] + (c1[ch] - c0[ch]) * f
    return out.round().astype(np.uint8)
