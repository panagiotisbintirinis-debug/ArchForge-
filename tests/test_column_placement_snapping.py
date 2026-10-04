from math import atan2, degrees

from archforge.core.commands import CommandStack
from archforge.core.model import Document, Entity
from archforge.core.viewport import PointerController, PointerEvent


def _wall(x1, y1, x2, y2):
    return Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0,
                           'height': 2.7, 'thickness': 0.2})


def _place_column(doc, x, y, *, shift=False):
    controller = PointerController(doc, CommandStack(doc))
    controller.set_tool('structural_column')
    controller.pointer_down(PointerEvent(x, y, shift=shift))
    controller.pointer_move(PointerEvent(x, y, shift=shift))
    result = controller.pointer_up(PointerEvent(x, y, shift=shift))
    return doc.get(result.entity_id)


def _room():
    doc = Document()
    for a, b in (((0, 0), (4, 0)), ((4, 0), (4, 3)), ((4, 3), (0, 3)), ((0, 3), (0, 0))):
        doc.add(_wall(a[0], a[1], b[0], b[1]))
    return doc


def test_column_snaps_to_wall_corner_from_a_human_click_distance():
    doc = _room()
    column = _place_column(doc, 3.78, 2.81)
    assert (column.params['x'], column.params['y']) == (4.0, 3.0)


def test_column_on_a_skewed_wall_sits_on_its_axis_and_follows_its_direction():
    doc = Document()
    wall = _wall(0.0, 0.0, 4.0, 1.0)
    doc.add(wall)
    column = _place_column(doc, 2.0, 0.72)
    # Projected onto the wall centerline (y = x / 4).
    assert abs(column.params['y'] - column.params['x'] / 4.0) < 1e-9
    assert abs(column.params['rotation'] - degrees(atan2(1.0, 4.0))) < 1e-9


def test_column_snaps_to_floor_slab_corner():
    doc = Document()
    doc.add(Entity('floor', {'points': [(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)],
                             'z': 0.0, 'thickness': 0.15}))
    column = _place_column(doc, 4.8, 3.83)
    assert (column.params['x'], column.params['y']) == (5.0, 4.0)


def test_shift_places_a_free_column_exactly_where_clicked():
    doc = _room()
    column = _place_column(doc, 3.96, 2.97, shift=True)
    assert (column.params['x'], column.params['y']) == (3.96, 2.97)
    assert column.params['rotation'] == 0.0


def test_column_snaps_to_auto_floor_corner():
    from archforge.core.commands import CreateRoomFloors

    doc = _room()
    stack = CommandStack(doc)
    signatures = [face.signature for face in doc.active_room_faces()]
    stack.execute(CreateRoomFloors(signatures))
    floor = next(e for e in doc.entities.values() if e.kind == 'room_floor')

    from archforge.architecture.rooms import room_floor_geometry
    corners = room_floor_geometry(doc, floor)['points']
    cx, cy = corners[0]
    column = _place_column(doc, cx + 0.2, cy + 0.15)
    assert (column.params['x'], column.params['y']) == (cx, cy)
