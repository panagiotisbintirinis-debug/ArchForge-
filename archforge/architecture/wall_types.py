"""Wall assemblies: layered build-ups that set a wall's thickness and look.

Layers are listed from the exterior face (wall side A, the +normal side of
the wall line) to the interior face.  Choosing a type sets the wall's
thickness to the sum of its layers; the wall's centre line stays put.

The U-value shown is INDICATIVE only: the EN ISO 6946 sum of layer
resistances d/λ plus surface resistances Rsi = 0.13, Rse = 0.04 m²K/W.  Each
layer is made of a building material (``construction/building_materials.py``)
whose λ is a typical, unverified value unless the project entered the data
sheet's λ.  It ignores thermal bridges, studs and moisture, so it is not a
verified energy calculation (e.g. KENAK).
"""
import math

RSI, RSE = 0.13, 0.04


class Layer(tuple):
    """``(name, thickness m, λ W/mK, colour, insulation?)`` of one layer, plus the building-material id it is made of
    (``construction/building_materials.py``) — every reader that unpacks the five fields keeps working."""

    def __new__(cls, material_id, thickness, doc=None):
        from archforge.construction.building_materials import material
        m = material(material_id, doc)
        if m is None:
            raise KeyError(f"unknown building material {material_id}")
        self = super().__new__(cls, (m.name, float(thickness), m.conductivity, m.colour, m.insulation))
        self.material_id = m.id
        return self

    def __reduce__(self):
        return (Layer, (self.material_id, self[1]))

    def with_doc(self, doc):
        """The same layer with the project's data-sheet values (λ) of its material."""
        return Layer(self.material_id, self[1], doc)


_PLASTER = Layer("cement_plaster", 0.02)
_GYPSUM = Layer("gypsum_board", 0.0125)
_BRICK = Layer("hollow_brick", 0.09)
_STONE = Layer("stone_masonry", 0.50)
_CONCRETE = Layer("reinforced_concrete", 0.25)
_BEARING_MASONRY = Layer("bearing_masonry", 0.25)


def _wool(d):
    return Layer("mineral_wool", d)


def _xps(d):
    return Layer("xps", d)


def _eps(d):
    return Layer("eps", d)


WALL_TYPES = {
    "generic": ("Γενικός (χωρίς σύνθεση)", None),
    "drywall_100": ("Γυψοσανίδα 10 cm (μονή, με ορυκτοβάμβακα)", [_GYPSUM, _wool(0.075), _GYPSUM]),
    "drywall_double_125": ("Γυψοσανίδα 12,5 cm (διπλή, ηχομόνωση)", [_GYPSUM, _GYPSUM, _wool(0.075), _GYPSUM, _GYPSUM]),
    "brick_partition": ("Τούβλο 13 cm χωρίς μόνωση (εσωτερικός)", [_PLASTER, _BRICK, _PLASTER]),
    "brick_double_insulated": ("Διπλή τοιχοποιία με μόνωση 5 cm (εξωτερικός)", [_PLASTER, _BRICK, _xps(0.05), _BRICK, _PLASTER]),
    "stone_uninsulated": ("Πετροκτιστός 54 cm χωρίς μόνωση", [_PLASTER, _STONE, _PLASTER]),
    "stone_insulated": ("Πετροκτιστός με εσωτερική μόνωση 5 cm", [_PLASTER, _STONE, _wool(0.05), _GYPSUM]),
    "bearing_interior_25": ("Φέρων εσωτερικός τοίχος 25 cm + σοβάδες", [_PLASTER, _BEARING_MASONRY, _PLASTER]),
    "concrete_etics": ("Μπετό με εξωτερική θερμοπρόσοψη 8 cm", [_PLASTER, _eps(0.08), _CONCRETE, _PLASTER]),
}
# Isotex wood-cement formwork blocks (construction/isotex.py): with or without a graphite EPS insert.
from archforge.construction.isotex import wall_type_layers as _isotex_layers  # noqa: E402
WALL_TYPES.update(_isotex_layers())
# ICF: EPS formwork blocks on both faces with a concrete core (construction/icf.py).
from archforge.construction.icf import wall_type_layers as _icf_layers  # noqa: E402
WALL_TYPES.update(_icf_layers())


# «Γυάλινος τοίχος» from the wall tool's menu (owner 29/10): an ordinary wall with the clear glass material, so it is
# see-through in 3D and counted as glass.  Thickness = DESIGN_DEFAULT (a glass pane in its profile), changeable in
# Ιδιότητες; no U-value or structural claim is made for it.
GLASS_WALL = {"thickness": 0.05, "material_id": "glass_clear", "label": "Γυάλινος τοίχος (διάφανος)"}


def layers(wall_type, doc=None):
    """The type's layers, exterior first; with ``doc`` the project's data-sheet λ of each material applies."""
    entry = WALL_TYPES.get(str(wall_type))
    out = list(entry[1]) if entry and entry[1] else []
    return [layer.with_doc(doc) for layer in out] if doc is not None else out


def layer_materials(wall_type, doc=None):
    """``[(building material, thickness m)]`` of the type, exterior first."""
    from archforge.construction.building_materials import material
    return [(material(layer.material_id, doc), layer[1]) for layer in layers(wall_type)]


def total_thickness(wall_type):
    return sum(layer[1] for layer in layers(wall_type))


def indicative_u(wall_type, doc=None):
    """Indicative U (W/m²K) from the layers' λ (the project's data-sheet values with ``doc``), or None for generic
    walls (a block's published U when known)."""
    from archforge.construction.isotex import BLOCKS, code_of_wall_type
    code = code_of_wall_type(wall_type)
    if code and BLOCKS[code][6] is not None:
        return BLOCKS[code][6]
    ls = layers(wall_type, doc)
    if not ls:
        return None
    r = RSI + RSE + sum(d / lam for _n, d, lam, _c, _i in ls)
    return 1.0 / r


def face_colors(wall_type, sign=1):
    """(side A colour, side B colour) of the finishing layers; ``sign`` −1 = side B faces outside
    (``wall_face.outside_sign``): the assembly's exterior layer is on side B."""
    ls = layers(wall_type)
    if not ls:
        return None
    return (ls[0][3], ls[-1][3]) if sign >= 0 else (ls[-1][3], ls[0][3])


def layer_lines(params, wall_type, sign=1):
    """Plan lines at internal layer boundaries: ``[(points, is_insulation_boundary)]`` (``sign`` as ``face_colors``)."""
    ls = layers(wall_type)
    if sign < 0:
        ls = list(reversed(ls))                   # the exterior layers on side B
    if len(ls) < 2:
        return []
    x1, y1, x2, y2 = (float(params[k]) for k in ("x1", "y1", "x2", "y2"))
    length = math.hypot(x2 - x1, y2 - y1)
    if length < 1e-9:
        return []
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    nx, ny = -uy, ux
    t = float(params["thickness"])
    total = sum(layer[1] for layer in ls)
    scale = t / total if total > 0 else 1.0       # follow the wall's actual thickness
    out, offset = [], t / 2
    for k in range(len(ls) - 1):
        offset -= ls[k][1] * scale
        insulation = ls[k][4] or ls[k + 1][4]
        out.append(([(x1 + nx * offset, y1 + ny * offset), (x2 + nx * offset, y2 + ny * offset)], insulation))
    return out
