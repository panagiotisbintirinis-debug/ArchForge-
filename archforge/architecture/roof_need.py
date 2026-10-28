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
    """Fraction (0..1) of ``polygon`` lying under the rooms of any storey above ``base_z``.

    Every storey above counts, not only the next one: in a split-level house (owner:
    Υπόγειο −2,70, Ισόγειο ±0,00, ημιόροφος +1,40) the basement lies under the half
    level, beside the ground floor — its ceiling is a slab, not a roof.
    """
    above = [z for z in _storeys(doc) if z > base_z + 0.5]
    if not above:
        return 0.0
    upper = []
    for z in above:
        try:
            upper += [[(float(p[0]), float(p[1])) for p in f.polygon] for f in doc.active_room_faces(z=z)]
        except Exception as exc:
            from archforge.core.notices import not_computed
            not_computed("roof.coverage", f"Στέγες: δεν αναγνωρίστηκαν οι χώροι του ορόφου {z:+.2f} — δεν είναι "
                         "γνωστό τι σκεπάζει από πάνω", exc=exc)
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


# Room uses that are open to the sky: never given a roof or terrace slab.
OPEN_AIR_USES = ("Πισίνα", "Αυλή", "Αίθριο")


def _known_coverage(doc, polygon, base_z):
    """``coverage``, or None when a storey above could not be read: then no roof is added or removed (Α3)."""
    from archforge.core.notices import collecting
    with collecting() as unknown:
        c = coverage(doc, polygon, base_z)
    return None if unknown else c


def _faces_or_said(doc, z, what):
    try:
        return doc.active_room_faces(z=z)
    except Exception as exc:
        from archforge.core.notices import not_computed
        not_computed("roof.storey_rooms", f"{what}: δεν αναγνωρίστηκαν οι χώροι του ορόφου {z:+.2f}, δεν ελέγχθηκε",
                     exc=exc)
        return []


def roof_plan(doc):
    """What "Fix roofs" would do: ``{"remove": [roof ids under a storey], "add": [room signatures without a roof]}``."""
    remove, roofed = [], set()
    for e in doc.entities.values():
        if e.kind != "room_roof":
            continue
        if e.params.get("scope") == "storey":
            # A storey roof follows the plan: it covers exactly the rooms that need it.
            from archforge.architecture.storey_slabs import storey_faces
            roofed.update(f.signature for f in storey_faces(doc, "room_roof", float(e.params["level_z"])))
            continue
        found = room_face_of(doc, e)
        if found is None:
            continue
        face, base_z = found
        roofed.add(face.signature)
        c = _known_coverage(doc, face.polygon, base_z)
        if c is not None and c >= COVERED:
            remove.append(e.id)
    add = []
    for z in _storeys(doc):
        faces = _faces_or_said(doc, z, "Στέγες")
        for face in faces:
            if face.signature in roofed or under_pitched_roof(doc, face.polygon, z):
                continue
            if doc.room_metadata(face.signature).get("use") in OPEN_AIR_USES:
                continue                                  # a pool or a courtyard stays open to the sky
            c = _known_coverage(doc, face.polygon, z)
            if c is not None and c < COVERED:
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
        faces = _faces_or_said(doc, z, "Οροφές σοφίτας")
        for face in faces:
            if face.signature in ceiled or not under_pitched_roof(doc, face.polygon, z):
                continue
            if coverage(doc, face.polygon, z) >= COVERED:
                continue                      # a storey above: its ceiling is that floor slab, not an attic
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
