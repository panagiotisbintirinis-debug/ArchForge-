"""A set of drawings of one project, related to each other (owner 22/10: «να βρεις τις συσχετίσεις ανά τα PDF …
πάνω από δύο PDF σε σειρά σημαίνει ότι ακολουθούν το ίδιο σχέδιο, οπότε πρέπει να συγχωνευτούν παραμετρικά»).

Each sheet is classified from its title (the largest text) and file name — building («NEW VILLA», «OLD VILLA»),
kind (plan / section / site plan) and floor (ground / lower / upper …) — and carries *anchors*: what is written
the same on several sheets at the same place of the project:

* levels «+114.00m [F.L.]» (the value is the key: the same spot level on the plan and the masterplan);
* section marks «T.01», «A2.2» (the cut line drawn on the plan and on the masterplan).

Sheets are related by the anchors they share: two or more give scale, turn and place at once (a similarity,
fitted on the agreeing pairs — RANSAC then least squares), so a masterplan without a written scale is scaled by
the plans.  Sheets of the same building at the same scale with too few shared anchors (lower / upper floor)
are related by their walls: the shift most wall corners agree on.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

PT_M = 25.4 / 72.0 / 1000.0                  # one PDF point on paper, in metres

KINDS = (("site", r"MASTER\s*PLAN|SITE\s*PLAN|ΓΕΝΙΚΗ|ΤΟΠΟΓΡΑΦ|ΔΙΑΓΡΑΜΜΑ\s+ΚΑΛΥΨΗΣ"),
         ("section", r"SECTION|ΤΟΜΗ"), ("elevation", r"ELEVATION|ΟΨΗ"), ("plan", r"PLAN|ΚΑΤΟΨΗ"))
FLOORS = (("basement", r"BASEMENT|ΥΠΟΓΕΙ"), ("lower", r"LOWER|ΚΑΤΩ"), ("ground", r"GROUND|ΙΣΟΓΕΙ"),
          ("upper", r"UPPER|ΑΝΩ|FIRST|1ST|ΟΡΟΦΟΣ\s*1|Α['΄]?\s*ΟΡΟΦ"), ("roof", r"ROOF|ΔΩΜΑ"))
FLOOR_ORDER = {"basement": 0, "lower": 1, "ground": 2, "upper": 3, "roof": 4}
NOISE = r"PLAN|SECTION|ELEVATION|FLOOR|GROUND|LOWER|UPPER|MASTER|COMMENTS?|SCALE|ΚΑΤΟΨΗ|ΤΟΜΗ|ΟΨΗ|\d+|_|-|/"


@dataclass
class Sheet:
    path: str
    page: int = 0
    title: str = ""
    kind: str = "plan"
    building: str = ""
    floor: Optional[str] = None
    scale: Optional[int] = None
    texts: list = field(default_factory=list)
    anchors: List[Tuple[str, float, float]] = field(default_factory=list)     # (key, x, y) in metres at its scale
    segments: list = field(default_factory=list)                                # dark lines, metres at its scale
    page_size: Tuple[float, float] = (0.0, 0.0)                                 # visible page, PDF points
    water: list = field(default_factory=list)                                   # blue fills: [[(x, y)…]] metres
    items: list = field(default_factory=list)                                   # blocks / words: [(kind, x, y)] metres

    @property
    def metres_per_pt(self):
        return PT_M * (self.scale or 1)

    def levels(self):
        """(value, ceiling, x, y) of the written levels, metres at the sheet's scale."""
        return [(float(k[1:].rstrip("C")), k.endswith("C"), x, y) for k, x, y in self.anchors if k.startswith("L")]


def _match(table, text):
    return next((key for key, pattern in table if re.search(pattern, text, re.I)), None)


def classify(path, texts):
    """(title, kind, building, floor) from the largest text and the file name."""
    title = max(texts, key=lambda t: t.size).text if texts else ""
    name = os.path.splitext(os.path.basename(path))[0].replace("_", " ")
    both = f"{title} {name}"
    kind = _match(KINDS, title) or _match(KINDS, name) or "plan"
    floor = _match(FLOORS, title) or _match(FLOORS, name)
    m = re.search(r"\b((?:NEW|OLD|MAIN|EXISTING|ΝΕΑ|ΠΑΛΙΑ|ΥΦΙΣΤΑΜΕΝ\w*)\s+[A-ZΑ-Ω]+)", both.upper())
    building = m.group(1) if m else ""
    if not building and kind != "site":
        rest = re.sub(NOISE, " ", re.sub(r"^[0-9a-f]{8}\s", "", name.upper()))
        building = " ".join(rest.split()[:2])
    return title, kind, building.strip(), floor


def anchors(texts, metres_per_pt):
    """(key, x, y) of the levels and section marks, in metres at the sheet's scale."""
    from archforge.project.drawing_text import levels
    out = [(f"L{l.value:+.2f}{'C' if l.ceiling else ''}", l.x * metres_per_pt, l.y * metres_per_pt) for l in levels(texts)]
    for t in texts:
        if re.fullmatch(r"[A-ZΑ-Ω]{1,2}\d?\.\d{1,2}", t.text.strip()) and t.text.strip() not in ("A.1", "A.2"):
            out.append((f"M{t.text.strip()}", t.x * metres_per_pt, t.y * metres_per_pt))
    return out


def read_sheet(path, page=0, scale=None):
    """Everything the set needs of one PDF page (its texts and dark lines are read once)."""
    from archforge.project import drawing_text as T
    from archforge.project.underlay import pdf_vector_segments
    import pdfplumber
    texts = T.pdf_texts(path, page)
    with pdfplumber.open(str(path)) as pdf:
        x0, top, x1, bottom = (float(v) for v in pdf.pages[int(page)].cropbox)
    title, kind, building, floor = classify(path, texts)
    segs = pdf_vector_segments(path, page, dark_only=True)
    n = scale or T.scale(texts) or T.scale_from_dimensions(texts, segs)[0]
    k = PT_M * (n or 1)
    from archforge.project import drawing_contents as C
    return Sheet(path, page, title, kind, building, floor, n, texts, anchors(texts, k),
                 [(a * k, b * k, c * k, d * k) for a, b, c, d in segs], (x1 - x0, bottom - top),
                 [[(x * k, y * k) for x, y in poly] for poly in water_fills(path, page)],
                 C.read_items(path, page, k) + [(w, x * k, y * k) for w, x, y in C.words(texts)])


def _water(colour):
    """A pool's water: a light blue fill (the owner's drawings: 0,60 / 0,76 / 0,80) — blue and green over red."""
    if not isinstance(colour, (list, tuple)) or len(colour) != 3:
        return False
    r, g, b = (float(v) for v in colour)
    return b > r + 0.05 and g > r + 0.03 and min(g, b) > 0.5


def water_fills(path, page=0):
    """Water-coloured filled areas of the page as shown (PDF points, y up — the underlay's drawing units)."""
    import pdfplumber
    out = []
    with pdfplumber.open(str(path)) as pdf:
        p = pdf.pages[int(page)]
        cx0, ct, cx1, cb = (float(v) for v in p.cropbox)
        for o in list(p.curves) + list(p.rects):
            if not o.get("fill") or not _water(o.get("non_stroking_color")):
                continue
            pts = o.get("pts") or [(o["x0"], o["top"]), (o["x1"], o["top"]), (o["x1"], o["bottom"]), (o["x0"], o["bottom"])]
            if len(pts) >= 3:
                out.append([(float(x) - cx0, cb - float(t)) for x, t in pts])
    return out


# ------------------------------------------------------------------------------------------------------- pools

def _hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def min_rectangle(points):
    """(cx, cy, length, width, rotation°) of the smallest rectangle around the points (rotating calipers)."""
    hull = _hull([(round(x, 4), round(y, 4)) for x, y in points])
    best = None
    for i in range(len(hull)):
        (x1, y1), (x2, y2) = hull[i], hull[(i + 1) % len(hull)]
        L = math.hypot(x2 - x1, y2 - y1)
        if L < 1e-9:
            continue
        ux, uy = (x2 - x1) / L, (y2 - y1) / L
        us = [x * ux + y * uy for x, y in hull]
        vs = [-x * uy + y * ux for x, y in hull]
        area = (max(us) - min(us)) * (max(vs) - min(vs))
        if best is None or area < best[0]:
            cu, cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
            a, b = max(us) - min(us), max(vs) - min(vs)
            ang = math.degrees(math.atan2(uy, ux))
            if b > a:
                a, b, ang = b, a, ang + 90.0
            best = (area, (cu * ux - cv * uy, cu * uy + cv * ux, a, b, (ang + 90.0) % 180.0 - 90.0))
    return best[1] if best else None


def pools(sheets, placed, min_side=1.5, min_area=4.0, join=1.0):
    """Pools of the set in the site frame: water fills of every placed sheet, grouped where they touch (the same
    pool on the plan, its own sheet and the masterplan is one), each the smallest rectangle around it.
    ``[(cx, cy, length, width, rotation, sheet indices)]``."""
    blobs = []
    for i, (sim, _how) in placed.items():
        for poly in sheets[i].water:
            pts = [sim.apply(p) for p in poly]
            r = min_rectangle(pts)
            if r is None or r[3] < 0.30:
                continue                     # a glazing line drawn in water blue, not water
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            blobs.append([[(i, p) for p in pts], (min(xs), min(ys), max(xs), max(ys)), {i}])
    merged = True
    while merged:
        merged = False
        for a in range(len(blobs)):
            for b in range(a + 1, len(blobs)):
                (pa, ba, ia), (pb, bb, ib) = blobs[a], blobs[b]
                if ba[0] - join <= bb[2] and bb[0] - join <= ba[2] and ba[1] - join <= bb[3] and bb[1] - join <= ba[3]:
                    blobs[a] = [pa + pb, (min(ba[0], bb[0]), min(ba[1], bb[1]), max(ba[2], bb[2]), max(ba[3], bb[3])), ia | ib]
                    del blobs[b]
                    merged = True
                    break
            if merged:
                break
    out = []
    for tagged, _box, idx in blobs:
        # One pool drawn on several sheets: the finest scale tells it best, and of those the smallest rectangle
        # is the water alone (the plan draws the overflow channel too: 7,94 × 3,59 against the pool sheet's 2,98).
        each = []
        for i in idx:
            r = min_rectangle([p for k, p in tagged if k == i])
            if r and r[3] >= min_side and r[2] * r[3] >= min_area:
                each.append((sheets[i].scale or 10 ** 6, r[2] * r[3], r))
        if each:
            r = min(each)[2]
            out.append((*r, sorted(idx)))
    return out


# ------------------------------------------------------------------------------------------------------- levels

ABSOLUTE = 10.0          # written altitudes (+114.00) vs levels relative to a building's ±0,00 (-2.80)


def building_zero(sheets):
    """Altitude of a building's ±0,00: the altitude written next to its «±0.00» on any of its sheets (within 1 m)
    — OLD VILLA: «±00.00m» with «+131.80m» 47 cm away."""
    for s in sheets:
        lv = [l for l in s.levels() if not l[1]]
        for v, _c, x, y in lv:
            if abs(v) > 1e-6:
                continue
            near = sorted((math.dist((x, y), (u, w)), a) for a, _c2, u, w in lv if a >= ABSOLUTE)
            if near and near[0][0] <= 1.0:
                return near[0][1]
    return None


def floor_altitude(sheet, zero=None):
    """Altitude of the floor a plan shows: its most written relative level from the building's ±0,00 when known
    (OLD VILLA lower: −2.80 → +129.00), else its most written altitude (NEW VILLA: +114.00 ×4)."""
    lv = [l for l in sheet.levels() if not l[1]]
    rel = Counter(round(v, 2) for v, _c, _x, _y in lv if abs(v) < ABSOLUTE)
    ab = Counter(round(v, 2) for v, _c, _x, _y in lv if v >= ABSOLUTE)
    if rel and zero is not None:
        v, _n = max(rel.items(), key=lambda kv: (kv[1], -abs(kv[0])))
        return round(zero + v, 2)
    if ab:
        return max(ab.items(), key=lambda kv: (kv[1], kv[0]))[0]
    return None


# --------------------------------------------------------------------------------------------- relating sheets

@dataclass
class Similarity:
    scale: float          # B = scale · R(turn) · A + shift
    turn: float           # degrees
    shift: Tuple[float, float]
    inliers: int
    error: float          # rms of the agreeing anchors (m)

    def apply(self, p):
        c, s = math.cos(math.radians(self.turn)), math.sin(math.radians(self.turn))
        return (self.scale * (c * p[0] - s * p[1]) + self.shift[0], self.scale * (s * p[0] + c * p[1]) + self.shift[1])


def _fit(pairs):
    """Least-squares similarity (Umeyama, 2D) mapping the a-points onto the b-points."""
    n = len(pairs)
    ax = sum(a[0] for a, _b in pairs) / n; ay = sum(a[1] for a, _b in pairs) / n
    bx = sum(b[0] for _a, b in pairs) / n; by = sum(b[1] for _a, b in pairs) / n
    sxx = sxy = var = 0.0
    for (a, b) in pairs:
        u, v, p, q = a[0] - ax, a[1] - ay, b[0] - bx, b[1] - by
        sxx += u * p + v * q
        sxy += u * q - v * p
        var += u * u + v * v
    if var < 1e-12:
        return None
    turn = math.atan2(sxy, sxx)
    scale = math.hypot(sxx, sxy) / var
    c, s = math.cos(turn), math.sin(turn)
    shift = (bx - scale * (c * ax - s * ay), by - scale * (s * ax + c * ay))
    return Similarity(scale, math.degrees(turn), shift, n, 0.0)


def relate_by_anchors(a, b, tolerance=0.35, scale_range=(0.02, 50.0), same_scale=False):
    """Similarity from sheet a's anchors onto sheet b's, or None (fewer than 3 agreeing / all at one spot)."""
    cand = [(p[1:], q[1:]) for p in a for q in b if p[0] == q[0]]
    if len(cand) < 3:
        return None
    best = None
    for i in range(len(cand)):
        for j in range(i + 1, len(cand)):
            (pa, qa), (pb, qb) = cand[i], cand[j]
            if math.dist(pa, pb) < 1.0 or math.dist(qa, qb) < 1e-6:
                continue
            sim = _fit([cand[i], cand[j]])
            if sim is None or not scale_range[0] <= sim.scale <= scale_range[1]:
                continue
            if same_scale and abs(sim.scale - 1) > 0.02:
                continue
            ok = [(p, q) for p, q in cand if math.dist(sim.apply(p), q) <= tolerance * max(1.0, sim.scale)]
            # Each anchor of a counts once (four «+114.00» on the plan are not four confirmations of one).
            used, unique = set(), []
            for p, q in sorted(ok, key=lambda pq: math.dist(sim.apply(pq[0]), pq[1])):
                if p not in used and q not in used:
                    used.update((p, q)); unique.append((p, q))
            if best is None or len(unique) > len(best):
                best = unique
    if not best or len(best) < 3:
        return None
    sim = _fit(best)
    sim.inliers = len(best)
    sim.error = math.sqrt(sum(math.dist(sim.apply(p), q) ** 2 for p, q in best) / len(best))
    return sim


def _corners(segments, limit=1500):
    pts = Counter()
    for x1, y1, x2, y2 in segments:
        if math.hypot(x2 - x1, y2 - y1) >= 0.5:
            for x, y in ((x1, y1), (x2, y2)):
                pts[(round(x / 0.05), round(y / 0.05))] += 1
    return [(x * 0.05, y * 0.05) for (x, y), _n in pts.most_common(limit)]


def relate_by_walls(a_segments, b_segments, cell=0.05, min_votes=12):
    """The shift (same scale, no turn) that brings most of a's line ends onto b's: Similarity or None."""
    A, B = _corners(a_segments), _corners(b_segments)
    if not A or not B:
        return None
    votes = Counter()
    for x1, y1 in A:
        for x2, y2 in B:
            votes[(round((x2 - x1) / cell), round((y2 - y1) / cell))] += 1
    (dx, dy), n = votes.most_common(1)[0]
    # Neighbouring cells are the same shift split by rounding.
    n = sum(votes.get((dx + i, dy + j), 0) for i in (-1, 0, 1) for j in (-1, 0, 1))
    if n < min_votes:
        return None
    return Similarity(1.0, 0.0, (dx * cell, dy * cell), n, cell)


def relate_by_walls_confirmed(plan, site, reach=1.5, peaks=6, min_votes=12):
    """A plan onto the site plan by its walls (both in metres, no turn), when a level written on both confirms the
    place: the OLD VILLA's lower floor writes only levels relative to its ±0,00 (−2.80, −3.45) — one shared value,
    too few for anchors — but its walls are on the masterplan (81 corners) and «−2.80» lands 0,5 m from the
    masterplan's «−2.80».  Of the strongest shifts the first a shared level confirms; None if none does."""
    A, B = _corners(plan.segments), _corners(site.segments)
    if not A or not B:
        return None
    cell = 0.05
    votes = Counter()
    for x1, y1 in A:
        for x2, y2 in B:
            votes[(round((x2 - x1) / cell), round((y2 - y1) / cell))] += 1
    mine = [(k, x, y) for k, x, y in plan.anchors if k.startswith("L")]
    theirs = [(k, x, y) for k, x, y in site.anchors if k.startswith("L")]
    seen = []
    for (dx, dy), _n in votes.most_common(peaks * 9):
        if any(abs(dx - a) <= 1 and abs(dy - b) <= 1 for a, b in seen):
            continue
        seen.append((dx, dy))
        if len(seen) > peaks:
            break
        n = sum(votes.get((dx + i, dy + j), 0) for i in (-1, 0, 1) for j in (-1, 0, 1))
        if n < min_votes:
            break
        sx, sy = dx * cell, dy * cell
        if any(k == q and math.dist((x + sx, y + sy), (u, v)) <= reach for k, x, y in mine for q, u, v in theirs):
            return Similarity(1.0, 0.0, (sx, sy), n, cell)
    return None


def zero_from_site(site, site_sim, plan, plan_sim, reach=3.0, near=1.0):
    """A building's ±0,00 from the site plan, where its sheets write no «±0.00»: the plan's relative level placed
    on the site plan meets the same relative level there, written next to an altitude (masterplan: «−2.80m» with
    «+129.00m» 33 cm away → ±0,00 = +131,80)."""
    lv = [(v, x, y) for v, c, x, y in site.levels() if not c]
    for v, c, x, y in plan.levels():
        if c or abs(v) >= ABSOLUTE:
            continue
        p = plan_sim.apply((x, y))
        for w, u, t in lv:
            if abs(w - v) > 1e-6 or math.dist(site_sim.apply((u, t)), p) > reach:
                continue
            alts = sorted((math.dist((u, t), (a, b)), z) for z, a, b in lv if z >= ABSOLUTE)
            if alts and alts[0][0] <= near:
                return round(alts[0][1] - v, 2)
    return None


# ------------------------------------------------------------------------------------------------ the whole set

def relate(sheets: List[Sheet]):
    """Place every sheet in the frame of the site plan (else the plan with most anchors): ``{index: (Similarity, how)}``.

    Anchors first (any two sheets: plan ↔ masterplan ↔ other building's plan), then walls for sheets of the
    same building and scale (lower ↔ upper floor).  Unplaced sheets are left out (the person places them
    with «Ταίριασμα με 2 σημεία»)."""
    plans = [i for i, s in enumerate(sheets) if s.kind in ("plan", "site") and s.scale]
    if not plans:
        return {}
    sites = [i for i in plans if sheets[i].kind == "site"]
    ref = max(sites or plans, key=lambda i: len(sheets[i].anchors))
    placed = {ref: (Similarity(1.0, 0.0, (0.0, 0.0), 0, 0.0), "αναφορά")}
    # The site plan's walls are the last resort: a floor of the same building, once placed, tells the place
    # better (OLD VILLA lower floor: 0,4 m off on the masterplan, exact on its upper floor's walls).
    site_walls = False
    changed = True
    while changed or not site_walls:
        if not changed:
            site_walls = True
        changed = False
        for i, s in enumerate(sheets):
            if i in placed or s.kind == "section":
                continue
            for j, (sim_j, _how) in list(placed.items()):
                t = sheets[j]
                same = bool(s.scale and t.scale)
                # Both scales known (written or from the dimensions): the match may only confirm them (±2 %);
                # the NEW VILLA on the masterplan: free 0,93 / 18 cm, held 0,99 / 7 cm.
                sim = relate_by_anchors(s.anchors, t.anchors, same_scale=same)
                how = f"υψόμετρα/σημάδια ({sim.inliers} κοινά)" if sim else ""
                if sim is None and same and s.kind == t.kind == "plan" and s.building == t.building and s.scale == t.scale:
                    sim = relate_by_walls(s.segments, t.segments)
                    how = f"τοίχοι ({sim.inliers} γωνίες)" if sim else ""
                if sim is None and site_walls and same and s.kind == "plan" and t.kind == "site":
                    sim = relate_by_walls_confirmed(s, t)
                    how = f"τοίχοι στη γενική διάταξη ({sim.inliers} γωνίες, ίδιο υψόμετρο)" if sim else ""
                if sim is not None:
                    placed[i] = (_chain(sim, sim_j), how)
                    changed = True
                    site_walls = False
                    break
    return placed


def _chain(first, then):
    """``then ∘ first`` as one similarity."""
    p0, p1 = first.apply((0.0, 0.0)), first.apply((1.0, 0.0))
    q0, q1 = then.apply(p0), then.apply(p1)
    scale = math.dist(q0, q1)
    turn = math.degrees(math.atan2(q1[1] - q0[1], q1[0] - q0[0]))
    return Similarity(scale, turn, q0, first.inliers, first.error)


def pool_level(sheets, placed, centre, reach=8.0):
    """Altitude of a pool: the written altitude nearest its centre on any placed sheet (within ``reach`` m)."""
    best = None
    for i, (sim, _how) in placed.items():
        for v, ceiling, x, y in sheets[i].levels():
            if ceiling or v < ABSOLUTE:
                continue
            d = math.dist(sim.apply((x, y)), centre)
            if d <= reach and (best is None or d < best[0]):
                best = (d, v)
    return None if best is None else best[1]


def platform(points, grow=0.30):
    """The smallest rectangle around ``points`` grown by ``grow`` on every side, as 4 corners."""
    r = min_rectangle(points)
    if r is None:
        return None
    cx, cy, L, W, rot = r
    a = math.radians(rot)
    c, s = math.cos(a), math.sin(a)
    hl, hw = L / 2 + grow, W / 2 + grow
    return [[cx + c * u - s * v, cy + s * u + c * v] for u, v in ((-hl, -hw), (hl, -hw), (hl, hw), (-hl, hw))]
