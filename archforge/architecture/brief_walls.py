"""The project answers change the drawing: existing walls take the wall system the brief now says.

When the exterior or interior wall answer changes (Στοιχεία έργου):

* exterior walls take the new type and thickness; measured on the outside
  (new buildings) the outer face stays where it is and the extra thickness
  goes inwards — measured inside (renovations) the inner face stays; corners
  and T junctions are joined again, doors and windows keep their place;
* interior walls take the interior type and thickness on their axis;
* walls marked «Υφιστάμενο» (renovation survey) are never changed.

One command, one undo, together with the answer itself.
"""
from __future__ import annotations

from archforge.architecture.dimension_reference import reconnect


def _storeys(doc):
    return sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"})


def wall_changes(doc):
    """``{entity_id: params}`` making the drawing follow the brief (empty when it already does)."""
    from archforge.mep.ventilation import exterior_walls
    from archforge.project.brief import get_brief, interior_wall_defaults, wall_defaults
    brief = get_brief(doc)
    if brief is None:
        return {}
    ext_type, ext_t = wall_defaults(doc)
    interior = interior_wall_defaults(doc)
    measure = brief.get("measure", "exterior")
    out = {}
    for z in _storeys(doc):
        walls = [e for e in doc.entities.values() if e.kind == "wall" and abs(float(e.params.get("z", 0.0)) - z) < .05]
        normals = {w.id: n for w, n in exterior_walls(doc, z)}
        shift, typed = {}, {}
        for w in walls:
            if str(w.params.get("phase", "new")) == "existing":
                continue
            old_t = float(w.params.get("thickness", .2))
            if w.id in normals:
                new_type, new_t = ext_type, ext_t
                # The measured face stays put: outside for new buildings, inside for renovations.
                if abs(new_t - old_t) > 1e-6:
                    shift[w.id] = -(new_t - old_t) / 2 if measure == "exterior" else (new_t - old_t) / 2
            elif interior is not None:
                new_type, new_t, _bearing = interior
            else:
                continue
            change = {}
            if new_type and str(w.params.get("wall_type", "")) != new_type:
                change["wall_type"] = new_type
            if abs(new_t - old_t) > 1e-6:
                change["thickness"] = new_t
            if change:
                typed[w.id] = change
        moved, openings = reconnect(doc, walls, normals, shift) if shift else ({}, {})
        existing = {w.id for w in walls if str(w.params.get("phase", "new")) == "existing"}
        for wid, params in moved.items():
            if wid in existing:
                continue                       # an existing wall stays exactly as surveyed; the new ones meet it
            out.setdefault(wid, {}).update(params)
        for wid, params in typed.items():
            out.setdefault(wid, {}).update(params)
        for oid, offset in openings.items():
            out[oid] = {"offset": offset}
    return out


def apply_command(doc):
    """CompositeCommand applying ``wall_changes`` (walls before their openings), or None."""
    from archforge.core.commands import CompositeCommand, UpdateEntity
    changes = wall_changes(doc)
    if not changes:
        return None
    order = sorted(changes, key=lambda i: doc.get(i).kind != "wall")
    return CompositeCommand([UpdateEntity(i, changes[i]) for i in order], "Τοίχοι από τα Στοιχεία έργου")
