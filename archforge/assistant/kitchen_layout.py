"""Kitchen along the walls of a room (Ι / Γ / Π): the assistant's proposal.

The user points at a room (or draws guide legs along its walls); the
planner turns the free wall length into segments (doors, low windows and
whatever already stands there are cut out; a door on the neighbouring wall
near a corner keeps its swing free), puts an L corner unit where two legs
meet, then searches the positions of fridge, sink (+ dishwasher) and hob
and fills the rest with base units of equal width (custom widths are the
Greek carpenter's practice).  Wall units go over the base run, never in
front of a window and never over the hob (the hood is there).

Rules (proposed values, common kitchen-planning practice — Neufert, NKBA
kitchen planning guidelines — not a code requirement):

* hob: ≥ 30 cm of worktop on one side and ≥ 40 cm on the other, not under
  a window, hood 65 cm above it;
* sink: ≥ 40 cm of worktop beside it, preferably under a window or near an
  existing water point; dishwasher right next to it;
* fridge at the end of the run, ≥ 30 cm of worktop to the hob;
* work triangle fridge–sink–hob: 4.0–7.9 m in total, each side 1.2–2.7 m;
* U: ≥ 1.00 m clear between the opposite worktops (1.10–1.20 m better).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from archforge.assistant.room_layout import (LayoutProposal, cabinet_entity, library_entity, obstacles,
                                             point_entity, run_interval, spec_legs, subtract)
from archforge.assistant.room_walls import DOOR_MARGIN, fmt_m, is_corner, room_runs

BASE_D, WALL_D, CORNER = 0.60, 0.35, 0.90
FRIDGE_W, SINK_W, SINK_SMALL, DW_W, HOB_W = 0.60, 0.80, 0.60, 0.60, 0.60
TOP = 0.90            # worktop surface: base 86 cm + worktop 4 cm
HOOD_Z = TOP + 0.65   # hood 65 cm above the hob
WALL_Z, WALL_H = 1.45, 0.72
FRIDGE_H, FRIDGE_TOP_Z, FRIDGE_TOP_H = 1.85, 1.87, 0.30
LOW_SILL = TOP + 0.02  # a window lower than the worktop stops the base run
MIN_UNIT = 0.15
HOB_LANDING = (0.30, 0.40)
SINK_LANDING = 0.40
SINK_HOB = 0.40
TRIANGLE = (4.0, 7.9)
TRIANGLE_SIDE = (1.2, 2.7)
U_CLEAR = 1.00
STEP = 0.10

SHAPES = {"auto": "Αυτόματο", "I": "Ι (ευθεία)", "L": "Γ (γωνία)", "U": "Π"}
SHAPE_LETTER = {"I": "Ι", "L": "Γ", "U": "Π"}
RULES = (
    "Εστία: ≥ 30 cm πάγκος από τη μία πλευρά, ≥ 40 cm από την άλλη· όχι κάτω από παράθυρο· απορροφητήρας 65 cm πάνω της",
    "Νεροχύτης: ≥ 40 cm πάγκος δίπλα, κατά προτίμηση κάτω από παράθυρο ή κοντά σε παροχή· πλυντήριο πιάτων δίπλα του",
    "Ψυγείο στην άκρη της σειράς, ≥ 30 cm πάγκος ως την εστία",
    "Τρίγωνο εργασίας ψυγείο–νεροχύτης–εστία: σύνολο 4,0–7,9 m, κάθε πλευρά 1,2–2,7 m",
    "Κρεμαστά όχι μπροστά από παράθυρο ούτε πάνω από την εστία",
    "Π: ελεύθερο ανάμεσα στους πάγκους ≥ 1,00 m (καλύτερα 1,10–1,20 m)",
)
SOURCE = "Προτεινόμενες τιμές — συνήθης πρακτική σχεδιασμού κουζίνας (Neufert, οδηγίες NKBA), όχι κανονιστική απαίτηση"
COUNTER_KINDS = ("dw",)


@dataclass
class Seg:
    run: int
    s0: float
    s1: float
    leg: int
    corner_before: bool = False
    corner_after: bool = False

    @property
    def length(self):
        return self.s1 - self.s0


def _cuts(doc, runs, level, ignore):
    """Per run: intervals no base unit may take (doors with a margin, low windows, things in the way)."""
    stuff = obstacles(doc, level, ignore)
    out = []
    for r in runs:
        cuts = [(o.s0 - DOOR_MARGIN, o.s1 + DOOR_MARGIN) for o in r.doors()]
        cuts += [(o.s0, o.s1) for o in r.windows() if o.sill < LOW_SILL]
        for _e, poly in stuff:
            iv = run_interval(r, poly, BASE_D + 0.05)
            if iv:
                cuts.append(iv)
        out.append(cuts)
    return out


def _door_swing_cut(runs, i, at_end):
    """How far the run must stay from its end / start: a door of the neighbouring wall near that corner."""
    n = len(runs)
    r = runs[i]
    keep = 0.0
    if at_end:
        adj = runs[(i + 1) % n]
        for d in adj.doors():
            if d.s0 < BASE_D + DOOR_MARGIN:
                keep = max(keep, d.width + DOOR_MARGIN)
    else:
        adj = runs[(i - 1) % n]
        for d in adj.doors():
            if adj.length - d.s1 < BASE_D + DOOR_MARGIN:
                keep = max(keep, d.width + DOOR_MARGIN)
    return min(keep, r.length)


def segments(runs, legs, cuts):
    """Free base-run segments in path order and the corners that get an L unit (leg index k: between k and k+1)."""
    corners = set()
    for k in range(len(legs) - 1):
        i, lo, hi = legs[k]
        j, lo2, hi2 = legs[k + 1]
        if not (is_corner(runs, i, j) and hi >= runs[i].length - 0.02 and lo2 <= 0.02):
            continue
        zone_i = (runs[i].length - CORNER, runs[i].length)
        zone_j = (0.0, CORNER)
        if hi - lo < CORNER or hi2 - lo2 < CORNER:
            continue
        if subtract([zone_i], cuts[i]) == [zone_i] and subtract([zone_j], cuts[j]) == [zone_j]:
            corners.add(k)
    segs = []
    for k, (i, lo, hi) in enumerate(legs):
        r = runs[i]
        a, b = lo, hi
        if k - 1 in corners:
            a = max(a, CORNER)
        elif k > 0 and lo <= 0.02 and is_corner(runs, legs[k - 1][0], i) and legs[k - 1][2] >= runs[legs[k - 1][0]].length - 0.02:
            a = max(a, BASE_D)                      # the previous leg runs into this corner
        elif lo <= 0.02:
            a = max(a, _door_swing_cut(runs, i, False))
        if k in corners:
            b = min(b, r.length - CORNER)
        elif hi >= r.length - 0.02:
            b = min(b, r.length - _door_swing_cut(runs, i, True))
        for p0, p1 in subtract([(a, b)], cuts[i], MIN_UNIT):
            segs.append(Seg(i, p0, p1, k, corner_before=(k - 1 in corners and abs(p0 - CORNER) < 1e-6),
                            corner_after=(k in corners and abs(p1 - (r.length - CORNER)) < 1e-6)))
    return segs, corners


# ------------------------------------------------------------------ automatic legs
def _free(r, cuts):
    return subtract([(0.0, r.length)], cuts, 0.0)


def candidates(runs, cuts, shape="auto"):
    """Possible legs ``[(shape, legs)]`` for a click in the room, best first."""
    n = len(runs)
    ok = [r.thickness > 0 and r.length >= CORNER for r in runs]
    out = []

    def tail(i):
        parts = _free(runs[i], cuts[i])
        return parts[-1] if parts and abs(parts[-1][1] - runs[i].length) < 1e-6 else None

    def head(i):
        parts = _free(runs[i], cuts[i])
        return parts[0] if parts and parts[0][0] < 1e-6 else None

    for i in range(n):
        if not ok[i]:
            continue
        if shape in ("auto", "I"):
            parts = _free(runs[i], cuts[i])
            if parts:
                lo, hi = max(parts, key=lambda p: p[1] - p[0])
                if hi - lo >= 1.2:
                    out.append(("I", [(i, lo, hi)]))
        j, k = (i + 1) % n, (i + 2) % n
        if shape in ("auto", "L") and ok[j] and is_corner(runs, i, j):
            t, h = tail(i), head(j)
            if t and h and t[1] - t[0] >= CORNER + 0.3 and h[1] - h[0] >= CORNER + 0.3:
                out.append(("L", [(i, *t), (j, *h)]))
        if shape in ("auto", "U") and n >= 4 and ok[j] and ok[k] and is_corner(runs, i, j) and is_corner(runs, j, k):
            t, h = tail(i), head(k)
            whole = _free(runs[j], cuts[j])
            if t and h and whole == [(0.0, runs[j].length)]:
                out.append(("U", [(i, *t), (j, 0.0, runs[j].length), (k, *h)]))

    def cheap(c):
        sh, legs = c
        segs, _corners = segments(runs, legs, cuts)
        total = sum(s.length for s in segs) + CORNER * len(_corners)
        window = any(o.sill >= LOW_SILL for i, _lo, _hi in legs for o in runs[i].windows())
        weight = {"L": 0.0, "U": 0.4, "I": 0.8}[sh]
        if sh == "U" and _u_clear(runs, legs) < U_CLEAR:
            weight += 5.0
        return weight - min(total, 5.5) - (0.6 if window else 0.0)
    return sorted(out, key=cheap)


def _u_clear(runs, legs):
    if len(legs) < 3:
        return float("inf")
    a, b = runs[legs[0][0]], runs[legs[-1][0]]
    dist = (b.a[0] - a.a[0]) * a.n[0] + (b.a[1] - a.a[1]) * a.n[1]
    return dist - 2 * BASE_D


def shape_of(legs):
    return {1: "I", 2: "L"}.get(len(legs), "U")


# ------------------------------------------------------------------ appliances
def _positions(segs, width):
    out = []
    for k, s in enumerate(segs):
        if s.length < width - 1e-9:
            continue
        xs = {round(s.s0, 4), round(s.s1 - width, 4)}
        x = s.s0 + STEP
        while x + width < s.s1 - 1e-9:
            xs.add(round(x, 4))
            x += STEP
        out += [(k, x) for x in sorted(xs)]
    return out


def _check(segs, items):
    """Items ``[(seg, a, b, kind)]`` fit: no overlap, and every leftover gap is 0 or fillable (≥ MIN_UNIT)."""
    per = {}
    for it in items:
        per.setdefault(it[0], []).append(it)
    for k, its in per.items():
        its.sort(key=lambda t: t[1])
        edge = segs[k].s0
        for _k, a, b, _kind in its:
            gap = a - edge
            if gap < -1e-6 or 1e-6 < gap < MIN_UNIT - 1e-6:
                return False
            edge = b
        gap = segs[k].s1 - edge
        if gap < -1e-6 or 1e-6 < gap < MIN_UNIT - 1e-6:
            return False
    return True


def _counter(segs, items, k, pos, direction):
    """Worktop from ``pos`` along segment ``k`` (direction ±1) to the next non-worktop item or the end."""
    s = segs[k]
    limit = s.s1 if direction > 0 else s.s0
    for kk, a, b, kind in items:
        if kk != k or kind in COUNTER_KINDS:
            continue
        if direction > 0 and a >= pos - 1e-6:
            limit = min(limit, a)
        if direction < 0 and b <= pos + 1e-6:
            limit = max(limit, b)
    run = abs(limit - pos)
    end_corner = s.corner_after if direction > 0 else s.corner_before
    if end_corner and abs(limit - (s.s1 if direction > 0 else s.s0)) < 1e-6:
        run += CORNER
    return run


def _front(runs, segs, k, a, b, depth=BASE_D):
    return runs[segs[k].run].point((a + b) / 2, depth)


def search(runs, segs, *, flip=False, dishwasher=True, fridge=True, water=(), sink_w=SINK_W):
    """Best placements, ``[(score, items)]`` with items ``[(seg, a, b, kind)]``, best first."""
    if not segs:
        return []
    items0 = []
    if fridge:
        if flip:
            last = len(segs) - 1
            if segs[last].length >= FRIDGE_W - 1e-9:
                items0.append((last, segs[last].s1 - FRIDGE_W, segs[last].s1, "fridge"))
        elif segs[0].length >= FRIDGE_W - 1e-9:
            items0.append((0, segs[0].s0, segs[0].s0 + FRIDGE_W, "fridge"))
    sinks = _positions(segs, sink_w)
    hobs = _positions(segs, HOB_W)
    windows = {}
    for i in {s.run for s in segs}:
        windows[i] = [(o.s0, o.s1) for o in runs[i].windows() if o.sill >= LOW_SILL]
    fridge_pt = _front(runs, segs, *items0[0][:3], depth=0.65) if items0 else None
    found = []
    for sk, sx in sinks:
        sink = (sk, sx, sx + sink_w, "sink")
        if not _check(segs, items0 + [sink]):
            continue
        dws = []
        if dishwasher:
            for a in (sx - DW_W, sx + sink_w):
                dw = (sk, a, a + DW_W, "dw")
                if segs[sk].s0 - 1e-6 <= a and a + DW_W <= segs[sk].s1 + 1e-6 and _check(segs, items0 + [sink, dw]):
                    dws.append(dw)
        dws = dws or [None]
        sink_pt = _front(runs, segs, sk, sx, sx + sink_w)
        run_s = runs[segs[sk].run]
        mid = sx + sink_w / 2
        base = 0.0
        if any(w0 - 0.05 <= mid <= w1 + 0.05 for w0, w1 in windows.get(segs[sk].run, ())):
            base -= 1.5
        if water:
            sp = run_s.point(mid, 0.0)
            base += 0.4 * min(math.hypot(sp[0] - wx, sp[1] - wy) for wx, wy in water)
        for dw in dws:
            fixed = items0 + [sink] + ([dw] if dw else [])
            extra = base + (3.0 if dishwasher and dw is None else 0.0)
            if dw and ((dw[1] - segs[sk].s0 < 1e-6 and segs[sk].corner_before) or
                       (segs[sk].s1 - dw[2] < 1e-6 and segs[sk].corner_after)):
                extra += 0.5                             # the dishwasher door would hit the corner unit
            sink_land = max(_counter(segs, fixed, sk, sx, -1), _counter(segs, fixed, sk, sx + sink_w, 1))
            if sink_land < SINK_LANDING - 1e-6:
                continue
            for hk, hx in hobs:
                hob = (hk, hx, hx + HOB_W, "hob")
                items = fixed + [hob]
                if not _check(segs, items):
                    continue
                left, right = _counter(segs, items, hk, hx, -1), _counter(segs, items, hk, hx + HOB_W, 1)
                if min(left, right) < HOB_LANDING[0] - 1e-6 or max(left, right) < HOB_LANDING[1] - 1e-6:
                    continue
                if hk == sk and (hx >= sx and hx - (sx + sink_w) < SINK_HOB - 1e-6 or hx < sx and sx - (hx + HOB_W) < SINK_HOB - 1e-6):
                    # Worktop between sink and hob (a dishwasher counts: it has a worktop on top).
                    gap = (hx - (sx + sink_w)) if hx >= sx else (sx - (hx + HOB_W))
                    if gap < SINK_HOB - 1e-6:
                        continue
                score = extra
                hmid = hx + HOB_W / 2
                if any(w0 - 0.05 <= hmid <= w1 + 0.05 for w0, w1 in windows.get(segs[hk].run, ())):
                    score += 3.0
                if (hx - segs[hk].s0 < 0.1 and segs[hk].corner_before) or (segs[hk].s1 - hx - HOB_W < 0.1 and segs[hk].corner_after):
                    score += 0.3
                hob_pt = _front(runs, segs, hk, hx, hx + HOB_W)
                sh = math.dist(sink_pt, hob_pt)
                if fridge_pt is not None:
                    fs, hf = math.dist(fridge_pt, sink_pt), math.dist(hob_pt, fridge_pt)
                    tri = fs + sh + hf
                    score += 1.5 * max(0.0, TRIANGLE[0] - tri) + 1.5 * max(0.0, tri - TRIANGLE[1])
                    for side in (fs, sh, hf):
                        score += 0.5 * max(0.0, TRIANGLE_SIDE[0] - side) + 0.3 * max(0.0, side - TRIANGLE_SIDE[1])
                else:
                    score += 0.5 * max(0.0, TRIANGLE_SIDE[0] - sh) + 0.3 * max(0.0, sh - TRIANGLE_SIDE[1])
                found.append((round(score, 4), items))
    found.sort(key=lambda f: f[0])
    out = []
    for score, items in found:
        key = {it[3]: (it[0], it[1]) for it in items}
        if any(all(k2[0] == key[kind][0] and abs(k2[1] - key[kind][1]) < 0.45 for kind, k2 in prev.items() if kind in key)
               for prev in (dict((it[3], (it[0], it[1])) for it in o[1]) for o in out)):
            continue
        out.append((score, items))
        if len(out) >= 3:
            break
    return out


def _fill(length, lo=0.40, hi=0.90, target=0.60):
    """Equal widths that fill ``length`` exactly (custom widths, carpenter's practice)."""
    if length < MIN_UNIT - 1e-9:
        return []
    n = max(1, int(round(length / target)))
    while length / n > hi and n < 50:
        n += 1
    while n > 1 and length / n < lo:
        n -= 1
    return [length / n] * n


def _water_points(doc, room, level):
    from archforge.assistant.understanding import inside
    out = []
    for e in doc.entities.values():
        p = e.params
        if e.kind == "plumbing_point" and p.get("point_type") in ("kitchen_sink", "water_supply") and not p.get("layout_id") \
                or e.kind == "drainage_point" and p.get("point_type") == "stack":
            if abs(float(p.get("z", 0.0)) - level) < 0.5 and (inside(room["polygon"], float(p["x"]), float(p["y"])) or e.kind == "drainage_point"):
                out.append((float(p["x"]), float(p["y"])))
    return out


# ------------------------------------------------------------------ the proposal
def plan_kitchen(doc, room, *, legs=None, options=None, variant=0, z=None, ignore=()):
    options = dict(options or {})
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    shape = options.get("shape", "auto")
    dishwasher = bool(options.get("dishwasher", True))
    fridge = bool(options.get("fridge", True))
    runs = room_runs(doc, room, level)
    cuts = _cuts(doc, runs, level, ignore)
    water = _water_points(doc, room, level)
    if legs:
        choices = [(shape_of(legs), legs, flip, k) for k in range(3) for flip in (False, True)]
    else:
        cands = candidates(runs, cuts, shape)[:6]
        choices = [(sh, lg, flip, 0) for sh, lg in cands for flip in (False, True)]
    spec = {"kind": "kitchen", "options": options, "z": level, "point": list(room["centroid"])}
    if not choices:
        return LayoutProposal("kitchen", [], "Κουζίνα — δεν βρέθηκε θέση", notes=list(RULES), source=SOURCE,
                              problems=["Δεν βρέθηκε ελεύθερος τοίχος για κουζίνα (πόρτες/εμπόδια) — σχεδίασε γραμμή πάνω στον τοίχο"],
                              spec=spec)
    cache = {}
    picked = None
    for step in range(len(choices)):
        v = (variant + step) % len(choices)
        sh, lg, flip, rank = choices[v]
        key = (tuple(lg), flip)
        if key not in cache:
            segs, corners = segments(runs, lg, cuts)
            sols = search(runs, segs, flip=flip, dishwasher=dishwasher, fridge=fridge, water=water)
            if not sols and dishwasher:
                sols = search(runs, segs, flip=flip, dishwasher=False, fridge=fridge, water=water)
            if not sols:
                sols = search(runs, segs, flip=flip, dishwasher=False, fridge=fridge, water=water, sink_w=SINK_SMALL)
            if not sols and fridge:
                sols = search(runs, segs, flip=flip, dishwasher=False, fridge=False, water=water, sink_w=SINK_SMALL)
            cache[key] = (segs, corners, sols)
        segs, corners, sols = cache[key]
        if rank < len(sols) or (not sols and segs and legs):
            picked = (v, sh, lg, segs, corners, sols[rank] if rank < len(sols) else None)
            break
    if picked is None:
        sh, lg = choices[0][0], choices[0][1]
        segs, corners = segments(runs, lg, cuts)
        picked = (0, sh, lg, segs, corners, None)
    v, sh, lg, segs, corners, sol = picked
    stored, walls = spec_legs(runs, lg)
    spec.update(shape=sh, legs=stored, walls=walls, variant=v)
    proposal = _build(doc, runs, lg, segs, corners, sol, level, options)
    proposal.spec, proposal.legs, proposal.variant, proposal.variants = spec, list(lg), v, len(choices)
    proposal.label = f"Κουζίνα {SHAPE_LETTER[sh]} · παραλλαγή {v + 1}/{len(choices)}"
    if sh == "U" and _u_clear(runs, lg) < U_CLEAR:
        proposal.problems.append(f"Π: ελεύθερο ανάμεσα στους πάγκους {fmt_m(_u_clear(runs, lg))} < 1,00 m")
    return proposal


def _build(doc, runs, legs, segs, corners, sol, level, options):
    from archforge.assistant.suggestions import _vent_entity
    ents, notes, problems = [], [], []
    items = sol[1] if sol else []
    dishwasher = bool(options.get("dishwasher", True))
    if sol is None:
        problems.append("Δεν χωράνε νεροχύτης και εστία με τους προτεινόμενους πάγκους — μόνο ντουλάπια")
    kinds = {it[3] for it in items}
    if items and dishwasher and "dw" not in kinds:
        problems.append("Δεν χωράει πλυντήριο πιάτων δίπλα στον νεροχύτη")
    if items and options.get("fridge", True) and "fridge" not in kinds:
        problems.append("Το ψυγείο δεν χωράει στην άκρη της σειράς — τοποθέτησέ το ξεχωριστά")
    hosts = {}
    hob_at = fridge_at = None
    # Corner units.
    for k in sorted(corners):
        i = legs[k][0]
        r = runs[i]
        ents.append(cabinet_entity("corner", r, r.length - CORNER, CORNER, level, "corner"))
    # Appliances and the base units around them.
    for k, s in enumerate(segs):
        r = runs[s.run]
        mine = sorted([it for it in items if it[0] == k], key=lambda t: t[1])
        edge = s.s0
        for _k, a, b, kind in mine + [(k, s.s1, s.s1, None)]:
            x = edge
            for w in _fill(a - edge):
                if w < 0.30:
                    ents.append(cabinet_entity("base", r, x, w, level, "base", name="Συρόμενο καλάθι (cargo)",
                                               mechanism="cargo", doors=0, drawers=0, shelves=0))
                else:
                    ents.append(cabinet_entity("base", r, x, w, level, "base"))
                x += w
            if kind == "sink":
                cab = cabinet_entity("sink", r, a, b - a, level, "sink")
                ents.append(cab)
                ents.append(point_entity("kitchen_sink", r, (a + b) / 2, level, cab))
                hosts["sink"] = (r, a, b)
            elif kind == "dw":
                cab = cabinet_entity("base", r, a, b - a, level, "dishwasher", name="Πλυντήριο πιάτων (εντοιχιζόμενο)",
                                     doors=1, drawers=0, shelves=0)
                ents.append(cab)
                ents.append(point_entity("dishwasher", r, (a + b) / 2, level, cab))
            elif kind == "hob":
                cab = cabinet_entity("drawers", r, a, b - a, level, "hob_base", name="Ντουλάπι εστίας (συρτάρια)")
                ents.append(cab)
                hob = library_entity("Εστία κεραμική 60", r, (a + b) / 2, 0.64, level + TOP, "hob")
                hood = library_entity("Απορροφητήρας 60", r, (a + b) / 2, None, level + HOOD_Z, "hood")
                for extra in (hob, hood):
                    if extra is not None:
                        extra.params["layout_host"] = cab.id
                        ents.append(extra)
                hx, hy = r.point((a + b) / 2, 0.30)
                vent = _vent_entity("hood", hx, hy, level)
                vent.params["layout_host"] = cab.id
                ents.append(vent)
                hob_at = (s.run, a, b)
            elif kind == "fridge":
                fr = library_entity("Ψυγειοκαταψύκτης 60", r, (a + b) / 2, None, level, "fridge")
                if fr is None:
                    fr = cabinet_entity("tall", r, a, b - a, level, "fridge", name="Ψυγείο (εντοιχιζόμενο)")
                ents.append(fr)
                fridge_at = (s.run, a, b)
            edge = b
    # Wall units over the base run: not over the hob, not in front of a window or door, short over the fridge.
    by_leg = {}
    for s in segs:
        lo = WALL_D if s.corner_before else s.s0
        hi = runs[s.run].length if s.corner_after else s.s1
        by_leg.setdefault((s.leg, s.run), []).append((lo, hi))
    for k in corners:
        i, j = legs[k][0], legs[k + 1][0]
        by_leg.setdefault((k, i), []).append((runs[i].length - CORNER, runs[i].length))
        by_leg.setdefault((k + 1, j), []).append((WALL_D, CORNER))
    for (_leg, i), spans in by_leg.items():
        r = runs[i]
        spans = _merge(spans)
        cuts = [(o.s0 - 0.05, o.s1 + 0.05) for o in r.openings if o.top > WALL_Z + 0.02 and o.sill < WALL_Z + WALL_H]
        if hob_at and hob_at[0] == i:
            cuts.append((hob_at[1], hob_at[2]))
        if fridge_at and fridge_at[0] == i:
            cuts.append((fridge_at[1], fridge_at[2]))
        for lo, hi in subtract(spans, cuts, 0.0):
            if hi - lo < 0.30 - 1e-9:
                continue
            x = lo
            for w in _fill(hi - lo, lo=0.30):
                ents.append(cabinet_entity("wall", r, x, w, level, "wall"))
                x += w
    if fridge_at:
        r = runs[fridge_at[0]]
        ents.append(cabinet_entity("wall", r, fridge_at[1], fridge_at[2] - fridge_at[1], level, "wall",
                                   name="Κρεμαστό πάνω από ψυγείο", height=FRIDGE_TOP_H, z=FRIDGE_TOP_Z, shelves=0))
    # What the proposal measured.
    base_len = sum(s.length for s in segs) + CORNER * len(corners)
    n_base = sum(1 for e in ents if e.kind == "cabinet" and e.params["cabinet_type"] != "wall")
    n_wall = sum(1 for e in ents if e.kind == "cabinet" and e.params["cabinet_type"] == "wall")
    notes.append(f"Πάγκος {fmt_m(base_len)} · {n_base} κάτω ντουλάπια, {n_wall} κρεμαστά" +
                 (f", {len(corners)} γωνιακό" if corners else ""))
    pts = {}
    for k, a, b, kind in items:
        pts[kind] = runs[segs[k].run].point((a + b) / 2, 0.65 if kind == "fridge" else BASE_D)
    if {"fridge", "sink", "hob"} <= set(pts):
        fs, sh, hf = math.dist(pts["fridge"], pts["sink"]), math.dist(pts["sink"], pts["hob"]), math.dist(pts["hob"], pts["fridge"])
        tri = fs + sh + hf
        ok = TRIANGLE[0] <= tri <= TRIANGLE[1]
        notes.append(f"Τρίγωνο εργασίας: {fs:.1f} + {sh:.1f} + {hf:.1f} = {tri:.1f} m".replace(".", ",") +
                     (" ✓" if ok else " ⚠ εκτός 4,0–7,9 m"))
    for k, a, b, kind in items:
        if kind == "sink":
            r = runs[segs[k].run]
            if any(o.s0 - 0.05 <= (a + b) / 2 <= o.s1 + 0.05 for o in r.windows() if o.sill >= LOW_SILL):
                notes.append("Νεροχύτης κάτω από το παράθυρο ✓")
        if kind == "hob":
            left, right = _counter(segs, items, k, a, -1), _counter(segs, items, k, b, 1)
            notes.append(f"Εστία: πάγκος {fmt_m(left)} / {fmt_m(right)} εκατέρωθεν")
    notes += list(RULES)
    return LayoutProposal("kitchen", ents, "", notes=notes, problems=problems, source=SOURCE)


def _merge(spans):
    spans = sorted(spans)
    out = []
    for lo, hi in spans:
        if out and lo <= out[-1][1] + 1e-6:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out
