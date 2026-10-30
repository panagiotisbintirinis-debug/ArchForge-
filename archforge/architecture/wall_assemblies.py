"""The project's own wall assemblies («Συνθέσεις του έργου», spec §3 step 2, owner 30/10).

The built-in types (``wall_types.WALL_TYPES``) are defaults and never change.  The project keeps its own types in
``doc.constructions["walltype:proj_…"]``; every command here is one undo step:

* ``new_type_command`` / ``copy_type_command``: a new type from layers, or a copy of any type (built-in or project);
* ``edit_type_command``: change a project type's name / layers → **every wall of that type** follows (thickness =
  sum of the new layers), in the same undo step;
* ``own_type_command``: change the layers of one wall only → the wall gets its own copy (a curved wall: the whole arc).

A layer is ``{"material": building-material id, "thickness": m, "role": building_materials.ROLES key}``.
"""
from __future__ import annotations

from archforge.architecture.wall_types import (CONSTRUCTION_PREFIX, PROJECT_PREFIX, is_project_type, label, layers,
                                               project_types)
from archforge.construction.building_materials import MATERIALS, ROLES
from archforge.core.commands import CompositeCommand, SetConstruction, UpdateEntities


def clean_layers(rows):
    """Validated layer specs (ValueError in Greek on a bad row)."""
    out = []
    for i, r in enumerate(rows or (), 1):
        mid = str(r.get("material", ""))
        if mid not in MATERIALS:
            raise ValueError(f"στρώση {i}: άγνωστο υλικό δόμησης «{mid}»")
        d = float(r.get("thickness", 0) or 0)
        if not d > 0:
            raise ValueError(f"στρώση {i}: το πάχος πρέπει να είναι θετικό")
        role = str(r.get("role") or MATERIALS[mid].role)
        if role not in ROLES:
            raise ValueError(f"στρώση {i}: άγνωστος ρόλος «{role}»")
        out.append({"material": mid, "thickness": round(d, 4), "role": role})
    if not out:
        raise ValueError("μια σύνθεση θέλει τουλάχιστον μία στρώση")
    return out


def layer_specs(doc, wall_type):
    return [layer.spec() for layer in layers(wall_type, doc)]


def next_key(doc):
    used = set(project_types(doc)) | {str(k)[len(CONSTRUCTION_PREFIX):] for k in (doc.constructions or {})}
    n = 1
    while f"{PROJECT_PREFIX}{n}" in used:
        n += 1
    return f"{PROJECT_PREFIX}{n}"


def walls_of_type(doc, wall_type):
    return [e for e in doc.entities.values() if e.kind == "wall" and str(e.params.get("wall_type")) == str(wall_type)]


def _thickness_follows(doc, wall_type, rows):
    total = round(sum(r["thickness"] for r in rows), 4)
    changes = {w.id: {"thickness": total} for w in walls_of_type(doc, wall_type)
               if abs(float(w.params.get("thickness", 0.0)) - total) > 1e-9}
    return UpdateEntities(changes) if changes else None


def new_type_command(doc, name, rows):
    """``(key, command)``: a new project type."""
    rows = clean_layers(rows)
    name = str(name).strip() or "Νέα σύνθεση"
    key = next_key(doc)
    return key, SetConstruction(CONSTRUCTION_PREFIX + key, {"label": name, "layers": rows})


def copy_type_command(doc, wall_type, name=None):
    """``(key, command)``: a project copy of any type with layers («Αντίγραφο»)."""
    rows = layer_specs(doc, wall_type)
    if not rows:
        raise ValueError("ο γενικός τοίχος δεν έχει στρώσεις να αντιγραφούν")
    return new_type_command(doc, name or f"{label(wall_type, doc)} — αντίγραφο", rows)


def edit_type_command(doc, wall_type, *, name=None, rows=None):
    """Change a project type; every wall of it takes the new thickness (one undo)."""
    if not is_project_type(wall_type) or wall_type not in project_types(doc):
        raise ValueError("οι έτοιμες συνθέσεις δεν αλλάζουν: κάνε αντίγραφο και άλλαξε εκείνο")
    current = doc.constructions[CONSTRUCTION_PREFIX + wall_type]
    rows = clean_layers(rows) if rows is not None else [dict(r) for r in current["layers"]]
    props = {"label": str(name).strip() if name else current.get("label", wall_type), "layers": rows}
    return CompositeCommand([SetConstruction(CONSTRUCTION_PREFIX + wall_type, props),
                             _thickness_follows(doc, wall_type, rows)], label="Αλλαγή σύνθεσης")


def own_type_command(doc, wall_id, rows, name=None):
    """``(key, command)``: this wall (the whole arc of a curved wall) gets its own type with ``rows``."""
    from archforge.architecture.curved_wall import spread_command
    wall = doc.get(wall_id)
    if wall is None or wall.kind != "wall":
        raise ValueError("διάλεξε τοίχο")
    rows = clean_layers(rows)
    base = str(wall.params.get("wall_type", "generic"))
    key, create = new_type_command(doc, name or f"{label(base, doc)} — {wall.name or 'τοίχος'}", rows)
    total = round(sum(r["thickness"] for r in rows), 4)
    return key, CompositeCommand([create, spread_command(doc, wall_id, {"wall_type": key, "thickness": total})],
                                 label="Δική του σύνθεση")
