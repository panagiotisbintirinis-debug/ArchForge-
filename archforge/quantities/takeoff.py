"""Quantity take-off (επιμέτρηση) per room, from the Document.

Rules (stated so the quantities can be checked):

* Net interior surfaces: the room outline (wall axes) is offset inwards by
  half the thickness of each bounding wall.  Height = the lowest bounding
  wall (floor to ceiling).
* Walls: net perimeter × height, minus the doors and windows of the room
  (width × height).  Ceiling = net floor area.
* Wet rooms (bathroom / WC): wall tiles up to 2.10 m (minus the part of the
  openings below 2.10 m); the rest of the wall is painted.  Floor tiles in
  every room unless the room's floor finish says wood/parquet.
* Skirting: net perimeter minus door widths (not in tiled wet rooms).
* Slab openings (atrium, inner balcony, void): their part of the room is
  taken out of the floor (floor cuts of the storey) and of the ceiling
  (roof cuts of the storey, floor cuts of the storey above).  Slabs: net
  area and concrete volume of every slab after its openings.
* Renovation: walls marked for demolition give demolition m² and m³; new
  openings in existing walls are listed as openings to cut.
"""
from __future__ import annotations

import math

WET_TILE_HEIGHT = 2.10
PROVENANCE = ("Επιμέτρηση από το σχέδιο: καθαρές εσωτερικές επιφάνειες (άξονες τοίχων μείον μισό πάχος), "
              "ανοίγματα αφαιρούνται, πλακάκια τοίχου μπάνιου ως 2,10 m — προς έλεγχο πριν την τιμολόγηση")


def _area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
               for i in range(len(poly))) / 2.0


def _edge_thickness(doc, a, b, z):
    """Thickness of the wall whose axis carries the edge a-b (0.15 when none)."""
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    for w in doc.entities.values():
        if w.kind != "wall" or abs(float(w.params.get("z", 0.0)) - z) > 0.05:
            continue
        p = w.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        dist = abs((x2 - x1) * (y1 - my) - (x1 - mx) * (y2 - y1)) / L
        t = ((mx - x1) * (x2 - x1) + (my - y1) * (y2 - y1)) / (L * L)
        if dist < 0.02 and -0.01 <= t <= 1.01:
            return float(p["thickness"])
    return 0.15


def net_polygon(doc, poly, z):
    """Room outline offset inwards by half the thickness of each bounding wall."""
    pts = [(float(p[0]), float(p[1])) for p in poly]
    if _area(pts) < 0:
        pts = pts[::-1]                                    # counter-clockwise: inside is on the left
    n = len(pts)
    lines = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
        nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
        d = _edge_thickness(doc, a, b, z) / 2
        lines.append(((a[0] + nx * d, a[1] + ny * d), (b[0] + nx * d, b[1] + ny * d)))
    out = []
    for i in range(n):
        (p1, p2), (p3, p4) = lines[i - 1], lines[i]
        den = (p1[0] - p2[0]) * (p3[1] - p4[1]) - (p1[1] - p2[1]) * (p3[0] - p4[0])
        if abs(den) < 1e-12:
            out.append(p3)
            continue
        t = ((p1[0] - p3[0]) * (p3[1] - p4[1]) - (p1[1] - p3[1]) * (p3[0] - p4[0])) / den
        out.append((p1[0] + t * (p2[0] - p1[0]), p1[1] + t * (p2[1] - p1[1])))
    return out


def _room_height(doc, poly, z):
    hs = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        for w in doc.entities.values():
            if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - z) < 0.05 and _edge_thickness(doc, a, b, z) == float(w.params["thickness"]):
                hs.append(float(w.params["height"]))
                break
    return min(hs) if hs else 2.7


def _cut_area(doc, net, z, target, storeys):
    from archforge.architecture.storey_slabs import openings_for
    from archforge.geometry.regions import islands_area, region
    cuts = [poly for _e, poly in openings_for(doc, z, target)]
    if target == "roof":
        above = [s for s in storeys if s > z + 0.5]
        if above:
            cuts += [poly for _e, poly in openings_for(doc, min(above), "floor")]
    if not cuts:
        return 0.0
    return max(0.0, abs(_area(net)) - islands_area(region([net], cuts)))


def slab_quantities(doc):
    """Concrete slabs after their openings: ``[{"name", "area_m2", "openings_m2", "volume_m3"}]``."""
    from archforge.architecture.rooms import room_slab_geometry
    from archforge.geometry.regions import islands_area
    out = []
    for e in doc.entities.values():
        if e.kind not in ("room_floor", "room_roof", "room_ceiling", "room_foundation"):
            continue
        try:
            g = room_slab_geometry(doc, e)
        except (ValueError, KeyError):
            g = None
        if g is None:
            continue
        islands = g.get("islands") or [(g["points"], [])]
        net = islands_area(islands)
        gross = sum(abs(_area(o)) for o, _h in islands)
        out.append({"name": e.name or e.kind, "area_m2": round(net, 2), "openings_m2": round(gross - net, 2),
                    "volume_m3": round(net * float(g["thickness"]), 2)})
    return out


def take_off(doc):
    """``{"rooms": [...], "demolition": {...}, "totals": {...}, "provenance": str}``."""
    from archforge.assistant.understanding import read_drawing
    reading = read_drawing(doc)
    rooms = []
    storeys = sorted(float(s["z"]) for s in reading["storeys"])
    for storey in reading["storeys"]:
        z = storey["z"]
        for r in storey["rooms"]:
            net = net_polygon(doc, r["polygon"], z)
            floor = abs(_area(net))
            floor_cut = _cut_area(doc, net, z, "floor", storeys)
            ceiling = max(0.0, floor - _cut_area(doc, net, z, "roof", storeys))
            floor = max(0.0, floor - floor_cut)
            perim = sum(math.dist(net[i], net[(i + 1) % len(net)]) for i in range(len(net)))
            h = _room_height(doc, r["polygon"], z)
            openings, door_w, below = 0.0, 0.0, 0.0
            for oid in r["windows"] + r["doors"]:
                o = doc.get(oid).params
                w_, h_ = float(o.get("width", 0.0)), float(o.get("height", 0.0))
                sill = float(o.get("sill", 0.0)) if doc.get(oid).kind == "window" else 0.0
                openings += w_ * h_
                below += w_ * max(0.0, min(sill + h_, WET_TILE_HEIGHT) - min(sill, WET_TILE_HEIGHT))
                if doc.get(oid).kind == "door":
                    door_w += w_
            walls = max(0.0, perim * h - openings)
            wet = r["use"] in ("bathroom", "wc")
            wall_tiles = max(0.0, perim * min(h, WET_TILE_HEIGHT) - below) if wet else 0.0
            finish = str((doc.room_metadata(r["signature"]) or {}).get("floor_finish", "")).lower()
            wood = any(k in finish for k in ("ξύλ", "ξυλ", "wood", "parquet", "πάρκε", "παρκε"))
            rooms.append({
                "storey": storey["name"], "name": r["name"], "use": r["use"], "height_m": round(h, 2),
                "floor_m2": round(floor, 2), "perimeter_m": round(perim, 2), "ceiling_m2": round(ceiling, 2),
                "walls_m2": round(walls, 2), "openings_m2": round(openings, 2),
                "paint_walls_m2": round(walls - wall_tiles, 2), "paint_ceiling_m2": round(ceiling, 2),
                "floor_tiles_m2": 0.0 if wood else round(floor, 2), "wood_floor_m2": round(floor, 2) if wood else 0.0,
                "wall_tiles_m2": round(wall_tiles, 2), "skirting_m": 0.0 if wet else round(max(0.0, perim - door_w), 2),
            })
    demo = {"walls_m2": 0.0, "walls_m3": 0.0, "count": 0, "openings_to_cut": 0, "openings_to_cut_m2": 0.0}
    for e in doc.entities.values():
        p = e.params
        if e.kind == "wall" and str(p.get("phase", "new")) == "demolish":
            L = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
            demo["walls_m2"] += L * float(p["height"])
            demo["walls_m3"] += L * float(p["height"]) * float(p["thickness"])
            demo["count"] += 1
        elif e.kind in ("door", "window", "opening") and str(p.get("phase", "new")) == "new" and e.parent_id in doc.entities \
                and str(doc.get(e.parent_id).params.get("phase", "new")) == "existing":
            demo["openings_to_cut"] += 1
            demo["openings_to_cut_m2"] += float(p.get("width", 0.0)) * float(p.get("height", 0.0))
    demo = {k: round(v, 2) if isinstance(v, float) else v for k, v in demo.items()}
    keys = ("floor_m2", "ceiling_m2", "walls_m2", "paint_walls_m2", "paint_ceiling_m2", "floor_tiles_m2",
            "wood_floor_m2", "wall_tiles_m2", "skirting_m")
    totals = {k: round(sum(r[k] for r in rooms), 2) for k in keys}
    return {"rooms": rooms, "demolition": demo, "totals": totals, "slabs": slab_quantities(doc), "provenance": PROVENANCE}


COLUMNS = (("storey", "Όροφος"), ("name", "Χώρος"), ("floor_m2", "Δάπεδο m²"), ("perimeter_m", "Περίμετρος m"),
           ("height_m", "Ύψος m"), ("walls_m2", "Τοίχοι m² (πλην ανοιγμ.)"), ("paint_walls_m2", "Βαφή τοίχων m²"),
           ("paint_ceiling_m2", "Βαφή οροφής m²"), ("floor_tiles_m2", "Πλακάκια δαπέδου m²"),
           ("wall_tiles_m2", "Πλακάκια τοίχου m²"), ("wood_floor_m2", "Ξύλινο δάπεδο m²"), ("skirting_m", "Σοβατεπί m"))


def to_csv(result):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([label for _k, label in COLUMNS])
    for r in result["rooms"]:
        w.writerow([str(r[k]).replace(".", ",") if isinstance(r[k], float) else r[k] for k, _l in COLUMNS])
    t = result["totals"]
    w.writerow(["Σύνολο", ""] + [str(t.get(k, "")).replace(".", ",") for k, _l in COLUMNS[2:]])
    d = result["demolition"]
    w.writerow([])
    w.writerow(["Καθαιρέσεις τοίχων m²", str(d["walls_m2"]).replace(".", ","), "m³", str(d["walls_m3"]).replace(".", ",")])
    w.writerow(["Διανοίξεις σε υφιστάμενους τοίχους", d["openings_to_cut"], "m²", str(d["openings_to_cut_m2"]).replace(".", ",")])
    for s in result.get("slabs", ()):
        w.writerow([s["name"], "m²", str(s["area_m2"]).replace(".", ","), "οπές m²", str(s["openings_m2"]).replace(".", ","),
                    "m³", str(s["volume_m3"]).replace(".", ",")])
    return buf.getvalue()
