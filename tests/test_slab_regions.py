"""Plan regions with holes (slab outline): union, difference, offset, watertight prism."""
import pytest

from archforge.geometry.mesh import MeshPayload
from archforge.geometry.mesh_validation import validate_mesh
from archforge.geometry.regions import islands_area, offset_loop, prism_with_holes, region, signed_area

ROOM1 = [(0, 0), (4.5, 0), (4.5, 5), (0, 5)]
# Owner's screenshot: a room with a slanted wall that starts on Room 1's bottom wall, and a block up-right.
ROOM2 = [(2.2, 0), (5, -2.8), (9.3, -2.25), (9.3, 6.5), (4.2, 6.5), (4.2, 5.9), (4.5, 5), (4.5, 0)]


def test_union_of_rooms_sharing_split_edges_is_one_island():
    islands = region([ROOM1, ROOM2])
    assert len(islands) == 1 and islands[0][1] == []
    assert islands_area(islands) == pytest.approx(abs(signed_area(ROOM1)) + abs(signed_area(ROOM2)))


def test_holes_inside_and_across_the_outline():
    hole = [(5.5, 1), (7.5, 1), (7.5, 3), (6.5, 4), (5.5, 3)]           # non-convex-free pentagon inside
    notch = [(8, 4), (10, 4), (10, 5), (8, 5)]                            # crosses the outer wall: a notch
    l_hole = [(1, 1), (3, 1), (3, 2), (2, 2), (2, 3), (1, 3)]             # L-shaped (non-convex) hole
    islands = region([ROOM1, ROOM2], [hole, notch, l_hole])
    assert len(islands) == 1 and len(islands[0][1]) == 2
    expected = abs(signed_area(ROOM1)) + abs(signed_area(ROOM2)) - abs(signed_area(hole)) - 1.3 * 1 - 3.0
    assert islands_area(islands) == pytest.approx(expected)
    v, t, r = prism_with_holes(islands, 0.0, 0.2)
    report = validate_mesh(MeshPayload(v, t, r))
    assert report.watertight, report.findings[:3]
    top = sum(abs(signed_area([v[i][:2] for i in tri])) for tri, role in zip(t, r) if role == 'top')
    assert top == pytest.approx(expected)


def test_offset_steps_where_collinear_edges_have_different_distances():
    loop = [(0, 0), (2, 0), (4, 0), (4, 2), (0, 2)]
    out = offset_loop(loop, [0.1, 0.0, 0.1, 0.1, 0.1])
    assert (2.0, -0.1) in [tuple(round(c, 6) for c in p) for p in out]
    assert (2.0, 0.0) in [tuple(round(c, 6) for c in p) for p in out]
