"""Mechanisms from the UI (owner 21/10: «Μηχανικά — η μηχανή υπάρχει, κανένα εργαλείο»).

A ``mechanical_part`` is a box whose (x, y, z) is its corner and ``rotation`` turns it about that
corner (geometry/mesh.py ``_box_mesh``, kinematics ``base_part_matrix``).  A joint moves the second
part (child) relative to the first (parent); anchor and axis are in the rest/world frame.

``default_joint`` picks what a person would expect without typing vectors:

* Στροφή (revolute, μεντεσές): vertical axis on the child's corner nearest the parent — a door leaf
  or a flap hinged on the frame it touches; 0…90°.
* Ολίσθηση (prismatic): along the line parent → child, 0 … the child's own length on that line —
  a drawer or a sliding leaf runs out by its own size.
* Σταθερή (fixed): rigidly attached (follows the parent's motion).
"""
from __future__ import annotations

import math

JOINT_LABELS = {"revolute": "Στροφή (μεντεσές)", "prismatic": "Ολίσθηση (συρτάρι / συρόμενο)", "fixed": "Σταθερή"}
UNITS = {"revolute": "°", "prismatic": "m", "fixed": ""}


def part_params(cx, cy, z, width, depth, height, rotation=0.0):
    """A part centred on (cx, cy): its corner goes half a size back (rotation about the corner)."""
    a = math.radians(float(rotation)); c, s = math.cos(a), math.sin(a)
    hw, hd = float(width) / 2.0, float(depth) / 2.0
    return {"x": float(cx) - (c * hw - s * hd), "y": float(cy) - (s * hw + c * hd), "z": float(z),
            "width": float(width), "depth": float(depth), "height": float(height), "rotation": float(rotation)}


def corners(params):
    """Plan corners of the part at rest (corner origin, rotation about it)."""
    a = math.radians(float(params.get("rotation", 0.0))); c, s = math.cos(a), math.sin(a)
    x, y, w, d = (float(params[k]) for k in ("x", "y", "width", "depth"))
    return [(x + c * u - s * v, y + s * u + c * v) for u, v in ((0, 0), (w, 0), (w, d), (0, d))]


def centre(params):
    pts = corners(params)
    return (sum(p[0] for p in pts) / 4.0, sum(p[1] for p in pts) / 4.0)


def default_joint(parent, child, joint_type):
    """Joint params of ``joint_type`` between parent/child part entities (see module doc)."""
    pc, cc = centre(parent.params), centre(child.params)
    z = float(child.params["z"])
    base = {"joint_type": joint_type, "parent_part": parent.id, "child_part": child.id, "anchor": [cc[0], cc[1], z], "axis": [0.0, 0.0, 1.0],
            "min_value": 0.0, "max_value": 0.0, "value": 0.0}
    if joint_type == "revolute":
        hinge = min(corners(child.params), key=lambda q: math.dist(q, pc))
        base.update(anchor=[hinge[0], hinge[1], z], min_value=0.0, max_value=90.0)
    elif joint_type == "prismatic":
        dx, dy = cc[0] - pc[0], cc[1] - pc[1]
        n = math.hypot(dx, dy)
        ux, uy = (dx / n, dy / n) if n > 1e-9 else (1.0, 0.0)
        pts = corners(child.params)
        reach = max(p[0] * ux + p[1] * uy for p in pts) - min(p[0] * ux + p[1] * uy for p in pts)
        base.update(axis=[ux, uy, 0.0], min_value=0.0, max_value=round(reach, 4))
    elif joint_type != "fixed":
        raise ValueError(f"άγνωστος τύπος άρθρωσης: {joint_type}")
    return base


def posed_corners(doc):
    """``{part_id: plan corners}`` at the joints' current values (rest pose when the tree is invalid)."""
    from archforge.geometry.plan import _mechanical_transforms
    parts = {eid: e for eid, e in doc.entities.items() if e.kind == "mechanical_part"}
    if not parts:
        return {}
    try:
        transforms = _mechanical_transforms(doc, {})
    except ValueError as exc:
        from archforge.core.notices import not_computed
        not_computed("kinematics.pose", "Μηχανισμός: μη έγκυρη κινηματική — εμφανίζεται η θέση ηρεμίας", exc=exc)
        return {eid: corners(e.params) for eid, e in parts.items()}
    out = {}
    for eid, e in parts.items():
        m = transforms[eid]
        w, d = float(e.params["width"]), float(e.params["depth"])
        out[eid] = [(m[0][0] * u + m[0][1] * v + m[0][3], m[1][0] * u + m[1][1] * v + m[1][3])
                    for u, v in ((0, 0), (w, 0), (w, d), (0, d))]
    return out
