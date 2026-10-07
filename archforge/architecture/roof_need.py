"""Where a roof is needed: only over the parts of a storey with nothing built above.

A room of a storey is covered when the rooms of the next storey up lie over
it.  Coverage is the fraction of the room's plan area (sampled on a 10 cm
grid) inside the rooms of the storey directly above.  A roof is needed when
less than half of the room is covered; a partly covered room is reported so
the user can decide.
"""
from __future__ import annotations

COVERED = 0.98          # a room this much under the storey above needs no roof; less: a terrace on the open part


def _inside(poly, x, y):
    hit = False
    for i in range(len(poly)):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def _storeys(doc):
    return sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall" and e.visible})


def coverage(doc, polygon, base_z, cell=0.10):
    """Fraction (0..1) of ``polygon`` lying under the rooms of the storey above ``base_z``."""
    above = [z for z in _storeys(doc) if z > base_z + 0.5]
    if not above:
        return 0.0
    try:
        upper = [[(float(p[0]), float(p[1])) for p in f.polygon] for f in doc.active_room_faces(z=above[0])]
    except Exception:
        upper = []
    if not upper:
        return 0.0
    poly = [(float(p[0]), float(p[1])) for p in polygon]
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    total = covered = 0
    y = min(ys) + cell / 2
    while y < max(ys):
        x = min(xs) + cell / 2
        while x < max(xs):
            if _inside(poly, x, y):
                total += 1
                if any(_inside(u, x, y) for u in upper):
                    covered += 1
            x += cell
        y += cell
    return covered / total if total else 0.0


def room_face_of(doc, entity):
    """(face, base_z) of a room-linked slab entity (room_roof, room_floor …), or None."""
    from archforge.architecture.rooms import find_room_face, find_room_face_by_id
    p = entity.params
    found = find_room_face_by_id(doc, p["room_id"]) if p.get("room_id") else None
    if found is None and p.get("room_signature"):
        found = find_room_face(doc, p["room_signature"])
    return found


def roof_needed(doc, signature):
    """(needed, coverage) for the room with ``signature``."""
    from archforge.architecture.rooms import find_room_face
    found = find_room_face(doc, signature)
    if found is None:
        return True, 0.0
    face, base_z = found
    c = coverage(doc, face.polygon, base_z)
    return c < COVERED, c


def under_pitched_roof(doc, polygon, base_z):
    """True when a timber roof spans the room (its eaves at or above the room's storey)."""
    from archforge.assistant.understanding import centroid
    cx, cy = centroid([(float(p[0]), float(p[1])) for p in polygon])
    for e in doc.entities.values():
        if e.kind != "pitched_roof":
            continue
        p = e.params
        if float(p["eave_z"]) > base_z + 0.5 and min(float(p["x0"]), float(p["x1"])) <= cx <= max(float(p["x0"]), float(p["x1"])) \
                and min(float(p["y0"]), float(p["y1"])) <= cy <= max(float(p["y0"]), float(p["y1"])):
            return True
    return False


def roof_plan(doc):
    """What "Fix roofs" would do: ``{"remove": [roof ids under a storey], "add": [room signatures without a roof]}``."""
    remove, roofed = [], set()
    for e in doc.entities.values():
        if e.kind != "room_roof":
            continue
        found = room_face_of(doc, e)
        if found is None:
            continue
        face, base_z = found
        roofed.add(face.signature)
        if coverage(doc, face.polygon, base_z) >= COVERED:
            remove.append(e.id)
    add = []
    for z in _storeys(doc):
        try:
            faces = doc.active_room_faces(z=z)
        except Exception:
            faces = []
        for face in faces:
            if face.signature in roofed or under_pitched_roof(doc, face.polygon, z):
                continue
            if coverage(doc, face.polygon, z) < COVERED:
                add.append(face.signature)
    return {"remove": remove, "add": add}


def attic_rooms(doc):
    """Rooms under a timber roof without a flat ceiling yet: ``[(face, base_z, room_id)]`` (attic candidates)."""
    from archforge.architecture.room_identity import room_id_for_signature
    from archforge.assistant.understanding import centroid, inside
    ceiled = set()
    for e in doc.entities.values():
        if e.kind == "room_ceiling":
            found = room_face_of(doc, e)
            if found is not None:
                ceiled.add(found[0].signature)
    joists = [(float(e.params["z"]), centroid([(float(q[0]), float(q[1])) for q in e.params["points"]]))
              for e in doc.entities.values() if e.kind == "ceiling_joists"]
    out = []
    for z in _storeys(doc):
        try:
            faces = doc.active_room_faces(z=z)
        except Exception:
            faces = []
        for face in faces:
            if face.signature in ceiled or not under_pitched_roof(doc, face.polygon, z):
                continue
            poly = [(float(p[0]), float(p[1])) for p in face.polygon]
            if any(abs(jz - z) < 0.05 and inside(poly, *c) for jz, c in joists):
                continue
            out.append((face, z, room_id_for_signature(doc, face.signature, z=z)))
    return out


def attic_ceiling_entities(doc, kind="slab", thickness=0.15):
    """Entities for a flat attic ceiling in every attic room: concrete slab or timber joists."""
    from archforge.core.model import Entity
    out = []
    for face, z, room_id in attic_rooms(doc):
        if kind == "joists":
            from archforge.assistant.suggestions import joists_entity
            out.append(joists_entity(face.polygon, z, name="Δοκίδες οροφής σοφίτας"))
            continue
        tops = [float(doc.get(w).params["z"]) + float(doc.get(w).params["height"]) for w in face.wall_ids if w in doc.entities]
        top = min(tops) if tops else z + 2.7
        params = {"room_signature": face.signature, "thickness": float(thickness), "offset_z": top - z - float(thickness)}
        if room_id is not None:
            params["room_id"] = room_id
        out.append(Entity("room_ceiling", params, name="Οροφή σοφίτας"))
    return out
