from __future__ import annotations

from typing import Dict, Mapping


# Built-in ArchForge surface library.
#
# These are intentionally texture-free PBR presets. A material id is stored on
# the authoritative entity, while this catalog provides stable visual defaults.
# Later texture maps can be added to the same records without changing projects.
MATERIAL_PRESETS: Dict[str, dict] = {
    # Paint & plaster
    "plaster_white": {
        "name": "White Plaster",
        "category": "Paint & Plaster",
        "color": "#e6e1d7",
        "roughness": 0.82,
        "metalness": 0.00,
    },
    "plaster_warm": {
        "name": "Warm Mineral Plaster",
        "category": "Paint & Plaster",
        "color": "#d4c2a6",
        "roughness": 0.86,
        "metalness": 0.00,
    },
    "paint_charcoal": {
        "name": "Charcoal Paint",
        "category": "Paint & Plaster",
        "color": "#44484b",
        "roughness": 0.72,
        "metalness": 0.00,
    },

    # Concrete & masonry
    "concrete_smooth": {
        "name": "Smooth Concrete",
        "category": "Concrete & Masonry",
        "color": "#aaa9a3",
        "roughness": 0.76,
        "metalness": 0.00,
    },
    "concrete_rough": {
        "name": "Rough Concrete",
        "category": "Concrete & Masonry",
        "color": "#989993",
        "roughness": 0.94,
        "metalness": 0.00,
    },
    "limestone_light": {
        "name": "Light Limestone",
        "category": "Concrete & Masonry",
        "color": "#c8bea6",
        "roughness": 0.84,
        "metalness": 0.00,
    },
    "stone_dark": {
        "name": "Dark Stone",
        "category": "Concrete & Masonry",
        "color": "#5b5c58",
        "roughness": 0.88,
        "metalness": 0.00,
    },

    # Wood
    "wood_oak": {
        "name": "Natural Oak",
        "category": "Wood",
        "color": "#b98755",
        "roughness": 0.64,
        "metalness": 0.00,
    },
    "wood_walnut": {
        "name": "Walnut",
        "category": "Wood",
        "color": "#6b4632",
        "roughness": 0.66,
        "metalness": 0.00,
    },
    "wood_weathered": {
        "name": "Weathered Timber",
        "category": "Wood",
        "color": "#817667",
        "roughness": 0.88,
        "metalness": 0.00,
    },

    # Tile & ceramic
    "ceramic_light": {
        "name": "Light Ceramic Tile",
        "category": "Tile & Ceramic",
        "color": "#d9d7cf",
        "roughness": 0.36,
        "metalness": 0.00,
    },
    "terracotta": {
        "name": "Terracotta",
        "category": "Tile & Ceramic",
        "color": "#a9583d",
        "roughness": 0.78,
        "metalness": 0.00,
    },
    "slate_tile": {
        "name": "Slate Tile",
        "category": "Tile & Ceramic",
        "color": "#555c61",
        "roughness": 0.70,
        "metalness": 0.01,
    },

    # Metal
    "steel_brushed": {
        "name": "Brushed Steel",
        "category": "Metal",
        "color": "#aeb5b9",
        "roughness": 0.34,
        "metalness": 0.82,
    },
    "steel_black": {
        "name": "Black Steel",
        "category": "Metal",
        "color": "#33383d",
        "roughness": 0.44,
        "metalness": 0.78,
    },
    "aluminium": {
        "name": "Aluminium",
        "category": "Metal",
        "color": "#c5c9ca",
        "roughness": 0.30,
        "metalness": 0.88,
    },
    "copper": {
        "name": "Copper",
        "category": "Metal",
        "color": "#a75f3d",
        "roughness": 0.38,
        "metalness": 0.84,
    },

    # Roofing / exterior
    "roof_clay": {
        "name": "Clay Roof Tile",
        "category": "Roofing & Exterior",
        "color": "#8d4b36",
        "roughness": 0.82,
        "metalness": 0.00,
    },
    "roof_membrane_dark": {
        "name": "Dark Flat-Roof Membrane",
        "category": "Roofing & Exterior",
        "color": "#42474b",
        "roughness": 0.90,
        "metalness": 0.00,
    },
    "zinc_seam": {
        "name": "Standing-Seam Zinc",
        "category": "Roofing & Exterior",
        "color": "#808b90",
        "roughness": 0.48,
        "metalness": 0.72,
    },
}


def material_categories():
    return tuple(sorted({str(spec["category"]) for spec in MATERIAL_PRESETS.values()}))


def materials_in_category(category: str):
    category = str(category)
    return tuple(
        (material_id, dict(spec))
        for material_id, spec in MATERIAL_PRESETS.items()
        if spec.get("category") == category
    )


def material_spec(material_id: str | None) -> Mapping[str, object] | None:
    if not material_id:
        return None
    spec = MATERIAL_PRESETS.get(str(material_id))
    return None if spec is None else dict(spec)
