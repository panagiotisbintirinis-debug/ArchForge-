from archforge.architecture.roof_clip import open_parts


def _area(p):
    return abs(sum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p)))) / 2


def test_half_covered_room_keeps_the_open_half():
    room = [(0, 0), (5, 0), (5, 8), (0, 8)]
    parts = open_parts(room, [[(0, 4), (5, 4), (5, 8), (0, 8)]])
    assert len(parts) == 1 and abs(_area(parts[0]) - 20) < 1e-9


def test_l_shaped_open_part_is_one_outline():
    room = [(0, 0), (10, 0), (10, 8), (0, 8)]
    parts = open_parts(room, [[(0, 4), (5, 4), (5, 8), (0, 8)]])
    assert len(parts) == 1 and len(parts[0]) == 6 and abs(_area(parts[0]) - 60) < 1e-9


def test_terrace_round_a_smaller_upper_floor_is_rectangles():
    room = [(0, 0), (10, 0), (10, 10), (0, 10)]
    parts = open_parts(room, [[(3, 3), (7, 3), (7, 7), (3, 7)]])
    assert len(parts) > 1 and abs(sum(_area(p) for p in parts) - 84) < 1e-9


def test_nothing_above_or_all_covered():
    room = [(0, 0), (4, 0), (4, 4), (0, 4)]
    assert open_parts(room, []) is None
    assert open_parts(room, [[(-1, -1), (5, -1), (5, 5), (-1, 5)]]) == []
