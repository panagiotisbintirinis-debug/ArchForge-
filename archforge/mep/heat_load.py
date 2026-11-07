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
    # 07/11 (owner: «σε πολυκατοικία με κοινόχρηστες σκάλες οι απώλειες πρέπει να υπολογίζουν και αυτά»): what
    # separates a heated room from an unheated one (stairwell, storage, boiler room) loses A·U·b·ΔT.  DESIGN_DEFAULT
    # 0,5 — to be checked against ΤΟΤΕΕ 20701-1 / ΤΕΕ-ΚΕΝΑΚ; changed per project.
    "heat_b_unheated": (0.5, "", "Συντελεστής b προς μη θερμαινόμενους χώρους"),
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
        stored.update({k: v for k, v in climate(doc).params.items() if k.startswith(("heat_u_", "heat_b_")) and v not in (None, "")})
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
    rooms_out = []
    b = a.get("heat_b_unheated")
    unheated_w = 0.0
    for z in _storeys(doc):
        try:
            outer = exterior_walls(doc, z)
        except Exception as exc:
            not_computed("heat.exterior", f"Θέρμανση: δεν βρέθηκαν οι εξωτερικοί τοίχοι του ορόφου {z:+.2f}", exc=exc)
            not_counted.append(f"εξωτερικοί τοίχοι ορόφου {z:+.2f}")
            continue
        try:
            faces = list(doc.active_room_faces(z=z))
        except Exception as exc:
            not_computed("heat.rooms", f"Θέρμανση: δεν αναγνωρίστηκαν οι χώροι του ορόφου {z:+.2f}", exc=exc)
            not_counted.append(f"αερισμός ορόφου {z:+.2f}")
            faces = None
        heights = [float(e.params["height"]) for e in doc.entities.values()
                   if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 0.05]
        h = sum(heights) / len(heights) if heights else 0.0
        if faces:
            # With rooms (07/11): every loss belongs to a heated room — the exterior walls along it, its openings,
            # what separates it from an unheated room (stairwell, storage…: × b), its air.  Unheated rooms lose
            # nothing of their own (ΤΟΤΕΕ 20701-1: they are outside the heated envelope).
            st = _storey_rooms(doc, z, faces, outer, a, dt, h)
            rooms_out += st["rooms"]
            walls_w += st["walls_w"]; openings_w += st["openings_w"]; unheated_w += st["unheated_w"]
            opening_area += st["opening_area"]; no_u_walls += st["no_u_walls"]
            volume += st["volume"]
            continue
        for w, _normal in outer:                     # a storey without closed rooms: its exterior walls as before
            ww, ow, oa, missing = _wall_loss(doc, w, a, dt)
            walls_w += ww; openings_w += ow; opening_area += oa; no_u_walls += missing
    if rooms_out and b is None and any(r["unheated_m2"] for r in rooms_out):
        not_counted.append("όρια προς μη θερμαινόμενους χώρους (δώστε συντελεστή b: Θέρμανση › Θερμοκρασίες σχεδιασμού…)")
    roof_w = sum(r["parts"]["Οροφή / δώμα"] for r in rooms_out)
    floor_w = sum(r["parts"]["Δάπεδο"] for r in rooms_out)
    roof_a = sum(r["roof_m2"] for r in rooms_out)
    floor_a = sum(r["floor_m2"] for r in rooms_out)
    roof_missing = roof_a if a.get("heat_u_roof") is None else 0.0
    floor_missing = floor_a if a.get("heat_u_floor") is None else 0.0
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
             ("Προς μη θερμαινόμενους", unheated_w), ("Θερμογέφυρες", bridges_w), ("Αερισμός", vent_w)]
    watts = walls_w + roof_w + floor_w + openings_w + unheated_w + bridges_w + vent_w
    apartments = {}
    for r in rooms_out:
        apartments[r["apartment"]] = apartments.get(r["apartment"], 0.0) + r["watts"]
    from archforge.mep.design_climate import source_text
    return {"watts": round(watts), "kw": round(watts / 1000.0, 1), "delta_t": dt, "season": season,
            "climate_source": source_text(doc),
            "volume_m3": round(volume, 1), "roof_m2": round(roof_a, 2), "floor_m2": round(floor_a, 2),
            "rooms": rooms_out, "apartments": {k: round(v) for k, v in apartments.items()}, "parts": [(n, round(v)) for n, v in parts],
            "not_counted": not_counted, "assumptions": a, "provenance": PROVENANCE}


def _heated(doc, face):
    from archforge.mep.heating_layout import UNHEATED_USES, _room_use
    return not any(_room_use(doc, face).startswith(u) for u in UNHEATED_USES)


def apartment_of(doc, face, z):
    """The room's apartment (Ιδιότητες χώρου ▸ Διαμέρισμα); unheated rooms are the building's common parts; without
    one, one apartment per storey (owner 07/11: «προεπιλογή ένα ανά όροφο»)."""
    meta = doc.room_metadata(face.signature) if hasattr(doc, "room_metadata") else {}
    own = str(meta.get("apartment") or "").strip()
    if own:
        return own
    if not _heated(doc, face):
        return "Κοινόχρηστα"
    from archforge.core.storey_names import level_name
    name = next((n for n, v in doc.levels.items() if abs(float(v) - z) < 0.05), None)
    return f"Διαμέρισμα {level_name(name) if name else f'{z:+.2f}'}"


def _wall_loss(doc, w, a, dt, length=None, ops=None, factor=1.0):
    """``(wall W, openings W, openings m² without U, 1 if the wall has no U)`` for ``length`` of the wall (all of it by
    default) with the openings ``ops`` (its own by default), × ``factor`` (b towards an unheated room)."""
    from archforge.architecture.wall_types import indicative_u
    from archforge.mep.opening_thermal import uw
    p = w.params
    L = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"])) if length is None else length
    if ops is None:
        ops = [o for o in doc.entities.values() if o.kind in ("door", "window", "opening") and o.parent_id == w.id]
    holes = sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) for o in ops)
    open_w = open_missing = 0.0
    for o in ops:
        area_o = float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0))
        u_o = uw(doc, o)[0]          # declared Uw, else EN ISO 10077-1 from Uf/Ug/ψg, else the project's
        if u_o is None:
            open_missing += area_o
        else:
            open_w += area_o * float(u_o) * dt * factor
    u = indicative_u(p.get("wall_type", "generic"), doc)
    if u is None:
        u = a["heat_u_walls"]                # the project's one value for walls without a build-up
    if u is None:
        return 0.0, open_w, open_missing, 1
    return max(0.0, L * float(p["height"]) - holes) * u * dt * factor, open_w, open_missing, 0


def _spans(w, poly):
    """Stretches ``(lo, hi)`` along wall ``w``'s axis where a side of ``poly`` lies on it."""
    p = w.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return []
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    out = []
    for i in range(len(poly)):
        q, r = poly[i], poly[(i + 1) % len(poly)]
        if abs((float(q[0]) - x1) * uy - (float(q[1]) - y1) * ux) > 1e-3 or \
                abs((float(r[0]) - x1) * uy - (float(r[1]) - y1) * ux) > 1e-3:
            continue
        ta = (float(q[0]) - x1) * ux + (float(q[1]) - y1) * uy
        tb = (float(r[0]) - x1) * ux + (float(r[1]) - y1) * uy
        lo, hi = max(0.0, min(ta, tb)), min(L, max(ta, tb))
        if hi - lo > 1e-6:
            out.append((lo, hi))
    return out


def _overlap(xs, ys):
    return [(max(a, c), min(b, d)) for a, b in xs for c, d in ys if min(b, d) - max(a, c) > 1e-6]


def _ops_in(doc, w, spans):
    ops = [o for o in doc.entities.values() if o.kind in ("door", "window", "opening") and o.parent_id == w.id]
    return [o for o in ops if any(lo - 1e-6 <= float(o.params.get("offset", 0.0)) <= hi + 1e-6 for lo, hi in spans)]


def _storey_rooms(doc, z, faces, outer, a, dt, h):
    """Each heated room of a storey with its losses: exterior walls along it, their openings, the walls / doors to an
    unheated room × b, roof / floor (``_slabs``), air.  Totals of the storey for ``heat_load``."""
    b = a.get("heat_b_unheated")
    exterior = {w.id for w, _n in outer}
    walls = [e for e in doc.entities.values() if e.kind == "wall" and e.visible
             and abs(float(e.params.get("z", 0.0)) - z) < 0.05]
    heated = [_heated(doc, f) for f in faces]
    slabs = _slabs(doc)
    out = {"rooms": [], "walls_w": 0.0, "openings_w": 0.0, "unheated_w": 0.0, "opening_area": 0.0, "no_u_walls": 0,
           "volume": 0.0}
    no_u = set()
    spans = {(w.id, i): _spans(w, f.polygon) for w in walls for i, f in enumerate(faces)}
    for i, f in enumerate(faces):
        area = _polygon_area(f.polygon)
        meta = doc.room_metadata(f.signature) if hasattr(doc, "room_metadata") else {}
        room = {"z": z, "signature": f.signature, "name": meta.get("name") or f"Χώρος {i + 1}", "use": meta.get("use", ""),
                "heated": heated[i], "apartment": apartment_of(doc, f, z), "area_m2": round(area, 2),
                "polygon": [tuple(map(float, q[:2])) for q in f.polygon], "unheated_m2": 0.0,
                "roof_m2": 0.0, "floor_m2": 0.0}
        parts = {"Εξωτερικοί τοίχοι": 0.0, "Οροφή / δώμα": 0.0, "Δάπεδο": 0.0, "Κουφώματα": 0.0,
                 "Προς μη θερμαινόμενους": 0.0, "Αερισμός": 0.0}
        if heated[i]:
            for w in walls:
                mine = spans[(w.id, i)]
                if not mine:
                    continue
                if w.id in exterior:
                    ww, ow, oa, miss = _wall_loss(doc, w, a, dt, sum(hi - lo for lo, hi in mine), _ops_in(doc, w, mine))
                    parts["Εξωτερικοί τοίχοι"] += ww; parts["Κουφώματα"] += ow
                    out["opening_area"] += oa
                    if miss:
                        no_u.add(w.id)
                    continue
                # Interior wall: the stretch shared with an unheated room loses towards it (× b).
                cold = [s_ for k, g in enumerate(faces) if not heated[k] and k != i for s_ in spans[(w.id, k)]]
                shared = _overlap(mine, cold)
                if shared:
                    length = sum(hi - lo for lo, hi in shared)
                    room["unheated_m2"] += length * float(w.params["height"])
                    if b is not None:
                        ww, ow, _oa, _m = _wall_loss(doc, w, a, dt, length, _ops_in(doc, w, shared), float(b))
                        parts["Προς μη θερμαινόμενους"] += ww + ow
            roof, floor, roof_cold, floor_cold = slabs.get((z, f.signature), (0.0, 0.0, 0.0, 0.0))
            room["roof_m2"], room["floor_m2"] = round(roof, 2), round(floor, 2)
            room["unheated_m2"] += roof_cold + floor_cold
            ur, uf = a.get("heat_u_roof"), a.get("heat_u_floor")
            if ur is not None:
                parts["Οροφή / δώμα"] = roof * ur * dt
            if uf is not None:
                parts["Δάπεδο"] = floor * uf * dt
            if b is not None:     # a slab over / under an unheated room: its U (roof / floor) × b
                parts["Προς μη θερμαινόμενους"] += (roof_cold * (ur or 0.0) + floor_cold * (uf or 0.0)) * dt * float(b)
            parts["Αερισμός"] = AIR_HEAT * a["heat_air_changes"] * area * h * dt
            out["volume"] += area * h
        out["walls_w"] += parts["Εξωτερικοί τοίχοι"]; out["openings_w"] += parts["Κουφώματα"]
        out["unheated_w"] += parts["Προς μη θερμαινόμενους"]
        room["unheated_m2"] = round(room["unheated_m2"], 2)
        room["parts"] = {k: round(v, 1) for k, v in parts.items()}
        room["watts"] = round(sum(parts.values()), 1)
        out["rooms"].append(room)
    out["no_u_walls"] = len(no_u)
    return out


def _slabs(doc):
    """``{(storey z, room signature): (roof m², floor m², roof over an unheated room m², floor over one m²)}`` for
    the heated rooms: the part with no room above / below is roof / floor to outside or ground; under / over an
    unheated room it loses × b."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    zs = _storeys(doc)
    faces, warm, cold = {}, {}, {}
    for z in zs:
        try:
            fs = list(doc.active_room_faces(z=z))
        except Exception:                                  # noqa: BLE001 — said by the storey loop
            fs = []
        polys = [(f.signature, _heated(doc, f), Polygon([(float(p[0]), float(p[1])) for p in f.polygon]).buffer(0)) for f in fs]
        faces[z] = polys
        warm[z] = unary_union([g for _s, h, g in polys if h]) if any(h for _s, h, _g in polys) else None
        cold[z] = unary_union([g for _s, h, g in polys if not h]) if any(not h for _s, h, _g in polys) else None

    def cut(g, other):
        return g.intersection(other).area if other is not None and not other.is_empty else 0.0
    out = {}
    for i, z in enumerate(zs):
        up, down = (zs[i + 1] if i + 1 < len(zs) else None), (zs[i - 1] if i > 0 else None)
        for sig, heated, g in faces[z]:
            if not heated:
                continue
            roof_cold = cut(g, cold.get(up)) if up is not None else 0.0
            floor_cold = cut(g, cold.get(down)) if down is not None else 0.0
            roof = g.area - (cut(g, warm.get(up)) if up is not None else 0.0) - roof_cold
            floor = g.area - (cut(g, warm.get(down)) if down is not None else 0.0) - floor_cold
            out[(z, sig)] = (max(0.0, roof), max(0.0, floor), roof_cold, floor_cold)
    return out


def _roof_and_floor_by_face(doc):
    """``{(z, signature): (roof m², floor m²)}`` of the heated rooms (``_slabs``)."""
    return {k: (r, f) for k, (r, f, _rc, _fc) in _slabs(doc).items()}


def _roof_and_floor(doc, a, dt):
    """Roof / floor losses of the heated rooms with the project's U — without a U the area is said, not guessed."""
    areas = _slabs(doc).values()
    roof_a = sum(r for r, _f, _rc, _fc in areas)
    floor_a = sum(f for _r, f, _rc, _fc in areas)
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
            f"δεν μετρήθηκαν: {'; '.join(result['not_counted'])}"
            + ("" if len(result.get("apartments") or {}) < 2 else " · ανά διαμέρισμα: " + ", ".join(
                f"{k} {_gr(v / 1000.0)} kW" for k, v in result["apartments"].items() if v)))


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
