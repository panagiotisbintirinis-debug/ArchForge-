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
FILL_TOGETHER = 0.85            # rooms must fill this share of their outline to share one roof (as the automatic roofs)


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def uncovered_lower_rooms(doc):
    """Signatures of lower storeys' rooms with no storey above and no roof yet (they get a terrace slab)."""
    from archforge.architecture.roof_need import roof_plan
    storeys = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"})
    lower = {f.signature for z in storeys[:-1] for f in doc.active_room_faces(z=z)}
    return [s for s in roof_plan(doc)["add"] if s in lower]


def _room_box(doc, room, z):
    walls = [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < .05]
    t = max((float(w.params.get("thickness", .2)) for w in walls), default=.2) / 2
    h = max((float(w.params.get("height", 2.7)) for w in walls), default=2.7)
    xs = [q[0] for q in room["polygon"]]; ys = [q[1] for q in room["polygon"]]
    return min(xs) - t, min(ys) - t, max(xs) + t, max(ys) + t, z + h


def _tiled_params(doc, room, z):
    from archforge.structure.timber_roof import _auto_form, default_params
    x0, y0, x1, y1, eave = _room_box(doc, room, z)
    from archforge.structure.timber_roof import wall_sides
    params, reason = _auto_form(doc, dict(default_params(doc, z=z), x0=x0, y0=y0, x1=x1, y1=y1, eave_z=eave))
    return dict(params, gables=wall_sides(doc, params, z=z)), reason


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


def _rectangles(rooms):
    """Axis-aligned rectangles that together cover exactly the rooms, largest first (an L → body + wing).

    ``[]`` when a room is not axis-aligned (then each room keeps its own roof)."""
    for r in rooms:
        poly = r["polygon"]
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if abs(a[0] - b[0]) > 1e-3 and abs(a[1] - b[1]) > 1e-3:
                return []
    xs = sorted({round(q[0], 3) for r in rooms for q in r["polygon"]})
    ys = sorted({round(q[1], 3) for r in rooms for q in r["polygon"]})
    filled = {(i, j) for i in range(len(xs) - 1) for j in range(len(ys) - 1)
              if any(inside(r["polygon"], (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2) for r in rooms)}
    out = []
    while filled:
        best = None
        for i0, j0 in sorted(filled):
            i1 = i0
            while (i1 + 1, j0) in filled:
                i1 += 1
            for i_end in range(i0, i1 + 1):           # every width from i0, then as tall as it stays full
                j1 = j0
                while all((i, j1 + 1) in filled for i in range(i0, i_end + 1)):
                    j1 += 1
                area = (xs[i_end + 1] - xs[i0]) * (ys[j1 + 1] - ys[j0])
                if best is None or area > best[0] + 1e-9:
                    best = (area, i0, j0, i_end, j1)
        _a, i0, j0, i1, j1 = best
        filled -= {(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)}
        out.append([(xs[i0], ys[j0]), (xs[i1 + 1], ys[j0]), (xs[i1 + 1], ys[j1 + 1]), (xs[i0], ys[j1 + 1])])
    return out


def form_roofs(doc, form, z):
    """Tiled roofs of the chosen form over the storey at ``z`` — never over a room chosen as terrace.

    No terrace: one roof over the whole storey (as before).  With terraces: one
    roof over the other rooms together when their outline holds no terrace,
    else one roof per room.  Returns ``[params]``.
    """
    from archforge.assistant.understanding import read_drawing
    from archforge.structure.timber_roof import default_params, wall_sides
    storey = next((s for s in read_drawing(doc)["storeys"] if abs(s["z"] - z) < 1e-6), None)
    terraces = {e.params.get("room_signature") for e in doc.entities.values()
                if e.kind == "room_roof" and str(e.params.get("roof_type", "flat")) == "flat"}
    from archforge.architecture.roof_need import OPEN_AIR_USES
    rooms = storey["rooms"] if storey else []
    # A pool, yard or atrium stays open to the sky: no tiled roof over it, as for the terrace slabs.
    open_air = {r["signature"] for r in rooms if doc.room_metadata(r["signature"]).get("use") in OPEN_AIR_USES}
    flat_rooms = [r for r in rooms if r["signature"] in terraces or r["signature"] in open_air]
    others = [r for r in rooms if r not in flat_rooms]
    if rooms and not others:
        raise ValueError("Όλοι οι χώροι του ορόφου έχουν ταράτσα — Στέγη → «Κεραμοσκεπή σε χώρο» για να αλλάξεις κάποιον")
    if not others:
        params = default_params(doc, z=z, form=form)
        return [dict(params, gables=wall_sides(doc, params, z=z))]
    xs = [q[0] for r in others for q in r["polygon"]]; ys = [q[1] for r in others for q in r["polygon"]]
    union = [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]
    box_area = (max(xs) - min(xs)) * (max(ys) - min(ys))
    fill = sum(_area(r["polygon"]) for r in others) / box_area if box_area > 0 else 0.0
    # One roof over the rooms together only when they fill their outline (a rectangle, not an L / T)
    # and no terrace lies inside it; else one roof per room — never a roof over empty space.
    together = fill >= FILL_TOGETHER and not any(inside(union, *centroid(r["polygon"])) for r in flat_rooms)
    if together and not flat_rooms:
        params = default_params(doc, z=z, form=form)
        return [dict(params, gables=wall_sides(doc, params, z=z))]
    if together:
        groups = [[{"polygon": union, "signature": "", "name": ""}]]
    else:
        # An L / T: one roof per rectangle of the plan (body + wing), not one per room — a roof per room left
        # every inner wall on a roof's edge, so none went up to the roof, and hips stood inside the rooms.
        rects = _rectangles(others)
        groups = [[{"polygon": q, "signature": "", "name": ""}] for q in rects] if rects else [[r] for r in others]
    out = []
    for (room,) in groups:
        params, _reason = _tiled_params(doc, room, z)
        params = dict(params, roof_form=form)
        params["gables"] = wall_sides(doc, params, z=z)
        out.append(params)
    return out
