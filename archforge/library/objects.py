"""Derived geometry for ``library_object`` entities.

The entity owns placement (x, y, z, rotation in degrees about Z) and target
size (width, depth, height in metres).  The mesh is the referenced asset
scaled per axis by target / native size, so sizes in the Inspector are exact.
A missing asset yields a box of the target size, so the model stays usable.
"""
import math

from archforge.library.assets import load_asset

SIZE_KEYS = ("width", "depth", "height")


def _box(w, d, h):
    hw, hd = w / 2, d / 2
    v = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
         (-hw, -hd, h), (hw, -hd, h), (hw, hd, h), (-hw, hd, h)]
    quads = ((0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (3, 2, 1, 0))
    tris = [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]
    return v, tris


def library_object_mesh(params):
    """Return (vertices, triangles, roles) in world coordinates."""
    w, d, h = (float(params[k]) for k in SIZE_KEYS)
    asset = load_asset(str(params["asset"]))
    if asset is None:
        local, tris = _box(w, d, h)
        role = "placeholder"
    else:
        nw, nd, nh = (float(s) for s in asset["size"])
        sx, sy, sz = w / nw, d / nd, h / nh
        local = [(x * sx, y * sy, z * sz) for x, y, z in asset["vertices"]]
        tris = [tuple(t) for t in asset["triangles"]]
        role = "body"
    a = math.radians(float(params.get("rotation", 0.0)))
    c, s = math.cos(a), math.sin(a)
    ox, oy, oz = (float(params[k]) for k in ("x", "y", "z"))
    verts = tuple((ox + c * x - s * y, oy + s * x + c * y, oz + z) for x, y, z in local)
    return verts, tuple(tris), tuple(role for _ in tris)


def footprint(params):
    """Rotated plan rectangle of the object, counter-clockwise."""
    w, d = float(params["width"]), float(params["depth"])
    a = math.radians(float(params.get("rotation", 0.0)))
    c, s = math.cos(a), math.sin(a)
    x, y = float(params["x"]), float(params["y"])
    return [(x + c * px - s * py, y + s * px + c * py)
            for px, py in ((-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2))]


def resized(params, key, value):
    """Changes for setting one size; uniform objects keep their proportions."""
    value = float(value)
    if value <= 0:
        raise ValueError("dimension must be > 0")
    if not params.get("uniform", 1.0):
        return {key: value}
    factor = value / float(params[key])
    return {k: float(params[k]) * factor for k in SIZE_KEYS}


def _scale_rotate(params, asset):
    w, d = float(params["width"]), float(params["depth"])
    nw, nd = (float(v) for v in asset["size"][:2])
    a = math.radians(float(params.get("rotation", 0.0)))
    c, s = math.cos(a), math.sin(a)
    x0, y0 = float(params["x"]), float(params["y"])

    def to_world(q):
        px, py = q[0] * w / nw, q[1] * d / nd
        return (x0 + c * px - s * py, y0 + s * px + c * py)
    return to_world


def plan_symbol_world(params):
    """The asset's 2D symbol placed in the plan: ``[(closed, points)]``.

    Empty when the asset is missing or has no symbol (the footprint
    rectangle still shows the object).
    """
    asset = load_asset(str(params["asset"]))
    if asset is None or "plan" not in asset:
        return []
    to_world = _scale_rotate(params, asset)
    out = [(True, [to_world(q) for q in loop]) for loop in asset["plan"].get("outline", [])]
    out += [(False, [to_world(q) for q in line]) for line in asset["plan"].get("lines", [])]
    return out


def triangle_colors(params):
    """Per-triangle hex colours from the asset palette, or None."""
    asset = load_asset(str(params["asset"]))
    if asset is None or "palette" not in asset:
        return None
    palette = asset["palette"]
    return [palette[i] for i in asset["tri_part"]]
