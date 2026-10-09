"""Vertical section (τομή) of the building on a line drawn in the plan.

Owner: «Η τομή δεν δουλεύει.»  A contractor draws the cut line across the building and expects
the drawing a section is: what the plane cuts (walls, slabs, stair, roof) filled/hatched with a
heavy outline, what lies behind it seen in elevation (openings, the stair, the roof), and the
storey levels (±0,00, +3,00 …).

``section_line`` entities hold only the line (x1, y1, x2, y2) and which side is looked at
(``flip``); everything here is derived from the same evaluated meshes as the 3D view, never
stored.  Coordinates of the drawing: ``u`` along the line from its start (A, on the left as you
look), ``z`` up.  Plain data, no Qt, so tests read it directly.
"""
from __future__ import annotations

import math

LETTERS = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
ARROW = 0.60            # plan symbol: length of the view arrows at both ends (m)
EPS = 1e-7

# How a cut part is drawn (Greek drafting practice): reinforced concrete dark, masonry hatched,
# roof timber/tiles hatched brown, joinery outlined only.
CONCRETE = {"room_floor", "room_roof", "room_ceiling", "room_foundation", "floor", "structural_column",
            "structural_beam", "stair", "ramp"}
MASONRY = {"wall", "pod"}
ROOF = {"pitched_roof", "ceiling_joists", "drywall_ceiling"}
JOINERY = {"door", "window", "opening", "railing", "kitchen_part", "cabinet", "library_object", "plant"}


def cut_style(kind):
    if kind in CONCRETE:
        return "concrete"
    if kind in MASONRY:
        return "masonry"
    if kind in ROOF:
        return "roof"
    if kind in JOINERY:
        return "joinery"
    return "other"


def next_section_name(doc):
    """«Τομή Α-Α», then Β-Β … — the first letter not used by another section line."""
    used = {str(e.name) for e in doc.entities.values() if e.kind == "section_line"}
    for letter in LETTERS:
        name = f"Τομή {letter}-{letter}"
        if name not in used:
            return name
    return f"Τομή {len(used) + 1}"


def section_letter(name):
    """«Τομή Β-Β» → «Β» (the mark written at the ends of the line in the plan)."""
    tail = str(name or "").replace("Τομή", "").strip()
    return tail.split("-")[0].strip() or "Α"


def frame(params):
    """(A, along, normal, length): the line start, its unit direction and the unit view direction."""
    x1, y1, x2, y2 = (float(params[k]) for k in ("x1", "y1", "x2", "y2"))
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1e-6:
        raise ValueError("η γραμμή τομής θέλει μήκος")
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    nx, ny = -uy, ux                        # looking to the left of A→B: A on the left, B on the right
    if int(params.get("flip", 0)):
        nx, ny = -nx, -ny
        (x1, y1), ux, uy = (x2, y2), -ux, -uy      # turned round: B is now on the left
    return (x1, y1), (ux, uy), (nx, ny), length


def plan_symbol(params, letter="Α"):
    """Plan marks of the section: the cut line, an arrow at each end pointing where you look, the letters.

    ``{"line": (a, b), "arrows": [(tail, head, (w1, w2))], "labels": [(text, (x, y))]}``
    """
    a = (float(params["x1"]), float(params["y1"]))
    b = (float(params["x2"]), float(params["y2"]))
    _o, (ux, uy), (nx, ny), _l = frame(params)
    arrows, labels = [], []
    for (px, py) in (a, b):
        head = (px + nx * ARROW, py + ny * ARROW)
        back = (head[0] - nx * 0.22, head[1] - ny * 0.22)
        wing = ((back[0] + ux * 0.11, back[1] + uy * 0.11), (back[0] - ux * 0.11, back[1] - uy * 0.11))
        arrows.append(((px, py), head, wing))
        labels.append((letter, (px + nx * (ARROW + 0.25), py + ny * (ARROW + 0.25))))
    return {"line": (a, b), "arrows": arrows, "labels": labels}


def _clip_polygon(points, depths):
    """Part of a 3D polygon on the looked-at side (depth ≥ 0), with its depths."""
    out, out_d = [], []
    n = len(points)
    for i in range(n):
        p, q = points[i], points[(i + 1) % n]
        dp, dq = depths[i], depths[(i + 1) % n]
        if dp >= 0:
            out.append(p); out_d.append(dp)
        if (dp >= 0) != (dq >= 0):
            t = dp / (dp - dq)
            out.append(tuple(p[k] + (q[k] - p[k]) * t for k in range(3))); out_d.append(0.0)
    return out, out_d


def _chain(segments, tol=1e-5):
    """Join cut segments into closed loops (watertight meshes) and leftover open chains."""
    def key(p):
        return (round(p[0] / tol), round(p[1] / tol))
    ends = {}
    for i, (p, q) in enumerate(segments):
        ends.setdefault(key(p), []).append((i, 0))
        ends.setdefault(key(q), []).append((i, 1))
    used = [False] * len(segments)
    loops, chains = [], []
    for start in range(len(segments)):
        if used[start]:
            continue
        used[start] = True
        p, q = segments[start]
        path = [p, q]
        closed = False
        while True:
            nxt = None
            for j, side in ends.get(key(path[-1]), ()):
                if not used[j]:
                    nxt = (j, side)
                    break
            if nxt is None:
                break
            j, side = nxt
            used[j] = True
            point = segments[j][1 - side]
            if key(point) == key(path[0]):
                closed = True
                break
            path.append(point)
        (loops if closed and len(path) >= 3 else chains).append(path)
    return loops, chains


def _shade(color, factor, lighten=0.45):
    """Material colour lightened towards paper white and shaded by how squarely the face is seen."""
    try:
        c = str(color).lstrip("#")
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))
    except (ValueError, TypeError):
        r, g, b = 200, 200, 200
    out = []
    for v in (r, g, b):
        v = v + (255 - v) * lighten
        out.append(max(0, min(255, int(v * factor))))
    return tuple(out)


def _objects(doc, evaluation=None):
    from archforge.rendering.scene import build_pbr_scene_payload
    if evaluation is None:
        from archforge.geometry.incremental import IncrementalEvaluationCache
        from archforge.geometry.sculpt import SculptedPreviewBackend
        evaluation = IncrementalEvaluationCache(SculptedPreviewBackend()).sync(doc)
    objects = build_pbr_scene_payload(evaluation, (), doc=doc).get("objects", ())
    # One body per entity: the 3D splits a wall by finish, the cut needs it whole (closed loops).
    merged = {}
    for o in objects:
        if o.get("kind") in ("terrain", "mep_pipe", "elec_box", "elec_cable", "section_line"):
            continue                      # site, networks and helpers are not part of a building section
        key = o.get("id") or o.get("render_part") or id(o)
        m = merged.setdefault(key, {"id": o.get("id", ""), "kind": o.get("kind", ""), "vertices": [], "triangles": [], "colors": []})
        base = len(m["vertices"])
        m["vertices"].extend(o.get("vertices", ()))
        color = (o.get("material") or {}).get("color", "#bdc5ce")
        for t in o.get("triangles", ()):
            m["triangles"].append((base + int(t[0]), base + int(t[1]), base + int(t[2])))
            m["colors"].append(color)
    return list(merged.values())


def levels(doc):
    """Storey levels as a section marks them: ``[(z, "±0,00"), (3.0, "+3,00") …]`` with the storey names."""
    from archforge.ui.project_outline import _level_label, _levels
    out = []
    for name, z in _levels(doc):
        mark = "±0,00" if abs(z) < 5e-3 else f"{z:+.2f}".replace(".", ",")
        out.append((float(z), mark, _level_label(name)))
    return out


def cut_section(doc, params, evaluation=None, depth=None):
    """The section drawing on ``params`` (a section_line's x1, y1, x2, y2, flip).

    Returns ``{"cuts": [{"id", "kind", "style", "loops", "chains"}],
    "faces": [{"points", "depth", "fill", "edges"}] (far to near), "levels": [...],
    "bounds": (u0, z0, u1, z1), "length": line length}``.
    """
    (ox, oy), (ux, uy), (nx, ny), length = frame(params)
    limit = float(depth) if depth else None
    cuts, faces = [], []
    u0 = z0 = math.inf
    u1 = z1 = -math.inf

    def project(p):
        return ((p[0] - ox) * ux + (p[1] - oy) * uy, p[2])

    for obj in _objects(doc, evaluation):
        verts = [tuple(float(c) for c in v) for v in obj.get("vertices", ())]
        if not verts:
            continue
        d = [(x - ox) * nx + (y - oy) * ny for x, y, _z in verts]
        d = [v if abs(v) > EPS else EPS for v in d]        # nothing lies exactly on the plane
        if max(d) < 0:
            continue                                         # wholly behind the viewer
        if limit is not None and min(d) > limit:
            continue
        kind = str(obj.get("kind", ""))
        tris = obj.get("triangles", ())
        # Feature edges (outline, folds): an edge with one triangle or a fold over 25°.
        def vkey(i):
            x, y, z = verts[i]
            return (round(x, 4), round(y, 4), round(z, 4))
        normals, edge_tris = [], {}
        for t, (a, b, c) in enumerate(tris):
            pa, pb, pc = verts[a], verts[b], verts[c]
            e1 = [pb[k] - pa[k] for k in range(3)]
            e2 = [pc[k] - pa[k] for k in range(3)]
            nrm = (e1[1] * e2[2] - e1[2] * e2[1], e1[2] * e2[0] - e1[0] * e2[2], e1[0] * e2[1] - e1[1] * e2[0])
            ln = math.sqrt(sum(v * v for v in nrm)) or 1.0
            normals.append(tuple(v / ln for v in nrm))
            for i, j in ((a, b), (b, c), (c, a)):
                edge_tris.setdefault(tuple(sorted((vkey(i), vkey(j)))), []).append(t)
        feature = set()
        for edge, ts in edge_tris.items():
            if len(ts) == 1 or (len(ts) >= 2 and sum(normals[ts[0]][k] * normals[ts[1]][k] for k in range(3)) < math.cos(math.radians(25))):
                feature.add(edge)
        segments = []
        for t, (a, b, c) in enumerate(tris):
            da, db, dc = d[a], d[b], d[c]
            if max(da, db, dc) < 0:
                continue
            # The cut: where the plane crosses this triangle.
            if min(da, db, dc) < 0:
                pts = []
                for i, j in ((a, b), (b, c), (c, a)):
                    if (d[i] >= 0) != (d[j] >= 0):
                        s = d[i] / (d[i] - d[j])
                        p = tuple(verts[i][k] + (verts[j][k] - verts[i][k]) * s for k in range(3))
                        pts.append(project(p))
                if len(pts) == 2 and math.dist(pts[0], pts[1]) > 1e-9:
                    segments.append((pts[0], pts[1]))
            # Behind the cut: the visible part of the face, in elevation.
            poly, pd = _clip_polygon([verts[a], verts[b], verts[c]], [da, db, dc])
            if len(poly) < 3:
                continue
            nrm = normals[t]
            facing = abs(nrm[0] * nx + nrm[1] * ny)
            light = 0.78 + 0.22 * facing if abs(nrm[2]) < 0.5 else 0.9
            edges = []
            for i, j in ((a, b), (b, c), (c, a)):
                if tuple(sorted((vkey(i), vkey(j)))) in feature and d[i] >= 0 and d[j] >= 0:
                    edges.append((project(verts[i]), project(verts[j])))
            faces.append({"points": [project(p) for p in poly], "depth": sum(pd) / len(pd),
                          "fill": _shade(obj["colors"][t], light), "edges": edges, "kind": kind})
            for p in poly:
                uu, zz = project(p)
                u0, u1, z0, z1 = min(u0, uu), max(u1, uu), min(z0, zz), max(z1, zz)
        if segments:
            loops, chains = _chain(segments)
            cuts.append({"id": str(obj.get("id", "")), "kind": kind, "style": cut_style(kind),
                         "loops": loops, "chains": chains})
    faces.sort(key=lambda f: -f["depth"])
    if u0 == math.inf:
        u0, z0, u1, z1 = 0.0, 0.0, length, 3.0
    return {"cuts": cuts, "faces": faces, "levels": levels(doc), "bounds": (u0, z0, u1, z1), "length": length}
