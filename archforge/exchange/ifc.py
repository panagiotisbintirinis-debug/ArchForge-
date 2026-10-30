"""IFC4 export: the building as other engineers' programs read it (owner 30/10: «IFC … η εξαγωγή στοιχείων προς
άλλους μηχανικούς»).

Project → Site → Building → one IfcBuildingStorey per storey (elevation from the project levels).  Every built
element of the Document is written with the class of ``mapping.KINDS`` and its own body — the very mesh the 3D view
shows (``geometry.mesh``), as an ``IfcTriangulatedFaceSet`` in project coordinates, so curved walls, sculpt, roofs and
stairs leave as they are drawn.  On top of the body, the relations a BIM program needs:

* walls carry their axis (``Axis`` representation, the plan line) and their **layer set** (wall_types: material and thickness of each layer), ``Pset_WallCommon``
  (LoadBearing, IsExternal, an indicative U), and every door / window as an ``IfcOpeningElement`` voiding the wall
  (``IfcRelVoidsElement``) filled by an ``IfcDoor`` / ``IfcWindow`` (``IfcRelFillsElement``) with its sizes;
* rooms become ``IfcSpace`` (name, use, net floor area as the take-off measures it), extruded to the storey height;
* each element has the ``ArchForge`` property set (kind, id, name, wall type, phase) so it can come back.

Units: metre.  Origin: the project origin (0, 0, 0) of ArchForge.  Read-only for the Document.
"""
from __future__ import annotations

import datetime
import math

from archforge.exchange.mapping import storey_label, storey_of, storeys, target, SKIP

SCHEMA = "IFC4"


class _Writer:
    def __init__(self, doc, project_name):
        import ifcopenshell
        import ifcopenshell.api
        import ifcopenshell.guid
        self.api, self.guid = ifcopenshell.api, ifcopenshell.guid
        self.doc = doc
        self.f = ifcopenshell.file(schema=SCHEMA)
        f = self.f
        self.project = self.run("root.create_entity", ifc_class="IfcProject", name=project_name or "ArchForge")
        # Metres (the default of assign_unit is millimetres: the values written in metres read 1000× too small).
        self.run("unit.assign_unit", units=[self.run("unit.add_si_unit", unit_type=t)
                                            for t in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT", "PLANEANGLEUNIT")])
        model = self.run("context.add_context", context_type="Model")
        self.body = self.run("context.add_context", context_type="Model", context_identifier="Body",
                             target_view="MODEL_VIEW", parent=model)
        self.axis = self.run("context.add_context", context_type="Model", context_identifier="Axis",
                             target_view="GRAPH_VIEW", parent=model)
        self.site = self.run("root.create_entity", ifc_class="IfcSite", name="Οικόπεδο")
        self.building = self.run("root.create_entity", ifc_class="IfcBuilding", name=project_name or "Κτίριο")
        self.run("aggregate.assign_object", products=[self.site], relating_object=self.project)
        self.run("aggregate.assign_object", products=[self.building], relating_object=self.site)
        self.origin = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, 0.0)))
        self.placement = f.createIfcLocalPlacement(None, self.origin)
        for obj in (self.site, self.building):
            obj.ObjectPlacement = self.placement
        self.storeys = {}
        for name, z in storeys(doc):
            s = self.run("root.create_entity", ifc_class="IfcBuildingStorey", name=storey_label(name))
            s.Elevation = float(z); s.LongName = str(name); s.ObjectPlacement = self.placement
            self.run("aggregate.assign_object", products=[s], relating_object=self.building)
            self.storeys[name] = s
        self.contained = {name: [] for name in self.storeys}
        self.materials = {}
        self.counts = {}

    def run(self, usecase, **kw):
        return self.api.run(usecase, self.f, **kw)

    # ------------------------------------------------------------------ geometry
    def mesh_shape(self, vertices, triangles):
        f = self.f
        pts = f.createIfcCartesianPointList3D([tuple(float(c) for c in v) for v in vertices])
        faces = f.createIfcTriangulatedFaceSet(pts, None, True, [tuple(int(i) + 1 for i in t) for t in triangles])
        rep = f.createIfcShapeRepresentation(self.body, "Body", "Tessellation", [faces])
        return f.createIfcProductDefinitionShape(None, None, [rep])

    def prism_shape(self, polygon, z, height):
        f = self.f
        pts = [f.createIfcCartesianPoint((float(x), float(y))) for x, y in polygon]
        profile = f.createIfcArbitraryClosedProfileDef("AREA", None, f.createIfcPolyline(pts + [pts[0]]))
        where = f.createIfcAxis2Placement3D(f.createIfcCartesianPoint((0.0, 0.0, float(z))))
        solid = f.createIfcExtrudedAreaSolid(profile, where, f.createIfcDirection((0.0, 0.0, 1.0)), float(height))
        rep = f.createIfcShapeRepresentation(self.body, "Body", "SweptSolid", [solid])
        return f.createIfcProductDefinitionShape(None, None, [rep])

    def element(self, ifc_class, name, predefined=None, storey=None, shape=None):
        e = self.run("root.create_entity", ifc_class=ifc_class, name=name, predefined_type=predefined) if predefined \
            else self.run("root.create_entity", ifc_class=ifc_class, name=name)
        e.ObjectPlacement = self.placement
        if shape is not None:
            e.Representation = shape
        if storey is not None:
            self.contained[storey].append(e)
        self.counts[ifc_class] = self.counts.get(ifc_class, 0) + 1
        return e

    def pset(self, product, name, props):
        props = {k: v for k, v in props.items() if v is not None and v != ""}
        if props:
            pset = self.run("pset.add_pset", product=product, name=name)
            self.run("pset.edit_pset", pset=pset, properties=props)

    # ------------------------------------------------------------------ materials
    def layer_set(self, wall_type, thickness):
        from archforge.architecture.wall_types import label as type_label, layers
        key = (str(wall_type), round(float(thickness), 4))
        if key in self.materials:
            return self.materials[key]
        label = type_label(wall_type, self.doc)
        mset = self.run("material.add_material_set", name=f"{label} {thickness * 100:.0f} cm", set_type="IfcMaterialLayerSet")
        rows = layers(wall_type, self.doc) or [("Τοιχοποιία", float(thickness), None, None, None)]
        for row in rows:
            mat = self.material(str(row[0]))
            layer = self.run("material.add_layer", layer_set=mset, material=mat)
            layer.LayerThickness = float(row[1])
        self.materials[key] = mset
        return mset

    def material(self, name):
        key = ("m", name)
        if key not in self.materials:
            self.materials[key] = self.run("material.add_material", name=name)
        return self.materials[key]


def _bodies(doc):
    from archforge.geometry.mesh import TessellatedPreviewBackend
    out = {}
    for body in TessellatedPreviewBackend().evaluate(doc).bodies:
        if body.payload is not None and body.payload.vertices:
            out.setdefault(body.entity_id, body.payload)
    return out


def _openings(doc, wall):
    return [e for e in doc.entities.values() if e.kind in ("door", "window", "opening") and e.parent_id == wall.id]


def _opening_box(wall, opening, depth_extra=0.02, panel=None):
    """Plan-and-height box of an opening in its wall (vertices, triangles); ``panel`` = thickness of a door / window
    leaf in the middle of the wall instead of the full wall depth."""
    p, q = wall.params, opening.params
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = -uy, ux
    c, w = float(q.get("offset", L / 2)), float(q.get("width", 0.9))
    sill = float(q.get("sill", q.get("bottom", 0.0)) or 0.0)
    h = float(q.get("height", 2.1))
    t = (float(panel) if panel else float(p.get("thickness", 0.2)) + depth_extra) / 2
    z0 = float(p.get("z", 0.0)) + sill
    pts = []
    for s in (c - w / 2, c + w / 2):
        for o in (-t, t):
            pts.append((x1 + ux * s + nx * o, y1 + uy * s + ny * o))
    a, b, cc, d = pts[0], pts[2], pts[3], pts[1]                       # around the footprint
    ring = [a, b, cc, d]
    verts = [(x, y, z0) for x, y in ring] + [(x, y, z0 + h) for x, y in ring]
    tris = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7)]
    for i in range(4):
        j = (i + 1) % 4
        tris += [(i, j, 4 + j), (i, 4 + j, 4 + i)]
    return verts, tris, (w, h, sill)


def _exterior_ids(doc):
    """Ids of the walls with open space on one side (mep/ventilation.exterior_walls), every storey."""
    from archforge.mep.ventilation import exterior_walls
    out = set()
    for z in {round(float(e.params.get("z", 0.0)), 3) for e in doc.entities.values() if e.kind == "wall"}:
        try:
            out |= {w.id for w, _n in exterior_walls(doc, z)}
        except Exception:                                               # noqa: BLE001 — a property, never a stop
            pass
    return out


def export_ifc(doc, path, project_name="ArchForge"):
    """Write ``path`` (IFC4).  Returns a summary: counts per IFC class, storeys, spaces, what was left out."""
    w = _Writer(doc, project_name)
    bodies = _bodies(doc)
    from archforge.architecture.wall_types import indicative_u, label as type_label
    left_out = {}
    exterior = _exterior_ids(doc)
    for e in sorted(doc.entities.values(), key=lambda e: (e.kind, e.id)):
        if e.kind in SKIP:
            continue
        mesh = bodies.get(e.id)
        if mesh is None:
            left_out[e.kind] = left_out.get(e.kind, 0) + 1
            continue
        ifc_class, predefined, _layer, greek = target(e)
        zmin = min(v[2] for v in mesh.vertices)
        storey = storey_of(doc, zmin)[0]
        el = w.element(ifc_class, e.name or greek, predefined, storey, w.mesh_shape(mesh.vertices, mesh.triangles))
        el.Tag = e.id
        p = e.params
        w.pset(el, "ArchForge", {"Kind": e.kind, "Id": e.id, "Name": e.name or "", "Phase": p.get("phase"),
                                  "WallType": p.get("wall_type"), "CurveId": (p.get("curve") or {}).get("id")
                                  if isinstance(p.get("curve"), dict) else None})
        if e.kind == "wall":
            # The wall's axis as BIM programs read it (and as ifc_import takes it back): the plan line, at the base.
            axis = w.run("geometry.add_axis_representation", context=w.axis,
                         axis=((float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))))
            el.Representation.Representations = (axis,) + tuple(el.Representation.Representations)
            wall_type = p.get("wall_type", "generic")
            w.run("material.assign_material", products=[el], material=w.layer_set(wall_type, float(p["thickness"])))
            u = indicative_u(wall_type, doc)
            w.pset(el, "Pset_WallCommon", {"LoadBearing": bool(p.get("load_bearing", False)),
                                            "IsExternal": e.id in exterior,
                                            "ThermalTransmittance": round(u, 3) if u else None,
                                            "Reference": type_label(wall_type, doc)})
            for o in _openings(doc, e):
                verts, tris, (ow, oh, sill) = _opening_box(e, o)
                hole = w.element("IfcOpeningElement", f"Άνοιγμα {o.name or ''}".strip(), "OPENING", None,
                                 w.mesh_shape(verts, tris))
                w.run("feature.add_feature", feature=hole, element=el)
                if o.kind == "opening":
                    continue
                kind = "IfcDoor" if o.kind == "door" else "IfcWindow"
                pv, pt, _s = _opening_box(e, o, panel=0.06)
                leaf = w.element(kind, o.name or ("Πόρτα" if o.kind == "door" else "Παράθυρο"),
                                 "DOOR" if o.kind == "door" else "WINDOW", storey, w.mesh_shape(pv, pt))
                leaf.OverallWidth, leaf.OverallHeight, leaf.Tag = float(ow), float(oh), o.id
                w.run("feature.add_filling", opening=hole, element=leaf)
                w.pset(leaf, "ArchForge", {"Kind": o.kind, "Id": o.id, "Sill": round(sill, 3), "HostWall": e.id})
        if e.kind in ("structural_column", "structural_beam"):
            w.pset(el, "Pset_ColumnCommon" if e.kind == "structural_column" else "Pset_BeamCommon",
                   {"LoadBearing": True, "Reference": p.get("construction")})
    spaces = _spaces(doc, w)
    for name, products in w.contained.items():
        if products:
            w.run("spatial.assign_container", products=products, relating_structure=w.storeys[name])
    w.f.write(str(path))
    return {"file": str(path), "schema": SCHEMA, "storeys": [storey_label(n) for n, _z in storeys(doc)],
            "counts": dict(sorted(w.counts.items())), "spaces": spaces, "left_out": left_out,
            "date": datetime.date.today().isoformat()}


def _spaces(doc, w):
    """Rooms as IfcSpace on their storey: name, use, net area (as the take-off), up to the next storey or 2,70 m."""
    from archforge.quantities.takeoff import _area, net_polygon
    levels = storeys(doc)
    out = []
    for i, (name, z) in enumerate(levels):
        height = (levels[i + 1][1] - z) if i + 1 < len(levels) else 2.7
        for index, face in enumerate(doc.active_room_faces(z=z), start=1):
            data = doc.room_metadata(face.signature)
            label = data.get("name") or f"Χώρος {index}"
            try:
                net = net_polygon(doc, face.polygon, z)
            except Exception:                                           # noqa: BLE001
                net = [tuple(q) for q in face.polygon]
            area = abs(_area(net))
            sp = w.element("IfcSpace", label, "INTERNAL", None, w.prism_shape(net, z, height))
            sp.LongName = data.get("use") or label
            w.run("aggregate.assign_object", products=[sp], relating_object=w.storeys[name])
            qto = w.run("pset.add_qto", product=sp, name="Qto_SpaceBaseQuantities")
            w.run("pset.edit_qto", qto=qto, properties={"NetFloorArea": round(area, 2), "Height": round(height, 2)})
            w.pset(sp, "ArchForge", {"Signature": face.signature, "Use": data.get("use")})
            out.append({"storey": storey_label(name), "name": label, "area_m2": round(area, 2)})
    return out
