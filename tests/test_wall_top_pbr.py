import math

import pytest

from archforge.ui.wall_top_pbr import wall_top_pbr_handles


def test_pbr_handle_contract_preserves_semantic_identity_and_world_center():
    handles = [
        {
            "handle_id": "wall-top:wall-7:start",
            "entity_id": "wall-7",
            "endpoint": "start",
            "position": [1.25, -3.5, 2.8],
            "preview": False,
        },
        {
            "handle_id": "wall-top:wall-7:end",
            "entity_id": "wall-7",
            "endpoint": "end",
            "position": [4.0, 0.5, 3.4],
            "preview": True,
        },
    ]

    rendered = wall_top_pbr_handles(handles, radius=0.125)

    assert rendered == [
        {
            "handle_id": "wall-top:wall-7:start",
            "center": [1.25, -3.5, 2.8],
            "radius": 0.125,
            "preview": False,
            "pickable": True,
        },
        {
            "handle_id": "wall-top:wall-7:end",
            "center": [4.0, 0.5, 3.4],
            "radius": 0.125,
            "preview": True,
            "pickable": True,
        },
    ]
    assert all("entity_id" not in item and "endpoint" not in item for item in rendered)


def test_pbr_handle_contract_rejects_duplicate_renderer_identity():
    duplicate = {
        "handle_id": "wall-top:wall-7:start",
        "position": [0.0, 0.0, 2.4],
    }
    with pytest.raises(ValueError, match="unique"):
        wall_top_pbr_handles([duplicate, dict(duplicate)])


def test_pbr_handle_contract_rejects_nonpositive_radius():
    with pytest.raises(ValueError, match="> 0"):
        wall_top_pbr_handles([], radius=0.0)


@pytest.mark.parametrize("bad_radius", [math.nan, math.inf, -math.inf])
def test_pbr_handle_contract_rejects_nonfinite_radius(bad_radius):
    with pytest.raises(ValueError, match="finite"):
        wall_top_pbr_handles([], radius=bad_radius)


@pytest.mark.parametrize(
    "bad_position",
    ([math.nan, 0.0, 2.4], [0.0, math.inf, 2.4], [0.0, 0.0, -math.inf]),
)
def test_pbr_handle_contract_rejects_nonfinite_world_center(bad_position):
    with pytest.raises(ValueError, match="position must be finite"):
        wall_top_pbr_handles(
            [{"handle_id": "wall-top:wall-7:start", "position": bad_position}]
        )
