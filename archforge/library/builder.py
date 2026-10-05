"""Build ArchForge-original library meshes from simple solids (centimetres).

A spec is ``{"name", "category", "expect_cm", "parts": [...]}``; each part is
one closed solid with a colour and a material-part name:

  box          min, max
  rounded_box  min, max, radius            (vertical edges rounded)
  cylinder     base, radius, height, axis  (axis "z" default, or "x"/"y")
  taper        base, r0, r1, height        (vertical frustum)
  ellipsoid    center, radii               (cushions, basins, shades)

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
