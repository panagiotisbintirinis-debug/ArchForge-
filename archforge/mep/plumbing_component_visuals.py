"""Presentation geometry for explicit plumbing_accessory entities.

Geometry here is symbolic/presentation-only unless a manufacturer product later
supplies dimensions.  The authoritative item is the plumbing_accessory entity.
"""
from __future__ import annotations


def plan_primitives(doc):
    from archforge.core.plan_scene import Primitive2D
    out = []
    for e in doc.entities.values():
        if e.kind != "plumbing_accessory" or not e.visible:
            continue
        p = e.params
        x, y = float(p.get("x", 0.0)), float(p.get("y", 0.0))
        r = 0.08
        # Diamond + short cross: readable but compact in a technical plan.
        out.append(Primitive2D(
            "polyline", ((x, y-r), (x+r, y), (x, y+r), (x-r, y), (x, y-r)),
            entity_id=e.id, role="plumbing-accessory",
            meta=(("accessory_type", str(p.get("accessory_type", ""))),),
        ))
        out.append(Primitive2D(
            "line", ((x-r*.55, y), (x+r*.55, y)), entity_id=e.id,
            role="plumbing-accessory",
            meta=(("accessory_type", str(p.get("accessory_type", ""))),),
        ))
    return out


def _box(cx, cy, cz, sx=.10, sy=.10, sz=.10):
    x0, x1 = cx-sx/2, cx+sx/2; y0, y1 = cy-sy/2, cy+sy/2; z0, z1 = cz-sz/2, cz+sz/2
    verts = [
        (x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
        (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1),
    ]
    tris = [
        (0,2,1),(0,3,2),(4,5,6),(4,6,7),
        (0,1,5),(0,5,4),(1,2,6),(1,6,5),
        (2,3,7),(2,7,6),(3,0,4),(3,4,7),
    ]
    return verts, tris


def scene_objects(doc):
    out = []
    for e in doc.entities.values():
        if e.kind != "plumbing_accessory" or not e.visible:
            continue
        p = e.params
        x, y, z = float(p.get("x", 0.0)), float(p.get("y", 0.0)), float(p.get("z", 0.0))
        verts, tris = _box(x, y, z + .05)
        out.append({
            "id": str(e.id),
            "render_part": f"plumbing-accessory:{e.id}",
            "kind": "plumbing_accessory",
            "layer": "mep",
            "vertices": [[float(a), float(b), float(c)] for a,b,c in verts],
            "triangles": [[int(a), int(b), int(c)] for a,b,c in tris],
            "surfaces": ["component"] * len(tris),
            "material": {"color": "#6b7280", "roughness": 0.38, "metalness": 0.55},
            "plumbing_meta": {
                "accessory_type": str(p.get("accessory_type", "")),
                "host_kind": str(p.get("host_kind", "")),
                "presentation_only": True,
            },
        })
    return out
