import pytest

from archforge.core.model import Document, Entity


def _wall():
    return Entity('wall', {
        'x1': 0.0, 'y1': 0.0, 'z': 0.0,
        'x2': 5.0, 'y2': 0.0,
        'height': 3.0, 'thickness': 0.2,
    })


def _door(parent_id, offset=1.5, width=0.9, height=2.1):
    return Entity('door', {
        'offset': offset,
        'width': width,
        'height': height,
        'sill': 0.0,
    }, parent_id=parent_id)


def _window(parent_id, offset=3.0, width=1.0, height=1.0, sill=1.0):
    return Entity('window', {
        'offset': offset,
        'width': width,
        'height': height,
        'sill': sill,
    }, parent_id=parent_id)


def test_overlapping_wall_openings_are_rejected():
    doc = Document()
    wall = _wall(); doc.add(wall)
    door = _door(wall.id, offset=2.0, width=1.2, height=2.1); doc.add(door)

    overlapping = _window(wall.id, offset=2.2, width=1.0, height=1.0, sill=1.0)
    with pytest.raises(ValueError, match='overlap'):
        doc.add(overlapping)

    assert overlapping.id not in doc.entities
    assert doc.children.get(wall.id) == [door.id]


def test_openings_may_touch_but_not_overlap():
    doc = Document()
    wall = _wall(); doc.add(wall)
    left = _window(wall.id, offset=1.0, width=1.0, height=1.0, sill=1.0); doc.add(left)
    right = _window(wall.id, offset=2.0, width=1.0, height=1.0, sill=1.0); doc.add(right)

    assert left.id in doc.entities and right.id in doc.entities


def test_vertically_separated_openings_may_share_horizontal_span():
    doc = Document()
    wall = _wall(); doc.add(wall)
    lower = _window(wall.id, offset=2.5, width=1.2, height=0.8, sill=0.2); doc.add(lower)
    upper = _window(wall.id, offset=2.5, width=1.2, height=0.8, sill=1.0); doc.add(upper)

    assert lower.id in doc.entities and upper.id in doc.entities


def test_opening_update_that_creates_overlap_is_atomic():
    doc = Document()
    wall = _wall(); doc.add(wall)
    door = _door(wall.id, offset=1.25, width=1.0, height=2.1); doc.add(door)
    window = _window(wall.id, offset=3.5, width=1.0, height=1.0, sill=1.0); doc.add(window)
    before = dict(window.params)
    before_revision = window.revision

    with pytest.raises(ValueError, match='overlap'):
        doc.update(window.id, {'offset': 1.4})

    assert window.params == before
    assert window.revision == before_revision
