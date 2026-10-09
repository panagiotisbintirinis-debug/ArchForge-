"""Storey slabs (πλάκα ορόφου) and slab openings (οπές πλάκας, αίθρια, κενά).

Owner: «Να μπορώ στις πλάκες να κόβω τμήματα εσωτερικά για αίθρια ή εσωτερικά
μπαλκόνια. Εδώ πλάκα μπαίνει μόνο στο ένα τμήμα.»  Cause: one slab per room,
bound to the room's identity — when a room is extended or merged (a wall
removed, walls added) its identity changes, the slab goes dormant and the
new part stays without a slab.

A **storey slab** is a ``room_floor`` / ``room_roof`` with ``scope='storey'``
and ``level_z``: its outline is derived live from every closed room of the
storey (their union, so no overlaps and no gaps along interior walls):

* floor: on the wall axes (the rule of the room floors);
* roof (δώμα): only over the rooms that need a roof (nothing built above
  them, no tiled roof over them — ``roof_need``), offset to the outer face
  of the walls plus ``overhang`` (outer edges) — the rule of the flat roofs.

Rooms that keep a slab of their own (an older per-room floor/roof) are left
out, so two slabs never overlap.

A **slab opening** (``kind='slab_opening'``) cuts the slabs of its storey:

* ``points`` — drawn outline (rectangle or polygon), or ``room_id`` — a whole
  room (an atrium follows its walls);
* ``cuts`` — ``floor`` (the storey's floor slab: an inner balcony / double
  height over the storey below), ``roof`` (the slab over the storey: atrium,
  light well) or ``both``;
* ``use`` — atrium / inner balcony / void (for the name and the take-off).

A room opening is taken out *before* the roof offset, so the roof slab still
covers the atrium walls up to their inner face.  Structure: the opening area
is excluded from the slab panels and flagged «ενίσχυση περιμετρικά της οπής —
προς έλεγχο μηχανικού» (``structure/slabs.py``).
"""
from __future__ import annotations

import math

from archforge.geometry.regions import islands_area, offset_loop, region, region_loops, group_loops, signed_area, winding

CUTS = {'floor': 'Δάπεδο (κενό προς τον κάτω όροφο)', 'roof': 'Οροφή / δώμα (ανοιχτό προς τα πάνω)',
        'both': 'Δάπεδο και οροφή (σε όλο το ύψος)'}
USES = {'atrium': 'Αίθριο', 'inner_balcony': 'Εσωτερικό μπαλκόνι / κενό διπλού ύψους', 'void': 'Οπή πλάκας'}
DEFAULT_CUTS = {'atrium': 'both', 'inner_balcony': 'floor', 'void': 'floor'}
SLAB_KINDS = ('room_floor', 'room_roof', 'room_ceiling')
SCOPES = ('room', 'storey')
REINFORCEMENT_NOTE = 'ενίσχυση περιμετρικά της οπής — προς έλεγχο μηχανικού'
MIN_SIDE = 0.20          # smallest drawn opening side (m)


# --- schema validators (core/model.py) ---------------------------------------------------

def validate_cuts(v):
    v = str(v)
    if v not in CUTS:
        raise ValueError('slab opening cuts must be floor, roof or both')
    return v


def validate_use(v):
    v = str(v)
    if v not in USES:
        raise ValueError('slab opening use must be atrium, inner_balcony or void')
    return v


def validate_scope(v):
    v = str(v)
    if v not in SCOPES:
        raise ValueError('slab scope must be room or storey')
    return v


def validate_opening(p):
    """Checks across fields: an outline or a room, never neither."""
    if not p.get('room_id') and not p.get('points'):
        raise ValueError('slab opening needs points or a room')
    if 'level_z' not in p:
        raise ValueError('slab opening needs its storey level_z')
    if p.get('points'):
        xs = [q[0] for q in p['points']]
        ys = [q[1] for q in p['points']]
        if max(xs) - min(xs) < MIN_SIDE - 1e-9 or max(ys) - min(ys) < MIN_SIDE - 1e-9:
            raise ValueError(f'slab opening must be at least {MIN_SIDE * 100:.0f} cm across')
    return p


# --- openings -------------------------------------------------------------------------------

def opening_polygon(doc, entity, tolerance=1e-5):
    """Live outline of a slab opening (its room's face for a room opening), or None."""
    p = entity.params
    if p.get('room_id'):
        from archforge.architecture.rooms import find_room_face_by_id
        found = find_room_face_by_id(doc, p['room_id'], tolerance=tolerance)
        return [tuple(map(float, q)) for q in found[0].polygon] if found else None
    return [(float(q[0]), float(q[1])) for q in p['points']]


def openings_for(doc, level_z, target, tolerance=1e-4):
    """``[(entity, polygon)]`` of the openings of storey ``level_z`` cutting its ``floor`` or ``roof``."""
    out = []
    for e in doc.entities.values():
        if e.kind != 'slab_opening' or not e.visible:
            continue
        if abs(float(e.params['level_z']) - float(level_z)) > tolerance:
            continue
        if e.params.get('cuts', 'both') not in (target, 'both'):
            continue
        poly = opening_polygon(doc, e)
        if poly and len(poly) >= 3:
            out.append((e, poly))
    return out


def slab_target(kind):
    return 'floor' if kind == 'room_floor' else 'roof'


def opening_area(doc, entity):
    poly = opening_polygon(doc, entity)
    return abs(signed_area(poly)) if poly else 0.0


def opening_name(use):
    return USES.get(use, USES['void'])


def railing_points(doc, entity, inset=0.05):
    """Closed railing path around an opening: on the slab side, ``inset`` from the edge (cm of the channel)."""
    poly = opening_polygon(doc, entity)
    if not poly:
        return None
    loop = poly if signed_area(poly) > 0 else poly[::-1]
    # Outwards from the opening = onto the slab.
    path = offset_loop(loop, [inset] * len(loop))
    return [[round(x, 4), round(y, 4)] for x, y in path]


# --- storey slab geometry ----------------------------------------------------------------------

_CACHE = {}


def _fingerprint(doc, entity):
    keys = []
    for e in doc.entities.values():
        if e.kind in ('wall', 'slab_opening', 'pitched_roof') or (e.kind in SLAB_KINDS and e.id != entity.id):
            keys.append((e.id, e.kind, e.visible, repr(sorted(e.params.items()))))
    return hash((tuple(sorted(keys)), repr(sorted(entity.params.items())), repr(sorted(doc.room_bindings))))


def _own_slab_faces(doc, kind, level_z):
    """Signatures of the rooms of the storey that keep a per-room slab of this kind."""
    from archforge.architecture.roof_need import room_face_of
    out = set()
    for e in doc.entities.values():
        if e.kind != kind or e.params.get('scope') == 'storey':
            continue
        if kind == 'room_roof' and e.params.get('roof_type', 'flat') != 'flat':
            continue
        found = room_face_of(doc, e)
        if found is not None and abs(found[1] - level_z) < 1e-4:
            out.add(found[0].signature)
    return out


def storey_faces(doc, kind, level_z):
    """Room faces of the storey covered by its storey slab of ``kind``."""
    from archforge.architecture.roof_need import COVERED, coverage, under_pitched_roof
    faces = doc.active_room_faces(z=level_z)
    own = _own_slab_faces(doc, kind, level_z)
    out = []
    for f in faces:
        if f.signature in own:
            continue
        if kind == 'room_roof':
            # The slab over a storey is one plate, under a terrace or under the next storey alike
            # (owner: «πάλι μέρη της πλάκας εξαφανίζονται»); only a tiled roof replaces it.
            if under_pitched_roof(doc, f.polygon, level_z):
                continue
        out.append(f)
    return out


def _walls_at(doc, level_z):
    return [w for w in doc.entities.values() if w.kind == 'wall' and w.visible and abs(float(w.params['z']) - level_z) < 1e-4]


def _edge_wall(walls, a, b, tolerance=1e-4):
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    best = None
    for w in walls:
        p = w.params
        x1, y1, x2, y2 = float(p['x1']), float(p['y1']), float(p['x2']), float(p['y2'])
        wl = math.hypot(x2 - x1, y2 - y1)
        if wl < 1e-9 or abs(dx * (y2 - y1) - dy * (x2 - x1)) / (length * wl) > 1e-4:
            continue
        if abs((mx - x1) * (y2 - y1) - (my - y1) * (x2 - x1)) / wl > tolerance:
            continue
        t = ((mx - x1) * (x2 - x1) + (my - y1) * (y2 - y1)) / (wl * wl)
        if -1e-6 <= t <= 1 + 1e-6 and (best is None or float(p['thickness']) > float(best.params['thickness'])):
            best = w
    return best


def _roof_islands(doc, faces, level_z, atria, overhang, edge_offsets, tolerance):
    """Union of the roof faces minus the atria, pushed out to the wall faces (and eaves)."""
    walls = _walls_at(doc, level_z)
    loops = region_loops([f.polygon for f in faces] + atria,
                         lambda x, y: any(winding(x, y, f.polygon) for f in faces) and not any(winding(x, y, a) for a in atria),
                         tolerance)
    # An edge shared with another room of the storey (under the upper storey, own roof) stops at the wall axis.
    from archforge.architecture.rooms import _on_any_edge
    roofed = {f.signature for f in faces}
    others = [tuple(f.polygon) for f in doc.active_room_faces(z=level_z) if f.signature not in roofed]
    offsets = []
    for loop in loops:
        outer = signed_area(loop) > 0
        dist = []
        for i, a in enumerate(loop):
            b = loop[(i + 1) % len(loop)]
            w = _edge_wall(walls, a, b)
            d = 0.0
            if w is not None and not _on_any_edge(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), others):
                d = 0.5 * float(w.params['thickness']) + float(edge_offsets.get(w.id, 0.0)) + (float(overhang) if outer else 0.0)
            dist.append(d)
        offsets.append(offset_loop(loop, dist))
    if not offsets:
        return []

    def inside(x, y):
        return sum(winding(x, y, q) for q in offsets) > 0
    return group_loops(region_loops(offsets, inside, tolerance))


def _slab_over_storey_below(doc, level_z, tolerance=1e-5):
    """Outer loops of the storey roof slabs that end at ``level_z`` (the plate this storey stands on)."""
    out = []
    for e in doc.entities.values():
        if e.kind != 'room_roof' or e.params.get('scope') != 'storey':
            continue
        lz = float(e.params['level_z'])
        if lz >= level_z - 1e-4 or abs(lz + float(e.params.get('offset_z', 0.0)) - level_z) > .05:
            continue
        g = storey_slab_geometry(doc, e, tolerance)
        if g:
            out += [outer for outer, _holes in g['islands']]
    return out


def storey_slab_geometry(doc, entity, tolerance=1e-5):
    """Live outline of a storey slab: ``{'islands', 'points', 'holes', 'z', 'thickness', …}`` or None."""
    fp = _fingerprint(doc, entity)
    hit = _CACHE.get((id(doc), entity.id))
    if hit is not None and hit[0] == fp:
        return hit[1]
    p = entity.params
    level_z = float(p['level_z'])
    target = slab_target(entity.kind)
    faces = storey_faces(doc, entity.kind, level_z)
    openings = openings_for(doc, level_z, target)
    result = None
    if faces:
        drawn = [poly for e, poly in openings if not e.params.get('room_id')]
        rooms = [poly for e, poly in openings if e.params.get('room_id')]
        if entity.kind == 'room_roof':
            islands = _roof_islands(doc, faces, level_z, rooms, p.get('overhang', 0.0), p.get('edge_offsets') or {}, tolerance)
            if drawn and islands:
                islands = region([o for o, _h in islands], [h for _o, hs in islands for h in hs] + drawn, tolerance)
        else:
            # Above another storey the floor plate is the slab over that storey: only what overhangs it
            # (cantilever, balcony) is left to this floor slab, so nothing is counted twice.
            below = [poly for poly in _slab_over_storey_below(doc, level_z, tolerance)]
            islands = region([f.polygon for f in faces], rooms + drawn + below, tolerance)
        if islands:
            islands.sort(key=lambda isl: -abs(signed_area(isl[0])))
            wall_ids = tuple(dict.fromkeys(w for f in faces for w in f.wall_ids))
            result = {'points': islands[0][0], 'holes': islands[0][1], 'islands': islands,
                      'z': level_z + float(p.get('offset_z', 0.0)), 'thickness': float(p['thickness']),
                      'room_id': None, 'room_signature': '', 'wall_ids': wall_ids, 'level_z': level_z,
                      'area': islands_area(islands), 'openings': tuple(e.id for e, _poly in openings)}
    if len(_CACHE) > 256:
        _CACHE.clear()
    _CACHE[(id(doc), entity.id)] = (fp, result)
    return result


def cut_room_slab(doc, entity, geometry, tolerance=1e-5):
    """Per-room slab outline minus the openings of its storey (adds ``islands``/``holes``); None when nothing is left."""
    if geometry is None:
        return None
    from archforge.architecture.rooms import find_room_face, find_room_face_by_id
    p = entity.params
    found = find_room_face_by_id(doc, p['room_id']) if p.get('room_id') else find_room_face(doc, p.get('room_signature', ''))
    base_z = found[1] if found else geometry['z'] - float(p.get('offset_z', 0.0))
    openings = openings_for(doc, base_z, slab_target(entity.kind))
    if not openings:
        geometry['islands'] = [(list(geometry['points']), [])]
        geometry['holes'] = []
        return geometry
    islands = region([geometry['points']], [poly for _e, poly in openings], tolerance)
    if not islands:
        return None
    islands.sort(key=lambda isl: -abs(signed_area(isl[0])))
    geometry.update(points=islands[0][0], holes=islands[0][1], islands=islands)
    return geometry


# --- commands -----------------------------------------------------------------------------------

def storey_slab_name(kind, level_name):
    storey = 'Ισόγειο' if level_name in ('Ground', 'XY', '') else str(level_name)
    return ('Πλάκα δαπέδου' if kind == 'room_floor' else 'Πλάκα δώματος') + f' — {storey}'


def _roof_offset(doc, level_z):
    tops = sorted(float(w.params['z']) + float(w.params['height']) for w in _walls_at(doc, level_z))
    return (tops[len(tops) // 2] - level_z) if tops else 2.7


def storey_slab_plan(doc, kind, level_z, level_name='', thickness=None):
    """``(entity or None, [ids to remove])``: one slab of ``kind`` for the storey, replacing its per-room ones."""
    from archforge.core.model import Entity
    from archforge.architecture.roof_need import room_face_of
    level_z = float(level_z)
    existing = [e for e in doc.entities.values() if e.kind == kind and e.params.get('scope') == 'storey'
                and abs(float(e.params['level_z']) - level_z) < 1e-4]
    remove = []
    for e in doc.entities.values():
        if e.kind != kind or e.params.get('scope') == 'storey':
            continue
        if kind == 'room_roof' and e.params.get('roof_type', 'flat') != 'flat':
            continue
        found = room_face_of(doc, e)
        if found is not None:
            if abs(found[1] - level_z) < 1e-4:
                remove.append(e.id)
        else:
            # A dormant slab of a room that no longer exists (extended / merged): it goes too.
            binding = doc.room_bindings.get(e.params.get('room_id'), {})
            if abs(float(binding.get('z', level_z)) - level_z) < 1e-4:
                remove.append(e.id)
    if existing:
        return None, remove
    if kind == 'room_floor':
        params = {'scope': 'storey', 'level_z': level_z, 'thickness': float(thickness or .15), 'offset_z': 0.0}
    else:
        params = {'scope': 'storey', 'level_z': level_z, 'thickness': float(thickness or .20),
                  'offset_z': _roof_offset(doc, level_z), 'roof_type': 'flat', 'overhang': 0.0}
    return Entity(kind, params, name=storey_slab_name(kind, level_name)), remove


def storey_slab_command(doc, kind, level_z, level_name='', thickness=None):
    """One undo: the storey slab added and the per-room slabs of the storey removed; None when nothing to do."""
    from archforge.core.commands import AddEntity, CompositeCommand, DeleteEntities
    entity, remove = storey_slab_plan(doc, kind, level_z, level_name, thickness)
    if entity is None and not remove:
        return None, None
    return CompositeCommand([DeleteEntities(remove) if remove else None, AddEntity(entity) if entity else None],
                            'Πλάκα ορόφου'), entity


def opening_entity(doc, points=None, room_id=None, use='void', cuts=None, level_z=None):
    from archforge.core.model import Entity
    level_z = float(doc.work_plane.origin[2]) if level_z is None else float(level_z)
    params = {'level_z': level_z, 'use': use, 'cuts': cuts or DEFAULT_CUTS[use]}
    if room_id:
        params['room_id'] = str(room_id)
    else:
        params['points'] = [[round(float(x), 4), round(float(y), 4)] for x, y in points]
    return Entity('slab_opening', params, name=opening_name(use))


def room_opening_entity(doc, x, y, use='atrium'):
    """An opening that is the whole room at (x, y) of the active storey (follows its walls), or None."""
    from archforge.architecture.room_identity import reconcile_room_bindings
    from archforge.geometry.regions import point_in_polygon
    z = float(doc.work_plane.origin[2])
    for face, room_id in reconcile_room_bindings(doc, z=z):
        if point_in_polygon(float(x), float(y), face.polygon):
            if any(e.kind == 'slab_opening' and e.params.get('room_id') == room_id for e in doc.entities.values()):
                return None
            return opening_entity(doc, room_id=room_id, use=use, level_z=z)
    return None


def plan_cross(poly):
    """Two diagonals of an opening for the plan (Greek practice for a void in the slab)."""
    n = len(poly)
    if n == 4:
        return [(poly[0], poly[2]), (poly[1], poly[3])]
    from archforge.geometry.regions import point_in_polygon
    best = []
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            a, b = poly[i], poly[j]
            if not point_in_polygon((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, poly):
                continue
            best.append((math.hypot(b[0] - a[0], b[1] - a[1]), (a, b)))
    best.sort(key=lambda t: -t[0])
    if not best:
        return []
    first = best[0][1]
    # The second diagonal: the longest one that shares no corner with the first (a cross, not a fan).
    second = next((seg for _l, seg in best[1:] if not set(seg) & set(first)), None)
    return [first] + ([second] if second else [])
