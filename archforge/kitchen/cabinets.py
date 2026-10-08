"""Parametric kitchen cabinets and wardrobes.

One ``cabinet`` entity holds the design intent (type, size, doors, drawers,
shelves, plinth, worktop, handle, front style, mechanism); the boxes of the
carcass, fronts, handles, plinth, worktop, hanging rail and the inside
mechanisms are derived from it.  Panel thicknesses and gaps stay constant
when the size changes, so resizing never distorts doors or frames.

Local frame: origin at the centre of the footprint on the floor, front face
towards -Y, back towards +Y, Z up.  ``rotation`` is in degrees about Z.
Dimensions are metres; the worktop sits on top of ``height``.

Anchors (common European kitchen practice, generic types, no brands): base
units 60 cm deep with the worktop at 90 cm, wall units 35 cm deep and 72/90
cm high, a framed (shaker) door has a 6–7 cm frame with the panel ~5 mm
deeper, a 90×90 L corner takes a 3/4 carousel, a blind corner leaves 60 cm
plus a 5 cm filler for the run that covers it.  Indicative sizes, not a
manufacturer's drawing.
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
SHAKER_RAIL = 0.065  # frame (κάσα) of a framed or glazed door, 6–7 cm
PANEL_RECESS = 0.005  # the panel (ταμπλάς) of a framed door sits 5 mm deeper
GLASS = 0.004        # glass of a glazed door
GOLA = 0.03          # gola: finger groove instead of a handle
GOLA_CHANNEL = 0.004  # the aluminium channel at the back of the groove
EDGE_PROFILE = 0.02  # handle profile on the grip edge of the front
WIRE = 0.008         # wire of the baskets
CORNER_ARM = 0.60    # each leg of an L corner unit = depth of the base run
BLIND_FILLER = 0.05  # filler so the door of a blind corner clears the other run

TYPES = {
    # type: name, defaults
    "base": ("Ντουλάπι βάσης", dict(width=0.60, depth=0.60, height=0.86, plinth=0.10, doors=1, drawers=1, shelves=1, worktop=1.0, z=0.0)),
    "drawers": ("Συρταριέρα", dict(width=0.60, depth=0.60, height=0.86, plinth=0.10, doors=0, drawers=3, shelves=0, worktop=1.0, z=0.0)),
    "sink": ("Ντουλάπι νεροχύτη", dict(width=0.80, depth=0.60, height=0.86, plinth=0.10, doors=2, drawers=0, shelves=0, worktop=1.0, z=0.0)),
    "wall": ("Κρεμαστό ντουλάπι", dict(width=0.60, depth=0.35, height=0.72, plinth=0.0, doors=1, drawers=0, shelves=2, worktop=0.0, z=1.45)),
    "tall": ("Ψηλό ντουλάπι", dict(width=0.60, depth=0.60, height=2.10, plinth=0.10, doors=2, drawers=0, shelves=4, worktop=0.0, z=0.0)),
    "wardrobe": ("Ντουλάπα", dict(width=1.00, depth=0.60, height=2.40, plinth=0.08, doors=2, drawers=0, shelves=1, worktop=0.0, z=0.0)),
    # Corner units: width along the back wall, depth along the side wall (on the left).
    "corner": ("Γωνιακό ντουλάπι βάσης (Γ)", dict(width=0.90, depth=0.90, height=0.86, plinth=0.10, doors=2, drawers=0, shelves=1, worktop=1.0, z=0.0)),
    "corner_blind": ("Γωνιακό τυφλό ντουλάπι", dict(width=1.10, depth=0.60, height=0.86, plinth=0.10, doors=1, drawers=0, shelves=1, worktop=1.0, z=0.0)),
}
HANDLES = ("bar", "knob", "none", "edge")
HANDLE_NAMES = {"bar": "Μπάρα", "knob": "Πόμολο", "edge": "Προφίλ πάνω ακμής", "none": "Χωρίς (push)"}
FRONT_STYLES = {"flat": "Λεία", "shaker": "Ταμπλαδωτή (κάσα)", "glass": "Με τζάμι (βιτρίνα)",
                "gola": "Χωρίς χερούλι (gola)"}
MECHANISMS = {
    # mechanism: name, the cabinet types it fits (None = every type)
    "none": ("Χωρίς μηχανισμό", None),
    "cargo": ("Συρόμενο καλάθι (cargo)", ("base",)),
    "bin": ("Κάδοι απορριμμάτων συρόμενοι", ("sink", "base")),
    "inner_drawers": ("Εσωτερικά συρτάρια", ("base", "tall", "wardrobe")),
    "lift_up": ("Ανακλινόμενη πόρτα", ("wall",)),
    "larder": ("Συρόμενη αποθήκη (ψηλή)", ("tall",)),
    "carousel": ("Καρουζέλ 3/4", ("corner",)),
    "half_moon": ("Φασόλι (περιστρεφόμενα ράφια)", ("corner_blind",)),
}
DEFAULT_MECHANISM = {"corner": "carousel", "corner_blind": "half_moon"}
BLIND_SIDES = {"left": "Τυφλό αριστερά", "right": "Τυφλό δεξιά"}
ROLES = ("carcass", "shelf", "front", "handle", "plinth", "worktop", "rail", "glass", "mechanism")
ROLE_NAMES = {"carcass": "Κουφάρι", "shelf": "Ράφια", "front": "Πόρτες/συρτάρια", "handle": "Χερούλια",
              "plinth": "Βάση (πόδι)", "worktop": "Πάγκος", "rail": "Ράβδος κρεμάστρας",
              "glass": "Τζάμι", "mechanism": "Μηχανισμοί"}


def default_params(cabinet_type, x=0.0, y=0.0, z=None, rotation=0.0, width=None):
    """Complete parameters for a new cabinet of ``cabinet_type``."""
    _name, d = TYPES[cabinet_type]
    p = dict(d)
    if width is not None:
        p["width"] = float(width)
    p["doors"] = auto_doors(cabinet_type, p["width"]) if p["doors"] else 0
    p.update(x=float(x), y=float(y), rotation=float(rotation), cabinet_type=cabinet_type, handle="bar",
             front_style="flat", mechanism=DEFAULT_MECHANISM.get(cabinet_type, "none"))
    if cabinet_type == "corner_blind":
        p["blind_side"] = "left"
    if z is not None:
        p["z"] = float(z)
    return p


def auto_doors(cabinet_type, width):
    """Doors a carpenter would fit: up to 60 cm per door (50 cm for wardrobes)."""
    if cabinet_type in ("corner", "corner_blind"):
        return 2 if cabinet_type == "corner" else 1      # bi-fold pair / one door beside the blind part
    leaf = 0.5 if cabinet_type == "wardrobe" else 0.6
    return max(1, int(math.ceil(width / leaf - 1e-9)))


def mechanisms_for(cabinet_type):
    """Mechanisms offered for a cabinet type (``none`` first)."""
    return [k for k, (_n, kinds) in MECHANISMS.items() if kinds is None or cabinet_type in kinds]


def mechanism(p):
    """The mechanism that applies (one that does not fit the type is ignored)."""
    m = str(p.get("mechanism", "none"))
    return m if m in mechanisms_for(str(p.get("cabinet_type", "base"))) else "none"


def _box(parts, role, x0, y0, z0, x1, y1, z1):
    if x1 - x0 > 1e-6 and y1 - y0 > 1e-6 and z1 - z0 > 1e-6:
        parts.append((role, (x0, y0, z0), (x1, y1, z1)))


def _put(parts, role, face, u0, t0, z0, u1, t1, z1):
    """Box in the frame of a front: ``u`` along it, ``t`` inwards from its outer face."""
    axis, plane = face
    if axis == "-y":
        _box(parts, role, u0, plane + t0, z0, u1, plane + t1, z1)
    else:                                   # "+x": a front facing +X (left leg of an L corner), u along +Y
        _box(parts, role, plane - t1, u0, z0, plane - t0, u1, z1)


def _front(parts, f, style, handle):
    """One door / drawer / pull-out / flap in the chosen style, with its handle."""
    face, u0, u1, z0, z1, grip = f["face"], f["u0"], f["u1"], f["z0"], f["z1"], f["grip"]
    if f["kind"] == "blind":
        style = "flat" if style != "gola" else style
    if style == "gola":
        # Finger groove on the grip edge: the front is shorter, an aluminium channel sits behind.
        t0, t1 = FRONT - GOLA_CHANNEL, FRONT
        if grip == "top":
            z1 -= GOLA
            _put(parts, "handle", face, u0 - GAP, t0, z1, u1 + GAP, t1, z1 + GOLA + GAP)
        elif grip == "bottom":
            z0 += GOLA
            _put(parts, "handle", face, u0 - GAP, t0, z0 - GOLA - GAP, u1 + GAP, t1, z0)
        elif grip == "u1":
            u1 -= GOLA
            _put(parts, "handle", face, u1, t0, z0 - GAP, u1 + GOLA + GAP, t1, z1 + GAP)
        else:
            u0 += GOLA
            _put(parts, "handle", face, u0 - GOLA - GAP, t0, z0 - GAP, u0, t1, z1 + GAP)
    if style in ("flat", "gola"):
        _put(parts, "front", face, u0, 0.0, z0, u1, FRONT, z1)
    else:
        # Frame (κάσα) and a panel: deeper wood, or glass for a glazed door.
        r = min(SHAKER_RAIL, (u1 - u0) / 4, (z1 - z0) / 4)
        _put(parts, "front", face, u0, 0.0, z0, u0 + r, FRONT, z1)
        _put(parts, "front", face, u1 - r, 0.0, z0, u1, FRONT, z1)
        _put(parts, "front", face, u0 + r, 0.0, z0, u1 - r, FRONT, z0 + r)
        _put(parts, "front", face, u0 + r, 0.0, z1 - r, u1 - r, FRONT, z1)
        if style == "glass" and f["kind"] in ("door", "flap"):
            _put(parts, "glass", face, u0 + r, (FRONT - GLASS) / 2, z0 + r, u1 - r, (FRONT + GLASS) / 2, z1 - r)
        else:
            _put(parts, "front", face, u0 + r, PANEL_RECESS, z0 + r, u1 - r, FRONT, z1 - r)
    spec = f.get("handle")
    if style == "gola" or handle == "none" or spec is None:
        return
    if handle == "edge":
        # Profile on the grip edge, in front of the face.
        if grip == "top":
            _put(parts, "handle", face, u0, -0.012, z1 - EDGE_PROFILE, u1, 0.0, z1)
        elif grip == "bottom":
            _put(parts, "handle", face, u0, -0.012, z0, u1, 0.0, z0 + EDGE_PROFILE)
        elif grip == "u1":
            _put(parts, "handle", face, u1 - EDGE_PROFILE, -0.012, z0, u1, 0.0, z1)
        else:
            _put(parts, "handle", face, u0, -0.012, z0, u0 + EDGE_PROFILE, 0.0, z1)
    elif spec[0] == "h":                    # horizontal: drawers, pull-outs, flaps
        _k, cu, hz, hw = spec
        if handle == "bar":
            _put(parts, "handle", face, cu - hw / 2, -0.025, hz - 0.006, cu + hw / 2, 0.0, hz + 0.006)
        else:
            _put(parts, "handle", face, cu - 0.012, -0.025, hz - 0.012, cu + 0.012, 0.0, hz + 0.012)
    else:                                   # vertical, on the opening edge of a door
        _k, hx, hz0 = spec
        if handle == "bar":
            _put(parts, "handle", face, hx - 0.006, -0.025, hz0, hx + 0.006, 0.0, hz0 + 0.16)
        else:
            _put(parts, "handle", face, hx - 0.012, -0.025, hz0 + 0.06, hx + 0.012, 0.0, hz0 + 0.084)


def _rect_fronts(kind, mech, w, x0, x1, yf, zb, zt, doors, drawers):
    """Fronts of a rectangular cabinet ``[dict]`` and the level between drawers and doors."""
    face = ("-y", yf)
    top_grip = "bottom" if kind == "wall" else "top"
    if mech in ("cargo", "bin", "larder"):
        # One pull-out front carrying the baskets / bins.
        handle = ("v", 0.0, min(1.0, zt - 0.25)) if mech == "larder" else ("h", 0.0, zt - DRAWER_FRONT / 2, min(0.16, w * 0.5))
        return [dict(kind="pullout", face=face, u0=x0 + GAP, u1=x1 - GAP, z0=zb + GAP, z1=zt - GAP, handle=handle,
                     grip="u1" if mech == "larder" else "top")], zb
    if mech == "lift_up":
        return [dict(kind="flap", face=face, u0=x0 + GAP, u1=x1 - GAP, z0=zb + GAP, z1=zt - GAP,
                     handle=("h", 0.0, zb + 0.05, min(0.16, w * 0.5)), grip="bottom")], zb
    if kind == "corner_blind":
        # Blind part on the left (mirrored for the right), the door beside it.
        door = w - CORNER_ARM - BLIND_FILLER
        xd = x1 - door
        return [dict(kind="blind", face=face, u0=x0 + GAP, u1=xd - GAP, z0=zb + GAP, z1=zt - GAP, handle=None, grip="top"),
                dict(kind="door", face=face, u0=xd + GAP, u1=x1 - GAP, z0=zb + GAP, z1=zt - GAP,
                     handle=("v", xd + GAP + 0.04, zt - 0.20), grip="top")], zb
    fronts = []
    # Fronts: drawers at the top above the doors (or full height when no doors)
    drawer_h = DRAWER_FRONT if doors else (zt - zb) / max(drawers, 1)
    if kind == "wardrobe" or kind == "tall":
        drawer_h = min(drawer_h, 0.25)
    z_split = zt - drawers * drawer_h if doors else zb
    for k in range(drawers):
        top = zt - k * drawer_h
        fronts.append(dict(kind="drawer", face=face, u0=x0 + GAP, u1=x1 - GAP, z0=top - drawer_h + GAP, z1=top - GAP,
                           handle=("h", 0.0, top - drawer_h / 2, min(0.16, w * 0.5)), grip="top"))
    if doors:
        leaf = w / doors
        for k in range(doors):
            lx0, lx1 = x0 + k * leaf + GAP, x0 + (k + 1) * leaf - GAP
            # Handle on the opening edge: pairs open from the middle.
            right_hinge = doors > 1 and k < doors / 2
            hx = lx1 - 0.04 if right_hinge or (doors == 1) else lx0 + 0.04
            if kind == "wall":
                hz0 = zb + 0.05
            elif kind in ("tall", "wardrobe"):
                hz0 = min(1.0, z_split - 0.25)
            else:
                hz0 = z_split - 0.20
            grip = top_grip if kind not in ("tall", "wardrobe") else ("u1" if hx > (lx0 + lx1) / 2 else "u0")
            fronts.append(dict(kind="door", face=face, u0=lx0, u1=lx1, z0=zb + GAP, z1=z_split - GAP,
                               handle=("v", hx, hz0), grip=grip))
    return fronts, z_split


def _baskets(parts, xi0, xi1, yi0, yi1, z0, z1, n):
    """Pull-out frame with ``n`` wire baskets (cargo / larder)."""
    for xa, xb in ((xi0, xi0 + 0.012), (xi1 - 0.012, xi1)):        # posts of the frame, front and back
        _box(parts, "mechanism", xa, yi0 - 0.012, z0, xb, yi0, z1)
        _box(parts, "mechanism", xa, yi1, z0, xb, yi1 + 0.012, z1)
    pitch = (z1 - z0) / n
    rail = min(0.10, pitch * 0.4)
    wires = max(2, int((xi1 - xi0) / 0.03) + 1)
    for k in range(n):
        zk = z0 + k * pitch + 0.02
        for ya, yb in ((yi0, yi0 + WIRE), (yi1 - WIRE, yi1)):       # cross bars under the wires
            _box(parts, "mechanism", xi0, ya, zk - WIRE, xi1, yb, zk)
        for i in range(wires):
            xw = xi0 + (xi1 - xi0 - WIRE) * i / (wires - 1)
            _box(parts, "mechanism", xw, yi0, zk, xw + WIRE, yi1, zk + WIRE)
        zr = zk + rail
        for xa in (xi0, xi1 - WIRE):
            for ya in (yi0, yi1 - WIRE):
                _box(parts, "mechanism", xa, ya, zk + WIRE, xa + WIRE, ya + WIRE, zr - WIRE)
        _box(parts, "mechanism", xi0, yi0, zr - WIRE, xi1, yi0 + WIRE, zr)
        _box(parts, "mechanism", xi0, yi1 - WIRE, zr - WIRE, xi1, yi1, zr)
        _box(parts, "mechanism", xi0, yi0 + WIRE, zr - WIRE, xi0 + WIRE, yi1 - WIRE, zr)
        _box(parts, "mechanism", xi1 - WIRE, yi0 + WIRE, zr - WIRE, xi1, yi1 - WIRE, zr)


def _inner_drawers(parts, xi0, xi1, yi0, yi1, z0, z1, n):
    """``n`` drawers behind the doors: bottom, front, back and two sides each."""
    pitch = (z1 - z0) / n
    hd, t = min(0.16, pitch - 0.04), 0.012
    for k in range(n):
        zk = z0 + k * pitch + 0.01
        _box(parts, "mechanism", xi0, yi0, zk, xi1, yi0 + 0.016, zk + hd)
        _box(parts, "mechanism", xi0, yi1 - t, zk + t, xi1, yi1, zk + hd - 0.02)
        _box(parts, "mechanism", xi0, yi0 + 0.016, zk, xi0 + t, yi1 - t, zk + hd)
        _box(parts, "mechanism", xi1 - t, yi0 + 0.016, zk, xi1, yi1 - t, zk + hd)
        _box(parts, "mechanism", xi0 + t, yi0 + 0.016, zk, xi1 - t, yi1 - t, zk + t)


def _arc(cx, cy, rx, ry, a0, a1, n):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def _carousel_shape(p):
    """Centre and radius of the 3/4 carousel of an L corner (local frame)."""
    w, d = float(p["width"]), float(p["depth"])
    x0, x1, yf, yb = -w / 2, w / 2, -d / 2, d / 2
    cx, cy = x0 + CORNER_ARM - FRONT - 0.01, yb - CORNER_ARM + FRONT + 0.01
    r = min(x1 - CARCASS - cx, yb - BACK - cy, cx - x0 - BACK, cy - yf - CARCASS) - 0.015
    return cx, cy, r


def _half_moon_shape(p):
    """Flat edge, centre and half-axes of the half-moon trays (blind part on the left)."""
    w, d = float(p["width"]), float(p["depth"])
    x0, x1, yf, yb = -w / 2, w / 2, -d / 2, d / 2
    door = w - CORNER_ARM - BLIND_FILLER
    yi0, yi1 = yf + FRONT + 0.02, yb - BACK - 0.02
    xf = x1 - CARCASS - 0.035
    return xf, (yi0 + yi1) / 2, min(door + 0.20, xf - x0 - CARCASS - 0.02), (yi1 - yi0) / 2


def _trays(prisms, outline, rim, z0, z1, n):
    """``n`` trays (outline + a rim on its curved edge) between z0 and z1."""
    for k in range(n):
        zk = z0 + 0.02 + k * (z1 - z0) / n
        prisms.append(("mechanism", outline, zk, zk + 0.012))
        prisms.append(("mechanism", rim, zk + 0.012, zk + 0.05))


def _build(p):
    """Derived solids of the cabinet: boxes ``[(role, lo, hi)]`` and prisms ``[(role, polygon, z0, z1)]``."""
    w, d, h = float(p["width"]), float(p["depth"]), float(p["height"])
    kind = str(p.get("cabinet_type", "base"))
    plinth = min(float(p.get("plinth", 0.0)), h * 0.5)
    doors, drawers, shelves = int(p.get("doors", 0)), int(p.get("drawers", 0)), int(p.get("shelves", 0))
    handle = str(p.get("handle", "bar"))
    style = str(p.get("front_style", "flat"))
    mech = mechanism(p)
    if w < 2 * CARCASS + 0.05 or d < FRONT + BACK + 0.05 or h - plinth < 2 * CARCASS + 0.05:
        raise ValueError("cabinet is too small for its panels")
    if kind == "corner":
        return _corner(p, w, d, h, plinth, shelves, handle, style, mech)
    if kind == "corner_blind" and w < CORNER_ARM + BLIND_FILLER + 0.25:
        raise ValueError("blind corner cabinet is too narrow for its door")
    parts, prisms = [], []
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
    if mech in ("cargo", "bin", "larder", "lift_up"):
        doors = drawers = 0
    fronts, z_split = _rect_fronts(kind, mech, w, x0, x1, yf, zb, zt, doors, drawers)
    for f in fronts:
        _front(parts, f, style, handle)
    # Inside: x/y limits of what slides on runners.
    xi0, xi1, yi0, yi1 = x0 + CARCASS + 0.013, x1 - CARCASS - 0.013, yc + 0.025, yb - BACK - 0.02
    shelf_floor = inner0
    if mech in ("cargo", "bin", "larder", "carousel", "half_moon") or mech == "inner_drawers" and kind == "base":
        shelves = 0
    if mech == "inner_drawers":
        n = 3
        top = (z_split - CARCASS if doors and drawers else inner1) if kind == "base" else inner0 + n * 0.20
        _inner_drawers(parts, xi0, xi1, yi0, yi1, inner0, top, n)
        shelf_floor = top if kind == "tall" else inner0
    # Shelves inside the door zone
    top_shelf_zone = z_split - CARCASS if doors and drawers else inner1
    for k in range(shelves):
        zs = shelf_floor + (top_shelf_zone - shelf_floor) * (k + 1) / (shelves + 1)
        if kind == "wardrobe":
            zs = inner1 - 0.30 - k * 0.35          # hat shelves near the top
            if zs <= inner0 + 0.2:
                break
        _box(parts, "shelf", x0 + CARCASS, yc + 0.02, zs - CARCASS / 2, x1 - CARCASS, yb - BACK, zs + CARCASS / 2)
    if kind == "wardrobe":
        zr = inner1 - 0.30 - (0.07 if shelves else 0.0) - 0.05
        _box(parts, "rail", x0 + CARCASS, -0.01, zr - 0.01, x1 - CARCASS, 0.01, zr + 0.01)
    if mech == "cargo":
        _box(parts, "mechanism", xi0, yi0 - 0.012, inner0, xi1, yi1 + 0.012, inner0 + 0.01)     # runner plate
        _baskets(parts, xi0, xi1, yi0, yi1, inner0 + 0.01, inner1 - 0.02, 2)
    elif mech == "larder":
        _baskets(parts, xi0, xi1, yi0, yi1, inner0, inner1 - 0.02, max(3, int(round((inner1 - inner0) / 0.36))))
    elif mech == "bin":
        # Pull-out frame with lidded bins at the front (the siphon stays free behind).
        n = max(1, min(3, int((xi1 - xi0) / 0.22)))
        depth = min(0.40, yi1 - yi0 - 0.02)
        zp = inner0 + 0.017
        _box(parts, "mechanism", xi0, yi0, inner0 + 0.005, xi1, yi0 + depth + 0.02, zp)
        bw = (xi1 - xi0 - 0.01 * (n + 1)) / n
        for k in range(n):
            bx = xi0 + 0.01 + k * (bw + 0.01)
            bh = min(0.34, inner1 - zp - 0.10)
            _box(parts, "mechanism", bx + 0.004, yi0 + 0.01, zp, bx + bw - 0.004, yi0 + depth, zp + bh)
            _box(parts, "mechanism", bx, yi0 + 0.006, zp + bh, bx + bw, yi0 + depth + 0.004, zp + bh + 0.012)
    elif mech == "lift_up":
        # Lift mechanism on each side at the top, arm to the flap.
        for xa, xb in ((x0 + CARCASS, x0 + CARCASS + 0.02), (x1 - CARCASS - 0.02, x1 - CARCASS)):
            _box(parts, "mechanism", xa, yc + 0.03, inner1 - 0.17, xb, yc + 0.23, inner1 - 0.01)
            _box(parts, "mechanism", xa + 0.006, yc + 0.002, inner1 - 0.12, xb - 0.006, yc + 0.03, inner1 - 0.10)
    elif mech == "half_moon":
        xf, cy, a, b = _half_moon_shape(p)
        outline = _arc(xf, cy, a, b, 90.0, 270.0, 24)
        rim = _arc(xf, cy, a, b, 90.0, 270.0, 24) + _arc(xf, cy, a - 0.01, b - 0.01, 270.0, 90.0, 24)
        _trays(prisms, outline, rim, inner0, inner1, 2)
        _box(parts, "mechanism", xf + 0.005, cy - 0.015, inner0, x1 - CARCASS, cy + 0.015, inner1)
    if float(p.get("worktop", 0.0)):
        _box(parts, "worktop", x0, yf - OVERHANG, h, x1, yb, h + WORKTOP)
    if kind == "corner_blind" and p.get("blind_side", "left") == "right":
        parts, prisms = _mirrored(parts, prisms)
    return parts, prisms


def _mirrored(parts, prisms):
    """Left/right mirror (x → -x) of boxes and prisms, keeping polygons counter-clockwise."""
    boxes = [(role, (-hi[0], lo[1], lo[2]), (-lo[0], hi[1], hi[2])) for role, lo, hi in parts]
    return boxes, [(role, [(-x, y) for x, y in reversed(poly)], z0, z1) for role, poly, z0, z1 in prisms]


def _corner_outline(p, inset_wall, inset_end, front):
    """L polygon of a corner unit: walls at -X and +Y, the free corner at the front right.

    ``inset_wall`` from the walls, ``inset_end`` from the ends of the legs,
    ``front`` = distance of the inner faces from the door plane (negative = in front).
    """
    w, d = float(p["width"]), float(p["depth"])
    x0, x1, yf, yb = -w / 2, w / 2, -d / 2, d / 2
    xa, ya = x0 + CORNER_ARM - front, yb - CORNER_ARM + front
    return [(x0 + inset_wall, yf + inset_end), (xa, yf + inset_end), (xa, ya), (x1 - inset_end, ya),
            (x1 - inset_end, yb - inset_wall), (x0 + inset_wall, yb - inset_wall)]


def _corner(p, w, d, h, plinth, shelves, handle, style, mech):
    """L-shaped corner base unit with a bi-fold pair of doors (and the 3/4 carousel)."""
    if w < CORNER_ARM + 0.15 or d < CORNER_ARM + 0.15:
        raise ValueError("corner cabinet legs are too short")
    parts, prisms = [], []
    x0, x1, yf, yb = -w / 2, w / 2, -d / 2, d / 2
    xa, ya = x0 + CORNER_ARM, yb - CORNER_ARM            # door planes of the two legs
    zb, zt = plinth, h
    inner0, inner1 = zb + CARCASS, zt - CARCASS
    if plinth > 0:
        prisms.append(("plinth", _corner_outline(p, BACK, CARCASS, PLINTH_SETBACK), 0.0, plinth))
    zs0 = 0.0 if plinth > 0 else zb                       # end panels run to the floor
    _box(parts, "carcass", x0, yf, zs0, xa - FRONT, yf + CARCASS, zt)                 # end of the left leg
    _box(parts, "carcass", x1 - CARCASS, ya + FRONT, zs0, x1, yb, zt)                 # end of the back leg
    _box(parts, "carcass", x0, yf + CARCASS, inner0, x0 + BACK, yb, inner1)           # backs on both walls
    _box(parts, "carcass", x0 + BACK, yb - BACK, inner0, x1 - CARCASS, yb, inner1)
    inner = _corner_outline(p, BACK, CARCASS, FRONT)
    prisms.append(("carcass", inner, zb, inner0))
    prisms.append(("carcass", inner, inner1, zt))
    # Bi-fold doors on the two inner faces; the handle on the free edge of the back one.
    fronts = [dict(kind="door", face=("+x", xa), u0=yf + GAP, u1=ya + FRONT - GAP, z0=zb + GAP, z1=zt - GAP,
                   handle=None, grip="top"),
              dict(kind="door", face=("-y", ya), u0=xa + GAP, u1=x1 - GAP, z0=zb + GAP, z1=zt - GAP,
                   handle=("v", x1 - GAP - 0.04, zt - 0.20), grip="top")]
    for f in fronts:
        _front(parts, f, style, handle)
    if mech == "carousel":
        cx, cy, r = _carousel_shape(p)
        outline = [(cx, cy)] + _arc(cx, cy, r, r, 0.0, 270.0, 27)
        rim = _arc(cx, cy, r, r, 0.0, 270.0, 27) + _arc(cx, cy, r - 0.01, r - 0.01, 270.0, 0.0, 27)
        _trays(prisms, outline, rim, inner0, inner1, 2)
        prisms.append(("mechanism", _arc(cx, cy, 0.015, 0.015, 0.0, 315.0, 7), inner0, inner1))   # pole
    else:
        shelf = _corner_outline(p, BACK, CARCASS, FRONT + 0.02)
        for k in range(shelves):
            zs = inner0 + (inner1 - inner0) * (k + 1) / (shelves + 1)
            prisms.append(("shelf", shelf, zs - CARCASS / 2, zs + CARCASS / 2))
    if float(p.get("worktop", 0.0)):
        prisms.append(("worktop", _corner_outline(p, 0.0, 0.0, -OVERHANG), h, h + WORKTOP))
    return parts, prisms


def cabinet_boxes(p):
    """Derived boxes ``[(role, lo, hi)]`` in the local frame."""
    return _build(p)[0]


def cabinet_prisms(p):
    """Derived prisms ``[(role, polygon, z0, z1)]`` (L corner panels, carousel trays) in the local frame."""
    return _build(p)[1]


def cabinet_roles(p):
    """Roles present in the cabinet, in drawing order."""
    boxes, prisms = _build(p)
    out = []
    for role in [b[0] for b in boxes] + [q[0] for q in prisms]:
        if role not in out:
            out.append(role)
    return out


def front_counts(p):
    """How many doors, drawers, pull-outs, flaps and blind panels the cabinet has."""
    w, d, h = float(p["width"]), float(p["depth"]), float(p["height"])
    kind, mech = str(p.get("cabinet_type", "base")), mechanism(p)
    if kind == "corner":
        return {"door": 2}
    doors, drawers = int(p.get("doors", 0)), int(p.get("drawers", 0))
    if mech in ("cargo", "bin", "larder", "lift_up"):
        doors = drawers = 0
    plinth = min(float(p.get("plinth", 0.0)), h * 0.5)
    fronts, _z = _rect_fronts(kind, mech, w, -w / 2, w / 2, -d / 2, plinth, h, doors, drawers)
    out = {}
    for f in fronts:
        out[f["kind"]] = out.get(f["kind"], 0) + 1
    return out


def cabinet_mesh(p):
    """World-space (vertices, triangles, roles) of the cabinet."""
    a = math.radians(float(p.get("rotation", 0.0)))
    c, s = math.cos(a), math.sin(a)
    ox, oy, oz = float(p["x"]), float(p["y"]), float(p["z"])
    verts, tris, roles = [], [], []
    quads = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    boxes, prisms = _build(p)
    for role, lo, hi in boxes:
        base = len(verts)
        for x in (lo[0], hi[0]):
            for y in (lo[1], hi[1]):
                for z in (lo[2], hi[2]):
                    verts.append((ox + c * x - s * y, oy + s * x + c * y, oz + z))
        for q0, q1, q2, q3 in quads:
            tris += [(base + q0, base + q1, base + q2), (base + q0, base + q2, base + q3)]
            roles += [role, role]
    if prisms:
        from archforge.geometry.mesh import _triangulate
    for role, poly, z0, z1 in prisms:
        # Same winding as the boxes above (faces towards the inside of the solid).
        if sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly))) < 0:
            poly = poly[::-1]
        base, n = len(verts), len(poly)
        for z in (z0, z1):
            verts += [(ox + c * x - s * y, oy + s * x + c * y, oz + z) for x, y in poly]
        cap = _triangulate(poly)
        tris += [(base + i, base + j, base + k) for i, j, k in cap]
        tris += [(base + n + i, base + n + k, base + n + j) for i, j, k in cap]
        for i in range(n):
            j = (i + 1) % n
            tris += [(base + i, base + n + i, base + n + j), (base + i, base + n + j, base + j)]
        roles += [role] * (2 * len(cap) + 2 * n)
    return tuple(verts), tuple(tris), tuple(roles)


def footprint(p):
    """Rotated plan outline (carcass + fronts), counter-clockwise; L-shaped for a corner unit."""
    w, d = float(p["width"]), float(p["depth"])
    if p.get("cabinet_type") == "corner":
        return _world(p, _corner_outline(p, 0.0, 0.0, 0.0))
    return _world(p, [(-w / 2, -d / 2), (w / 2, -d / 2), (w / 2, d / 2), (-w / 2, d / 2)])


def front_line(p):
    """Plan line marking the face of the doors (inside the footprint)."""
    w, d = float(p["width"]), float(p["depth"])
    if p.get("cabinet_type") == "corner":
        xa, ya = -w / 2 + CORNER_ARM - FRONT, d / 2 - CORNER_ARM + FRONT
        return _world(p, [(xa, -d / 2), (xa, ya), (w / 2, ya)])
    return _world(p, [(-w / 2, -d / 2 + FRONT), (w / 2, -d / 2 + FRONT)])


def plan_marks(p):
    """Hidden lines of a mechanism that shows in plan (carousel, half-moon trays): ``[[(x, y)…]]``."""
    mech, kind = mechanism(p), p.get("cabinet_type")
    if mech == "carousel":
        cx, cy, r = _carousel_shape(p)
        return [_world(p, [(cx, cy)] + _arc(cx, cy, r, r, 0.0, 270.0, 27) + [(cx, cy)])]
    if mech == "half_moon":
        xf, cy, a, b = _half_moon_shape(p)
        pts = _arc(xf, cy, a, b, 90.0, 270.0, 24)
        if kind == "corner_blind" and p.get("blind_side", "left") == "right":
            pts = [(-x, y) for x, y in pts]
        return [_world(p, pts + pts[:1])]
    return []


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


def plan_box(x, y, rotation, width, depth):
    """Plan corners of a cabinet (centre x, y; local X along the run)."""
    a = math.radians(rotation)
    ux, uy, nx, ny = math.cos(a), math.sin(a), -math.sin(a), math.cos(a)
    return [(x + ux * sx * width / 2 + nx * sy * depth / 2, y + uy * sx * width / 2 + ny * sy * depth / 2)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


def _overlap(p, q, margin=0.01):
    """Separating-axis test for two convex polygons, shrunk by ``margin`` (touching is not overlapping)."""
    for poly in (p, q):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            ax, ay = -(y2 - y1), x2 - x1
            L = math.hypot(ax, ay) or 1.0
            ax, ay = ax / L, ay / L
            pa = [vx * ax + vy * ay for vx, vy in p]; qa = [vx * ax + vy * ay for vx, vy in q]
            if max(pa) <= min(qa) + margin or max(qa) <= min(pa) + margin:
                return False
    return True


def _wall_box(p):
    x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
    L = math.hypot(x2 - x1, y2 - y1) or 1.0
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    t = float(p.get("thickness", .2)) / 2
    return [(x1 - uy * t, y1 + ux * t), (x2 - uy * t, y2 + ux * t), (x2 + uy * t, y2 - ux * t), (x1 + uy * t, y1 - ux * t)]


def _levels_overlap(a, b):
    """Base and wall cabinets share the plan; they collide only if their heights overlap."""
    za, zb = float(a.get("z", 0.0)), float(b.get("z", 0.0))
    return za < zb + float(b.get("height", .86)) - .01 and zb < za + float(a.get("height", .86)) - .01


def snap_to_side_walls(doc, x, y, rotation, width, depth, *, tolerance=0.35, z=None):
    """Slide along the run so a side touches the face of a wall across the run (the corner of the kitchen)."""
    level = doc.work_plane.origin[2] if z is None else z
    a = math.radians(rotation)
    ux, uy = math.cos(a), math.sin(a)
    best = None
    for e in doc.entities.values():
        if e.kind != "wall" or abs(float(e.params.get("z", 0.0)) - level) > 0.05:
            continue
        box = _wall_box(e.params)
        # The wall must lie across the run: its faces along the run direction bound the cabinet.
        along = [(vx - x) * ux + (vy - y) * uy for vx, vy in box]
        across_n = [(vx - x) * -uy + (vy - y) * ux for vx, vy in box]
        if max(across_n) < -depth / 2 or min(across_n) > depth / 2:
            continue                                  # not beside the cabinet
        lo, hi = min(along), max(along)
        if hi - lo > 1.5 * (max(across_n) - min(across_n)) + 1.0:
            continue                                  # a wall along the run, not across it
        # The wall on the cabinet's left gets its left side, the one on the right its right side.
        target = hi + width / 2 if (lo + hi) / 2 < 0 else lo - width / 2
        if abs(target) <= tolerance and (best is None or abs(target) < abs(best)):
            best = target
    if best is None or abs(best) > tolerance:
        return x, y
    return x + ux * best, y + uy * best


def fit_problem(doc, params, *, ignore=(), host=None):
    """Why a cabinet with ``params`` does not fit (a wall or another cabinet in the way), or None."""
    z = float(params.get("z", 0.0))
    level = doc.work_plane.origin[2]
    me = plan_box(float(params["x"]), float(params["y"]), float(params.get("rotation", 0.0)),
                   float(params["width"]), float(params["depth"]))
    for e in doc.entities.values():
        if e.id in ignore:
            continue
        if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - level) < .05 and _overlap(me, _wall_box(e.params), .015):
            return "πέφτει πάνω σε τοίχο"
        if e.kind == "cabinet" and _levels_overlap(params, e.params):
            q = e.params
            if _overlap(me, plan_box(float(q["x"]), float(q["y"]), float(q.get("rotation", 0.0)), float(q["width"]), float(q["depth"]))):
                return f"πέφτει πάνω σε «{e.name or 'ντουλάπι'}»"
    return None


def snap_to_neighbours(doc, x, y, rotation, width, depth, *, tolerance=0.35, ignore=()):
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
