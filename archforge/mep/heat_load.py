"""Indicative heating power (F06, owner 28/10): «το πρόγραμμα προτείνει την απαιτούμενη ισχύ από τις απώλειες».

Not a heating study (EN 12831-1 / ΚΕΝΑΚ): an indication from what the model has, shown with every assumption.

* Transmission through **exterior walls**: net area (length × height − openings) × U × ΔT, U from the wall's
  layers (``wall_types.indicative_u``, EN ISO 6946 with the materials' λ: typical, or the project's data sheet).
  A wall without a build-up has no U: it is listed under «δεν μετρήθηκαν», never guessed.
* **Openings**: area × U of the openings — only when the project gives one (``u_openings``); else not counted, said.
* **Ventilation**: 0.34 Wh/(m³K) (ρ·c of air) × air changes per hour × room volume × ΔT.
* Roof, floor and thermal bridges are not counted yet — said on the result.

Temperatures and air changes are the owner's assumptions (28/10: «υποθετικές θερμοκρασίες με περιθώριο αλλαγής…
μέσα 20, έξω καλοκαίρι 28, χειμώνα 12»), stored on the project's heat source / connection point (its Properties),
not in the project brief (a brief changes other defaults, e.g. the wall tool's).
The kind of heat source (boiler, heat pump…) is the mechanical engineer's decision: nothing here chooses it.
"""
from __future__ import annotations

import math

AIR_HEAT = 0.34          # Wh/(m³·K): density × specific heat of air (physics, not a design choice)

# Owner 28/10, DESIGN_DEFAULT: changed per project («περιθώριο αλλαγής»).
ASSUMPTIONS = {
    "heat_theta_int": (20.0, "°C", "Θερμοκρασία μέσα (άνεση)"),
    "heat_theta_ext_winter": (12.0, "°C", "Θερμοκρασία έξω, χειμώνας"),
    "heat_theta_ext_summer": (28.0, "°C", "Θερμοκρασία έξω, καλοκαίρι"),
    "heat_air_changes": (0.5, "1/h", "Αλλαγές αέρα την ώρα"),
    "heat_u_openings": (None, "W/m²K", "U κουφωμάτων (από τον κατασκευαστή)"),
    "heat_u_walls": (None, "W/m²K", "U εξωτερικών τοίχων χωρίς σύνθεση"),
}
PROVENANCE = "DESIGN_DEFAULT — υπόθεση ιδιοκτήτη 28/10, αλλάζει ανά έργο· όχι μελέτη θέρμανσης (EN 12831-1 / ΚΕΝΑΚ)"


def assumptions(doc):
    """``{key: value}``: the values on the project's heat source / connection point, else the owner's defaults."""
    from archforge.mep.heating_layout import source_of
    e = source_of(doc)
    stored = dict(e.params) if e is not None else {}
    out = {}
    for key, (default, _unit, _label) in ASSUMPTIONS.items():
        value = stored.get(key, default)
        out[key] = None if value is None else float(value)
    return out


def _storeys(doc):
    zs = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall" and e.visible})
    return zs


def _polygon_area(poly):
    return abs(sum(float(poly[i][0]) * float(poly[(i + 1) % len(poly)][1]) -
                   float(poly[(i + 1) % len(poly)][0]) * float(poly[i][1]) for i in range(len(poly)))) / 2


def heat_load(doc, season="winter"):
    """``{"watts", "kw", "delta_t", "parts": [...], "not_counted": [...], "assumptions", "provenance"}``."""
    from archforge.architecture.wall_types import indicative_u
    from archforge.core.notices import not_computed
    from archforge.mep.ventilation import exterior_walls
    a = assumptions(doc)
    outside = a["heat_theta_ext_winter"] if season == "winter" else a["heat_theta_ext_summer"]
    dt = abs(a["heat_theta_int"] - outside)
    parts, not_counted = [], []
    walls_w = openings_w = vent_w = 0.0
    no_u_walls = 0
    opening_area = 0.0
    volume = 0.0
    for z in _storeys(doc):
        try:
            outer = exterior_walls(doc, z)
        except Exception as exc:
            not_computed("heat.exterior", f"Θέρμανση: δεν βρέθηκαν οι εξωτερικοί τοίχοι του ορόφου {z:+.2f}", exc=exc)
            not_counted.append(f"εξωτερικοί τοίχοι ορόφου {z:+.2f}")
            continue
        for w, _normal in outer:
            p = w.params
            length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
            gross = length * float(p["height"])
            holes = sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0))
                        for o in doc.entities.values()
                        if o.kind in ("door", "window", "opening") and o.parent_id == w.id)
            opening_area += holes
            u = indicative_u(p.get("wall_type", "generic"), doc)
            if u is None:
                u = a["heat_u_walls"]                # the project's one value for walls without a build-up
            if u is None:
                no_u_walls += 1
                continue
            walls_w += max(0.0, gross - holes) * u * dt
        try:
            faces = doc.active_room_faces(z=z)
        except Exception as exc:
            not_computed("heat.rooms", f"Θέρμανση: δεν αναγνωρίστηκαν οι χώροι του ορόφου {z:+.2f}", exc=exc)
            not_counted.append(f"αερισμός ορόφου {z:+.2f}")
            continue
        heights = [float(e.params["height"]) for e in doc.entities.values()
                   if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 0.05]
        h = sum(heights) / len(heights) if heights else 0.0
        volume += sum(_polygon_area(f.polygon) for f in faces) * h
    if no_u_walls:
        not_counted.append(f"{no_u_walls} εξωτερικοί τοίχοι χωρίς σύνθεση (δώστε τύπο τοίχου ή U τοίχων)")
    if opening_area > 0:
        if a["heat_u_openings"] is None:
            not_counted.append(f"κουφώματα {_gr(opening_area)} m² (δώστε U κουφωμάτων)")
        else:
            openings_w = opening_area * a["heat_u_openings"] * dt
    vent_w = AIR_HEAT * a["heat_air_changes"] * volume * dt
    not_counted += ["οροφή / στέγη", "δάπεδο", "θερμογέφυρες"]
    parts = [("Εξωτερικοί τοίχοι", walls_w), ("Κουφώματα", openings_w), ("Αερισμός", vent_w)]
    watts = walls_w + openings_w + vent_w
    return {"watts": round(watts), "kw": round(watts / 1000.0, 1), "delta_t": dt, "season": season,
            "volume_m3": round(volume, 1), "parts": [(n, round(v)) for n, v in parts],
            "not_counted": not_counted, "assumptions": a, "provenance": PROVENANCE}


def _gr(v, digits=1):
    return f"{v:.{digits}f}".replace(".", ",")


def summary(result):
    """One Greek line for the user: the power, what it rests on and what it leaves out."""
    a = result["assumptions"]
    outside = a["heat_theta_ext_winter"] if result["season"] == "winter" else a["heat_theta_ext_summer"]
    g = lambda v: f"{v:g}".replace(".", ",")
    return (f"Ενδεικτική ισχύς θέρμανσης ≈ {_gr(result['kw'])} kW (μέσα {g(a['heat_theta_int'])} °C, έξω {g(outside)} °C, "
            f"ΔT {g(result['delta_t'])} K, {g(a['heat_air_changes'])} αλλαγές αέρα/ώρα) — υπόθεση, όχι μελέτη· "
            f"δεν μετρήθηκαν: {'; '.join(result['not_counted'])}")


CONNECTION_NAME = "Σημείο σύνδεσης θέρμανσης (το είδος της πηγής: μηχανολόγος)"
# Owner 28/10: «το σημείο θέρμανσης να είναι απλά ένα σημείο και μετά βλέπουμε· μην το βάλεις μέσα στο χώρο» —
# outside, against a blind exterior wall (where a boiler-room addition would go); one point, moved like any other.


def _blind_wall(doc):
    """``(wall, outward normal, storey z)``: the longest exterior wall of the lowest storey without a door or window
    (None when every exterior wall has one: then the longest, said)."""
    from archforge.core.notices import not_computed
    from archforge.mep.ventilation import exterior_walls
    storeys = _storeys(doc)
    if not storeys:
        return None
    z = storeys[0]
    try:
        outer = exterior_walls(doc, z)
    except Exception as exc:
        not_computed("heat.blind_wall", "Λεβητοστάσιο: δεν βρέθηκαν οι εξωτερικοί τοίχοι", exc=exc)
        return None
    hosts = {o.parent_id for o in doc.entities.values() if o.kind in ("door", "window", "opening")}
    length = lambda w: math.hypot(float(w.params["x2"]) - float(w.params["x1"]), float(w.params["y2"]) - float(w.params["y1"]))
    blind = [(w, n) for w, n in outer if w.id not in hosts]
    pick = max(blind or outer, key=lambda wn: length(wn[0]), default=None)
    if pick is None:
        return None
    if not blind:
        not_computed("heat.blind_wall", "Λεβητοστάσιο: δεν υπάρχει τυφλός εξωτερικός τοίχος — μπήκε στον μακρύτερο, "
                     "μετακινήστε το")
    return pick[0], pick[1], z


def connection_point(doc):
    """F06: the heating connection point when the design has no source — ``Entity`` or None.

    A reference, not a choice of system: ``point_type="heat_source"`` with its suggested power in ``power_w``,
    a point just outside a blind exterior wall (never inside a room), carrying the project's heat assumptions.
    None when there is a source already or no exterior wall."""
    from archforge.core.model import Entity
    from archforge.mep.heating_layout import source_of
    if source_of(doc) is not None:
        return None
    found = _blind_wall(doc)
    if found is None:
        return None
    wall, (nx, ny), z = found
    p = wall.params
    mx, my = (float(p["x1"]) + float(p["x2"])) / 2, (float(p["y1"]) + float(p["y2"])) / 2
    from archforge.mep.heating_layout import BODY
    out = float(p["thickness"]) / 2 + BODY["heat_source"][1] / 2      # its symbol touches the outer face
    angle = math.degrees(math.atan2(float(p["y2"]) - float(p["y1"]), float(p["x2"]) - float(p["x1"])))
    load = heat_load(doc)
    params = {"x": mx + nx * out, "y": my + ny * out, "z": z, "point_type": "heat_source", "rotation": angle,
              "power_w": float(load["watts"])}
    params.update({k: v for k, v in load["assumptions"].items() if v is not None})
    return Entity("heating_point", params, name=CONNECTION_NAME)
