import pytest

from archforge.rendering.sun import sun_direction, sun_position


def test_noon_sun_is_due_south_and_high_in_june_low_in_december():
    el_jun, az_jun = sun_position(12.0, 6)
    el_dec, az_dec = sun_position(12.0, 12)
    assert az_jun == pytest.approx(180.0, abs=0.5) and az_dec == pytest.approx(180.0, abs=0.5)
    assert el_jun == pytest.approx(90 - 38 + 23.3, abs=1.0)
    assert el_dec == pytest.approx(90 - 38 - 23.3, abs=1.0)


def test_morning_sun_is_east_evening_sun_is_west_and_night_is_below_horizon():
    assert 60 < sun_position(8.0, 6)[1] < 120
    assert 240 < sun_position(16.0, 6)[1] < 300
    assert sun_position(0.0, 6)[0] < 0


def test_direction_vector():
    x, y, z = sun_direction(30.0, 180.0)
    assert (round(x, 6), round(y, 6), round(z, 6)) == (0.0, round(-0.8660254, 6), 0.5)
    with pytest.raises(ValueError):
        sun_position(12.0, 13)
