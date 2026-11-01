"""Reversible manual height edits on the authoritative semantic Document.

Two independent human intents:

* Changing a named storey's elevation moves its storey-bound objects and the
  endpoints of connected stairs/ramps.  Adjacent floor levels remain fixed.
* Changing its nominal clear height adjusts a common ceiling and, when the
  ceiling coincides with the wall tops, the enclosing walls and their roofs.

Neither command estimates a code-compliant height, a safe stair riser or a
structural design.  Both retain the original entity IDs and relationships.
Ambiguous mixed wall/ceiling heights are refused instead of silently flattened.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from archforge.core.commands import Command, _restore_document_state, _legacy_world_modifier
from archforge.core.model import Document, WorkPlane

EPS = 1e-5  # geometric comparison only, not a building regulation
SITE_KINDS = {"terrain", "site_path", "plant", "pool"}
ATTACHED_KINDS = {"door", "window", "opening", "structural_support", "structural_load",
                  "mechanical_mount", "organic_opening_patch"}
ABSOLUTE_Z = ("z", "level_z", "floor_level", "elevation_z")


def _restore_with_order(doc, state, selection):
    """Keep the exact serialized entity order too (load defers linked children)."""
    _restore_document_state(doc, state, selection)
    order = [raw["id"] for raw in state.get("entities", [])]
    if order != list(doc.entities):
        doc.entities = {eid: doc.entities[eid] for eid in order if eid in doc.entities}


def _at(a, b):
    return abs(float(a) - float(b)) <= EPS


def _finite(value, name):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"Μη έγκυρο {name}")
    return number


def _level(doc, name):
    if name not in doc.levels:
        raise ValueError(f"Δεν υπάρχει η στάθμη «{name}»")
    return float(doc.levels[name])


def _owner(levels, z):
    """Name of the floor below a point (same geometry ownership as the project tree)."""
    ordered = sorted(((str(name), float(value)) for name, value in levels.items()), key=lambda x: x[1])
    below = [name for name, value in ordered if value <= float(z) + EPS]
    return below[-1] if below else ordered[0][0]


def _level_owner(doc, entity):
    p, kind = entity.params, entity.kind
    if kind in SITE_KINDS or kind in ATTACHED_KINDS or kind in ("stair", "ramp", "mechanical_joint"):
        return None
    if kind == "structural_column":
        return str(p.get("base_level", ""))
    if kind == "structural_beam" and p.get("level") in doc.levels:
        return str(p["level"])
    if kind == "pitched_roof" and "eave_z" in p:
        # A roof follows a storey only when its eave actually coincides with
        # wall tops from *one* named storey; avoid a guessed height threshold.
        owners = {_owner(doc.levels, wall.params["z"])
                  for wall in doc.entities.values() if wall.kind == "wall" and
                  _at(float(wall.params["z"]) + float(wall.params["height"]), p["eave_z"])}
        return next(iter(owners)) if len(owners) == 1 else None
    if kind == "railing" and p.get("stair_side") and entity.parent_id in doc.entities:
        return None  # the linked stair updates and synchronizes its own railing
    for key in ABSOLUTE_Z:
        if key in p:
            return _owner(doc.levels, p[key])
    return None


def _reference_key(params):
    return next((key for key in ABSOLUTE_Z if key in params), None)


def _relevel(doc, name, elevation):
    old = _level(doc, name)
    target = _finite(elevation, "υψόμετρο ορόφου")
    dz = target - old
    if abs(dz) <= EPS:
        return False
    ordered = sorted(float(z) for n, z in doc.levels.items() if n != name)
    if any(_at(target, value) for value in ordered):
        raise ValueError("Η στάθμη συμπίπτει με άλλη στάθμη ορόφου")
    before_below = sum(z < old - EPS for z in ordered)
    after_below = sum(z < target - EPS for z in ordered)
    if before_below != after_below:
        raise ValueError("Η νέα στάθμη θα περνούσε πάνω/κάτω από άλλη στάθμη ορόφου")

    active_level_before = doc.active_level_name()
    original_owners = {eid: _level_owner(doc, e) for eid, e in doc.entities.items()}
    changes = {}
    shifted = set()
    for eid, entity in doc.entities.items():
        p, kind = entity.params, entity.kind
        if kind == "structural_column":
            base, top = p.get("base_level"), p.get("top_level")
            move_base = base == name
            move_top = top == name
            if not (move_base or move_top):
                continue
            change = {}
            if move_base:
                change["z"] = float(p["z"]) + dz
            change["height"] = float(p["height"]) + dz * (int(move_top) - int(move_base))
            if change["height"] <= EPS:
                raise ValueError("Η νέα στάθμη θα μηδένιζε το ύψος κολόνας")
            changes[eid] = change
            shifted.add(eid)
        elif kind in ("stair", "ramp"):
            lower = _at(p["lower_z"], old)
            upper = _at(p.get("upper_floor_z", p["upper_z"]), old)
            if not (lower or upper):
                continue
            lo = float(p["lower_z"]) + (dz if lower else 0)
            hi = float(p["upper_z"]) + (dz if upper else 0)
            if hi - lo <= EPS:
                raise ValueError("Η νέα στάθμη θα αντέστρεφε τη σκάλα/ράμπα")
            change = {"lower_z": lo, "upper_z": hi}
            if upper and "upper_floor_z" in p:
                change["upper_floor_z"] = float(p["upper_floor_z"]) + dz
            if kind == "stair":
                change["riser_height"] = (hi - lo) / int(p["riser_count"])
            else:
                change["slope_pct"] = 100 * (hi - lo) / float(p["run_length"])
            changes[eid] = change
            shifted.add(eid)
        elif kind == "mechanical_joint":
            continue  # handled when the movement of both parts is known
        elif kind == "pitched_roof" and original_owners[eid] == name:
            changes[eid] = {"eave_z": float(p["eave_z"]) + dz}
            shifted.add(eid)
        elif original_owners[eid] == name:
            key = _reference_key(p)
            if key is None:
                if kind == "mesh":
                    raise ValueError("Πλέγμα χωρίς σημασιολογική στάθμη: δεν μπορεί να μετακινηθεί αυτόματα")
                continue
            changes[eid] = {key: float(p[key]) + dz}
            shifted.add(eid)

    # A mechanical joint stores an absolute anchor in addition to the IDs of
    # its connected parts.  Shift it only when both parts move together.
    for eid, entity in doc.entities.items():
        if entity.kind != "mechanical_joint":
            continue
        parent, child = entity.params.get("parent_part"), entity.params.get("child_part")
        moved = (parent in shifted, child in shifted)
        if any(moved) and not all(moved):
            raise ValueError("Μηχανική σύνδεση ενώνει διαφορετικές στάθμες· απαιτεί χειροκίνητη επαλήθευση")
        if all(moved) and "anchor" in entity.params:
            a = entity.params["anchor"]
            changes[eid] = {"anchor": (a[0], a[1], float(a[2]) + dz)}

    # Validate all dependent objects on the disposable semantic document.
    for eid, delta in changes.items():
        doc.update(eid, delta)
    doc.levels[name] = target
    wp = doc.work_plane
    if wp.name == name or (_at(wp.origin[2], old) and active_level_before == name):
        doc.work_plane = WorkPlane(name=name, origin=(wp.origin[0], wp.origin[1], target),
                                   u=tuple(wp.u), v=tuple(wp.v))
    for binding in doc.room_bindings.values():
        if _at(binding.get("z", 1e100), old):
            binding["z"] = target
    for mod in doc.surface_modifiers.values():
        if mod.target.owner_id in shifted and _legacy_world_modifier(mod):
            center = mod.target.subregion["world_center"]
            mod.target.subregion["world_center"] = [center[0], center[1], center[2] + dz]
            doc.mark_dirty(mod.target.owner_id)
    return True


def clear_height(doc, name):
    """Current common room-ceiling underside, otherwise common wall-top height.

    A mixed/ambiguous set is deliberately not compressed into a false number.
    """
    z = _level(doc, name)
    walls = [e for e in doc.entities.values() if e.kind == "wall" and _at(e.params["z"], z)]
    ceilings = [e for e in doc.entities.values() if e.kind == "room_ceiling" and
                _at(e.params.get("level_z", 1e100), z)]
    values = [float(e.params["offset_z"]) for e in ceilings] if ceilings else \
             [float(e.params["height"]) for e in walls]
    if not values:
        raise ValueError("Δεν υπάρχει οροφή ή τοίχος στον όροφο για μέτρηση καθαρού ύψους")
    if any(not _at(h, values[0]) for h in values[1:]):
        raise ValueError("Υπάρχουν διαφορετικά ύψη στον όροφο· δεν θα εξισωθούν αυτόματα")
    return values[0]


def _clear_height(doc, name, height):
    z = _level(doc, name)
    target = _finite(height, "καθαρό ύψος")
    if target <= EPS:
        raise ValueError("Το καθαρό ύψος πρέπει να είναι θετικό")
    higher = [float(value) for n, value in doc.levels.items() if n != name and float(value) > z + EPS]
    if higher and target >= min(higher) - z - EPS:
        raise ValueError("Το καθαρό ύψος φτάνει ή περνά την επόμενη στάθμη· απαιτεί ξεχωριστή μελέτη")
    current = clear_height(doc, name)
    delta = target - current
    if abs(delta) <= EPS:
        return False
    ceilings = [e for e in doc.entities.values() if e.kind == "room_ceiling" and
                _at(e.params.get("level_z", 1e100), z)]
    walls = [e for e in doc.entities.values() if e.kind == "wall" and _at(e.params["z"], z)]
    if ceilings:
        # A separate suspended ceiling can move independently of full-height
        # walls and the structural roof (this is the actual clear height).
        for e in ceilings:
            doc.update(e.id, {"offset_z": target})
        if not walls or not all(_at(e.params["height"], current) for e in walls):
            if any(float(e.params["height"]) < target - EPS for e in walls):
                raise ValueError("Η νέα ψευδοροφή θα ξεπερνούσε το ύψος τοίχου")
            return True
    elif any(not _at(e.params["height"], current) for e in walls):
        raise ValueError("Υπάρχουν διαφορετικά ύψη τοίχων· δεν θα εξισωθούν αυτόματα")

    for wall in walls:
        doc.update(wall.id, {"height": target})
    # Preserve slabs and roofs whose undersides/eaves were attached to those
    # wall tops.  Independently positioned roofs remain independent.
    for entity in list(doc.entities.values()):
        p = entity.params
        if entity.kind == "room_roof" and _at(p.get("level_z", 1e100), z) and \
                _at(p.get("offset_z", 1e100), current):
            doc.update(entity.id, {"offset_z": target})
        elif entity.kind == "pitched_roof" and _at(p.get("eave_z", 1e100), z + current):
            doc.update(entity.id, {"eave_z": z + target})
        elif entity.kind == "ceiling_joists" and _at(p.get("z", 1e100), z + current):
            doc.update(entity.id, {"z": z + target})
    return True


@dataclass
class _StoreyEdit(Command):
    name: str
    value: float
    before: dict | None = field(default=None, init=False, repr=False)
    after: dict | None = field(default=None, init=False, repr=False)
    selection: list[str] = field(default_factory=list, init=False, repr=False)
    noop: bool = field(default=False, init=False)

    def do(self, doc):
        if self.after is not None:
            _restore_with_order(doc, self.after, self.selection)
            return
        self.before = copy.deepcopy(doc.to_dict())
        self.selection = list(doc.selection)
        staged = Document.from_dict(copy.deepcopy(self.before))
        if self._apply(staged, self.name, self.value):
            self.after = copy.deepcopy(staged.to_dict())
            _restore_with_order(doc, self.after, self.selection)
        else:
            self.noop = True

    def undo(self, doc):
        if self.before is not None:
            _restore_with_order(doc, self.before, self.selection)


@dataclass
class ChangeStoreyElevation(_StoreyEdit):
    """Edit the selected *absolute* floor elevation, not every level above it."""

    def _apply(self, doc, name, value):
        return _relevel(doc, name, value)


@dataclass
class ChangeStoreyClearHeight(_StoreyEdit):
    """Edit ceiling underside; move coincident walls/roof only if coupled."""

    def _apply(self, doc, name, value):
        return _clear_height(doc, name, value)
