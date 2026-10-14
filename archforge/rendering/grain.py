"""Surface grain: which procedural texture a derived mesh wears in the 3D view.

Plaster, concrete, timber, roof tiles, metal and soil are generated in the
page (archforge/ui/pbr_look_js.py) as colour-variation, normal and roughness
maps at real size, so no image files are needed and nothing is downloaded.
The grain is render state only: it is derived from the kind and the material
the Document already stores and is never saved.
"""
from __future__ import annotations

from typing import Mapping, Optional

GRAINS = ("plaster", "concrete", "wood", "roof_tile", "metal", "soil", "grass", "fabric", "smooth")

# Material library categories (rendering/materials.py) -> grain.
_CATEGORY_GRAIN = {
    "Χρώματα & σοβάδες": "plaster",
    "Θερμοπρόσοψη & επενδύσεις": "plaster",
    "Σκυρόδεμα": "concrete",
    "Ξύλα": "wood",
    "Μέταλλα & κουφώματα": "metal",
    "Υφάσματα & δέρματα": "fabric",
    "Μελαμίνες": "smooth",
    "Πάγκοι κουζίνας": "smooth",
}

_ID_GRAIN = (
    ("wood_cladding", "wood"), ("wpc_", "wood"), ("acm_", "metal"), ("fibre_cement", "concrete"),
    ("roof_tile", "roof_tile"), ("roof_clay", "roof_tile"), ("zinc_", "metal"),
    ("roof_membrane", "concrete"), ("roof_gravel", "concrete"), ("roof_slate", "concrete"),
    ("garden_lawn", "grass"), ("garden_gravel", "concrete"), ("garden_pebbles", "concrete"),
    ("garden_deck", "wood"), ("floor_parquet", "wood"), ("floor_laminate", "wood"),
    ("floor_vinyl", "wood"), ("floor_carpet", "fabric"), ("lacquer", "smooth"),
)

# Default look of a kind when no library material is set.
_KIND_GRAIN = {
    "wall": "plaster", "roof_gable": "plaster", "room_ceiling": "plaster",
    "drywall_ceiling": "plaster",
    "room_floor": "concrete", "floor": "concrete", "room_foundation": "concrete",
    "room_roof": "concrete", "structural_column": "concrete", "structural_beam": "concrete",
    "stair": "concrete", "ramp": "concrete", "site_path": "concrete", "railing_base": "concrete",
    "terrain": "soil",
    "roof_tiles": "roof_tile",
    "door_frame": "wood", "door_leaf": "wood", "plant_trunk": "wood", "arboreal_branch": "wood",
    "roof_plate": "wood", "roof_ridge": "wood", "roof_hip": "wood", "roof_rafter": "wood",
    "roof_batten": "wood", "roof_counter_batten": "wood", "roof_boarding": "wood",
    "ceiling_joists": "wood",
}


def surface_grain(kind: str, material: Mapping, role: Optional[str] = None) -> Optional[str]:
    """Grain for a derived mesh of ``kind`` (``role``: roof/wall surface role).

    ``None`` = no texture: glass, patterned stone/tile (its own joints) and
    anything metallic or see-through keeps the plain PBR surface.
    """
    if material.get("pattern_key") or float(material.get("opacity", 1.0)) < 1.0:
        return None
    material_id = str(material.get("material_id") or "")
    if material_id:
        for prefix, grain in _ID_GRAIN:
            if material_id.startswith(prefix):
                return grain
        from archforge.rendering.materials import MATERIAL_PRESETS
        preset = MATERIAL_PRESETS.get(material_id)
        if preset is not None:
            grain = _CATEGORY_GRAIN.get(str(preset.get("category")))
            if grain:
                return grain
    if float(material.get("metalness", 0.0)) >= 0.5:
        return "metal"
    if kind == "pitched_roof" and role:
        return _KIND_GRAIN.get("roof_tiles" if role == "tiles" else f"roof_{role}")
    return _KIND_GRAIN.get(kind) or (_KIND_GRAIN.get(role) if role else None)
