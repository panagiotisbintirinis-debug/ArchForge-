"""Project tree derived from the Document: only things that actually exist.

``project_outline(doc)`` returns plain nested nodes so the tree widget, tests
and any other view share one truth:

    {"label": str, "entity_id": str|None, "level": str|None, "children": [...]}

Storeys come from ``doc.levels`` (sorted by elevation), rooms from the room
topology of each storey, and every entity is listed once under its storey and
category.  Empty categories are omitted.
"""
from __future__ import annotations

CATEGORIES = (
    ("Τοίχοι", ("wall",)),
    ("Ανοίγματα", ("door", "window", "opening")),
    ("Σκάλες & ράμπες", ("stair", "ramp")),
    ("Δομικά", ("structural_column", "structural_beam", "structural_support", "structural_load")),
    ("Πλάκες & στέγες", ("floor", "room_floor", "room_ceiling", "room_foundation", "room_roof")),
    ("Ντουλάπια & κουζίνα", ("cabinet", "kitchen_part")),
    ("Έπιπλα", ("library_object", "box")),
    ("Μηχανολογικά", ("mep_terminal", "mechanical_part", "mechanical_joint", "mechanical_mount", "mesh")),
    ("Οργανικά", ("pod", "arboreal_branch", "organic_junction", "organic_opening_patch")),
)
SITE = ("terrain", "plant", "site_path")
KIND_LABELS = {
    "wall": "Τοίχος", "door": "Πόρτα", "window": "Παράθυρο", "opening": "Άνοιγμα", "stair": "Σκάλα",
    "ramp": "Ράμπα", "structural_column": "Κολόνα", "structural_beam": "Δοκός", "floor": "Πλάκα",
    "room_floor": "Δάπεδο", "room_ceiling": "Οροφή", "room_foundation": "Θεμέλιο", "room_roof": "Στέγη",
    "cabinet": "Ντουλάπι", "kitchen_part": "Κομμάτι κουζίνας", "library_object": "Αντικείμενο",
    "box": "Κουτί", "terrain": "Έδαφος", "plant": "Φυτό", "site_path": "Μονοπάτι", "pod": "Pod",
}


def _levels(doc):
    """Storeys as the floor selector shows them (same source of truth)."""
    try:
        from archforge.architecture.stairs import discover_building_levels
        found = [(str(i["name"]), float(i["elevation"])) for i in discover_building_levels(doc)]
    except Exception:
        found = []
    if not found:
        found = [(str(n), float(z)) for n, z in doc.levels.items()]
    return sorted(found, key=lambda t: t[1]) or [("Ground", 0.0)]


def _owner(levels, z, tol=1e-4):
    """Name of the highest storey at or below ``z`` (the lowest storey otherwise)."""
    below = [n for n, lz in levels if lz <= z + tol]
    return below[-1] if below else levels[0][0]


def entity_level(doc, entity, levels=None):
    """Storey name an entity belongs to, or None for site items."""
    levels = levels or _levels(doc)
    p, k = entity.params, entity.kind
    if k in SITE:
        return None
    if k in ("door", "window", "opening") and entity.parent_id in doc.entities:
        return entity_level(doc, doc.get(entity.parent_id), levels)
    names = {n for n, _z in levels}
    if k == "structural_column" and p.get("base_level") in names:
        return str(p["base_level"])
    if k == "structural_beam" and p.get("level") in names:
        return str(p["level"])
    if k == "structural_support" and entity.parent_id in doc.entities:
        return entity_level(doc, doc.get(entity.parent_id), levels)
    for key in ("z", "floor_level", "level_z", "lower_z", "elevation_z"):
        if key in p:
            try:
                return _owner(levels, float(p[key]))
            except (TypeError, ValueError):
                break
    return levels[0][0]


def _label(entity):
    if entity.name:
        return entity.name
    p, k = entity.params, entity.kind
    base = KIND_LABELS.get(k, k)
    if k == "wall":
        import math
        length = math.hypot(float(p["x2"]) - float(p["x1"]), float(p["y2"]) - float(p["y1"]))
        return f"{base} {length:.2f} m"
    if k in ("cabinet", "library_object", "box") and "width" in p:
        return f"{base} {float(p['width']) * 100:.0f} cm"
    return base


def _rooms(doc, z):
    try:
        from archforge.architecture.topology import room_metrics
        out = []
        for index, face in enumerate(doc.active_room_faces(z=z), start=1):
            data = doc.room_metadata(face.signature)
            area = room_metrics(face.polygon)["area"]
            out.append(f"{data.get('name') or f'Room {index}'}  {area:.2f} m²")
        return out
    except Exception:
        return []


def project_outline(doc, title="Έργο"):
    levels = _levels(doc)
    by_level = {name: {} for name, _z in levels}
    site = []
    for eid, e in doc.entities.items():
        if e.kind in SITE:
            site.append(eid)
            continue
        level = entity_level(doc, e, levels)
        by_level.setdefault(level, {}).setdefault(e.kind, []).append(eid)
    children = []
    for name, z in levels:
        kinds = by_level.get(name, {})
        groups = []
        rooms = _rooms(doc, z)
        if rooms:
            groups.append({"label": f"Δωμάτια ({len(rooms)})", "entity_id": None, "level": name,
                           "children": [{"label": r, "entity_id": None, "level": name, "children": []} for r in rooms]})
        listed = set()
        for title_, kind_list in CATEGORIES:
            ids = [eid for k in kind_list for eid in kinds.get(k, [])]
            listed.update(kind_list)
            if ids:
                groups.append({"label": f"{title_} ({len(ids)})", "entity_id": None, "level": name,
                               "children": [{"label": _label(doc.get(i)), "entity_id": i, "level": name, "children": []}
                                            for i in ids]})
        other = [eid for k, ids in kinds.items() if k not in listed for eid in ids]
        if other:
            groups.append({"label": f"Άλλα ({len(other)})", "entity_id": None, "level": name,
                           "children": [{"label": _label(doc.get(i)), "entity_id": i, "level": name, "children": []}
                                        for i in other]})
        children.append({"label": f"{name}  ({z:+.2f} m)", "entity_id": None, "level": name, "children": groups})
    if site:
        children.append({"label": f"Οικόπεδο ({len(site)})", "entity_id": None, "level": None,
                         "children": [{"label": _label(doc.get(i)), "entity_id": i, "level": None, "children": []}
                                      for i in site]})
    return {"label": title, "entity_id": None, "level": None, "children": children}


def used_materials(doc):
    """Palette materials actually assigned in the project: ``[(id, name, count)]``."""
    from archforge.rendering.materials import MATERIAL_PRESETS
    counts = {}
    for e in doc.entities.values():
        ids = [e.params.get("material_id")] + list((e.params.get("surface_materials") or {}).values())
        for mid in {m for m in ids if m}:
            counts[mid] = counts.get(mid, 0) + 1
    return sorted(((m, MATERIAL_PRESETS.get(m, {}).get("name", m), n) for m, n in counts.items()), key=lambda t: t[1])
