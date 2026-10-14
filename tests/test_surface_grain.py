from archforge.rendering.grain import GRAINS, surface_grain


def test_grain_follows_material_then_kind():
    assert surface_grain('wall', {'material_id': 'plaster_white'}) == 'plaster'
    assert surface_grain('wall', {}) == 'plaster'
    assert surface_grain('terrain', {}) == 'soil'
    assert surface_grain('pitched_roof', {}, 'tiles') == 'roof_tile'
    assert surface_grain('door', {}, 'door_leaf') == 'wood'
    assert surface_grain('wall', {'material_id': 'garden_lawn'}) == 'grass'


def test_glass_and_patterned_surfaces_keep_their_own_look():
    assert surface_grain('window', {'opacity': 0.3}, 'window_glass') is None
    assert surface_grain('wall', {'material_id': 'stone_pelion', 'pattern_key': 'k'}) is None


def test_every_grain_is_known():
    for kind in ('wall', 'terrain', 'room_floor', 'structural_beam'):
        assert surface_grain(kind, {}) in GRAINS
