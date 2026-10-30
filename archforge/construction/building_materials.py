"""Building materials («Υλικά δόμησης»): the one registry the wall layers point to (owner 30/10).

Spec: ``docs/specs/menu_relations_and_wall_layers.md`` §3 step 1.  A wall layer names a material id from here;
the material carries what the layer needs beyond its thickness:

* ``name``, ``category``, ``colour`` (plan/section fill) and ``hatch`` (section pattern key, DESIGN_DEFAULT);
* ``conductivity`` λ (W/mK) with its own provenance status (``core/provenance.py``);
* ``density`` (kg/m³): **none built in** — only what the user enters from a data sheet;
* ``insulation`` and ``role`` (``structure`` / ``insulation`` / ``finish`` / ``board``), the layer's default role;
* ``appearance``: the 3D/PBR material (``rendering/materials.py``) the layer looks like when it is a face, or None
  when the layer is never seen (insulation inside the wall);
* ``price_code``: the code in the price book (``quantities/price_book.py``, per m³).  No price is built in.

The built-in λ values are the *typical* values the program used since the wall types were written: none is
cross-checked against a source in force, so every one is registered ``UNVERIFIED`` (Isotex: from the maker's
published data, still «προς έλεγχο»).  They give an indicative U only.

A project may override a material's λ / density with the value from the data sheet of the product it uses:
``doc.materials["bmat:<id>"] = {"conductivity": .., "density": .., "source": ..}`` (``set_properties_command``,
one undo).  Such a value is ``MANUFACTURER_DATA`` — the user's entry, with the source the user typed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional

from archforge.core.commands import Command, SetMaterial
from archforge.core.provenance import MANUFACTURER_DATA, UNVERIFIED, Rule, register

PROJECT_PREFIX = "bmat:"
ROLES = {"structure": "Φέρουσα / πυρήνας", "insulation": "Μόνωση", "finish": "Τελείωμα", "board": "Πλάκα / επένδυση"}
HATCHES = ("plaster", "gypsum", "brick", "stone", "concrete", "masonry", "insulation_soft", "insulation_rigid",
           "wood_cement")

_TYPICAL = "Τυπική τιμή λ που χρησιμοποιούσε το πρόγραμμα· δεν διασταυρώθηκε με ισχύουσα πηγή"
_CHECK = "Για επαλήθευση: ΤΟΤΕΕ 20701-2 (πίνακες λ) ή φύλλο του προϊόντος που θα μπει."
_ISOTEX = ("Από δημοσιευμένα στοιχεία Isotex (construction/isotex.py SOURCE)· επιβεβαίωση με το τρέχον φυλλάδιο")


@dataclass(frozen=True)
class BuildingMaterial:
    id: str
    name: str
    category: str
    colour: str
    hatch: str
    role: str
    insulation: bool = False
    conductivity: float | None = None      # λ, W/mK
    conductivity_status: str = UNVERIFIED
    conductivity_source: str = ""
    density: float | None = None           # kg/m³ — from the user's data sheet only
    appearance: str | None = None          # rendering/materials.py id
    note: str = ""

    @property
    def price_code(self):
        return f"bmat.{self.id}"


def _m(id_, name, category, colour, hatch, role, lam, appearance=None, insulation=False, source=_TYPICAL, note=_CHECK):
    return BuildingMaterial(id_, name, category, colour, hatch, role, insulation, lam, UNVERIFIED, source,
                            appearance=appearance, note=note)


MATERIALS: dict[str, BuildingMaterial] = {m.id: m for m in (
    # λ values exactly as the wall types used them before the registry (no U changes silently).
    _m("cement_plaster", "Σοβάς", "Κονιάματα", "#ece6da", "plaster", "finish", 0.87, "plaster_white"),
    _m("gypsum_board", "Γυψοσανίδα", "Ξηρά δόμηση", "#f1efea", "gypsum", "board", 0.25, "paint_white_matt"),
    _m("hollow_brick", "Οπτόπλινθος διάτρητος", "Τοιχοποιία", "#b5653b", "brick", "structure", 0.47, "brick_exposed"),
    _m("stone_masonry", "Λιθοδομή", "Τοιχοποιία", "#9b8f7d", "stone", "structure", 1.70, "stone_cladding"),
    _m("reinforced_concrete", "Οπλισμένο σκυρόδεμα", "Σκυρόδεμα", "#a3a3a0", "concrete", "structure", 2.30,
       "concrete_rough"),
    _m("bearing_masonry", "Φέρουσα τοιχοποιία", "Τοιχοποιία", "#a8704a", "masonry", "structure", 0.80, "brick_old"),
    _m("mineral_wool", "Ορυκτοβάμβακας", "Μονώσεις", "#e8d38a", "insulation_soft", "insulation", 0.037, insulation=True),
    _m("xps", "Εξηλασμένη πολυστερίνη (XPS)", "Μονώσεις", "#9cc3d9", "insulation_rigid", "insulation", 0.034,
       insulation=True),
    _m("eps", "Διογκωμένη πολυστερίνη (EPS)", "Μονώσεις", "#e9eef0", "insulation_rigid", "insulation", 0.036,
       insulation=True),
    _m("isotex_wood_cement", "Ξυλότσιμεντο Isotex", "Δομικά συστήματα", "#b9a98c", "wood_cement", "structure", 0.11,
       source=_ISOTEX),
    _m("isotex_graphite_eps", "EPS γραφίτη (Neopor®)", "Δομικά συστήματα", "#6f7780", "insulation_rigid", "insulation",
       0.031, insulation=True, source=_ISOTEX),
    _m("infill_concrete", "Σκυρόδεμα πλήρωσης", "Σκυρόδεμα", "#a3a3a0", "concrete", "structure", 2.30),
    _m("icf_eps", "EPS καλουπιού ICF", "Δομικά συστήματα", "#e9eef0", "insulation_rigid", "insulation", 0.036,
       insulation=True),
    _m("icf_core_concrete", "Σκυρόδεμα πυρήνα ICF", "Σκυρόδεμα", "#a3a3a0", "concrete", "structure", 2.30),
)}

register(*(Rule(f"materials.{m.id}.conductivity",
                f"λ {m.name} = {m.conductivity:g} W/mK για το ενδεικτικό U των συνθέσεων τοίχου",
                m.conductivity_status, note=f"{m.conductivity_source}. {m.note}".strip())
           for m in MATERIALS.values() if m.conductivity is not None))


def overrides(doc):
    """``{id: {"conductivity", "density", "source"}}`` the project holds (other ``doc.materials`` keys ignored)."""
    raw = getattr(doc, "materials", None) or {}
    return {k[len(PROJECT_PREFIX):]: dict(v) for k, v in raw.items()
            if str(k).startswith(PROJECT_PREFIX) and isinstance(v, dict)}


def material(material_id, doc=None):
    """The material with the project's data-sheet values applied, or None for an unknown id."""
    base = MATERIALS.get(str(material_id))
    if base is None:
        return None
    o = overrides(doc).get(base.id)
    if not o:
        return base
    changes = {}
    if o.get("conductivity") is not None:
        changes.update(conductivity=float(o["conductivity"]), conductivity_status=MANUFACTURER_DATA,
                       conductivity_source=str(o.get("source") or "Φύλλο προϊόντος (εισαγωγή χρήστη)"))
    if o.get("density") is not None:
        changes["density"] = float(o["density"])
    return replace(base, **changes) if changes else base


def by_category():
    out = {}
    for m in MATERIALS.values():
        out.setdefault(m.category, []).append(m)
    return out


def set_properties_command(doc, material_id, *, conductivity=None, density=None, source=""):
    """``SetMaterial`` that stores the project's data-sheet values for one material (one undo); ``None`` clears a
    value, all ``None`` returns the material to the built-in values."""
    if str(material_id) not in MATERIALS:
        raise ValueError(f"άγνωστο υλικό δόμησης: {material_id}")
    for label, v in (("λ", conductivity), ("πυκνότητα", density)):
        if v is not None and not float(v) > 0:
            raise ValueError(f"{label} πρέπει να είναι θετικό")
    key = PROJECT_PREFIX + str(material_id)
    if conductivity is None and density is None:
        return ClearBuildingMaterial(key)
    return SetMaterial(key, {"conductivity": None if conductivity is None else float(conductivity),
                             "density": None if density is None else float(density), "source": str(source or "")})


@dataclass
class ClearBuildingMaterial(Command):
    """Drops the project's data-sheet values of one material (back to the built-in ones)."""
    key: str
    before: Optional[Dict[str, Any]] = None

    def do(self, doc):
        self.before = doc.materials.pop(self.key, None)

    def undo(self, doc):
        if self.before is not None:
            doc.materials[self.key] = self.before
