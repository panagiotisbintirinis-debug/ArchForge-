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

**Section underlay** (owner 21/10, «NEW VILLA SECTION» 1:50): the same entity with
``section_id`` = a ``section_line``.  Then (x, y) are the section's (u, z) — distance
along the cut line and height — and it is drawn only in that section's tab, never in the
plan.  Placed with two clicks (a point of the drawing → where it belongs, e.g. its ±0,00
on ArchForge's ±0,00), calibrated like the plan one.
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


def for_section(params, section_id):
    """``params`` (from dxf_params / pdf_params) as the underlay of section ``section_id``: lower-left at u = 0, z = 0."""
    out = dict(params)
    out.update(section_id=str(section_id), x=0.0, y=0.0, z=0.0)
    return out


def moved(params, a, b):
    """Params after placing: the drawing point clicked at ``a`` goes to ``b`` (translation only)."""
    return {"x": float(params["x"]) + b[0] - a[0], "y": float(params["y"]) + b[1] - a[1]}


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
    """Plan underlays (of the storey at ``z``); section underlays are left out."""
    out = [e for e in doc.entities.values() if e.kind == "underlay" and not e.params.get("section_id")]
    if z is not None:
        out = [e for e in out if abs(float(e.params.get("z", 0.0)) - float(z)) < 1e-3]
    return out


def section_underlays(doc, section_id):
    return [e for e in doc.entities.values() if e.kind == "underlay" and e.params.get("section_id") == section_id]


# ------------------------------------------------------------------------------------------- lines of a PDF page

DARK = 0.15                          # «black pen»: every colour channel at most this (0 = black)


def _dark(colour):
    """Near-black in the PDF colour spaces pdfplumber reports: gray (1), RGB (3), CMYK (4)."""
    if colour is None:
        return False
    c = [float(v) for v in (colour if isinstance(colour, (list, tuple)) else (colour,))]
    if len(c) == 4:
        return c[3] >= 1.0 - DARK or all(v >= 1.0 - DARK for v in c[:3])
    return bool(c) and max(c) <= DARK


def pdf_vector_segments(path, page=0, dark_only=False):
    """The straight lines drawn on a PDF page, in PDF points with y up (the underlay's drawing units).

    A PDF exported from CAD keeps its lines (paths); a scanned one has only a picture → empty list.
    Lines, rectangle edges and the straight pieces of paths are read (pdfplumber); curves become chords.

    The frame is the page *as shown* — the one QtPdf renders for the picture: origin at the lower-left of
    the visible area (CropBox, ISO 32000-1 §14.11.2), page rotation applied.  CAD exports often crop a
    large sheet (the owner's villa drawings: 1200 × 600 mm sheets, 1872 × 1656 pt visible); measured from
    the MediaBox the lines came out shifted from the picture.  Lines wholly outside the visible area are
    not drawn on screen and are left out.  pdfplumber already reports the rotated page with ``top``
    measured down from its top edge, and its ``cropbox`` as (x0, top, x1, bottom) in that frame.

    ``dark_only``: only lines drawn — or areas filled — in near-black.  Architectural CAD draws walls with
    the dark pens; hatching, terrain, trees, furniture fills and red mark-ups are coloured or grey (the
    owner's NEW VILLA PLAN: 57 240 lines → 27 085 dark, the false «walls» on the road, trees and pool gone)."""
    import pdfplumber
    out = []
    with pdfplumber.open(str(path)) as pdf:
        p = pdf.pages[int(page)]
        cx0, ct, cx1, cb = (float(v) for v in p.cropbox)

        def add(pts, obj):
            if dark_only and not ((obj.get("stroke") and _dark(obj.get("stroking_color"))) or
                                  (obj.get("fill") and _dark(obj.get("non_stroking_color")))):
                return
            for (x1, t1), (x2, t2) in zip(pts, pts[1:]):
                if abs(x2 - x1) + abs(t2 - t1) <= 1e-6:
                    continue
                if max(x1, x2) < cx0 or min(x1, x2) > cx1 or max(t1, t2) < ct or min(t1, t2) > cb:
                    continue                                          # outside the visible area
                out.append((float(x1) - cx0, cb - float(t1), float(x2) - cx0, cb - float(t2)))
        for ln in p.lines:
            add(ln.get("pts") or [(ln["x0"], ln["top"]), (ln["x1"], ln["bottom"])], ln)
        for r in p.rects:
            x0, x1, t0, t1 = r["x0"], r["x1"], r["top"], r["bottom"]
            add([(x0, t0), (x1, t0), (x1, t1), (x0, t1), (x0, t0)], r)
        for c in p.curves:
            add(c.get("pts") or [], c)
    return out


def underlay_model_segments(params, dark_only=False):
    """Lines of any underlay in model coordinates (DXF: kept in the project; PDF: read from its file)."""
    if params.get("source") == "pdf":
        return [(*to_model(params, x1, y1), *to_model(params, x2, y2))
                for x1, y1, x2, y2 in pdf_vector_segments(params["path"], params.get("page", 0), dark_only)]
    return model_segments(params)
