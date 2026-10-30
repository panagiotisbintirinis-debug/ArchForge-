"""Building materials registry (wall layers, spec §3 step 1): one source for λ, density, hatch and look."""
import pytest

from archforge.architecture.wall_types import WALL_TYPES, indicative_u, layer_materials, layers
from archforge.construction.building_materials import (BUILDING_MATERIALS, HATCHES, building_material,
                                                       building_material_rules, layer)
from archforge.core.provenance import DESIGN_DEFAULT, UNVERIFIED, VERIFIED, rules
from archforge.rendering.materials import MATERIAL_PRESETS


def test_every_wall_layer_points_at_a_registry_material_with_the_same_values():
    for key in WALL_TYPES:
        for row, mid in zip(layers(key), layer_materials(key)):
            m = BUILDING_MATERIALS[mid]
            name, _d, lam, color, insulation = row             # old 5-tuple shape still unpacks
            assert (name, lam, color, insulation) == (m.name, m.conductivity, m.color, m.insulation)
            assert row.material_id == mid


def test_registry_entries_are_complete_and_honest():
    for mid, m in BUILDING_MATERIALS.items():
        assert m.id == mid and m.name and m.category
        assert m.conductivity > 0 and (m.density is None or m.density > 0)
        assert m.hatch in HATCHES
        assert m.appearance is None or m.appearance in MATERIAL_PRESETS
        assert m.cost is None                                   # a price is the user's, never ours
        assert m.status in (UNVERIFIED, DESIGN_DEFAULT)         # typical values, nothing verified
        assert m.status != VERIFIED


def test_material_values_are_registered_in_provenance():
    ids = {r.id for r in rules("building_materials.")}
    assert {r.id for r in building_material_rules()} <= ids
    assert "building_materials.conductivity" in ids and "building_materials.density" in ids
    assert all(r.status != VERIFIED for r in building_material_rules())


def test_layer_helper_and_lookup():
    row = layer("concrete_reinforced", 0.25)
    assert row[1] == 0.25 and row.material_id == "concrete_reinforced"
    assert building_material("concrete_reinforced").conductivity == pytest.approx(2.30)
    assert building_material("nope") is None
    with pytest.raises(KeyError):
        layer("nope", 0.1)


def test_indicative_u_unchanged_by_the_registry():
    # Same λ as before the registry (values moved, not changed).
    assert indicative_u("brick_double_insulated") == pytest.approx(
        1 / (0.13 + 0.04 + 2 * 0.02 / 0.87 + 2 * 0.09 / 0.47 + 0.05 / 0.034))
    assert layer_materials("generic") == []
