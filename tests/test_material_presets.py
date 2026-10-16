"""Built-in material catalog: Greek names, valid PBR values, stable ids."""
import re

from archforge.rendering.materials import (
    MATERIAL_PRESETS,
    MATERIAL_USES,
    material_categories,
    material_spec,
    materials_for_use,
    materials_in_category,
)

# Ids that existed before the Greek catalog; saved projects store them.
LEGACY_IDS = (
    "plaster_white", "plaster_warm", "paint_charcoal",
    "concrete_smooth", "concrete_rough", "limestone_light", "stone_dark",
    "wood_oak", "wood_walnut", "wood_weathered",
    "ceramic_light", "terracotta", "slate_tile",
    "steel_brushed", "steel_black", "aluminium", "copper",
    "roof_clay", "roof_membrane_dark", "zinc_seam",
)


def test_catalog_size_and_legacy_ids_kept():
    assert 140 <= len(MATERIAL_PRESETS) <= 180
    for material_id in LEGACY_IDS:
        assert material_id in MATERIAL_PRESETS, material_id
    assert re.fullmatch(r"[a-z0-9_]+", "".join(MATERIAL_PRESETS)) is not None


def test_every_spec_is_valid_pbr():
    for material_id, spec in MATERIAL_PRESETS.items():
        assert re.fullmatch(r"#[0-9a-f]{6}", spec["color"]), material_id
        assert 0.0 <= spec["roughness"] <= 1.0, material_id
        assert 0.0 <= spec["metalness"] <= 1.0, material_id
        assert 0.0 < spec.get("opacity", 1.0) <= 1.0, material_id
        assert spec["use"] and set(spec["use"]) <= set(MATERIAL_USES), material_id


def test_names_and_categories_are_greek():
    # Latin letters only inside a RAL colour code (e.g. "RAL 7016").
    for material_id, spec in MATERIAL_PRESETS.items():
        for text in (spec["name"], spec["category"]):
            assert not re.search(r"[A-Za-z]", re.sub(r"RAL \d{4}", "", text)), (material_id, text)
            assert re.search(r"[Ͱ-Ͽἀ-῿]", text), (material_id, text)
    names = [spec["name"] for spec in MATERIAL_PRESETS.values()]
    assert len(names) == len(set(names))


def test_categories_ordered_and_populated():
    cats = material_categories()
    assert cats[0] == "Χρώματα & σοβάδες"
    assert "Θερμοπρόσοψη & επενδύσεις" in cats
    assert sum(len(materials_in_category(c)) for c in cats) == len(MATERIAL_PRESETS)
    for category in cats:
        assert len(materials_in_category(category)) >= 3, category


def test_filter_by_use():
    facade = dict(materials_for_use("πρόσοψη"))
    assert "etics_white" in facade and "wood_oak" not in facade
    assert "alu_ral7016" in dict(materials_for_use("κούφωμα"))
    for use in MATERIAL_USES:
        assert materials_for_use(use), use


def test_glass_opacity_reaches_the_renderer():
    from types import SimpleNamespace

    from archforge.core.model import Document, Entity
    from archforge.geometry.mesh import MeshPayload
    from archforge.rendering.scene import build_pbr_scene_payload

    assert material_spec("glass_clear")["opacity"] < 1.0
    mesh = MeshPayload(
        vertices=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 0.0, 3.0)),
        triangles=((0, 1, 2),),
        triangle_surfaces=("front",),
    )
    evaluation = SimpleNamespace(bodies=(SimpleNamespace(entity_id="w", semantic_kind="wall", payload=mesh),))
    doc = Document()
    doc.add(Entity('wall', {
        'x1': 0.0, 'y1': 0.0, 'x2': 2.0, 'y2': 0.0,
        'z': 0.0, 'height': 3.0, 'thickness': 0.15,
        'material_id': 'glass_clear',
    }, id='w'))
    material = build_pbr_scene_payload(evaluation, doc=doc)['objects'][0]['material']
    assert material['material_name'] == 'Γυαλί διαφανές'
    assert material['opacity'] == MATERIAL_PRESETS['glass_clear']['opacity']
