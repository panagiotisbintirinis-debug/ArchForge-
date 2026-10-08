"""Railings (κάγκελα) for balconies, terraces, openings and stairs.

``kind='railing'`` params:

* ``points``: plan polyline ``[[x, y], ...]`` or ``[[x, y, dz], ...]``; ``dz``
  is the walking line at that point above ``z`` (the nosing line of a
  stair), so one railing can follow a flight;
* ``z``: storey / base elevation; ``closed`` 1 = the last point joins the first;
* ``height``: top of the handrail above the walking line;
* ``railing_type`` (see ``TYPES``), ``handrail`` shape and ``handrail_size``,
  ``post_spacing`` (largest bay), ``gap`` (largest clear gap of the infill),
  ``base_height`` (curb / ποδιά under the railing, 0 = none) and ``metal``
  (finish of the metal parts).

Anchors (practice — προμελέτη, προς έλεγχο):

* height ≥ 1.00 m on balconies, terraces and roofs (ΝΟΚ ν. 4067/2012 /
  Κτιριοδομικός Κανονισμός — πηγή προς έλεγχο); on stairs 0.90 m above the
  nosing line (common practice, προς έλεγχο);
* clear gap of the infill and under the bottom rail ≤ 10–11 cm, so that a
  child's head cannot pass (κανόνας σφαίρας 10 cm, ευρωπαϊκή πρακτική — προς έλεγχο);
* a post at every end and corner and at most every 1.2–1.5 m (κατασκευαστική πρακτική);
* horizontal bars and cables can be climbed: not where small children play.

The geometry is derived: every member is a closed solid (swept profile,
hexahedron or vertical prism) with a role — handrail, post, infill, glass,
base — that carries its material (``surface_materials[role]`` overrides it).
"""
from __future__ import annotations

import math

DEFAULT_HEIGHT = 1.00        # balconies / terraces (ΝΟΚ — προς έλεγχο)
STAIR_HEIGHT = 0.90          # above the nosing line (πρακτική — προς έλεγχο)
MAX_GAP = 0.11               # clear gap of the infill (κανόνας σφαίρας 10 cm, ανοχή 1 cm)
MAX_POST_SPACING = 1.5
BOTTOM_CLEAR = 0.05          # floor (or nosing line) to the bottom rail / glass
SIDE_DROP = 0.20             # posts on a flight are fixed on the side of the stair, below the nosing line
GLASS = 0.0175               # laminated 8+8 mm (αντιθραυστικό) — typical, προς έλεγχο από τον προμηθευτή
CHANNEL = (0.10, 0.11)       # recessed aluminium base profile: width, depth (10 cm in the slab, 1 cm lip)
PARAPET = 0.20               # masonry parapet thickness (τούβλο + σοβάδες)
BASE_WIDTH = 0.15            # concrete curb / ποδιά under a railing

TYPES = {
    # type: label, post size and sides (0 = none), infill member, default handrail and finish
    'balusters': dict(label='Κάγκελα κάθετα', post=.04, sides=4, bar=.016, bottom=(.03, .02),
                      handrail='square', size=.045, metal='iron'),
    'bars': dict(label='Οριζόντιες ράβδοι', post=.05, sides=4, bar=.016, handrail='square', size=.05, metal='aluminium'),
    'glass_posts': dict(label='Τζάμι με ορθοστάτες', post=.045, sides=8, handrail='round', size=.042, metal='inox'),
    'glass_channel': dict(label='Τζάμι σε χωνευτό προφίλ', post=0.0, handrail='square', size=.03, metal='aluminium'),
    'panel': dict(label='Πάνελ συμπαγές', post=.05, sides=4, sheet=.006, bottom=(.04, .02),
                  handrail='square', size=.05, metal='aluminium'),
    'perforated': dict(label='Πάνελ διάτρητο', post=.05, sides=4, sheet=.006, bottom=(.04, .02),
                       handrail='square', size=.05, metal='aluminium'),
    'cable': dict(label='Συρματόσχοινο inox', post=.045, sides=8, bar=.006, handrail='round', size=.042, metal='inox'),
    'timber': dict(label='Ξύλινο', post=.09, sides=4, bar=.04, bottom=(.07, .045), handrail='flat', size=.09, metal='iron'),
    'parapet': dict(label='Κτιστό στηθαίο', post=0.0, handrail='flat', size=.25, metal='iron'),
}
HANDRAILS = {'round': 'Στρογγυλή', 'square': 'Τετράγωνη', 'flat': 'Πλατιά (λάμα / ξύλο / ποδιά)', 'none': 'Χωρίς'}
METALS = {'iron': 'Σίδερο βαμμένο', 'aluminium': 'Αλουμίνιο', 'inox': 'Ανοξείδωτο (inox)'}
ROLES = ('handrail', 'post', 'infill', 'glass', 'base')
ROLE_NAMES = {'handrail': 'Κουπαστή', 'post': 'Ορθοστάτες', 'infill': 'Πλήρωση', 'glass': 'Τζάμι', 'base': 'Βάση / ποδιά'}
PARAM_NAMES = {'height': 'Ύψος κουπαστής (m)', 'handrail_size': 'Διάσταση κουπαστής (m)',
               'post_spacing': 'Ορθοστάτες ανά (m, μέγιστο)', 'gap': 'Καθαρό κενό πλήρωσης (m, μέγιστο)',
               'base_height': 'Ύψος βάσης / ποδιάς (m)', 'z': 'Στάθμη (m)'}

_METAL_LOOK = {'iron': ('#33373b', .55, .35), 'aluminium': ('#4a4f55', .45, .55), 'inox': ('#c4c8cc', .22, .9)}


def default_params(railing_type, points, z=0.0, height=None, **extra):
    """Complete parameters of a new railing of ``railing_type`` along ``points``."""
    spec = TYPES[railing_type]
    stair = any(len(q) > 2 and abs(float(q[2])) > 1e-9 for q in points)
    p = {'points': [[float(v) for v in q] for q in points], 'z': float(z), 'closed': 0,
         'height': float(height if height is not None else (STAIR_HEIGHT if stair else DEFAULT_HEIGHT)),
         'railing_type': railing_type, 'handrail': spec['handrail'], 'handrail_size': spec['size'],
         'post_spacing': 1.2, 'gap': 0.10, 'base_height': 0.0, 'metal': spec['metal']}
    p.update(extra)
    return p


# --- validation (used by the Document schema) -------------------------------------------

def validate_points(v):
    if not isinstance(v, (list, tuple)) or len(v) < 2:
        raise ValueError('railing needs at least two points')
    out = []
    for q in v:
        if not isinstance(q, (list, tuple)) or len(q) not in (2, 3):
            raise ValueError('railing point must be [x, y] or [x, y, dz]')
        q = [float(c) for c in q]
        if not all(math.isfinite(c) for c in q):
            raise ValueError('railing point must be finite')
        if out and math.hypot(q[0] - out[-1][0], q[1] - out[-1][1]) < 0.01:
            raise ValueError('railing points must be at least 1 cm apart')
        out.append(q)
    _frames([q + [0.0] * (3 - len(q)) for q in out], False)     # rejects fold-backs
    return out


def validate(p):
    """Checks across fields (after each field passed its own validator)."""
    missing = {'points', 'height', 'railing_type'} - set(p)
    if missing:
        raise ValueError('railing is missing required fields: ' + ', '.join(sorted(missing)))
    if int(p.get('closed', 0)) and len(p.get('points', ())) < 3:
        raise ValueError('a closed railing needs at least three points')
    if 'height' in p and float(p['height']) > 3.0:
        raise ValueError('railing height must be at most 3 m')
    if float(p.get('base_height', 0.0)) > float(p.get('height', DEFAULT_HEIGHT)) - 0.3 and p.get('railing_type') != 'parapet':
        raise ValueError('the base (ποδιά) must stay at least 30 cm below the handrail')
    if 'post_spacing' in p and not 0.3 <= float(p['post_spacing']) <= MAX_POST_SPACING:
        raise ValueError(f'post spacing must be between 0.30 and {MAX_POST_SPACING:.2f} m')
    if 'gap' in p and not 0.02 <= float(p['gap']) <= MAX_GAP:
        raise ValueError(f'clear gap must be between 0.02 and {MAX_GAP:.2f} m (child safety)')
    if 'handrail_size' in p and not 0.02 <= float(p['handrail_size']) <= 0.40:
        raise ValueError('handrail size must be between 0.02 and 0.40 m')
    return p


# --- path ---------------------------------------------------------------------------------

def path(p):
    """World points ``[(x, y, z_walk)]`` of the walking line."""
    z = float(p.get('z', 0.0))
    return [(float(q[0]), float(q[1]), z + (float(q[2]) if len(q) > 2 else 0.0)) for q in p['points']]


def _segments(pts, closed):
    n = len(pts)
    return [(pts[i], pts[(i + 1) % n]) for i in range(n if closed else n - 1)]


def _frames(pts, closed):
    """Per-vertex plan mitre vectors (left side) for a swept profile."""
    segs = _segments(pts, closed)
    normals = []
    for a, b in segs:
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        normals.append((-(b[1] - a[1]) / L, (b[0] - a[0]) / L))
    out = []
    for k in range(len(pts)):
        before = normals[k - 1] if (k > 0 or closed) else None
        after = normals[k] if k < len(normals) else None
        if before is None or after is None:
            out.append(before or after)
            continue
        d = 1.0 + before[0] * after[0] + before[1] * after[1]
        if d < 0.03:
            raise ValueError('railing folds back on itself (angle too sharp)')
        out.append(((before[0] + after[0]) / d, (before[1] + after[1]) / d))
    return out


def length(p):
    """Running length along the railing (on a flight: along the slope), m."""
    return sum(math.dist(a, b) for a, b in _segments(path(p), bool(int(p.get('closed', 0)))))


# --- solids ----------------------------------------------------------------------------------

class _Mesh:
    def __init__(self):
        self.verts, self.tris, self.roles = [], [], []

    def solid(self, role, verts, tris):
        """Add one closed solid, turned outward (positive volume)."""
        vol = sum(_dot(verts[a], _cross(verts[b], verts[c])) for a, b, c in tris)
        if vol < 0:
            tris = [(a, c, b) for a, b, c in tris]
        base = len(self.verts)
        self.verts += [tuple(v) for v in verts]
        self.tris += [(a + base, b + base, c + base) for a, b, c in tris]
        self.roles += [role] * len(tris)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sweep(mesh, role, pts, closed, profile, h_at=None):
    """Profile ``[(o, h)]`` (o: to the left in plan, h: up) swept along the walking line."""
    frames = _frames(pts, closed)
    rings = [[(x + m[0] * o, y + m[1] * o, z + h) for o, h in profile] for (x, y, z), m in zip(pts, frames)]
    verts = [v for ring in rings for v in ring]
    n, k = len(profile), len(rings)
    tris = []
    for i in range(k if closed else k - 1):
        r0, r1 = i * n, ((i + 1) % k) * n
        for j in range(n):
            a, b, c, d = r0 + j, r1 + j, r1 + (j + 1) % n, r0 + (j + 1) % n
            tris += [(a, b, c), (a, c, d)]
    if not closed:
        last = (k - 1) * n
        for j in range(1, n - 1):
            tris += [(0, j, j + 1), (last, last + j + 1, last + j)]
    mesh.solid(role, verts, tris)


_HEX = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))


def _hexa(mesh, role, corner):
    """Hexahedron from ``corner(i_along, i_side, i_up)`` (bit-indexed like a box)."""
    verts = [corner(i, j, k) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    tris = []
    for q0, q1, q2, q3 in _HEX:
        tris += [(q0, q1, q2), (q0, q2, q3)]
    mesh.solid(role, verts, tris)


def _prism(mesh, role, cx, cy, z0, z1, size, sides, angle):
    """Vertical post: square (4 sides) or near-round (8 sides) of width ``size``."""
    r = size / 2 / math.cos(math.pi / sides)              # flat-to-flat width = size
    start = angle + math.pi / sides
    ring = [(cx + r * math.cos(start + 2 * math.pi * i / sides), cy + r * math.sin(start + 2 * math.pi * i / sides))
            for i in range(sides)]
    verts = [(x, y, z0) for x, y in ring] + [(x, y, z1) for x, y in ring]
    tris = []
    for i in range(sides):
        j = (i + 1) % sides
        tris += [(i, j, sides + j), (i, sides + j, sides + i)]
    for i in range(1, sides - 1):
        tris += [(0, i + 1, i), (sides, sides + i, sides + i + 1)]
    mesh.solid(role, verts, tris)


def _rail_profile(shape, size):
    """Cross-section ``[(o, h)]`` centred on (0, 0) and its height."""
    if shape == 'round':
        r = size / 2
        return [(r * math.cos(2 * math.pi * i / 12), r * math.sin(2 * math.pi * i / 12)) for i in range(12)], size
    if shape == 'flat':
        h = min(0.05, max(0.02, 0.4 * size))
        return _rect(size, h), h
    return _rect(size, size), size


def _rect(w, h, h0=None):
    lo = -h / 2 if h0 is None else h0
    return [(-w / 2, lo), (w / 2, lo), (w / 2, lo + h), (-w / 2, lo + h)]


def _shifted(profile, dh):
    return [(o, h + dh) for o, h in profile]


# --- the railing -----------------------------------------------------------------------------

def post_positions(p):
    """``[(x, y, z_walk, angle, sloped)]``: every end and corner, then evenly at most ``post_spacing`` apart."""
    spec = TYPES[p['railing_type']]
    if not spec['post']:
        return []
    pts, closed = path(p), bool(int(p.get('closed', 0)))
    segs = _segments(pts, closed)
    sloped = [abs(b[2] - a[2]) > 1e-6 for a, b in segs]
    spacing = float(p.get('post_spacing', 1.2))
    out = []
    for i, (a, b) in enumerate(segs):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        angle = math.atan2(b[1] - a[1], b[0] - a[0])
        n = max(1, math.ceil(L / spacing - 1e-9))
        last = n if (not closed or i < len(segs) - 1) else n - 1     # a closed loop meets its first post
        for j in range(0 if i == 0 else 1, last + 1):
            t = j / n
            corner_slope = sloped[i] or (j == n and i + 1 < len(segs) and sloped[i + 1]) or \
                (j == 0 and i > 0 and sloped[i - 1])
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, angle, corner_slope))
    return out


def bays(p):
    """Clear bays between post faces: ``[(segment index, s0, s1)]`` along each segment (plan metres)."""
    spec = TYPES[p['railing_type']]
    pts, closed = path(p), bool(int(p.get('closed', 0)))
    half = spec['post'] / 2
    out = []
    for i, (a, b) in enumerate(_segments(pts, closed)):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, math.ceil(L / float(p.get('post_spacing', 1.2)) - 1e-9))
        for j in range(n):
            out.append((i, L * j / n + half, L * (j + 1) / n - half))
    return out


def baluster_offsets(s0, s1, bar, gap):
    """Centres of vertical bars in a bay so no clear gap exceeds ``gap``."""
    clear = s1 - s0
    k = max(0, math.ceil((clear - gap) / (gap + bar) - 1e-9))
    g = (clear - k * bar) / (k + 1)
    return [s0 + g * (j + 1) + bar * (j + 0.5) for j in range(k)]


def horizontal_levels(h0, h1, bar, gap):
    """Centre heights of horizontal bars / cables between ``h0`` and ``h1``."""
    span = h1 - h0
    m = max(0, math.ceil((span - gap) / (gap + bar) - 1e-9))
    g = (span - m * bar) / (m + 1)
    return [h0 + g * (j + 1) + bar * (j + 0.5) for j in range(m)]


def railing_mesh(p):
    """World-space ``(vertices, triangles, roles)`` of the railing; every member a closed solid."""
    kind = p['railing_type']
    spec = TYPES[kind]
    pts, closed = path(p), bool(int(p.get('closed', 0)))
    segs = _segments(pts, closed)
    height = float(p['height'])
    shape = str(p.get('handrail', spec['handrail']))
    size = float(p.get('handrail_size', spec['size']))
    gap = float(p.get('gap', 0.10))
    h0 = 0.0 if kind == 'parapet' else float(p.get('base_height', 0.0))
    mesh = _Mesh()
    hr_h = 0.0
    if shape != 'none':
        profile, hr_h = _rail_profile(shape, size)
        _sweep(mesh, 'handrail', pts, closed, _shifted(profile, height - hr_h / 2))
    top = height - hr_h                                   # underside of the handrail
    if kind == 'parapet':
        _sweep(mesh, 'base', pts, closed, _rect(PARAPET, top, 0.0))
        return tuple(mesh.verts), tuple(mesh.tris), tuple(mesh.roles)
    if h0 > 0:
        _sweep(mesh, 'base', pts, closed, _rect(BASE_WIDTH, h0, 0.0))
    # Posts: vertical, into the handrail; on a flight fixed on the side, below the nosing line.
    for x, y, zw, angle, sloped in post_positions(p):
        lift = hr_h / 2 if hr_h else 0.0
        _prism(mesh, 'post', x, y, zw + h0 - (SIDE_DROP if sloped else 0.0), zw + height - lift, spec['post'], spec['sides'], angle)

    def corner_fn(i, s0, s1, o0, o1, ha, hb):
        a, b = segs[i]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        ux, uy, k = (b[0] - a[0]) / L, (b[1] - a[1]) / L, (b[2] - a[2]) / L
        nx, ny = -uy, ux

        def corner(ia, io, ih):
            s, o = (s0, s1)[ia], (o0, o1)[io]
            return (a[0] + ux * s + nx * o, a[1] + uy * s + ny * o, a[2] + k * s + (ha, hb)[ih])
        return corner

    bottom = spec.get('bottom')
    rail_top = h0 + BOTTOM_CLEAR
    if bottom:
        _sweep(mesh, 'infill', pts, closed, _rect(bottom[0], bottom[1], rail_top))
        rail_top += bottom[1]
    if kind in ('balusters', 'timber'):
        bar = spec['bar']
        for i, s0, s1 in bays(p):
            for c in baluster_offsets(s0, s1, bar, gap):
                _hexa(mesh, 'infill', corner_fn(i, c - bar / 2, c + bar / 2, -bar / 2, bar / 2, rail_top - 0.005, top + 0.005))
    elif kind in ('bars', 'cable'):
        bar = spec['bar']
        prof = _rect(bar, bar) if kind == 'bars' else \
            [(bar / 2 * math.cos(2 * math.pi * i / 6), bar / 2 * math.sin(2 * math.pi * i / 6)) for i in range(6)]
        for h in horizontal_levels(h0, top, bar, gap):
            _sweep(mesh, 'infill', pts, closed, _shifted(prof, h))
    elif kind in ('panel', 'perforated'):
        t = spec['sheet']
        for i, s0, s1 in bays(p):
            _hexa(mesh, 'infill', corner_fn(i, s0 - 0.002, s1 + 0.002, -t / 2, t / 2, rail_top - 0.005, top - 0.03))
    elif kind == 'glass_posts':
        for i, s0, s1 in bays(p):
            _hexa(mesh, 'glass', corner_fn(i, s0 + 0.02, s1 - 0.02, -GLASS / 2, GLASS / 2, h0 + BOTTOM_CLEAR, top - 0.04))
    elif kind == 'glass_channel':
        w, d = CHANNEL
        _sweep(mesh, 'base', pts, closed, _rect(w, d, h0 - d + 0.01))
        for i, (a, b) in enumerate(segs):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            inner0 = closed or i > 0
            inner1 = closed or i < len(segs) - 1
            # Panes meet at a corner with a joint of a few millimetres.
            s0 = (GLASS / 2 + 0.003) if inner0 else 0.0
            s1 = L - ((GLASS / 2 + 0.003) if inner1 else 0.0)
            _hexa(mesh, 'glass', corner_fn(i, s0, s1, -GLASS / 2, GLASS / 2, h0 - d + 0.03, top + (0.005 if hr_h else 0.0)))
    return tuple(mesh.verts), tuple(mesh.tris), tuple(mesh.roles)


def max_clear_gap(p):
    """Largest clear gap of the infill (between bars, and to the posts / floor / handrail), m."""
    kind = p['railing_type']
    spec = TYPES[kind]
    gap = float(p.get('gap', 0.10))
    if kind in ('balusters', 'timber'):
        worst = 0.0
        for _i, s0, s1 in bays(p):
            cs = baluster_offsets(s0, s1, spec['bar'], gap)
            edges = [s0] + [x for c in cs for x in (c - spec['bar'] / 2, c + spec['bar'] / 2)] + [s1]
            worst = max([worst] + [edges[j + 1] - edges[j] for j in range(0, len(edges), 2)])
        return max(worst, BOTTOM_CLEAR)
    if kind in ('bars', 'cable'):
        shape = str(p.get('handrail', spec['handrail']))
        hr_h = _rail_profile(shape, float(p.get('handrail_size', spec['size'])))[1] if shape != 'none' else 0.0
        h0 = float(p.get('base_height', 0.0))
        hs = horizontal_levels(h0, float(p['height']) - hr_h, spec['bar'], gap)
        edges = [h0] + [x for h in hs for x in (h - spec['bar'] / 2, h + spec['bar'] / 2)] + [float(p['height']) - hr_h]
        return max(edges[j + 1] - edges[j] for j in range(0, len(edges), 2))
    return BOTTOM_CLEAR if kind in ('glass_posts', 'panel', 'perforated') else 0.0


# --- plan ------------------------------------------------------------------------------------

def plan_width(p):
    spec = TYPES[p['railing_type']]
    shape = str(p.get('handrail', spec['handrail']))
    w = [spec['post'], 0.03]
    if shape != 'none':
        w.append(float(p.get('handrail_size', spec['size'])))
    if p['railing_type'] == 'parapet':
        w.append(PARAPET)
    if p['railing_type'] == 'glass_channel':
        w.append(CHANNEL[0])
    if float(p.get('base_height', 0.0)) > 0:
        w.append(BASE_WIDTH)
    return max(w)


def plan_outline(p):
    """Plan band of the railing: a polygon (open railing) or the two rings of a closed one."""
    pts, closed = path(p), bool(int(p.get('closed', 0)))
    frames = _frames(pts, closed)
    half = plan_width(p) / 2
    left = [(x + m[0] * half, y + m[1] * half) for (x, y, _z), m in zip(pts, frames)]
    right = [(x - m[0] * half, y - m[1] * half) for (x, y, _z), m in zip(pts, frames)]
    if closed:
        return [left + left[:1], right + right[:1]]
    return [left + right[::-1]]


def plan_posts(p):
    """Small squares of the posts in plan."""
    size = TYPES[p['railing_type']]['post']
    out = []
    for x, y, _z, a, _s in post_positions(p):
        c, s, h = math.cos(a), math.sin(a), size / 2
        out.append([(x + c * u - s * v, y + s * u + c * v) for u, v in ((-h, -h), (h, -h), (h, h), (-h, h), (-h, -h))])
    return out


# --- materials -------------------------------------------------------------------------------

def role_material(p, role):
    """Default look of a role for this railing type / finish (palette materials override it)."""
    kind = p.get('railing_type', 'balusters')
    color, rough, metal = _METAL_LOOK.get(str(p.get('metal', 'iron')), _METAL_LOOK['iron'])
    if role == 'glass':
        return {'color': '#a9c3d2', 'roughness': 0.03, 'metalness': 0.1, 'opacity': 0.3}
    if kind == 'timber' and role in ('handrail', 'post', 'infill'):
        return {'color': '#8a5a33' if role != 'infill' else '#9a6a40', 'roughness': 0.7, 'metalness': 0.0}
    if kind == 'parapet':
        return {'color': '#ddd6ca', 'roughness': 0.85, 'metalness': 0.0} if role == 'base' else \
            {'color': '#e6e1d8', 'roughness': 0.35, 'metalness': 0.0}         # marble / concrete coping
    if role == 'base' and kind != 'glass_channel':
        return {'color': '#c9c4bb', 'roughness': 0.85, 'metalness': 0.0}       # concrete curb
    spec = {'color': color, 'roughness': rough, 'metalness': metal}
    if role == 'infill' and kind == 'perforated':
        spec['opacity'] = 0.6                                                   # see-through sheet
    return spec


# --- stairs ----------------------------------------------------------------------------------

def _flights(c):
    """``[(start, direction, steps, first step index, end height)]`` of a stair in its local frame."""
    n, t, r = c.tread_count, c.tread_depth, c.riser_height
    rise = c.upper_z - c.lower_z
    if c.layout == 'straight':
        return [((0.0, 0.0), (1.0, 0.0), n, 0, rise)]
    first = max(1, n // 2)
    second = n - first
    if c.layout == 'l':
        turn = float(c.turn_direction)
        return [((0.0, 0.0), (1.0, 0.0), first, 0, first * r),
                ((first * t + c.landing_depth / 2, turn * c.landing_depth / 2), (0.0, turn), second, first, rise)]
    if c.layout == 'u':
        offset = c.turn_direction * (c.width + 0.20)
        return [((0.0, 0.0), (1.0, 0.0), first, 0, first * r),
                ((first * t, offset), (-1.0, 0.0), second, first, rise)]
    raise ValueError('Κάγκελο σε σπιράλ σκάλα: δεν υποστηρίζεται ακόμη — σχεδίασέ το με σημεία')


def stair_railing_lines(stair_params, side, edge=0.03):
    """Walking lines of a stair railing on ``side`` ('left' / 'right' going up), one per flight.

    The line passes over the nosings (κουπαστή 90 cm πάνω από τη μύτη) and ``edge``
    outside the side of the flight, where the posts are fixed.  Returns
    ``[[[x, y, dz], ...], ...]`` with ``dz`` above the stair's ``lower_z``.
    """
    from archforge.architecture.stairs import _local_to_world, candidate_from_params
    c = candidate_from_params(stair_params)
    t, r = c.tread_depth, c.riser_height
    sign = 1.0 if side == 'left' else -1.0
    o = sign * (c.width / 2 + edge)
    lines = []
    for (sx, sy), (dx, dy), m, k0, end in _flights(c):
        nx, ny = -dy, dx

        def at(s, dz):
            x, y = _local_to_world(c, sx + dx * s + nx * o, sy + dy * s + ny * o)
            return [x, y, dz]
        line = [at(0.0, (k0 + 1) * r)]
        if m > 1:
            line.append(at((m - 1) * t, (k0 + m) * r))
        line.append(at(m * t, end))
        if len(line) == 3:                                  # drop a middle point on the same slope
            (x0, z0), (x1, z1), (x2, z2) = ((0.0, line[0][2]), ((m - 1) * t, line[1][2]), (m * t, line[2][2]))
            if abs((z1 - z0) * (x2 - x0) - (z2 - z0) * (x1 - x0)) < 1e-9:
                line.pop(1)
        lines.append(line)
    return lines


def _along_wall(doc, line, z, reach=0.30):
    """True when a wall of the storey runs along most of the plan line (that side needs no railing)."""
    (ax, ay, _), (bx, by, _) = line[0], line[-1]
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-9:
        return False
    ux, uy = (bx - ax) / L, (by - ay) / L
    for e in doc.entities.values():
        if e.kind != 'wall' or abs(float(e.params.get('z', 0.0)) - z) > 0.05:
            continue
        q = e.params
        w1, w2 = (float(q['x1']), float(q['y1'])), (float(q['x2']), float(q['y2']))
        far = reach + float(q.get('thickness', 0.2)) / 2
        dist = [abs((w[0] - ax) * -uy + (w[1] - ay) * ux) for w in (w1, w2)]
        if max(dist) > far:
            continue
        s = sorted((w[0] - ax) * ux + (w[1] - ay) * uy for w in (w1, w2))
        if min(s[1], L) - max(s[0], 0.0) >= 0.6 * L:
            return True
    return False


def stair_railings(doc, stair, railing_type='balusters'):
    """Params of the railings of a stair: each open side of each flight (sides along a wall are skipped)."""
    p = stair.params
    z = float(p['lower_z'])
    out = []
    for side in ('left', 'right'):
        for line in stair_railing_lines(p, side):
            if _along_wall(doc, line, z):
                continue
            out.append(default_params(railing_type, line, z=z, height=STAIR_HEIGHT))
    return out
