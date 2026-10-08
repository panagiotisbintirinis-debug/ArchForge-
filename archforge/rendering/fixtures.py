"""Derived 3D fixtures for doors and windows (render only).

The wall mesh already carries the opening as a hole; these parts fill it
visually: window frame + glass (with a mullion when wide), door frame +
leaf. They are rebuilt from the authoritative door/window params and the
host wall on every render, carry the opening's entity id (so clicking the
glass selects the window) and never enter fabrication geometry.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

FRAME_FACE = 0.06     # visible frame width (m)
FRAME_DEPTH = 0.08    # frame depth across the wall (m)
GLASS = 0.012
LEAF = 0.04
# «Ανοιχτά κουφώματα στο 3D» (Προβολή): view choice, not Document; the angle
# of each door/window is its own ``open_angle`` when it has one.
SHOW_OPEN = False


def set_show_open(on):
    global SHOW_OPEN
    SHOW_OPEN = bool(on)


def display_angle(params):
    """Leaf angle shown in 3D (degrees): the opening's own, else the view choice."""
    own = float(params.get('open_angle', 0.0) or 0.0)
    if own > 0:
        return own
    from archforge.architecture.joinery import OPEN_ANGLE_DEFAULT
    return OPEN_ANGLE_DEFAULT if SHOW_OPEN else 0.0


def _box(u0, u1, n0, n1, z0, z1):
    corners = [(u, n, z) for z in (z0, z1) for n in (n0, n1) for u in (u0, u1)]
    # index = zi*4 + ni*2 + ui
    quads = [
        (0, 1, 3, 2), (4, 6, 7, 5),          # bottom, top
        (0, 4, 5, 1), (2, 3, 7, 6),          # n0, n1 faces
        (0, 2, 6, 4), (1, 5, 7, 3),          # u0, u1 faces
    ]
    tris = []
    for a, b, c, d in quads:
        tris += [(a, b, c), (a, c, d)]
    return corners, tris


def opening_fixture_parts(doc, opening) -> List[Tuple[str, Tuple, Tuple]]:
    """[(material_key, vertices, triangles), ...] in world coordinates."""
    if opening.kind not in ('door', 'window') or not opening.parent_id:
        return []
    if opening.parent_id not in doc.entities:
        return []
    host = doc.get(opening.parent_id)
    if host.kind != 'wall':
        return []
    w = host.params; o = opening.params
    x1, y1, x2, y2 = (float(w[k]) for k in ('x1', 'y1', 'x2', 'y2'))
    L = math.hypot(x2 - x1, y2 - y1)
    if L < 1e-9:
        return []
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = -uy, ux
    zb = float(w['z']); wall_h = float(w['height']); t = float(w['thickness'])
    width = float(o.get('width', 0.0)); height = float(o.get('height', 0.0))
    center = float(o.get('offset', 0.0)); sill = float(o.get('sill', 0.0))
    u0 = max(0.0, center - width / 2.0); u1 = min(L, center + width / 2.0)
    z0 = max(0.0, sill); z1 = min(wall_h, sill + height)
    if u1 - u0 <= 2 * FRAME_FACE + 0.02 or z1 - z0 <= 2 * FRAME_FACE + 0.02:
        return []
    fd = min(FRAME_DEPTH, t) / 2.0; fw = FRAME_FACE
    boxes: Dict[str, list] = {}

    def add(key, *extent):
        boxes.setdefault(key, []).append(_box(*extent))

    from archforge.architecture.joinery import inside_sign, is_typed, joinery_boxes_posed, pose_point
    if is_typed(o):
        # Typed joinery (architecture/joinery.py): boxes per role in the
        # opening's frame (u along, s > 0 towards the inside, z up); open
        # leaves turn about their hinge / slide (pose, local frame first).
        sign_in = inside_sign(doc, host)
        posed = joinery_boxes_posed(opening.kind, dict(o, width=u1 - u0, height=z1 - z0), t, sign_in,
                                    display_angle(o))
        for role, lo, hi, pose in posed:
            corners, tris = _box(lo[0], hi[0], lo[1], hi[1], lo[2], hi[2])
            moved = []
            for u, s, z in corners:
                u, s = pose_point(pose, u, s)
                moved.append((u0 + u, s * sign_in, z0 + z))
            if sign_in < 0:
                tris = [(a, c, b) for a, b, c in tris]       # the mirror keeps faces outward
            boxes.setdefault(f'{opening.kind}_{role}', []).append((moved, tris))
        return _parts(boxes, x1, y1, ux, uy, nx, ny, zb)

    door = opening.kind == 'door'
    frame = 'door_frame' if door else 'window_frame'
    add(frame, u0, u0 + fw, -fd, fd, z0, z1)
    add(frame, u1 - fw, u1, -fd, fd, z0, z1)
    add(frame, u0 + fw, u1 - fw, -fd, fd, z1 - fw, z1)
    if door:
        add('door_leaf', u0 + fw, u1 - fw, -LEAF / 2, LEAF / 2, z0, z1 - fw)
    else:
        add(frame, u0 + fw, u1 - fw, -fd, fd, z0, z0 + fw)
        inner0, inner1 = u0 + fw, u1 - fw
        if inner1 - inner0 > 1.2:  # wide window: two sashes
            mid = (inner0 + inner1) / 2.0
            add(frame, mid - fw / 2, mid + fw / 2, -fd, fd, z0 + fw, z1 - fw)
            add('window_glass', inner0, mid - fw / 2, -GLASS / 2, GLASS / 2, z0 + fw, z1 - fw)
            add('window_glass', mid + fw / 2, inner1, -GLASS / 2, GLASS / 2, z0 + fw, z1 - fw)
        else:
            add('window_glass', inner0, inner1, -GLASS / 2, GLASS / 2, z0 + fw, z1 - fw)

    return _parts(boxes, x1, y1, ux, uy, nx, ny, zb)


def _parts(boxes, x1, y1, ux, uy, nx, ny, zb):
    parts = []
    for key, items in boxes.items():
        verts: List[Tuple[float, float, float]] = []; tris: List[Tuple[int, int, int]] = []
        for corners, box_tris in items:
            base = len(verts)
            for u, n, z in corners:
                verts.append((x1 + ux * u + nx * n, y1 + uy * u + ny * n, zb + z))
            tris += [(a + base, b + base, c + base) for a, b, c in box_tris]
        parts.append((key, tuple(verts), tuple(tris)))
    return parts
