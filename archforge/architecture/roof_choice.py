"""Roof per room: a tiled roof on one room, a terrace (flat roof) on the next.

Choosing for a room:

* «Κεραμοσκεπή»: its flat roof (if any) goes; a tiled roof over the room
  (outer faces of its walls), the form chosen as for the automatic roofs
  (shed against a taller wall, hipped when near-square, else gable).
* «Ταράτσα»: a flat roof slab on the room.

Either way, a tiled roof that also covered the room is split: it goes, and
every other room it covered gets its own tiled roof, so their choice stays.
One command, one undo.
"""
from __future__ import annotations

from archforge.assistant.understanding import centroid, inside

CHOICES = {"tiled": "Κεραμοσκεπή", "terrace": "Ταράτσα (δώμα)"}


def _room_box(doc, room, z):
    walls = [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < .05]
    t = max((float(w.params.get("thickness", .2)) for w in walls), default=.2) / 2
    h = max((float(w.params.get("height", 2.7)) for w in walls), default=2.7)
    xs = [q[0] for q in room["polygon"]]; ys = [q[1] for q in room["polygon"]]
    return min(xs) - t, min(ys) - t, max(xs) + t, max(ys) + t, z + h


def _tiled_params(doc, room, z):
    from archforge.structure.timber_roof import _auto_form, default_params
    x0, y0, x1, y1, eave = _room_box(doc, room, z)
    params, reason = _auto_form(doc, dict(default_params(doc, z=z), x0=x0, y0=y0, x1=x1, y1=y1, eave_z=eave))
    return params, reason


def room_roof_command(doc, room, choice, z=None):
    """(command, message) setting the roof of ``room`` (a reading room) to 'tiled' or 'terrace'."""
    from archforge.assistant.understanding import read_drawing
    from archforge.core.commands import AddEntities, CompositeCommand, CreateRoomRoofs, DeleteEntities
    from archforge.core.model import Entity
    from archforge.structure.timber_roof import FORMS
    if choice not in CHOICES:
        raise ValueError(f"choice must be one of {', '.join(CHOICES)}")
    z = float(doc.work_plane.origin[2]) if z is None else float(z)
    storey = next((s for s in read_drawing(doc)["storeys"] if abs(s["z"] - z) < 1e-6), None)
    rooms = storey["rooms"] if storey else [room]
    cx, cy = centroid(room["polygon"])
    _x0, _y0, _x1, _y1, eave = _room_box(doc, room, z)
    remove, add, notes = [], [], []
    # Tiled roofs over this room: they go; the other rooms under them keep a tiled roof of their own.
    flat = {e.params.get("room_signature"): e for e in doc.entities.values() if e.kind == "room_roof"}
    for e in list(doc.entities.values()):
        if e.kind != "pitched_roof" or abs(float(e.params["eave_z"]) - eave) > .3:
            continue
        p = e.params
        box = [(float(p["x0"]), float(p["y0"])), (float(p["x1"]), float(p["y0"])), (float(p["x1"]), float(p["y1"])), (float(p["x0"]), float(p["y1"]))]
        if not inside(box, cx, cy):
            continue
        remove.append(e.id)
        for other in rooms:
            if other["signature"] == room["signature"] or other["signature"] in flat:
                continue
            if inside(box, *centroid(other["polygon"])):
                params, _r = _tiled_params(doc, other, z)
                add.append(Entity("pitched_roof", params, name=f"Κεραμοσκεπή {FORMS[params['roof_form']].lower()}"))
                notes.append(f"{other['name']}: κρατά κεραμοσκεπή")
    old_flat = flat.get(room["signature"])
    commands = []
    if choice == "tiled":
        if old_flat is not None:
            remove.append(old_flat.id)
        params, reason = _tiled_params(doc, room, z)
        add.append(Entity("pitched_roof", params, name=f"Κεραμοσκεπή {FORMS[params['roof_form']].lower()}"))
        notes.insert(0, f"{room['name']}: {reason}")
    else:
        if old_flat is None:
            commands.append(CreateRoomRoofs([room["signature"]], thickness=.20, roof_type="flat"))
        notes.insert(0, f"{room['name']}: ταράτσα (πλάκα δώματος)")
    if remove:
        commands.insert(0, DeleteEntities(remove))
    if add:
        commands.append(AddEntities(add))
    if not commands:
        return None, f"{room['name']}: έχει ήδη {CHOICES[choice].lower()}"
    return CompositeCommand(commands, f"Στέγη χώρου: {CHOICES[choice]}"), " · ".join(notes)
