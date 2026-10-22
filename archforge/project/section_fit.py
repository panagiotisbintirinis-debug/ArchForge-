"""The engineer's section put where it belongs, by itself (HANDOFF 22/10: «τομή αυτόματα στη θέση της (σημάδι
T.01/A2.2) και επαλήθευση στάθμεων/εδάφους με την τομή»).

* **Where it cuts**: the plan writes the section mark at both ends of the cut line («T.01» twice, 22,8 m apart on the
  NEW VILLA plan); placed in the site frame those two marks are the section line.
* **Which way it looks, where it starts, how high**: the section sheet writes no level and no mark (the owner's
  «NEW VILLA SECTION» has only dimensions), so it is fitted on what the model has on that line:
  - a pool the line crosses: the water drawn in the section (a light blue fill, 3,02 m wide, its surface the pool's
    water level) against the pool in the model (2,98 m across on the line) — along and up at once;
  - otherwise the walls: their faces against the long vertical lines of the drawing (along), their bottoms
    against those lines' bottoms (up).
  Looking one way or the other is decided by the walls: the side on which more wall faces of the model meet a
  vertical line of the drawing.
* **Checked against the drawing**: for every wall of the model the line crosses, the height the drawing gives it
  (its vertical line's top over the floor) — «τοίχος 3,00 m στο μοντέλο, 3,70 m στην τομή».

Plain data, no Qt: the import (ui/drawing_set_import.py) makes the section line and the underlay from it.
"""
from __future__ import annotations

import math
from collections import Counter

FACE_TOL = 0.12          # m — a wall face and a drawn vertical line are the same (pen width, plaster)
MIN_VERTICAL = 1.0       # m — a wall in the section is at least this tall (hatching, stones, plants are not)
REACH = 1.0              # m — the cut line is taken this far beyond its two marks


def cut_lines(sheets, placed, building=None, min_length=3.0):
    """``[(mark, (x1, y1), (x2, y2), sheet index)]`` — a section mark written twice on a placed plan (its two ends),
    in the site frame.  Marks that draw the same line (T.01 and the sheet number A2.2 beside it) count once."""
    out = []
    for i, (sim, _how) in sorted(placed.items()):
        s = sheets[i]
        if s.kind != "plan" or (building and s.building != building):
            continue
        by = {}
        for k, x, y in s.anchors:
            if k.startswith("M"):
                by.setdefault(k, []).append((x, y))
        # The cut's own mark (T.01) before the sheet number drawn beside it (A2.2).
        for k in sorted(by, key=lambda k: (not k[1:2] in "TΤ", k)):
            pts = by[k]
            if len(pts) != 2 or math.dist(*pts) < min_length:
                continue
            a, b = sim.apply(pts[0]), sim.apply(pts[1])
            if any(_same_line((a, b), (c, d)) for _k, c, d, _i in out):
                continue
            out.append((k[1:], a, b, i))
    return out


def _same_line(p, q, tol=0.6):
    (a, b), (c, d) = p, q
    return (math.dist(a, c) <= tol and math.dist(b, d) <= tol) or (math.dist(a, d) <= tol and math.dist(b, c) <= tol)


def frame(line, flip):
    """(origin, along) of a section line as output/section_cut.frame sees it (A on the left as you look)."""
    from archforge.output.section_cut import frame as F
    (x1, y1), (x2, y2) = line
    (ox, oy), (ux, uy), _n, _l = F({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "flip": flip})
    return (ox, oy), (ux, uy)


def _clip(origin, along, length, polygon):
    """(t0, t1) of the line ``origin + t·along`` (0 − REACH ≤ t ≤ length + REACH) inside a convex polygon, or None."""
    t0, t1 = -REACH, length + REACH
    n = len(polygon)
    area = sum(polygon[i][0] * polygon[(i + 1) % n][1] - polygon[(i + 1) % n][0] * polygon[i][1] for i in range(n))
    sign = 1.0 if area > 0 else -1.0
    for i in range(n):
        (ax, ay), (bx, by) = polygon[i], polygon[(i + 1) % n]
        nx, ny = sign * (by - ay), -sign * (bx - ax)            # outward normal
        num = nx * (ax - origin[0]) + ny * (ay - origin[1])
        den = nx * along[0] + ny * along[1]
        if abs(den) < 1e-12:
            if num < 0:
                return None
            continue
        t = num / den
        if den > 0:
            t1 = min(t1, t)
        else:
            t0 = max(t0, t)
        if t0 > t1:
            return None
    return (t0, t1)


def model_on_line(doc, line, flip):
    """What the model has on the line: ``{"walls": [(u0, u1, z0, z1)], "pools": [(u0, u1, water z, id)]}``."""
    from archforge.site.pool import WATER_DROP, param, rim
    origin, along = frame(line, flip)
    length = math.dist(*line)
    walls, pools = [], []
    for e in doc.entities.values():
        p = e.params
        if e.kind == "wall":
            x1, y1, x2, y2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
            L = math.hypot(x2 - x1, y2 - y1)
            if L < 1e-6:
                continue
            h = float(p.get("thickness", 0.2)) / 2
            nx, ny = -(y2 - y1) / L * h, (x2 - x1) / L * h
            t = _clip(origin, along, length, [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny), (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)])
            if t and t[1] - t[0] < 2.0:                 # crossed, not run along
                z = float(p.get("z", 0.0))
                walls.append((t[0], t[1], z, z + float(p.get("height", 3.0))))
        elif e.kind == "pool":
            t = _clip(origin, along, length, [tuple(q) for q in rim(p)])
            if t:
                pools.append((t[0], t[1], float(p.get("z", 0.0)) - WATER_DROP.get(param(p, "pool_type"), 0.0), e.id))
    return {"walls": sorted(walls), "pools": pools}


def drawing_features(sheet):
    """Of the section sheet (metres at its scale): long vertical lines ``[(x, y0, y1)]`` and water bodies
    ``[(x0, x1, top)]`` (water fills grouped where they touch; glazing strips under 0,5 m left out)."""
    verticals = []
    for x1, y1, x2, y2 in sheet.segments:
        if abs(x2 - x1) <= 0.02 and abs(y2 - y1) >= MIN_VERTICAL:
            verticals.append(((x1 + x2) / 2, min(y1, y2), max(y1, y2)))
    boxes = []
    for poly in sheet.water:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        boxes.append([min(xs), min(ys), max(xs), max(ys)])
    merged = True
    while merged:
        merged = False
        for a in range(len(boxes)):
            for b in range(a + 1, len(boxes)):
                A, B = boxes[a], boxes[b]
                if A[0] - 0.02 <= B[2] and B[0] - 0.02 <= A[2] and A[1] - 0.02 <= B[3] and B[1] - 0.02 <= A[3]:
                    boxes[a] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3])]
                    del boxes[b]
                    merged = True
                    break
            if merged:
                break
    water = [(b[0], b[2], b[3]) for b in boxes if b[2] - b[0] >= 0.5 and b[3] - b[1] >= 0.5]
    return {"verticals": verticals, "water": water}


def _faces(walls):
    return [(u, z0, z1) for u0, u1, z0, z1 in walls for u in (u0, u1)]


def _matches(walls, verticals, du, dz):
    """Wall faces of the model that meet a drawn vertical line (shifted by du, dz) — ``[(face, line)]``."""
    out = []
    for f in _faces(walls):
        near = [v for v in verticals if abs(v[0] + du - f[0]) <= FACE_TOL and v[1] + dz < f[2] and v[2] + dz > f[1]]
        if near:
            out.append((f, min(near, key=lambda v: abs(v[0] + du - f[0]))))
    return out


def _by_walls(walls, verticals):
    """(du, dz) from the walls alone: faces against vertical lines (along), then their bottoms (up)."""
    votes = Counter()
    for u, _z0, _z1 in _faces(walls):
        for x, _y0, _y1 in verticals:
            votes[round((u - x) / 0.05)] += 1
    if not votes:
        return None
    k, _n = votes.most_common(1)[0]
    du = sum(k2 * 0.05 * votes[k2] for k2 in (k - 1, k, k + 1)) / max(1, sum(votes[k2] for k2 in (k - 1, k, k + 1)))
    bottoms = Counter()
    for f in _faces(walls):
        for x, y0, _y1 in verticals:
            if abs(x + du - f[0]) <= FACE_TOL:
                bottoms[round((f[1] - y0) / 0.05)] += 1
    if not bottoms:
        return None
    return du, bottoms.most_common(1)[0][0] * 0.05


def fit(sheet, doc, line):
    """Place the section ``sheet`` on ``line`` (two plan points): ``{"flip", "x", "y", "how", "matched", "faces",
    "heights": [(u, model height, drawn height)]}`` (x, y: the underlay's place — drawing metres + (x, y) =
    the section's (u, z)) or None when nothing on the line can be told in the drawing."""
    drawn = drawing_features(sheet)
    best = None
    for flip in (0, 1):
        m = model_on_line(doc, line, flip)
        tries = []
        for u0, u1, wz, _id in m["pools"]:
            for x0, x1, top in drawn["water"]:
                if abs((u1 - u0) - (x1 - x0)) <= 0.15 * max(u1 - u0, x1 - x0):
                    tries.append(((u0 + u1) / 2 - (x0 + x1) / 2, wz - top, "νερό πισίνας"))
        if not tries and m["walls"]:
            w = _by_walls(m["walls"], drawn["verticals"])
            if w:
                tries.append((*w, "τοίχοι"))
        for du, dz, how in tries:
            matched = _matches(m["walls"], drawn["verticals"], du, dz)
            score = (len(matched), how == "νερό πισίνας")
            if best is None or score > best[0]:
                best = (score, flip, du, dz, how, matched, len(_faces(m["walls"])), m["walls"])
    if best is None:
        return None
    _score, flip, du, dz, how, matched, faces, walls = best
    heights = []
    for u0, u1, z0, z1 in walls:
        # A line drawn from this wall's floor up (not the pool wall below it, not a line that merely passes).
        tops = [line_[2] + dz for f, line_ in matched if f[0] in (u0, u1) and abs(line_[1] + dz - z0) <= 0.35]
        if tops:
            heights.append(((u0 + u1) / 2, round(z1 - z0, 2), round(max(tops) - z0, 2)))
    return {"flip": flip, "x": du, "y": dz, "how": how, "matched": len(matched), "faces": faces, "heights": heights}


def report(found, name="Τομή"):
    """One paragraph for the person: how it was placed and where the drawing disagrees with the model."""
    if not found:
        return f"{name}: δεν βρέθηκε θέση (ούτε πισίνα ούτε τοίχοι του μοντέλου στη γραμμή) — «Τοποθέτηση 2 κλικ»"
    text = (f"{name}: στη θέση της από {found['how']} · {found['matched']}/{found['faces']} παρειές τοίχων πάνω σε "
            f"γραμμές του σχεδίου")
    off = [(u, a, b) for u, a, b in found["heights"] if abs(a - b) > 0.10]
    if off:
        text += " · ύψη που διαφέρουν: " + ", ".join(
            f"στα {u:.1f} m τοίχος {a:.2f} m στο μοντέλο, {b:.2f} m στην τομή".replace(".", ",") for u, a, b in off[:4])
    return text
