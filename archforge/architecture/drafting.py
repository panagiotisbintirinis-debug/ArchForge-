"""Simple CAD drafting and notes in the plan (owner: «εργαλεία CAD απλά και μαζί εργαλείο σημειώσεων»).

Plain 2D drawing on a storey, outside the building model: it is drawn in the plan, printed in the PDF and written
to the DXF (``exchange/mapping.PLAN_LAYERS``), never built in 3D or counted in quantities.

* ``cad_line``   — a line or polyline: ``points`` [[x, y], …] (≥ 2), ``closed`` (rectangle / polygon);
* ``cad_circle`` — centre ``cx, cy`` and radius ``r``;
* ``cad_arc``    — centre, radius and the angles ``a0 → a1`` (degrees, counter-clockwise), from 3 clicks;
* ``note``       — a text at ``x, y``; ``size`` = text height in metres for the drawings; an optional arrow to
  ``leader_x, leader_y``.

Every one carries ``level_z`` (the storey it belongs to, as dimensions do) and ``line_style``
(``solid`` / ``dashed`` / ``dotted``).  One entity = one undo, saved with the project like any other.
"""
from __future__ import annotations

import math

KINDS = ("cad_line", "cad_circle", "cad_arc", "note")
LINE_STYLES = ("solid", "dashed", "dotted")
ARC_STEP_DEG = 6.0                  # arcs and circles are drawn as polylines of ≤ 6° segments
NAMES = {"cad_line": "Γραμμή", "cad_circle": "Κύκλος", "cad_arc": "Τόξο", "note": "Σημείωση"}


# ------------------------------------------------------------------ validation (core/model.SCHEMAS)
def points2(v):
    if not isinstance(v, (list, tuple)) or len(v) < 2:
        raise ValueError("a drafting line needs at least two points")
    out = []
    for p in v:
        if not isinstance(p, (list, tuple)) or len(p) != 2:
            raise ValueError("each point must be [x, y]")
        x, y = float(p[0]), float(p[1])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError("point must be finite")
        out.append([x, y])
    if all(math.dist(out[0], q) < 1e-6 for q in out[1:]):
        raise ValueError("the points of a line must not all coincide")
    return out


def note_text(v):
    v = str(v).strip()
    if not v:
        raise ValueError("a note needs some text")
    return v[:2000]


# ------------------------------------------------------------------ entities
def _entity(kind, params, z):
    from archforge.core.model import Entity
    params = dict(params, level_z=float(z))
    params.setdefault("line_style", "solid")
    return Entity(kind, params, name=NAMES[kind])


def line_entity(points, z, closed=False, style="solid"):
    return _entity("cad_line", {"points": [list(map(float, p)) for p in points], "closed": int(bool(closed)),
                                "line_style": style}, z)


def rectangle_entity(a, b, z, style="solid"):
    (x0, y0), (x1, y1) = a, b
    if abs(x1 - x0) < 1e-6 or abs(y1 - y0) < 1e-6:
        raise ValueError("το ορθογώνιο χρειάζεται πλάτος και ύψος")
    return line_entity([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z, closed=True, style=style)


def circle_entity(centre, through, z, style="solid"):
    r = math.dist(centre, through)
    if r < 1e-4:
        raise ValueError("ο κύκλος χρειάζεται ακτίνα")
    return _entity("cad_circle", {"cx": float(centre[0]), "cy": float(centre[1]), "r": r, "line_style": style}, z)


def arc_through(a, m, b):
    """(cx, cy, r, a0, a1) of the arc from ``a`` through ``m`` to ``b`` (degrees, counter-clockwise a0 → a1)."""
    ax, ay = a; mx, my = m; bx, by = b
    d = 2 * (ax * (my - by) + mx * (by - ay) + bx * (ay - my))
    if abs(d) < 1e-9:
        raise ValueError("τα τρία σημεία του τόξου είναι στην ίδια ευθεία")
    sa, sm, sb = ax * ax + ay * ay, mx * mx + my * my, bx * bx + by * by
    cx = (sa * (my - by) + sm * (by - ay) + sb * (ay - my)) / d
    cy = (sa * (bx - mx) + sm * (ax - bx) + sb * (mx - ax)) / d
    r = math.hypot(ax - cx, ay - cy)
    ang = [math.degrees(math.atan2(y - cy, x - cx)) % 360 for x, y in (a, m, b)]
    a0, am, a1 = ang
    ccw = (am - a0) % 360 <= (a1 - a0) % 360           # going counter-clockwise from a, m comes before b
    if not ccw:
        a0, a1 = a1, a0
    return cx, cy, r, a0, a1


def arc_entity(a, m, b, z, style="solid"):
    cx, cy, r, a0, a1 = arc_through(a, m, b)
    return _entity("cad_arc", {"cx": cx, "cy": cy, "r": r, "a0": a0, "a1": a1, "line_style": style}, z)


def note_entity(at, text, z, size=0.25, leader=None):
    params = {"x": float(at[0]), "y": float(at[1]), "text": text, "size": float(size)}
    if leader is not None:
        params.update(leader_x=float(leader[0]), leader_y=float(leader[1]))
    return _entity("note", params, z)


# ------------------------------------------------------------------ drawing
def arc_points(cx, cy, r, a0, a1):
    span = (a1 - a0) % 360 or 360.0
    n = max(2, int(math.ceil(span / ARC_STEP_DEG)))
    return tuple((cx + r * math.cos(math.radians(a0 + span * k / n)), cy + r * math.sin(math.radians(a0 + span * k / n)))
                 for k in range(n + 1))


def outline(entity):
    """The polyline a drafting entity draws as (closed shapes repeat their first point); () for a note."""
    p = entity.params
    if entity.kind == "cad_line":
        pts = tuple((float(x), float(y)) for x, y in p["points"])
        return pts + (pts[0],) if int(p.get("closed", 0)) and len(pts) > 2 else pts
    if entity.kind == "cad_circle":
        return arc_points(float(p["cx"]), float(p["cy"]), float(p["r"]), 0.0, 360.0)
    if entity.kind == "cad_arc":
        return arc_points(float(p["cx"]), float(p["cy"]), float(p["r"]), float(p["a0"]), float(p["a1"]))
    return ()


def leader(entity):
    """(tip, base) of a note's arrow, or None."""
    p = entity.params
    if entity.kind != "note" or "leader_x" not in p:
        return None
    return (float(p["leader_x"]), float(p["leader_y"])), (float(p["x"]), float(p["y"]))


def snap_points(entity):
    """Points of a drawing a new click can snap to: ends and corners, centres, arc ends, note anchors."""
    p = entity.params
    if entity.kind == "cad_line":
        return [tuple(map(float, q)) for q in p["points"]]
    if entity.kind == "cad_circle":
        return [(float(p["cx"]), float(p["cy"]))]
    if entity.kind == "cad_arc":
        pts = outline(entity)
        return [(float(p["cx"]), float(p["cy"])), pts[0], pts[-1]]
    if entity.kind == "note":
        return [(float(p["x"]), float(p["y"]))]
    return []


def plan_primitives(doc, f):
    """Drafting and notes of the active storey into the plan frame (core/plan_scene.build_plan_frame)."""
    from archforge.core.plan_scene import Primitive2D
    z = float(doc.work_plane.origin[2])
    for e in doc.entities.values():
        if e.kind not in KINDS or not e.visible or abs(float(e.params.get("level_z", 0.0)) - z) > 1e-5:
            continue
        style = (("line_style", str(e.params.get("line_style", "solid"))),)
        if e.kind == "note":
            tip_base = leader(e)
            if tip_base is not None:
                (tx, ty), (bx, by) = tip_base
                f.primitives.append(Primitive2D("polyline", ((bx, by), (tx, ty)), entity_id=e.id, role="note-leader"))
                ang = math.atan2(by - ty, bx - tx)
                head = 0.12
                for s in (-0.4, 0.4):
                    f.primitives.append(Primitive2D("polyline", ((tx, ty), (tx + head * math.cos(ang + s),
                                                                          ty + head * math.sin(ang + s))),
                                                    entity_id=e.id, role="note-leader"))
            f.primitives.append(Primitive2D("label", ((float(e.params["x"]), float(e.params["y"])),), entity_id=e.id,
                                            role="note", meta=(("text", str(e.params["text"])), ("align", (0.0, 1.0)),
                                                               ("size", float(e.params.get("size", 0.25))))))
            continue
        f.primitives.append(Primitive2D("polyline", outline(e), entity_id=e.id, role="cad-line", meta=style))
