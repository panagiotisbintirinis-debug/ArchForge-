"""Generate the ten human-openable ArchForge residential integration projects.

These files are TEST FIXTURES, not engineering designs. Geometry, MEP and structure
exist to exercise the software pipeline. Any price values are synthetic test values
(1.00) and must never be presented as market prices.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "manifest.json"


def _entity(kind, params, name, eid):
    return {
        "kind": kind,
        "params": params,
        "name": name,
        "id": eid,
        "parent_id": None,
        "locked": False,
        "visible": True,
        "revision": 0,
    }


def _cabinet(x, y, z, kind="base"):
    p = {
        "x": x, "y": y, "z": z, "rotation": 0.0,
        "width": 0.6, "depth": 0.6, "height": 0.86, "plinth": 0.10,
        "height_end": 0.86, "cabinet_type": kind,
        "doors": 1, "drawers": 1, "shelves": 1, "worktop": 1.0,
        "handle": "bar", "front_style": "flat", "mechanism": "none",
        "blind_side": "left",
    }
    if kind == "sink":
        p.update(width=0.8, doors=2, drawers=0, shelves=0, mechanism="bin")
    return p


def _price_book():
    prices = {}
    for diameter in (15, 16, 18, 20, 22, 26):
        for network in ("cold", "hot"):
            prices[f"plumbing.pipe.{network}.dn{diameter}"] = {"material": 1.0, "labour": 1.0}
    for point_type in ("wc", "basin", "shower", "kitchen_sink"):
        prices[f"plumbing.point.{point_type}"] = {"material": 1.0, "labour": 1.0}
    for network in ("cold", "hot"):
        for ways in range(1, 13):
            prices[f"plumbing.manifold.{network}.{ways}way"] = {"material": 1.0, "labour": 1.0}
    return prices


def build_project(spec):
    n = int(spec["id"][1:])
    storeys = int(spec["storeys"])
    w = [10, 11, 9, 12, 8, 14, 7, 13, 10, 12][n - 1]
    d = [8, 7, 9, 9, 7, 10, 11, 8, 10, 8][n - 1]
    heights = [float(v) for v in spec["levels"]]
    levels = {"Ground": 0.0}
    zs = [0.0]
    z = 0.0
    for i, h in enumerate(heights[:-1], start=1):
        z += h
        z = round(z, 3)
        levels[f"Level {i}"] = z
        zs.append(z)

    entities = []
    for k, z in enumerate(zs):
        h = heights[k]
        corners = [(0, 0), (w, 0), (w, d), (0, d)]
        for j, (a, b) in enumerate(zip(corners, corners[1:] + corners[:1])):
            entities.append(_entity("wall", {
                "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                "z": z, "height": h - 0.30, "thickness": 0.25,
            }, f"Exterior wall L{k}", f"s{n:02d}-wall-{k}-{j}"))
        entities.append(_entity("wall", {
            "x1": w / 2, "y1": 0, "x2": w / 2, "y2": d,
            "z": z, "height": h - 0.30, "thickness": 0.15,
        }, f"Partition A L{k}", f"s{n:02d}-part-{k}-a"))
        entities.append(_entity("wall", {
            "x1": 0, "y1": d / 2, "x2": w, "y2": d / 2,
            "z": z, "height": h - 0.30, "thickness": 0.15,
        }, f"Partition B L{k}", f"s{n:02d}-part-{k}-b"))
        entities.append(_entity("floor", {
            "points": [[0, 0], [w, 0], [w, d], [0, d]],
            "z": z - 0.18 if z else -0.18, "thickness": 0.18,
        }, f"Floor L{k}", f"s{n:02d}-floor-{k}"))

        furniture = [
            (1.0, 1.0, 2.2, 0.9, 0.75, "Καναπές"),
            (w - 2.4, d - 2.0, 2.0, 1.6, 0.55, "Κρεβάτι"),
            (w / 2 - 0.8, d / 2 + 0.7, 1.6, 0.9, 0.75, "Τραπέζι"),
        ]
        for j, (x, y, fw, fd, fh, label) in enumerate(furniture):
            entities.append(_entity("box", {
                "x": x, "y": y, "z": z, "width": fw, "depth": fd,
                "height": fh, "rotation": 0.0,
            }, f"{label} L{k}", f"s{n:02d}-furn-{k}-{j}"))

        if k == 0 or k == len(zs) - 1:
            entities.append(_entity("cabinet", _cabinet(1.0, d - 0.5, z),
                                    f"Kitchen base L{k}", f"s{n:02d}-cab-{k}-0"))
            entities.append(_entity("cabinet", _cabinet(1.8, d - 0.5, z, "sink"),
                                    f"Kitchen sink cabinet L{k}", f"s{n:02d}-cab-{k}-1"))

    for idx, z in enumerate(zs[1:1 + int(spec["balconies"])], start=1):
        if idx % 2:
            points = [[2, 0], [w - 2, 0], [w - 2, -1.6], [2, -1.6]]
        else:
            points = [[0, 2], [-1.5, 2], [-1.5, d - 2], [0, d - 2]]
        entities.append(_entity("floor", {"points": points, "z": z - 0.18, "thickness": 0.18},
                                f"Balcony L{idx}", f"s{n:02d}-balcony-{idx}"))
        entities.append(_entity("railing", {
            "points": [points[1], points[2], points[3], points[0]],
            "z": z, "closed": 0, "height": 1.05,
        }, f"Balcony railing L{idx}", f"s{n:02d}-rail-{idx}"))

    if spec["split_level"]:
        sz = 1.40
        levels["Split +1.40"] = sz
        x0, x1, y0, y1 = w + 1.0, w + 5.0, 1.0, d - 1.0
        points = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
        entities.append(_entity("floor", {"points": points, "z": sz - 0.18, "thickness": 0.18},
                                "Split-level wing floor", f"s{n:02d}-split-floor"))
        for j, (a, b) in enumerate(zip(points, points[1:] + points[:1])):
            entities.append(_entity("wall", {
                "x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1],
                "z": sz, "height": 2.70, "thickness": 0.20,
            }, "Split-level wing wall", f"s{n:02d}-split-wall-{j}"))

    top_z = zs[-1] + heights[-1]
    entities.append(_entity("pitched_roof", {
        "x0": 0.0, "y0": 0.0, "x1": w, "y1": d, "eave_z": top_z,
        "pitch": 25 + 2 * (n % 5), "overhang": 0.45, "rafter_spacing": 0.60,
        "roof_form": spec["roof_form"], "tile": spec["tile"], "snow_zone": 2,
        "altitude": 0.0, "insulation": "none", "insulation_thickness": 0.0,
        "shed_high": "auto",
    }, f"{spec['name']} tiled roof", f"s{n:02d}-roof"))

    xs, ys = [0, w / 2, w], [0, d / 2, d]
    for k, z in enumerate(zs):
        h = heights[k]
        top = z + h
        for ix, x in enumerate(xs):
            for iy, y in enumerate(ys):
                entities.append(_entity("structural_column", {
                    "x": x, "y": y, "z": z, "width": 0.40, "depth": 0.40,
                    "height": h, "rotation": 0.0, "role": "structural",
                    "construction": "reinforced_concrete", "section": "rectangular",
                    "base_level": "Ground" if k == 0 else f"Level {k}",
                    "top_level": f"Level {k + 1}" if k + 1 < len(zs) else "Unassigned",
                    "profile": "",
                }, "", f"s{n:02d}-col-{k}-{ix}-{iy}"))
        beam_z = top - 0.50
        for iy, y in enumerate(ys):
            entities.append(_entity("structural_beam", {
                "x1": 0, "y1": y, "x2": w, "y2": y, "z": beam_z,
                "width": 0.25, "height": 0.50, "role": "structural",
                "construction": "reinforced_concrete", "section": "rectangular",
                "level": f"Level {k}" if k else "Ground", "profile": "",
            }, "", f"s{n:02d}-beamx-{k}-{iy}"))
        for ix, x in enumerate(xs):
            entities.append(_entity("structural_beam", {
                "x1": x, "y1": 0, "x2": x, "y2": d, "z": beam_z,
                "width": 0.25, "height": 0.50, "role": "structural",
                "construction": "reinforced_concrete", "section": "rectangular",
                "level": f"Level {k}" if k else "Ground", "profile": "",
            }, "", f"s{n:02d}-beamy-{k}-{ix}"))

    entities.append(_entity("plumbing_point", {
        "x": 0.6, "y": 0.6, "z": 0.0, "point_type": "water_supply",
        "pipe_system": spec["pipe_system"],
    }, "Παροχή κρύου νερού", f"s{n:02d}-water"))
    for k, z in enumerate(zs):
        for j, (point_type, x, y) in enumerate((
            ("wc", 1.0, d - 1.0), ("basin", 2.0, d - 1.0),
            ("shower", 3.0, d - 1.0), ("kitchen_sink", 1.8, d - 0.7),
        )):
            entities.append(_entity("plumbing_point", {
                "x": x, "y": y, "z": z, "point_type": point_type,
            }, f"{point_type} L{k}", f"s{n:02d}-plumb-{k}-{j}"))

        electrical = (
            ("panel", 0.7, 0.7), ("light", w / 4, d / 4),
            ("light", 3 * w / 4, 3 * d / 4), ("switch", 0.8, d / 2),
            ("socket", 2.0, 0.5), ("socket", w - 2.0, 0.5),
            ("kitchen_socket", 1.5, d - 0.4),
        )
        for j, (point_type, x, y) in enumerate(electrical):
            entities.append(_entity("electrical_point", {
                "x": x, "y": y, "z": z, "point_type": point_type,
            }, f"{point_type} L{k}", f"s{n:02d}-elec-{k}-{j}"))

    entities.append(_entity("price_list", {
        "vat": 0.0, "trade_prices": _price_book(),
    }, "TEST_FIXTURE prices — not market data", f"s{n:02d}-prices"))

    return {
        "format": 7,
        "entities": entities,
        "dependencies": {},
        "levels": levels,
        "work_plane": {"name": "XY", "origin": [0, 0, 0], "u": [1, 0, 0], "v": [0, 1, 0]},
        "materials": {}, "constructions": {}, "room_data": {}, "room_bindings": {},
        "surface_modifiers": [],
    }


def main():
    specs = json.loads(MANIFEST.read_text(encoding="utf8"))
    for spec in specs:
        path = ROOT / spec["file"]
        path.write_text(json.dumps(build_project(spec), ensure_ascii=False, indent=2) + "\n", encoding="utf8")
        print(f"generated {path.name}")


if __name__ == "__main__":
    main()
