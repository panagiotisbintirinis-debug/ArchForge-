"""DXF export: the plan of each storey, line for line as ArchForge draws it, in layers a CAD office recognises.

The same 2D primitives the plan view paints (``core/plan_scene.build_plan_frame``) — walls (filled), openings with
their swings, dimensions, room names with areas, columns, beams, stairs, furniture, MEP symbols — are written per
storey to one DXF file each («<όνομα> - Ισόγειο.dxf»), in metres (``$INSUNITS`` = 6), at the project coordinates, so
an engineer can overlay them on his own drawings.  Layers from ``mapping.PLAN_LAYERS`` (A-WALL, A-DOOR, S-COLS …);
cameras, underlays and editing handles are left out.  Read-only for the Document.
"""
from __future__ import annotations

import os

from archforge.exchange.mapping import plan_layer, storey_label, storeys

TEXT_HEIGHT = {"A-AREA-IDEN": 0.18, "A-ANNO-DIMS": 0.12}
COLORS = {"A-WALL": 7, "A-WALL-CNTR": 8, "A-DOOR": 3, "A-GLAZ": 4, "A-ANNO-DIMS": 1, "A-AREA-IDEN": 2, "A-AREA": 9,
          "S-COLS": 5, "S-BEAM": 5, "S-FRAM": 5, "A-FLOR-STRS": 6, "A-FURN": 8, "E-POWR": 30, "E-LITE": 40,
          "P-FIXT": 150, "M-HOTW": 10}


def _storey_doc(doc, name, z):
    """A copy of the Document looking at storey ``name`` (the plan draws the work plane's storey)."""
    from archforge.core.model import Document, WorkPlane
    copy = Document.from_dict(doc.to_dict())
    wp = copy.work_plane
    copy.work_plane = WorkPlane(name=str(name), origin=(float(wp.origin[0]), float(wp.origin[1]), float(z)),
                                u=tuple(wp.u), v=tuple(wp.v))
    copy.selection = []
    return copy


def _layer(dxf, name):
    if name not in dxf.layers:
        dxf.layers.add(name, color=COLORS.get(name, 7))
    return name


def write_storey(doc, name, z, path):
    """One storey's plan to ``path``; returns ``{layer: entities written}``."""
    import ezdxf
    from ezdxf import units
    from archforge.core.plan_scene import build_plan_frame
    dxf = ezdxf.new("R2010", setup=True)
    dxf.units = units.M
    dxf.header["$INSUNITS"] = 6
    dxf.header["$MEASUREMENT"] = 1
    msp = dxf.modelspace()
    counts = {}
    frame = build_plan_frame(_storey_doc(doc, name, z))
    for p in frame.primitives:
        layer = plan_layer(p.role)
        if layer is None:
            continue
        attrs = {"layer": _layer(dxf, layer)}
        pts = [(float(a), float(b)) for a, b in p.points]
        meta = dict(p.meta)
        if p.kind == "line" and len(pts) >= 2:
            msp.add_line(pts[0], pts[1], dxfattribs=attrs)
        elif p.kind in ("polyline", "polygon") and len(pts) >= 2:
            closed = p.kind == "polygon"
            msp.add_lwpolyline(pts, close=closed, dxfattribs=attrs)
            if closed and layer in ("A-WALL", "S-COLS") and len(pts) >= 3:
                hatch = msp.add_hatch(color=COLORS.get(layer, 7), dxfattribs={"layer": layer})
                islands = meta.get("islands")
                if islands:
                    for outer, holes in islands:
                        hatch.paths.add_polyline_path([tuple(q) for q in outer], is_closed=True)
                        for h in holes:
                            hatch.paths.add_polyline_path([tuple(q) for q in h], is_closed=True)
                else:
                    hatch.paths.add_polyline_path(pts, is_closed=True)
        elif p.kind == "ellipse" and pts:
            rx, ry = float(p.radius_x), float(p.radius_y)
            if abs(rx - ry) < 1e-9:
                msp.add_circle(pts[0], rx, dxfattribs=attrs)
            elif rx > 0 and ry > 0:
                import math
                a = math.radians(float(p.rotation))
                major = (rx * math.cos(a), rx * math.sin(a)) if rx >= ry else (-ry * math.sin(a), ry * math.cos(a))
                msp.add_ellipse(pts[0], major_axis=major, ratio=min(rx, ry) / max(rx, ry), dxfattribs=attrs)
        elif p.kind == "label" and pts:
            text = str(meta.get("text", "")).strip()
            if not text:
                continue
            h = TEXT_HEIGHT.get(layer, 0.12)
            m = msp.add_mtext(text.replace("\n", "\\P"), dxfattribs={**attrs, "char_height": h,
                                                                       "rotation": float(meta.get("angle", 0.0) or 0.0)})
            m.set_location(pts[0], attachment_point=5)                 # middle centre, as the plan places it
        else:
            continue
        counts[layer] = counts.get(layer, 0) + 1
    dxf.saveas(path)
    return counts


def export_dxf(doc, path, project_name="ArchForge"):
    """One DXF per storey next to ``path`` («<path stem> - <storey>.dxf»); a single storey keeps ``path``.
    Returns ``{"files": [...], "storeys": {label: {layer: n}}}``."""
    stem, ext = os.path.splitext(str(path))
    ext = ext or ".dxf"
    levels = storeys(doc)
    files, report = [], {}
    for name, z in levels:
        label = storey_label(name)
        out = f"{stem}{ext}" if len(levels) == 1 else f"{stem} - {label}{ext}"
        report[label] = write_storey(doc, name, z, out)
        files.append(out)
    return {"files": files, "storeys": report}
