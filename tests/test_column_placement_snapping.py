from math import atan2, degrees

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent


def _wall(x1, y1, x2, y2, thickness=0.2):
    return Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                           'height': 2.7, 'thickness': thickness})


def _place_column(doc, x, y, *, shift=False):
    controller = PointerController(doc, CommandStack(doc))
    controller.set_tool('structural_column')
    controller.pointer_down(PointerEvent(x, y, shift=shift))
    controller.pointer_move(PointerEvent(x, y, shift=shift))
    result = controller.pointer_up(PointerEvent(x, y, shift=shift))
    return doc.get(result.entity_id)


def _loop(doc, points, thickness=0.2):
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        doc.add(_wall(a[0], a[1], b[0], b[1], thickness))
    return doc


def _room(thickness=0.2):
    return _loop(Document(), [(0, 0), (4, 0), (4, 3), (0, 3)], thickness)


def _footprint(column):
    p = column.params
    from math import cos, radians, sin
    a = radians(p['rotation']); c, s = cos(a), sin(a)
    pts = [(p['x'] + lx * c - ly * s, p['y'] + lx * s + ly * c)
           for lx, ly in ((-p['width'] / 2, -p['depth'] / 2), (p['width'] / 2, -p['depth'] / 2),
                          (p['width'] / 2, p['depth'] / 2), (-p['width'] / 2, p['depth'] / 2))]
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    return min(xs), max(xs), min(ys), max(ys)


def _close(a, b):
    return abs(a - b) < 1e-9


def test_corner_column_outer_corner_is_flush_with_the_outer_wall_corner():
    doc = _room()
    column = _place_column(doc, 3.78, 2.81)
    xmin, xmax, ymin, ymax = _footprint(column)
    # Outer wall faces are at x = 4.1 and y = 3.1 (thickness 0.2).
    assert _close(xmax, 4.1) and _close(ymax, 3.1)
    # A 0.25 m column is thicker than the 0.2 m wall: the extra shows inside.
    assert _close(xmin, 3.85) and _close(ymin, 2.85)


def test_every_corner_of_the_room_keeps_the_column_inside_the_outline():
    doc = _room()
    for (cx, cy), expected in (((0.1, 0.1), (-0.1, None, -0.1, None)),
                               ((3.9, 0.1), (None, 4.1, -0.1, None)),
                               ((0.1, 2.9), (-0.1, None, None, 3.1))):
        xmin, xmax, ymin, ymax = _footprint(_place_column(doc, cx, cy))
        for got, want in zip((xmin, xmax, ymin, ymax), expected):
            if want is not None:
                assert _close(got, want)


def test_column_on_an_outer_wall_is_flush_with_its_outer_face():
    doc = _room()
    column = _place_column(doc, 3.9, 1.5)
    xmin, xmax, _, _ = _footprint(column)
    assert _close(xmax, 4.1)
    assert _close(xmin, 3.85)
    assert _close(column.params['y'], 1.5)


def test_reflex_corner_of_an_l_shaped_room_is_flush_on_the_outside():
    # L-shaped room; (2, 2) is the inner (reflex) corner of the building.
    doc = _loop(Document(), [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)])
    xmin, xmax, ymin, ymax = _footprint(_place_column(doc, 2.1, 2.1))
    # Outside the building is the notch x > 2, y > 2: faces at x = 2.1, y = 2.1.
    assert _close(xmax, 2.1) and _close(ymax, 2.1)
    assert _close(xmin, 1.85) and _close(ymin, 1.85)


def test_column_on_a_skewed_free_wall_sits_on_its_axis_and_follows_its_direction():
    doc = Document()
    doc.add(_wall(0.0, 0.0, 4.0, 1.0))
    column = _place_column(doc, 2.0, 0.72)
    assert abs(column.params['y'] - column.params['x'] / 4.0) < 1e-9
    assert abs(column.params['rotation'] - degrees(atan2(1.0, 4.0))) < 1e-9


def test_column_snaps_inside_a_floor_slab_corner():
    doc = Document()
    doc.add(Entity('floor', {'points': [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)],
                             'z': 0.0, 'thickness': 0.15}))
    xmin, xmax, ymin, ymax = _footprint(_place_column(doc, 4.8, 3.83))
    assert _close(xmax, 5.0) and _close(ymax, 4.0)
    assert _close(xmin, 4.75) and _close(ymin, 3.75)


def test_auto_floor_room_corner_uses_the_outer_wall_corner():
    from archforge.core.commands import CreateRoomFloors

    doc = _room()
    stack = CommandStack(doc)
    stack.execute(CreateRoomFloors([face.signature for face in doc.active_room_faces()]))
    xmin, xmax, ymin, ymax = _footprint(_place_column(doc, 0.15, 0.2))
    assert _close(xmin, -0.1) and _close(ymin, -0.1)


def test_shift_places_a_free_column_exactly_where_clicked():
    doc = _room()
    column = _place_column(doc, 3.96, 2.97, shift=True)
    assert (column.params['x'], column.params['y']) == (3.96, 2.97)
    assert column.params['rotation'] == 0.0
