import math

import pytest

from archforge.geometry.wall_detail import detailed_wall_geometry, wall_height_at, wall_top_heights


def _wall(**changes):
    params = {
        'x1': 1.0, 'y1': 2.0, 'z': 0.4,
        'x2': 5.0, 'y2': 2.0,
        'height': 3.0, 'thickness': 0.2,
    }
    params.update(changes)
    return params


def _top_vertices(params):
    vertices, triangles, roles = detailed_wall_geometry(params, target_step=0.5)
    indices = {i for tri, role in zip(triangles, roles) if role == 'top' for i in tri}
    return [vertices[i] for i in indices]


def test_legacy_uniform_wall_profile_is_backward_compatible():
    params = _wall()
    assert wall_top_heights(params) == (3.0, 3.0)
    assert wall_height_at(params, 2.0) == pytest.approx(3.0)
    assert {round(v[2], 9) for v in _top_vertices(params)} == {3.4}


def test_endpoint_heights_create_linear_semantic_sloped_top():
    params = _wall(start_height=2.0, end_height=4.0)
    assert wall_top_heights(params) == (2.0, 4.0)
    assert wall_height_at(params, 0.0) == pytest.approx(2.0)
    assert wall_height_at(params, 2.0) == pytest.approx(3.0)
    assert wall_height_at(params, 4.0) == pytest.approx(4.0)

    top = _top_vertices(params)
    start_z = [z for x, y, z in top if math.isclose(x, 1.0)]
    middle_z = [z for x, y, z in top if math.isclose(x, 3.0)]
    end_z = [z for x, y, z in top if math.isclose(x, 5.0)]
    assert start_z and all(z == pytest.approx(2.4) for z in start_z)
    assert middle_z and all(z == pytest.approx(3.4) for z in middle_z)
    assert end_z and all(z == pytest.approx(4.4) for z in end_z)


def test_reverse_slope_keeps_endpoint_identity():
    params = _wall(start_height=4.0, end_height=2.0)
    assert wall_height_at(params, 1.0) == pytest.approx(3.5)
    assert wall_height_at(params, 3.0) == pytest.approx(2.5)


def test_endpoint_heights_must_remain_positive_and_finite():
    with pytest.raises(ValueError):
        detailed_wall_geometry(_wall(start_height=0.0))
    with pytest.raises(ValueError):
        detailed_wall_geometry(_wall(end_height=float('nan')))
