"""Building materials («υλικά δόμησης»): one registry for what a wall layer is made of.

Spec ``docs/specs/menu_relations_and_wall_layers.md`` §3 step 1.  A wall layer
points at an id here (``wall_types.layer``) instead of carrying its own name,
λ and colour, so the plan hatch, the section, the quantities, the U-value and
the IFC material all read one entry.

Each entry: name, category, λ (W/mK), density (kg/m³), section hatch, the
appearance material (``rendering/materials.py`` id, the look of an exposed
face; None = never seen, e.g. insulation inside the wall), colour of the layer
in plan and insulation flag.  No price: prices live only in the common price
book (``quantities/price_book.py``), entered by the user.

Values are typical, not product data: λ and density are UNVERIFIED (common
EN ISO 10456 / manufacturer-range figures, not cross-checked; the data sheet
of the product used wins).

Ids are stable (saved projects will store them) and never renamed.
"""
from __future__ import annotations

from dataclasses import dataclass

from archforge.core.provenance import DESIGN_DEFAULT, UNVERIFIED, Rule, register

# Section hatches the plan / section / DXF will draw (step 4); names only for now.
HATCHES = ("plaster", "gypsum", "brick", "masonry", "stone", "concrete", "insulation", "wood_cement", "solid")


@dataclass(frozen=True)
class BuildingMaterial:
    id: str
    name: str
    category: str
    conductivity: float          # λ, W/mK (typical)
    density: float | None        # kg/m³ (typical)
    hatch: str
    appearance: str | None       # rendering material id of an exposed face
    color: str                   # layer colour in plan / face colour when exposed
    insulation: bool = False
    status: str = UNVERIFIED


BUILDING_MATERIALS: dict[str, BuildingMaterial] = {}


def _add(category, rows):
    for mid, (name, lam, rho, hatch, look, color, *ins) in rows.items():
        BUILDING_MATERIALS[mid] = BuildingMaterial(mid, name, category, lam, rho, hatch, look, color, bool(ins and ins[0]))


# id: (name, λ, density, hatch, appearance, colour[, insulation])
_add("Κονιάματα & επενδύσεις", {
    "plaster_lime_cement": ("Σοβάς", 0.87, 1800, "plaster", "plaster_white", "#ece6da"),
    "gypsum_board": ("Γυψοσανίδα", 0.25, 900, "gypsum", "paint_white_matt", "#f1efea"),
})
_add("Τοιχοποιίες", {
    "brick_perforated": ("Οπτόπλινθος διάτρητος", 0.47, 1000, "brick", "brick_exposed", "#b5653b"),
    "stone_masonry": ("Λιθοδομή", 1.70, 2200, "stone", "stone_pelion", "#9b8f7d"),
    "bearing_masonry": ("Φέρουσα τοιχοποιία", 0.80, 1600, "masonry", "brick_old", "#a8704a"),
    "wood_cement_isotex": ("Ξυλότσιμεντο Isotex", 0.11, None, "wood_cement", None, "#b9a98c"),
})
_add("Σκυρόδεμα", {
    "concrete_reinforced": ("Οπλισμένο σκυρόδεμα", 2.30, 2400, "concrete", "concrete_smooth", "#a3a3a0"),
    "concrete_core_icf": ("Σκυρόδεμα πυρήνα ICF", 2.30, 2400, "concrete", "concrete_rough", "#a3a3a0"),
    "concrete_infill_isotex": ("Σκυρόδεμα πλήρωσης", 2.30, 2400, "concrete", "concrete_rough", "#a3a3a0"),
})
_add("Θερμομονώσεις", {
    "mineral_wool": ("Ορυκτοβάμβακας", 0.037, 40, "insulation", None, "#e8d38a", True),
    "xps": ("Εξηλασμένη πολυστερίνη (XPS)", 0.034, 35, "insulation", None, "#9cc3d9", True),
    "eps": ("Διογκωμένη πολυστερίνη (EPS)", 0.036, 20, "insulation", None, "#e9eef0", True),
    "eps_icf_form": ("EPS καλουπιού ICF", 0.036, None, "insulation", None, "#e9eef0", True),
    "eps_graphite": ("EPS γραφίτη (Neopor®)", 0.031, None, "insulation", None, "#6f7780", True),
})


class Layer(tuple):
    """A wall layer: the 5-tuple ``(name, thickness, λ, colour, insulation)`` callers unpack, plus ``material_id``."""

    material_id: str

    def __new__(cls, material_id, thickness):
        m = BUILDING_MATERIALS[material_id]
        row = super().__new__(cls, (m.name, float(thickness), m.conductivity, m.color, m.insulation))
        row.material_id = material_id
        return row

    def __reduce__(self):
        return (Layer, (self.material_id, self[1]))


def layer(material_id, thickness):
    """A wall layer of ``thickness`` m of a registry material (KeyError for an unknown id)."""
    return Layer(material_id, thickness)


def building_material(material_id):
    return BUILDING_MATERIALS.get(str(material_id))


def building_material_rules():
    return _RULES


_RULES = register(
    Rule("building_materials.conductivity",
         "λ υλικών δόμησης (σοβάς 0,87 · γυψοσανίδα 0,25 · οπτόπλινθος 0,47 · λιθοδομή 1,70 · σκυρόδεμα 2,30 · "
         "ορυκτοβάμβακας 0,037 · XPS 0,034 · EPS 0,036 · EPS γραφίτη 0,031 · ξυλότσιμεντο 0,11 W/mK)", UNVERIFIED,
         note="Τυπικές τιμές (EN ISO 10456 / εύρος κατασκευαστών) — δεν διασταυρώθηκαν· το U είναι ενδεικτικό, όχι "
              "μελέτη ΚΕΝΑΚ· το λ του προϊόντος από το φυλλάδιο υπερισχύει."),
    Rule("building_materials.density",
         "Πυκνότητα υλικών δόμησης για βάρη/ποσότητες (σκυρόδεμα 2400 · λιθοδομή 2200 · σοβάς 1800 · οπτόπλινθος 1000 "
         "kg/m³ …· κενό = άγνωστο)", UNVERIFIED,
         note="Τυπικές τιμές, όχι από φυλλάδιο· δεν χρησιμοποιούνται σε στατικό υπολογισμό."),
    Rule("building_materials.hatch_and_look",
         "Διαγράμμιση τομής και υλικό εμφάνισης ανά υλικό δόμησης", DESIGN_DEFAULT,
         note="Επιλογή του προγράμματος για την παρουσίαση· αλλάζει χωρίς τεχνική συνέπεια."),
)
