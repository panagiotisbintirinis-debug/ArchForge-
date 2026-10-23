"""Dimensions on the plan (owner 23/10: «μεζούρα / αυτόματη τοποθέτηση διαστάσεων όταν το επιλέξουμε, εξωτερικά και
εσωτερικά — αυτό που λείπει γενικά από το πρόγραμμα»).

Two entities hold what the human asked for; the numbers are always read from the walls, so they never go stale:

* ``auto_dimensions`` — one per storey (``level_z``), with ``exterior`` / ``interior`` on or off:
  - exterior: on every façade, outside its outer face, a chain through the jambs of its doors / windows
    (when it has any), then the whole façade, then — where a façade does not span the building — the overall
    width / depth of the storey;
  - interior: the clear sizes of every room, face to face, inside it (the opposite side of a rectangle is not
    repeated).
* ``dimension`` — one measured with the tape (Μεζούρα): two points and how far the line sits off them.

``storey_dimensions`` gives plain dicts ``{"a", "b", "n", "offset", "value", "kind", "entity_id"}`` — ``a``/``b``
the measured points, ``n`` the unit direction the dimension line is pushed out to, ``offset`` how far.
``drawing`` turns one into lines and the text anchor; the plan view and the PDF draw both from these.
"""
from __future__ import annotations

import math

LEVEL_TOL = 1e-4
MIN_LENGTH = 0.05           # m: shorter pieces are not dimensioned
TIER = (0.60, 1.10, 1.60)   # m outside the outer face: openings chain, façade, overall
INSIDE = 0.35               # m inside a room's face for its clear size
COLLINEAR = 0.01            # m: outer faces this close on the same line are one façade


def _level(e):
    return float(e.params.get("level_z", e.params.get("z", 0.0)))


def settings(doc, z):
    """The storey's ``auto_dimensions`` entity, or None."""
    for e in doc.entities.values():
        if e.kind == "auto_dimensions" and abs(_level(e) - float(z)) <= LEVEL_TOL:
            return e
    return None


def _walls(doc, z):
    return [e for e in doc.entities.values()
            if e.kind == "wall" and e.visible and abs(float(e.params.get("z", 0.0)) - float(z)) <= LEVEL_TOL]


def _on_segment_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    ll = dx * dx + dy * dy
    if ll <= 1e-12:
        return math.hypot(px - ax, py - ay)
    u = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / ll))
    return math.hypot(px - ax - u * dx, py - ay - u * dy)


def _facades(doc, z):
    """Outer faces of the exterior walls joined into façades: ``[{"n", "u", "line", "lo", "hi", "stops"}]``.

    ``u`` runs along the façade, ``line`` is the face's distance along ``n`` from the origin, ``lo``/``hi`` its
    extent along ``u`` (corners included: an end that meets another wall runs on by half its thickness) and
    ``stops`` the jambs of its openings."""
    from archforge.architecture.openings import plan_segment
    from archforge.mep.ventilation import exterior_walls
    walls = _walls(doc, z)
    axes = [(o.id, *(float(o.params[k]) for k in ("x1", "y1", "x2", "y2"))) for o in walls]
    children = {}
    for e in doc.entities.values():
        if e.kind in ("door", "window", "opening") and e.parent_id:
            children.setdefault(e.parent_id, []).append(e)
    faces = []
    for w, (nx, ny) in exterior_walls(doc, z):
        p = w.params
        ax, ay, bx, by = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
        L = math.hypot(bx - ax, by - ay)
        if L < MIN_LENGTH:
            continue
        t = float(p.get("thickness", 0.2))
        ux, uy = -ny, nx                    # along the face, the same way for every face looking out along n
        meets = lambda x, y: any(_on_segment_dist(x, y, *rest) < 0.01 for oid, *rest in axes if oid != w.id)
        e0 = t / 2 if meets(ax, ay) else 0.0
        e1 = t / 2 if meets(bx, by) else 0.0
        fx, fy = ax + nx * t / 2, ay + ny * t / 2           # a point of the outer face
        line = fx * nx + fy * ny
        sa = ax * ux + ay * uy
        sb = bx * ux + by * uy
        lo, hi = (sa - e0, sb + e1) if sa <= sb else (sb - e1, sa + e0)
        stops = []
        for o in children.get(w.id, ()):
            try:
                (qx, qy), (rx, ry) = plan_segment(p, o.params)
            except (KeyError, TypeError, ValueError):
                continue
            stops += [qx * ux + qy * uy, rx * ux + ry * uy]
        faces.append({"n": (nx, ny), "u": (ux, uy), "line": line, "lo": lo, "hi": hi, "stops": stops})
    # Collinear outer faces that touch are one façade (a wall split at a T, two walls in a row).
    faces.sort(key=lambda f: (round(f["n"][0], 3), round(f["n"][1], 3), round(f["line"], 2), f["lo"]))
    out = []
    for f in faces:
        g = out[-1] if out else None
        if (g is not None and abs(g["n"][0] * f["n"][0] + g["n"][1] * f["n"][1] - 1.0) < 1e-6
                and abs(g["line"] - f["line"]) <= COLLINEAR and f["lo"] <= g["hi"] + COLLINEAR):
            g["hi"] = max(g["hi"], f["hi"]); g["stops"] += f["stops"]
        else:
            out.append(dict(f, stops=list(f["stops"])))
    return out


def _point(f, s, extra=0.0):
    (nx, ny), (ux, uy) = f["n"], f["u"]
    d = f["line"] + extra
    return (ux * s + nx * d, uy * s + ny * d)


def exterior(doc, z, entity_id=""):
    """Chains outside the building on storey ``z`` (see the module text)."""
    out = []
    facades = _facades(doc, z)
    if not facades:
        return out

    def dim(a, b, n, offset, value):
        out.append({"a": a, "b": b, "n": n, "offset": offset, "value": value, "kind": "exterior",
                    "entity_id": entity_id})
    for f in facades:
        n = f["n"]
        stops = sorted(s for s in f["stops"] if f["lo"] + MIN_LENGTH <= s <= f["hi"] - MIN_LENGTH)
        tier = 0
        if stops:
            chain = [f["lo"]] + stops + [f["hi"]]
            for s0, s1 in zip(chain, chain[1:]):
                if s1 - s0 >= MIN_LENGTH:
                    dim(_point(f, s0), _point(f, s1), n, TIER[0], s1 - s0)
            tier = 1
        dim(_point(f, f["lo"]), _point(f, f["hi"]), n, TIER[tier], f["hi"] - f["lo"])
    # Overall: on each side of the storey, unless the outermost façade there already spans it all.
    pts = [_point(f, s) for f in facades for s in (f["lo"], f["hi"])]
    xs, ys = [q[0] for q in pts], [q[1] for q in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    for n, a, b, span in (((0.0, -1.0), (x0, y0), (x1, y0), x1 - x0),
                          ((0.0, 1.0), (x0, y1), (x1, y1), x1 - x0),
                          ((-1.0, 0.0), (x0, y0), (x0, y1), y1 - y0),
                          ((1.0, 0.0), (x1, y0), (x1, y1), y1 - y0)):
        side = [f for f in facades if f["n"][0] * n[0] + f["n"][1] * n[1] > 1 - 1e-6]
        if not side or span < MIN_LENGTH:
            continue
        outer = max(f["line"] for f in side)
        if any(abs(f["line"] - outer) <= COLLINEAR and f["hi"] - f["lo"] >= span - COLLINEAR for f in side):
            continue
        # Measured on the bounding line, pushed out past the outermost façade's chains.
        dim(a, b, n, TIER[2], span)
    return out


def _area(pts):
    return sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts))) / 2


def interior(doc, z, entity_id=""):
    """Every room's clear sizes, face to face, drawn just inside it."""
    from archforge.quantities.takeoff import net_polygon
    out = []
    try:
        faces = doc.active_room_faces(z=float(z))
    except (ValueError, KeyError):
        return out
    for face in faces:
        try:
            pts = [(float(x), float(y)) for x, y in net_polygon(doc, face.polygon, float(z))]
        except (ValueError, KeyError, ZeroDivisionError):
            continue
        if len(pts) < 3 or abs(_area(pts)) < 0.2:
            continue
        if _area(pts) < 0:
            pts = pts[::-1]                                  # counter-clockwise: inside on the left
        edges = []
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L >= 0.30:
                edges.append((L, a, b))
        chosen = []
        for L, a, b in sorted(edges, key=lambda q: -q[0]):
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            twin = False
            for L2, c, d in chosen:
                vx, vy = (d[0] - c[0]) / L2, (d[1] - c[1]) / L2
                if abs(ux * vx + uy * vy) < 0.999 or abs(L - L2) > 0.01:
                    continue
                s = sorted((c[0] * ux + c[1] * uy, d[0] * ux + d[1] * uy))
                t = sorted((a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy))
                if min(s[1], t[1]) - max(s[0], t[0]) >= 0.5 * L:
                    twin = True                              # the opposite side of a rectangle: said once
                    break
            if twin:
                continue
            chosen.append((L, a, b))
            n = (-uy, ux)                                    # inwards
            depth = min(INSIDE, 0.25 * min(L, max(0.3, math.sqrt(abs(_area(pts))))))
            out.append({"a": a, "b": b, "n": n, "offset": depth, "value": L, "kind": "interior",
                        "entity_id": entity_id})
    return out


def manual(e):
    """A tape-measured ``dimension`` entity as a dimension dict."""
    p = e.params
    a, b = (float(p["x1"]), float(p["y1"])), (float(p["x2"]), float(p["y2"]))
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-9:
        return None
    off = float(p.get("offset", 0.0))
    n = (-(b[1] - a[1]) / L, (b[0] - a[0]) / L)
    if off < 0:
        n, off = (-n[0], -n[1]), -off
    return {"a": a, "b": b, "n": n, "offset": off, "value": L, "kind": "manual", "entity_id": e.id}


def storey_dimensions(doc, z):
    """Everything the human asked to be dimensioned on storey ``z``."""
    out = []
    s = settings(doc, z)
    if s is not None and s.visible:
        if int(s.params.get("exterior", 0)):
            out += exterior(doc, z, s.id)
        if int(s.params.get("interior", 0)):
            out += interior(doc, z, s.id)
    for e in doc.entities.values():
        if e.kind == "dimension" and e.visible and abs(_level(e) - float(z)) <= LEVEL_TOL:
            d = manual(e)
            if d is not None:
                out.append(d)
    return out


def drawing(d, tick=0.08, overshoot=0.08, gap=0.05):
    """Lines of one dimension: ``{"line", "extensions", "ticks", "text_at", "angle"}`` (world units, degrees)."""
    (ax, ay), (bx, by), (nx, ny), off = d["a"], d["b"], d["n"], float(d["offset"])
    a2, b2 = (ax + nx * off, ay + ny * off), (bx + nx * off, by + ny * off)
    ext = []
    if off > gap:
        for (px, py), (qx, qy) in (((ax, ay), a2), ((bx, by), b2)):
            ext.append(((px + nx * gap, py + ny * gap), (qx + nx * overshoot, qy + ny * overshoot)))
    L = math.hypot(b2[0] - a2[0], b2[1] - a2[1]) or 1.0
    ux, uy = (b2[0] - a2[0]) / L, (b2[1] - a2[1]) / L
    # Architectural ticks: 45° across the line.
    tx, ty = (ux + nx) * tick / math.sqrt(2), (uy + ny) * tick / math.sqrt(2)
    ticks = [((q[0] - tx, q[1] - ty), (q[0] + tx, q[1] + ty)) for q in (a2, b2)]
    angle = math.degrees(math.atan2(uy, ux))
    if angle > 90.001:
        angle -= 180
    elif angle <= -90.001:
        angle += 180
    mid = ((a2[0] + b2[0]) / 2, (a2[1] + b2[1]) / 2)
    return {"line": (a2, b2), "extensions": ext, "ticks": ticks, "text_at": mid, "angle": angle}


def fmt(v):
    """«3,45» — metres with two decimals and a Greek comma (as the selected wall's distances)."""
    return f"{v:.2f}".replace(".", ",")


# ------------------------------------------------------------------ the tape (Μεζούρα)
def tape_snap(doc, x, y, tolerance, grid=None):
    """Where a tape click at (x, y) lands: a corner of the wall faces, else on a face, else the usual snap.

    ``(x, y, kind)``; kind is ``"corner"`` / ``"face"`` / the snap kind / ``""`` (nowhere special)."""
    from archforge.core.snapping import best_snap, wall_face_segments
    faces = [(a, b) for a, b, _eid, _k in wall_face_segments(doc)
             if _on_segment_dist(x, y, a[0], a[1], b[0], b[1]) <= 3 * tolerance]
    best = None
    for i, (a, b) in enumerate(faces):
        for q in (a, b):
            d = math.hypot(q[0] - x, q[1] - y)
            if d <= tolerance and (best is None or d < best[0]):
                best = (d, q)
        for c, e in faces[i + 1:]:
            q = _cross(a, b, c, e)
            if q is not None:
                d = math.hypot(q[0] - x, q[1] - y)
                if d <= tolerance and (best is None or d < best[0]):
                    best = (d, q)
    if best is not None:
        return best[1][0], best[1][1], "corner"
    near = None
    for a, b in faces:
        dx, dy = b[0] - a[0], b[1] - a[1]
        ll = dx * dx + dy * dy
        if ll <= 1e-12:
            continue
        u = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / ll))
        q = (a[0] + u * dx, a[1] + u * dy)
        d = math.hypot(q[0] - x, q[1] - y)
        if d <= tolerance and (near is None or d < near[0]):
            near = (d, q)
    if near is not None:
        return near[1][0], near[1][1], "face"
    sp = best_snap(doc, x, y, tolerance, grid)
    if sp is not None:
        return float(sp.x), float(sp.y), str(sp.kind)
    return float(x), float(y), ""


def _cross(a, b, c, d):
    """Crossing of the lines a–b and c–d (not parallel), or None."""
    den = (a[0] - b[0]) * (c[1] - d[1]) - (a[1] - b[1]) * (c[0] - d[0])
    if abs(den) < 1e-9:
        return None
    t = ((a[0] - c[0]) * (c[1] - d[1]) - (a[1] - c[1]) * (c[0] - d[0])) / den
    return (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))


def tape_offset(a, b, x, y):
    """Signed offset (along the left normal of a→b) that puts the dimension line through (x, y)."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-9:
        return 0.0
    return ((x - a[0]) * -(b[1] - a[1]) + (y - a[1]) * (b[0] - a[0])) / L


def tape_entity(a, b, z, offset=0.0):
    """A ``dimension`` entity measured from ``a`` to ``b`` on storey ``z``."""
    from archforge.core.model import Entity
    if math.hypot(b[0] - a[0], b[1] - a[1]) < 0.01:
        raise ValueError("τα δύο σημεία της μεζούρας συμπίπτουν")
    return Entity("dimension", {"x1": float(a[0]), "y1": float(a[1]), "x2": float(b[0]), "y2": float(b[1]),
                                "level_z": float(z), "offset": float(offset)}, name="Διάσταση")


def set_auto(doc, z, exterior=None, interior=None):
    """The command that turns the storey's automatic dimensions on / off (one undo)."""
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    s = settings(doc, z)
    if s is None:
        params = {"level_z": float(z), "exterior": int(bool(exterior)), "interior": int(bool(interior))}
        return AddEntity(Entity("auto_dimensions", params, name="Διαστάσεις (αυτόματα)"))
    changes = {}
    if exterior is not None:
        changes["exterior"] = int(bool(exterior))
    if interior is not None:
        changes["interior"] = int(bool(interior))
    return UpdateEntity(s.id, changes)
