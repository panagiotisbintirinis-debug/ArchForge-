"""Άνεμος της περιοχής και έκθεση μπαλκονιών / όψεων (ιδιοκτήτης 06/11: «κατεύθυνση ανέμου περιοχής… μπορεί να
επηρεάσει τη χρήση μπαλκονιών και θερμοκρασίες εξωτερικές»).

* Δεδομένα: ``mep/totee_20701_3_site`` — ΤΟΤΕΕ 20701-3/2010, Παράρτημα Α (επικρατούσα διεύθυνση και μέση ένταση σε
  μποφόρ για Ιανουάριο, Φεβρουάριο, Ιούλιο, Αύγουστο· θερμοκρασίες των μηνών), Πίν. 3.11 (μέση ταχύτητα m/s ανά μήνα),
  Πίν. 1.1 (θέση του σταθμού). Ο σταθμός είναι αυτός των θερμοκρασιών σχεδιασμού του έργου (``design_climate``).
* Ο χρήστης μπορεί να δώσει δική του διεύθυνση χειμώνα / καλοκαιριού (``wind_dir_winter`` / ``wind_dir_summer``), π.χ.
  από τοπική γνώση ή μετρήσεις — τότε λέγεται «δική σας».
* Έκθεση μιας πλευράς: ο άνεμος έρχεται ΑΠΟ τη διεύθυνση του πίνακα· πλευρά που κοιτά ως 67,5° από αυτήν =
  «εκτεθειμένη», 112,5° και πάνω = «υπήνεμη», ενδιάμεσα «πλάγια» (μισός τομέας της ροδιάς των 8 διευθύνσεων,
  DESIGN_DEFAULT). Ένα μπαλκόνι που το καλύπτει το κτίριο προς τον άνεμο (ακτίνα 1,2 m πάνω από την πλάκα, ως
  ``SHELTER_REACH``) λέγεται «προστατευμένο από το κτίριο».

Τι δεν είναι: ροή ανέμου γύρω από το κτίριο (CFD), ριπές, μετρήσεις στο οικόπεδο. Η ΤΟΤΕΕ 20701-2 υπολογίζει το Rse με
άνεμο 4 m/s (Πίν. 3β): η σύγκριση με τον άνεμο του σταθμού λέγεται, το Rse δεν αλλάζει χωρίς το κείμενο του EN ISO 6946.
"""
from __future__ import annotations

import math

import numpy as np

from archforge.mep import totee_20701_3_site as TS

MONTH_NAMES = {1: "Ιανουάριος", 2: "Φεβρουάριος", 7: "Ιούλιος", 8: "Αύγουστος"}
WINTER, SUMMER = (1, 2), (7, 8)
WINDWARD_DEG, LEEWARD_DEG = 67.5, 112.5
SHELTER_REACH = 15.0             # m: the house farther than this upwind does not count as shelter (DESIGN_DEFAULT)
RSE_WIND = 4.0                   # m/s behind Rse = 0,04 (ΤΟΤΕΕ 20701-2/2021 Πίν. 3β, Παρατηρήσεις)
OVERRIDES = {"wind_dir_winter": WINTER, "wind_dir_summer": SUMMER}


def station(doc):
    """The ΤΟΤΕΕ station / town of the project's design temperatures, or None (the user's own value)."""
    from archforge.mep.design_climate import preset_of
    key = preset_of(doc)
    return key[len("totee:"):] if key.startswith("totee:") else None


def climate(doc):
    """``{"station", "lat", "months": {m: {"dir", "bf", "ms", "abs_min", "mean_min", "mean_max", "abs_max", "from"}},
    "speed": [12 m/s] or None, "notes": [...]}`` — the project's wind and month temperatures."""
    from archforge.mep.design_climate import entity
    st = station(doc)
    own = dict(entity(doc).params) if entity(doc) is not None else {}
    app = TS.APPENDIX_A.get(st) if st else None
    speed = TS.WIND_SPEED.get(st) if st else None
    months, notes = {}, []
    for m in (1, 2, 7, 8):
        row = app["months"].get(m) if app else None
        d = {"dir": None, "bf": None, "ms": speed[m - 1] if speed else None, "abs_min": None, "mean_min": None,
             "mean_max": None, "abs_max": None, "from": None}
        if row:
            d.update(dir=row[0], bf=row[1], abs_min=row[2], mean_min=row[3], mean_max=row[4], abs_max=row[5],
                     **{"from": f"{TS.SOURCE} Παρ. Α ({st}, {app['period']})"})
        for key, ms in OVERRIDES.items():
            if m in ms and own.get(key):
                d["dir"], d["from"] = own[key], "δική σας"
        months[m] = d
    if st is None:
        notes.append("οι θερμοκρασίες σχεδιασμού είναι δικές σας: χωρίς σταθμό ΤΟΤΕΕ, ο άνεμος μόνο αν τον δώσετε")
    elif app is None:
        notes.append(f"«{st}» δεν είναι σταθμός του Παραρτήματος Α της ΤΟΤΕΕ 20701-3: δώστε τη διεύθυνση του ανέμου")
    return {"station": st, "lat": TS.STATIONS.get(st, (None,))[0] if st else None, "months": months,
            "speed": list(speed) if speed else None, "notes": notes}


def set_command(doc, winter=None, summer=None):
    """The user's own prevailing direction for winter / summer ('' = back to ΤΟΤΕΕ) — one undo."""
    from archforge.mep.design_climate import set_command as climate_set
    changes = {}
    for key, v in (("wind_dir_winter", winter), ("wind_dir_summer", summer)):
        if v is None:
            continue
        if v and v not in TS.DIRECTIONS:
            raise ValueError(f"διεύθυνση ανέμου: μία από {', '.join(TS.DIRECTIONS)}")
        changes[key] = v or None
    return climate_set(doc, changes)


def _angle(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def exposure(facing_deg, wind_dir):
    """«εκτεθειμένη» / «πλάγια» / «υπήνεμη» of a side whose outside looks to ``facing_deg`` (true, clockwise from N)."""
    gap = _angle(facing_deg, TS.DIRECTION_DEG[wind_dir])
    return "εκτεθειμένη" if gap <= WINDWARD_DEG else ("υπήνεμη" if gap >= LEEWARD_DEG else "πλάγια")


def _plan_direction(true_deg, north_deg):
    """Unit (x, y) in the plan towards the true azimuth ``true_deg`` (north_deg: true north clockwise from +y)."""
    a = math.radians(true_deg + north_deg)
    return math.sin(a), math.cos(a)


def balconies(doc):
    """``[floor entity]`` of the balconies (role 'balcony')."""
    return [e for e in doc.entities.values() if e.kind == "floor" and e.params.get("role") == "balcony" and e.visible]


def balcony_sides(doc, e):
    """``[(a, b, outward (x, y), free)]`` of a balcony outline (free = not against a wall of its storey)."""
    from archforge.architecture.balcony import _against_wall, _storey_walls, slab_level
    pts = [tuple(map(float, q)) for q in e.params["points"]]
    area2 = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
    walls = _storey_walls(doc, slab_level(e.params))
    out = []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        L = math.dist(a, b) or 1.0
        dx, dy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        n = (dy, -dx) if area2 > 0 else (-dy, dx)          # counter-clockwise outline: the outside is on the right
        out.append((a, b, n, not _against_wall(a, b, walls)))
    return out


def sheltered(doc, e, wind_dir, north_deg, tri=None):
    """True when the house stands between the balcony and the wind (a ray from 1,2 m above the slab towards the wind
    meets the model within ``SHELTER_REACH``)."""
    from archforge.architecture.balcony import slab_level
    from archforge.site.solar_study import blocked, obstacles
    tri = obstacles(doc) if tri is None else tri
    pts = np.array(e.params["points"], dtype=float)
    cx, cy = pts[:, 0].mean(), pts[:, 1].mean()
    z = slab_level(e.params) + 1.2
    dx, dy = _plan_direction(TS.DIRECTION_DEG[wind_dir], north_deg)
    v0, e1, e2 = tri
    if len(v0):
        near = np.linalg.norm(v0[:, :2] - np.array([cx, cy]), axis=1) <= SHELTER_REACH + 10.0
        tri = (v0[near], e1[near], e2[near])
    samples = np.array([(cx, cy, z)] + [(q[0] * 0.7 + cx * 0.3, q[1] * 0.7 + cy * 0.3, z) for q in pts])
    hits = blocked(samples, (dx, dy, 0.0), tri, max_t=SHELTER_REACH)
    return bool(hits.mean() >= 0.5)


def balcony_study(doc):
    """One row per balcony and month (1, 2, 7, 8): the wind, how its free sides meet it, shelter, sun hours, temps."""
    from archforge.architecture.balcony import slab_level
    from archforge.site.solar_study import blocked, obstacles, site, sun_vector, STEP_MIN
    cl = climate(doc)
    s = site(doc)
    tri = obstacles(doc)
    rows = []
    for e in balconies(doc):
        sides = [x for x in balcony_sides(doc, e) if x[3]]
        pts = np.array(e.params["points"], dtype=float)
        z = slab_level(e.params) + 0.9
        samples = np.array([(pts[:, 0].mean(), pts[:, 1].mean(), z)] +
                           [(q[0] * 0.6 + pts[:, 0].mean() * 0.4, q[1] * 0.6 + pts[:, 1].mean() * 0.4, z) for q in pts])
        for m, w in cl["months"].items():
            sun = 0.0
            for h in range(0, 24 * 60, STEP_MIN):
                v = sun_vector(h / 60.0 + STEP_MIN / 120.0, m, s["latitude"], s["north_deg"])
                if v is not None:
                    sun += (1.0 - float(blocked(samples, v, tri).mean())) * STEP_MIN / 60.0
            row = {"id": e.id, "level": slab_level(e.params), "month": m, "wind": w, "sun_h": round(sun, 1),
                   "exposure": None, "facing": [], "sheltered": None}
            if w["dir"]:
                facings = [(math.degrees(math.atan2(n[0], n[1])) - s["north_deg"]) % 360.0 for _a, _b, n, _f in sides]
                kinds = [exposure(f, w["dir"]) for f in facings]
                row["facing"] = facings
                row["sheltered"] = sheltered(doc, e, w["dir"], s["north_deg"], tri)
                if row["sheltered"]:
                    row["exposure"] = "προστατευμένο από το κτίριο"
                elif "εκτεθειμένη" in kinds:
                    row["exposure"] = "εκτεθειμένο"
                elif "πλάγια" in kinds:
                    row["exposure"] = "πλάγια στον άνεμο"
                else:
                    row["exposure"] = "υπήνεμο"
            rows.append(row)
    return {"climate": cl, "site": s, "rows": rows}


def facade_note(doc, outward, north_deg=None):
    """«Χειμώνας: άνεμος Β 2,4 Bf (3,9 m/s) — η όψη είναι εκτεθειμένη· η ΤΟΤΕΕ υπολογίζει το Rse με 4 m/s» or ''."""
    from archforge.site.solar_study import site
    cl = climate(doc)
    north = site(doc)["north_deg"] if north_deg is None else north_deg
    facing = (math.degrees(math.atan2(outward[0], outward[1])) - north) % 360.0
    parts = []
    for label, months in (("Χειμώνας", WINTER), ("Καλοκαίρι", SUMMER)):
        w = cl["months"][months[0]]
        if not w["dir"]:
            continue
        text = f"{label}: άνεμος από {w['dir']}"
        if w["bf"] is not None:
            text += f" {w['bf']:g} Bf".replace(".", ",")
        if w["ms"] is not None:
            text += f" ({w['ms']:g} m/s)".replace(".", ",")
        parts.append(text + f" — η όψη είναι {exposure(facing, w['dir'])}")
    if not parts:
        return ""
    w = cl["months"][1]
    if w["ms"] is not None:
        parts.append(f"η ΤΟΤΕΕ 20701-2 υπολογίζει το Rse με άνεμο {RSE_WIND:g} m/s (Ιανουάριος σταθμού: "
                     + f"{w['ms']:g} m/s)".replace(".", ","))
    return " · ".join(parts)
