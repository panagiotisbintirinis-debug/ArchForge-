"""Drawing-only topology helpers for the plumbing technical plan.

These helpers never change routing, quantities or engineering decisions.  They
turn the already-derived plumbing route into presentation metadata so a reader
can visually follow bends, branches and vertical continuations.
"""
from __future__ import annotations

import math


def _same_plane(a, b, z, tolerance=1e-6):
    return abs(float(a[2]) - float(b[2])) <= tolerance and abs(float(a[2]) - float(z)) <= tolerance


def _logical_endpoint(point, a, b, network, system_key, hot_offset):
    """Undo the branched hot-water display offset for node matching only.

    The routing coordinates remain untouched.  Manifold home-runs use additional
    per-run offsets, so they are deliberately not reverse-engineered here.
    """
    x, y = float(point[0]), float(point[1])
    if network != "hot" or system_key == "manifold" or not hot_offset:
        return (x, y)
    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])
    length = math.hypot(dx, dy)
    if length <= 1e-12:
        return (x, y)
    ox = -dy / length * float(hot_offset)
    oy = dx / length * float(hot_offset)
    return (x - ox, y - oy)


def _key(point, digits=5):
    return (round(float(point[0]), digits), round(float(point[1]), digits))


def technical_plan_topology(routed, level_z, screed, hot_offset):
    """Return drawing-only bridges, junctions and riser markers.

    ``bridges`` join display-offset pieces that belong to the same logical node.
    ``junctions`` mark true plan nodes with three or more connected runs.
    ``risers`` mark vertical pipe segments crossing the active plan plane.
    """
    plane_z = float(level_z) + float(screed)
    system_key = str(routed.get("report", {}).get("system", ""))
    bridges = []
    junctions = []
    risers = []

    for network in ("cold", "hot"):
        nodes = {}
        for a, b, diameter in routed.get(network, ()):
            a = tuple(float(v) for v in a)
            b = tuple(float(v) for v in b)
            if _same_plane(a, b, plane_z):
                for displayed, other in ((a, b), (b, a)):
                    logical = _logical_endpoint(displayed, a, b, network, system_key, hot_offset)
                    nodes.setdefault(_key(logical), []).append({
                        "display": (displayed[0], displayed[1]),
                        "diameter": int(diameter),
                    })
                continue

            # A vertical segment that intersects the active screed plane is a
            # continuation/riser in plan.  It is not a horizontal break.
            if abs(a[0] - b[0]) <= 1e-9 and abs(a[1] - b[1]) <= 1e-9:
                lo, hi = sorted((a[2], b[2]))
                if lo - 1e-6 <= plane_z <= hi + 1e-6 and hi - lo > 1e-6:
                    direction = "up" if max(a[2], b[2]) > plane_z + 1e-6 else "down"
                    risers.append({
                        "network": network,
                        "point": (a[0], a[1]),
                        "diameter": int(diameter),
                        "direction": direction,
                    })

        for logical_key, entries in nodes.items():
            if len(entries) < 2:
                continue
            unique = []
            for entry in entries:
                p = entry["display"]
                if not any(math.dist(p, q) <= 1e-7 for q in unique):
                    unique.append(p)
            if not unique:
                continue
            cx = sum(p[0] for p in unique) / len(unique)
            cy = sum(p[1] for p in unique) / len(unique)
            centre = (cx, cy)

            # For branched hot water the display offset changes direction at a
            # bend, producing visible gaps.  Join only endpoints proven to share
            # the same reconstructed logical node.  Never do proximity guessing.
            if len(unique) > 1 and system_key != "manifold":
                for p in unique:
                    if math.dist(p, centre) > 1e-7:
                        bridges.append({"network": network, "a": p, "b": centre})

            # Three or more incident runs are a true branch/junction.  Degree is
            # based on route topology, not screen proximity.
            if len(entries) >= 3:
                junctions.append({
                    "network": network,
                    "point": centre,
                    "logical_point": logical_key,
                })

    return {"bridges": bridges, "junctions": junctions, "risers": risers}
