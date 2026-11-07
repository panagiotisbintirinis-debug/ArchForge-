"""Indicative heating power (F06, owner 28/10): «το πρόγραμμα προτείνει την απαιτούμενη ισχύ από τις απώλειες».

Not a heating study (EN 12831-1 / ΚΕΝΑΚ): an indication from what the model has, shown with every assumption.

* Transmission through **exterior walls**: net area (length × height − openings) × U × ΔT, U from the wall's
  layers (``wall_types.indicative_u``, EN ISO 6946 with the materials' λ: typical, or the project's data sheet).
  A wall without a build-up has no U: it is listed under «δεν μετρήθηκαν», never guessed.
* **Openings**: area × Uw of each door / window (its own ``u_value``, else the project's ``u_openings``); one with
  neither is not counted, said.
* **Ventilation**: 0.34 Wh/(m³K) (ρ·c of air) × air changes per hour × room volume × ΔT.
* **Thermal bridges**: Σ ψ·l × ΔT, lengths from the drawing, ψ from the project's catalogue (``mep/thermal_bridges``);
  a kind without ψ is listed under «δεν μετρήθηκαν».
* **Roof and floor** (07/11): the rooms' area with no room above / below × the project's U × ΔT; without a U
  the area is listed under «δεν μετρήθηκαν».

Temperatures and air changes are the owner's assumptions (28/10: «υποθετικές θερμοκρασίες με περιθώριο αλλαγής…
μέσα 20, έξω καλοκαίρι 28, χειμώνα 12»), stored on the project's heat source / connection point (its Properties),
not in the project brief (a brief changes other defaults, e.g. the wall tool's).
The kind of heat source (boiler, heat pump…) is the mechanical engineer's decision: nothing here chooses it.
"""
from __future__ import annotations

import math

AIR_HEAT = 0.34          # Wh/(m³·K): density × specific heat of air (physics, not a design choice)

# Owner 28/10, DESIGN_DEFAULT: changed per project («περιθώριο αλλαγής»).
from archforge.mep.design_climate import FIELDS as _CLIMATE

# Temperatures and air changes: the project's design values (mep/design_climate.py, 04/11 — a preset with its source or
# the user's own; nothing fixed). U values: on the heat source / connection point, as before.
ASSUMPTIONS = {key: (default, unit, label) for key, (default, unit, label, _src) in _CLIMATE.items()}
ASSUMPTIONS.update({
    "heat_u_openings": (None, "W/m²K", "U κουφωμάτων (από τον κατασκευαστή)"),
    "heat_u_walls": (None, "W/m²K", "U εξωτερικών τοίχων χωρίς σύνθεση"),
    # 07/11 (κουτί ελέγχου): roof / ceiling to outside and floor on the ground or over open space — the project's U
    # (for the ground the equivalent U' of the floor, ΤΟΤΕΕ 20701-1), given by the user, never guessed.
    "heat_u_roof": (None, "W/m²K", "U οροφής / δώματος προς τα έξω"),
    "heat_u_floor": (None, "W/m²K", "U δαπέδου (ισοδύναμο U' προς έδαφος / πιλοτή)"),
})
PROVENANCE = ("DESIGN_DEFAULT — θερμοκρασίες σχεδιασμού του έργου (αλλάζουν ανά έργο, Εγκαταστάσεις › Θέρμανση › "
              "Θερμοκρασίες σχεδιασμού…)· όχι μελέτη θέρμανσης (EN 12831-1 / ΚΕΝΑΚ)")


def assumptions(doc):
    """``{key: value}``: the values on the project's heat source / connection point, else the owner's defaults."""
    from archforge.mep.design_climate import values
    from archforge.mep.heating_layout import source_of
    e = source_of(doc)
    stored = dict(e.params) if e is not None else {}
    from archforge.mep.design_climate import entity as climate
    if climate(doc) is not None:                   # the project's design values (Θερμοκρασίες σχεδιασμού…) win
        stored.update({k: v for k, v in climate(doc).params.items() if k.startswith("heat_u_") and v not in (None, "")})
    out = dict(values(doc))                     # temperatures / air changes: the project's design values
    for key, (default, _unit, _label) in ASSUMPTIONS.items():
        if key not in out:
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
            hosted = [o for o in doc.entities.values()
                      if o.kind in ("door", "window", "opening") and o.parent_id == w.id]
            holes = sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) for o in hosted)
            for o in hosted:
                # Each door / window with its own Uw (Λίστες › Κουφώματα), else the project's one value.
                area_o = float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0))
                from archforge.mep.opening_thermal import uw as _uw
                u_o = _uw(doc, o)[0]          # declared Uw, else EN ISO 10077-1 from Uf/Ug/ψg, else the project's
                if u_o is None:
                    opening_area += area_o
                else:
                    openings_w += area_o * float(u_o) * dt
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
    roof_w, floor_w, roof_a, floor_a, roof_missing, floor_missing = _roof_and_floor(doc, a, dt)
    if roof_missing > 0:
        not_counted.append(f"οροφή / δώμα {_gr(roof_missing)} m² (δώστε U οροφής: Θέρμανση › Θερμοκρασίες σχεδιασμού…)")
    if floor_missing > 0:
        not_counted.append(f"δάπεδο {_gr(floor_missing)} m² (δώστε U δαπέδου: Θέρμανση › Θερμοκρασίες σχεδιασμού…)")
    if no_u_walls:
        not_counted.append(f"{no_u_walls} εξωτερικοί τοίχοι χωρίς σύνθεση (δώστε τύπο τοίχου ή U τοίχων)")
    if opening_area > 0:                             # the area of openings with no U (their own or the project's)
        not_counted.append(f"κουφώματα {_gr(opening_area)} m² (δώστε U κουφωμάτων: Λίστες › Κουφώματα ή του έργου)")
    vent_w = AIR_HEAT * a["heat_air_changes"] * volume * dt
    # Thermal bridges (κριτική v5 k7): Σ ψ·l from the drawing's lengths and the project's ψ — a kind without ψ is said.
    from archforge.mep.thermal_bridges import summary as bridges
    tb = bridges(doc)
    bridges_w = tb["h_tb"] * dt
    if tb["missing_n"]:
        not_counted.append(f"θερμογέφυρες: {tb['missing_n']} θέσεις, {_gr(tb['missing_m'])} m χωρίς ψ "
                           "(Θέρμανση › Θερμογέφυρες…)")
    not_counted += [f"θερμογέφυρες που δεν βρίσκει η γεωμετρία ({tb['not_found']})"]
    parts = [("Εξωτερικοί τοίχοι", walls_w), ("Οροφή / δώμα", roof_w), ("Δάπεδο", floor_w), ("Κουφώματα", openings_w),
             ("Θερμογέφυρες", bridges_w), ("Αερισμός", vent_w)]
    watts = walls_w + roof_w + floor_w + openings_w + bridges_w + vent_w
    from archforge.mep.design_climate import source_text
    return {"watts": round(watts), "kw": round(watts / 1000.0, 1), "delta_t": dt, "season": season,
            "climate_source": source_text(doc),
            "volume_m3": round(volume, 1), "roof_m2": round(roof_a, 2), "floor_m2": round(floor_a, 2), "parts": [(n, round(v)) for n, v in parts],
            "not_counted": not_counted, "assumptions": a, "provenance": PROVENANCE}


def _roof_and_floor_by_face(doc):
    """``{(storey z, room signature): (roof m², floor m²)}``: the part of each room with no room of the storey above
    over it (roof / terrace / ceiling to outside) and with no room of the storey below under it (the lowest storey
    on the ground, or a floor over open space)."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    zs = _storeys(doc)
    faces, shapes = {}, {}
    for z in zs:
        try:
            fs = list(doc.active_room_faces(z=z))
        except Exception:                                  # noqa: BLE001 — said by the volume part already
            fs = []
        polys = [(f.signature, Polygon([(float(p[0]), float(p[1])) for p in f.polygon]).buffer(0)) for f in fs]
        faces[z] = polys
        shapes[z] = unary_union([g for _s, g in polys]) if polys else None
    out = {}
    for i, z in enumerate(zs):
        above = shapes[zs[i + 1]] if i + 1 < len(zs) else None
        below = shapes[zs[i - 1]] if i > 0 else None
        for sig, g in faces[z]:
            roof = g.area - (g.intersection(above).area if above is not None and not above.is_empty else 0.0)
            floor = g.area - (g.intersection(below).area if below is not None and not below.is_empty else 0.0)
            out[(z, sig)] = (roof, floor)
    return out


def _roof_and_floor(doc, a, dt):
    """Losses through what is above and below the rooms (``_roof_and_floor_by_face``) — area × U × ΔT with the
    project's U (``heat_u_roof`` / ``heat_u_floor``).  Without a U the area is said, not guessed."""
    areas = _roof_and_floor_by_face(doc).values()
    roof_a = sum(r for r, _f in areas)
    floor_a = sum(f for _r, f in areas)
    ur, uf = a.get("heat_u_roof"), a.get("heat_u_floor")
    roof_w = roof_a * ur * dt if ur is not None else 0.0
    floor_w = floor_a * uf * dt if uf is not None else 0.0
    return roof_w, floor_w, roof_a, floor_a, (roof_a if ur is None else 0.0), (floor_a if uf is None else 0.0)


def _gr(v, digits=1):
    return f"{v:.{digits}f}".replace(".", ",")


def summary(result):
    """One Greek line for the user: the power, what it rests on and what it leaves out."""
    a = result["assumptions"]
    outside = a["heat_theta_ext_winter"] if result["season"] == "winter" else a["heat_theta_ext_summer"]
    g = lambda v: f"{v:g}".replace(".", ",")
    return (f"Ενδεικτική ισχύς θέρμανσης ≈ {_gr(result['kw'])} kW (μέσα {g(a['heat_theta_int'])} °C, έξω {g(outside)} °C, "
            f"ΔT {g(result['delta_t'])} K, {g(a['heat_air_changes'])} αλλαγές αέρα/ώρα· έξω: {result.get('climate_source', '')}) — "
            f"υπόθεση, όχι μελέτη· οι θερμοκρασίες αλλάζουν: Θέρμανση › Θερμοκρασίες σχεδιασμού… · "
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
