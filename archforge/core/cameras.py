"""Saved cameras («Κάμερες»): where the human stands and where they look.

A ``camera`` entity is a view preference, not part of the building: it never
counts in quantities, rooms or slabs and has no 3D geometry (geometry/plan.py
treats it as a relationship node).  It belongs to one storey and is saved with
the project; placing, moving, turning and deleting it are ordinary commands
(one undo each), so the plan, the camera list and the 3D view share one truth.

Params (all plain numbers):

* ``x``, ``y``      — eye position in the plan (m)
* ``level_z``       — floor of the storey it belongs to (m)
* ``height``        — eye height above that floor (default 1,60 m)
* ``heading``       — where it looks in the plan, degrees (0 = +X / east, 90 = +Y / north)
* ``pitch``         — look up (+) / down (−), degrees
* ``fov``           — horizontal angle of view, degrees (default 60°); the plan
                      cone shows exactly this angle, so what the cone covers is
                      what the 3D view shows from side to side.
"""
from __future__ import annotations

import math

from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity

KIND = "camera"
DEFAULT_HEIGHT = 1.60
DEFAULT_FOV = 60.0
FOV_RANGE = (20.0, 120.0)
PITCH_RANGE = (-80.0, 80.0)
CONE_LENGTH = 2.6          # m: how far the view cone reaches in the plan (a drawing aid)
NAME_PREFIX = "Κάμερα"


def is_camera(entity):
    return entity is not None and entity.kind == KIND


def cameras(doc):
    """Cameras of the project, in the order they were made."""
    return [e for e in doc.entities.values() if e.kind == KIND]


def next_camera_name(doc):
    used = {str(e.name) for e in cameras(doc)}
    n = 1
    while f"{NAME_PREFIX} {n}" in used:
        n += 1
    return f"{NAME_PREFIX} {n}"


def storey_of(doc, z):
    """Floor elevation of the storey at or below ``z`` (lowest storey otherwise)."""
    levels = sorted(float(v) for v in (getattr(doc, "levels", None) or {}).values()) or [0.0]
    below = [v for v in levels if v <= float(z) + 1e-4]
    return below[-1] if below else levels[0]


def storey_name(doc, level_z):
    for name, z in (getattr(doc, "levels", None) or {}).items():
        if abs(float(z) - float(level_z)) <= 1e-4:
            return str(name)
    return None


def heading_to(x, y, tx, ty):
    """Plan heading (degrees) from (x, y) towards (tx, ty), or None when too close."""
    dx, dy = float(tx) - float(x), float(ty) - float(y)
    if math.hypot(dx, dy) < 0.05:
        return None
    return math.degrees(math.atan2(dy, dx)) % 360.0


def make_params(x, y, heading, level_z=0.0, height=DEFAULT_HEIGHT, fov=DEFAULT_FOV, pitch=0.0):
    return {"x": float(x), "y": float(y), "level_z": float(level_z), "height": float(height),
            "heading": float(heading) % 360.0, "pitch": float(pitch), "fov": float(fov)}


def make_camera(doc, x, y, heading, level_z=None, **extra):
    """A new camera entity on the active storey (not yet added)."""
    if level_z is None:
        level_z = float(doc.work_plane.origin[2])
    return Entity(KIND, make_params(x, y, heading, level_z, **extra), name=next_camera_name(doc))


def add_camera_command(doc, x, y, heading, level_z=None, **extra):
    entity = make_camera(doc, x, y, heading, level_z, **extra)
    return AddEntity(entity), entity


def eye_z(p):
    return float(p.get("level_z", 0.0)) + float(p.get("height", DEFAULT_HEIGHT))


def direction(p):
    """Unit view direction (dx, dy, dz) from heading and pitch."""
    h = math.radians(float(p.get("heading", 0.0)))
    t = math.radians(float(p.get("pitch", 0.0)))
    return math.cos(h) * math.cos(t), math.sin(h) * math.cos(t), math.sin(t)


def target(p, distance=2.0):
    dx, dy, dz = direction(p)
    return float(p["x"]) + dx * distance, float(p["y"]) + dy * distance, eye_z(p) + dz * distance


def aim_point(p, length=CONE_LENGTH):
    """Plan point at the tip of the cone (the handle that turns the camera)."""
    h = math.radians(float(p.get("heading", 0.0)))
    return float(p["x"]) + math.cos(h) * length, float(p["y"]) + math.sin(h) * length


def cone(p, length=CONE_LENGTH, steps=12):
    """Plan polygon of the view cone: the eye, then the arc from one edge of the view to the other."""
    h = float(p.get("heading", 0.0))
    half = float(p.get("fov", DEFAULT_FOV)) / 2.0
    x, y = float(p["x"]), float(p["y"])
    pts = [(x, y)]
    for k in range(steps + 1):
        a = math.radians(h - half + 2.0 * half * k / steps)
        pts.append((x + math.cos(a) * length, y + math.sin(a) * length))
    return pts


def body(p, size=0.34):
    """Plan outline of the camera symbol: a small box behind the eye and the lens in front."""
    h = math.radians(float(p.get("heading", 0.0)))
    c, s = math.cos(h), math.sin(h)
    x, y = float(p["x"]), float(p["y"])

    def w(u, v):          # u along the view, v to the left
        return x + c * u - s * v, y + s * u + c * v
    L, W = size, size * 0.62
    box = [w(-L, -W / 2), w(-0.02, -W / 2), w(-0.02, W / 2), w(-L, W / 2)]
    lens = [w(-0.02, -W * 0.22), w(size * 0.32, -W * 0.48), w(size * 0.32, W * 0.48), w(-0.02, W * 0.22)]
    return box, lens


def view_payload(entity):
    """What the 3D view needs to stand at the camera (the eye-level view line, pbr_viewport)."""
    p = entity.params
    dx, dy, _dz = direction(dict(p, pitch=0.0))
    x, y = float(p["x"]), float(p["y"])
    return {"kind": "camera", "x1": x, "y1": y, "x2": x + dx, "y2": y + dy,
            "z": float(p.get("level_z", 0.0)), "eye": eye_z(p), "pitch": float(p.get("pitch", 0.0)),
            "hfov": float(p.get("fov", DEFAULT_FOV)), "camera_id": entity.id, "name": entity.name}


def params_from_view(doc, state):
    """Camera params from the 3D view as it is now (``{"position", "target", "hfov"}``)."""
    px, py, pz = (float(v) for v in state["position"])
    tx, ty, tz = (float(v) for v in state["target"])
    dx, dy, dz = tx - px, ty - py, tz - pz
    horizontal = math.hypot(dx, dy)
    if horizontal < 1e-6 and abs(dz) < 1e-6:
        raise ValueError("η τρέχουσα προβολή δεν έχει κατεύθυνση")
    heading = math.degrees(math.atan2(dy, dx)) % 360.0 if horizontal > 1e-6 else 90.0
    pitch = max(PITCH_RANGE[0], min(PITCH_RANGE[1], math.degrees(math.atan2(dz, horizontal))))
    level = storey_of(doc, pz)
    fov = max(FOV_RANGE[0], min(FOV_RANGE[1], float(state.get("hfov") or DEFAULT_FOV)))
    return make_params(px, py, heading, level, height=max(0.05, pz - level), fov=round(fov, 1), pitch=round(pitch, 1))


def camera_from_view(doc, state):
    return Entity(KIND, params_from_view(doc, state), name=next_camera_name(doc))


# --- commands (one undo each) -------------------------------------------------------------------

def move_command(doc, eid, dx, dy):
    p = doc.get(eid).params
    return UpdateEntity(eid, {"x": float(p["x"]) + float(dx), "y": float(p["y"]) + float(dy)})


def aim_command(doc, eid, tx, ty):
    """Turn the camera to look at plan point (tx, ty); None when the point is on the eye."""
    p = doc.get(eid).params
    h = heading_to(p["x"], p["y"], tx, ty)
    return None if h is None else UpdateEntity(eid, {"heading": h})


def rotate_command(doc, eid, angle):
    p = doc.get(eid).params
    return UpdateEntity(eid, {"heading": (float(p.get("heading", 0.0)) + float(angle)) % 360.0})


# --- plan drawing (plain primitives; ui/camera_tool.py paints them) ----------------------------

def plan_body(p, eid=""):
    """The camera body: what the mouse picks in the plan."""
    from archforge.core.plan_scene import Primitive2D
    return Primitive2D("polygon", tuple(body(p)[0]), entity_id=eid, role="camera", meta=(("part", "body"),))


def plan_extras(p, name, eid="", selected=False, ghost=False):
    """View cone (exactly the horizontal angle the 3D shows), its axis, the lens and the name."""
    from archforge.core.plan_scene import Primitive2D
    flags = (("camera", eid), ("selected", bool(selected)), ("ghost", bool(ghost)))
    ax, ay = aim_point(p)
    x, y = float(p["x"]), float(p["y"])
    return [
        Primitive2D("polygon", tuple(cone(p)), role="camera-cone", meta=flags),
        Primitive2D("polyline", ((x, y), (ax, ay)), role="camera-cone", meta=flags + (("axis", True),)),
        Primitive2D("polygon", tuple(body(p)[1]), entity_id=eid, role="camera", meta=(("part", "lens"), ("ghost", bool(ghost)))),
        Primitive2D("label", ((x, y - 0.30),), entity_id=eid, role="camera-label",
                    meta=(("text", name or NAME_PREFIX), ("align", (0.5, 0.0)), ("ghost", bool(ghost)))),
    ]
