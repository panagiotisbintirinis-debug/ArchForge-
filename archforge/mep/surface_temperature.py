"""Θερμοκρασία επιφάνειας τοίχων και κουφωμάτων — η «θερμική όψη» απέξω, όπως τη δείχνει μια θερμοκάμερα.

Ιδιοκτήτης 05/11: «κανονικά πρέπει να φαίνονται οι θερμοκρασίες οπτικά από εξωτερική πλευρά χρωματικά».

Σταθερή κατάσταση, μονοδιάστατη ροή (EN ISO 6946): η ροή q = U·(θi − θe) περνά από την αντίσταση επιφάνειας, άρα
θse = θe + U·Rse·(θi − θe)   (εξωτερική επιφάνεια)    θsi = θi − U·Rsi·(θi − θe)   (εσωτερική).
Rsi, Rse: ΤΟΤΕΕ 20701-2 Πίνακας 3β (εξωτερικοί τοίχοι και παράθυρα: 0,13 / 0,04). θi, θe: οι θερμοκρασίες σχεδιασμού του
έργου (``mep/design_climate``). U: η σύνθεση του τοίχου (``wall_types.indicative_u``) ή το U του έργου για τοίχους
χωρίς σύνθεση· Uw κάθε κουφώματος ή του έργου.

Τι δεν είναι: ακτινοβολία ουρανού, ήλιος, άνεμος, θερμοχωρητικότητα, ανάκλαση — μια πραγματική φωτογραφία διαφέρει.
Θερμογέφυρες, στέγη, πλάκες: δεν υπολογίζονται ακόμη· επιφάνεια χωρίς U = «δεν υπολογίστηκε», ποτέ μαντεμένη.
"""
from __future__ import annotations

# Thermography palette «iron» (black → violet → red → orange → yellow → white): a display choice (DESIGN_DEFAULT),
# the usual palette of building thermography, so a picture of the program reads like the camera's.
IRON = ((0.00, (0, 0, 0)), (0.15, (32, 0, 96)), (0.32, (120, 0, 140)), (0.50, (190, 30, 110)),
        (0.66, (230, 80, 30)), (0.80, (250, 160, 0)), (0.92, (255, 230, 60)), (1.00, (255, 255, 255)))
UNKNOWN = (78, 80, 86)                                 # not computed: a dark neutral grey, never a palette colour
GROUND = (22, 18, 40)                                  # the ground / terrain: near the cold end, as a camera sees it
MIN_SPAN = 1.0                                         # K: the camera's auto range never narrower than this


def palette(t, stops=IRON):
    """``(r, g, b)`` at ``t`` ∈ [0, 1] of the palette."""
    t = max(0.0, min(1.0, float(t)))
    for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
        if t <= t1:
            f = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            return tuple(round(a + (b - a) * f) for a, b in zip(c0, c1))
    return stops[-1][1]


def surface_temperatures(doc, side="exterior", season="winter"):
    """``{"items": {entity id: {"kind", "u", "theta"}}, "unknown": [ids], "theta_i", "theta_e", "rs", "source"}``.

    Exterior walls (``ventilation.exterior_walls``) and their doors / windows, every storey."""
    from archforge.architecture.wall_types import indicative_u
    from archforge.mep.heat_load import assumptions
    from archforge.mep.totee_20701_2 import TABLE_3B
    from archforge.mep.ventilation import exterior_walls
    a = assumptions(doc)
    ti = a["heat_theta_int"]
    te = a["heat_theta_ext_winter"] if season == "winter" else a["heat_theta_ext_summer"]
    rsi, rse = TABLE_3B["wall_exterior"]
    rs = rse if side == "exterior" else rsi
    items, unknown = {}, []

    def theta(u):
        q = u * (ti - te)
        return te + q * rse if side == "exterior" else ti - q * rsi

    storeys = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values()
                      if e.kind == "wall" and e.visible})
    for z in storeys:
        for w, _n in exterior_walls(doc, z):
            u = indicative_u(w.params.get("wall_type", "generic"), doc) or a["heat_u_walls"]
            if u is None:
                unknown.append(w.id)
            else:
                items[w.id] = {"kind": "wall", "u": float(u), "theta": round(theta(float(u)), 2)}
            for o in doc.entities.values():
                if o.kind in ("door", "window") and o.parent_id == w.id:
                    from archforge.mep.opening_thermal import uw as _uw
                    uo = _uw(doc, o)[0]
                    if uo is None:
                        unknown.append(o.id)
                    else:
                        items[o.id] = {"kind": o.kind, "u": float(uo), "theta": round(theta(float(uo)), 2)}
    return {"items": items, "unknown": unknown, "theta_i": ti, "theta_e": te, "rs": rs, "side": side,
            "source": (f"θ{'se' if side == 'exterior' else 'si'} = θe + U·R·ΔT, R = " + f"{rs:g}".replace(".", ",")
                       + " m²K/W (ΤΟΤΕΕ 20701-2 Πίν. 3β), θi " + f"{ti:g}".replace(".", ",") + " °C, θe "
                       + f"{te:g}".replace(".", ",") + " °C")}


def thermal_view(doc, side="exterior"):
    """What the 3D draws: ``{"colors": {id: [r, g, b]}, "unknown": [ids], "legend": {...}}`` — the camera's auto range:
    the coldest and warmest surface computed, at least ``MIN_SPAN`` apart."""
    st = surface_temperatures(doc, side)
    temps = [v["theta"] for v in st["items"].values()]
    if temps:
        # As a camera outdoors: the scale starts at the outside air (sky and ground are colder still), so the best
        # insulated wall is just above black, not black.
        lo, hi = min(min(temps), st["theta_e"]), max(temps)
        if hi - lo < MIN_SPAN:
            mid = (hi + lo) / 2
            lo, hi = mid - MIN_SPAN / 2, mid + MIN_SPAN / 2
    else:
        lo, hi = st["theta_e"], st["theta_e"] + MIN_SPAN
    colors = {eid: list(palette((v["theta"] - lo) / (hi - lo))) for eid, v in st["items"].items()}
    return {"colors": colors, "unknown": st["unknown"], "unknown_color": list(UNKNOWN), "ground_color": list(GROUND),
            "legend": {"min": round(lo, 1), "max": round(hi, 1), "stops": [[t, list(c)] for t, c in IRON],
                       "title": "Θερμοκρασία εξωτερικής επιφάνειας" if side == "exterior" else
                                "Θερμοκρασία εσωτερικής επιφάνειας",
                       "note": st["source"] + " · γκρι = δεν υπολογίστηκε (χωρίς U / στέγη / πλάκες)"},
            "count": len(colors)}
