"""Conduit map (χάρτης σωληνώσεων) — owner 18/10: from the cable lines and their destinations come the conduits, as a
construction map the trade can price (material + labour per size) and prefabricate.

A spiral conduit takes only so many conductors: with more, the friction and the pull deform the cables or cut them
at the bends.  Owner's table 18/10 (ΕΛΟΤ HD 60364-5-52 space factor 33–40 %, conduit makers' guides — KOUVIDIS,
Courbi), single-core H07V-U/R («ΝΥΑ») conductors in spiral / rigid plastic conduit:

* MAX_CONDUCTORS[Ø][mm²] — where the table gives a range the lower (safe) end is kept; a piece carrying mixed
  sections fits when Σ n/max ≤ 1 (each section takes its share of the space);
* more than MAX_BENDS 90° bends with no box between → one size bigger;
* a piece outside the building (ground, lean concrete — e.g. to the pool's equipment room): double-wall heavy duty
  conduit, at least Ø50 (OUTDOOR_MIN);
* low-voltage (UTP / bus) never shares a power conduit — they are routed apart (mep/low_voltage.py).

Circuits that travel the same way share a conduit while it fits in the largest size; each conduit is cut into pieces
box to box (panel, junction/pull/floor box, device), each with the smallest size that carries it.
"""
from __future__ import annotations

import math

SIZES = (16, 20, 25, 32)
# Owner's table 18/10 — maximum H07V conductors per conduit (lower end of each range).  Φ32 for 1,5 / 2,5 mm² is not
# in the table: taken in proportion to the 4 mm² column of the same row (7 vs 4 in Φ25) and marked so.
# 10 mm² (cooker line): the table's NYM-J 3×10 needs Φ32 → three single cores in Φ32.
MAX_CONDUCTORS = {16: {1.5: 3, 2.5: 2},
                  20: {1.5: 5, 2.5: 3, 4.0: 3, 6.0: 2},
                  25: {1.5: 8, 2.5: 6, 4.0: 4, 6.0: 3},
                  32: {1.5: 14, 2.5: 10, 4.0: 7, 6.0: 5, 10.0: 3}}
MAX_BENDS = 2                  # 90° bends between boxes; more → one size bigger
OUTDOOR_MIN = 50               # heavy duty double-wall conduit in the ground / outside the building
OUTDOOR_SIZES = (50, 63)
RULE = ("Πίνακας ιδιοκτήτη 18/10 (ΕΛΟΤ HD 60364-5-52 συντ. πλήρωσης 33–40 %, οδηγίες KOUVIDIS/Courbi): αγωγοί H07V ανά "
        "Φ — Φ16: 3×1,5 ή 2×2,5· Φ20: 5×1,5 / 3×2,5 / 3×4 / 2×6· Φ25: 8×1,5 / 6×2,5 / 4×4 / 3×6· Φ32: 7×4 / 5×6 "
        "(1,5/2,5 αναλογικά, 3×10 όπως NYM 3×10)· > 2 καμπύλες χωρίς κουτί → ένα μέγεθος πάνω· έξω/στο έδαφος διπλού "
        "δομήματος ≥ Φ50· ασθενή ποτέ με ισχυρά")


def fill(dn, conductors):
    """Share of the conduit taken by ``{mm²: n}`` (≤ 1 fits); a section the size cannot take → infinity."""
    table = MAX_CONDUCTORS[dn]
    total = 0.0
    for mm2, n in conductors.items():
        cap = table.get(mm2) or next((v for k, v in sorted(table.items()) if k >= mm2), 0)
        if not cap:
            return math.inf
        total += n / cap
    return total


def size_for(conductors, bends, outdoor=False):
    """Smallest Ø for ``{mm²: n}`` conductors with ``bends`` bends, else None (needs another conduit)."""
    if outdoor:
        return OUTDOOR_SIZES[0] if fill(32, conductors) <= 1 else OUTDOOR_SIZES[1]
    fits = [dn for dn in SIZES if fill(dn, conductors) <= 1 + 1e-9]
    if not fits:
        return None
    k = SIZES.index(fits[0]) + (1 if bends > MAX_BENDS else 0)
    return SIZES[k] if k < len(SIZES) else None


def _outdoor(doc, p):
    """A conduit point in the ground outside the building: not in a room, not in a wall, at floor level."""
    from archforge.mep.electrical import _floor_of
    from archforge.mep.heating_layout import _inside
    floor = _floor_of(doc, p[2])
    if p[2] - floor > 0.5:
        return False
    try:
        faces = doc.active_room_faces(z=floor)
    except Exception:                                     # noqa: BLE001
        faces = []
    if any(_inside(f.polygon, p[0], p[1]) for f in faces):
        return False
    for w in doc.entities.values():
        if w.kind == "wall" and abs(float(w.params.get("z", 0.0)) - floor) < 0.05:
            q = w.params
            ax, ay, bx, by = (float(q[k]) for k in ("x1", "y1", "x2", "y2"))
            L2 = (bx - ax) ** 2 + (by - ay) ** 2 or 1.0
            t = max(0.0, min(1.0, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / L2))
            if math.hypot(ax + (bx - ax) * t - p[0], ay + (by - ay) * t - p[1]) <= float(q["thickness"]) / 2 + 0.25:
                return False
    return True


def _key(p):
    return (round(p[0], 3), round(p[1], 3), round(p[2], 3))


def _direction(a, b):
    d = [b[i] - a[i] for i in range(3)]
    n = math.sqrt(sum(v * v for v in d)) or 1.0
    return tuple(round(v / n, 6) for v in d)


def conduit_map(doc, route=None):
    """``{"pieces": [...], "by_size": {Ø: m}, "conduits": n, "warnings": [...], "rule": RULE}``."""
    from archforge.mep.electrical import POINT_TYPES, electrical_points, mount_z, route_cables_cached
    route = route if route is not None else route_cables_cached(doc)
    circuits = {c["id"]: c for c in route["circuits"]}
    edges_of = {}
    for a, b, group, cid in route["runs"]:
        if group == "switch" and "switch_runs" in route:
            continue
        key = cid or f"switch:{_key(a)[:2]}"          # a switch leg is a line of its own (switch → its lights)
        edges_of.setdefault(key, set()).add(tuple(sorted((_key(a), _key(b)))))
    for a, b, sid in route.get("switch_runs", []):
        edges_of.setdefault(f"switch:{sid}", set()).add(tuple(sorted((_key(a), _key(b)))))
    if not edges_of:
        return {"pieces": [], "by_size": {}, "conduits": 0, "warnings": [], "rule": RULE, "split_boxes": [], "outdoor_m": 0.0}
    # Switch legs: join the pieces of one switch into one line (they start at the same switch box).
    def cond(cid):
        return {float(circuits[cid]["cable_mm2"]): 3} if cid in circuits else {1.5: 2}     # L N PE · switch: L + return

    def merged(*parts):
        out = {}
        for p in parts:
            for k, v in p.items():
                out[k] = out.get(k, 0) + v
        return out
    # Bundles: the longest lines first; each joins the bundle it shares most route with, while it fits in Φ32.
    bundles = []
    for cid in sorted(edges_of, key=lambda c: (-len(edges_of[c]), c)):
        best = None
        for b in bundles:
            if fill(SIZES[-1], merged(b["cond"], cond(cid))) > 1 + 1e-9:
                continue
            shared = len(edges_of[cid] & b["edges"])
            if shared and (best is None or shared > best[0]):
                best = (shared, b)
        if best is None:
            bundles.append({"lines": [cid], "edges": set(edges_of[cid]), "cond": cond(cid)})
        else:
            b = best[1]
            b["lines"].append(cid); b["edges"] |= edges_of[cid]; b["cond"] = merged(b["cond"], cond(cid))
    boxes = {_key((x, y, z)): kind for x, y, z, kind, _c in route["boxes"]}
    pts = electrical_points(doc)
    panel = next((e for e in pts if e.params["point_type"] == "panel"), None)

    def name_of(node):
        if node in boxes:
            return {"junction": "κουτί διακλάδωσης", "pull": "κουτί διέλευσης", "floor": "κουτί δαπέδου"}[boxes[node]]
        if panel is not None and math.hypot(node[0] - float(panel.params["x"]), node[1] - float(panel.params["y"])) < 0.3 \
                and abs(node[2] - mount_z(doc, panel.params)) < 0.3:
            return "πίνακας"
        near = [(math.hypot(node[0] - float(e.params["x"]), node[1] - float(e.params["y"])) + abs(node[2] - mount_z(doc, e.params)), e)
                for e in pts]
        d, e = min(near, key=lambda t: t[0]) if near else (9.9, None)
        if e is not None and d < 0.6:
            return e.name or POINT_TYPES[e.params["point_type"]][0]
        # Where a shared conduit parts (lines leave it) the cables need a box to come out: one per place.
        split.add(node)
        return "κουτί διακλάδωσης σωληνώσεων"
    pieces, warnings, split = [], [], set()
    for n, b in enumerate(bundles, 1):
        adj = {}
        lines_on = {}
        for cid in b["lines"]:
            for e in edges_of[cid]:
                lines_on.setdefault(e, set()).add(cid)
        for a_, b_ in lines_on:
            adj.setdefault(a_, set()).add(b_); adj.setdefault(b_, set()).add(a_)
        cut = {v for v, ns in adj.items() if len(ns) != 2 or v in boxes}
        # A change in the lines carried (a circuit leaves) also ends a piece.
        for v, ns in adj.items():
            if len(ns) == 2:
                e1, e2 = (tuple(sorted((v, u))) for u in ns)
                if lines_on[e1] != lines_on[e2]:
                    cut.add(v)
        seen, k = set(), 0
        for start in sorted(cut) or [next(iter(adj))]:
            for nxt in sorted(adj[start]):
                e0 = tuple(sorted((start, nxt)))
                if e0 in seen:
                    continue
                chain, prev, cur = [start, nxt], start, nxt
                seen.add(e0)
                while cur not in cut:
                    step = next(u for u in adj[cur] if u != prev)
                    seen.add(tuple(sorted((cur, step))))
                    prev, cur = cur, step
                    chain.append(cur)
                length = sum(math.dist(p, q) for p, q in zip(chain, chain[1:]))
                dirs = [_direction(p, q) for p, q in zip(chain, chain[1:])]
                bends = sum(1 for d1, d2 in zip(dirs, dirs[1:]) if d1 != d2)
                lines = sorted(lines_on[e0], key=lambda c: (len(c), c))
                mm2 = merged(*(cond(c) for c in lines))
                mid = chain[len(chain) // 2]
                outdoor = _outdoor(doc, mid)
                dn = size_for(mm2, bends, outdoor)
                count = 1
                if dn is None:
                    # More than Φ32 carries with these bends: a second conduit (or a pull box to cut the bends).
                    count = 2 if fill(SIZES[-1], mm2) <= 2 else math.ceil(fill(SIZES[-1], mm2))
                    dn = SIZES[-1]
                    warnings.append(f"Σωλήνωση Σ{n}: {len(lines)} γραμμές με {bends} καμπύλες δεν χωρούν σε έναν Φ32 — "
                                    f"{count} σωλήνες ή κουτί διέλευσης στη διαδρομή")
                k += 1
                pieces.append({"id": f"Σ{n}.{k}", "conduit": f"Σ{n}", "from": name_of(chain[0]), "to": name_of(chain[-1]),
                               "a": chain[0], "b": chain[-1], "points": chain, "length_m": round(length, 2), "dn": dn,
                               "count": count, "bends": bends, "outdoor": outdoor, "fill": round(fill(dn, mm2) if dn in MAX_CONDUCTORS else 0.0, 2),
                               "line_ids": lines,
                               "lines": [c if c in circuits else "επιστροφή διακόπτη" for c in lines],
                               "conductors": " + ".join(f"{v}×{s:g}".replace(".", ",") for s, v in sorted(mm2.items()))})
    by_size = {}
    for p in pieces:
        by_size[p["dn"]] = round(by_size.get(p["dn"], 0.0) + p["length_m"] * p["count"], 2)
    return {"pieces": pieces, "by_size": dict(sorted(by_size.items())), "conduits": len(bundles), "warnings": warnings, "rule": RULE,
            "split_boxes": sorted(split), "outdoor_m": round(sum(p["length_m"] * p["count"] for p in pieces if p["outdoor"]), 2)}
