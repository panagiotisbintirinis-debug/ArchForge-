"""Drainage (αποχέτευση): fixtures, floor drains, stacks and manhole; pipes derived with their slope.

The fixtures are the plumbing points already in the Document (basin, WC,
shower, bathtub, sink, washing machines).  The user may place floor drains,
stacks and the manhole (``drainage_point``); what is missing is placed
automatically and reported.  Rules (EN 12056-2 system I and common Greek
practice; for review by a mechanical engineer):

* Discharge units DU: basin 0.5, shower 0.6, bathtub / sink / dishwasher /
  washing machine / floor drain 0.8, WC (6 l) 2.0.  Flow Qww = K·√ΣDU with
  K = 0.5 (dwellings).
* Branches: basin Φ40; shower, bathtub, sink, machines, floor drain Φ50; WC
  Φ100 (Greek trade size, DN100).  Collectors: any WC upstream → Φ100; else
  Qww ≤ 0.8 l/s Φ50, ≤ 1.5 l/s Φ75, ≤ 4.0 l/s Φ100, more Φ125.
* In a bathroom, basin, shower, bathtub and washing machine drain into the
  floor drain (σιφώνι δαπέδου); the WC goes straight to the collector.
  Every bathroom gets a floor drain (auto at the shower/bath, else the
  room's centre) unless one is placed.
* Horizontal pipes in the floor zone at 2 % slope towards the outlet: the
  farthest pipe runs just under the floor (2 cm cover) and every metre
  towards the outlet goes 2 cm lower.  The depth needed under the floor is
  reported; the floor build-up takes up to 20 cm, beyond that the extra
  depth is made up with cement screed (τσιμεντοκονία) raising the floor.
* Upper storeys drain into a vertical stack: Φ100 while its flow (foul plus any
  rainwater led into it, 0.03 l/s·m²) stays ≤ 4 l/s, else Φ125 (auto: the wall nearest
  the WCs), carried down to the ground storey and vented 50 cm above the
  roof.  The ground storey (with the stacks' feet) drains to the manhole
  outside (auto: 1 m out of the nearest exterior wall).
* Same orthogonal, wall-avoiding router as the water supply.
"""
from __future__ import annotations

import math

from archforge.mep.plumbing import CELL, _Grid, _grow, _levels, _room_key

PROVENANCE = ("Προμελέτη αποχέτευσης: EN 12056-2 (σύστημα I, μονάδες εκροής, Qww = 0,5·√ΣDU), κλάδοι Φ40/50/100 (λεκάνη Φ100), "
              "κλίση 2 %, στήλη Φ100 έως 4 l/s αλλιώς Φ125 (μαζί τα όμβρια αν πέφτουν μέσα), γέμισμα δαπέδου έως 20 cm, πέραν τσιμεντοκονία, αερισμός, φρεάτιο — προς έλεγχο από μηχανολόγο")
# fixture: DU, branch DN, drains into the floor drain in a bathroom
FIXTURES = {"basin": (0.5, 40, True), "wc": (2.0, 100, False), "shower": (0.6, 50, True), "bathtub": (0.8, 50, True),
            "kitchen_sink": (0.8, 50, False), "dishwasher": (0.8, 50, False), "washing_machine": (0.8, 50, True)}
POINT_TYPES = {"floor_drain": ("Σιφώνι δαπέδου", "Σ"), "stack": ("Κατακόρυφη στήλη αποχέτευσης", "ΣΤ"),
               "manhole": ("Φρεάτιο", "Φ")}
FLOOR_DRAIN_DU, FLOOR_DRAIN_DN = 0.8, 50
SLOPE, COVER, SCREED = 0.02, 0.02, 0.20
STACK_Q100 = 4.0          # l/s, stack DN100 with primary ventilation (EN 12056-2 Table 11)
RAIN_INTENSITY = 0.03     # l/(s·m²) design rainfall on a roof or terrace (≈ 110 mm/h), runoff coefficient 1.0


def stack_flow(du, rain_area=0.0):
    """Flow down a stack (l/s): foul Qww = 0.5·√ΣDU plus rainwater r·A when roof/terrace water falls in it."""
    return K_DWELLING * math.sqrt(max(du, 0.0)) + RAIN_INTENSITY * max(float(rain_area), 0.0)


def stack_dn(du, rain_area=0.0):
    """Vertical stack Φ100 or Φ125 by the volume it carries, rainwater included (owner's rule)."""
    return 100 if stack_flow(du, rain_area) <= STACK_Q100 else 125
K_DWELLING = 0.5


def drainage_points(doc):
    return [e for e in doc.entities.values() if e.kind == "drainage_point"]


def _floor_of(doc, z):
    levels = sorted(set(_levels(doc)) | set(_storeys(doc)))
    below = [lz for lz in levels if lz <= z + 1e-4]
    return below[-1] if below else levels[0]


def _storeys(doc):
    return sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"} or {0.0})


def collector_dn(du, has_wc):
    q = K_DWELLING * math.sqrt(max(du, 0.0))
    if has_wc:
        return 100 if q <= 4.0 else 125
    if q <= 0.8:
        return 50
    if q <= 1.5:
        return 75
    return 100 if q <= 4.0 else 125


def _nearest_wall_point(doc, z, x, y, into=0.15):
    best = None
    for w in doc.entities.values():
        if w.kind != "wall" or abs(float(w.params.get("z", 0.0)) - z) > 0.05:
            continue
        p = w.params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        if L2 < 1e-12:
            continue
        t = max(0.05, min(0.95, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            off = float(p["thickness"]) / 2 + into
            ux, uy = ((x - px) / d, (y - py) / d) if d > 1e-9 else (0.0, 0.0)
            best = (d, (px + ux * off, py + uy * off))
    return best[1] if best else (x, y)


def _auto_manhole(doc, z, x, y):
    from archforge.mep.ventilation import exterior_walls
    best = None
    for w, (nx, ny) in exterior_walls(doc, z):
        p = w.params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L2 = (bx - ax) ** 2 + (by - ay) ** 2
        t = max(0.1, min(0.9, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            best = (d, (px + nx * 1.0, py + ny * 1.0))
    return best[1] if best else (x + 1.5, y)


def route_drainage(doc):
    """``{"pipes": [(a, b, dn, kind)], "nodes": [...], "report": {...}}`` — derived, never stored."""
    from archforge.mep.plumbing import plumbing_points
    storeys = _storeys(doc)
    ground = storeys[0]
    report = {"warnings": [], "auto": [], "length_by_dn": {}, "depth_m": {}, "provenance": PROVENANCE}
    result = {"pipes": [], "nodes": [], "report": report}
    fixtures = [e for e in plumbing_points(doc) if e.params["point_type"] in FIXTURES]
    if not fixtures:
        return result
    placed = drainage_points(doc)
    # Stacks: placed ones, else one per upper storey group of WCs (auto).
    stacks = [(float(e.params["x"]), float(e.params["y"]), e.id) for e in placed if e.params["point_type"] == "stack"]
    rain = {e.id: float(e.params.get("rain_area", 0.0) or 0.0) for e in placed if e.params["point_type"] == "stack"}
    by_storey = {}
    for e in fixtures:
        by_storey.setdefault(_floor_of(doc, float(e.params["z"])), []).append(e)
    upper = [z for z in by_storey if z > ground + 1e-6]
    if upper and not stacks:
        wet = [e for z in upper for e in by_storey[z]]
        wcs = [e for e in wet if e.params["point_type"] == "wc"] or wet
        cx = sum(float(e.params["x"]) for e in wcs) / len(wcs)
        cy = sum(float(e.params["y"]) for e in wcs) / len(wcs)
        z0 = min(upper)
        sx, sy = _nearest_wall_point(doc, z0, cx, cy)
        stacks = [(sx, sy, None)]
        report["auto"].append(f"Στήλη αποχέτευσης (αυτόματα) στον τοίχο κοντά στα WC: ({sx:.2f}, {sy:.2f})")
    manholes = [(float(e.params["x"]), float(e.params["y"]), e.id) for e in placed if e.params["point_type"] == "manhole"]
    top_z = max(_levels(doc) + [storeys[-1]])
    stack_du = {i: (0.0, False) for i in range(len(stacks))}
    stack_floors = {i: 0 for i in range(len(stacks))}
    floor_drains = [e for e in placed if e.params["point_type"] == "floor_drain"]
    for z in sorted(by_storey, reverse=True) + ([ground] if ground not in by_storey and upper else []):
        members = by_storey.get(z, [])
        is_ground = abs(z - ground) < 1e-6
        if is_ground:
            if manholes:
                rx, ry = manholes[0][0], manholes[0][1]
            else:
                ax_ = [float(e.params["x"]) for e in members] + [s[0] for s in stacks]
                ay_ = [float(e.params["y"]) for e in members] + [s[1] for s in stacks]
                rx, ry = _auto_manhole(doc, z, sum(ax_) / len(ax_), sum(ay_) / len(ay_))
                report["auto"].append(f"Φρεάτιο (αυτόματα) 1 m έξω από τον πλησιέστερο εξωτερικό τοίχο: ({rx:.2f}, {ry:.2f})")
            result["nodes"].append({"kind": "manhole", "x": rx, "y": ry, "z": z, "auto": not manholes})
        else:
            # The nearest stack serves this storey.
            k = min(range(len(stacks)), key=lambda i: math.hypot(stacks[i][0] - members[0].params["x"], stacks[i][1] - members[0].params["y"]))
            rx, ry = stacks[k][0], stacks[k][1]
        # Targets: WCs and non-bathroom fixtures directly; bathroom fixtures via the room's floor drain.
        targets = {}            # id -> (x, y, du, has_wc, branch_dn, label)
        branches = []           # (fixture xy, drain xy, dn)
        rooms = {}
        for e in members:
            t = e.params["point_type"]
            du, dn, via_drain = FIXTURES[t]
            room = _room_key(doc, float(e.params["x"]), float(e.params["y"]), z)
            if via_drain and room is not None:
                rooms.setdefault(room, []).append(e)
            else:
                targets[e.id] = (float(e.params["x"]), float(e.params["y"]), du, t == "wc", dn)
        for room, fx in rooms.items():
            if len(fx) == 1 and fx[0].params["point_type"] in ("washing_machine", "basin") and \
                    not any(o.params["point_type"] in ("shower", "bathtub", "wc") for o in members
                            if _room_key(doc, float(o.params["x"]), float(o.params["y"]), z) == room):
                e = fx[0]                                    # e.g. a laundry machine on its own: direct branch
                du, dn, _v = FIXTURES[e.params["point_type"]]
                targets[e.id] = (float(e.params["x"]), float(e.params["y"]), du, False, dn)
                continue
            drain = next((d for d in floor_drains if abs(_floor_of(doc, float(d.params["z"])) - z) < 1e-6 and
                          _room_key(doc, float(d.params["x"]), float(d.params["y"]), z) == room), None)
            if drain is not None:
                dx, dy, did = float(drain.params["x"]), float(drain.params["y"]), drain.id
            else:
                anchor = next((o for o in fx if o.params["point_type"] in ("shower", "bathtub")), None)
                if anchor is not None:
                    dx, dy = float(anchor.params["x"]) + 0.3, float(anchor.params["y"])
                else:
                    dx = sum(float(o.params["x"]) for o in fx) / len(fx)
                    dy = sum(float(o.params["y"]) for o in fx) / len(fx)
                did = f"auto-drain:{room}"
                report["auto"].append(f"Σιφώνι δαπέδου (αυτόματα) στο {room}")
            du = FLOOR_DRAIN_DU + sum(FIXTURES[o.params["point_type"]][0] for o in fx)
            targets[did] = (dx, dy, du, False, collector_dn(du, False))
            result["nodes"].append({"kind": "floor_drain", "x": dx, "y": dy, "z": z, "auto": drain is None, "room": str(room)})
            for o in fx:
                branches.append(((float(o.params["x"]), float(o.params["y"])), (dx, dy), FIXTURES[o.params["point_type"]][1]))
        # Stack feet arriving on the ground storey.
        if is_ground:
            for i, (sx, sy, _sid) in enumerate(stacks):
                du, wc = stack_du[i]
                if du > 0:
                    targets[f"stack:{i}"] = (sx, sy, du, wc, stack_dn(du, rain.get(stacks[i][2], 0.0)))
        if not targets:
            continue
        pts = [(v[0], v[1]) for v in targets.values()] + [(rx, ry)]
        grid = _Grid(doc, z, pts)
        root = grid.cell(rx, ry)
        cell_of = {tid: grid.cell(v[0], v[1]) for tid, v in targets.items()}
        paths, _loads, parent = _grow(grid, root, cell_of)
        # Per edge: discharge units and whether a WC is upstream.
        edge_du, edge_wc = {}, {}
        for tid, path in paths.items():
            du, wc = targets[tid][2], targets[tid][3]
            c = path[0]
            while parent.get(c) is not None:
                key = (c, parent[c])
                edge_du[key] = edge_du.get(key, 0.0) + du
                edge_wc[key] = edge_wc.get(key, False) or wc
                c = parent[c]
        # Distance of every node to the outlet (along the tree) for the slope.
        def dist(c):
            n = 0
            while parent.get(c) is not None:
                c = parent[c]
                n += 1
            return n * CELL
        far = max([dist(c) for c in cell_of.values()] + [0.0])
        dn_max = max([collector_dn(edge_du[k], edge_wc[k]) for k in edge_du] + [50])
        z_root = z - COVER - dn_max / 1000 - SLOPE * far

        def invert(c):
            return z_root + SLOPE * dist(c)
        for (c, p), du in edge_du.items():
            dn = collector_dn(du, edge_wc[(c, p)])
            a, b = grid.point(c), grid.point(p)
            result["pipes"].append(((a[0], a[1], invert(c)), (b[0], b[1], invert(p)), dn, "collector"))
        for (fx_, dr, dn) in branches:
            dz = invert(grid.cell(*dr))
            L = math.dist(fx_, dr)
            result["pipes"].append(((fx_[0], fx_[1], dz + SLOPE * L), (dr[0], dr[1], dz), dn, "branch"))
        depth = z - z_root
        report["depth_m"][round(z, 2)] = round(depth, 3)
        if depth > SCREED + 1e-6 and not is_ground:
            extra = math.ceil((depth - SCREED) * 100)
            report.setdefault("screed_m", {})[round(z, 2)] = extra / 100
            report["warnings"].append(
                f"Όροφος +{z:.2f}: η αποχέτευση θέλει βάθος {depth * 100:.0f} cm κάτω από το δάπεδο — το γέμισμα παίρνει έως "
                f"{SCREED * 100:.0f} cm, τα υπόλοιπα {extra} cm με τσιμεντοκονία (ανύψωση δαπέδου) ή υποβιβασμό πλάκας")
        # This storey's flow goes down its stack.
        if not is_ground:
            total = sum(v[2] for v in targets.values())
            wc = any(v[3] for v in targets.values())
            prev = stack_du[k]
            stack_du[k] = (prev[0] + total, prev[1] or wc)
            stack_floors[k] += 1
    # Stacks: vertical from the highest storey that uses them down to the ground collector, vented over the roof.
    for i, (sx, sy, sid) in enumerate(stacks):
        if stack_du[i][0] <= 0:
            continue
        roof = top_z + 0.5 if top_z > ground else ground + 3.5
        area = rain.get(sid, 0.0)
        dn = stack_dn(stack_du[i][0], area)
        if area > 0:
            report["warnings"].append(
                f"Στήλη ({sx:.2f}, {sy:.2f}): δέχεται και όμβρια {area:.0f} m² — μικτή στήλη Φ{dn} "
                f"({stack_flow(stack_du[i][0], area):.2f} l/s), να επιβεβαιωθεί από μηχανολόγο")
        result["pipes"].append(((sx, sy, ground - 0.3), (sx, sy, roof), dn, "stack"))
        result["nodes"].append({"kind": "stack", "x": sx, "y": sy, "z": ground, "auto": sid is None, "dn": dn,
                                "floors": stack_floors[i], "flow_ls": round(stack_flow(stack_du[i][0], area), 2),
                                "rain_area": area})
    for a, b, dn, kind in result["pipes"]:
        report["length_by_dn"][dn] = round(report["length_by_dn"].get(dn, 0.0) + math.dist(a, b), 2)
    return result


_CACHE = {"key": None, "value": None}


def route_drainage_cached(doc):
    items = []
    for e in doc.entities.values():
        if e.kind in ("plumbing_point", "drainage_point", "wall"):
            items.append((e.kind, e.id, tuple(sorted((k, str(v)) for k, v in e.params.items()))))
    key = (tuple(sorted(items)), tuple(sorted((str(k), float(v)) for k, v in doc.levels.items())),
           tuple(sorted((k, str(v)) for k, v in getattr(doc, "room_data", {}).items())))
    if _CACHE["key"] != key:
        _CACHE["key"], _CACHE["value"] = key, route_drainage(doc)
    return _CACHE["value"]


def point_marker_mesh(params):
    """Floor drain grate, stack collar or manhole box (selectable in 3D)."""
    from archforge.mep.plumbing import pipe_mesh
    x, y, z = (float(params[k]) for k in ("x", "y", "z"))
    kind = params["point_type"]
    if kind == "manhole":
        return pipe_mesh((x, y, z - 0.6), (x, y, z), 600, sides=4)
    if kind == "stack":
        return pipe_mesh((x, y, z), (x, y, z + 0.3), 160, sides=12)
    return pipe_mesh((x, y, z - 0.02), (x, y, z + 0.005), 150, sides=8)
