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
    texts = T.pdf_texts(path, page)
    title, kind, building, floor = classify(path, texts)
    segs = pdf_vector_segments(path, page, dark_only=True)
    n = scale or T.scale(texts) or T.scale_from_dimensions(texts, segs)[0]
    k = PT_M * (n or 1)
    return Sheet(path, page, title, kind, building, floor, n, texts, anchors(texts, k),
                 [(a * k, b * k, c * k, d * k) for a, b, c, d in segs])


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
    changed = True
    while changed:
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
                if sim is not None:
                    placed[i] = (_chain(sim, sim_j), how)
                    changed = True
                    break
    return placed


def _chain(first, then):
    """``then ∘ first`` as one similarity."""
    p0, p1 = first.apply((0.0, 0.0)), first.apply((1.0, 0.0))
    q0, q1 = then.apply(p0), then.apply(p1)
    scale = math.dist(q0, q1)
    turn = math.degrees(math.atan2(q1[1] - q0[1], q1[0] - q0[0]))
    return Similarity(scale, turn, q0, first.inliers, first.error)
