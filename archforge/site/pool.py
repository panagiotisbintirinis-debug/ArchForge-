"""Swimming pool (owner 17/10, scenario 9 of STRESS_SUITE_10): basin, equipment room, pipes, safety zones, quantities.

A ``pool`` entity is the basin: centre ``x, y`` at the rim level ``z``, ``length`` × ``width`` (inside), turned by
``rotation``; the floor slopes from ``depth_shallow`` (start of the length) to ``depth_deep``.  ``pool_type``:

* ``skimmer``: water ~10 cm under a coping stone; skimmers in the wall take the surface water;
* ``overflow`` (υπερχειλιστική): water at the rim, spilling into a perimeter channel with a grating, collected in a
  balance tank whose volume is declared (``balance_tank_m3``) — never assumed.

Any other shape — an L with a round spa, as the owner's OLD VILLA pool — is the ``outline``: the inside edge as
local (u, v) points, drawn and measured as it is (area, perimeter, walls, coping, the hole in the ground); length and
width are then its extents, and changing them stretches the shape.  Without an outline the basin is the rectangle.

Its equipment room (μηχανοστάσιο / αντλιοστάσιο) is at ``plant_x, plant_y`` (``plant_w`` × ``plant_d``).  Suction and
delivery run there in PVC-U PN10 (SDR 21, EN ISO 1452-2: wall = Ø/21).

What is CHECKED (physics, no rule of thumb):
* water velocity v = Q / A in suction and delivery for the declared pump flow ``pump_flow_m3h``, against the limit of
  the owner's specification (1.5 m/s); the smallest Ø that satisfies it is proposed;
* electrical safety zones of HD 60364-7-702 as the owner's specification states them: zone 0 the basin, zone 1 up
  to 2.0 m from its rim (and 2.5 m high), zone 2 a further 1.5 m — no socket / switch / non-SELV point in zones
  0–1, the SELV transformer of the underwater lights out of zone 1 (it sits in the equipment room).

What is DECLARED by the owner on the pool (counted, priced, never sized here): skimmers, inlets, bottom drains,
underwater lights, pump flow, heat pump kW, salt electrolysis.  Quantities: water volume, excavation (no working
space or slopes — the contractor's), concrete C25/30 with integral waterproofing, waterproofing and mosaic areas,
coping or overflow channel + grating, pipes, equipment, a separate 30 mA RCD for the equipment room.
"""
from __future__ import annotations

import math

POOL_TYPES = {"skimmer": "Με skimmer (στέψη)", "overflow": "Υπερχειλιστική (κανάλι υπερχείλισης)"}
DEFAULTS = {"length": 8.0, "width": 4.0, "depth_shallow": 1.10, "depth_deep": 1.80, "rotation": 0.0,
            "pool_type": "skimmer", "wall": 0.25, "floor": 0.25, "coping": 0.30,
            "plant_w": 2.50, "plant_d": 3.00, "suction_dn": 63, "delivery_dn": 50, "pump_flow_m3h": 0.0,
            "skimmers": 2, "inlets": 4, "main_drains": 1, "lights": 0, "balance_tank_m3": 0.0,
            "heat_pump_kw": 0.0, "electrolysis": 0}
V_MAX = 1.5                    # m/s — owner's specification (scenario 9), suction and delivery
ZONE1, ZONE2 = 2.0, 1.5        # m — HD 60364-7-702 zones as the owner's specification states them
SDR = 21                       # PVC-U PN10 (EN ISO 1452-2)
PVC_SIZES = (50, 63, 75, 90, 110, 125, 140, 160)
CHANNEL_W = 0.20               # overflow channel width beside the rim (drawing/quantities)
BLINDING = 0.10                # lean concrete under the floor slab (m)
WATER_DROP = {"skimmer": 0.10, "overflow": 0.0}
PROVENANCE = ("Πισίνα: γεωμετρία και ποσότητες από το σχέδιο· ταχύτητα v=Q/A σε PVC-U PN10 (EN ISO 1452-2, SDR 21) με "
              "όριο 1,5 m/s της προδιαγραφής του ιδιοκτήτη· ζώνες κατά HD 60364-7-702 όπως τις δίνει η προδιαγραφή — "
              "αντλία, φίλτρο, χημεία, στατική λεκάνης και ηλεκτρολογική μελέτη: μηχανικοί (ENGINEER_REVIEW)")


def param(p, key):
    value = p.get(key, DEFAULTS[key])
    return type(DEFAULTS[key])(value) if not isinstance(DEFAULTS[key], str) else str(value)


def _frame(p):
    r = math.radians(param(p, "rotation"))
    return float(p["x"]), float(p["y"]), math.cos(r), math.sin(r)


def to_world(p, u, v):
    """Local (u along the length from the centre, v across) → plan."""
    x, y, c, s = _frame(p)
    return (x + u * c - v * s, y + u * s + v * c)


def to_local(p, x, y):
    cx, cy, c, s = _frame(p)
    dx, dy = x - cx, y - cy
    return (dx * c + dy * s, -dx * s + dy * c)


def _signed(poly):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1])) / 2


def outline(p, grow=0.0):
    """Local (u, v) inside edge of the basin, counter-clockwise, grown by ``grow`` (m) on every side: the drawn
    shape (``outline``, stretched to ``length`` × ``width``) or the rectangle."""
    raw = p.get("outline") or ()
    L, W = param(p, "length"), param(p, "width")
    if len(raw) >= 3:
        pts = [(float(u), float(v)) for u, v in raw]
        u0, u1 = min(q[0] for q in pts), max(q[0] for q in pts)
        v0, v1 = min(q[1] for q in pts), max(q[1] for q in pts)
        ku = L / (u1 - u0) if u1 - u0 > 1e-9 else 1.0
        kv = W / (v1 - v0) if v1 - v0 > 1e-9 else 1.0
        cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
        pts = [((u - cu) * ku, (v - cv) * kv) for u, v in pts]
        if _signed(pts) < 0:
            pts.reverse()
    else:
        pts = [(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)]
    if grow:
        from archforge.geometry.regions import offset_loop
        pts = offset_loop(pts, [grow] * len(pts))             # counter-clockwise: the outside is to the right
    return pts


def fillet(points, radius, tolerance=0.02):
    """Plan corners rounded with ``radius`` (each limited to what its two edges allow), arcs as short chords within
    ``tolerance`` — a spa's round end is two 90° corners rounded by half its width."""
    pts = [tuple(map(float, q)) for q in points]
    n = len(pts)
    if radius <= 0 or n < 3:
        return pts
    out = []
    for i in range(n):
        a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
        u = (a[0] - b[0], a[1] - b[1]); v = (c[0] - b[0], c[1] - b[1])
        lu, lv = math.hypot(*u), math.hypot(*v)
        if lu < 1e-9 or lv < 1e-9:
            continue
        u = (u[0] / lu, u[1] / lu); v = (v[0] / lv, v[1] / lv)
        cos = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
        half = math.acos(cos) / 2
        if half < 1e-3 or abs(half - math.pi / 2) < 1e-3:
            out.append(b); continue                       # straight on: nothing to round
        r = min(radius, lu / 2 * math.tan(half), lv / 2 * math.tan(half))
        t = r / math.tan(half)                            # from the corner to where the arc touches each edge
        p1 = (b[0] + u[0] * t, b[1] + u[1] * t); p2 = (b[0] + v[0] * t, b[1] + v[1] * t)
        bis = (u[0] + v[0], u[1] + v[1]); lb = math.hypot(*bis)
        centre = (b[0] + bis[0] / lb * r / math.sin(half), b[1] + bis[1] / lb * r / math.sin(half))
        a1 = math.atan2(p1[1] - centre[1], p1[0] - centre[0]); a2 = math.atan2(p2[1] - centre[1], p2[0] - centre[0])
        sweep = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
        step = 2 * math.acos(max(-1.0, min(1.0, 1 - tolerance / r))) if r > tolerance else abs(sweep)
        k = max(1, int(math.ceil(abs(sweep) / max(step, 1e-3))))
        out += [(centre[0] + r * math.cos(a1 + sweep * j / k), centre[1] + r * math.sin(a1 + sweep * j / k)) for j in range(k + 1)]
    return out


def with_outline(p, plan_points, radius=0.0):
    """The pool's params changed to the shape drawn at ``plan_points`` (plan, any order of turn), corners rounded
    by ``radius``: centre and length/width become the shape's extents in the pool's own direction; the equipment
    room keeps its place.  The same for a person drawing the outline and for a drawing set's water (one path)."""
    pts = fillet(plan_points, radius)
    if len(pts) < 3 or abs(_signed(pts)) < 0.5:
        raise ValueError("Η πισίνα θέλει περίγραμμα τουλάχιστον 3 κορυφών και 0,5 m²")
    local = [to_local(p, x, y) for x, y in pts]
    u0, u1 = min(q[0] for q in local), max(q[0] for q in local)
    v0, v1 = min(q[1] for q in local), max(q[1] for q in local)
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    cx, cy = to_world(p, cu, cv)
    shape = [[round(u - cu, 4), round(v - cv, 4)] for u, v in local]
    if _signed(shape) < 0:
        shape.reverse()
    return {"x": cx, "y": cy, "length": round(u1 - u0, 4), "width": round(v1 - v0, 4), "outline": shape}


def rim(p, grow=0.0):
    """Plan outline of the basin's inside edge, grown by ``grow`` (m) on every side."""
    return [to_world(p, u, v) for u, v in outline(p, grow)]


def area(p, grow=0.0):
    return abs(_signed(outline(p, grow)))


def perimeter(p, grow=0.0):
    pts = outline(p, grow)
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:] + pts[:1]))


def _nearest_on(pts, u, v):
    best = None
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((u - ax) * dx + (v - ay) * dy) / L2))
        q = (ax + dx * t, ay + dy * t)
        d = math.dist(q, (u, v))
        if best is None or d < best[0]:
            best = (d, q)
    return best


def depth_at(p, u):
    """Water depth at local ``u`` (shallow end at -length/2)."""
    L = param(p, "length")
    t = min(1.0, max(0.0, (u + L / 2) / L))
    return param(p, "depth_shallow") + (param(p, "depth_deep") - param(p, "depth_shallow")) * t


def distance_to_rim(p, x, y):
    """Plan distance from (x, y) to the basin (0 inside)."""
    from archforge.geometry.regions import point_in_polygon
    u, v = to_local(p, x, y)
    pts = outline(p)
    return 0.0 if point_in_polygon(u, v, pts) else _nearest_on(pts, u, v)[0]


def zone_of(p, x, y):
    d = distance_to_rim(p, x, y)
    return 0 if d <= 0.0 else (1 if d <= ZONE1 else (2 if d <= ZONE1 + ZONE2 else None))


def inner_diameter(dn):
    return dn - 2 * round(dn / SDR, 1)


def velocity(flow_m3h, dn):
    d = inner_diameter(dn) / 1000.0
    return flow_m3h / 3600.0 / (math.pi * d * d / 4)


def smallest_ok(flow_m3h):
    return next((dn for dn in PVC_SIZES if velocity(flow_m3h, dn) <= V_MAX), None)


def plant_rect(p):
    px, py = float(p.get("plant_x", p["x"])), float(p.get("plant_y", p["y"]))
    w, d = param(p, "plant_w") / 2, param(p, "plant_d") / 2
    return [(px - w, py - d), (px + w, py - d), (px + w, py + d), (px - w, py + d)]


def pipe_route(p):
    """Plan route of the suction / delivery pair: from the rim point nearest the equipment room, at right angles."""
    px, py = float(p.get("plant_x", p["x"])), float(p.get("plant_y", p["y"]))
    u, v = to_local(p, px, py)
    start = to_world(p, *_nearest_on(outline(p), u, v)[1])
    return [start, (px, start[1]), (px, py)]


def analyse(doc, pool):
    """Everything derived from one pool: geometry, quantities, checks.  Pure — call it as often as needed."""
    p = pool.params
    L, W = param(p, "length"), param(p, "width")
    ds, dd = param(p, "depth_shallow"), param(p, "depth_deep")
    t, tf = param(p, "wall"), param(p, "floor")
    kind = param(p, "pool_type")
    avg = (ds + dd) / 2
    # Any shape: the floor slopes along the length; walls are the perimeter at the mean depth (exact for the
    # rectangle and for a shape whose length is symmetric about the middle).
    A, P = area(p), perimeter(p)
    outer = area(p, t)
    floor_area = A * math.sqrt(1 + ((dd - ds) / L) ** 2)
    walls_area = P * avg
    wet = floor_area + walls_area
    volume = A * avg
    concrete_floor = outer * tf
    concrete_walls = perimeter(p, t / 2) * avg * t
    excavation = outer * (avg + tf + BLINDING)
    perimeter_m = P
    route = pipe_route(p)
    run = sum(math.dist(a, b) for a, b in zip(route, route[1:]))
    # Each pipe: from the equipment room to the basin, down to its fittings, around half the rim to reach them.
    pipe_len = run + avg + perimeter_m / 2
    flow = param(p, "pump_flow_m3h")
    checks, warnings = [], []
    hydraulics = {}
    for name, key in (("Αναρρόφηση", "suction_dn"), ("Κατάθλιψη", "delivery_dn")):
        dn = param(p, key)
        if flow > 0:
            v = velocity(flow, dn)
            ok = v <= V_MAX
            hydraulics[key] = {"dn": dn, "v": round(v, 2), "ok": ok}
            checks.append((f"{name} Φ{dn}: v = {v:.2f} m/s ≤ {V_MAX}", ok,
                           "" if ok else f"ελάχιστο Φ{smallest_ok(flow)} για {flow:.0f} m³/h"))
        else:
            hydraulics[key] = {"dn": dn, "v": None, "ok": None}
    if flow <= 0:
        warnings.append("Πισίνα: δεν δηλώθηκε παροχή αντλίας (m³/h) — ο έλεγχος ταχύτητας στους σωλήνες δεν γίνεται")
    if kind == "overflow" and param(p, "balance_tank_m3") <= 0:
        warnings.append("Υπερχειλιστική: δεν δηλώθηκε όγκος δεξαμενής εξισορρόπησης (m³)")
    # Electrical zones (plan): what stands in zones 0–1, and the SELV transformer's place.
    bad = []
    level = float(p.get("z", 0.0))
    for e in doc.entities.values():
        if e.kind != "electrical_point" or abs(float(e.params.get("z", 0.0)) - level) > 2.5:
            continue
        zone = zone_of(p, float(e.params["x"]), float(e.params["y"]))
        if zone in (0, 1) and not e.params.get("selv"):
            bad.append(f"{e.name or e.params.get('point_type')} (ζώνη {zone})")
    plant_d = min(distance_to_rim(p, x, y) for x, y in plant_rect(p))
    checks.append(("Ζώνες 0–1 (HD 60364-7-702): καμία πρίζα / διακόπτης / μη-SELV συσκευή", not bad, ", ".join(bad)))
    if param(p, "lights"):
        checks.append((f"Τροφοδοτικό SELV φωτιστικών (στο μηχανοστάσιο) έξω από τη ζώνη 1: {plant_d:.2f} m > {ZONE1}",
                       plant_d > ZONE1, "" if plant_d > ZONE1 else "μετακίνησε το μηχανοστάσιο πιο μακριά από το χείλος"))
    rows = [("Εκσκαφή λεκάνης πισίνας (χωρίς χώρο εργασίας/πρανή)", "m³", round(excavation, 2)),
            ("Σκυρόδεμα καθαριότητας", "m³", round(outer * BLINDING, 2)),
            ("Σκυρόδεμα πισίνας C25/30 με στεγανωτικό μάζας — πυθμένας", "m³", round(concrete_floor, 2)),
            ("Σκυρόδεμα πισίνας C25/30 με στεγανωτικό μάζας — τοιχώματα", "m³", round(concrete_walls, 2)),
            ("Στεγάνωση λεκάνης (εποξειδική / επαλειφόμενη)", "m²", round(wet, 2)),
            ("Ψηφίδα / πλακίδιο πισίνας", "m²", round(wet, 2)),
            ("Νερό πλήρωσης", "m³", round(volume, 2))]
    if kind == "overflow":
        rows += [("Κανάλι υπερχείλισης", "m", round(perimeter(p, CHANNEL_W / 2), 2)),
                 ("Σχάρα καναλιού υπερχείλισης", "m", round(perimeter(p, CHANNEL_W / 2), 2))]
        if param(p, "balance_tank_m3") > 0:
            rows.append((f"Δεξαμενή εξισορρόπησης {param(p, 'balance_tank_m3'):.0f} m³", "τεμ.", 1))
    else:
        rows.append(("Στέψη (κοπίνγκ) περιμετρικά", "m", round(perimeter(p, param(p, "coping") / 2), 2)))
    rows += [(f"Σωλήνας PVC-U PN10 κολυμβητηρίου Φ{param(p, 'suction_dn')} (αναρρόφηση)", "m", round(pipe_len, 2)),
             (f"Σωλήνας PVC-U PN10 κολυμβητηρίου Φ{param(p, 'delivery_dn')} (κατάθλιψη)", "m", round(pipe_len, 2))]
    for key, label in (("skimmers", "Skimmer"), ("inlets", "Στόμιο επιστροφής (inlet)"), ("main_drains", "Σιφώνι πυθμένα"),
                       ("lights", "Υποβρύχιο φωτιστικό LED 12V SELV")):
        if param(p, key):
            rows.append((label, "τεμ.", param(p, key)))
    if param(p, "lights"):
        rows.append(("Μετασχηματιστής ασφαλείας SELV 12V (στο μηχανοστάσιο)", "τεμ.", 1))
    rows += [(f"Αντλία ανακυκλοφορίας {flow:.0f} m³/h" if flow else "Αντλία ανακυκλοφορίας (παροχή από μηχανολόγο)", "τεμ.", 1),
             ("Φίλτρο άμμου", "τεμ.", 1),
             (f"Μηχανοστάσιο πισίνας {param(p, 'plant_w'):.2f}×{param(p, 'plant_d'):.2f}", "τεμ.", 1),
             ("Διαφορικός 30 mA Type A — ξεχωριστός για μηχανοστάσιο/πισίνα", "τεμ.", 1)]
    if param(p, "heat_pump_kw"):
        rows.append((f"Αντλία θερμότητας πισίνας {param(p, 'heat_pump_kw'):.0f} kW", "τεμ.", 1))
    if param(p, "electrolysis"):
        rows.append(("Σύστημα ηλεκτρόλυσης άλατος", "τεμ.", 1))
    return {"volume_m3": round(volume, 2), "wet_area_m2": round(wet, 2), "concrete_m3": round(concrete_floor + concrete_walls, 2),
            "excavation_m3": round(excavation, 2), "perimeter_m": round(perimeter_m, 3), "pipe_m": round(pipe_len, 2), "route": route,
            "hydraulics": hydraulics, "checks": checks, "warnings": warnings, "rows": rows, "plant_distance_m": round(plant_d, 2),
            "provenance": PROVENANCE}


def pools(doc):
    return [e for e in doc.entities.values() if e.kind == "pool"]


# ----------------------------------------------------------------------------------------------- 3D
def _quad(verts, tris, a, b, c, d):
    base = len(verts)
    verts += [a, b, c, d]
    tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]


def _flat(verts, tris, poly, z, holes=()):
    """A horizontal face over ``poly`` (minus ``holes``) at height ``z`` (or ``z(x, y)``), facing up."""
    from archforge.geometry.regions import triangulate_with_holes
    pts, tt = triangulate_with_holes(poly, holes)
    base = len(verts)
    verts += [(x, y, z(x, y) if callable(z) else z) for x, y in pts]
    tris += [tuple(base + i for i in t) for t in tt]


def coping_mesh(p):
    """The ring around the basin (coping stone or overflow grating), selectable: ``(verts, tris)``."""
    z = float(p.get("z", 0.0))
    inner = rim(p)
    outer = rim(p, CHANNEL_W if param(p, "pool_type") == "overflow" else param(p, "coping"))
    verts, tris = [], []
    _flat(verts, tris, outer, z + 0.03, [inner])
    n = len(inner)
    for i in range(n):
        a, b = inner[i], inner[(i + 1) % n]
        _quad(verts, tris, (a[0], a[1], z), (a[0], a[1], z + 0.03), (b[0], b[1], z + 0.03), (b[0], b[1], z))
    return verts, tris


def basin_meshes(p):
    """``{"tile": mesh, "water": mesh, "plant": mesh}`` — the lined inside, the water, the equipment room box."""
    z = float(p.get("z", 0.0))
    local = outline(p)
    bottom = lambda u: z - depth_at(p, u)
    pts = [to_world(p, u, v) for u, v in local]
    tv, tt = [], []
    by_xy = {pt: bottom(uv[0]) for pt, uv in zip(pts, local)}
    _flat(tv, tt, pts, lambda x, y: by_xy.get((x, y), bottom(to_local(p, x, y)[0])))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        a, b = pts[i], pts[j]
        _quad(tv, tt, (a[0], a[1], z), (b[0], b[1], z), (b[0], b[1], bottom(local[j][0])), (a[0], a[1], bottom(local[i][0])))
    # Water at its real level (10 cm under the coping for a skimmer pool): the ground has a hole for the basin
    # (site/terrain.building_exclusions), so it is no longer lifted over the ground plane to be seen.
    zw = z - WATER_DROP.get(param(p, "pool_type"), 0.0)
    wv, wt = [], []
    _flat(wv, wt, pts, zw)
    pr = plant_rect(p)
    pv, pt = [], []
    h = 2.40
    zb = z - 2.60                                     # underground equipment room (owner's scenario 9)
    for i in range(4):
        j = (i + 1) % 4
        _quad(pv, pt, (*pr[i], zb), (*pr[j], zb), (*pr[j], zb + h), (*pr[i], zb + h))
    _quad(pv, pt, (*pr[0], zb + h), (*pr[1], zb + h), (*pr[2], zb + h), (*pr[3], zb + h))
    return {"tile": (tv, tt), "water": (wv, wt), "plant": (pv, pt)}
