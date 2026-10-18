"""Roof tool (owner 18/10): the two views of a tiled roof — its layers and its timber framing — and the cutting list.

Layers view: the build-up over the rafters (boarding → vapour barrier → insulation → breathable membrane → counter
battens → battens → tiles) with thickness, weight and λ: the self-weight G (kN/m²) and the indicative U.

Framing view: only the timber, each piece with a code — ridge Κ-1, rafters Ψ-01…, jack rafters ΚΨ-01…, hips Γ-1…,
wall plates Τ-1…, posts Ο-1… — its market section, net and order length, and its cuts:

* rafters: plumb cut at the ridge (the roof pitch), seat cut on the wall plate («σαμάρι», 2,5–3,5 cm deep);
* jack rafters: compound cut where they meet the hip (plumb at the pitch + plan bevel);
* hips: plumb cut at the ridge at the hip's own pitch, seat on the plate corner.

Sections come only from MARKET (owner's table of the Greek timber yards — sawn and glulam), never a theoretical
size.  The rafter is sized by timber_roof.size_rafter over the market rafter sizes; the ridge as a beam between the
gable walls / hip ends on the rafters' share of load, with posts (ορθοστάτες) added where no market ridge spans it.
Pre-design for review by a structural engineer: no wind, seismic action or connections (timber_roof's limits).
"""
from __future__ import annotations

import math

# Owner's table 18/10 — commercial sections (b, h) in m, smallest first.
MARKET = {
    "batten": ((0.03, 0.05), (0.04, 0.05)),
    "counter_batten": ((0.04, 0.05), (0.05, 0.05), (0.05, 0.06)),
    "rafter": ((0.065, 0.13), (0.075, 0.15), (0.08, 0.15), (0.08, 0.16), (0.08, 0.18), (0.10, 0.18), (0.10, 0.20)),
    "hip": ((0.10, 0.20), (0.12, 0.24), (0.14, 0.24)),
    "plate": ((0.10, 0.10), (0.10, 0.12), (0.12, 0.12), (0.15, 0.15)),
    "ridge": ((0.10, 0.20), (0.12, 0.20), (0.14, 0.24), (0.20, 0.20)),
    "post": ((0.12, 0.12), (0.15, 0.15), (0.20, 0.20)),
}
ORDER_EXTRA = 0.20             # m — owner: net length + 15–20 cm for the bevel cuts (upper end kept)
ORDER_STEP = 0.05              # m — order lengths rounded up to 5 cm
SEAT_DEPTH = (0.025, 0.035)    # m — seat cut («σαμάρι») depth range, owner 18/10
ROLE_CODE = {"ridge": "Κ", "rafter": "Ψ", "jack": "ΚΨ", "hip": "Γ", "plate": "Τ", "post": "Ο"}
ROLE_NAME = {"ridge": "Κορφιάς", "rafter": "Ψαλίδι", "jack": "Κοντό ψαλίδι", "hip": "Γωνία τετράρριχτης", "plate": "Τεγίδα",
             "post": "Ορθοστάτης κορφιά", "batten": "Λάτα κεραμιδιών", "counter_batten": "Αντιλάτα (αερισμός)"}
PROVENANCE = ("Εργαλείο στέγης: διατομές μόνο από τον πίνακα της αγοράς (ιδιοκτήτης 18/10)· ψαλίδια και κορφιάς σε κάμψη "
              "(C24, k_mod 0,9, γ_M 1,3) και βέλος L/300 με μόνιμα των στρώσεων + χιόνι· γωνίες με h ≥ ψαλίδι + 4 cm "
              "(γεωμετρία κοψιμάτων, όχι στατικός έλεγχος)· χωρίς άνεμο/σεισμό/συνδέσεις — προς έλεγχο από στατικό")


def section_label(s):
    return f"{s[0] * 100:g}×{s[1] * 100:g}".replace(".", ",")


# ----------------------------------------------------------------------------------------------- layers view
def layers(p):
    """Layers bottom to top: ``[(name, thickness m, weight kN/m², λ or None, role)]`` + G and U."""
    from archforge.structure.timber_roof import BATTEN, BATTENS_WEIGHT, TILE_THICK, TILE_WEIGHT, TILES, build_up, dead_load, indicative_u
    rows = [(n, t, w, lam, role) for n, t, w, lam, role in build_up(p)]
    cb = MARKET["counter_batten"][0]
    rows.append((f"Αντιλάτες {section_label(cb)} (κενό αερισμού)", cb[0], BATTENS_WEIGHT / 2, None, "counter_batten"))
    rows.append((f"Λάτες {section_label(MARKET['batten'][0])} ανά {TILES[p.get('tile', 'roman')][1] * 100:.0f} cm",
                 BATTEN[1], BATTENS_WEIGHT / 2, None, "batten"))
    rows.append((TILES[p.get("tile", "roman")][0], TILE_THICK, TILE_WEIGHT, None, "tiles"))
    return {"rows": rows, "g_kn_m2": round(dead_load(p), 2), "u_w_m2k": round(indicative_u(p), 2)}


# ----------------------------------------------------------------------------------------------- sizing
def _bending_ok(section, q_uls, q_sls, span):
    from archforge.structure.timber_roof import E_MEAN, F_MK, GAMMA_M, K_MOD
    b, h = section
    sigma = q_uls * span ** 2 / 8.0 / (b * h ** 2 / 6.0) / 1000.0
    defl = 5 * q_sls * span ** 4 / (384 * E_MEAN * 1000 * b * h ** 3 / 12.0)
    return sigma <= K_MOD * F_MK / GAMMA_M and defl <= span / 300.0, round(sigma, 2), round(defl * 1000, 1)


def ridge_design(p, length):
    """Ridge between its supports: the rafters' share (half of each side) as a line load; posts added at equal
    spacing until a market section carries it.  ``{"section", "posts", "span_m", ...}``."""
    from archforge.structure.timber_roof import dead_load, rafter_span, snow_load
    alpha = math.radians(float(p["pitch"]))
    s, _sk, _mu = snow_load(p)
    g_plan = dead_load(p) / math.cos(alpha)
    width = rafter_span(p)                       # half of each side = one rafter span (plan)
    q_uls, q_sls = (1.35 * g_plan + 1.5 * s) * width, (g_plan + s) * width
    for posts in range(0, 12):
        span = length / (posts + 1)
        for sec in MARKET["ridge"]:
            ok, sigma, defl = _bending_ok(sec, q_uls, q_sls, span)
            if ok:
                return {"section": sec, "posts": posts, "span_m": round(span, 2), "sigma_mpa": sigma, "deflection_mm": defl,
                        "q_uls_kn_m": round(q_uls, 2), "ok": True}
    return {"section": MARKET["ridge"][-1], "posts": 11, "span_m": round(length / 12, 2), "ok": False, "q_uls_kn_m": round(q_uls, 2)}


def hip_section(rafter):
    """Smallest market hip deep enough for the jack rafters' cuts (rafter h + 4 cm)."""
    return next((s for s in MARKET["hip"] if s[1] >= rafter[1] + 0.04 - 1e-9), MARKET["hip"][-1])


# ----------------------------------------------------------------------------------------------- framing view
def framing(p):
    """Pieces of the framing: ``[{"code", "role", "name", "section", "a", "b", "net_m", "order_m", "cuts": [...]}]``
    + battens / counter battens by length, the ridge design and the totals."""
    from archforge.structure.timber_roof import TILES, members, planes, ridge_z, size_rafter
    pitch = float(p["pitch"])
    alpha = math.radians(pitch)
    rafter = size_rafter(p)
    rsec = (rafter["section"]["b"], rafter["section"]["h"]) if rafter["section"] else MARKET["rafter"][-1]
    rz = ridge_z(p) if p.get("roof_form", "gable") != "shed" else None
    raw = members(p)
    plate = MARKET["plate"][0]
    seat = round(min(SEAT_DEPTH[1], max(SEAT_DEPTH[0], rsec[1] / 5)), 3)
    hip_pitch = math.degrees(math.atan(math.tan(alpha) / math.sqrt(2)))
    pieces, battens_m = [], 0.0
    ridge = None
    for role, a, b, _size in raw:
        net = math.dist(a, b)
        if role == "batten":
            battens_m += net
            continue
        if role == "rafter":
            top = max(a[2], b[2])
            kind = "rafter" if rz is None or abs(top - rz) < 0.02 else "jack"
            cuts = [f"Πάνω: κάθετη κοπή {pitch:g}°" if kind == "rafter" else
                    f"Πάνω: διπλή λοξή — κάθετη {pitch:g}° + 45° σε κάτοψη (πάνω στη γωνία)",
                    f"Κάτω: σαμάρι στην τεγίδα βάθος {seat * 100:.1f} cm, έδραση {plate[0] * 100:.0f} cm".replace(".", ","),
                    "Άκρο γείσου: κάθετη κοπή"]
            pieces.append({"role": kind, "section": rsec, "a": a, "b": b, "net_m": net, "cuts": cuts})
        elif role == "hip":
            pieces.append({"role": "hip", "section": hip_section(rsec), "a": a, "b": b, "net_m": net,
                           "cuts": [f"Πάνω: κάθετη κοπή {hip_pitch:.1f}° (κλίση γωνίας) + διπλή λοξή 45° στον κορφιά".replace(".", ","),
                                    "Κάτω: σαμάρι στη γωνία της τεγίδας (διπλό)"]})
        elif role == "ridge":
            ridge = ridge_design(p, net)
            pieces.append({"role": "ridge", "section": ridge["section"], "a": a, "b": b, "net_m": net,
                           "cuts": ["Ίσια κοπή στα άκρα" if p.get("roof_form") != "hip" else "Άκρα: υποδοχή γωνιών (45° σε κάτοψη)"]})
        elif role == "plate":
            pieces.append({"role": "plate", "section": plate, "a": a, "b": b, "net_m": net,
                           "cuts": ["Ψαλιδωτή ένωση στις γωνίες (μισό-μισό)", "Αγκύρωση με ντίζες στο σενάζ"]})
    # Posts under the ridge where its span needed them, on the slab / beams below (at the wall top).
    if ridge and ridge["posts"]:
        (r,) = [q for q in pieces if q["role"] == "ridge"]
        ez = float(p["eave_z"])
        sec = (ridge["section"][0], ridge["section"][0]) if ridge["section"][0] >= 0.12 else MARKET["post"][0]
        sec = next((s for s in MARKET["post"] if s[0] >= sec[0] - 1e-9), MARKET["post"][-1])
        for k in range(1, ridge["posts"] + 1):
            t = k / (ridge["posts"] + 1)
            x, y = r["a"][0] + (r["b"][0] - r["a"][0]) * t, r["a"][1] + (r["b"][1] - r["a"][1]) * t
            top = r["a"][2] - ridge["section"][1]
            pieces.append({"role": "post", "section": sec, "a": (x, y, ez), "b": (x, y, top), "net_m": top - ez,
                           "cuts": ["Ίσια κοπή· στήριξη σε δοκό/τοίχο από κάτω (στατικός)"]})
    # Codes in reading order per role: ridge, rafters, jacks, hips, plates, posts.
    order = ("ridge", "rafter", "jack", "hip", "plate", "post")
    pieces.sort(key=lambda q: (order.index(q["role"]), round(q["a"][1], 2), round(q["a"][0], 2)))
    counters = {}
    for q in pieces:
        counters[q["role"]] = counters.get(q["role"], 0) + 1
        n = counters[q["role"]]
        q["code"] = f"{ROLE_CODE[q['role']]}-{n:02d}" if q["role"] in ("rafter", "jack") else f"{ROLE_CODE[q['role']]}-{n}"
        q["name"] = ROLE_NAME[q["role"]]
        q["net_m"] = round(q["net_m"], 3)
        # Order length: net + the bevel allowance, up to the next 5 cm (pieces a cm apart become one type).
        q["order_m"] = round(math.ceil((q["net_m"] + ORDER_EXTRA) / ORDER_STEP - 1e-9) * ORDER_STEP, 2)
    # Counter battens: along every rafter over its slope length.
    counter_m = sum(q["net_m"] for q in pieces if q["role"] in ("rafter", "jack"))
    slope_area = sum(_area(plane[0]) for plane in planes(p)) / math.cos(alpha)
    volume = {}
    for q in pieces:
        key = section_label(q["section"])
        volume[key] = volume.get(key, 0.0) + q["section"][0] * q["section"][1] * q["order_m"]
    volume[section_label(MARKET["batten"][0])] = volume.get(section_label(MARKET["batten"][0]), 0.0) + \
        MARKET["batten"][0][0] * MARKET["batten"][0][1] * battens_m
    volume[section_label(MARKET["counter_batten"][0])] = volume.get(section_label(MARKET["counter_batten"][0]), 0.0) + \
        MARKET["counter_batten"][0][0] * MARKET["counter_batten"][0][1] * counter_m
    return {"pieces": pieces, "battens_m": round(battens_m, 1), "counter_battens_m": round(counter_m, 1),
            "slope_area_m2": round(slope_area, 2), "ridge": ridge, "rafter": rafter,
            "volume_m3": {k: round(v, 3) for k, v in sorted(volume.items())},
            "volume_total_m3": round(sum(volume.values()), 3), "provenance": PROVENANCE}


def cutting_list(p):
    """Identical pieces grouped: ``[{"codes", "name", "section", "order_m", "net_m", "count", "cuts"}]``."""
    f = framing(p)
    groups = {}
    for q in f["pieces"]:
        key = (q["role"], q["section"], q["order_m"], tuple(q["cuts"]))
        g = groups.setdefault(key, {"codes": [], "name": q["name"], "section": section_label(q["section"]),
                                    "order_m": q["order_m"], "net_m": q["net_m"], "count": 0, "cuts": q["cuts"], "role": q["role"]})
        g["codes"].append(q["code"])
        g["count"] += 1
    rows = sorted(groups.values(), key=lambda g: (("ridge", "rafter", "jack", "hip", "plate", "post").index(g["role"]), -g["order_m"]))
    return {"rows": rows, **{k: f[k] for k in ("battens_m", "counter_battens_m", "slope_area_m2", "volume_m3", "volume_total_m3",
                                                "ridge", "provenance")}}


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2
