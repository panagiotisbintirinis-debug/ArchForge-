"""Wall assemblies: layered build-ups that set a wall's thickness and look.

Layers are listed from the exterior face (wall side A, the +normal side of
the wall line) to the interior face.  Choosing a type sets the wall's
thickness to the sum of its layers; the wall's centre line stays put.

The U-value shown is INDICATIVE only: the EN ISO 6946 sum of layer
resistances d/λ plus surface resistances Rsi = 0.13, Rse = 0.04 m²K/W, using
typical λ values listed here.  It ignores thermal bridges, studs, moisture
and product data, so it is not a verified energy calculation (e.g. KENAK).
"""
import math

RSI, RSE = 0.13, 0.04

# name, thickness (m), λ (W/mK, typical), colour, insulation?
_PLASTER = ("Σοβάς", 0.02, 0.87, "#ece6da", False)
_GYPSUM = ("Γυψοσανίδα", 0.0125, 0.25, "#f1efea", False)
_BRICK = ("Οπτόπλινθος διάτρητος", 0.09, 0.47, "#b5653b", False)
_STONE = ("Λιθοδομή", 0.50, 1.70, "#9b8f7d", False)
_CONCRETE = ("Οπλισμένο σκυρόδεμα", 0.25, 2.30, "#a3a3a0", False)
_BEARING_MASONRY = ("Φέρουσα τοιχοποιία", 0.25, 0.80, "#a8704a", False)


def _wool(d):
    return ("Ορυκτοβάμβακας", d, 0.037, "#e8d38a", True)


def _xps(d):
    return ("Εξηλασμένη πολυστερίνη (XPS)", d, 0.034, "#9cc3d9", True)


def _eps(d):
    return ("Διογκωμένη πολυστερίνη (EPS)", d, 0.036, "#e9eef0", True)


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


def layers(wall_type):
    entry = WALL_TYPES.get(str(wall_type))
    return list(entry[1]) if entry and entry[1] else []


def total_thickness(wall_type):
    return sum(layer[1] for layer in layers(wall_type))


def indicative_u(wall_type):
    """Indicative U (W/m²K) from typical λ values, or None for generic walls."""
    ls = layers(wall_type)
    if not ls:
        return None
    r = RSI + RSE + sum(d / lam for _n, d, lam, _c, _i in ls)
    return 1.0 / r


def face_colors(wall_type):
    """(exterior face colour, interior face colour) of the finishing layers."""
    ls = layers(wall_type)
    if not ls:
        return None
    return ls[0][3], ls[-1][3]


def layer_lines(params, wall_type):
    """Plan lines at internal layer boundaries: ``[(points, is_insulation_boundary)]``."""
    ls = layers(wall_type)
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
