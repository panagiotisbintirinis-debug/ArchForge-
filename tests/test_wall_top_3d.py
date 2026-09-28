import pytest

from archforge.core.wall_top_3d import (
    vertical_height_from_ray,
    wall_top_endpoint_world,
)


def _wall(**changes):
    params = {
        'x1': 1.0, 'y1': 2.0, 'z': 0.4,
        'x2': 4.0, 'y2': 6.0,
        'height': 3.0, 'thickness': 0.2,
    }
    params.update(changes)
    return params


def test_endpoint_world_positions_preserve_semantic_start_end_on_rotated_wall():
    wall = _wall(start_height=2.25, end_height=4.5)
    assert wall_top_endpoint_world(wall, 'start') == pytest.approx((1.0, 2.0, 2.65))
    assert wall_top_endpoint_world(wall, 'end') == pytest.approx((4.0, 6.0, 4.9))


def test_endpoint_world_positions_keep_legacy_uniform_height_compatible():
    wall = _wall()
    assert wall_top_endpoint_world(wall, 'start')[2] == pytest.approx(3.4)
    assert wall_top_endpoint_world(wall, 'end')[2] == pytest.approx(3.4)


def test_perspective_ray_maps_to_vertical_endpoint_edit_line():
    # Ray from (0,0,5) through (2,2,3): at endpoint XY (2,2) its Z is 3.
    height = vertical_height_from_ray(
        base_z=0.5,
        endpoint_xy=(2.0, 2.0),
        ray_origin=(0.0, 0.0, 5.0),
        ray_direction=(2.0, 2.0, -2.0),
    )
    assert height == pytest.approx(2.5)


def test_3d_height_mapping_is_independent_of_wall_axis_alignment():
    # The helper receives the semantic endpoint position, not an X/Y wall class.
    height = vertical_height_from_ray(
        base_z=0.25,
        endpoint_xy=(4.0, 6.0),
        ray_origin=(1.0, 1.0, 6.0),
        ray_direction=(3.0, 5.0, -3.0),
    )
    assert height == pytest.approx(2.75)


def test_parallel_vertical_ray_is_rejected_instead_of_guessing_height():
    with pytest.raises(ValueError, match='parallel'):
        vertical_height_from_ray(0.0, (1.0, 2.0), (1.0, 2.0, 5.0), (0.0, 0.0, -1.0))


def test_drag_cannot_move_top_below_wall_base():
    with pytest.raises(ValueError, match='above base'):
        vertical_height_from_ray(
            base_z=1.0,
            endpoint_xy=(2.0, 2.0),
            ray_origin=(0.0, 0.0, 0.5),
            ray_direction=(2.0, 2.0, 0.0),
        )
