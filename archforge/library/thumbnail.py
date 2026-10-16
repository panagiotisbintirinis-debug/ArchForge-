"""Library thumbnails: a small 3/4 view of an asset mesh (pure geometry, no Qt).

The library tree shows a picture next to every object ("you can't tell what
you pick from a name").  ``thumbnail_faces`` projects the stored mesh of an
asset (``library/assets.py``: Z up, centred on X/Y, base at Z=0) to an
axonometric view from the front-right and above, shades each triangle by its
angle to a fixed light, and returns the faces back-to-front (painter's
algorithm) in pixel coordinates.  ``ui/library_icons.py`` paints them.

Appearance only, like the 3D preview: no measurement is read from the picture.
"""
from __future__ import annotations

import math

# Camera: looking from front-right-above (azimuth 30° off the front, 30° down).
_AZ = math.radians(30.0)
_EL = math.radians(30.0)
_LIGHT = (-0.35, -0.55, 0.76)          # from the front-left, above
DEFAULT_COLOR = "#b9b2a6"
MAX_FACES = 6000                       # big imported meshes: keep the largest faces


def _camera():
    # Right, up and towards-viewer vectors of the view (world Z up, front = -Y).
    ca, sa, ce, se = math.cos(_AZ), math.sin(_AZ), math.cos(_EL), math.sin(_EL)
    right = (ca, sa, 0.0)
    toward = (sa * ce, -ca * ce, se)
    up = (-sa * se, ca * se, ce)
    return right, up, toward


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _shade(hex_color: str, k: float) -> str:
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        rgb = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        rgb = [185, 178, 166]
    return "#" + "".join(f"{max(0, min(255, round(c * k))):02x}" for c in rgb)


def thumbnail_faces(record, size: int = 48, margin: int = 3):
    """``[(points, hex_color)]`` back-to-front, fitted into ``size`` px.

    ``record`` is an asset record (``vertices``, ``triangles``, optional
    ``palette``/``tri_part``).  Returns ``[]`` when there is no geometry."""
    verts = record.get("vertices") or []
    tris = record.get("triangles") or []
    if not verts or not tris:
        return []
    palette = record.get("palette") or []
    parts = record.get("tri_part") or []
    right, up, toward = _camera()
    light_len = math.sqrt(_dot(_LIGHT, _LIGHT))
    light = tuple(c / light_len for c in _LIGHT)
    proj = [(_dot(v, right), _dot(v, up), _dot(v, toward)) for v in verts]
    faces = []
    for n, t in enumerate(tris):
        a, b, c = (verts[i] for i in t)
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        w = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
        nrm = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
        length = math.sqrt(_dot(nrm, nrm))
        if length <= 1e-12:
            continue
        nrm = tuple(x / length for x in nrm)
        if _dot(nrm, toward) < 0:       # meshes are not always wound outwards: light both sides
            nrm = tuple(-x for x in nrm)
        k = 0.55 + 0.45 * max(0.0, _dot(nrm, light))
        base = palette[parts[n]] if n < len(parts) and parts[n] < len(palette) else DEFAULT_COLOR
        depth = sum(proj[i][2] for i in t) / 3.0
        faces.append((depth, length, [(proj[i][0], proj[i][1]) for i in t], _shade(str(base), k)))
    if not faces:
        return []
    if len(faces) > MAX_FACES:
        faces = sorted(faces, key=lambda f: -f[1])[:MAX_FACES]
    xs = [p[0] for f in faces for p in f[2]]
    ys = [p[1] for f in faces for p in f[2]]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    scale = (size - 2 * margin) / span
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
    faces.sort(key=lambda f: f[0])     # farthest first
    half = size / 2.0
    return [([(half + (x - cx) * scale, half - (y - cy) * scale) for x, y in pts], color)
            for _d, _l, pts, color in faces]
