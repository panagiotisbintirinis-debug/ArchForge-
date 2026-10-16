"""Dimensions of a selected wall, read from the Document (owner 15/10: «εμφανείς διαστάσεις με επιλογή»).

* its length (centre line);
* on each side, the clear distance (face to face) to the nearest parallel wall that faces it.

``offset`` shows the same dimensions with the wall moved that far along ``wall_normal`` (live while it is
being moved).  ``offset_for`` is the move that gives a typed clear distance on one side.  Nothing is stored:
the numbers are derived from the walls each time.
"""
from __future__ import annotations

import math

from archforge.architecture.wall_edit import _ends, _walls, wall_normal

PARALLEL = 0.999        # |cos| between the axes
MIN_OVERLAP = 0.05      # m of shared length for two walls to "face" each other


def wall_dims(doc, eid, offset=0.0):
    """``{"length": {...}, "sides": [{"side", "clear", "a", "b", "neighbour"}]}`` or None (not a wall)."""
    w = doc.entities.get(eid)
    if w is None or w.kind != "wall":
        return None
    (ax, ay), (bx, by) = _ends(w.params)
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-6:
        return None
    ux, uy = (bx - ax) / L, (by - ay) / L
    nx, ny = wall_normal(w.params)
    ax, ay, bx, by = ax + nx * offset, ay + ny * offset, bx + nx * offset, by + ny * offset
    t = float(w.params.get("thickness", 0.2))
    z = float(w.params.get("z", 0.0))
    best = {}
    for o in _walls(doc, z):
        if o.id == eid:
            continue
        (cx, cy), (dx, dy) = _ends(o.params)
        M = math.hypot(dx - cx, dy - cy)
        if M < 1e-6 or abs((dx - cx) / M * ux + (dy - cy) / M * uy) < PARALLEL:
            continue
        s0 = (cx - ax) * ux + (cy - ay) * uy
        s1 = (dx - ax) * ux + (dy - ay) * uy
        lo, hi = max(0.0, min(s0, s1)), min(L, max(s0, s1))
        if hi - lo < MIN_OVERLAP:
            continue
        d = ((cx + dx) / 2 - ax) * nx + ((cy + dy) / 2 - ay) * ny      # centre line to centre line
        if abs(d) < 1e-6:
            continue
        side = 1 if d > 0 else -1
        clear = abs(d) - t / 2 - float(o.params.get("thickness", 0.2)) / 2
        if clear <= 0.0:
            continue
        if side not in best or abs(d) < best[side][0]:
            best[side] = (abs(d), o.id, clear, lo + (hi - lo) * 0.25)     # off the middle, where room names sit
    sides = []
    for side, (_d, oid, clear, s) in sorted(best.items(), reverse=True):
        px, py = ax + ux * s + nx * side * t / 2, ay + uy * s + ny * side * t / 2
        sides.append({"side": side, "clear": clear, "neighbour": oid,
                      "a": (px, py), "b": (px + nx * side * clear, py + ny * side * clear)})
    # The length on the side with more room (or + when nothing is there), 45 cm off the face.
    out_side = max((1, -1), key=lambda s: next((x["clear"] for x in sides if x["side"] == s), 99.0))
    k = out_side * (t / 2 + 0.45)
    length = {"value": L, "a": (ax + nx * k, ay + ny * k), "b": (bx + nx * k, by + ny * k), "side": out_side}
    return {"length": length, "sides": sides, "normal": (nx, ny), "thickness": t}


def offset_for(doc, eid, side, clear):
    """The move (m, along ``wall_normal``) that makes the clear distance on ``side`` equal ``clear``."""
    dims = wall_dims(doc, eid)
    now = next((x["clear"] for x in (dims or {}).get("sides", ()) if x["side"] == side), None)
    if now is None:
        raise ValueError("δεν υπάρχει απέναντι τοίχος σε αυτή την πλευρά")
    if clear <= 0:
        raise ValueError("η απόσταση πρέπει να είναι θετική")
    return side * (now - float(clear))


def fmt(v):
    """«3,45» — metres with two decimals and a Greek comma."""
    return f"{v:.2f}".replace(".", ",")


# ------------------------------------------------------------------ any object: its clearances to the walls
# Owner 15/10: «επιμήκυνση και μετακίνηση: εάν κρατάμε πατημένο το ποντίκι σε οτιδήποτε το κάνουμε να μετακινηθεί
# … χρειάζεσαι και άμεση αναγνώριση — το μεγάλωσα 2 πόντους, το μετακίνησα 20, πόσο έχω μέχρι απέναντι, πόσο
# χώρο χρειάζομαι».

def footprint(params):
    """``(cx, cy, ux, uy, half_w, half_d)`` of an object with x / y / width / depth (rotation in degrees), or None."""
    try:
        cx, cy = float(params["x"]), float(params["y"])
        w, d = float(params["width"]), float(params["depth"])
    except (KeyError, TypeError, ValueError):
        return None
    a = math.radians(float(params.get("rotation", 0.0) or 0.0))
    return cx, cy, math.cos(a), math.sin(a), w / 2, d / 2


def _ray_to_walls(doc, px, py, dx, dy, z, ignore=(), limit=30.0):
    """Distance from (px, py) along (dx, dy) to the nearest wall face on storey ``z``, or None."""
    best = None
    for w in _walls(doc, z):
        if w.id in ignore:
            continue
        (ax, ay), (bx, by) = _ends(w.params)
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        half = float(w.params.get("thickness", 0.2)) / 2
        for side in (1, -1):                       # both faces of the wall
            fx, fy = ax + nx * half * side, ay + ny * half * side
            den = dx * uy - dy * ux                       # cross(d, u)
            if abs(den) < 1e-9:
                continue                                  # parallel to this wall
            # p + t·d = f + s·u  →  t = cross(f − p, u) / cross(d, u),  s = cross(f − p, d) / cross(d, u)
            qx, qy = fx - px, fy - py
            t = (qx * uy - qy * ux) / den
            s = (qx * dy - qy * dx) / den
            if t > 1e-6 and -1e-6 <= s <= L + 1e-6 and t <= limit and (best is None or t < best):
                best = t
    return best


def object_clearances(doc, params, z=None, ignore=()):
    """From the middle of each side of an object's footprint, outwards, the distance to the nearest wall face:
    ``[{"side": "front"/"back"/"left"/"right", "value", "a", "b"}]`` (sides with no wall within 30 m left out)."""
    f = footprint(params)
    if f is None:
        return []
    cx, cy, ux, uy, hw, hd = f
    z = float(params.get("z", 0.0)) if z is None else float(z)
    nx, ny = -uy, ux
    out = []
    for name, (dx, dy), h in (("right", (ux, uy), hw), ("left", (-ux, -uy), hw),
                              ("back", (nx, ny), hd), ("front", (-nx, -ny), hd)):
        px, py = cx + dx * h, cy + dy * h
        t = _ray_to_walls(doc, px, py, dx, dy, z, ignore)
        if t is not None:
            out.append({"side": name, "value": t, "a": (px, py), "b": (px + dx * t, py + dy * t)})
    return out
