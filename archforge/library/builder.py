"""Build ArchForge-original library meshes from simple solids (centimetres).

A spec is ``{"name", "category", "expect_cm", "parts": [...]}``; each part is
one closed solid with a colour and a material-part name:

  box          min, max
  rounded_box  min, max, radius            (vertical edges rounded)
  cylinder     base, radius, height, axis  (axis "z" default, or "x"/"y")
  taper        base, r0, r1, height        (vertical frustum)
  ellipsoid    center, radii               (cushions, basins, shades)
  beam         a, b, width, thickness      (box along a→b: slanted backs, splayed legs, arcs)
  torus        center, radius, tube, axis, arc   (rings, handles, hoops; arc < 360 is capped)
  lathe        base, profile [(r, z), ...] (turned shapes: vases, amphorae, urns, lamp bases)

Specs are tiny, deterministic and project-owned, so the core library ships
with ArchForge and is rebuilt identically on every machine.
"""
import math

CM = 0.01


def box(lo, hi):
    c = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    return [tuple(c[i] for i in t) for a, b, cc, d in quads for t in ((a, b, cc), (a, cc, d))]


def frustum(base, r0, r1, height, segments=20, axis="z"):
    ring = [(math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments)) for k in range(segments)]
    lo = [(r0 * c, r0 * s, 0.0) for c, s in ring]
    hi = [(r1 * c, r1 * s, height) for c, s in ring]
    tris = []
    for k in range(segments):
        n = (k + 1) % segments
        tris += [(lo[k], lo[n], hi[n]), (lo[k], hi[n], hi[k])]
        tris += [((0.0, 0.0, 0.0), lo[n], lo[k]), ((0.0, 0.0, height), hi[k], hi[n])]
    return [tuple(_orient(v, base, axis) for v in t) for t in tris]


def _orient(v, base, axis):
    x, y, z = v
    if axis == "x":
        x, y, z = z, x, y
    elif axis == "y":
        x, y, z = y, z, x
    return (base[0] + x, base[1] + y, base[2] + z)


def rounded_box(lo, hi, radius, segments=6):
    r = max(0.0, min(radius, (hi[0] - lo[0]) / 2 - 1e-6, (hi[1] - lo[1]) / 2 - 1e-6))
    if r <= 0:
        return box(lo, hi)
    corners = [(hi[0] - r, hi[1] - r, 0), (lo[0] + r, hi[1] - r, 90), (lo[0] + r, lo[1] + r, 180), (hi[0] - r, lo[1] + r, 270)]
    outline = []
    for cx, cy, start in corners:
        for k in range(segments + 1):
            a = math.radians(start + 90 * k / segments)
            outline.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    tris = []
    n = len(outline)
    for k in range(n):
        (ax, ay), (bx, by) = outline[k], outline[(k + 1) % n]
        tris += [((ax, ay, lo[2]), (bx, by, lo[2]), (bx, by, hi[2])), ((ax, ay, lo[2]), (bx, by, hi[2]), (ax, ay, hi[2]))]
        tris += [((cx, cy, lo[2]), (bx, by, lo[2]), (ax, ay, lo[2])), ((cx, cy, hi[2]), (ax, ay, hi[2]), (bx, by, hi[2]))]
    return tris


def ellipsoid(center, radii, rings=8, segments=16):
    cx, cy, cz = center
    rx, ry, rz = radii
    pts = []
    for i in range(rings + 1):
        phi = math.pi * i / rings - math.pi / 2
        pts.append([(cx + rx * math.cos(phi) * math.cos(2 * math.pi * k / segments),
                     cy + ry * math.cos(phi) * math.sin(2 * math.pi * k / segments),
                     cz + rz * math.sin(phi)) for k in range(segments)])
    tris = []
    for i in range(rings):
        for k in range(segments):
            n = (k + 1) % segments
            a, b, c, d = pts[i][k], pts[i][n], pts[i + 1][n], pts[i + 1][k]
            if i > 0:
                tris.append((a, b, c))
            if i < rings - 1:
                tris.append((a, c, d))
    return tris


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(sum(c * c for c in a))
    return tuple(c / n for c in a)


def beam(a, b, width, thickness):
    """Box of width x thickness whose centre line runs from a to b.

    The width lies horizontal (across the slope), so a slanted chair back or a
    splayed leg keeps its broad face where a person expects it.
    """
    d = _unit(_sub(b, a))
    length = math.dist(a, b)
    ref = (0.0, 1.0, 0.0) if abs(d[2]) > 0.999 else (0.0, 0.0, 1.0)
    s = _unit(_cross(d, ref))
    t = _cross(d, s)                       # (s, t, d) right-handed

    def at(x, y, z):
        return tuple(a[i] + s[i] * x + t[i] * y + d[i] * z for i in range(3))
    # box() winds its faces inwards; reversed here so the beam faces outwards.
    return [(at(*tri[0]), at(*tri[2]), at(*tri[1]))
            for tri in box((-width / 2, -thickness / 2, 0.0), (width / 2, thickness / 2, length))]


def torus(center, radius, tube, axis="z", arc=360.0, start=0.0, segments=24, sides=10):
    """Ring of major ``radius`` and tube radius ``tube``; a partial arc is closed by flat caps."""
    full = arc >= 360.0
    steps = segments if full else max(2, int(round(segments * arc / 360.0)))
    count = steps if full else steps + 1
    rings = []
    for k in range(count):
        u = math.radians(start + arc * k / steps)
        rings.append([((radius + tube * math.cos(2 * math.pi * j / sides)) * math.cos(u),
                       (radius + tube * math.cos(2 * math.pi * j / sides)) * math.sin(u),
                       tube * math.sin(2 * math.pi * j / sides)) for j in range(sides)])
    tris = []
    for k in range(steps):
        r0, r1 = rings[k], rings[(k + 1) % count]
        for j in range(sides):
            n = (j + 1) % sides
            tris += [(r0[j], r1[j], r1[n]), (r0[j], r1[n], r0[n])]
    if not full:
        for ring, centre, flip in ((rings[0], math.radians(start), True), (rings[-1], math.radians(start + arc), False)):
            c = (radius * math.cos(centre), radius * math.sin(centre), 0.0)
            for j in range(sides):
                n = (j + 1) % sides
                tris.append((c, ring[j], ring[n]) if flip else (c, ring[n], ring[j]))
    return [tuple(_orient(v, center, axis) for v in t) for t in tris]


def lathe(base, profile, segments=24):
    """Surface of revolution about a vertical axis; profile is (radius, z) from bottom to top."""
    ring = [(math.cos(2 * math.pi * k / segments), math.sin(2 * math.pi * k / segments)) for k in range(segments)]
    loops = [[(r * c, r * s, z) for c, s in ring] for r, z in profile]
    tris = []
    for lo, hi in zip(loops, loops[1:]):
        for k in range(segments):
            n = (k + 1) % segments
            tris += [(lo[k], lo[n], hi[n]), (lo[k], hi[n], hi[k])]
    z0, z1 = profile[0][1], profile[-1][1]
    for k in range(segments):
        n = (k + 1) % segments
        tris += [((0.0, 0.0, z0), loops[0][n], loops[0][k]), ((0.0, 0.0, z1), loops[-1][k], loops[-1][n])]
    return [tuple((base[0] + x, base[1] + y, base[2] + z) for x, y, z in t) for t in tris]


def part_triangles(part):
    shape = part["shape"]
    if shape == "box":
        return box(part["min"], part["max"])
    if shape == "rounded_box":
        return rounded_box(part["min"], part["max"], part.get("radius", 2))
    if shape == "cylinder":
        return frustum(part["base"], part["radius"], part["radius"], part["height"],
                       part.get("segments", 20), part.get("axis", "z"))
    if shape == "taper":
        return frustum(part["base"], part["r0"], part["r1"], part["height"], part.get("segments", 20))
    if shape == "ellipsoid":
        return ellipsoid(part["center"], part["radii"], part.get("rings", 8), part.get("segments", 16))
    if shape == "beam":
        return beam(part["a"], part["b"], part["width"], part["thickness"])
    if shape == "torus":
        return torus(part["center"], part["radius"], part["tube"], part.get("axis", "z"), part.get("arc", 360.0),
                     part.get("start", 0.0), part.get("segments", 24), part.get("sides", 10))
    if shape == "lathe":
        return lathe(part["base"], part["profile"], part.get("segments", 24))
    raise ValueError(f"unknown shape {shape!r}")


def build(spec):
    """Spec -> (triangles in metres, per-triangle colours, colour -> part name)."""
    tris, colors, names = [], [], {}
    for part in spec["parts"]:
        t = [tuple(tuple(c * CM for c in v) for v in tri) for tri in part_triangles(part)]
        color = part.get("color", "#c8bfb0")
        tris += t
        colors += [color] * len(t)
        if part.get("part"):
            names.setdefault(color, part["part"])
    return tris, colors, names


def size_cm(tris):
    pts = [v for t in tris for v in t]
    return [round((max(p[i] for p in pts) - min(p[i] for p in pts)) / CM, 2) for i in range(3)]
