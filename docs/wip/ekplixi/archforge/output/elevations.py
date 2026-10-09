"""Elevations (όψεις) and the door/window schedule (πίνακας κουφωμάτων), as PDF sheets.

Όψεις — Βόρεια, Νότια, Ανατολική, Δυτική — orthographic and vector on A4
landscape, two per page, all four at the same scale.  Every visible thing is
a flat face in 3D (wall faces, wall ends, slab and column sides, the gable
infills and the pitched roof drawn as a slab of the roof's thickness) projected
on the façade plane:

* a face is kept only when it looks towards the viewer (back faces and faces
  seen edge-on are dropped);
* hidden lines by painter's order: faces are drawn from the farthest to the
  nearest (by their nearest point) and filled, so nearer walls and roofs cover
  what is behind them;
* doors, windows and openings are drawn on the wall face that hosts them
  (same depth, just in front), with their schedule mark;
* ground line with earth hatch, level marks on the left (±0.00, +3.00 …,
  ridge/top), storey heights and the overall height dimensioned on the right.

Πίνακας κουφωμάτων — one row per TYPE (same kind, size, sill, shape and for
doors exterior/interior): mark, a small elevation sketch, kind, width ×
height, sill, quantity, storeys and the rooms it serves.

Marks (they must not clash with the structural ones: Κ columns, Δ beams,
Πλ slabs, Π footings):

* «Θ1, Θ2 …»   θύρες (doors);
* «ΠΡ1, ΠΡ2 …» παράθυρα (windows) — «Π» alone is the footings' mark;
* «ΑΝ1, ΑΝ2 …» ανοίγματα χωρίς κούφωμα (plain/arched openings).

Everything comes from the Document; nothing is typed twice.
"""
from __future__ import annotations

import datetime
import math

from PySide6.QtCore import QMarginsF, Qt
from PySide6.QtGui import QColor, QPageLayout, QPageSize, QPainter, QPdfWriter

from archforge.output.pdf import (DIM, INK, SCALES, Sheet, _dimension, _on_segment_dist, _scale_bar, _title_block,
                                  level_name)

ROOF_THICK = 0.25            # m, rafter + boarding + tiles, as drawn on the elevation
WALL_FILL = QColor(255, 255, 255)
ROOF_FILL = QColor(232, 205, 188)
ROOF_EDGE_FILL = QColor(214, 178, 156)
SLAB_FILL = QColor(222, 222, 222)
GLASS = QColor(214, 230, 238)
DOOR_FILL = QColor(236, 224, 206)
VOID_FILL = QColor(95, 95, 95)
FAINT = QColor(150, 150, 150)
MARK_INK = QColor(176, 106, 48)

# key, title, viewing direction in plan (the viewer looks along it)
VIEWS = (("north", "Βόρεια όψη", (0.0, -1.0)), ("south", "Νότια όψη", (0.0, 1.0)),
         ("east", "Ανατολική όψη", (-1.0, 0.0)), ("west", "Δυτική όψη", (1.0, 0.0)))

PREFIX = {"door": "Θ", "window": "ΠΡ", "opening": "ΑΝ"}
KIND_ORDER = {"door": 0, "window": 1, "opening": 2}


# ================================================================ schedule (pure)
def _opening_dims(e):
    p = e.params
    w = float(p.get("width", 0.9))
    h = float(p.get("height", 2.1 if e.kind == "door" else 1.2))
    sill = 0.0 if e.kind == "door" else float(p.get("sill", 0.9 if e.kind == "window" else 0.0))
    shape = str(p.get("shape", "rectangle")) if e.kind == "opening" else "rectangle"
    rise = float(p.get("arch_rise", min(w / 2, .4))) if shape == "arch" else 0.0
    return w, h, sill, shape, rise


def _room_name(name):
    import re
    m = re.fullmatch(r"Room (\d+)", str(name))
    return f"Χώρος {m.group(1)}" if m else str(name)


def _type_text(kind, exterior, shape):
    if kind == "door":
        return "Εξωτερική θύρα" if exterior else "Εσωτερική θύρα"
    if kind == "window":
        return "Παράθυρο"
    return "Τοξωτό άνοιγμα" if shape == "arch" else "Άνοιγμα"


def opening_schedule(doc):
    """Door / window / opening schedule: one row per type, marks Θ (doors), ΠΡ (windows), ΑΝ (openings).

    Each row: ``{"mark", "kind", "type", "width", "height", "sill", "shape", "arch_rise", "exterior",
    "count", "ids", "storeys", "rooms"}`` (metres).  Types are ordered doors → windows → openings,
    larger first; only openings hosted by a wall are listed.
    """
    from archforge.assistant.understanding import _opening_sides, inside, read_drawing
    from archforge.mep.ventilation import exterior_walls
    storeys = read_drawing(doc)["storeys"]
    ext_cache = {}

    def storey_of(z):
        return next((s for s in storeys if abs(float(s["z"]) - z) < .05), None)

    def is_exterior(wall, z):
        if z not in ext_cache:
            ext_cache[z] = {w.id for w, _n in exterior_walls(doc, z)}
        return wall.id in ext_cache[z]
    groups = {}
    for e in sorted(doc.entities.values(), key=lambda e: e.id):
        if e.kind not in PREFIX or not e.parent_id:
            continue
        host = doc.entities.get(e.parent_id)
        if host is None or host.kind != "wall" or str(host.params.get("phase", "new")) == "demolish":
            continue
        z = float(host.params.get("z", 0.0))
        w, h, sill, shape, rise = _opening_dims(e)
        ext = is_exterior(host, z) if e.kind == "door" else False
        key = (e.kind, round(w, 3), round(h, 3), round(sill, 3), shape, round(rise, 3), ext)
        g = groups.setdefault(key, {"kind": e.kind, "type": _type_text(e.kind, ext, shape), "width": w, "height": h,
                                    "sill": sill, "shape": shape, "arch_rise": rise, "exterior": ext, "count": 0,
                                    "ids": [], "storeys": [], "rooms": [], "_z": []})
        g["count"] += 1
        g["ids"].append(e.id)
        s = storey_of(z)
        sname = level_name(s["name"]) if s else f"{z:+.2f}"
        if sname not in g["storeys"]:
            g["storeys"].append(sname); g["_z"].append(z)
        if s:
            sides = _opening_sides(doc, e)
            for r in s["rooms"]:
                if any(inside(r["polygon"], sx, sy) for sx, sy in sides):
                    rn = _room_name(r["name"])
                    if rn not in g["rooms"]:
                        g["rooms"].append(rn)
    rows = sorted(groups.values(), key=lambda g: (KIND_ORDER[g["kind"]], not g["exterior"], -g["width"], -g["height"],
                                                  g["sill"], g["shape"]))
    numbers = {}
    for g in rows:
        numbers[g["kind"]] = numbers.get(g["kind"], 0) + 1
        g["mark"] = f"{PREFIX[g['kind']]}{numbers[g['kind']]}"
        g["storeys"] = [n for _z, n in sorted(zip(g.pop("_z"), g["storeys"]))]
    return rows


def opening_marks(doc):
    """``{opening_id: mark}`` from the schedule (the same mark on the elevations)."""
    return {i: g["mark"] for g in opening_schedule(doc) for i in g["ids"]}


# ================================================================ elevation geometry (pure)
def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == "wall" and str(e.params.get("phase", "new")) != "demolish"]


def _ccw(poly):
    a = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return poly if a >= 0 else poly[::-1]


def _faces(doc):
    """All candidate faces in 3D: ``[{"pts": [(x,y,z)…], "n": (nx,ny) or None, "role", ...}]``.

    ``n`` is the horizontal outward normal of a vertical face (None for a roof top, whose facing is
    decided from its 3D normal ``n3``).
    """
    faces = []
    walls = _walls(doc)
    by_z = {}
    for w in walls:
        by_z.setdefault(round(float(w.params.get("z", 0.0)), 2), []).append(w)

    def vertical(a, b, z0, z1, role, **kw):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 1e-6 or z1 - z0 < 1e-6:
            return
        n = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)          # right of a→b
        faces.append(dict(pts=[(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)], n=n, role=role, **kw))

    def prism(poly, z0, z1, role, **kw):
        poly = _ccw([tuple(map(float, q)) for q in poly])
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            vertical(a, b, z0, z1, role, **kw)               # CCW: right of a→b is outside
    # Walls: both long faces (extended into the walls they meet) and the free ends.
    for w in walls:
        p = w.params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-6:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        nx, ny = -uy, ux
        t = float(p.get("thickness", .2))
        z0 = float(p.get("z", 0.0)); z1 = z0 + float(p.get("height", 3.0))
        same = by_z.get(round(z0, 2), [])

        def joined(x, y):
            return any(o.id != w.id and _on_segment_dist(x, y, *(float(o.params[k]) for k in ("x1", "y1", "x2", "y2"))) < .01
                       for o in same)
        ja, jb = joined(ax, ay), joined(bx, by)
        s0, s1 = (-t / 2 if ja else 0.0), (L + t / 2 if jb else L)
        P = lambda u, s: (ax + ux * u + nx * s, ay + uy * u + ny * s)
        frame = {"a": (ax, ay), "u": (ux, uy), "n": (nx, ny), "t": t, "z": z0}
        vertical(P(s1, t / 2), P(s0, t / 2), z0, z1, "wall", wall=w, side=1.0, frame=frame)    # left side (+n)
        vertical(P(s0, -t / 2), P(s1, -t / 2), z0, z1, "wall", wall=w, side=-1.0, frame=frame)
        if not ja:
            vertical(P(s0, t / 2), P(s0, -t / 2), z0, z1, "wall-end")
        if not jb:
            vertical(P(s1, -t / 2), P(s1, t / 2), z0, z1, "wall-end")
    # Columns.
    for c in doc.entities.values():
        if c.kind != "structural_column":
            continue
        p = c.params
        x, y, z = float(p["x"]), float(p["y"]), float(p.get("z", 0.0))
        w2, d2 = float(p.get("width", .3)) / 2, float(p.get("depth", .3)) / 2
        r = math.radians(float(p.get("rotation", 0.0)))
        cr, sr = math.cos(r), math.sin(r)
        pts = [(x + cr * dx - sr * dy, y + sr * dx + cr * dy) for dx, dy in ((-w2, -d2), (w2, -d2), (w2, d2), (-w2, d2))]
        prism(pts, z, z + float(p.get("height", 3.0)), "column")
    # Room slabs (floors, ceilings, flat roofs/terraces) and plain floors: their edges.
    from archforge.architecture.rooms import ROOM_SLAB_KINDS, room_slab_geometry
    for e in doc.entities.values():
        if e.kind in ROOM_SLAB_KINDS:
            try:
                g = room_slab_geometry(doc, e)
            except Exception:
                g = None
            if not g:
                continue
            for part in g.get("parts") or [g["points"]]:
                if len(part) >= 3:
                    prism(part, g["z"], g["z"] + g["thickness"], "roof-slab" if e.kind == "room_roof" else "slab")
        elif e.kind == "floor" and len(e.params.get("points", ())) >= 3:
            z = float(e.params["z"])
            prism(e.params["points"], z, z + float(e.params.get("thickness", .2)), "slab")
    # Pitched roofs: each plane as a slab of ROOF_THICK, plus the gable infills.
    from archforge.structure.timber_roof import gable_walls, height_at, planes
    for e in doc.entities.values():
        if e.kind != "pitched_roof":
            continue
        p = e.params
        for plane in planes(p):
            poly = _ccw([tuple(q) for q in plane[0]])
            bottom = [(x, y, height_at(p, plane, x, y)) for x, y in poly]
            top = [(x, y, z + ROOF_THICK) for x, y, z in bottom]
            (ax_, ay_, az), (bx_, by_, bz), (cx_, cy_, cz) = top[0], top[1], top[2]
            # Normal of the top surface (pointing up).
            ux, uy, uz = bx_ - ax_, by_ - ay_, bz - az
            vx, vy, vz = cx_ - ax_, cy_ - ay_, cz - az
            n3 = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
            if n3[2] < 0:
                n3 = tuple(-c for c in n3)
            faces.append(dict(pts=top, n=None, n3=n3, role="roof"))
            for i in range(len(poly)):
                j = (i + 1) % len(poly)
                a, b = poly[i], poly[j]
                L = math.hypot(b[0] - a[0], b[1] - a[1])
                if L < 1e-6:
                    continue
                n = ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)
                faces.append(dict(pts=[bottom[i], bottom[j], top[j], top[i]], n=n, role="roof-edge"))
        for verts, _tris in gable_walls(p):
            m = len(verts) // 2
            front, back = verts[:m], verts[m:]
            dx, dy = front[0][0] - back[0][0], front[0][1] - back[0][1]
            L = math.hypot(dx, dy) or 1.0
            faces.append(dict(pts=list(front), n=(dx / L, dy / L), role="gable"))
    return faces


def project(doc, view):
    """Faces of one elevation, painter-sorted: ``[(depth, role, [(s, z)…], face)]`` farthest first."""
    vx, vy = view
    rx, ry = vy, -vx                                         # paper right
    items = []
    for f in _faces(doc):
        if f["n"] is not None:
            if f["n"][0] * vx + f["n"][1] * vy > -1e-6:
                continue
        else:
            n3 = f["n3"]
            if n3[0] * vx + n3[1] * vy > -1e-6:
                continue
        pts2 = [(x * rx + y * ry, z) for x, y, z in f["pts"]]
        a = sum(pts2[i][0] * pts2[(i + 1) % len(pts2)][1] - pts2[(i + 1) % len(pts2)][0] * pts2[i][1] for i in range(len(pts2)))
        if abs(a) < 1e-6:
            continue
        depth = min(x * vx + y * vy for x, y, _z in f["pts"])
        items.append((depth, f["role"], pts2, f))
    prio = {"wall-end": 0, "column": 0, "slab": 1, "roof-slab": 1, "wall": 1, "gable": 1, "roof-edge": 2, "roof": 3}
    items.sort(key=lambda it: (-round(it[0], 4), prio.get(it[1], 0)))
    return items


def _opening_shape(e, frame, side, rx, ry):
    """Opening rectangle on the paper axis: (s0, s1, z0, z1, shape, rise)."""
    w, h, sill, shape, rise = _opening_dims(e)
    c = float(e.params.get("offset", 0.0))
    (ax, ay), (ux, uy), (nx, ny), t = frame["a"], frame["u"], frame["n"], frame["t"]
    pts = [(ax + ux * u + nx * side * t / 2, ay + uy * u + ny * side * t / 2) for u in (c - w / 2, c + w / 2)]
    ss = sorted(x * rx + y * ry for x, y in pts)
    z0 = frame["z"] + sill
    return ss[0], ss[1], z0, z0 + h, shape, rise


def _levels(doc):
    zs = sorted({round(float(w.params.get("z", 0.0)), 3) for w in _walls(doc)})
    return zs


# ================================================================ drawing
def _draw_elevation(sh, doc, view, to_mm, marks, children):
    vx, vy = view
    rx, ry = vy, -vx
    for depth, role, pts2, f in project(doc, view):
        mm = [to_mm(*q) for q in pts2]
        if role == "roof":
            sh.poly(mm, width=.3, fill=ROOF_FILL)
        elif role == "roof-edge":
            sh.poly(mm, width=.25, fill=ROOF_EDGE_FILL)
        elif role in ("slab", "roof-slab"):
            sh.poly(mm, width=.3, fill=SLAB_FILL)
        else:
            sh.poly(mm, width=.35 if role == "wall" else .3, fill=WALL_FILL)
        if role == "wall":
            for e in children.get(f["wall"].id, ()):
                _draw_opening(sh, e, _opening_shape(e, f["frame"], f["side"], rx, ry), to_mm, marks.get(e.id))


def _arch_path(sh, s0, s1, z0, z1, rise, to_mm, steps=16):
    pts = [(s0, z0), (s1, z0), (s1, z1 - rise)]
    c, half = (s0 + s1) / 2, (s1 - s0) / 2
    for i in range(1, steps):
        a = math.pi * i / steps
        pts.append((c + half * math.cos(a), z1 - rise + rise * math.sin(a)))
    pts.append((s0, z1 - rise))
    return [to_mm(*q) for q in pts]


def _draw_opening(sh, e, rect, to_mm, mark):
    s0, s1, z0, z1, shape, rise = rect
    (x0, y1), (x1, y0) = to_mm(s0, z0), to_mm(s1, z1)      # paper: y0 top, y1 bottom
    w, h = x1 - x0, y1 - y0
    fr = min(.6, max(.25, min(w, h) * .06))                  # frame width (mm on paper)
    if e.kind == "window":
        sh.rect(x0, y0, w, h, width=.3, fill=WALL_FILL)
        sh.rect(x0 + fr, y0 + fr, w - 2 * fr, h - 2 * fr, width=.18, fill=GLASS)
        if s1 - s0 > 1.0:                                    # two sashes
            sh.line(x0 + w / 2, y0 + fr, x0 + w / 2, y1 - fr, width=.25)
        sh.line(x0 - .6, y1, x1 + .6, y1, width=.4)           # sill
    elif e.kind == "door":
        sh.rect(x0, y0, w, h, width=.3, fill=WALL_FILL)
        sh.rect(x0 + fr, y0 + fr, w - 2 * fr, h - fr, width=.18, fill=DOOR_FILL)
        if w > 4:
            sh.rect(x0 + fr + w * .12, y0 + fr + h * .1, w - 2 * fr - w * .24, h * .35, width=.12)
            sh.rect(x0 + fr + w * .12, y0 + fr + h * .52, w - 2 * fr - w * .24, h * .35, width=.12)
        sh.line(x1 - fr - w * .14, y0 + h * .52, x1 - fr - w * .14 - max(.6, w * .1), y0 + h * .52, width=.3)
    else:
        if shape == "arch" and rise > 0:
            sh.poly(_arch_path(sh, s0, s1, z0, z1, rise, to_mm), width=.3, fill=VOID_FILL)
        else:
            sh.rect(x0, y0, w, h, width=.3, fill=VOID_FILL)
    if mark and w > 3:
        sh.text((x0 + x1) / 2, y0 + min(2.2, h / 3), mark, size=5.5, bold=True, align="center", w=12,
                color=QColor(255, 255, 255) if e.kind == "opening" else MARK_INK)


def _level_text(z):
    return "±0.00" if abs(z) < .005 else f"{z:+.2f}".replace("-", "−")


def _level_mark(sh, x, y, z, label, x_edge):
    sh.line(x + 3, y, x_edge - 1, y, color=FAINT, width=.12, style=Qt.PenStyle.DashLine)
    sh.poly([(x, y), (x + 1.6, y - 2.4), (x - 1.6, y - 2.4)], width=.15, fill=INK)
    sh.text(x - 2.2, y - 3.6, _level_text(z), size=6.5, bold=True, align="right", w=20)
    if label:
        sh.text(x - 2.2, y + 1.3, label, size=5.5, align="right", w=24, color=QColor(100, 100, 100))


def _bounds(doc, view):
    pts = [q for _d, _r, pts2, _f in project(doc, view) for q in pts2]
    if not pts:
        return None
    return min(q[0] for q in pts), max(q[0] for q in pts), min(q[1] for q in pts), max(q[1] for q in pts)


LEFT_MM, RIGHT_MM, LABEL_MM = 26.0, 22.0, 14.0


def _layout(bounds):
    """(scale, slots): the largest scale at which every elevation fits; slots are (x, y, w, h) in mm."""
    W = max(b[1] - b[0] for b in bounds) + 2.0               # + ground line run-out
    H = max(b[3] - min(0.0, b[2]) for b in bounds) + .6
    side = [(12, 20, 136, 152), (150, 20, 136, 152)]
    stacked = [(12, 18, 275, 78), (12, 97, 275, 78)]

    def fits(slots, s):
        k = 1000.0 / s
        x, y, w, h = slots[0]
        return W * k <= w - LEFT_MM - RIGHT_MM and H * k <= h - LABEL_MM
    best = None
    for slots in (stacked, side):
        s = next((s for s in SCALES if fits(slots, s)), None)
        if s is not None and (best is None or s < best[0]):
            best = (s, slots)
    return best or (SCALES[-1], stacked)


def _children(doc):
    out = {}
    for e in doc.entities.values():
        if e.kind in PREFIX and e.parent_id:
            out.setdefault(e.parent_id, []).append(e)
    return out


def _elevation_in_slot(sh, doc, view, title, b, slot, scale, marks, children, levels, top_z):
    k = 1000.0 / scale
    x, y, w, h = slot
    ground = 0.0 if any(abs(z) < .05 for z in levels) or not levels else min(levels)
    s_min, s_max = b[0], b[1]
    z_lo = min(ground, b[2])
    left = x + LEFT_MM + (w - LEFT_MM - RIGHT_MM - (s_max - s_min) * k) / 2
    base = y + h - LABEL_MM - .3 * k                      # paper y of z_lo

    def to_mm(s, z):
        return left + (s - s_min) * k, base - (z - z_lo) * k
    _draw_elevation(sh, doc, view, to_mm, marks, children)
    # Ground: earth hatch below the line, run out 1 m each side.
    gx0, gy = to_mm(s_min - 1.0, ground)
    gx1, _ = to_mm(s_max + 1.0, ground)
    sh.rect(gx0, gy, gx1 - gx0, 2.2, color=QColor(255, 255, 255), width=.01, fill=QColor(255, 255, 255))
    i = 0.0
    while gx0 + i < gx1 - 1.5:
        sh.line(gx0 + i, gy + 2.2, gx0 + i + 1.6, gy + .2, color=QColor(120, 120, 120), width=.1)
        i += 1.8
    sh.line(gx0, gy, gx1, gy, width=.6)
    # Level marks on the left: every storey, then the top.
    mx = left - 12
    marks_z = [(z, level_name(n)) for z, n in levels_named(doc) if z >= z_lo - 1e-6]
    if not any(abs(z - ground) < .005 for z, _n in marks_z):
        marks_z.insert(0, (ground, ""))
    marks_z.append((top_z, "Κορυφή"))
    last = None
    for z, label in sorted(marks_z):
        if last is not None and (z - last) * k < 5:
            continue
        _level_mark(sh, mx, to_mm(0, z)[1], z, label, left)
        last = z
    # Heights on the right: storey chain and the overall.
    rx_ = to_mm(s_max, 0)[0]
    chain = sorted({ground, *[z for z, _n in marks_z if z > ground - 1e-6], top_z})
    to_mm_dim = lambda s, z: to_mm(s, z)
    if len(chain) > 2:
        for a, c in zip(chain, chain[1:]):
            if c - a > .05:
                _dimension(sh, (s_max, a), (s_max, c), (1.0, 0.0), 6.0, c - a, to_mm_dim)
        _dimension(sh, (s_max, ground), (s_max, top_z), (1.0, 0.0), 13.0, top_z - ground, to_mm_dim)
    else:
        _dimension(sh, (s_max, ground), (s_max, top_z), (1.0, 0.0), 6.0, top_z - ground, to_mm_dim)
    # Title under the drawing.
    cx = (to_mm(s_min, 0)[0] + rx_) / 2
    sh.text(cx, base + 6.5, title, size=10.5, bold=True, align="center", w=80)
    sh.line(cx - 16, base + 9.4, cx + 16, base + 9.4, width=.3)
    sh.text(cx, base + 12, f"1:{scale}", size=7, align="center", w=40, color=QColor(90, 90, 90))


def levels_named(doc):
    """``[(z, storey name)]`` for the storeys that have walls, lowest first."""
    from archforge.assistant.understanding import read_drawing
    return [(float(s["z"]), s["name"]) for s in read_drawing(doc)["storeys"] if s["walls"]]


def _top_z(doc, b_all):
    return max(b[3] for b in b_all)


def draw_elevations(sh, doc, new_page, project, date, page_no):
    """The four elevations, two per page through ``new_page()``; returns the scales used."""
    views = [(key, title, v, _bounds(doc, v)) for key, title, v in VIEWS]
    views = [t for t in views if t[3] is not None]
    if not views:
        return []
    scale, slots = _layout([t[3] for t in views])
    marks, children = opening_marks(doc), _children(doc)
    levels = _levels(doc)
    top_z = _top_z(doc, [t[3] for t in views])
    scales = []
    for i in range(0, len(views), 2):
        pair = views[i:i + 2]
        new_page()
        sh.text(12, 10, "Όψεις", size=13, bold=True, w=200)
        for (key, title, v, b), slot in zip(pair, slots):
            _elevation_in_slot(sh, doc, v, title, b, slot, scale, marks, children, levels, top_z)
        _scale_bar(sh, 14, 190, scale)
        _title_block(sh, "Όψεις — " + " · ".join(t[1].replace(" όψη", "") for t in pair), scale, page_no(), project, date)
        scales.append(scale)
    return scales


# ---------------------------------------------------------------- schedule page
def _sketch(sh, g, cx, cy, k):
    """Small elevation of one opening type centred at (cx, cy) mm; k = mm per metre."""
    w, h, sill = g["width"] * k, g["height"] * k, g["sill"] * k
    floor_y = cy + (h + sill) / 2
    x0, y0 = cx - w / 2, floor_y - sill - h
    sh.line(x0 - 2.5, floor_y, x0 + w + 2.5, floor_y, width=.3)
    if g["kind"] == "window":
        sh.rect(x0, y0, w, h, width=.3, fill=WALL_FILL)
        sh.rect(x0 + .5, y0 + .5, w - 1, h - 1, width=.15, fill=GLASS)
        n = 2 if g["width"] > 1.0 else 1
        for j in range(n):
            a, b = x0 + .5 + j * (w - 1) / n, x0 + .5 + (j + 1) * (w - 1) / n
            if j:
                sh.line(a, y0 + .5, a, y0 + h - .5, width=.25)
            # Opening sense (dashed triangle, apex on the hinge side).
            hinge = a if j == 0 else b
            free = b if j == 0 else a
            sh.line(free, y0 + .5, hinge, y0 + h / 2, color=FAINT, width=.12, style=Qt.PenStyle.DashLine)
            sh.line(free, y0 + h - .5, hinge, y0 + h / 2, color=FAINT, width=.12, style=Qt.PenStyle.DashLine)
        sh.line(x0 - .5, y0 + h, x0 + w + .5, y0 + h, width=.4)
        if sill > 1:
            sh.line(x0 + w + 1.2, y0 + h, x0 + w + 1.2, floor_y, color=DIM, width=.12)
    elif g["kind"] == "door":
        sh.rect(x0, y0, w, h, width=.3, fill=WALL_FILL)
        sh.rect(x0 + .5, y0 + .5, w - 1, h - .5, width=.15, fill=DOOR_FILL)
        sh.line(x0 + w - .5, y0 + .5, x0 + .5, y0 + h / 2, color=FAINT, width=.12, style=Qt.PenStyle.DashLine)
        sh.line(x0 + w - .5, y0 + h, x0 + .5, y0 + h / 2, color=FAINT, width=.12, style=Qt.PenStyle.DashLine)
        sh.line(x0 + w * .78, y0 + h * .52, x0 + w * .66, y0 + h * .52, width=.3)
    else:
        if g["shape"] == "arch" and g["arch_rise"] > 0:
            to = lambda s, z: (cx + s * k, floor_y - z * k)
            sh.poly(_arch_path(sh, -g["width"] / 2, g["width"] / 2, g["sill"], g["sill"] + g["height"], g["arch_rise"], to),
                    width=.3, fill=VOID_FILL)
        else:
            sh.rect(x0, y0, w, h, width=.3, fill=VOID_FILL)


def _cm(v):
    return f"{v * 100:.0f}"


SCHED_COLS = [("Σήμανση", 18, "center"), ("Όψη", 30, "center"), ("Είδος", 34, "left"), ("Π × Υ (cm)", 24, "center"),
              ("Ποδιά (cm)", 18, "center"), ("Τεμ.", 12, "center"), ("Όροφος", 36, "left"), ("Χώροι", 101, "left")]
ROW_H, PER_PAGE = 21.0, 7


def draw_opening_schedule(sh, doc, new_page, project, date, page_no):
    """Πίνακας κουφωμάτων pages through ``new_page()``; returns the number of pages drawn (0 if none)."""
    rows = opening_schedule(doc)
    if not rows:
        return 0
    k = min(14.0 / max(g["height"] + g["sill"] for g in rows), 22.0 / max(g["width"] for g in rows), 1000.0 / 150)
    chunks = [rows[i:i + PER_PAGE] for i in range(0, len(rows), PER_PAGE)]
    total_w = sum(c[1] for c in SCHED_COLS)
    for n, chunk in enumerate(chunks):
        new_page()
        sh.text(12, 10, "Πίνακας κουφωμάτων" + (" (συνέχεια)" if n else ""), size=13, bold=True, w=200)
        sh.text(12, 16.5, "Θ: θύρες · ΠΡ: παράθυρα · ΑΝ: ανοίγματα — διαστάσεις ανοίγματος τοίχου (πλάτος × ύψος), "
                "όψεις από την εξωτερική πλευρά", size=7.5, color=QColor(110, 110, 110), w=270)
        x, y = 12.0, 22.0
        sh.rect(x, y, total_w, 6.2, width=.2, fill=QColor(236, 231, 222))
        cx = x
        for title, w, align in SCHED_COLS:
            sh.text(cx + (2 if align == "left" else w / 2), y + 3.1, title, size=8, bold=True, align=align, w=w - 3)
            cx += w
        y += 6.2
        for g in chunk:
            rooms = g["rooms"]
            room_txt = ", ".join(rooms[:4]) + (f" κ.ά. ({len(rooms) - 4})" if len(rooms) > 4 else "")
            cells = [g["mark"], None, g["type"], f"{_cm(g['width'])} × {_cm(g['height'])}",
                     _cm(g["sill"]) if g["kind"] != "door" else "—", str(g["count"]), ", ".join(g["storeys"]), room_txt or "—"]
            cx = x
            for (title, w, align), v in zip(SCHED_COLS, cells):
                if v is None:
                    _sketch(sh, g, cx + w / 2, y + ROW_H / 2, k)
                else:
                    sh.text(cx + (2 if align == "left" else w / 2), y + ROW_H / 2, v, size=10 if title == "Σήμανση" else 8,
                            bold=title == "Σήμανση", align=align, w=w - 3,
                            color=MARK_INK if title == "Σήμανση" else INK)
                cx += w
            sh.line(x, y + ROW_H, x + total_w, y + ROW_H, color=QColor(210, 205, 196), width=.12)
            y += ROW_H
        cx = x
        for _t, w, _a in SCHED_COLS[:-1]:
            cx += w
            sh.line(cx, 22.0, cx, y, color=QColor(225, 220, 212), width=.1)
        if n == len(chunks) - 1:
            count = {kd: sum(g["count"] for g in rows if g["kind"] == kd) for kd in PREFIX}
            parts = [f"θύρες {count['door']}", f"παράθυρα {count['window']}"] + ([f"ανοίγματα {count['opening']}"] if count["opening"] else [])
            sh.text(12, y + 5, "Σύνολο: " + " · ".join(parts), size=9, bold=True, w=200)
            sh.text(12, y + 10.5, "Οι διαστάσεις είναι του ανοίγματος στον τοίχο· οι τελικές του κουφώματος "
                    "επιβεβαιώνονται με τον κατασκευαστή μετά την αποτύπωση.", size=7.5, color=QColor(110, 110, 110), w=180)
        _title_block(sh, "Πίνακας κουφωμάτων", None, page_no(), project, date)
    return len(chunks)


# ---------------------------------------------------------------- standalone export
def export_elevations_pdf(doc, path, project=None, include=("elevations", "openings")):
    """Only the elevations (and the door/window schedule); returns ``{"pages", "path", "scales"}``."""
    from archforge.quantities.quote import quote
    if not _walls(doc):
        raise ValueError("Δεν υπάρχουν τοίχοι — σχεδιάστε πρώτα τους ορόφους")
    project = project or quote(doc)["project"] or "Έργο"
    date = datetime.date.today().strftime("%d/%m/%Y")
    writer = QPdfWriter(str(path))
    writer.setResolution(300)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape, QMarginsF(0, 0, 0, 0)))
    writer.setTitle(f"{project} — Όψεις"); writer.setCreator("ArchForge")
    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    sh = Sheet(painter, 300 / 25.4)
    pages = 0

    def new_page():
        nonlocal pages
        if pages:
            writer.newPage()
        pages += 1
    scales = []
    if "elevations" in include:
        scales = draw_elevations(sh, doc, new_page, project, date, lambda: pages)
    if "openings" in include:
        draw_opening_schedule(sh, doc, new_page, project, date, lambda: pages)
    if not pages:
        new_page()
    painter.end()
    return {"pages": pages, "path": str(path), "scales": scales}
