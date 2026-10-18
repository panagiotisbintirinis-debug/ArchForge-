"""Δωμάτιο (ορθογώνιο): a room from one edge pulled out to a rectangle, or from its clear dimensions (owner 18/10).

The four walls are drawn by the plan's own wall path (brief thickness, partitions, junction splits, the storey
floor), so the room is ordinary walls the human edits like any other; the whole room is one undo step.
Dimensions are clear (inside faces): the wall axes sit half a wall thickness further out.
"""
from __future__ import annotations

import math


def corners_from_edge(a, b, p):
    """The rectangle on edge a→b pulled out to the pointer p: [a, b, b + n·d, a + n·d] (d = p's distance off a→b)."""
    (ax, ay), (bx, by) = a, b
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-9:
        return None
    ux, uy = (bx - ax) / L, (by - ay) / L
    nx, ny = -uy, ux
    d = (p[0] - ax) * nx + (p[1] - ay) * ny
    return [(ax, ay), (bx, by), (bx + nx * d, by + ny * d), (ax + nx * d, ay + ny * d)]


def corners_from_size(origin, width, depth, angle_deg=0.0):
    """Clear width × depth with its first corner at ``origin`` (inside face), turned by ``angle_deg``."""
    a = math.radians(angle_deg)
    ux, uy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    ox, oy = origin
    return [(ox, oy), (ox + ux * width, oy + uy * width),
            (ox + ux * width + nx * depth, oy + uy * width + ny * depth), (ox + nx * depth, oy + ny * depth)]


def size_of(corners):
    """(width, depth) of the rectangle."""
    (ax, ay), (bx, by), (cx, cy) = corners[:3]
    return math.hypot(bx - ax, by - ay), math.hypot(cx - bx, cy - by)


def axis_corners(clear, thickness):
    """The wall axes around a clear (inside) rectangle: each corner moved out by half the wall thickness."""
    cx = sum(x for x, _ in clear) / 4.0
    cy = sum(y for _, y in clear) / 4.0
    (ax, ay), (bx, by), (qx, qy) = clear[0], clear[1], clear[3]
    w, d = math.hypot(bx - ax, by - ay), math.hypot(qx - ax, qy - ay)
    if w < 1e-9 or d < 1e-9:
        return None
    u = ((bx - ax) / w, (by - ay) / w)
    n = ((qx - ax) / d, (qy - ay) / d)
    h = thickness / 2.0
    out = []
    for x, y in clear:
        su = 1.0 if (x - cx) * u[0] + (y - cy) * u[1] > 0 else -1.0
        sn = 1.0 if (x - cx) * n[0] + (y - cy) * n[1] > 0 else -1.0
        out.append((x + (su * u[0] + sn * n[0]) * h, y + (su * u[1] + sn * n[1]) * h))
    return out


def label(corners):
    w, d = size_of(corners)
    return f'{w:.2f} × {d:.2f} m · {w * d:.1f} m² (καθαρές)'.replace('.', ',')


def _walls(doc, z):
    for e in doc.entities.values():
        if e.kind == 'wall' and abs(float(e.params.get('z', 0.0)) - z) <= 1e-3:
            p = e.params
            yield e, (float(p['x1']), float(p['y1'])), (float(p['x2']), float(p['y2'])), float(p.get('thickness', 0.2))


def face_wall(doc, a, b, z, tol=0.02):
    """The existing wall whose face (or axis) the clear side a→b lies on: the room leans on it, and the two merge."""
    for e, (x1, y1), (x2, y2), t in _walls(doc, z):
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        off = lambda x, y: abs((x - x1) * uy - (y - y1) * ux)
        along = lambda x, y: (x - x1) * ux + (y - y1) * uy
        da, db = off(*a), off(*b)
        if abs(da - db) > tol or not (abs(da - t / 2) <= tol or da <= tol):
            continue
        lo, hi = sorted((along(*a), along(*b)))
        if lo >= -t - tol and hi <= L + t + tol:
            return e
    return None


def _intersect(p, d, q, e):
    """Point where the line p + s·d meets the line q + r·e (None when parallel)."""
    den = d[0] * e[1] - d[1] * e[0]
    if abs(den) < 1e-12:
        return None
    s = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / den
    return (p[0] + d[0] * s, p[1] + d[1] * s)


def plan_room(doc, clear, z, thickness):
    """[(start, end)] of the walls to draw around a clear rectangle.

    A side lying on an existing wall (its face, inside a space or next door) is not drawn: the room uses that wall,
    and the new walls run onto its axis, so they join it.  Every other side's axis is half a wall out."""
    cx = sum(x for x, _ in clear) / 4.0
    cy = sum(y for _, y in clear) / 4.0
    lines, drawn = [], []
    for a, b in zip(clear, clear[1:] + clear[:1]):
        d = (b[0] - a[0], b[1] - a[1])
        host = face_wall(doc, a, b, z)
        if host is not None:
            p = host.params
            lines.append(((float(p['x1']), float(p['y1'])), (float(p['x2']) - float(p['x1']), float(p['y2']) - float(p['y1']))))
            drawn.append(False)
            continue
        L = math.hypot(*d)
        n = (-d[1] / L, d[0] / L)
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        if (mid[0] - cx) * n[0] + (mid[1] - cy) * n[1] < 0:      # outward
            n = (-n[0], -n[1])
        h = thickness / 2.0
        lines.append(((a[0] + n[0] * h, a[1] + n[1] * h), d))
        drawn.append(True)
    corners = []
    for k in range(4):
        prev, cur = lines[k - 1], lines[k]
        pt = _intersect(prev[0], prev[1], cur[0], cur[1])
        if pt is None:
            return None
        corners.append(pt)
    return [(corners[k], corners[(k + 1) % 4]) for k in range(4) if drawn[k]]


def inside_space(doc, clear, z):
    """True when the rectangle lies inside a closed space already drawn: its new walls are partitions."""
    from archforge.assistant.understanding import inside
    cx = sum(x for x, _ in clear) / 4.0
    cy = sum(y for _, y in clear) / 4.0
    return any(inside(f.polygon, cx, cy) for f in doc.active_room_faces(z=z))
