"""Πλάτωμα (terrace) in one click: the closed area around a point becomes a level piece of ground.

Owner 22/10: the masterplan is terraces at written levels («+137.10m [F.L.]» parking, «+134.90» garden …) held by
retaining walls; drawing each outline by hand is what made the site «not easy».  A person clicks inside the area
the walls (retaining walls, building walls) close; the outline is that area up to the walls' faces, and the level
is the one the drawing writes inside it (or typed).  The importer of a drawing set uses the same functions, so a
plateau made by hand and one read off the drawing are the same terrain region.

Plain data, no Qt.  The region is an ordinary terrain region (site/elevation_regions.py): neighbouring plateaus at
different levels are a wall's thickness apart — that gap is where the ground steps, behind the wall.
"""
from __future__ import annotations

from archforge.geometry.regions import point_in_polygon, signed_area

TRANSITION = 0.5        # m — the ground leaves a plateau held by walls in half a metre (the step is behind the wall)
MAX_AREA = 2500.0       # m² — larger than a site's terrace: the click was outside every closed area


def area_at(doc, x, y):
    """The closed area around (x, y), up to the faces of the walls that close it: ``(polygon, storey z)`` — the
    smallest one, of any storey or of all walls together in plan (``z`` None): a terrace of the OLD VILLA is held
    by retaining walls drawn on its upper floor plan on one side and on the masterplan on the other — the ground
    sees them all at once, whatever storey they were drawn on.  None if nothing closes it."""
    from archforge.quantities.takeoff import net_polygon
    best = None
    zs = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall" and e.visible})
    for z in zs:
        for face in doc.active_room_faces(z=z):
            if not point_in_polygon(x, y, face.polygon):
                continue
            a = abs(signed_area(face.polygon))
            if a > MAX_AREA or (best is not None and a >= best[0]):
                continue
            net = net_polygon(doc, face.polygon, z)
            if len(net) >= 3 and abs(signed_area(net)) > 0.04:
                best = (a, [list(p) for p in net], z)
    if len(zs) > 1:
        plan = _plan_doc(doc)
        for face in plan.active_room_faces(z=0.0):
            if not point_in_polygon(x, y, face.polygon):
                continue
            a = abs(signed_area(face.polygon))
            if a > MAX_AREA or (best is not None and a >= best[0]):
                continue
            net = net_polygon(plan, face.polygon, 0.0)
            if len(net) >= 3 and abs(signed_area(net)) > 0.04:
                best = (a, [list(p) for p in net], None)
    return None if best is None else (best[1], best[2])


_PLAN = {}


def _plan_doc(doc):
    """All visible walls of ``doc`` on one level (a scratch document, cached while the walls stay the same)."""
    from archforge.core.model import Document, Entity
    walls = [e for e in doc.entities.values() if e.kind == "wall" and e.visible]
    key = tuple(sorted((e.id, tuple(round(float(e.params[k]), 5) for k in ("x1", "y1", "x2", "y2", "thickness")))
                       for e in walls))
    hit = _PLAN.get(id(doc))
    if hit is not None and hit[0] == key:
        return hit[1]
    plan = Document()
    for e in walls:
        p = dict(e.params, z=0.0, height=1.0)
        plan.add(Entity("wall", {k: p[k] for k in ("x1", "y1", "x2", "y2", "z", "height", "thickness")}))
    _PLAN.clear()
    _PLAN[id(doc)] = (key, plan)
    return plan


def written_level(doc, polygon, altitude_ref=0.0):
    """The finished-floor level the underlays write inside ``polygon`` (most written; relative to ±0,00 =
    ``altitude_ref``), or None.  Spot levels of ceilings ([C.L.]) do not count."""
    from collections import Counter
    from archforge.project.drawing_text import model_labels
    from archforge.project.underlay import underlays
    found = Counter()
    for u in underlays(doc):
        if u.params.get("source") != "pdf" or not u.visible:
            continue
        try:
            labels = model_labels(u.params)["levels"]
        except Exception:
            continue
        for lv in labels:
            if not lv.ceiling and lv.value >= 10.0 and point_in_polygon(lv.x, lv.y, polygon):
                found[round(lv.value, 2)] += 1
    if not found:
        return None
    value, _n = max(found.items(), key=lambda kv: (kv[1], kv[0]))
    return round(value - float(altitude_ref), 3)


def region(polygon, elevation, rid):
    return {"id": rid, "shape": "polygon", "points": [list(map(float, p)) for p in polygon],
            "elevation": float(elevation), "transition": TRANSITION}


def with_plateau(terrain_params, new, replace_same_place=True):
    """Terrain params with the region ``new`` added — a region of another level that it covers goes (the click
    is the newer word about that ground).  Raises ValueError when it cannot fit (validate_regions says why)."""
    import copy
    from archforge.site.elevation_regions import distance_to_region, validate_regions
    p = copy.deepcopy(terrain_params)
    kept = []
    for r in p.get("regions") or ():
        # Covered: most of its corners inside the new one or on its outline (the same area clicked again).
        inside = sum(distance_to_region(x, y, new["points"]) < 1e-6 for x, y in r["points"]) >= len(r["points"]) / 2
        if replace_same_place and inside:
            continue
        kept.append(r)
    p["regions"] = validate_regions(kept + [new])
    xs = [q[0] for q in new["points"]]; ys = [q[1] for q in new["points"]]
    p.update(x0=min(float(p["x0"]), min(xs)), y0=min(float(p["y0"]), min(ys)),
             x1=max(float(p["x1"]), max(xs)), y1=max(float(p["y1"]), max(ys)))
    return p


def written_level_near(doc, x, y, altitude_ref=0.0, reach=1.5):
    """The finished level the underlays write nearest (x, y) within ``reach`` m (relative to ±0,00), or None."""
    import math
    from archforge.project.drawing_text import model_labels
    from archforge.project.underlay import underlays
    best = None
    for u in underlays(doc):
        if u.params.get("source") != "pdf" or not u.visible:
            continue
        try:
            labels = model_labels(u.params)["levels"]
        except Exception:
            continue
        for lv in labels:
            d = math.dist((lv.x, lv.y), (x, y))
            if not lv.ceiling and lv.value >= 10.0 and d <= reach and (best is None or d < best[0]):
                best = (d, lv.value)
    return None if best is None else round(best[1] - float(altitude_ref), 3)
