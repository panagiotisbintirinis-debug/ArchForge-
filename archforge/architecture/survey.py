"""Αποτύπωση από μετρήσεις — a room's corners from measured sides and diagonals (owner 24/10: «η διάσταση είναι
εργαλείο από τοίχο σε τοίχο, διαγώνιες όταν δεν ξέρουμε τις γωνίες — έχω τοίχους να πάρω δέκα διαγώνιες μετρήσεις για
ένα δωμάτιο τεσσάρων τοίχων για να βγάλω τα παράγωνα · ειδικά σε μια νέα αποτύπωση υφισταμένου»).

The room is drawn roughly; what is measured on site is the clear room, face to face (σοβάς σε σοβά):

* ``survey_room(doc, face)`` — the room's corners on its inner faces (straight runs of walls are one side, a T-joint
  is not a corner), numbered 1…n round the room, with the drawn sides and diagonals;
* ``solve(corners, measurements)`` — least squares (Gauss–Newton) for the corners that fit every measured distance
  ``(i, j, metres)``; corner 1 stays where it is and side 1–2 keeps its direction.  Each measurement's residual is
  returned, so a mis-read tape shows at once; fewer than 2n − 3 independent measurements leaves the shape open
  (a quadrilateral: 4 sides + 1 diagonal at least) and is said so;
* ``apply_command(doc, room, solved)`` — the walls follow, each kept at its thickness outside the measured face; wall
  ends on the room's corners and walls joined along its sides (partitions, T-joints) move with them, one undo.
"""
from __future__ import annotations

import math

import numpy as np

TOL = 1e-3


def _line_through(a, b):
    L = math.dist(a, b)
    return (a, ((b[0] - a[0]) / L, (b[1] - a[1]) / L))


def _cross(p, d, q, e):
    """Crossing of the lines p + s·d and q + t·e (None when parallel)."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12:
        return None
    s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * s, p[1] + d[1] * s)


def _area(pts):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))


def _wall_on(doc, a, b, ids):
    """The wall (of ``ids``) whose axis carries the segment a–b."""
    for wid in ids:
        if wid not in doc.entities:
            continue
        p = doc.get(wid).params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-9:
            continue
        ok = True
        for q in (a, b):
            cross = abs((q[0] - ax) * (by - ay) - (q[1] - ay) * (bx - ax)) / L
            t = ((q[0] - ax) * (bx - ax) + (q[1] - ay) * (by - ay)) / (L * L)
            if cross > TOL or not (-TOL <= t <= 1 + TOL):
                ok = False
        if ok:
            return doc.get(wid)
    return None


def survey_room(doc, face):
    """The room ready to survey: ``{"axis", "inner", "half", "corners"}`` — its corners on the wall axes and on the inner
    faces (counter-clockwise, corner 1 first), and each side's half thickness."""
    poly = [tuple(map(float, q)) for q in face.polygon]
    if len(poly) > 2 and math.dist(poly[0], poly[-1]) < TOL:
        poly = poly[:-1]
    if _area(poly) < 0:
        poly = poly[::-1]
    # Corners: where the outline turns (collinear vertices — T-joints — are not corners).
    n = len(poly)
    axis = []
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        turn = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(turn) > 1e-6 * max(1.0, math.dist(a, b) * math.dist(b, c)):
            axis.append(b)
    m = len(axis)
    if m < 3:
        raise ValueError("ο χώρος δεν έχει γωνίες για αποτύπωση")
    half = []
    for i in range(m):
        a, b = axis[i], axis[(i + 1) % m]
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        sub = None
        for j in range(n):            # the polygon piece of this side that holds its middle → its wall
            p, q = poly[j], poly[(j + 1) % n]
            if _wall_on(doc, p, q, face.wall_ids) is not None and abs(math.dist(p, mid) + math.dist(mid, q) - math.dist(p, q)) < TOL:
                sub = _wall_on(doc, p, q, face.wall_ids)
                break
        if sub is None:
            sub = _wall_on(doc, a, b, face.wall_ids)
        half.append(float(sub.params.get("thickness", 0.2)) / 2 if sub is not None else 0.0)
    inner = _offset(axis, [-h for h in half])
    return {"axis": axis, "inner": inner, "half": half, "corners": m}


def _offset(pts, dist):
    """The polygon whose side i lies ``dist[i]`` outside side i of ``pts`` (counter-clockwise: − = inwards)."""
    m = len(pts)
    lines = []
    for i in range(m):
        a, b = pts[i], pts[(i + 1) % m]
        p, d = _line_through(a, b)
        nx, ny = -d[1], d[0]                                  # left of the side = inside (counter-clockwise)
        lines.append(((p[0] - nx * dist[i], p[1] - ny * dist[i]), d))
    out = []
    for i in range(m):
        (p, d), (q, e) = lines[i - 1], lines[i]
        x = _cross(p, d, q, e)
        out.append(x if x is not None else q)
    return out


def drawn(corners):
    """Every distance between corners as drawn: ``{(i, j): metres}`` (0-based, i < j)."""
    m = len(corners)
    return {(i, j): math.dist(corners[i], corners[j]) for i in range(m) for j in range(i + 1, m)}


def solve(corners, measurements, iterations=60):
    """``{"corners", "residuals", "rank_ok", "rms"}`` for the measured ``[(i, j, metres)]`` (0-based corners)."""
    m = len(corners)
    meas = [(int(i), int(j), float(v)) for i, j, v in measurements if v and float(v) > 0 and int(i) != int(j)]
    if not meas:
        raise ValueError("καμία μέτρηση")
    x = np.array(corners, dtype=float).ravel()
    a0 = x[0:2].copy()
    d0 = x[2:4] - a0
    d0 /= max(np.linalg.norm(d0), 1e-12)
    # Unknowns: corner 1 fixed; corner 2 slides along side 1–2; the others free → 1 + 2(m−2) = 2m − 3.
    def build(v):
        pts = np.zeros((m, 2))
        pts[0] = a0
        pts[1] = a0 + d0 * v[0]
        pts[2:] = v[1:].reshape(m - 2, 2)
        return pts
    v = np.concatenate([[float(np.dot(x[2:4] - a0, d0))], x[4:]])
    rank_ok = True
    for _ in range(iterations):
        pts = build(v)
        r = np.zeros(len(meas)); J = np.zeros((len(meas), len(v)))
        for k, (i, j, val) in enumerate(meas):
            dvec = pts[i] - pts[j]; dist = max(np.linalg.norm(dvec), 1e-12)
            r[k] = dist - val
            g = dvec / dist                                   # d dist / d p_i ; d / d p_j = −g
            for idx, sign in ((i, 1.0), (j, -1.0)):
                if idx == 1:
                    J[k, 0] += sign * float(np.dot(g, d0))
                elif idx >= 2:
                    J[k, 1 + 2 * (idx - 2): 3 + 2 * (idx - 2)] += sign * g
        rank_ok = np.linalg.matrix_rank(J, tol=1e-9) >= len(v)
        step, *_ = np.linalg.lstsq(J, -r, rcond=None)
        v = v + step
        if np.linalg.norm(step) < 1e-10:
            break
    pts = build(v)
    res = []
    for i, j, val in meas:
        res.append((i, j, val, float(np.linalg.norm(pts[i] - pts[j]) - val)))
    rms = math.sqrt(sum(e[3] ** 2 for e in res) / len(res))
    return {"corners": [tuple(map(float, p)) for p in pts], "residuals": res, "rank_ok": bool(rank_ok), "rms": rms}


def apply_command(doc, room, solved, z=None):
    """UpdateEntities moving the walls so the room's inner faces are the ``solved`` corners (one undo)."""
    from archforge.core.commands import UpdateEntities
    old_axis = room["axis"]
    new_axis = _offset(list(solved), list(room["half"]))             # the axes, half a wall outside the faces
    m = len(old_axis)
    level = float(doc.work_plane.origin[2] if z is None else z)

    def moved(q):
        for i in range(m):
            if math.dist(q, old_axis[i]) <= TOL:
                return new_axis[i]
        for i in range(m):
            a, b = old_axis[i], old_axis[(i + 1) % m]
            L = math.dist(a, b)
            t = ((q[0] - a[0]) * (b[0] - a[0]) + (q[1] - a[1]) * (b[1] - a[1])) / (L * L)
            cross = abs((q[0] - a[0]) * (b[1] - a[1]) - (q[1] - a[1]) * (b[0] - a[0])) / L
            if cross <= TOL and 0.0 <= t <= 1.0:
                c, d = new_axis[i], new_axis[(i + 1) % m]
                return (c[0] + (d[0] - c[0]) * t, c[1] + (d[1] - c[1]) * t)
        return None

    changes = {}
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - level) > 1e-4:
            continue
        p = e.params; ch = {}
        for k in ("1", "2"):
            q = moved((float(p["x" + k]), float(p["y" + k])))
            if q is not None and math.dist(q, (float(p["x" + k]), float(p["y" + k]))) > 1e-9:
                ch["x" + k], ch["y" + k] = float(q[0]), float(q[1])
        if ch:
            changes[e.id] = ch
    if not changes:
        raise ValueError("οι τοίχοι είναι ήδη στις μετρήσεις")
    return UpdateEntities(changes)
