"""Υδραυλικός υπολογισμός θέρμανσης (07/11, ουρά ιδιοκτήτη: «δίκτυο Υ» της κριτικής).

Από τη χάραξη (``heating_layout.route_heating``) και το φορτίο κάθε χώρου (``room_heat_load``):

* **παροχή** κάθε κυκλώματος  ṁ = Q / (cp · ΔT_δικτύου), Q = το φορτίο του χώρου του (μοιρασμένο στα σώματά του·
  βρόχος ενδοδαπέδιας = ο χώρος του, μοιρασμένος στους βρόχους του);
* **πτώση πίεσης** κάθε κυκλώματος Darcy–Weisbach  Δp = f · (L / D) · ρ v² / 2, f από Colebrook–White
  (τραχύτητα PEX-Al-PEX 0,007 mm), 64 / Re όταν Re < 2300 — ιδιότητες νερού στη μέση θερμοκρασία;
* **συλλέκτης**: παροχή = Σ των κυκλωμάτων του (διατήρηση μάζας), κύκλωμα-δείκτης (μέγιστο Δp);
* **κεντρικός** πηγή → συλλέκτες: παροχή, ταχύτητα, Pa/m.

Δεν μετρώνται (λέγεται στο αποτέλεσμα): τοπικές αντιστάσεις (γωνίες, ταυ, βάνες, θερμοστατικές), αντίσταση σώματος
και πηγής, εξισορρόπηση.  Θερμοκρασίες προσαγωγής / επιστροφής: του έργου στην πηγή (Ιδιότητες), αλλιώς οι
τυπικές του συστήματος, γραμμένες ως υπόθεση.  Δεν διαλέγει κυκλοφορητή: δίνει το Δp του δείκτη για τον μηχανολόγο.
"""
from __future__ import annotations

import math

ROUGHNESS = 0.007e-3          # m — PEX-Al-PEX (κατασκευαστές: 0,007 mm)
# Inside diameter (m) of the PEX-Al-PEX sizes the layout uses (outer × wall, typical manufacturer series).
INNER = {16: 0.012, 18: 0.014, 20: 0.016, 26: 0.020, 32: 0.026}
# DESIGN_DEFAULT supply / return (°C) per system when the source does not say — changed on the source.
DEFAULT_TEMPS = {"radiators": (70.0, 50.0), "underfloor": (40.0, 35.0), "fan_coil": (45.0, 40.0)}
# Water at 1 bar (IAPWS-IF97 rounded): °C → (ρ kg/m³, μ mPa·s, cp J/kgK).
WATER = ((10, 999.7, 1.306, 4192), (20, 998.2, 1.002, 4182), (30, 995.7, 0.797, 4178), (40, 992.2, 0.653, 4179),
         (50, 988.0, 0.547, 4181), (60, 983.2, 0.467, 4185), (70, 977.8, 0.404, 4190), (80, 971.8, 0.355, 4197),
         (90, 965.3, 0.315, 4205))
NOT_COUNTED = ("τοπικές αντιστάσεις (γωνίες, ταυ, βάνες, θερμοστατικές)", "αντίσταση σωμάτων / πηγής", "εξισορρόπηση")


def water(t):
    """(ρ, μ in Pa·s, cp) at ``t`` °C, linear between the table's rows."""
    t = min(max(float(t), WATER[0][0]), WATER[-1][0])
    for (t0, r0, m0, c0), (t1, r1, m1, c1) in zip(WATER, WATER[1:]):
        if t0 <= t <= t1:
            k = (t - t0) / (t1 - t0)
            return r0 + (r1 - r0) * k, (m0 + (m1 - m0) * k) * 1e-3, c0 + (c1 - c0) * k
    return WATER[-1][1], WATER[-1][2] * 1e-3, WATER[-1][3]


def friction(re, d, roughness=ROUGHNESS):
    if re <= 0:
        return 0.0
    if re < 2300:
        return 64.0 / re
    f = 0.02
    for _ in range(60):                               # Colebrook–White, fixed point (converges in a few steps)
        f = (1.0 / (-2.0 * math.log10(roughness / (3.7 * d) + 2.51 / (re * math.sqrt(f))))) ** 2
    return f


def pipe(load_w, inner_d, length_m, t_supply, t_return):
    """One pipe run carrying ``load_w``: ``{"kg_h", "l_h", "v", "re", "f", "pa_m", "dp_pa"}``."""
    dt = float(t_supply) - float(t_return)
    if dt <= 0:
        raise ValueError("Η θερμοκρασία προσαγωγής πρέπει να είναι πάνω από της επιστροφής")
    rho, mu, cp = water((float(t_supply) + float(t_return)) / 2)
    m = max(0.0, float(load_w)) / (cp * dt)            # kg/s
    area = math.pi * inner_d ** 2 / 4
    v = m / rho / area
    re = rho * v * inner_d / mu
    f = friction(re, inner_d)
    pa_m = f / inner_d * rho * v * v / 2
    return {"kg_h": m * 3600, "l_h": m / rho * 3.6e6, "v": v, "re": re, "f": f, "pa_m": pa_m,
            "dp_pa": pa_m * float(length_m)}


def temperatures(doc):
    from archforge.mep.heating_layout import source_of, system_of
    system = system_of(doc)
    ts, tr = DEFAULT_TEMPS.get(system, (70.0, 50.0))
    src = source_of(doc)
    p = src.params if src is not None else {}
    own = p.get("flow_temp") not in (None, "") and p.get("return_temp") not in (None, "")
    return (float(p["flow_temp"]), float(p["return_temp"]), "της πηγής") if own else (ts, tr, "υπόθεση (DESIGN_DEFAULT)")


def hydraulics(doc):
    """``{"temps", "manifolds": [{"id", "kg_h", "index", "circuits": [...]}], "two_pipe": [...], "not_counted",
    "warnings"}`` — every number with what it rests on."""
    from archforge.mep.heating_layout import distribution_of, route_heating_cached
    from archforge.mep.room_heat_load import emitter_loads, room_loads
    ts, tr, temps_src = temperatures(doc)
    route = route_heating_cached(doc)
    out = {"temps": (ts, tr, temps_src), "manifolds": [], "two_pipe": [], "not_counted": list(NOT_COUNTED), "warnings": []}
    rooms = {r["signature"]: r for r in room_loads(doc)["rooms"]}
    per_emitter = emitter_loads(doc)
    loops_of = {}
    for m in route["manifolds"]:
        for o in m["outlets"]:
            if str(o["circuit"]).startswith("loop:"):
                loops_of[o["circuit"]] = loops_of.get(o["circuit"], 0) + 1
    for m in route["manifolds"]:
        circuits = []
        for o in m["outlets"]:
            cid = str(o["circuit"])
            if cid.startswith("loop:"):
                room = rooms.get(cid[5:])
                load = (room["watts"] / loops_of[cid]) if room else 0.0
            else:
                load = per_emitter.get(cid, 0.0)
            d = INNER.get(int(o["dn"]))
            if d is None:
                out["warnings"].append(f"Φ{o['dn']}: άγνωστη εσωτερική διάμετρος — το κύκλωμα {o['no']} δεν μετρήθηκε")
                continue
            r = pipe(load, d, o["length_m"], ts, tr)
            circuits.append({"no": o["no"], "label": o["label"], "dn": o["dn"], "length_m": o["length_m"],
                             "load_w": round(load, 1), **{k: round(v, 4 if k == "f" else 2) for k, v in r.items()}})
            if load <= 0:
                out["warnings"].append(f"{o['no']} {o['label']}: χωρίς φορτίο χώρου (σώμα έξω από χώρο ή χωρίς U) — παροχή 0")
        if not circuits:
            continue
        total = sum(c["load_w"] for c in circuits)
        index = max(circuits, key=lambda c: c["dp_pa"])
        from archforge.mep.heating_layout import PIPE_SIZES, system_of
        main_dn = PIPE_SIZES[system_of(doc)][1]
        main = pipe(total, INNER[main_dn], 1.0, ts, tr)
        out["manifolds"].append({"id": m["id"], "z": m["z"], "load_w": round(total, 1),
                                 "kg_h": round(sum(c["kg_h"] for c in circuits), 2), "circuits": circuits,
                                 "index": index["no"], "index_dp_pa": index["dp_pa"],
                                 "main": {"dn": main_dn, "kg_h": round(main["kg_h"], 2), "v": round(main["v"], 3),
                                          "pa_m": round(main["pa_m"], 1)}})
    if distribution_of(doc) != "manifold":
        for eid, load in per_emitter.items():
            r = pipe(load, INNER[18], 1.0, ts, tr)
            out["two_pipe"].append({"emitter": eid, "load_w": round(load, 1), "kg_h": round(r["kg_h"], 2)})
        out["warnings"].append("Δισωλήνιο: παροχές ανά σώμα· πτώση πίεσης ανά διαδρομή όχι ακόμη")
    return out


def summary_lines(result):
    ts, tr, src = result["temps"]
    g = lambda v, d=0: f"{v:.{d}f}".replace(".", ",")
    lines = [f"Θερμοκρασίες {g(ts)}/{g(tr)} °C ({src}) · Colebrook–White, Darcy–Weisbach, PEX-Al-PEX 0,007 mm"]
    for m in result["manifolds"]:
        lines.append(f"Συλλέκτης {m['id']}: {g(m['load_w'] / 1000, 2)} kW · {g(m['kg_h'], 1)} kg/h · δείκτης {m['index']} "
                     f"{g(m['index_dp_pa'])} Pa · κεντρικός Φ{m['main']['dn']} {g(m['main']['v'], 2)} m/s, {g(m['main']['pa_m'])} Pa/m")
        for c in m["circuits"]:
            lines.append(f"  {c['no']} {c['label']}: {g(c['load_w'])} W · Φ{c['dn']} · {g(c['length_m'], 1)} m · "
                         f"{g(c['kg_h'], 1)} kg/h · {g(c['v'], 2)} m/s · Re {g(c['re'])} · {g(c['dp_pa'])} Pa")
    lines.append("Δεν μετρήθηκαν: " + "; ".join(result["not_counted"]))
    lines += result["warnings"]
    return lines
