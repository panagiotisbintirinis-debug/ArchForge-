"""Dragging a cabinet or a fixture: it clicks onto the wall behind it and onto its neighbour.

The back (local +Y) slides onto the face of a parallel wall within reach;
then a side onto a wall across the run or onto the next cabinet / fixture
with the same rotation and its back on the same line.  A WC keeps its axis
40 cm from the side wall or the next fixture (proposed value, see
``bath_layout``); everything else touches.  Rotation never changes: only
the translation is corrected, so the move stays one ``MoveEntities``.
"""
from __future__ import annotations

import math

REACH = 0.20          # how far the back / a side is pulled
SNAP_CATEGORIES = ("Μπάνιο", "Συσκευές")


def snappable(doc, e):
    """Cabinets and bathroom / kitchen fixtures standing on the floor (not a hob or a hood above it)."""
    if e.kind == "cabinet":
        return True
    if e.kind != "library_object":
        return False
    role = e.params.get("layout_role")
    if role in ("hob", "hood"):
        return False
    if role:
        return True
    from archforge.library.assets import load_asset
    asset = load_asset(str(e.params.get("asset", "")))
    return bool(asset) and any(c in SNAP_CATEGORIES for c in asset.get("category", []))


def side_gap(e):
    """Free space beside a fixture: a WC keeps its axis 40 cm from what is next to it."""
    if e.params.get("layout_role") == "wc" or "Λεκάνη" in (e.name or ""):
        return max(0.0, 0.40 - float(e.params["width"]) / 2)
    return 0.0


def _wall_faces(doc, level, rotation):
    """Wall faces ``(point, direction, outward normal, length)`` on the storey."""
    out = []
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - level) > 0.05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-6:
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        t = float(p.get("thickness", 0.2)) / 2
        for sgn in (1.0, -1.0):
            nx, ny = -uy * sgn, ux * sgn
            out.append(((x1 + nx * t, y1 + ny * t), (ux, uy), (nx, ny), L))
    return out


def snap_correction(doc, eid, params, ignore=(), entity=None):
    """``(dx, dy, kind)`` that makes the moved piece touch the wall / its neighbour, or None.

    ``entity``: a piece not in the Document yet (dragged from the Library).
    """
    e = entity if entity is not None else doc.get(eid)
    if not snappable(doc, e):
        return None
    x, y = float(params["x"]), float(params["y"])
    w, d = float(params["width"]), float(params["depth"])
    rot = math.radians(float(params.get("rotation", 0.0)))
    ux, uy = math.cos(rot), math.sin(rot)          # along the run (local +X)
    bx, by = -uy, ux                                # towards the back (local +Y)
    level = float(doc.work_plane.origin[2])
    faces = _wall_faces(doc, level, rot)
    cx = cy = 0.0
    kind = None
    # 1. Back on a parallel wall face that faces the piece.
    best = None
    for (fx, fy), (fux, fuy), (nx, ny), L in faces:
        if nx * bx + ny * by > -0.999:
            continue                                 # not a face looking at the back
        gap = (fx - (x + bx * d / 2)) * nx + (fy - (y + by * d / 2)) * ny   # >0: the back is behind the face
        along = (x - fx) * fux + (y - fy) * fuy
        if along + w / 2 < 0.02 or along - w / 2 > L - 0.02:
            continue
        if abs(gap) <= REACH and (best is None or abs(gap) < abs(best[0])):
            best = (gap, nx, ny)
    if best is not None:
        gap, nx, ny = best
        cx, cy, kind = nx * gap, ny * gap, "wall"
    x2, y2 = x + cx, y + cy
    # 2. A side on a wall across the run or on a neighbour.
    gap_me = side_gap(e)
    side = None
    for (fx, fy), (fux, fuy), (nx, ny), L in faces:
        if abs(nx * ux + ny * uy) < 0.999:
            continue
        across = (x2 - fx) * fux + (y2 - fy) * fuy
        if across + d / 2 < 0.0 or across - d / 2 > L:
            continue
        dist = (x2 - fx) * nx + (y2 - fy) * ny        # >0: the piece is on the face's side
        if dist <= 0:
            continue
        s = 1.0 if nx * ux + ny * uy > 0 else -1.0    # +1: the face is on the piece's -X side
        move = (w / 2 + gap_me - dist) * s
        if abs(move) <= REACH and (side is None or abs(move) < abs(side)):
            side = move
    for q in doc.entities.values():
        if q.id == eid or q.id in ignore or not snappable(doc, q):
            continue
        qp = q.params
        if abs((float(qp.get("rotation", 0.0)) - math.degrees(rot) + 180) % 360 - 180) > 1.0:
            continue
        if q.kind == "cabinet" and e.kind == "cabinet" and not _levels_overlap(params, qp):
            continue
        rx, ry = float(qp["x"]) - x2, float(qp["y"]) - y2
        if abs(rx * bx + ry * by - (d - float(qp["depth"])) / 2) > 0.05:
            continue                                  # backs not on the same line
        along = rx * ux + ry * uy
        gap = max(gap_me, side_gap(q))
        for target in (along - float(qp["width"]) / 2 - w / 2 - gap, along + float(qp["width"]) / 2 + w / 2 + gap):
            if abs(target) <= REACH and (side is None or abs(target) < abs(side)):
                side = target
    if side is not None:
        cx += ux * side
        cy += uy * side
        kind = kind or "neighbour"
    if kind is None:
        return None
    return cx, cy, kind


def _levels_overlap(a, b):
    from archforge.kitchen.cabinets import _levels_overlap as overlap
    return overlap(a, b)
