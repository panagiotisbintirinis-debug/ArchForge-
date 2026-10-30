"""IFC import (the translator, other way round — HANDOFF 30/10 «εισαγωγή IFC»).

Reads storeys, walls and the doors / windows / openings in them, and adds them to the project as **one undo step**
through the same commands as drawing by hand (``AddEntities``, ``SetLevel``, ``wall_assemblies``).  Nothing is
kept that the program cannot edit: what is not read is counted and said («δεν εισήχθησαν»).

* **Storeys** → project levels (``LongName`` when it holds our own name, else ``Name``) at their ``Elevation``.
* **Walls** → ``wall``: axis from the ``Axis`` representation (as ArchiCAD / Revit / our export write it); without
  one, the long side of the smallest rectangle round the body in plan.  Base and height from the body, thickness
  from the material layer set (else the rectangle's short side).
  Build-up: when every layer's material is one of ours by name (``construction/building_materials``) the wall gets
  the built-in type with the same layers, or a new project type (``wall_assemblies``); otherwise ``generic`` and the
  layer names are kept in the summary.
* **Doors / windows / openings** → hosted on their wall (``IfcRelVoidsElement`` / ``IfcRelFillsElement``): position
  along the axis, width, height and sill from the opening's body.
* Rooms come from the walls as always; slabs, roofs, stairs, MEP … are counted, not imported (yet).
"""
from __future__ import annotations

import math

WALL_CLASSES = ("IfcWall", "IfcWallStandardCase", "IfcCurtainWall")


def _settings():
    import ifcopenshell.geom
    s = ifcopenshell.geom.settings()
    s.set(s.USE_WORLD_COORDS, True)
    return s


def _verts(product, settings):
    import ifcopenshell.geom
    try:
        shape = ifcopenshell.geom.create_shape(settings, product)
    except Exception:                                       # noqa: BLE001 — no body: told as not imported
        return []
    v = shape.geometry.verts
    return [(v[i], v[i + 1], v[i + 2]) for i in range(0, len(v), 3)]


def _hull(points):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in points))
    if len(pts) < 3:
        return pts

    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lower, upper = half(pts), half(reversed(pts))
    return lower[:-1] + upper[:-1]


def min_rectangle(points):
    """(centre, unit long direction, long side, short side) of the smallest rectangle round ``points`` (plan)."""
    hull = _hull(points)
    best = None
    for i in range(len(hull)):
        a, b = hull[i], hull[(i + 1) % len(hull)]
        length = math.dist(a, b)
        if length < 1e-9:
            continue
        u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        n = (-u[1], u[0])
        su = [p[0] * u[0] + p[1] * u[1] for p in hull]
        sn = [p[0] * n[0] + p[1] * n[1] for p in hull]
        area = (max(su) - min(su)) * (max(sn) - min(sn))
        if best is None or area < best[0] - 1e-12:
            best = (area, u, n, (min(su), max(su)), (min(sn), max(sn)))
    if best is None:
        return None
    _a, u, n, (u0, u1), (n0, n1) = best
    if u1 - u0 < n1 - n0:                                      # the long side is the wall's direction
        u, n, (u0, u1), (n0, n1) = n, (-u[0], -u[1]), (n0, n1), (-u1, -u0)
    cu, cn = (u0 + u1) / 2, (n0 + n1) / 2
    centre = (u[0] * cu + n[0] * cn, u[1] * cu + n[1] * cn)
    return centre, u, u1 - u0, n1 - n0


def _axis(product, scale=1.0):
    """The plan end points of the ``Axis`` representation in world coordinates (metres), or None."""
    import numpy as np
    import ifcopenshell.util.placement as placement
    rep = product.Representation
    if rep is None:
        return None
    for r in rep.Representations:
        if r.RepresentationIdentifier != "Axis" or not r.Items:
            continue
        item = r.Items[0]
        pts = [tuple(p.Coordinates) for p in item.Points] if item.is_a("IfcPolyline") else \
            [tuple(c) for c in item.Points.CoordList] if item.is_a("IfcIndexedPolyCurve") else []
        if len(pts) < 2:
            continue
        m = placement.get_local_placement(product.ObjectPlacement) if product.ObjectPlacement else np.eye(4)
        out = []
        for p in (pts[0], pts[-1]):
            v = m @ np.array([float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0, 1.0])
            out.append((float(v[0]) * scale, float(v[1]) * scale))
        return out
    return None


def _layers(product, scale=1.0):
    import ifcopenshell.util.element as element
    mat = element.get_material(product, should_skip_usage=True)
    if mat is None or not mat.is_a("IfcMaterialLayerSet"):
        return [], ""
    return [(l.Material.Name if l.Material else "", float(l.LayerThickness) * scale) for l in mat.MaterialLayers], \
        str(mat.LayerSetName or "")


def _storey_of(product):
    for rel in getattr(product, "ContainedInStructure", ()) or ():
        s = rel.RelatingStructure
        if s.is_a("IfcBuildingStorey"):
            return s
    return None


def _storey_name(s):
    return str(s.LongName or s.Name or "Όροφος")


def read(path):
    """What the file holds, in plan terms: ``{"storeys", "walls", "openings", "not_imported"}``."""
    import ifcopenshell
    import ifcopenshell.util.unit as unit
    f = ifcopenshell.open(str(path))
    scale = unit.calculate_unit_scale(f)                       # file length unit → metres (bodies come in metres)
    settings = _settings()
    storeys = [(_storey_name(s), float(s.Elevation or 0.0) * scale) for s in f.by_type("IfcBuildingStorey")]
    walls, openings, counted = [], [], {}
    for w in (x for c in WALL_CLASSES for x in f.by_type(c, include_subtypes=False)):
        verts = _verts(w, settings)
        if not verts:
            counted[w.is_a()] = counted.get(w.is_a(), 0) + 1
            continue
        layers, set_name = _layers(w, scale)
        rect = min_rectangle([(x, y) for x, y, _z in verts])
        axis = _axis(w, scale)
        if axis is None and rect is not None:
            c, u, length, _short = rect
            axis = [(c[0] - u[0] * length / 2, c[1] - u[1] * length / 2), (c[0] + u[0] * length / 2, c[1] + u[1] * length / 2)]
        if axis is None or math.dist(*axis) < 1e-3:
            counted[w.is_a()] = counted.get(w.is_a(), 0) + 1
            continue
        thickness = sum(d for _n, d in layers) if layers else (rect[3] if rect else 0.2)
        z0, z1 = min(v[2] for v in verts), max(v[2] for v in verts)
        storey = _storey_of(w)
        walls.append({"guid": w.GlobalId, "name": str(w.Name or ""), "a": axis[0], "b": axis[1], "z": z0,
                      "height": z1 - z0, "thickness": thickness, "layers": layers, "layer_set": set_name,
                      "storey": _storey_name(storey) if storey else None})
        for rel in getattr(w, "HasOpenings", ()) or ():
            hole = rel.RelatedOpeningElement
            fills = [r.RelatedBuildingElement for r in getattr(hole, "HasFillings", ()) or ()]
            leaf = fills[0] if fills else None
            pts = _verts(hole, settings)
            if not pts:
                counted["IfcOpeningElement"] = counted.get("IfcOpeningElement", 0) + 1
                continue
            kind = "door" if leaf is not None and leaf.is_a("IfcDoor") else \
                "window" if leaf is not None and leaf.is_a("IfcWindow") else "opening"
            openings.append({"wall": w.GlobalId, "kind": kind, "name": str((leaf or hole).Name or ""), "points": pts,
                             "width": float(getattr(leaf, "OverallWidth", 0.0) or 0.0) * scale,
                             "height": float(getattr(leaf, "OverallHeight", 0.0) or 0.0) * scale})
    for cls in ("IfcSlab", "IfcRoof", "IfcStair", "IfcColumn", "IfcBeam", "IfcSpace", "IfcFurnishingElement",
                "IfcFlowTerminal", "IfcRailing", "IfcCovering"):
        n = len(f.by_type(cls))
        if n:
            counted[cls] = counted.get(cls, 0) + n
    return {"storeys": storeys, "walls": walls, "openings": openings, "not_imported": counted}


def _wall_type(doc, layers, set_name, made):
    """``(wall_type, command or None)`` for the IFC layers: a built-in type with the same layers, an earlier new
    one of this import, a new project type, or ``generic``."""
    from archforge.architecture import wall_assemblies as wa
    from archforge.architecture.wall_types import WALL_TYPES, layers as type_layers
    from archforge.construction.building_materials import MATERIALS
    by_name = {m.name: m.id for m in MATERIALS.values()}
    if not layers or not all(n in by_name for n, _d in layers):
        return "generic", None
    rows = [(by_name[n], round(d, 4)) for n, d in layers]
    for key in WALL_TYPES:
        if [(l.material_id, round(l[1], 4)) for l in type_layers(key)] == rows:
            return key, None
    sig = tuple(rows)
    if sig in made:
        return made[sig], None
    key, cmd = wa.new_type_command(doc, set_name or "Σύνθεση από IFC", [{"material": m, "thickness": d} for m, d in rows],
                                   taken=set(made.values()))
    made[sig] = key
    return key, cmd


def import_command(doc, data):
    """``(command, summary)``: everything read, as one undo step."""
    from archforge.core.commands import AddEntities, CompositeCommand, SetLevel
    from archforge.core.model import Entity
    commands, made, by_guid, entities = [], {}, {}, []
    known = {round(float(z), 4): n for n, z in doc.levels.items()}
    for name, z in data["storeys"]:
        if round(z, 4) not in known and name not in doc.levels:
            commands.append(SetLevel(name, float(z)))
            known[round(z, 4)] = name
    for w in data["walls"]:
        wall_type, cmd = _wall_type(doc, w["layers"], w["layer_set"], made)
        if cmd is not None:
            commands.append(cmd)
        e = Entity("wall", {"x1": w["a"][0], "y1": w["a"][1], "x2": w["b"][0], "y2": w["b"][1], "z": round(w["z"], 6),
                            "height": round(w["height"], 6), "thickness": round(w["thickness"], 6),
                            "wall_type": wall_type}, name=w["name"] or "Τοίχος")
        by_guid[w["guid"]] = (e, w)
        entities.append(e)
    placed = 0
    for o in data["openings"]:
        host = by_guid.get(o["wall"])
        if host is None:
            continue
        e, w = host
        a, b = w["a"], w["b"]
        length = math.dist(a, b)
        u = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
        s = [(x - a[0]) * u[0] + (y - a[1]) * u[1] for x, y, _z in o["points"]]
        zs = [z for _x, _y, z in o["points"]]
        width = min(max(s), length) - max(min(s), 0.0)
        height = max(zs) - min(zs)
        if o["width"] > 0 and o["width"] <= width + 0.05:
            width = o["width"]
        if o["height"] > 0 and o["height"] <= height + 0.05:
            height = o["height"]
        if width <= 0.01 or height <= 0.01:
            continue
        centre = (max(min(s), 0.0) + min(max(s), length)) / 2
        entities.append(Entity(o["kind"], {"offset": round(centre, 6), "width": round(width, 6), "height": round(height, 6),
                                           "sill": round(max(0.0, min(zs) - w["z"]), 6)},
                               name=o["name"] or None, parent_id=e.id))
        placed += 1
    if entities:
        commands.append(AddEntities(entities))
    summary = {"storeys": len(data["storeys"]), "walls": len(data["walls"]), "openings": placed,
               "new_types": len(made), "not_imported": dict(data["not_imported"])}
    return CompositeCommand(commands, "Εισαγωγή IFC"), summary


def import_ifc(doc, stack, path):
    """Read ``path`` and add it to the project (one undo step).  Returns the summary."""
    command, summary = import_command(doc, read(path))
    stack.execute(command)
    return summary
