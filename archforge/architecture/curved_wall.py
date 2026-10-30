"""Καμπύλος τοίχος (owner 29–30/10: «Τοίχος ▾ … καμπύλος» · «ξεκίνησε τον καμπύλο τοίχο»).

A curved wall is an arc drawn by three points — start, end, a point on the arc — made of ordinary straight walls
along it (chords, each within ``SAG`` of the true arc).  They are plain ``wall`` entities, so rooms, joins,
openings, quantities, 3D and sections treat them as every other wall; each one carries the arc it belongs to
(``params['curve']``: id, centre, radius, start angle, sweep, number of pieces) so the whole arc is selected,
reshaped (radius / pieces) and told apart as one wall.  This is a faceted arc, not a true curved solid: the
Ιδιότητες say so, with the deviation from the circle.
"""
from __future__ import annotations

import math
import uuid

SAG = 0.01            # m — largest gap between a piece and the circle when the pieces are chosen automatically
MIN_PIECES, MAX_PIECES = 4, 96


def arc_through(a, b, m):
    """The circle arc from ``a`` to ``b`` passing through ``m``: (cx, cy, r, start angle, sweep) — sweep signed
    (counter-clockwise > 0).  ValueError when the three points are (nearly) on one line."""
    (ax, ay), (bx, by), (mx, my) = [(float(p[0]), float(p[1])) for p in (a, b, m)]
    d = 2 * (ax * (my - by) + mx * (by - ay) + bx * (ay - my))
    if abs(d) < 1e-9 or math.dist((ax, ay), (bx, by)) < 0.05:
        raise ValueError("Καμπύλος τοίχος: τα τρία σημεία είναι σε ευθεία — δώσε το τρίτο πιο έξω από τη χορδή")
    sa, sm, sb = ax * ax + ay * ay, mx * mx + my * my, bx * bx + by * by
    cx = (sa * (my - by) + sm * (by - ay) + sb * (ay - my)) / d
    cy = (sa * (bx - mx) + sm * (ax - bx) + sb * (mx - ax)) / d
    r = math.dist((cx, cy), (ax, ay))
    t0 = math.atan2(ay - cy, ax - cx)
    tm = (math.atan2(my - cy, mx - cx) - t0) % (2 * math.pi)
    tb = (math.atan2(by - cy, bx - cx) - t0) % (2 * math.pi)
    sweep = tb if tm < tb else tb - 2 * math.pi          # the way round that passes through m
    return cx, cy, r, t0, sweep


def arc_with_radius(a, b, r, side):
    """The arc from ``a`` to ``b`` with radius ``r`` bulging to ``side`` (+1 left of a→b, −1 right), the shorter
    way round.  Used to change the radius of a drawn arc and keep its ends."""
    (ax, ay), (bx, by) = [(float(p[0]), float(p[1])) for p in (a, b)]
    c = math.dist((ax, ay), (bx, by))
    r = max(float(r), c / 2 + 1e-6)
    h = math.sqrt(max(0.0, r * r - c * c / 4))           # centre from the chord's middle
    sag = r - h
    nx, ny = -(by - ay) / c, (bx - ax) / c                # left of a→b
    mx, my = (ax + bx) / 2 + side * nx * sag, (ay + by) / 2 + side * ny * sag
    return arc_through((ax, ay), (bx, by), (mx, my))


def pieces_for(r, sweep, sag=SAG):
    """How many straight pieces keep every one within ``sag`` of the circle."""
    if r <= sag:
        return MIN_PIECES
    step = 2 * math.acos(max(-1.0, min(1.0, 1 - sag / r)))
    return max(MIN_PIECES, min(MAX_PIECES, int(math.ceil(abs(sweep) / max(step, 1e-6)))))


def points(cx, cy, r, t0, sweep, n):
    return [(cx + r * math.cos(t0 + sweep * k / n), cy + r * math.sin(t0 + sweep * k / n)) for k in range(n + 1)]


def deviation(r, sweep, n):
    """Largest gap (m) between a piece and the circle."""
    return r * (1 - math.cos(abs(sweep) / n / 2))


def wall_defaults(doc, choice=None):
    """Height, thickness and type the wall tool would give (project brief, «Τοίχος ▾» choice)."""
    from archforge.project.brief import wall_defaults as brief
    wall_type, thickness = brief(doc)
    height = 2.7
    if doc.active_level_name() == "Basement":
        z = float(doc.work_plane.origin[2])
        above = [float(v) for v in doc.levels.values() if float(v) > z + 1e-6]
        if above:
            height = min(above) - z
    extra = {}
    if choice == "glass":
        from archforge.architecture.wall_types import GLASS_WALL
        thickness, wall_type = float(GLASS_WALL["thickness"]), "generic"
        extra = {"material_id": GLASS_WALL["material_id"], "wall_kind": "glass"}
    elif choice:
        from archforge.architecture.wall_types import total_thickness
        wall_type = str(choice)
        if total_thickness(choice, doc) > 0:
            thickness = float(total_thickness(choice, doc))
    return {"height": float(height), "thickness": float(thickness), **({"wall_type": wall_type} if wall_type else {}),
            **extra}


def make_walls(doc, arc, n=None, base=None, curve_id=None, name=None):
    """The wall entities of an arc (cx, cy, r, t0, sweep): ``n`` pieces (None: by ``SAG``)."""
    from archforge.core.interaction import next_name
    from archforge.core.model import Entity
    cx, cy, r, t0, sweep = (float(v) for v in arc)
    n = int(n) if n else pieces_for(r, sweep)
    n = max(1, min(MAX_PIECES, n))
    base = dict(base if base is not None else wall_defaults(doc))
    base.setdefault("z", float(doc.work_plane.origin[2]))
    curve = {"id": curve_id or uuid.uuid4().hex[:12], "cx": round(cx, 6), "cy": round(cy, 6), "r": round(r, 6),
             "t0": round(t0, 9), "sweep": round(sweep, 9), "n": n}
    name = name or next_name(doc, "wall")
    pts = [(round(x, 6), round(y, 6)) for x, y in points(cx, cy, r, t0, sweep, n)]
    out = []
    for k, ((x1, y1), (x2, y2)) in enumerate(zip(pts, pts[1:])):
        params = {**base, "x1": x1, "y1": y1, "x2": x2, "y2": y2, "curve": dict(curve, piece=k)}
        out.append(Entity("wall", params, name=f"{name} (καμπύλος {k + 1}/{n})"))
    return out


def create_command(doc, a, b, m, n=None, choice=None):
    """«Καμπύλος τοίχος» from three plan points — (command, walls)."""
    from archforge.core.commands import AddEntities
    walls = make_walls(doc, arc_through(a, b, m), n, wall_defaults(doc, choice))
    return AddEntities(walls), walls


def members(doc, curve_id):
    """The walls of one arc, in order along it."""
    got = [e for e in doc.entities.values() if e.kind == "wall" and (e.params.get("curve") or {}).get("id") == curve_id]
    return sorted(got, key=lambda e: int(e.params["curve"].get("piece", 0)))


def info(doc, entity):
    """What the Ιδιότητες say about the arc of ``entity`` (None: a straight wall)."""
    c = entity.params.get("curve")
    if not c:
        return None
    walls = members(doc, c["id"])
    length = abs(float(c["r"]) * float(c["sweep"]))
    return {"id": c["id"], "r": float(c["r"]), "sweep_deg": math.degrees(abs(float(c["sweep"]))),
            "n": int(c["n"]), "length": length, "walls": [w.id for w in walls],
            "deviation": deviation(float(c["r"]), float(c["sweep"]), int(c["n"]))}


def reshape_command(doc, curve_id, r=None, n=None):
    """The arc rebuilt with another radius (ends kept, same side) and/or number of pieces — one undo step.
    Doors / windows on it keep their place along the arc (same fraction of its length, same ids) on the piece
    that now holds it; ValueError when one no longer fits in its piece (say which and why)."""
    from archforge.core.commands import AddEntities, CompositeCommand, DeleteEntities
    walls = members(doc, curve_id)
    if not walls:
        raise ValueError("Καμπύλος τοίχος: δεν βρέθηκε")
    c = dict(walls[0].params["curve"])
    cx, cy, r0, t0, sweep = (float(c[k]) for k in ("cx", "cy", "r", "t0", "sweep"))
    arc = (cx, cy, r0, t0, sweep)
    if r is not None and abs(float(r) - r0) > 1e-6:
        a, b = points(cx, cy, r0, t0, sweep, 1)
        mid = points(cx, cy, r0, t0, sweep, 2)[1]
        side = 1 if (b[0] - a[0]) * (mid[1] - a[1]) - (b[1] - a[1]) * (mid[0] - a[0]) > 0 else -1
        arc = arc_with_radius(a, b, float(r), side)
    if r is not None and n is None:
        n = pieces_for(arc[2], arc[4])
    base = {k: v for k, v in walls[0].params.items() if k not in ("x1", "y1", "x2", "y2", "curve")}
    name = str(walls[0].name or "").split(" (καμπύλος")[0] or None
    new = make_walls(doc, arc, n or int(c["n"]), base, curve_id=c["id"], name=name)
    moved = rehosted_openings(doc, walls, new)
    return CompositeCommand([DeleteEntities([w.id for w in walls]), AddEntities(new + moved)], "Καμπύλος τοίχος"), new


def _chord(w):
    p = w.params
    return math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))


def rehosted_openings(doc, old_walls, new_walls):
    """Copies of the doors / windows of ``old_walls`` on ``new_walls`` at the same fraction of the arc (the piece
    holding their centre; nudged inside it when they would cross its end).  Deleting the old pieces takes the
    originals with them; the copies keep their ids, so one undo brings everything back."""
    index = {w.id: k for k, w in enumerate(old_walls)}
    n_old, n_new = len(old_walls), len(new_walls)
    out = []
    for e in sorted(doc.entities.values(), key=lambda e: e.id):
        if e.kind not in ("door", "window", "opening") or e.parent_id not in index:
            continue
        old = old_walls[index[e.parent_id]]
        f = (index[e.parent_id] + float(e.params.get("offset", 0.0)) / max(_chord(old), 1e-9)) / n_old
        k = min(n_new - 1, max(0, int(f * n_new)))
        host = new_walls[k]
        length, half = _chord(host), float(e.params.get("width", 0.0)) / 2
        if 2 * half > length + 1e-9:
            raise ValueError(f"Καμπύλος τοίχος: «{e.name or e.kind}» πλάτους {2 * half:.2f} m δεν χωράει σε τμήμα "
                             f"{length:.2f} m — λιγότερα τμήματα ή μεγαλύτερη ακτίνα")
        offset = min(max((f * n_new - k) * length, half), length - half)
        copy = e.clone()
        copy.parent_id = host.id
        copy.params = {**e.params, "offset": round(offset, 6)}
        out.append(copy)
    return out


SHARED = ("height", "thickness", "z", "wall_type", "material_id", "wall_kind", "load_bearing", "reference")


def spread_command(doc, entity_id, changes):
    """A change of height / thickness / type on one piece of an arc goes to the whole arc (one undo): it is one
    wall to the human.  Other keys (or a straight wall) change that wall only."""
    from archforge.core.commands import UpdateEntities, UpdateEntity
    entity = doc.get(entity_id)
    c = entity.params.get("curve") if entity.kind == "wall" else None
    if not c or not set(changes) <= set(SHARED):
        return UpdateEntity(entity_id, changes)
    return UpdateEntities({w.id: dict(changes) for w in members(doc, c["id"])})
