"""Editing a drawn house by numbers (owner 18/10: «να μικρύνω ένα δωμάτιο ή να αλλάξω γωνία σε ένα τοίχο»).

* Corner angle of a wall: the angle it makes at its first end with the wall joined there (or with the plan's
  X axis when nothing is joined).  Its other end moves to the new direction, length kept, and every wall joined
  at that other end follows (the same junction move as dragging the corner handle) — the room stays closed.
* Room size: the clear width × depth of a four-sided room.  One side per direction moves (``wall_edit.MoveWall``:
  joined walls stretch, openings and objects on it follow) — of the two, the shorter wall line, i.e. the partition
  rather than the house's outer wall.
Both are one undo step.
"""
from __future__ import annotations

import copy
import math

from archforge.core.commands import CompositeCommand, UpdateEntities


def _ends(p):
    return (float(p['x1']), float(p['y1'])), (float(p['x2']), float(p['y2']))


def _joined_at(doc, wid, point, tol=1e-4):
    z = float(doc.get(wid).params.get('z', 0.0))
    out = []
    for e in doc.entities.values():
        if e.kind != 'wall' or e.id == wid or abs(float(e.params.get('z', 0.0)) - z) > 1e-3:
            continue
        for ep in (1, 2):
            if math.dist((float(e.params[f'x{ep}']), float(e.params[f'y{ep}'])), point) <= tol:
                out.append((e.id, ep))
    return out


def _direction_from(doc, wid, ep):
    """Unit direction of the wall leaving its endpoint ``ep``."""
    a, b = _ends(doc.get(wid).params)
    s, t = (a, b) if ep == 1 else (b, a)
    L = math.dist(s, t)
    return ((t[0] - s[0]) / L, (t[1] - s[1]) / L)


def corner_angle(doc, wid):
    """(angle in degrees 0–180, reference) of the wall at its first end: with the wall joined there, else with X."""
    a, _b = _ends(doc.get(wid).params)
    d = _direction_from(doc, wid, 1)
    joined = _joined_at(doc, wid, a)
    if joined:
        r = _direction_from(doc, *joined[0])
        return math.degrees(math.acos(max(-1.0, min(1.0, d[0] * r[0] + d[1] * r[1])))), joined[0][0]
    return math.degrees(math.atan2(d[1], d[0])) % 360.0, None


def set_corner_angle_command(doc, wid, angle_deg):
    """UpdateEntities: the wall turned about its first end to ``angle_deg`` (see ``corner_angle``)."""
    p = doc.get(wid).params
    a, b = _ends(p)
    L = math.dist(a, b)
    d = _direction_from(doc, wid, 1)
    joined = _joined_at(doc, wid, a)
    if joined:
        r = _direction_from(doc, *joined[0])
        side = 1.0 if r[0] * d[1] - r[1] * d[0] >= 0 else -1.0       # keep the side the wall is on
        ang = math.atan2(r[1], r[0]) + side * math.radians(angle_deg)
    else:
        ang = math.radians(angle_deg)
    if not 1.0 <= float(angle_deg) <= 359.0:
        raise ValueError('η γωνία πρέπει να είναι μεταξύ 1° και 359°')
    nb = (a[0] + math.cos(ang) * L, a[1] + math.sin(ang) * L)
    changes = {wid: copy.deepcopy(p)}
    changes[wid]['x2'], changes[wid]['y2'] = nb
    for oid, ep in _joined_at(doc, wid, b):                          # the corner at the far end goes with it
        q = changes.setdefault(oid, copy.deepcopy(doc.get(oid).params))
        q[f'x{ep}'], q[f'y{ep}'] = nb
        if math.hypot(float(q['x2']) - float(q['x1']), float(q['y2']) - float(q['y1'])) < 0.05:
            raise ValueError('ο γειτονικός τοίχος θα μηδενιζόταν')
    return UpdateEntities(changes)


def _edge_walls(doc, face, a, b, tol=0.02):
    """Walls of ``face`` lying on its edge a→b."""
    out = []
    for wid in face.wall_ids:
        if wid not in doc.entities:
            continue
        (x1, y1), (x2, y2) = _ends(doc.get(wid).params)
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        off = lambda x, y: abs((x - x1) * (y2 - y1) - (y - y1) * (x2 - x1)) / L
        if off(*a) <= tol and off(*b) <= tol:
            out.append(wid)
    return out


def room_size(doc, face):
    """Clear (width, depth) of a four-sided room and its sides [(edge, walls, thickness)], or None."""
    poly = list(face.polygon)
    if len(poly) != 4:
        return None
    sides = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        walls = _edge_walls(doc, face, a, b)
        t = max((float(doc.get(w).params.get('thickness', 0.0)) for w in walls), default=0.0)
        sides.append(((a, b), walls, t))
    w = math.dist(*sides[0][0]) - sides[1][2] / 2 - sides[3][2] / 2
    d = math.dist(*sides[1][0]) - sides[0][2] / 2 - sides[2][2] / 2
    return (w, d), sides


def resize_room_command(doc, face, width, depth):
    """CompositeCommand moving one side per direction so the clear size becomes width × depth."""
    from archforge.architecture.wall_edit import MoveWall, straight_run, wall_normal
    got = room_size(doc, face)
    if got is None:
        raise ValueError('μόνο τετράπλευρο δωμάτιο (για άλλα σχήματα: μετακίνησε τους τοίχους)')
    (w0, d0), sides = got
    if width <= 0.3 or depth <= 0.3:
        raise ValueError('πολύ μικρό δωμάτιο')
    cx = sum(x for x, _ in face.polygon) / 4.0
    cy = sum(y for _, y in face.polygon) / 4.0

    def run_length(wid):
        return sum(math.dist(*_ends(doc.get(i).params)) for i in straight_run(doc, wid) if i in doc.entities)

    moves = []
    for delta, pair in ((width - w0, (sides[1], sides[3])), (depth - d0, (sides[0], sides[2]))):
        if abs(delta) < 1e-4:
            continue
        candidates = [s for s in pair if s[1]]
        if not candidates:
            raise ValueError('δεν βρέθηκε τοίχος στην πλευρά του δωματίου')
        (a, b), walls, _t = min(candidates, key=lambda s: min(run_length(w) for w in s[1]))
        wid = walls[0]
        mx, my = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy
        L = math.hypot(mx, my) or 1.0
        n = wall_normal(doc.get(wid).params)
        moves.append(MoveWall(wid, delta * (mx * n[0] + my * n[1]) / L))
    return CompositeCommand(moves, 'Διαστάσεις δωματίου') if moves else None
