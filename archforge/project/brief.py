"""The project brief: the questions asked at the start of every project.

A choice is the answer to a question — without the question the program has
nothing to choose by.  The answers live in the Document (one
``project_brief`` entity, undoable, saved with the project) and drive the
defaults and the rules that follow:

* New construction or renovation.  In a renovation the drawn survey is the
  existing building: existing columns and beams cannot be moved; walls,
  openings and MEP can be marked for demolition (they count in the take-off).
* The wall system: it sets the wall type and thickness the wall tool draws,
  and whether the walls carry the loads (stone / solid masonry: no columns,
  the slab is designed instead) or are a shell around a concrete frame.
* The interior walls: single or double plasterboard, brick with plaster, or
  load-bearing (at least 25 cm).  A wall drawn inside a closed space takes
  this type instead of the shell's.
* Exterior or interior dimensions: new buildings are usually measured on
  the outside, renovations on the inside; the take-off always reports net
  interior surfaces.
* The floor system: concrete slab or timber beams with a timber floor.
"""
from __future__ import annotations

PROJECT_TYPES = {"new": "Νέα κατασκευή", "renovation": "Ανακαίνιση"}
# system: label, wall type (architecture.wall_types), thickness if no type (m), load-bearing walls
WALL_SYSTEMS = {
    "stone_bearing": ("Πέτρινοι φέροντες τοίχοι (πετροκτιστά)", "stone_uninsulated", None, True),
    "stone_insulated": ("Πέτρινοι φέροντες με εσωτερική θερμομόνωση", "stone_insulated", None, True),
    "brick_double_insulated": ("Διπλή τοιχοποιία με θερμομόνωση (κέλυφος σε σκελετό ΟΣ)", "brick_double_insulated", None, False),
    "brick_single": ("Μονή τοιχοποιία (κέλυφος σε σκελετό ΟΣ)", "brick_partition", None, False),
    "concrete_etics": ("Οπλισμένο σκυρόδεμα με θερμοπρόσοψη", "concrete_etics", None, False),
}
# interior walls: label, wall type, load-bearing
INTERIOR_WALLS = {
    "drywall_single": ("Γυψοσανίδα μονή (10 cm)", "drywall_100", False),
    "drywall_double": ("Γυψοσανίδα διπλή (12,5 cm, ηχομόνωση)", "drywall_double_125", False),
    "brick_plaster": ("Τούβλο με σοβά (13 cm)", "brick_partition", False),
    "bearing": ("Φέρων οργανισμός (ελάχιστο 25 cm)", "bearing_interior_25", True),
}
MIN_BEARING_THICKNESS = 0.25
MEASURES = {"exterior": "Εξωτερικές διαστάσεις κτίσματος", "interior": "Εσωτερικές διαστάσεις χώρων"}
FLOOR_SYSTEMS = {"rc_slab": "Πλάκα οπλισμένου σκυροδέματος", "timber": "Ξύλινοι δοκοί και ξύλινο μεσοπάτωμα"}
PHASES = {"new": "Νέο", "existing": "Υφιστάμενο", "demolish": "Καθαίρεση"}
QUESTIONS = (
    ("project_type", "Τι έργο είναι;", PROJECT_TYPES),
    ("wall_system", "Τι τοίχους έχει (εξωτερικούς);", WALL_SYSTEMS),
    ("interior_walls", "Τι εσωτερικούς τοίχους;", INTERIOR_WALLS),
    ("measure", "Μετράμε εξωτερικές ή εσωτερικές διαστάσεις;", MEASURES),
    ("floor_system", "Τι πατώματα / ταβάνια;", FLOOR_SYSTEMS),
)
DEFAULTS = {"project_type": "new", "wall_system": "brick_double_insulated", "interior_walls": "brick_plaster",
            "measure": "exterior", "floor_system": "rc_slab"}


def brief_entity(doc):
    return next((e for e in doc.entities.values() if e.kind == "project_brief"), None)


def get_brief(doc):
    """The answers, or None when the questions have not been answered yet."""
    e = brief_entity(doc)
    if e is None:
        return None
    out = dict(DEFAULTS)
    out.update({k: v for k, v in e.params.items() if k in DEFAULTS})
    return out


def wall_defaults(doc):
    """(wall_type, thickness) the wall tool should draw, from the brief (None, 0.15 without one)."""
    brief = get_brief(doc)
    if brief is None:
        return None, 0.15
    from archforge.architecture.wall_types import total_thickness
    _label, wall_type, thickness, _bearing = WALL_SYSTEMS[brief["wall_system"]]
    return wall_type, round(total_thickness(wall_type), 4) if wall_type else thickness


def interior_wall_defaults(doc):
    """(wall_type, thickness, load_bearing) for a wall drawn inside an enclosed space, or None without a brief."""
    brief = get_brief(doc)
    if brief is None:
        return None
    from archforge.architecture.wall_types import total_thickness
    _label, wall_type, bearing = INTERIOR_WALLS[brief["interior_walls"]]
    return wall_type, round(total_thickness(wall_type), 4), bearing


def wall_is_interior(faces, params):
    """True when the wall lies inside one of ``faces`` (closed spaces drawn before it): a partition, not the shell."""
    from archforge.assistant.understanding import inside
    x1, y1, x2, y2 = (float(params[k]) for k in ("x1", "y1", "x2", "y2"))
    probes = [(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t) for t in (0.25, 0.5, 0.75)]
    return any(all(inside(f.polygon, x, y) for x, y in probes) for f in faces)


def interior_walls(doc):
    """Walls inside the building outline (not exterior), any storey."""
    from archforge.mep.ventilation import exterior_walls
    zs = sorted({round(float(e.params.get("z", 0.0)), 4) for e in doc.entities.values() if e.kind == "wall"})
    outer = {w.id for z in zs for w, _n in exterior_walls(doc, z)}
    enclosed = {wid for z in zs for f in doc.active_room_faces(z=z) for wid in f.wall_ids}
    return [doc.get(i) for i in sorted(enclosed - outer)]


def load_bearing_walls(doc):
    brief = get_brief(doc)
    return bool(brief and WALL_SYSTEMS[brief["wall_system"]][3])


def is_renovation(doc):
    brief = get_brief(doc)
    return bool(brief and brief["project_type"] == "renovation")


def phase_of(entity):
    return str(entity.params.get("phase", "new"))
