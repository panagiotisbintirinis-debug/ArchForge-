"""Pergola: dragged as a rectangle in the plan, built from posts, beams and rafters.

Rules (stated so they can be checked):

* A side that runs along a wall of the storey (parallel, within 35 cm, over
  most of its length) is fixed to the wall with a ledger beam and has no
  posts, not even at its corners; every other side has posts at its corners and at most every 3 m.
* Beams on the four sides on top of the posts (or the ledger); rafters
  across the short direction every 50 cm on top of the beams.
* Timber (posts 12×12, beams 10×20, rafters 5×15 cm) or aluminium (posts
  10×10, beams 8×16, louvres 4×12 cm); height 2.60 m to the underside of
  the beams, from the storey floor (also on a roof terrace).
* Members are columns / beams with the role 'pergola': drawn in plan and
  3D, listed in the take-off, left out of the building's frame analysis.
"""
from __future__ import annotations

import math

MAX_POST_SPACING = 3.0
RAFTER_SPACING = 0.5
WALL_GAP = 0.35
SIZES = {"timber": {"post": .12, "beam": (.10, .20), "rafter": (.05, .15), "label": "ξύλινη"},
         "aluminium": {"post": .10, "beam": (.08, .16), "rafter": (.04, .12), "label": "αλουμινίου"}}


def _walls(doc, z):
    return [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < .05]


def attached_sides(doc, x0, y0, x1, y1, z):
    """Sides ('S', 'N', 'W', 'E') of the rectangle that run along a wall."""
    sides = {"S": ((x0, y0), (x1, y0)), "N": ((x0, y1), (x1, y1)), "W": ((x0, y0), (x0, y1)), "E": ((x1, y0), (x1, y1))}
    out = set()
    for name, ((ax, ay), (bx, by)) in sides.items():
        L = math.hypot(bx - ax, by - ay)
        horizontal = abs(by - ay) < 1e-9
        for w in _walls(doc, z):
            p = w.params
            wx1, wy1, wx2, wy2 = (float(p[k]) for k in ("x1", "y1", "x2", "y2"))
            t = float(p.get("thickness", .2)) / 2
            if horizontal and abs(wy1 - wy2) < .03 and abs(wy1 - ay) <= WALL_GAP + t:
                cover = min(max(wx1, wx2), max(ax, bx)) - max(min(wx1, wx2), min(ax, bx))
            elif not horizontal and abs(wx1 - wx2) < .03 and abs(wx1 - ax) <= WALL_GAP + t:
                cover = min(max(wy1, wy2), max(ay, by)) - max(min(wy1, wy2), min(ay, by))
            else:
                continue
            if cover >= .6 * L:
                out.add(name)
                break
    return out


def pergola_entities(doc, x1, y1, x2, y2, z=0.0, material="timber", height=2.6, level="Ground"):
    """Entities (posts, beams, rafters) and a report for a pergola over the dragged rectangle."""
    from archforge.core.model import Entity
    x0, x1_, y0, y1_ = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
    if x1_ - x0 < 1.0 or y1_ - y0 < 1.0:
        raise ValueError("Η πέργκολα θέλει τουλάχιστον 1 × 1 m — σύρε μεγαλύτερο ορθογώνιο")
    s = SIZES[material]
    cons = "timber" if material == "timber" else "aluminium"
    fixed = attached_sides(doc, x0, y0, x1_, y1_, z)
    beam_w, beam_h = s["beam"]; raf_w, raf_h = s["rafter"]
    top = z + height + beam_h                                     # top of the beams
    out = []

    def post(x, y):
        out.append(Entity("structural_column", {"x": x, "y": y, "z": z, "width": s["post"], "depth": s["post"],
                                                "height": height + beam_h, "rotation": 0.0, "role": "pergola",
                                                "construction": cons, "section": "rectangular", "base_level": level,
                                                "top_level": "Unassigned"}, name="Κολονάκι πέργκολας"))

    def beam(ax, ay, bx, by, w, h, ztop, name):
        out.append(Entity("structural_beam", {"x1": ax, "y1": ay, "x2": bx, "y2": by, "z": ztop - h, "width": w, "height": h,
                                              "role": "pergola", "construction": cons, "section": "rectangular",
                                              "level": level}, name=name))
    # Posts: corners and along the free sides.
    sides = {"S": ((x0, y0), (x1_, y0)), "N": ((x0, y1_), (x1_, y1_)), "W": ((x0, y0), (x0, y1_)), "E": ((x1_, y0), (x1_, y1_))}
    posts = set()
    for name, ((ax, ay), (bx, by)) in sides.items():
        if name in fixed:
            continue
        L = math.hypot(bx - ax, by - ay)
        n = max(1, math.ceil(L / MAX_POST_SPACING - 1e-9))
        for i in range(n + 1):
            posts.add((round(ax + (bx - ax) * i / n, 3), round(ay + (by - ay) * i / n, 3)))
    # A post on a side fixed to the wall is not needed: that end rests on the ledger.
    def on_fixed(x, y):
        return any((n in ("S", "N") and abs(y - sides[n][0][1]) < 1e-6) or (n in ("W", "E") and abs(x - sides[n][0][0]) < 1e-6)
                   for n in fixed)
    posts = {q for q in posts if not on_fixed(*q)}
    for x, y in sorted(posts):
        post(x, y)
    for name, ((ax, ay), (bx, by)) in sides.items():
        beam(ax, ay, bx, by, beam_w, beam_h, top, "Δοκός πέργκολας (στον τοίχο)" if name in fixed else "Δοκός πέργκολας")
    # Rafters across the short direction, on top of the beams.
    along_x = (x1_ - x0) >= (y1_ - y0)                           # rafters run across the short side
    span = (x1_ - x0) if along_x else (y1_ - y0)
    n = max(2, round(span / RAFTER_SPACING))
    for i in range(1, n):
        u = (x0 + (x1_ - x0) * i / n) if along_x else (y0 + (y1_ - y0) * i / n)
        if along_x:
            beam(u, y0, u, y1_, raf_w, raf_h, top + raf_h, "Τεγίδα πέργκολας")
        else:
            beam(x0, u, x1_, u, raf_w, raf_h, top + raf_h, "Τεγίδα πέργκολας")
    report = {"posts": len(posts), "beams": 4, "rafters": n - 1, "fixed": sorted(fixed), "area": (x1_ - x0) * (y1_ - y0),
              "label": s["label"]}
    return out, report
