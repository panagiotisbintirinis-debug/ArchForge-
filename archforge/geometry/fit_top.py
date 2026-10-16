"""One way to shape the top of any placed object (owner 14/10).

«Η κατασκευή είναι ένα για όλα τα αντικείμενα· ό,τι καμπύλες μπορεί να πάρει το υλικό με το Sculpt μπορούν
να πάρουν όλα τα υλικά· πρέπει απλά να έχουν κανόνες χωρίς να έχουν κανόνες.» · «βάζω ένα ντουλάπι ψηλό κάτω
από σκάλα ή στέγη — το ντουλάπι πρέπει να ακολουθεί την οροφή».

* ``top_heights`` (any object with x, y, z, width, depth, rotation — cabinet, library object …): the height of
  its top at the four plan corners (local −w/2,−d/2 → +w/2,−d/2 → +w/2,+d/2 → −w/2,+d/2).  The mesh is
  stretched above its base (plinth kept) so the top runs through them — a free shape, not a type.
* ``fit_to_ceiling`` is one rule that fills them: the ceiling over each corner (the underside of a stair,
  a tiled roof, the slab of the storey above), minus a gap.  The human applies it at will and can
  change or drop it; nothing is locked.
"""
from __future__ import annotations

import math

GAP = 0.02
MIN_HEIGHT = 0.20


def _local_corners(p):
    w, d = float(p['width']), float(p['depth'])
    return ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))


def _to_world(p, lx, ly):
    a = math.radians(float(p.get('rotation', 0.0)))
    return (float(p['x']) + math.cos(a) * lx - math.sin(a) * ly, float(p['y']) + math.sin(a) * lx + math.cos(a) * ly)


def _to_local(p, x, y):
    a = math.radians(float(p.get('rotation', 0.0)))
    dx, dy = x - float(p['x']), y - float(p['y'])
    return (math.cos(a) * dx + math.sin(a) * dy, -math.sin(a) * dx + math.cos(a) * dy)


def top_at(p, lx, ly):
    """Top height (above the object's base) at a local plan point, bilinear between the corners."""
    h = p.get('top_heights')
    if not h:
        return float(p['height'])
    w, d = float(p['width']), float(p['depth'])
    u = min(1.0, max(0.0, (lx + w / 2) / w)); v = min(1.0, max(0.0, (ly + d / 2) / d))
    return (h[0] * (1 - u) * (1 - v) + h[1] * u * (1 - v) + h[2] * u * v + h[3] * (1 - u) * v)


def apply_top_heights(p, vertices):
    """World vertices of an object stretched so its top follows ``top_heights`` (plinth kept)."""
    if not p.get('top_heights'):
        return tuple(vertices)
    base = float(p.get('z', 0.0)); height = float(p['height'])
    plinth = min(float(p.get('plinth', 0.0)), height * 0.5)
    out = []
    for x, y, z in vertices:
        dz = z - base
        if dz <= plinth + 1e-9:
            out.append((x, y, z)); continue
        target = top_at(p, *_to_local(p, x, y))
        out.append((x, y, base + plinth + (dz - plinth) * (target - plinth) / max(1e-9, height - plinth)))
    return tuple(out)


# --- the rule: up to the ceiling --------------------------------------------------------------------

def _stair_underside(doc, x, y, floor_z):
    from archforge.architecture import stair_options as SO
    from archforge.architecture.railings import _flights
    from archforge.architecture.stairs import candidate_from_params
    best = None
    for e in doc.entities.values():
        if e.kind != 'stair' or abs(float(e.params.get('lower_z', 0.0)) - floor_z) > 0.05:
            continue
        p = e.params
        try:
            c = candidate_from_params(p)
            flights = _flights(c)
        except ValueError:
            continue
        a = math.radians(c.angle_deg); ca, sa = math.cos(a), math.sin(a)
        lx = ca * (x - c.origin[0]) + sa * (y - c.origin[1]); ly = -sa * (x - c.origin[0]) + ca * (y - c.origin[1])
        offset = SO.underside_offset(p)
        pitch = c.riser_height / c.tread_depth
        for (sx, sy), (dx, dy), m, k0, _end in flights:
            s = (lx - sx) * dx + (ly - sy) * dy
            across = -(lx - sx) * dy + (ly - sy) * dx
            if not (-1e-6 <= s <= m * c.tread_depth + 1e-6 and abs(across) <= c.width / 2 + 1e-6):
                continue
            base = float(p['lower_z']) + k0 * c.riser_height
            if offset is None:                         # solid stair: its steps are the ceiling
                z = base + (min(m - 1, int(s / c.tread_depth)) + 1) * c.riser_height
            else:
                z = base + s * pitch + offset
            best = z if best is None else min(best, z)
        if c.layout in ('l', 'u'):
            # The landing between the flights is a ceiling too (walk-through 14/10: a tall cupboard
            # under it went up through it).
            first = max(1, c.tread_count // 2)
            if c.layout == 'l':
                cx, cy, sx_, sy_ = first * c.tread_depth + c.landing_depth / 2, 0.0, c.landing_depth, c.landing_depth
            else:
                off = c.turn_direction * (c.width + 0.20)
                cx, cy, sx_, sy_ = first * c.tread_depth + c.landing_depth / 2, off / 2, c.landing_depth, abs(off) + c.width
            if abs(lx - cx) <= sx_ / 2 + 1e-6 and abs(ly - cy) <= sy_ / 2 + 1e-6:
                top = float(p['lower_z']) + first * c.riser_height
                thick = {'solid': top - float(p['lower_z']), 'slab': SO.SLAB, 'cantilever': SO.TREAD_CANTILEVER * 1.5}.get(
                    SO.structure(p), (SO.TREAD_TIMBER if SO.structure(p) == 'timber' else SO.TREAD_STEEL) + 0.10)
                z = top - thick
                best = z if best is None else min(best, z)
    return best


def _roof_underside(doc, x, y):
    from archforge.geometry.regions import point_in_polygon
    from archforge.structure.timber_roof import height_at, planes, rafter_section
    best = None
    for e in doc.entities.values():
        if e.kind != 'pitched_roof':
            continue
        p = e.params
        try:
            depth = rafter_section(p)[1]
            for plane in planes(p):
                if point_in_polygon(x, y, plane[0]):
                    z = height_at(p, plane, x, y) - depth
                    best = z if best is None else min(best, z)
        except Exception:
            continue
    return best


def _storey_ceiling(doc, floor_z):
    """Underside of the slab over the storey (its «πλάκα από πάνω», else the next level − 20 cm)."""
    for e in doc.entities.values():
        if e.kind == 'room_roof' and e.params.get('scope') == 'storey' \
                and abs(float(e.params.get('level_z', 0.0)) - floor_z) < 1e-3:
            return floor_z + float(e.params.get('offset_z', 0.0))
    from archforge.architecture.stairs import next_level_above
    above = next_level_above(doc, floor_z)
    return None if above is None else float(above[0]) - 0.20


def ceiling_at(doc, x, y, floor_z):
    """The lowest thing over (x, y) of the storey at ``floor_z`` (absolute z), or None."""
    found = [z for z in (_stair_underside(doc, x, y, floor_z), _roof_underside(doc, x, y), _storey_ceiling(doc, floor_z))
             if z is not None and z > floor_z]
    return min(found) if found else None


def fit_to_ceiling(doc, entity):
    """Changes for ``entity`` so its top follows the ceiling over each corner (one UpdateEntity)."""
    p = entity.params
    floor_z = float(p.get('z', 0.0))
    heights = []
    for lx, ly in _local_corners(p):
        z = ceiling_at(doc, *_to_world(p, lx, ly), floor_z)
        if z is None:
            raise ValueError('Δεν βρέθηκε οροφή από πάνω (ούτε σκάλα, στέγη ή όροφος)')
        heights.append(round(z - floor_z - GAP, 3))
    if min(heights) < MIN_HEIGHT:
        raise ValueError(f'Κάτω από την οροφή μένουν μόνο {min(heights) * 100:.0f} cm σε μια γωνία — μετακίνησέ το')
    if max(heights) - min(heights) < 0.005:
        return {'height': heights[0], 'top_heights': []}
    return {'height': max(heights), 'top_heights': heights}
