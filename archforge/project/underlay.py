"""The engineer's drawing as an underlay (PDF page or DXF lines) under the plan of one storey.

Owner 15/10: «ο ηλεκτρολόγος ζητάει από τον μηχανικό το σχέδιο και εφαρμόζει το ArchForge».
An ``underlay`` entity is a picture to draw on, never design geometry: it is
saved with the project, belongs to a storey (``z``), never takes the clicks
meant for the drawing (it is chosen from the project tree) and has its own opacity.

Placement: a drawing point (u, v) in drawing units maps to the model as
``(x, y) + R(rotation) · m_per_unit · (u − u0, v − v0)``.

* **PDF**: drawing units are PDF points (1/72 inch, ISO 32000-1 §8.3.2.3
  "default user space"); with the scale the user reads on the title block
  (1:N) one point is ``25.4/72 mm × N``.  The page is rendered by QtPdf.
* **DXF** (ASCII): LINE, LWPOLYLINE, POLYLINE/VERTEX, ARC, CIRCLE are kept as
  segments (arcs as short chords; polyline bulges drawn straight).  The unit
  of the drawing is chosen by the user, who sees the overall size it gives.

Either way **calibration** (two clicks on a known dimension + the real
distance) sets the scale exactly; it is the recommended check.
"""
from __future__ import annotations

import math

PDF_POINT_MM = 25.4 / 72.0            # ISO 32000-1: default user space unit = 1/72 inch
DXF_UNITS = {"mm": 0.001, "cm": 0.01, "m": 1.0}
ARC_SEGMENTS = 24


# ---------------------------------------------------------------------------------------------------- DXF lines

def _pairs(text):
    lines = str(text).splitlines()
    for i in range(0, len(lines) - 1, 2):
        try:
            yield int(lines[i].strip()), lines[i + 1].strip()
        except ValueError:
            continue


def _arc(cx, cy, r, a0, a1):
    if a1 <= a0:
        a1 += 360.0
    n = max(2, int(math.ceil((a1 - a0) / 360.0 * ARC_SEGMENTS)))
    pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * k / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * k / n)))
           for k in range(n + 1)]
    return [(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]


def parse_dxf_segments(text):
    """``{"segments": [(x1, y1, x2, y2)], "layers": {name: count}}`` from an ASCII DXF (ENTITIES section)."""
    segs, layers = [], {}
    section, entity, data = None, None, {}
    poly, poly_closed, poly_layer = None, False, ""

    def add(seg_list, layer):
        if seg_list:
            segs.extend(seg_list)
            layers[layer] = layers.get(layer, 0) + len(seg_list)

    def chain(pts, closed):
        out = [(a[0], a[1], b[0], b[1]) for a, b in zip(pts, pts[1:])]
        if closed and len(pts) > 2:
            out.append((pts[-1][0], pts[-1][1], pts[0][0], pts[0][1]))
        return [s for s in out if (s[0], s[1]) != (s[2], s[3])]

    def flush():
        nonlocal poly
        layer = data.get(8, "0")
        if entity == "LINE" and 10 in data and 11 in data:
            add([(data[10], data.get(20, 0.0), data[11], data.get(21, 0.0))], layer)
        elif entity == "LWPOLYLINE" and data.get("_xy"):
            add(chain([tuple(p) for p in data["_xy"]], bool(int(data.get(70, 0)) & 1)), layer)
        elif entity == "ARC" and 10 in data and 40 in data:
            add(_arc(data[10], data.get(20, 0.0), data[40], data.get(50, 0.0), data.get(51, 360.0)), layer)
        elif entity == "CIRCLE" and 10 in data and 40 in data:
            add(_arc(data[10], data.get(20, 0.0), data[40], 0.0, 360.0), layer)
        elif entity == "VERTEX" and poly is not None and 10 in data:
            poly.append((data[10], data.get(20, 0.0)))

    for code, value in _pairs(text):
        if code == 0:
            if entity is not None and section == "ENTITIES":
                flush()
            if value == "SECTION":
                section, entity, data = "pending", None, {}
                continue
            if value == "ENDSEC":
                section, entity, data = None, None, {}
                continue
            if section == "ENTITIES" and value == "POLYLINE":
                poly, poly_closed, poly_layer = [], False, ""
            if section == "ENTITIES" and value == "SEQEND" and poly is not None:
                add(chain(poly, poly_closed), poly_layer or "0")
                poly = None
            entity, data = value, {}
            continue
        if section == "pending" and code == 2:
            section = value
            continue
        if section != "ENTITIES" or entity is None:
            continue
        if code == 8:
            data[8] = value
            if entity == "POLYLINE":
                poly_layer = value
        elif code in (10, 20, 11, 21, 40, 50, 51, 70):
            try:
                v = float(value)
            except ValueError:
                continue
            if entity == "LWPOLYLINE" and code in (10, 20):
                xy = data.setdefault("_xy", [])
                if code == 10:
                    xy.append([v, 0.0])
                elif xy:
                    xy[-1][1] = v
            else:
                data[code] = v
                if entity == "POLYLINE" and code == 70:
                    poly_closed = bool(int(v) & 1)
    return {"segments": segs, "layers": layers}


def bounds(segments):
    xs = [c for s in segments for c in (s[0], s[2])]
    ys = [c for s in segments for c in (s[1], s[3])]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)


def dxf_params(path, text, unit, z=0.0):
    """Underlay params for a DXF: its lower-left corner at the model origin, ``unit`` in DXF_UNITS."""
    found = parse_dxf_segments(text)
    if not found["segments"]:
        raise ValueError("Το DXF δεν έχει γραμμές (LINE/POLYLINE/ARC/CIRCLE) στο ENTITIES· αποθηκεύστε ως ASCII DXF")
    x0, y0, _x1, _y1 = bounds(found["segments"])
    return {"source": "dxf", "path": str(path), "page": 0, "x": 0.0, "y": 0.0, "z": float(z), "u0": x0, "v0": y0,
            "m_per_unit": DXF_UNITS[unit], "rotation": 0.0, "opacity": 0.6, "unit": unit,
            "segments": [[round(c, 6) for c in s] for s in found["segments"]]}


def dxf_size_m(text, unit):
    """Overall width × height (m) the DXF gets with ``unit`` — shown to the user to choose the unit."""
    x0, y0, x1, y1 = bounds(parse_dxf_segments(text)["segments"])
    k = DXF_UNITS[unit]
    return (x1 - x0) * k, (y1 - y0) * k


def pdf_params(path, page, scale_denominator, page_size_pt, z=0.0):
    """Underlay params for one PDF page drawn at 1:``scale_denominator``; page lower-left at the model origin."""
    w, h = page_size_pt
    return {"source": "pdf", "path": str(path), "page": int(page), "x": 0.0, "y": 0.0, "z": float(z), "u0": 0.0, "v0": 0.0,
            "m_per_unit": PDF_POINT_MM / 1000.0 * float(scale_denominator), "rotation": 0.0, "opacity": 0.6,
            "page_w": float(w), "page_h": float(h), "scale_denominator": float(scale_denominator)}


# ------------------------------------------------------------------------------------------------- placement

def to_model(params, u, v):
    s, r = float(params["m_per_unit"]), math.radians(float(params.get("rotation", 0.0)))
    du, dv = (u - float(params.get("u0", 0.0))) * s, (v - float(params.get("v0", 0.0))) * s
    return (float(params["x"]) + du * math.cos(r) - dv * math.sin(r), float(params["y"]) + du * math.sin(r) + dv * math.cos(r))


def calibrated(params, a, b, real_m):
    """Params after calibration: the distance a–b (model, as clicked) becomes ``real_m``; point a stays put."""
    measured = math.dist(a, b)
    if measured < 1e-9 or real_m <= 0:
        raise ValueError("Δύο διαφορετικά σημεία και πραγματική απόσταση > 0")
    k = real_m / measured
    ax, ay = a
    return {"m_per_unit": float(params["m_per_unit"]) * k,
            "x": ax + (float(params["x"]) - ax) * k, "y": ay + (float(params["y"]) - ay) * k}


def model_segments(params):
    """DXF underlay segments in model coordinates."""
    out = []
    for x1, y1, x2, y2 in params.get("segments", ()):
        out.append((*to_model(params, x1, y1), *to_model(params, x2, y2)))
    return out


def underlays(doc, z=None):
    out = [e for e in doc.entities.values() if e.kind == "underlay"]
    if z is not None:
        out = [e for e in out if abs(float(e.params.get("z", 0.0)) - float(z)) < 1e-3]
    return out
