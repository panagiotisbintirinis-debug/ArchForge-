"""Θερμικό φορτίο ανά χώρο (07/11): ό,τι υπολογίζει το ``heat_load`` για όλο το κτίριο, μοιρασμένο στους χώρους —
η βάση για τα σώματα και τον υδραυλικό υπολογισμό (παροχή κάθε κυκλώματος = φορτίο του χώρου του / c·ΔT).

Ίδιοι τύποι, ίδιες υποθέσεις και ίδια όρια με το ``heat_load`` (ενδεικτικό, όχι μελέτη EN 12831-1 / ΚΕΝΑΚ):

* **τοίχοι**: κάθε εξωτερικός τοίχος μοιράζεται στους χώρους που έχουν πλευρά πάνω στον άξονά του, κατά το μήκος
  της πλευράς · τα κουφώματα του τοίχου πάνε στον χώρο όπου πέφτει το κέντρο τους;
* **οροφή / δάπεδο**: το κομμάτι του χώρου χωρίς χώρο από πάνω / από κάτω;
* **αερισμός**: εμβαδόν × μέσο ύψος ορόφου × αλλαγές αέρα (όπως το σύνολο);
* **θερμογέφυρες**: μένουν στο κτίριο (δεν μοιράζονται — λέγεται).

Κανόνας: Σ χώρων + «κτίριο» = το σύνολο του ``heat_load``, όρο προς όρο (τεστ και έλεγχος των bot).
"""
from __future__ import annotations

import math


def _wall_rooms(doc, z, faces, outer):
    """``{(wall id, face index): (overlap m, [openings])}``: the length of each exterior wall each room lies along."""
    out = {}
    hosted = {}
    for o in doc.entities.values():
        if o.kind in ("door", "window", "opening") and o.parent_id:
            hosted.setdefault(o.parent_id, []).append(o)
    for w, _n in outer:
        p = w.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        ops = [(float(o.params.get("offset", 0.0)), o) for o in hosted.get(w.id, ())]
        for fi, f in enumerate(faces):
            poly = f.polygon
            spans = []
            for i in range(len(poly)):
                a, b = poly[i], poly[(i + 1) % len(poly)]
                da = abs((float(a[0]) - x1) * uy - (float(a[1]) - y1) * ux)
                db = abs((float(b[0]) - x1) * uy - (float(b[1]) - y1) * ux)
                if da > 1e-3 or db > 1e-3:
                    continue
                ta = (float(a[0]) - x1) * ux + (float(a[1]) - y1) * uy
                tb = (float(b[0]) - x1) * ux + (float(b[1]) - y1) * uy
                lo, hi = max(0.0, min(ta, tb)), min(L, max(ta, tb))
                if hi - lo > 1e-6:
                    spans.append((lo, hi))
            if spans:
                length = sum(hi - lo for lo, hi in spans)
                mine = [o for c, o in ops if any(lo - 1e-6 <= c <= hi + 1e-6 for lo, hi in spans)]
                out[(w.id, fi)] = (length, mine)
    return out


def room_loads(doc, season="winter"):
    """``{"rooms": [{"z", "signature", "name", "area_m2", "parts": {...}, "watts"}], "building": {...},
    "total": heat_load result}``."""
    from archforge.architecture.wall_types import indicative_u
    from archforge.mep.heat_load import AIR_HEAT, _polygon_area, _roof_and_floor_by_face, _storeys, heat_load
    from archforge.mep.opening_thermal import uw
    from archforge.mep.ventilation import exterior_walls
    total = heat_load(doc, season)
    a, dt = total["assumptions"], total["delta_t"]
    rooms = []
    zs = _storeys(doc)
    by_face = _roof_and_floor_by_face(doc)
    for z in zs:
        try:
            faces = list(doc.active_room_faces(z=z))
            outer = exterior_walls(doc, z)
        except Exception:                                  # noqa: BLE001 — the total says what it could not read
            continue
        heights = [float(e.params["height"]) for e in doc.entities.values()
                   if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 0.05]
        h = sum(heights) / len(heights) if heights else 0.0
        shares = _wall_rooms(doc, z, faces, outer)
        walls = {w.id: w for w, _n in outer}
        for fi, f in enumerate(faces):
            meta = doc.room_metadata(f.signature) if hasattr(doc, "room_metadata") else {}
            area = _polygon_area(f.polygon)
            wall_w = open_w = 0.0
            for (wid, k), (length, ops) in shares.items():
                if k != fi:
                    continue
                p = walls[wid].params
                holes = sum(float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) for o in ops)
                for o in ops:
                    u_o = uw(doc, o)[0]
                    if u_o is not None:
                        open_w += float(o.params.get("width", 0.0)) * float(o.params.get("height", 0.0)) * float(u_o) * dt
                u = indicative_u(p.get("wall_type", "generic"), doc)
                if u is None:
                    u = a["heat_u_walls"]
                if u is not None:
                    wall_w += max(0.0, length * float(p["height"]) - holes) * u * dt
            roof_a, floor_a = by_face.get((z, f.signature), (0.0, 0.0))
            ur, uf = a.get("heat_u_roof"), a.get("heat_u_floor")
            parts = {"Εξωτερικοί τοίχοι": wall_w, "Οροφή / δώμα": roof_a * ur * dt if ur is not None else 0.0,
                     "Δάπεδο": floor_a * uf * dt if uf is not None else 0.0, "Κουφώματα": open_w,
                     "Αερισμός": AIR_HEAT * a["heat_air_changes"] * area * h * dt}
            rooms.append({"z": z, "signature": f.signature, "name": meta.get("name") or f"Χώρος {fi + 1}",
                          "use": meta.get("use", ""), "area_m2": round(area, 2), "polygon": [tuple(map(float, q[:2])) for q in f.polygon],
                          "parts": {k: round(v, 1) for k, v in parts.items()}, "watts": round(sum(parts.values()), 1)})
    whole = dict(total["parts"])
    building = {k: round(float(v) - sum(r["parts"].get(k, 0.0) for r in rooms), 1) for k, v in whole.items()}
    return {"rooms": rooms, "building": building, "total": total}


def emitter_loads(doc):
    """``{emitter id: W}``: each room's load shared equally among the radiators / fan coils in it (the engineer
    sizes them — this is the flow each needs, for the hydraulics).  Emitters outside every room get nothing."""
    from archforge.mep.heating_layout import EMITTERS, heating_points
    from archforge.mep.ventilation import _floor_of
    from archforge.assistant.understanding import inside
    loads = room_loads(doc)
    ems = [e for e in heating_points(doc) if e.params.get("point_type") in EMITTERS]
    out = {e.id: 0.0 for e in ems}
    for r in loads["rooms"]:
        here = [e for e in ems if abs(_floor_of(doc, float(e.params["z"])) - r["z"]) < 1e-6
                and inside(r["polygon"], float(e.params["x"]), float(e.params["y"]))]
        for e in here:
            out[e.id] += r["watts"] / len(here)
    return out
