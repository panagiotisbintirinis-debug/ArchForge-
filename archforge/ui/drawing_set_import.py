"""Αρχείο ▸ Εισαγωγή ▸ «Σύνολο σχεδίων (πολλά PDF)…» (owner 22/10: «πάνω από δύο PDF σε σειρά … να συγχωνευτούν
παραμετρικά για να δώσουν το αποτέλεσμα»).

The sheets are read and related (project/drawing_set.py); after one confirmation (what was found, which altitude
is ±0,00) the project is made in one undoable step:

* every placed sheet becomes an underlay where it belongs (plans on their storey, the site plan at ±0,00);
* storeys per building from the floor levels written (OLD VILLA: ±0,00 = +131,80, lower floor −2,80 → +129,00);
* each plan is built on its storey (walls, doors / windows, room names, floor — ui/building_from_underlay.py);
* the ground from the site plan's altitudes (sloped plots: the building sits in the slope, as the section shows).
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox, QProgressDialog

FLOOR_NAMES = {"basement": "Υπόγειο", "lower": "Κάτω όροφος", "ground": "Ισόγειο", "upper": "Πάνω όροφος", "roof": "Δώμα"}
KIND_NAMES = {"plan": "κάτοψη", "section": "τομή", "site": "γενική διάταξη", "elevation": "όψη"}


def read(window, paths):
    """Sheets of ``paths`` (progress shown; Esc stops) — None when stopped."""
    from archforge.project.drawing_set import read_sheet
    progress = QProgressDialog("Ανάγνωση σχεδίων…", "Διακοπή", 0, len(paths), window)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    sheets = []
    for i, path in enumerate(paths):
        progress.setValue(i)
        progress.setLabelText(f"Ανάγνωση {i + 1}/{len(paths)}: {path.split('/')[-1]}")
        QApplication.processEvents()
        if progress.wasCanceled():
            return None
        sheets.append(read_sheet(path))
    progress.setValue(len(paths))
    return sheets


def plan_storeys(sheets, placed, reference):
    """``{sheet index: (storey name, z)}`` for the placed plans; z = floor altitude − ``reference``."""
    from archforge.project.drawing_set import floor_altitude
    out = {}
    zeros = building_zeros(sheets, placed)
    for i, s in enumerate(sheets):
        if i not in placed or s.kind != "plan":
            continue
        zero = zeros.get(s.building)
        alt = floor_altitude(s, zero)
        if alt is None:
            continue
        name = f"{s.building.title() or 'Κτίριο'} — {FLOOR_NAMES.get(s.floor, 'στάθμη')} {alt:+.2f}".replace(".", ",")
        out[i] = (name, round(alt - reference, 3), alt)
    # Two sheets of one building at one altitude (the plan and the pool-room plan) share the storey.
    first = {}
    for i, (name, z, alt) in sorted(out.items(), key=lambda kv: FLOOR_NAMES.get(sheets[kv[0]].floor) is None):
        key = (sheets[i].building, alt)
        first.setdefault(key, name)
        out[i] = (first[key], z, alt)
    return out


def building_zeros(sheets, placed):
    """``{building: altitude of its ±0,00}`` — written on its sheets, else read off the site plan."""
    from archforge.project.drawing_set import building_zero, zero_from_site
    sites = [j for j in placed if sheets[j].kind == "site"]
    out = {}
    for i, s in enumerate(sheets):
        if i not in placed or s.kind != "plan" or out.get(s.building) is not None:
            continue
        zero = building_zero([t for t in sheets if t.building == s.building])
        if zero is None:
            zero = next((z for j in sites for z in [zero_from_site(sheets[j], placed[j][0], s, placed[i][0])]
                         if z is not None), None)
        out[s.building] = zero
    return out


def default_reference(sheets, storeys):
    """±0,00: the ground floor's altitude (the first ground floor plan), else the lowest plan."""
    ground = [alt for i, (_n, _z, alt) in storeys.items() if sheets[i].floor == "ground"]
    alts = [alt for _n, _z, alt in storeys.values()]
    return ground[0] if ground else (min(alts) if alts else 0.0)


def add_pools(window, sheets, placed, reference):
    """Every pool of the set (water drawn on the sheets, project/drawing_set.pools) at its written altitude."""
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.project.drawing_set import pool_level, pools
    from archforge.site.pool import DEFAULTS, ZONE1
    import math
    made = []
    zeros = building_zeros(sheets, placed)
    for k, (cx, cy, length, width, rot, idx, shape) in enumerate(pools(sheets, placed), 1):
        p = {**DEFAULTS, "x": cx, "y": cy, "z": 0.0, "length": round(length, 3), "width": round(width, 3), "rotation": rot}
        if shape:
            # The L with its spa, as drawn — through the same function as Πισίνα ▸ «Σχεδίασε το σχήμα».
            from archforge.site.pool import to_world, with_outline
            p.update(with_outline(p, [to_world(p, u, v) for u, v in shape]))
        depth = pool_depth(sheets, placed, idx, (cx, cy), max(length, width))
        if depth:
            p.update(depth_shallow=depth, depth_deep=depth)
        # Its rim: from the levels written inside it (OLD VILLA: bottom «−1.65 [C.L.]» + «pool's depth 1.50» →
        # −0,15 = +131,65), else the nearest written altitude (NEW VILLA +114,00).
        from archforge.site.pool import rim as pool_rim
        alt = rim_level(sheets, placed, idx, pool_rim(p), zeros, depth)
        if alt is None:
            alt = pool_level(sheets, placed, (cx, cy))
        p["z"] = (alt - reference) if alt is not None else 0.0
        a = math.radians(rot)
        u = length / 2 + ZONE1 + float(p["plant_w"]) / 2 + 0.5            # equipment room beside it, out of zone 1
        p.update(plant_x=cx + u * math.cos(a), plant_y=cy + u * math.sin(a))
        # Where the drawing writes «ENGINE ROOM» next to the pool (the NEW VILLA's pool sheet), the equipment is there.
        from archforge.project import drawing_text as T
        rooms = [(sim.apply((r.x * sheets[i].metres_per_pt, r.y * sheets[i].metres_per_pt)), r.name)
                 for i in idx for sim, _h in (placed[i],) for r in T.rooms(sheets[i].texts)]
        engine = [xy for xy, name in rooms if T.greek_room(name)[0] == "Μηχανοστάσιο" and math.dist(xy, (cx, cy)) <= 12.0]
        if engine:
            ex, ey = min(engine, key=lambda xy: math.dist(xy, (cx, cy)))
            p.update(plant_x=ex, plant_y=ey)
        building = next((sheets[i].building for i in idx if sheets[i].building), "")
        e = Entity("pool", p, name=f"Πισίνα {building.title()}".strip() if building else f"Πισίνα {k}")
        window.stack.execute(AddEntity(e))
        made.append(e)
    return made


def add_sections(window, sheets, placed):
    """Every section sheet on its cut line (the mark written at both ends on its building's plan), as a section
    with the drawing under it, placed and turned to look the way the drawing does (project/section_fit.py).
    ``{sheet index: {"section": id, "underlay": id or None, "fit": dict or None, "report": text}}``."""
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.project import section_fit as F
    from archforge.project.underlay import for_section, pdf_params
    out = {}
    for i, s in enumerate(sheets):
        if s.kind != "section":
            continue
        lines = F.cut_lines(sheets, placed, building=s.building or None)
        if not lines:
            continue
        mark, a, b, _j = lines[0]
        found = F.fit(s, window.doc, (a, b))
        sec = Entity("section_line", {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                                      "flip": found["flip"] if found else 0}, name=f"Τομή {mark}")
        window.stack.execute(AddEntity(sec))
        params = for_section(pdf_params(s.path, s.page, s.scale or 100, s.page_size), sec.id)
        if found:
            params.update(x=found["x"], y=found["y"])
        u = Entity("underlay", params, name=f"Υπόβαθρο {s.path.split('/')[-1]}")
        window.stack.execute(AddEntity(u))
        line, flip = (a, b), (found["flip"] if found else 0)
        ground = [(*F.plan_point(line, flip, gu), gz) for gu, gz in F.ground_profile(s, found)]
        slab = F.roof_slab(s, found, F.model_on_line(window.doc, line, flip)["walls"]) if found else None
        out[i] = {"section": sec.id, "underlay": u.id, "fit": found, "report": F.report(found, sec.name),
                  "line": line, "flip": flip, "profile": F.ground_profile(s, found), "ground": ground,
                  "building": s.building, "slab": slab}
        if slab:
            out[i]["report"] += (f" · πλάκα οροφής από την τομή {slab['bottom']:.2f}–{slab['top']:.2f} "
                                 f"({slab['thickness'] * 100:.0f} cm)" +
                                 (f", ψευδοροφή {slab['ceiling']:.2f}" if slab["ceiling"] else "")).replace(".", ",")
    return out


def add_roof_slabs(window, sheets, storeys, sections, zeros=None, reference=0.0):
    """A roof slab (δώμα) over every storey built from a plan.  Where a section of the building says how high
    and how thick it is (NEW VILLA: underside 3,40, 20 cm), the storey's walls go up to its underside first;
    a storey under its building's ±0,00 (OLD VILLA lower floor +129,00, ±0,00 = +131,80) is closed by the floor
    of the ±0,00 storey: 20 cm whose top is at ±0,00; otherwise the slab sits on the walls as drawn (20 cm).
    ``[(storey name, slab id, where its height came from)]``."""
    from archforge.architecture.storey_slabs import storey_slab_command
    from archforge.core.commands import UpdateEntities
    doc = window.doc
    told = {v["building"]: v["slab"] for v in sections.values() if v.get("slab")}
    out, seen = [], set()
    for i, (name, z, _alt) in sorted(storeys.items(), key=lambda kv: kv[1][1]):
        if (name, z) in seen:
            continue
        seen.add((name, z))
        slab = told.get(sheets[i].building)
        how = "τομή" if slab else "τοίχοι"
        zero = (zeros or {}).get(sheets[i].building)
        if slab is None and zero is not None and zero - reference - z >= 2.2:
            how = "±0,00 του κτιρίου"
            top = round(zero - reference - z, 3)
            slab = {"bottom": round(top - 0.20, 3), "top": top, "thickness": 0.20, "ceiling": None}
        walls = [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 1e-3]
        if not walls:
            continue
        if slab:
            # Only the walls built at the default height are raised: a parapet or a retaining wall keeps its own.
            common = Counter(round(float(e.params["height"]), 3) for e in walls).most_common(1)[0][0]
            # A wall never goes lower than the head of a door / window in it.
            heads = {}
            for o in doc.entities.values():
                if o.parent_id and o.kind in ("door", "window", "opening"):
                    head = float(o.params.get("sill", 0.0)) + float(o.params.get("height", 0.0))
                    heads[o.parent_id] = max(heads.get(o.parent_id, 0.0), head)
            changes = {e.id: {"height": max(slab["bottom"], round(heads.get(e.id, 0.0), 3))} for e in walls
                       if abs(float(e.params["height"]) - common) < 1e-3}
            if changes:
                window.stack.execute(UpdateEntities(changes))
        command, entity = storey_slab_command(doc, "room_roof", z, name, thickness=slab["thickness"] if slab else None)
        if command is not None:
            window.stack.execute(command)
            out.append((name, entity.id if entity else None, how))
    return out


def _inside(polygon, x, y):
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def section_ground(terrain, sections):
    """The ground each section draws, as terrace levels of the terrain (site/terrain.py ``levels``): the drawn
    ground is finished ground — the slope below the house, the bank above it, the soil on its roof."""
    extra = [[x, y, z] for v in sections.values() for x, y, z in v["ground"]]
    if extra:
        terrain["levels"] = list(terrain.get("levels", [])) + extra
    return len(extra)


def green_roofs_from_sections(window, sections, roofs):
    """Υπόσκαφο: a roof slab the section draws soil on (ground over its top) becomes a green roof — the ground
    covers it (site/terrain.green_roofs).  ``[roof slab ids]``."""
    from archforge.architecture.storey_slabs import storey_slab_geometry
    from archforge.core.commands import UpdateEntity
    from archforge.geometry.regions import point_in_polygon
    doc = window.doc
    made = []
    for _name, rid, _how in roofs:
        if not rid or rid not in doc.entities:
            continue
        g = storey_slab_geometry(doc, doc.get(rid))
        if not g:
            continue
        top = float(g["z"]) + float(g["thickness"])
        over = [z for v in sections.values() for x, y, z in v.get("ground", ())
                if any(point_in_polygon(x, y, outer) for outer, _h in g["islands"]) and z > top + 0.05]
        if over:
            window.stack.execute(UpdateEntity(rid, {"green": 1, "soil": 0.10}))
            made.append(rid)
    return made


def rim_level(sheets, placed, idx, outline, zeros, depth=None):
    """Altitude of a pool's rim from the levels its sheets write inside it: the lowest is its bottom — plus the
    written depth it is the rim; without a depth, the highest of two or more is the water.  Relative levels count
    through the building's ±0,00.  None when nothing is written inside."""
    from archforge.geometry.regions import point_in_polygon
    inside = []
    for i in idx:
        s = sheets[i]
        sim = placed[i][0]
        zero = zeros.get(s.building) if s.kind == "plan" else None
        for v, _ceiling, x, y in s.levels():
            alt = v if v >= 10.0 else (zero + v if zero is not None else None)
            if alt is not None and point_in_polygon(*sim.apply((x, y)), outline):
                inside.append(alt)
    if not inside:
        return None
    if depth:
        return round(min(inside) + depth, 3)
    return round(max(inside), 3) if len(set(inside)) > 1 else None


def pool_depth(sheets, placed, idx, centre, reach):
    """The depth the drawing writes on the pool («pool's depth 1.50m»), or None."""
    import math
    import re
    for i in idx:
        sim = placed[i][0]
        k = sheets[i].metres_per_pt
        for t in sheets[i].texts:
            m = re.search(r"(?:DEPTH|ΒΑΘΟΣ)\D{0,6}(\d+[.,]\d+)", t.text, re.I)
            if m and math.dist(sim.apply((t.x * k, t.y * k)), centre) <= reach:
                return float(m.group(1).replace(",", "."))
    return None


def site_levels(doc, sheets, placed, reference, zeros=None):
    """The terrace levels the set writes outdoors, as terrain ``levels`` [[x, y, z]] (site/terrain.py): the
    absolute «F.L.» of every placed sheet, and the ones written relative to a building's ±0,00 (OLD VILLA
    «−1.20m», on its plans or — near it — on the masterplan) where that ±0,00 is known.  Levels inside a named
    indoor room are left out (there the ground is cut away); the same level written on two sheets counts once."""
    import math
    zeros = zeros or {}
    # Where each building is in the site frame: its plans' placed anchors.
    where = {}
    for i, (sim, _how) in placed.items():
        s = sheets[i]
        if s.kind == "plan" and s.building and zeros.get(s.building) is not None:
            where.setdefault(s.building, []).extend(sim.apply((x, y)) for _k, x, y in s.anchors)
    out = []
    for i, (sim, _how) in sorted(placed.items(), key=lambda kv: sheets[kv[0]].kind != "site"):
        s = sheets[i]
        for v, ceiling, x, y in s.levels():
            # «[C.L.]» outdoors is the deck / construction level (the OLD VILLA pool terrace −0.15 / −0.95), not a
            # ceiling: indoors (and inside a pool: its bottom) it is left out below.
            px, py = sim.apply((x, y))
            if _in_pool(doc, px, py):
                continue
            if v >= 10.0:
                alt = v
            else:
                b = s.building if s.kind == "plan" else min(
                    where, key=lambda k: min(math.dist((px, py), q) for q in where[k]), default=None)
                if b is None or zeros.get(b) is None or (s.kind != "plan" and min(math.dist((px, py), q) for q in where[b]) > 15.0):
                    continue
                alt = zeros[b] + v
            if _indoors(doc, px, py) or any(abs(q[2] - (alt - reference)) < 1e-3 and math.dist(q[:2], (px, py)) < 1.0 for q in out):
                continue
            out.append([round(px, 3), round(py, 3), round(alt - reference, 3)])
    return out


def _in_pool(doc, x, y):
    from archforge.geometry.regions import point_in_polygon
    from archforge.site.pool import rim
    return any(point_in_polygon(x, y, rim(e.params, 0.3)) for e in doc.entities.values() if e.kind == "pool")


def _indoors(doc, x, y):
    """(x, y) inside a named indoor room of any storey."""
    from archforge.architecture.roof_need import OPEN_AIR_USES
    from archforge.geometry.regions import point_in_polygon
    zs = {round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"}
    for z in zs:
        for f in doc.active_room_faces(z=z):
            if point_in_polygon(x, y, f.polygon):
                meta = doc.room_metadata(f.signature)
                if meta.get("name") and meta.get("use") not in OPEN_AIR_USES:
                    return True
    return False


def add_site_walls(window, sheets, placed):
    """The retaining walls of the site plan (its patterned bands — walls_from_lines) that no plan already drew,
    as walls of the ground storey; their height comes later from the ground on their two sides
    (site/retaining.py).  Rows of thin parallel pieces (a pergola's slats, a parking's lines) are not walls."""
    import math
    from archforge.architecture.building_from_drawing import tidy
    from archforge.architecture.walls_from_lines import find_walls
    from archforge.core.commands import AddEntities
    from archforge.core.model import Entity
    doc = window.doc
    sites = [i for i in placed if sheets[i].kind == "site"]
    if not sites:
        return []
    i = sites[0]
    sim = placed[i][0]
    segs = [(*sim.apply((a, b)), *sim.apply((c, d))) for a, b, c, d in sheets[i].segments]
    walls, _openings, _missing = tidy(find_walls(segs), [])
    existing = [(float(e.params["x1"]), float(e.params["y1"]), float(e.params["x2"]), float(e.params["y2"]))
                for e in doc.entities.values() if e.kind == "wall"]

    def drawn(a, b):
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        for x1, y1, x2, y2 in existing:
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy or 1e-12
            t = max(0.0, min(1.0, ((mx - x1) * dx + (my - y1) * dy) / L2))
            if math.hypot(mx - x1 - t * dx, my - y1 - t * dy) < 0.6:
                return True
        return False

    def slat(k):
        a, b, _t = walls[k]
        if math.dist(a, b) > 6.0:
            return False
        ang = math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        n = 0
        for j, (c, d, _u) in enumerate(walls):
            if j == k:
                continue
            ang2 = math.atan2(d[1] - c[1], d[0] - c[0]) % math.pi
            if min(abs(ang - ang2), math.pi - abs(ang - ang2)) < 0.05 and math.dist(mid, ((c[0] + d[0]) / 2, (c[1] + d[1]) / 2)) < 1.2:
                n += 1
        return n >= 2

    keep = [w for k, w in enumerate(walls) if not drawn(w[0], w[1]) and not slat(k)]
    z = float(doc.levels.get("Ground", 0.0))
    made = [Entity("wall", {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1], "z": z, "height": 1.0, "thickness": float(t)},
                   name=f"Τοιχίο {n}") for n, (a, b, t) in enumerate(keep, 1)]
    if made:
        window.stack.execute(AddEntities(made))
    return made


def site_plateaus(doc, sheets, placed, reference, zeros=None):
    """Every finished-floor level the set writes outdoors («+137.10m [F.L.]»), on the area the walls close around
    it, as a plateau — the same as a person's click with Έδαφος ▸ Πλάτωμα (site/plateaus.py).  Levels written
    relative to a building's ±0,00 (OLD VILLA «−1.20m») count where that ±0,00 is known.  Rooms are left out
    (inside a building the ground is cut away).  ``(regions, notes)``."""
    from collections import Counter, defaultdict
    from archforge.geometry.regions import signed_area
    from archforge.site import plateaus as P
    from archforge.site.elevation_regions import validate_regions
    zeros = zeros or {}
    votes = defaultdict(Counter)
    polys = {}
    for i, (sim, _how) in placed.items():
        s = sheets[i]
        zero = zeros.get(s.building)
        for v, ceiling, x, y in s.levels():
            if ceiling:
                continue
            alt = v if v >= 10.0 else (zero + v if zero is not None and s.kind == "plan" else None)
            if alt is None:
                continue
            found = P.area_at(doc, *sim.apply((x, y)))
            if found is None:
                continue
            poly, z = found
            key = tuple(map(tuple, (tuple(round(c, 3) for c in q) for q in poly)))
            if _is_room(doc, poly, z):
                continue
            polys[key] = poly
            votes[key][round(alt, 2)] += 1
    regions, notes = [], []
    # Largest first: a small terrace inside a large leaked area is the better word about its own ground.
    for key in sorted(votes, key=lambda k: abs(signed_area(polys[k]))):
        alt, _n = votes[key].most_common(1)[0]
        r = P.region(polys[key], round(alt - reference, 3), f"plateau-{len(regions) + 1}")
        try:
            validate_regions(regions + [r])
            regions.append(r)
        except ValueError as exc:
            notes.append(f"{alt:+.2f}: {exc}".replace(".", ","))
    return regions, notes


def _is_room(doc, polygon, z):
    """A named indoor room (bedroom, kitchen …) of storey z under ``polygon``: not a terrace."""
    from archforge.architecture.roof_need import OPEN_AIR_USES
    from archforge.geometry.regions import point_in_polygon
    cx = sum(p[0] for p in polygon) / len(polygon); cy = sum(p[1] for p in polygon) / len(polygon)
    for f in doc.active_room_faces(z=z):
        if point_in_polygon(cx, cy, f.polygon):
            meta = doc.room_metadata(f.signature)
            return bool(meta.get("name")) and meta.get("use") not in OPEN_AIR_USES
    return False


def platforms(doc, sheets, storeys, pools, transition=3.0):
    """Terrain regions: each building dug down to its lowest floor (the slope runs up to it — the NEW VILLA is
    partly underground), each pool level with its rim where no building platform is in the way."""
    from archforge.project.drawing_set import platform
    from archforge.site.elevation_regions import validate_regions
    regions = []
    lowest = {}
    for i, (_name, z, _alt) in storeys.items():
        b = sheets[i].building
        lowest[b] = min(lowest.get(b, z), z)
    for b, z in lowest.items():
        pts = [(float(e.params[k1]), float(e.params[k2])) for e in doc.entities.values()
               if e.kind == "wall" and abs(float(e.params["z"]) - z) < 1e-3 for k1, k2 in (("x1", "y1"), ("x2", "y2"))]
        corners = platform(pts) if len(pts) >= 3 else None
        if corners:
            regions.append({"id": f"building-{len(regions) + 1}", "shape": "polygon", "points": corners,
                            "elevation": round(z - 0.15, 3), "transition": transition})
    for e in pools:
        p = e.params
        from archforge.site.pool import rim
        corners = platform([tuple(q) for q in rim(p, 0.5)], grow=0.0)
        candidate = {"id": f"pool-{len(regions) + 1}", "shape": "polygon", "points": corners,
                     "elevation": round(float(p["z"]) - 0.05, 3), "transition": 2.0}
        try:
            validate_regions(regions + [candidate])
            regions.append(candidate)
        except ValueError as exc:                   # inside / against a building platform at another level
            from archforge.core.notices import not_computed
            not_computed("import.pool_platform", f"Εισαγωγή: το πλάτωμα της πισίνας {candidate['id']} δεν μπήκε", exc=exc)
    try:
        return validate_regions(regions)
    except ValueError as exc:
        from archforge.core.notices import not_computed
        kept = [r for r in regions if r["id"].startswith("building")][:1]
        not_computed("import.platforms", f"Εισαγωγή: τα πλατώματα συγκρούονται — κρατήθηκε μόνο "
                     f"{'το πρώτο του κτιρίου' if kept else 'κανένα'} από {len(regions)}", exc=exc)
        return kept


def summary_text(sheets, placed, storeys):
    lines = []
    for i, s in enumerate(sheets):
        where = placed.get(i)
        what = f"{s.building or 'οικόπεδο'} · {KIND_NAMES.get(s.kind, s.kind)}" + (f" · {FLOOR_NAMES.get(s.floor, '')}" if s.floor else "")
        scale = f"1:{s.scale}" if s.scale else "κλίμακα ;"
        if where is None:
            how = "χωρίς θέση" + (" — τομή: στη γραμμή του σημαδιού της στην κάτοψη" if s.kind == "section"
                                  else " — «Ταίριασμα με 2 σημεία» μετά")
        else:
            how = where[1]
        storey = f" → {storeys[i][0]}" if i in storeys else ""
        lines.append(f"• {s.path.split('/')[-1]}: {what}, {scale} — {how}{storey}")
    return "\n".join(lines)


def import_set(window, paths=None, reference=None, ask=True):
    """The whole flow; returns ``{"sheets", "placed", "storeys", "built", "terrain"}`` or None."""
    from archforge.core.commands import AddEntity, CreateFloorLevel
    from archforge.core.model import Entity
    from archforge.project.drawing_set import relate
    from archforge.project.underlay import pdf_params
    from archforge.ui import building_from_underlay as B
    if paths is None:
        paths, _f = QFileDialog.getOpenFileNames(window, "Σύνολο σχεδίων (πολλά PDF)", "", "PDF (*.pdf)")
    if not paths:
        return None
    sheets = read(window, list(paths))
    if sheets is None:
        return None
    placed = relate(sheets)
    probe = plan_storeys(sheets, placed, 0.0)
    if reference is None:
        reference = default_reference(sheets, probe)
    if ask:
        reference, ok = QInputDialog.getDouble(
            window, "Σύνολο σχεδίων", summary_text(sheets, placed, probe) +
            "\n\nΠοιο απόλυτο υψόμετρο είναι το ±0,00 του έργου;", float(reference), -500.0, 9000.0, 2)
        if not ok:
            return None
    storeys = plan_storeys(sheets, placed, float(reference))
    doc, stack = window.doc, window.stack
    since = len(stack.done)
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    built, terrain = {}, None
    from archforge.core.notices import collecting
    gathered = collecting()
    not_computed = gathered.__enter__()             # Α3: what the import could not read is in its report
    try:
        for i, (sim, _how) in sorted(placed.items(), key=lambda kv: (sheets[kv[0]].kind != "site", storeys.get(kv[0], ("", 0.0))[1])):
            s = sheets[i]
            z = storeys[i][1] if i in storeys else 0.0
            if i in storeys:
                name = storeys[i][0]
                existing = next((n for n, v in doc.levels.items() if abs(float(v) - z) < 1e-3), None)
                if existing is None:
                    stack.execute(CreateFloorLevel(name, z))
                else:
                    window._refresh_floor_selector(); window._activate_level_by_name(existing)
            params = pdf_params(s.path, s.page, s.scale or 100, s.page_size, z)
            params.update(m_per_unit=s.metres_per_pt * sim.scale, rotation=sim.turn, x=sim.shift[0], y=sim.shift[1])
            u = Entity("underlay", params, name=f"Υπόβαθρο {s.path.split('/')[-1]}")
            stack.execute(AddEntity(u))
            if s.kind == "plan" and i in storeys:
                from archforge.architecture.building_from_drawing import analyse_sheet
                built[i] = B.build(window, u.id, found=analyse_sheet(s, sim), ask=False)
            if s.kind == "site":
                pts = [(*sim.apply((x, y)), v) for v, c, x, y in s.levels() if not c and v >= B.ALTITUDE_MIN]
                if len(pts) >= 3:
                    from archforge.site.survey import terrain_from_survey
                    terrain = terrain_from_survey(doc, pts, in_place=True, altitude_ref=float(reference))
        made_pools = add_pools(window, sheets, placed, float(reference))
        sections = add_sections(window, sheets, placed)
        roofs = add_roof_slabs(window, sheets, storeys, sections, building_zeros(sheets, placed), float(reference))
        if terrain is not None:
            # The ground under everything that was drawn (retaining walls at the plot's edge, the pools), 5 m round.
            xs = [float(e.params[k]) for e in doc.entities.values() if e.kind == "wall" for k in ("x1", "x2")]
            ys = [float(e.params[k]) for e in doc.entities.values() if e.kind == "wall" for k in ("y1", "y2")]
            xs += [float(e.params["x"]) for e in made_pools]; ys += [float(e.params["y"]) for e in made_pools]
            if xs:
                nx0, ny0 = min(terrain["x0"], min(xs) - 5.0), min(terrain["y0"], min(ys) - 5.0)
                # «elevation» is the graded plane's height at (x0, y0): moving the corner keeps the same plane.
                terrain["elevation"] += (terrain["slope_x"] * (nx0 - terrain["x0"]) + terrain["slope_y"] * (ny0 - terrain["y0"])) / 100.0
                terrain.update(x0=nx0, y0=ny0, x1=max(terrain["x1"], max(xs) + 5.0), y1=max(terrain["y1"], max(ys) + 5.0))
            # The written levels are terraces held by the walls (site/terrain.py levels): the plane fitted through
            # them stays as the slope of the open ground; a pool's rim is level with it.  No dug platforms: the
            # ground steps at the walls the drawings draw.
            from archforge.site.elevation_regions import validate_regions
            site_walls = add_site_walls(window, sheets, placed)
            terrain["levels"] = site_levels(doc, sheets, placed, float(reference), building_zeros(sheets, placed))
            terrain["points"] = []
            regions = []
            for r in platforms(doc, sheets, storeys, made_pools):
                if r["id"].startswith("pool"):
                    try:
                        regions = validate_regions(regions + [r])
                    except ValueError as exc:
                        from archforge.core.notices import not_computed
                        not_computed("import.pool_platform", f"Εισαγωγή: το πλάτωμα της πισίνας {r['id']} δεν μπήκε",
                                     exc=exc)
            if regions:
                terrain["regions"] = regions
            section_ground(terrain, sections)
            stack.execute(AddEntity(Entity("terrain", terrain, name="Έδαφος")))
            green_roofs_from_sections(window, sections, roofs)
            # Each retaining wall from the lower ground on its one side to the higher on the other.
            from archforge.site.retaining import fit_command
            command, _n = fit_command(doc, site_walls)
            if command is not None:
                stack.execute(command)
        if sections:
            from archforge.project import section_fit as F
            from archforge.site.terrain import terrain_height_at
            for v in sections.values():
                if v["fit"] and v["profile"]:
                    off = F.ground_check(v["profile"], v["line"], v["flip"], lambda x, y: terrain_height_at(doc, x, y))
                    v["report"] += " · " + F.ground_text(off)
    finally:
        gathered.__exit__(None, None, None)
        QApplication.restoreOverrideCursor()
    stack.squash(since, "Σύνολο σχεδίων")
    window._refresh_floor_selector()
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    done = {"sheets": sheets, "placed": placed, "storeys": storeys, "built": built, "terrain": terrain, "pools": made_pools,
            "sections": sections, "roofs": roofs, "not_computed": [i.message for i in not_computed]}
    text = (f"{len(placed)} από {len(sheets)} σχέδια στη θέση τους · {len(set(n for n, _z, _a in storeys.values()))} όροφοι · "
            f"τοίχοι {sum(b['walls'] for b in built.values() if b)} · πισίνες {len(made_pools)} · "
            f"έδαφος από {len(terrain['points']) if terrain else 0} υψόμετρα"
            f" · πλάκες οροφής {len(roofs)} · τομές στη θέση τους {sum(1 for v in sections.values() if v['fit'])}"
            " — Ctrl+Z αναιρεί όλο το σύνολο")
    window.statusBar().showMessage(text, 20000)
    if ask:
        checks = "\n".join(v["report"] for v in sections.values())
        missing = "\n".join("• " + m for m in done["not_computed"])
        QMessageBox.information(window, "Σύνολο σχεδίων", summary_text(sheets, placed, storeys) + "\n\n" + text +
                                ("\n\n" + checks if checks else "") +
                                ("\n\nΕΛΛΙΠΗΣ ΕΙΣΑΓΩΓΗ — δεν διαβάστηκαν:\n" + missing if missing else ""))
    return done
