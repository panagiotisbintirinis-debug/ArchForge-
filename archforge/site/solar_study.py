"""Μελέτη ηλιασμού και σκίασης των κουφωμάτων (κενό 5 της αποτύπωσης δυνατοτήτων, 06/11).

Για κάθε παράθυρο / πόρτα σε εξωτερικό τοίχο και για έναν μήνα: πόσες ώρες άμεσου ήλιου παίρνει, από τι ώρα ως τι ώρα,
και τι ποσοστό της ημέρας το σκιάζει το ίδιο το κτίριο (προεξοχές, μπαλκόνια, στέγες, πτέρυγες), τα φυτά ή το έδαφος.

* Ήλιος: ``rendering/sun.sun_position`` (απόκλιση Cooper, ηλιακή ώρα — όχι ώρα ρολογιού), μέση μέρα του μήνα.
* Θέση: γεωγραφικό πλάτος και προσανατολισμός του βορρά του έργου (``design_climate``: ``latitude``, ``north_deg`` =
  πόσες μοίρες δεξιόστροφα από το +y της κάτοψης δείχνει ο πραγματικός βορράς). Προεπιλογή 38° Β, βορράς = +y
  (DESIGN_DEFAULT, λέγεται): αλλάζουν από «Ηλιασμός ▸ Θέση και βορράς».
* Σκίαση: ακτίνες από 3 × 3 σημεία της εξωτερικής επιφάνειας του κουφώματος προς τον ήλιο, κάθε ``STEP_MIN`` λεπτά,
  απέναντι στα τρίγωνα του ίδιου μοντέλου 3D (τοίχοι, πλάκες, στέγες, σκάλες, φέρων, φυτά, έδαφος). Τζάμια, έπιπλα και
  δίκτυα δεν σκιάζουν. Ήλιος με γωνία πρόσπτωσης > 85° στο τζάμι δεν μετριέται (γλιστρά πάνω του).

Τι δεν είναι: ηλιακά κέρδη σε kWh (χρειάζονται δεδομένα ακτινοβολίας της ΤΟΤΕΕ 20701-3 και g κουφώματος), γειτονικά
κτίρια (δεν υπάρχουν στο μοντέλο), συννεφιά.
"""
from __future__ import annotations

import math

import numpy as np

DEFAULT_LATITUDE = 38.0
STEP_MIN = 15
GRAZING_DEG = 85.0
NOT_SHADING = {"window", "door", "opening", "library_object", "cabinet", "kitchen_part", "mep_pipe", "elec_box",
               "elec_cable", "section_line", "camera", "mep_terminal", "electrical_point", "plumbing_point",
               "heating_point", "drainage_point", "ventilation_point"}
MONTHS = ("Ιανουάριος", "Φεβρουάριος", "Μάρτιος", "Απρίλιος", "Μάιος", "Ιούνιος", "Ιούλιος", "Αύγουστος",
          "Σεπτέμβριος", "Οκτώβριος", "Νοέμβριος", "Δεκέμβριος")


def site(doc):
    """``{"latitude", "north_deg", "assumed": [...]}``: the project's place on the earth (assumed values said)."""
    from archforge.mep.design_climate import entity
    p = dict(entity(doc).params) if entity(doc) is not None else {}
    assumed = []
    if p.get("latitude") is None:
        assumed.append(f"γεωγραφικό πλάτος {DEFAULT_LATITUDE:g}° Β (προεπιλογή)")
    if p.get("north_deg") is None:
        assumed.append("βορράς = +y της κάτοψης (προεπιλογή)")
    return {"latitude": float(p.get("latitude", DEFAULT_LATITUDE)), "north_deg": float(p.get("north_deg", 0.0)),
            "assumed": assumed}


def set_site_command(doc, latitude=None, north_deg=None):
    from archforge.mep.design_climate import set_command
    changes = {}
    if latitude is not None:
        if not -66.0 <= float(latitude) <= 66.0:
            raise ValueError("γεωγραφικό πλάτος −66° … 66°")
        changes["latitude"] = float(latitude)
    if north_deg is not None:
        changes["north_deg"] = float(north_deg) % 360.0
    return set_command(doc, changes)


def sun_vector(hour, month, latitude, north_deg):
    """Unit vector towards the sun in plan coordinates (x, y, z up), or None below the horizon."""
    from archforge.rendering.sun import sun_direction, sun_position
    el, az = sun_position(hour, month, latitude)
    if el <= 0:
        return None
    # True north is ``north_deg`` clockwise from the plan's +y: a true azimuth A is the plan azimuth A + north_deg
    # (north_deg = 90°: the sun in the true north stands on the plan's +x).
    return np.array(sun_direction(el, (az + north_deg) % 360.0))


def obstacles(doc):
    """``(v0, e1, e2)`` arrays of every shading triangle of the model (Möller–Trumbore form)."""
    from archforge.output.section_cut import _objects
    tris = []
    for o in _objects(doc):
        if o["kind"] in NOT_SHADING or not o["triangles"]:
            continue
        v = np.asarray(o["vertices"], dtype=float)
        t = np.asarray(o["triangles"], dtype=int)
        tris.append(v[t])
    if not tris:
        z = np.zeros((0, 3))
        return z, z, z
    all_t = np.concatenate(tris)
    v0 = all_t[:, 0]
    return v0, all_t[:, 1] - v0, all_t[:, 2] - v0


def blocked(origins, direction, tri, eps=1e-6):
    """Boolean per origin: does the ray origin + t·direction (t > 0) hit any triangle?"""
    v0, e1, e2 = tri
    if len(v0) == 0:
        return np.zeros(len(origins), dtype=bool)
    d = np.asarray(direction, dtype=float)
    pvec = np.cross(d, e2)                                  # (T, 3)
    det = np.einsum("ij,ij->i", e1, pvec)
    ok = np.abs(det) > eps
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    out = np.zeros(len(origins), dtype=bool)
    for i, o in enumerate(origins):
        tvec = o - v0
        u = np.einsum("ij,ij->i", tvec, pvec) * inv
        qvec = np.cross(tvec, e1)
        v = (qvec @ d) * inv
        t = np.einsum("ij,ij->i", e2, qvec) * inv
        hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-4)
        out[i] = bool(hit.any())
    return out


def window_samples(doc, opening, wall, outward, n=3, out=0.03):
    """``(points (n·n, 3), normal (3,))``: points on the outside face of the opening, a little outside it."""
    p, wp = opening.params, wall.params
    x1, y1, x2, y2 = (float(wp[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = outward
    t = float(wp["thickness"]) / 2 + out
    c, w = float(p["offset"]), float(p["width"])
    z0 = float(wp.get("z", 0.0)) + (float(p.get("sill", 0.0)) if opening.kind == "window" else 0.0)
    h = float(p["height"])
    pts = []
    for i in range(n):
        for j in range(n):
            s = c - w / 2 + w * (i + 0.5) / n
            z = z0 + h * (j + 0.5) / n
            pts.append((x1 + ux * s + nx * t, y1 + uy * s + ny * t, z))
    return np.array(pts), np.array((nx, ny, 0.0))


def study(doc, month=12, step_min=STEP_MIN, n=3):
    """``{"month", "site", "rows": [{"id", "kind", "storey_z", "facing", "sun_h", "possible_h", "shaded_pct",
    "first", "last"}], "day_h"}`` for every exterior door / window."""
    from archforge.mep.ventilation import exterior_walls
    s = site(doc)
    tri = obstacles(doc)
    hours = [h / 60.0 for h in range(0, 24 * 60, step_min)]
    suns = [(h, sun_vector(h + step_min / 120.0, month, s["latitude"], s["north_deg"])) for h in hours]
    suns = [(h, v) for h, v in suns if v is not None]
    rows = []
    storeys = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall" and e.visible})
    for z in storeys:
        for wall, outward in exterior_walls(doc, z):
            for o in doc.entities.values():
                if o.kind not in ("window", "door") or o.parent_id != wall.id or not o.visible:
                    continue
                pts, normal = window_samples(doc, o, wall, outward, n)
                lit = possible = 0.0
                first = last = None
                for h, v in suns:
                    cos_i = float(normal @ v)
                    if cos_i <= math.cos(math.radians(GRAZING_DEG)):
                        continue
                    possible += step_min / 60.0
                    frac = 1.0 - float(blocked(pts, v, tri).mean())
                    if frac > 0:
                        lit += frac * step_min / 60.0
                        first = h if first is None else first
                        last = h + step_min / 60.0
                rows.append({"id": o.id, "kind": o.kind, "storey_z": z, "facing": facing(outward, s["north_deg"]),
                             "sun_h": round(lit, 2), "possible_h": round(possible, 2),
                             "shaded_pct": round(100 * (1 - lit / possible), 0) if possible > 0 else None,
                             "first": first, "last": last})
    day = sum(step_min / 60.0 for _h, _v in suns)
    return {"month": month, "site": s, "rows": rows, "day_h": round(day, 2)}


COMPASS = ("Β", "ΒΑ", "Α", "ΝΑ", "Ν", "ΝΔ", "Δ", "ΒΔ")


def facing(outward, north_deg=0.0):
    """«Ν», «ΒΑ» …: where the outside of a wall looks, on the true compass."""
    az = (math.degrees(math.atan2(outward[0], outward[1])) - north_deg) % 360.0      # plan azimuth → true
    return COMPASS[int(((az + 22.5) % 360) // 45)]


def hhmm(h):
    if h is None:
        return "—"
    m = int(round(h * 60))
    return f"{m // 60:02d}:{m % 60:02d}"
