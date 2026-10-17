"""Derived plumbing presentation objects shared by 3D/UI.

The authoritative plumbing model remains the point set + route_plumbing().
Objects created here are disposable presentation geometry only.  They carry
technical metadata so the same derived manifold can be recognised in 3D, BOM
and owner/professional views.

The cabinet envelope used here is deliberately a DESIGN_DEFAULT presentation
symbol, not a manufacturer dimension.  A selected product may later replace it
with exact geometry and dimensions.
"""
from __future__ import annotations

from archforge.mep.plumbing import route_plumbing_cached


def _box_mesh(cx, cy, cz, width, depth, height):
    x0, x1 = cx - width / 2.0, cx + width / 2.0
    y0, y1 = cy - depth / 2.0, cy + depth / 2.0
    z0, z1 = cz - height / 2.0, cz + height / 2.0
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    t = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    return v, t


def manifold_scene_objects(doc) -> list[dict]:
    """One explicit scene object per derived manifold.

    The object is intentionally separate from the pipe mesh.  This lets the
    viewer recognise the manifold as a costable system component and gives us
    a stable render_part for later selection/product replacement.
    """
    routed = route_plumbing_cached(doc)
    out: list[dict] = []
    for index, manifold in enumerate(routed.get("manifolds", ())):
        system = str(manifold.get("system", "cold"))
        outlets = list(manifold.get("outlets", ()))
        n = len(outlets)

        # Presentation-only envelope.  Width follows outlet count so a 10-way
        # collector reads differently from a 2-way collector; these are NOT
        # manufacturer dimensions and are marked DESIGN_DEFAULT below.
        width = max(0.24, 0.14 + 0.055 * max(1, n))
        depth = 0.10
        height = 0.34
        z = float(manifold.get("z", 0.0)) + (0.50 if system == "cold" else 0.68)
        verts, tris = _box_mesh(float(manifold["x"]), float(manifold["y"]), z, width, depth, height)
        colour = "#2d6fb3" if system == "cold" else "#c73a2d"
        out.append({
            "id": "",
            "render_part": f"mep:manifold:{system}:{index}",
            "kind": "mep_manifold",
            "layer": "mep",
            "vertices": [[float(x), float(y), float(zv)] for x, y, zv in verts],
            "triangles": [[int(a), int(b), int(c)] for a, b, c in tris],
            "surfaces": ["cabinet"] * len(tris),
            "material": {"color": colour, "roughness": 0.42, "metalness": 0.18, "opacity": 0.86},
            "plumbing_meta": {
                "system": system,
                "outlet_count": n,
                "outlet_ids": outlets,
                "feed_mm": int(manifold.get("feed_mm", 0) or 0),
                "bom_code": f"plumbing.manifold.{system}.{n}way",
                "rule_status": "DESIGN_DEFAULT_PRESENTATION",
                "presentation_only": True,
            },
        })
    return out
