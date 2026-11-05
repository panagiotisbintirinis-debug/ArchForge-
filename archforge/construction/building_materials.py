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

05/11: the built-in λ come from ΤΟΤΕΕ 20701-2/2010 Πίνακας 2 (PDF from the owner, ``mep/totee_20701_2.py``):
``VERIFIED`` where a row gives the material exactly (σοβάς, οπλισμένο σκυρόδεμα), ``DESIGN_DEFAULT`` where the
density / product is not known (row nearest to the value used before, or a value inside the table's range), and
``UNVERIFIED`` where the table has no row (γυψοσανίδα) or the maker's figure is outside it (Isotex ξυλότσιμεντο).
They give an indicative U only — the product's data sheet (ⓘ of the material) decides.

A project may override a material's λ / density with the value from the data sheet of the product it uses:
``doc.materials["bmat:<id>"] = {"conductivity": .., "density": .., "source": ..}`` (``set_properties_command``,
one undo).  Such a value is ``MANUFACTURER_DATA`` — the user's entry, with the source the user typed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Dict, Optional

from archforge.core.commands import Command, SetMaterial
from archforge.core.provenance import DESIGN_DEFAULT, MANUFACTURER_DATA, UNVERIFIED, VERIFIED, Rule, register

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


def _m(id_, name, category, colour, hatch, role, lam, appearance=None, insulation=False, source=_TYPICAL, note=_CHECK,
       status=UNVERIFIED):
    return BuildingMaterial(id_, name, category, colour, hatch, role, insulation, lam, status, source,
                            appearance=appearance, note=note)


def _totee(code, pick="lower"):
    """λ and source of one row of ΤΟΤΕΕ 20701-2 Πίνακας 2 (05/11, PDF from the owner — mep/totee_20701_2.py)."""
    from archforge.mep.totee_20701_2 import row_values
    v = row_values(code, pick)
    return v["conductivity"], v["source"]


_ROW = "Άλλη γραμμή του πίνακα (πυκνότητα) ή φύλλο του προϊόντος: ⓘ του υλικού."
_RANGE = "Τιμή μέσα στο εύρος του πίνακα· το ακριβές λ από το φύλλο του προϊόντος (ⓘ του υλικού)."


MATERIALS: dict[str, BuildingMaterial] = {m.id: m for m in (
    # 05/11: λ from ΤΟΤΕΕ 20701-2 Πίνακας 2 where the table gives the material (VERIFIED: exact row), our choice of row
    # (DESIGN_DEFAULT: density not known — the row nearest to the value used before, so U barely moves), or a value
    # inside the table's range (DESIGN_DEFAULT: the data sheet decides). Not in the table: UNVERIFIED, said.
    _m("cement_plaster", "Σοβάς", "Κονιάματα", "#ece6da", "plaster", "finish", _totee("1.4.2-1800")[0], source=_totee("1.4.2-1800")[1], appearance="plaster_white",
       note="", status=VERIFIED),
    _m("gypsum_board", "Γυψοσανίδα", "Ξηρά δόμηση", "#f1efea", "gypsum", "board", 0.25, "paint_white_matt",
       note="Δεν υπάρχει στον Πίνακα 2 της ΤΟΤΕΕ 20701-2 (μόνο γυψοκονιάματα 1.4.5): λ από το φύλλο της πλάκας."),
    _m("hollow_brick", "Οπτόπλινθος διάτρητος", "Τοιχοποιία", "#b5653b", "brick", "structure",
       _totee("1.7.2.2-1200")[0], source=_totee("1.7.2.2-1200")[1], appearance="brick_exposed", note=_ROW, status=DESIGN_DEFAULT),
    _m("stone_masonry", "Λιθοδομή", "Τοιχοποιία", "#9b8f7d", "stone", "structure", _totee("1.1.1.8-σκληρός")[0], source=_totee("1.1.1.8-σκληρός")[1],
       appearance="stone_cladding", note="Λίθος χωρίς αρμούς (ο πίνακας δεν δίνει λιθοδομή με κονίαμα). " + _ROW,
       status=DESIGN_DEFAULT),
    _m("reinforced_concrete", "Οπλισμένο σκυρόδεμα", "Σκυρόδεμα", "#a3a3a0", "concrete", "structure",
       _totee("1.5.3-1%")[0], source=_totee("1.5.3-1%")[1], appearance="concrete_rough", note="", status=VERIFIED),
    _m("bearing_masonry", "Φέρουσα τοιχοποιία", "Τοιχοποιία", "#a8704a", "masonry", "structure",
       _totee("1.7.2.1-1900")[0], source=_totee("1.7.2.1-1900")[1], appearance="brick_old", note="Πλήρεις οπτόπλινθοι. " + _ROW, status=DESIGN_DEFAULT),
    _m("mineral_wool", "Ορυκτοβάμβακας", "Μονώσεις", "#e8d38a", "insulation_soft", "insulation", _totee("6.1.3.2")[0], source=_totee("6.1.3.2")[1],
       insulation=True, note=_RANGE, status=DESIGN_DEFAULT),
    _m("xps", "Εξηλασμένη πολυστερίνη (XPS)", "Μονώσεις", "#9cc3d9", "insulation_rigid", "insulation", 0.034,
       insulation=True, source=_totee("6.3.4.1")[1], note=_RANGE, status=DESIGN_DEFAULT),
    _m("eps", "Διογκωμένη πολυστερίνη (EPS)", "Μονώσεις", "#e9eef0", "insulation_rigid", "insulation", 0.036,
       insulation=True, source=_totee("6.3.3.2")[1], note=_RANGE, status=DESIGN_DEFAULT),
    _m("isotex_wood_cement", "Ξυλότσιμεντο Isotex", "Δομικά συστήματα", "#b9a98c", "wood_cement", "structure", 0.11,
       source=_ISOTEX, note="ΤΟΤΕΕ 20701-2 Πίν. 2 · 6.3.1 (ξυλόμαλλο, d ≥ 25 mm): 0,090–0,100 — η τιμή του "
                            "κατασκευαστή είναι πάνω από το εύρος· κρατιέται (δυσμενέστερη) ως την επιβεβαίωση."),
    _m("isotex_graphite_eps", "EPS γραφίτη (Neopor®)", "Δομικά συστήματα", "#6f7780", "insulation_rigid", "insulation",
       0.031, insulation=True, source=_ISOTEX,
       note="ΤΟΤΕΕ 20701-2 Πίν. 2 · 6.3.3.3: 0,030–0,032 — η τιμή του κατασκευαστή είναι μέσα στο εύρος."),
    _m("infill_concrete", "Σκυρόδεμα πλήρωσης", "Σκυρόδεμα", "#a3a3a0", "concrete", "structure", _totee("1.5.3-1%")[0], source=_totee("1.5.3-1%")[1],
       note="", status=VERIFIED),
    _m("icf_eps", "EPS καλουπιού ICF", "Δομικά συστήματα", "#e9eef0", "insulation_rigid", "insulation", 0.036,
       insulation=True, source=_totee("6.3.3.2")[1], note=_RANGE, status=DESIGN_DEFAULT),
    _m("icf_core_concrete", "Σκυρόδεμα πυρήνα ICF", "Σκυρόδεμα", "#a3a3a0", "concrete", "structure",
       _totee("1.5.3-1%")[0], source=_totee("1.5.3-1%")[1], note="", status=VERIFIED),
)}

register(*(Rule(f"materials.{m.id}.conductivity",
                f"λ {m.name} = {m.conductivity:g} W/mK για το ενδεικτικό U των συνθέσεων τοίχου",
                m.conductivity_status,
                source=m.conductivity_source if m.conductivity_status == VERIFIED else "",
                note=f"{m.conductivity_source}. {m.note}".strip())
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
