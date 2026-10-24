"""Walls drawn by a face (owner 21/10: «ο τοίχος σχεδιάζεται από τη μέση του και όχι από κάποια άκρη — δεν μπορείς
να κρατήσεις ευθεία» · «όταν ρωτάει από πού μετράμε, ο τοίχος να συνδέεται ανάλογα»).

The line the human draws is one face of the wall; the wall's body lies to the left or to the right of it (seen
along the drawing direction).  ``side`` is +1 (left), -1 (right) or 0 (the line is the axis, as before).

«Αυτόματα» follows the project brief (Στοιχεία έργου ▸ από πού μετράμε): measured outside → the body goes inside
the outline, measured inside → outside.  Which side is inside is known from the first corner (the turn of the
outline); until then the guess is «left», and the first wall is turned over at that corner if the guess was wrong.

Consecutive walls meet where their axes cross, so the faces drawn stay exactly where they were drawn.
"""
from __future__ import annotations

import math

SIDES = {'axis': 0, 'left': 1, 'right': -1}
LABELS = {'auto': 'Αυτόματα (από τα Στοιχεία έργου)', 'axis': 'Άξονας τοίχου', 'left': 'Αριστερή παρειά',
          'right': 'Δεξιά παρειά'}


def offset_segment(a, b, side, thickness):
    """The wall's axis for the face a→b with the body on ``side``."""
    L = math.dist(a, b)
    if not side or L < 1e-12:
        return tuple(a), tuple(b)
    h = side * thickness / 2.0
    nx, ny = -(b[1] - a[1]) / L * h, (b[0] - a[0]) / L * h
    return (a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)


def body_polygon(a, b, side, thickness):
    """The wall's outline in plan (for the preview): between the drawn line and the line ``thickness`` away."""
    L = math.dist(a, b)
    if L < 1e-12:
        return None
    nx, ny = -(b[1] - a[1]) / L, (b[0] - a[0]) / L
    if side:
        o, i = 0.0, side * thickness
    else:
        o, i = -thickness / 2.0, thickness / 2.0
    return ((a[0] + nx * o, a[1] + ny * o), (b[0] + nx * o, b[1] + ny * o),
            (b[0] + nx * i, b[1] + ny * i), (a[0] + nx * i, a[1] + ny * i))


def turn(d1, d2):
    """+1 when going from direction d1 to d2 turns left, -1 right, 0 straight on."""
    c = d1[0] * d2[1] - d1[1] * d2[0]
    return 0 if abs(c) < 1e-6 else (1 if c > 0 else -1)


def auto_side(measure, turning):
    """Body side for the brief's measure, given the outline's turning (+1 left / -1 right; 0 unknown → left)."""
    inside = turning or 1                    # turning left (counter-clockwise): the inside is on the left
    if measure == 'exterior':
        return inside
    if measure == 'interior':
        return -inside
    return 0


def intersect(a1, a2, b1, b2):
    """Crossing of the lines a1–a2 and b1–b2 (None when parallel)."""
    d = (a1[0] - a2[0]) * (b1[1] - b2[1]) - (a1[1] - a2[1]) * (b1[0] - b2[0])
    if abs(d) < 1e-12:
        return None
    t = ((a1[0] - b1[0]) * (b1[1] - b2[1]) - (a1[1] - b1[1]) * (b1[0] - b2[0])) / d
    return (a1[0] + t * (a2[0] - a1[0]), a1[1] + t * (a2[1] - a1[1]))


# --------------------------------------------------------------------------------------------- which face is outside
# Owner 23/10: «όταν βάζουμε υλικά σε τοίχο μέσα / έξω είναι ανάποδα — το εξωτερικό αλλάζει από μέσα». The wall's
# side A ('exterior' role, its +normal = left of x1→x2) is only where it was drawn from: a room drawn anticlockwise
# has side A inside. What faces the open air is read from the building: ``outside_sign`` is +1 when side A faces
# out (or the wall has rooms on both sides / none), −1 when side B does. Labels, the assembly's layer order and the
# finishing colours follow it; the stored data does not change.
_OUTSIDE = {'key': None, 'value': {}}


def outside_signs(doc):
    """``{wall_id: +1 | -1}`` for every wall whose side B faces the open air (others are absent = +1)."""
    walls = [e for e in doc.entities.values() if e.kind == 'wall']
    key = tuple((w.id, repr(sorted(w.params.items()))) for w in walls)
    if _OUTSIDE['key'] == key:
        return _OUTSIDE['value']
    from archforge.mep.ventilation import exterior_walls
    out = {}
    for z in sorted({round(float(w.params.get('z', 0.0)), 4) for w in walls}):
        for w, (nx, ny) in exterior_walls(doc, z):
            p = w.params
            ax, ay = -(float(p['y2']) - float(p['y1'])), float(p['x2']) - float(p['x1'])    # side A's direction
            if ax * nx + ay * ny < 0:
                out[w.id] = -1
    _OUTSIDE['key'], _OUTSIDE['value'] = key, out
    return out


def outside_sign(doc, wall_id):
    return outside_signs(doc).get(wall_id, 1)


def side_roles(doc, wall_id):
    """``(outside role, inside role)`` of an exterior wall — ``('exterior', 'interior')`` or swapped — or None for a
    wall with rooms (or nothing) on both sides."""
    from archforge.mep.ventilation import exterior_walls
    w = doc.get(wall_id)
    if not any(e.id == wall_id for e, _n in exterior_walls(doc, float(w.params.get('z', 0.0)))):
        return None
    return ('interior', 'exterior') if outside_sign(doc, wall_id) < 0 else ('exterior', 'interior')
