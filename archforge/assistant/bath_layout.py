"""Bathroom fixtures along the walls of a room: the assistant's proposal.

WC, basin and a shower tray or a bathtub (the user's choice), each with its
back on a wall, placed by a small search over the free wall positions:
every fixture keeps its clear area in front of it, nothing stands in a door
opening or in the swing of its leaf, the shower is never under a window.
A guide line drawn on a wall marks the plumbing wall: WC and basin stay on
it.  Each fixture gets its water / drain point (``plumbing_point``), so the
supply and drainage networks derive from it as for a hand-placed point.

Rules (proposed values — Neufert / common European practice, e.g. DIN
18022 — not a code requirement):

* WC: axis ≥ 40 cm from a side wall or the next fixture, ≥ 60 cm clear in front;
* basin: ≥ 70 cm clear in front;
* shower tray / bathtub: ≥ 70 cm clear in front; shower not under a window;
* nothing in front of the door or in the swing of its leaf.
"""
from __future__ import annotations

import math

from archforge.assistant.room_layout import LayoutProposal, core_asset, obstacles, spec_legs
from archforge.assistant.room_walls import DOOR_MARGIN, fmt_m, inner_polygon, room_runs

WETS = {"shower": "Ντουζιέρα", "bathtub": "Μπανιέρα"}
FIXTURES = {
    # key: asset name, front clear (m), min side gap to walls / fixtures (m; WC: axis 40 cm), plumbing point
    "wc": ("Λεκάνη WC με καζανάκι", 0.60, None, "wc"),
    "basin": ("Νιπτήρας με έπιπλο 80", 0.70, 0.05, "basin"),
    "basin_small": ("Νιπτήρας με κολόνα 60", 0.70, 0.10, "basin"),
    "shower": ("Ντουζιέρα 90×90", 0.70, 0.0, "shower"),
    "bathtub": ("Μπανιέρα 170×75", 0.70, 0.0, "bathtub"),
}
WC_AXIS = 0.40
STEP = 0.05
RULES = (
    "Λεκάνη: άξονας ≥ 40 cm από πλαϊνό τοίχο ή είδος, ελεύθερο μπροστά ≥ 60 cm",
    "Νιπτήρας: ελεύθερο μπροστά ≥ 70 cm",
    "Ντουζιέρα / μπανιέρα: ελεύθερο μπροστά ≥ 70 cm· η ντουζιέρα όχι κάτω από παράθυρο",
    "Τίποτα μπροστά από την πόρτα ή μέσα στο άνοιγμα του φύλλου· πλάτη στον τοίχο",
)
SOURCE = "Προτεινόμενες τιμές — Neufert / συνήθης ευρωπαϊκή πρακτική (π.χ. DIN 18022), όχι κανονιστική απαίτηση"


def _rect(run, s0, s1, d0, d1):
    return [run.point(s0, d0), run.point(s1, d0), run.point(s1, d1), run.point(s0, d1)]


def _overlap(p, q):
    from archforge.kitchen.cabinets import _overlap as sat
    return sat(p, q, 0.005)


def _inside(poly, rect):
    from archforge.assistant.understanding import inside
    cx = sum(x for x, _y in rect) / 4
    cy = sum(y for _x, y in rect) / 4
    for x, y in rect:
        if not inside(poly, x + (cx - x) * 0.002, y + (cy - y) * 0.002):
            return False
    xs, ys = [x for x, _y in rect], [y for _x, y in rect]
    return not any(_overlap(rect, [(vx - 1e-3, vy - 1e-3), (vx + 1e-3, vy - 1e-3), (vx + 1e-3, vy + 1e-3), (vx - 1e-3, vy + 1e-3)])
                   and min(xs) + 0.01 < vx < max(xs) - 0.01 and min(ys) + 0.01 < vy < max(ys) - 0.01 for vx, vy in poly)


def _candidates(key, size, runs, poly, swings, stuff, guide, front_scale):
    """Every allowed position of one fixture: dicts with the run, s, footprint, clear area and score parts."""
    name, front, side, _pt = FIXTURES[key]
    w, d = size[0], size[1]
    front *= front_scale
    out = []
    for r in runs:
        if r.thickness <= 0 or r.length < w - 1e-6:
            continue
        side_gap = (WC_AXIS - w / 2) if key == "wc" else side
        xs = {round(side_gap, 4), round(r.length - w - side_gap, 4)}
        x = side_gap
        while x <= r.length - w - side_gap + 1e-9:
            xs.add(round(x, 4))
            x += STEP
        for s in sorted(xs):
            if s < side_gap - 1e-6 or s + w > r.length - side_gap + 1e-6:
                continue
            if any(s < o.s1 + DOOR_MARGIN and s + w > o.s0 - DOOR_MARGIN for o in r.doors()):
                continue
            if key == "shower" and any(s < o.s1 and s + w > o.s0 for o in r.windows()):
                continue
            foot = _rect(r, s, s + w, 0.0, d)
            cw = max(w, 0.60)
            mid = s + w / 2
            clear = _rect(r, mid - cw / 2, mid + cw / 2, d, d + front)
            body = _rect(r, s - side_gap, s + w + side_gap, 0.0, d) if side_gap > 0 else foot
            if not _inside(poly, foot) or not _inside(poly, clear):
                continue
            if any(_overlap(foot, z) for z in swings) or any(_overlap(foot, q) for q in stuff):
                continue
            in_guide = guide is None or any(i == r.index and lo - 0.05 <= s and s + w <= hi + 0.05 for i, lo, hi in guide)
            if guide is not None and key in ("wc", "basin", "basin_small") and not in_guide:
                continue
            score = 0.0 if in_guide else 1.0
            at_start, at_end = s < 0.02, s + w > r.length - 0.02
            if key in ("shower", "bathtub"):
                score -= 1.0 if (at_start or at_end) else 0.0
                score -= 0.2 if at_start else 0.0          # the open glass side faces the room
                if key == "bathtub" and r.length - w < 0.08:
                    score -= 1.5                            # wall to wall: the classic bath
            if key == "wc":
                axis = min(mid, r.length - mid)
                score += abs(axis - 0.45)
            out.append(dict(key=key, run=r.index, s=s, w=w, d=d, foot=foot, clear=clear, body=body, score=score))
    out.sort(key=lambda c: c["score"])
    return out


def _compatible(c, placed):
    for p in placed:
        if _overlap(c["foot"], p["foot"]) or _overlap(c["foot"], p["clear"]) or _overlap(p["foot"], c["clear"]):
            return False
        if _overlap(c["body"], p["foot"]) or _overlap(p["body"], c["foot"]):
            return False
    return True


def _door_distance(runs, c):
    r = runs[c["run"]]
    x, y = r.point(c["s"] + c["w"] / 2, c["d"] / 2)
    best = None
    for q in runs:
        for o in q.doors():
            dx, dy = q.point((o.s0 + o.s1) / 2, 0.0)
            dist = math.hypot(x - dx, y - dy)
            best = dist if best is None else min(best, dist)
    return best or 0.0


def solve(runs, poly, swings, stuff, keys, sizes, guide=None, front_scale=1.0, keep=8):
    """Complete placements of ``keys``, best first: ``[(score, [candidate…])]``."""
    cands = {k: _candidates(k, sizes[k], runs, poly, swings, stuff, guide, front_scale) for k in keys}
    found = []

    def walk(i, placed, score):
        if len(found) > 400:
            return
        if i == len(keys):
            used = {p["run"] for p in placed}
            total = score + 0.6 * (len(used) - 1)
            for p in placed:
                dd = _door_distance(runs, p)
                total += (-0.15 * dd) if p["key"] in ("shower", "bathtub", "wc") else 0.15 * dd
            found.append((round(total, 4), list(placed)))
            return
        n = 0
        for c in cands[keys[i]]:
            if _compatible(c, placed):
                walk(i + 1, placed + [c], score + c["score"])
                n += 1
                if n >= keep:
                    break
    walk(0, [], 0.0)
    found.sort(key=lambda f: f[0])
    out = []
    for score, placed in found:
        sig = [(p["run"], round(p["s"] / 0.3)) for p in placed]
        if any(sig == [(p["run"], round(p["s"] / 0.3)) for p in o[1]] for o in out):
            continue
        out.append((score, placed))
    return out


def plan_bath(doc, room, *, legs=None, options=None, variant=0, z=None, ignore=()):
    options = dict(options or {})
    level = float(doc.work_plane.origin[2]) if z is None else float(z)
    wet = options.get("wet", "shower")
    runs = room_runs(doc, room, level)
    poly = inner_polygon(runs)
    swings = []
    for r in runs:
        for o in r.doors():
            swings.append(_rect(r, o.s0 - DOOR_MARGIN, o.s1 + DOOR_MARGIN, 0.0, o.width + DOOR_MARGIN))
    stuff = [q for _e, q in obstacles(doc, level, ignore)]
    sizes = {}
    for k, (name, *_r) in FIXTURES.items():
        asset = core_asset(name)
        sizes[k] = asset["size"] if asset else (0.6, 0.6, 0.8)
    problems = []
    attempts = [([wet, "wc", "basin"], 1.0, None),
                ([wet, "wc", "basin_small"], 1.0, None)]
    if wet == "shower":
        attempts.append(([wet, "wc", "basin_small"], 1.0, (0.80, 0.80, sizes["shower"][2])))
    attempts += [([wet, "wc", "basin_small"], 0.75, None), (["wc", "basin_small"], 1.0, None)]
    sols, used = [], None
    for keys, scale, shower_size in attempts:
        sz = dict(sizes)
        if shower_size:
            sz["shower"] = shower_size
        sols = solve(runs, poly, swings, stuff, keys, sz, guide=legs, front_scale=scale)
        if sols:
            used = (keys, scale, shower_size, sz)
            break
    spec = {"kind": "bath", "options": options, "z": level, "point": list(room["centroid"])}
    stored, walls = spec_legs(runs, legs or [])
    spec.update(legs=stored, walls=walls or sorted({w for r in runs for w in r.wall_ids}))
    if not sols:
        return LayoutProposal("bath", [], "Μπάνιο — δεν χωράει", notes=list(RULES), source=SOURCE, spec=spec,
                              problems=["Ο χώρος δεν χωράει λεκάνη και νιπτήρα με τους ελεύθερους χώρους — μεγάλωσε τον χώρο ή μετακίνησε την πόρτα"])
    keys, scale, shower_size, sz = used
    if scale < 1.0:
        problems.append("Ελεύθερος χώρος μπροστά στα είδη μικρότερος από τον προτεινόμενο (¾)")
    if shower_size:
        problems.append("Ντουζιέρα 80×80 (η 90×90 δεν χωράει)")
    if wet not in keys:
        problems.append(f"Δεν χωράει {WETS[wet].lower()} με ελεύθερο 70 cm μπροστά")
    if "basin_small" in keys and "basin" not in keys:
        problems.append("Νιπτήρας με κολόνα 60 (ο νιπτήρας με έπιπλο 80 δεν χωράει)")
    v = variant % len(sols)
    _score, placed = sols[v]
    ents, notes = [], []
    from archforge.core.model import Entity
    for c in placed:
        name, front, _side, pt = FIXTURES[c["key"]]
        r = runs[c["run"]]
        asset = core_asset(name)
        w, d = c["w"], c["d"]
        h = sz[c["key"]][2]
        x, y = r.point(c["s"] + w / 2, d / 2)
        role = "basin" if c["key"].startswith("basin") else c["key"]
        params = {"x": x, "y": y, "z": level, "rotation": r.rotation, "width": float(w), "depth": float(d),
                  "height": float(h), "uniform": 0.0 if (c["key"] == "shower" and shower_size) else 1.0,
                  "asset": asset["id"] if asset else "missing", "layout_role": role}
        if c["key"] == "shower" and shower_size:
            name = f"Ντουζιέρα {w * 100:.0f}×{d * 100:.0f}"
        fixture = Entity("library_object", params, name=name)
        ents.append(fixture)
        from archforge.assistant.room_layout import point_entity
        ents.append(point_entity(pt, r, c["s"] + w / 2, level, fixture))
        if c["key"] == "wc":
            notes.append(f"Λεκάνη: άξονας {fmt_m(min(c['s'] + w / 2, r.length - c['s'] - w / 2))} από τον πλαϊνό τοίχο, "
                         f"ελεύθερο μπροστά ≥ {fmt_m(front * scale)}")
    notes.append(f"{len(placed)} είδη σε {len({c['run'] for c in placed})} τοίχο(ους) · σημεία νερού/αποχέτευσης για καθένα")
    notes += list(RULES)
    proposal = LayoutProposal("bath", ents, "", notes=notes, problems=problems, source=SOURCE, spec=spec)
    spec["variant"] = v
    proposal.legs, proposal.variant, proposal.variants = list(legs or []), v, len(sols)
    proposal.label = f"Μπάνιο με {WETS[wet].lower()} · παραλλαγή {v + 1}/{len(sols)}"
    return proposal
