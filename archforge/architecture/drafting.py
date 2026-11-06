"""Ελεύθερη 2D σχεδίαση (CAD ▸ Σχεδίαση 2D): γραμμή, πολυγραμμή, ορθογώνιο / πολύγωνο, κύκλος, τόξο, κείμενο.

Ιδιοκτήτης 06/11 («προχώρα στα υπόλοιπα» της αποτύπωσης δυνατοτήτων): το μεγαλύτερο κενό ως CAD ήταν η ελεύθερη
σχεδίαση — λεπτομέρειες, σημειώσεις, βοηθητικές γραμμές. Ένα στοιχείο ``drafting`` ανά σχήμα, στον όροφο όπου
σχεδιάστηκε (``level_z``), μία αναίρεση ανά σχήμα, αποθηκεύεται με το έργο, βγαίνει στο DXF (layer A-DETL / A-ANNO-TEXT)
και στο PDF μαζί με την κάτοψη. Δεν είναι δομικό στοιχείο: δεν έχει 3D, ποσότητες ή IFC.

Παράμετροι: ``shape`` · ``points`` [[x, y], …] (γραμμή 2, πολυγραμμή ≥ 2, πολύγωνο ≥ 3) · ``cx, cy, r`` (κύκλος, τόξο)
· ``a0, a1`` μοίρες αριστερόστροφα από +x (τόξο) · ``text, x, y, height`` (ύψος γραμμάτων σε m), ``angle`` μοίρες ·
``style`` solid / dashed / dotted / dashdot · ``weight`` γραμμή σε mm (χαρτί) · ``hatch`` none / solid / diagonal /
cross (κλειστά σχήματα).
"""
from __future__ import annotations

import math

SHAPES = {"line": "Γραμμή", "polyline": "Πολυγραμμή", "polygon": "Πολύγωνο / ορθογώνιο", "circle": "Κύκλος",
          "arc": "Τόξο", "text": "Κείμενο"}
STYLES = {"solid": "Συνεχής", "dashed": "Διακεκομμένη", "dotted": "Στικτή", "dashdot": "Αξονική (παύλα-τελεία)"}
HATCHES = {"none": "Χωρίς", "solid": "Γέμισμα", "diagonal": "Διαγράμμιση", "cross": "Διασταυρούμενη"}
WEIGHTS = (0.13, 0.18, 0.25, 0.35, 0.5, 0.7)          # mm, ISO 128 pen widths (DESIGN_DEFAULT choice of the list)
DEFAULT_TEXT_HEIGHT = 0.25                           # m in the model = 2,5 mm at 1:100 (DESIGN_DEFAULT)
ARC_STEP_DEG = 5.0


def _finite(v, name):
    v = float(v)
    if not math.isfinite(v):
        raise ValueError(f"{name}: μη πεπερασμένη τιμή")
    return v


def validate(p):
    """Checked copy of a drafting entity's params (called by the model's schema)."""
    out = dict(p)
    shape = str(out.get("shape", ""))
    if shape not in SHAPES:
        raise ValueError(f"shape must be one of {', '.join(SHAPES)}")
    out["level_z"] = _finite(out.get("level_z", 0.0), "level_z")
    if shape in ("line", "polyline", "polygon"):
        pts = [(_finite(x, "x"), _finite(y, "y")) for x, y in out.get("points") or ()]
        need = {"line": 2, "polyline": 2, "polygon": 3}[shape]
        if len(pts) < need or (shape == "line" and len(pts) != 2):
            raise ValueError(f"{SHAPES[shape]}: χρειάζεται {'ακριβώς ' if shape == 'line' else 'τουλάχιστον '}{need} σημεία")
        if max(math.dist(pts[0], q) for q in pts[1:]) < 1e-6:
            raise ValueError(f"{SHAPES[shape]}: όλα τα σημεία συμπίπτουν")
        out["points"] = [list(q) for q in pts]
    elif shape in ("circle", "arc"):
        out["cx"], out["cy"] = _finite(out["cx"], "cx"), _finite(out["cy"], "cy")
        out["r"] = _finite(out["r"], "r")
        if out["r"] <= 0:
            raise ValueError("η ακτίνα πρέπει να είναι θετική")
        if shape == "arc":
            out["a0"], out["a1"] = _finite(out["a0"], "a0") % 360.0, _finite(out["a1"], "a1") % 360.0
            if abs(out["a0"] - out["a1"]) < 1e-6:
                raise ValueError("τόξο μηδενικής γωνίας")
    else:
        out["x"], out["y"] = _finite(out["x"], "x"), _finite(out["y"], "y")
        out["text"] = str(out.get("text", "")).strip()
        if not out["text"]:
            raise ValueError("κείμενο χωρίς γράμματα")
        out["height"] = _finite(out.get("height", DEFAULT_TEXT_HEIGHT), "height")
        if not 0.01 <= out["height"] <= 10:
            raise ValueError("ύψος γραμμάτων 1 cm … 10 m")
        out["angle"] = _finite(out.get("angle", 0.0), "angle") % 360.0
    style = str(out.get("style", "solid"))
    if style not in STYLES:
        raise ValueError(f"style must be one of {', '.join(STYLES)}")
    out["style"] = style
    out["weight"] = _finite(out.get("weight", 0.25), "weight")
    if not 0.05 <= out["weight"] <= 2.0:
        raise ValueError("πάχος γραμμής 0,05 … 2 mm")
    hatch = str(out.get("hatch", "none"))
    if hatch not in HATCHES:
        raise ValueError(f"hatch must be one of {', '.join(HATCHES)}")
    if hatch != "none" and shape not in ("polygon", "circle"):
        raise ValueError("γέμισμα μόνο σε κλειστά σχήματα (πολύγωνο, κύκλος)")
    out["hatch"] = hatch
    return out


def entity(shape, level_z=0.0, **params):
    """A new, validated ``drafting`` Entity."""
    from archforge.core.model import Entity
    p = validate({"shape": shape, "level_z": level_z, **params})
    return Entity("drafting", p, name=SHAPES[shape])


def rectangle(a, b, level_z=0.0, **params):
    """The polygon of the axis-aligned rectangle with opposite corners ``a`` and ``b``."""
    (x0, y0), (x1, y1) = a, b
    if abs(x1 - x0) < 1e-6 or abs(y1 - y0) < 1e-6:
        raise ValueError("ορθογώνιο μηδενικού εμβαδού")
    return entity("polygon", level_z, points=[(x0, y0), (x1, y0), (x1, y1), (x0, y1)], **params)


def arc_points(cx, cy, r, a0, a1, step=ARC_STEP_DEG):
    """Points of the arc from ``a0`` counter-clockwise to ``a1`` (degrees)."""
    sweep = (a1 - a0) % 360.0 or 360.0
    n = max(2, int(math.ceil(sweep / step)) + 1)
    return [(cx + r * math.cos(math.radians(a0 + sweep * i / (n - 1))),
             cy + r * math.sin(math.radians(a0 + sweep * i / (n - 1)))) for i in range(n)]


def arc_three_points(p0, p1, p2):
    """``(cx, cy, r, a0, a1)`` of the arc through ``p0`` → ``p1`` → ``p2`` (start, a point on it, end)."""
    (x1, y1), (x2, y2), (x3, y3) = p0, p1, p2
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-12:
        raise ValueError("τα τρία σημεία είναι στην ίδια ευθεία: δεν ορίζουν τόξο")
    ux = ((x1 * x1 + y1 * y1) * (y2 - y3) + (x2 * x2 + y2 * y2) * (y3 - y1) + (x3 * x3 + y3 * y3) * (y1 - y2)) / d
    uy = ((x1 * x1 + y1 * y1) * (x3 - x2) + (x2 * x2 + y2 * y2) * (x1 - x3) + (x3 * x3 + y3 * y3) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    ang = lambda x, y: math.degrees(math.atan2(y - uy, x - ux)) % 360.0
    a0, am, a1 = ang(x1, y1), ang(x2, y2), ang(x3, y3)
    if (am - a0) % 360.0 > (a1 - a0) % 360.0:         # the middle point is on the clockwise side: swap the ends
        a0, a1 = a1, a0
    return ux, uy, r, a0, a1


def outline(p):
    """The drawn points of a shape (closed shapes repeat nothing; ``closed`` says it)."""
    s = p["shape"]
    if s in ("line", "polyline", "polygon"):
        return [tuple(q) for q in p["points"]], s == "polygon"
    if s == "circle":
        return arc_points(p["cx"], p["cy"], p["r"], 0.0, 360.0)[:-1], True
    if s == "arc":
        return arc_points(p["cx"], p["cy"], p["r"], p["a0"], p["a1"]), False
    return [(p["x"], p["y"])], False


def length(p):
    """Drawn length (m) of a line shape; perimeter of a closed one; None for text."""
    s = p["shape"]
    if s == "text":
        return None
    if s == "circle":
        return 2 * math.pi * p["r"]
    if s == "arc":
        return math.radians((p["a1"] - p["a0"]) % 360.0 or 360.0) * p["r"]
    pts, closed = outline(p)
    total = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
    return total + (math.dist(pts[-1], pts[0]) if closed else 0.0)


def area(p):
    """Area (m²) of a closed shape, else None."""
    if p["shape"] == "circle":
        return math.pi * p["r"] ** 2
    if p["shape"] != "polygon":
        return None
    pts = p["points"]
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))) / 2


def translated(p, dx, dy):
    """The params moved by (dx, dy) — for the shared Move command."""
    q = dict(p)
    if "points" in q:
        q["points"] = [[x + dx, y + dy] for x, y in q["points"]]
    for kx, ky in (("cx", "cy"), ("x", "y")):
        if kx in q:
            q[kx], q[ky] = q[kx] + dx, q[ky] + dy
    return q


def primitives(e):
    """Plan primitives of one drafting entity: role ``drafting`` (lines, closed shapes with ``hatch`` meta) or
    ``drafting-text`` (a label with its height in metres and angle)."""
    from archforge.core.plan_scene import Primitive2D
    p = e.params
    meta = (("style", p.get("style", "solid")), ("weight", float(p.get("weight", 0.25))), ("hatch", p.get("hatch", "none")))
    s = p["shape"]
    if s == "text":
        return [Primitive2D("label", ((p["x"], p["y"]),), entity_id=e.id, role="drafting-text",
                            meta=(("text", p["text"]), ("height", float(p["height"])), ("angle", float(p.get("angle", 0.0))),
                                  ("align", (0.0, 1.0))))]
    if s == "circle":
        return [Primitive2D("ellipse", ((p["cx"], p["cy"]),), radius_x=p["r"], radius_y=p["r"], entity_id=e.id,
                            role="drafting", meta=meta)]
    pts, closed = outline(p)
    return [Primitive2D("polygon" if closed else ("line" if s == "line" else "polyline"), tuple(pts), entity_id=e.id,
                        role="drafting", meta=meta)]


def describe(p):
    """«Γραμμή 3,20 m», «Κύκλος r 0,50 m · 0,79 m²», «Κείμενο «ΣΗΜΕΙΩΣΗ»» — for the status bar and Properties."""
    s = p["shape"]
    num = lambda v: f"{v:.2f}".replace(".", ",")
    if s == "text":
        return f"Κείμενο «{p['text']}» · ύψος {num(p['height'])} m"
    if s == "circle":
        return f"Κύκλος r {num(p['r'])} m · {num(area(p))} m²"
    if s == "arc":
        return f"Τόξο r {num(p['r'])} m · μήκος {num(length(p))} m"
    a = area(p)
    return f"{SHAPES[s]} · μήκος {num(length(p))} m" + (f" · {num(a)} m²" if a is not None else "")
