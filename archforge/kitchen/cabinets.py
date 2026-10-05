"""Parametric kitchen cabinets and wardrobes.

One ``cabinet`` entity holds the design intent (type, size, doors, drawers,
shelves, plinth, worktop, handle); the boxes of the carcass, fronts,
handles, plinth, worktop and hanging rail are derived from it.  Panel
thicknesses and gaps stay constant when the size changes, so resizing never
distorts doors or frames.

Local frame: origin at the centre of the footprint on the floor, front face
towards -Y, back towards +Y, Z up.  ``rotation`` is in degrees about Z.
Dimensions are metres; the worktop sits on top of ``height``.
"""
import math

CARCASS = 0.018      # side, top, bottom, shelf panels
BACK = 0.008         # back panel
FRONT = 0.019        # door / drawer front
GAP = 0.003          # gap around fronts
WORKTOP = 0.04       # worktop thickness
OVERHANG = 0.02      # worktop overhang at the front
PLINTH_SETBACK = 0.05
DRAWER_FRONT = 0.16  # drawer front height above doors

TYPES = {
    # type: name, defaults
    "base": ("Ντουλάπι βάσης", dict(width=0.60, depth=0.60, height=0.86, plinth=0.10, doors=1, drawers=1, shelves=1, worktop=1.0, z=0.0)),
    "drawers": ("Συρταριέρα", dict(width=0.60, depth=0.60, height=0.86, plinth=0.10, doors=0, drawers=3, shelves=0, worktop=1.0, z=0.0)),
    "sink": ("Ντουλάπι νεροχύτη", dict(width=0.80, depth=0.60, height=0.86, plinth=0.10, doors=2, drawers=0, shelves=0, worktop=1.0, z=0.0)),
    "wall": ("Κρεμαστό ντουλάπι", dict(width=0.60, depth=0.35, height=0.72, plinth=0.0, doors=1, drawers=0, shelves=2, worktop=0.0, z=1.45)),
    "tall": ("Ψηλό ντουλάπι", dict(width=0.60, depth=0.60, height=2.10, plinth=0.10, doors=2, drawers=0, shelves=4, worktop=0.0, z=0.0)),
    "wardrobe": ("Ντουλάπα", dict(width=1.00, depth=0.60, height=2.40, plinth=0.08, doors=2, drawers=0, shelves=1, worktop=0.0, z=0.0)),
}
HANDLES = ("bar", "knob", "none")
ROLES = ("carcass", "shelf", "front", "handle", "plinth", "worktop", "rail")
ROLE_NAMES = {"carcass": "Κουφάρι", "shelf": "Ράφια", "front": "Πόρτες/συρτάρια", "handle": "Χερούλια",
              "plinth": "Βάση (πόδι)", "worktop": "Πάγκος", "rail": "Ράβδος κρεμάστρας"}


def default_params(cabinet_type, x=0.0, y=0.0, z=None, rotation=0.0, width=None):
    """Complete parameters for a new cabinet of ``cabinet_type``."""
    _name, d = TYPES[cabinet_type]
    p = dict(d)
    if width is not None:
        p["width"] = float(width)
    p["doors"] = auto_doors(cabinet_type, p["width"]) if p["doors"] else 0
    p.update(x=float(x), y=float(y), rotation=float(rotation), cabinet_type=cabinet_type, handle="bar")
    if z is not None:
        p["z"] = float(z)
    return p


def auto_doors(cabinet_type, width):
    """Doors a carpenter would fit: up to 60 cm per door (50 cm for wardrobes)."""
    leaf = 0.5 if cabinet_type == "wardrobe" else 0.6
    return max(1, int(math.ceil(width / leaf - 1e-9)))


def _box(parts, role, x0, y0, z0, x1, y1, z1):
    if x1 - x0 > 1e-6 and y1 - y0 > 1e-6 and z1 - z0 > 1e-6:
        parts.append((role, (x0, y0, z0), (x1, y1, z1)))


def cabinet_boxes(p):
    """Derived boxes ``[(role, lo, hi)]`` in the local frame."""
    w, d, h = float(p["width"]), float(p["depth"]), float(p["height"])
    kind = str(p.get("cabinet_type", "base"))
    plinth = min(float(p.get("plinth", 0.0)), h * 0.5)
    doors, drawers, shelves = int(p.get("doors", 0)), int(p.get("drawers", 0)), int(p.get("shelves", 0))
    handle = str(p.get("handle", "bar"))
    if w < 2 * CARCASS + 0.05 or d < FRONT + BACK + 0.05 or h - plinth < 2 * CARCASS + 0.05:
        raise ValueError("cabinet is too small for its panels")
    parts = []
    x0, x1 = -w / 2, w / 2
    yf, yb = -d / 2, d / 2            # front and back faces
    yc = yf + FRONT                   # carcass front
    zb, zt = plinth, h                # carcass bottom and top
    if plinth > 0:
        _box(parts, "plinth", x0 + CARCASS, yf + PLINTH_SETBACK, 0.0, x1 - CARCASS, yb - BACK, plinth)
        _box(parts, "carcass", x0, yc, 0.0, x0 + CARCASS, yb, plinth)      # sides run to the floor
        _box(parts, "carcass", x1 - CARCASS, yc, 0.0, x1, yb, plinth)
    # Carcass
    _box(parts, "carcass", x0, yc, zb, x0 + CARCASS, yb, zt)
    _box(parts, "carcass", x1 - CARCASS, yc, zb, x1, yb, zt)
    _box(parts, "carcass", x0 + CARCASS, yc, zb, x1 - CARCASS, yb - BACK, zb + CARCASS)
    _box(parts, "carcass", x0 + CARCASS, yc, zt - CARCASS, x1 - CARCASS, yb - BACK, zt)
    _box(parts, "carcass", x0 + CARCASS, yb - BACK, zb + CARCASS, x1 - CARCASS, yb, zt - CARCASS)
    inner0, inner1 = zb + CARCASS, zt - CARCASS
    # Fronts: drawers at the top above the doors (or full height when no doors)
    drawer_h = DRAWER_FRONT if doors else (zt - zb) / max(drawers, 1)
    if kind == "wardrobe" or kind == "tall":
        drawer_h = min(drawer_h, 0.25)
    z_split = zt - drawers * drawer_h if doors else zb
    for k in range(drawers):
        top = zt - k * drawer_h
        _box(parts, "front", x0 + GAP, yf, top - drawer_h + GAP, x1 - GAP, yc, top - GAP)
        if handle != "none":
            hz = top - drawer_h / 2
            if handle == "bar":
                hw = min(0.16, w * 0.5)
                _box(parts, "handle", -hw / 2, yf - 0.025, hz - 0.006, hw / 2, yf, hz + 0.006)
            else:
                _box(parts, "handle", -0.012, yf - 0.025, hz - 0.012, 0.012, yf, hz + 0.012)
    if doors:
        leaf = w / doors
        for k in range(doors):
            lx0, lx1 = x0 + k * leaf + GAP, x0 + (k + 1) * leaf - GAP
            _box(parts, "front", lx0, yf, zb + GAP, lx1, yc, z_split - GAP)
            if handle == "none":
                continue
            # Handle on the opening edge: pairs open from the middle.
            right_hinge = doors > 1 and k < doors / 2
            hx = lx1 - 0.04 if right_hinge or (doors == 1) else lx0 + 0.04
            if kind == "wall":
                hz0 = zb + 0.05
            elif kind in ("tall", "wardrobe"):
                hz0 = min(1.0, z_split - 0.25)
            else:
                hz0 = z_split - 0.20
            if handle == "bar":
                _box(parts, "handle", hx - 0.006, yf - 0.025, hz0, hx + 0.006, yf, hz0 + 0.16)
            else:
                _box(parts, "handle", hx - 0.012, yf - 0.025, hz0 + 0.06, hx + 0.012, yf, hz0 + 0.084)
    # Shelves inside the door zone
    top_shelf_zone = z_split - CARCASS if doors and drawers else inner1
    for k in range(shelves):
        zs = inner0 + (top_shelf_zone - inner0) * (k + 1) / (shelves + 1)
        if kind == "wardrobe":
            zs = inner1 - 0.30 - k * 0.35          # hat shelves near the top
            if zs <= inner0 + 0.2:
                break
        _box(parts, "shelf", x0 + CARCASS, yc + 0.02, zs - CARCASS / 2, x1 - CARCASS, yb - BACK, zs + CARCASS / 2)
    if kind == "wardrobe":
        zr = inner1 - 0.30 - (0.07 if shelves else 0.0) - 0.05
        _box(parts, "rail", x0 + CARCASS, -0.01, zr - 0.01, x1 - CARCASS, 0.01, zr + 0.01)
    if float(p.get("worktop", 0.0)):
        _box(parts, "worktop", x0, yf - OVERHANG, h, x1, yb, h + WORKTOP)
    return parts


def cabinet_mesh(p):
    """World-space (vertices, triangles, roles) of the cabinet."""
    a = math.radians(float(p.get("rotation", 0.0)))
    c, s = math.cos(a), math.sin(a)
    ox, oy, oz = float(p["x"]), float(p["y"]), float(p["z"])
    verts, tris, roles = [], [], []
    quads = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    for role, lo, hi in cabinet_boxes(p):
        base = len(verts)
        for x in (lo[0], hi[0]):
            for y in (lo[1], hi[1]):
                for z in (lo[2], hi[2]):
                    verts.append((ox + c * x - s * y, oy + s * x + c * y, oz + z))
        for q0, q1, q2, q3 in quads:
            tris += [(base + q0, base + q1, base + q2), (base + q0, base + q2, base + q3)]
            roles += [role, role]
    return tuple(verts), tuple(tris), tuple(roles)


def footprint(p):
    """Rotated plan rectangle (carcass + fronts), counter-clockwise."""
    w, d = float(p["width"]), float(p["depth"])
    return _world(p, [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)])


def front_line(p):
    """Plan line marking the face of the doors (inside the footprint)."""
    w, d = float(p["width"]), float(p["depth"])
    return _world(p, [(-w / 2, -d / 2 + FRONT), (w / 2, -d / 2 + FRONT)])


def _world(p, pts):
    a = math.radians(float(p.get("rotation", 0.0)))
    c, s = math.cos(a), math.sin(a)
    x, y = float(p["x"]), float(p["y"])
    return [(x + c * px - s * py, y + s * px + c * py) for px, py in pts]


def wall_aligned(doc, x, y, depth, *, tolerance=0.6, z=None):
    """Place a cabinet with its back on the nearest wall face near (x, y).

    Returns ``(x, y, rotation_deg)`` of the cabinet centre, or None when no
    wall of the active storey is within ``tolerance``.  The cabinet faces
    away from the wall, into the side of the wall the cursor is on.
    """
    level = doc.work_plane.origin[2] if z is None else z
    best = None
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - level) > 0.05:
            continue
        p = e.params
        x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-9:
            continue
        ux, uy = dx / length, dy / length
        t = max(0.0, min(length, (x - x1) * ux + (y - y1) * uy))
        px, py = x1 + ux * t, y1 + uy * t
        dist = math.hypot(x - px, y - py)
        if dist > tolerance + float(p["thickness"]) / 2 or (best and dist >= best[0]):
            continue
        side = 1.0 if (-uy) * (x - px) + ux * (y - py) >= 0 else -1.0
        nx, ny = -uy * side, ux * side
        best = (dist, px, py, nx, ny, float(p["thickness"]))
    if best is None:
        return None
    _dist, px, py, nx, ny, thickness = best
    off = thickness / 2 + depth / 2
    rotation = math.degrees(math.atan2(nx, -ny)) % 360.0
    return px + nx * off, py + ny * off, rotation


def snap_to_neighbours(doc, x, y, rotation, width, depth, *, tolerance=0.12, ignore=()):
    """Slide along the run so the cabinet's side touches a neighbour within tolerance."""
    a = math.radians(rotation)
    ux, uy = math.cos(a), math.sin(a)          # along the run (local +X)
    nx, ny = -uy, ux                            # local +Y (towards the wall)
    best = None
    for e in doc.entities.values():
        if e.kind != "cabinet" or e.id in ignore:
            continue
        q = e.params
        if abs((float(q.get("rotation", 0.0)) - rotation + 180) % 360 - 180) > 1.0:
            continue
        rx, ry = float(q["x"]) - x, float(q["y"]) - y
        across = rx * nx + ry * ny
        # Same run: both backs on the same line (centres differ by half the depth difference).
        if abs(across - (depth - float(q["depth"])) / 2) > 0.03:
            continue
        along = rx * ux + ry * uy
        for target in (along - float(q["width"]) / 2 - width / 2, along + float(q["width"]) / 2 + width / 2):
            if abs(target) <= tolerance and (best is None or abs(target) < abs(best)):
                best = target
    if best is None:
        return x, y
    return x + ux * best, y + uy * best
