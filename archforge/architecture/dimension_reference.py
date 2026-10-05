"""Dimension reference: walls drawn on a face (outside or inside), stored on their axis.

The project brief says how the building is measured: new buildings on the
outside, renovations on the inside.  The line the user draws is then that
face of the wall, not its axis — a 10×10 outline in 50 cm stone stays 10×10
outside and is 9×9 inside.

Which side is "inside" is not guessed while drawing: once a wall closes a
space (it has open space on one side only — an exterior wall) it moves by
half its thickness, inwards for exterior measuring, outwards for interior
measuring.  Corners are found again by intersecting the moved axes; walls
meeting it (T junctions) follow; doors and windows keep their place.
Interior partitions are drawn on their axis.
"""
from __future__ import annotations

import copy
import math

from archforge.core.commands import Command

TOL = 0.05


def _walls(doc, z):
    return [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < 0.05]


def _line(p):
    return (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))


def _intersect(a1, a2, b1, b2):
    d = (a1[0] - a2[0]) * (b1[1] - b2[1]) - (a1[1] - a2[1]) * (b1[0] - b2[0])
    if abs(d) < 1e-9:
        return None
    t = ((a1[0] - b1[0]) * (b1[1] - b2[1]) - (a1[1] - b1[1]) * (b1[0] - b2[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


def plan(doc, z):
    """``{wall_id: new params}`` and ``{opening_id: new offset}`` for the walls of storey ``z`` to apply."""
    from archforge.mep.ventilation import exterior_walls
    walls = _walls(doc, z)
    normals = {w.id: n for w, n in exterior_walls(doc, z)}
    # Only walls of a CLOSED space move (all of its walls together), never a half-drawn outline.
    try:
        enclosed = {wid for face in doc.active_room_faces(z=z) for wid in face.wall_ids}
    except Exception:
        enclosed = set()
    shift = {}
    for w in walls:
        ref = str(w.params.get("reference", "axis"))
        if ref in ("exterior", "interior") and not w.params.get("reference_applied") and w.id in normals \
                and w.id in enclosed:
            half = float(w.params["thickness"]) / 2
            shift[w.id] = -half if ref == "exterior" else half       # along the outward normal
    if not shift:
        return {}, {}
    moved = {}
    for w in walls:
        (a, b) = _line(w.params)
        s = shift.get(w.id, 0.0)
        n = normals.get(w.id, (0.0, 0.0))
        moved[w.id] = ((a[0] + n[0] * s, a[1] + n[1] * s), (b[0] + n[0] * s, b[1] + n[1] * s))
    walls_out, openings_out = {}, {}
    for w in walls:
        old = _line(w.params)
        new_line = moved[w.id]
        ends = []
        for k, p in enumerate(old):
            partner = None
            for o in walls:
                if o.id == w.id:
                    continue
                oa, ob = _line(o.params)
                shares = math.dist(p, oa) <= TOL or math.dist(p, ob) <= TOL
                L = math.dist(oa, ob)
                on_line = False
                if L > 1e-9 and not shares:
                    t = ((p[0] - oa[0]) * (ob[0] - oa[0]) + (p[1] - oa[1]) * (ob[1] - oa[1])) / (L * L)
                    dist = abs((ob[0] - oa[0]) * (oa[1] - p[1]) - (oa[0] - p[0]) * (ob[1] - oa[1])) / L
                    on_line = 0.0 < t < 1.0 and dist <= float(o.params["thickness"]) / 2 + TOL
                if (shares or on_line) and (o.id in shift or w.id in shift):
                    # Prefer a partner that moves too (an exterior corner).
                    if partner is None or (o.id in shift and partner.id not in shift):
                        partner = o
            q = new_line[k]
            if partner is not None:
                hit = _intersect(new_line[0], new_line[1], *moved[partner.id])
                if hit is not None and math.dist(hit, q) < 2.0:
                    q = hit
            ends.append(q)
        if any(math.dist(e, o) > 1e-9 for e, o in zip(ends, old)) or w.id in shift:
            params = {"x1": ends[0][0], "y1": ends[0][1], "x2": ends[1][0], "y2": ends[1][1]}
            if w.id in shift:
                params["reference_applied"] = True
            walls_out[w.id] = params
            # Keep doors and windows where they are in the world.
            ux, uy = old[1][0] - old[0][0], old[1][1] - old[0][1]
            L = math.hypot(ux, uy) or 1.0
            along = ((ends[0][0] - old[0][0]) * ux + (ends[0][1] - old[0][1]) * uy) / L
            if abs(along) > 1e-9:
                for o in doc.entities.values():
                    if o.kind in ("door", "window", "opening") and o.parent_id == w.id:
                        openings_out[o.id] = float(o.params["offset"]) - along
    return walls_out, openings_out


class ApplyDimensionReference(Command):
    """Move the face-drawn exterior walls of a storey onto their axis (one undoable step)."""

    def __init__(self, z):
        self.z = float(z)
        self.before = None
        self.after = None

    def do(self, doc):
        if self.after is None:
            walls, openings = plan(doc, self.z)
            self.before = {i: copy.deepcopy(doc.get(i).params) for i in list(walls) + list(openings)}
            self.after = {i: dict(p) for i, p in walls.items()}
            self.after.update({i: {"offset": v} for i, v in openings.items()})
        # Walls first (openings are validated against their host's new length).
        for i, changes in sorted(self.after.items(), key=lambda kv: doc.get(kv[0]).kind != "wall"):
            doc.update(i, changes)

    def undo(self, doc):
        for i, params in sorted((self.before or {}).items(), key=lambda kv: doc.get(kv[0]).kind == "wall"):
            restored = dict(params)
            if doc.get(i).kind == "wall":
                restored["reference_applied"] = bool(params.get("reference_applied", False))
            doc.update(i, restored)

    @property
    def changes(self):
        return bool(self.after)
