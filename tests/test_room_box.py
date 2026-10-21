"""Owner 18/10: «το δωμάτιο να βγαίνει με διαστάσεις ή να εξελίσσεται από μια ακμή σε παραλληλεπίπεδο, σαφώς
διαμορφώσιμο» — tried in several versions and against drawing the same walls one by one."""
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from archforge.architecture.room_box import corners_from_edge, corners_from_size, size_of
from archforge.ui import room_box_tool
from archforge.ui.main_window import MainWindow


@pytest.fixture
def window(tmp_path, monkeypatch):
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); app.processEvents()
    yield w
    w.hide()


def _walls(doc):
    return [e for e in doc.entities.values() if e.kind == 'wall']


def _floor_area(doc):
    from archforge.architecture.storey_slabs import storey_slab_geometry
    floors = [e for e in doc.entities.values() if e.kind == 'room_floor']
    return sum(storey_slab_geometry(doc, f)['area'] for f in floors)


def _axis_areas(doc):
    """Areas of the spaces on the wall axes (the topology's faces)."""
    def area(poly):
        return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]))) / 2
    return sorted(round(area(list(f.polygon)), 2) for f in doc.active_room_faces())


def _t(doc):
    from archforge.project.brief import wall_defaults
    return float(wall_defaults(doc)[1])


def _segments(doc):
    return sorted(tuple(round(float(e.params[k]), 3) for k in ('x1', 'y1', 'x2', 'y2')) for e in _walls(doc))


def test_geometry_edge_and_size_versions():
    c = corners_from_edge((0, 0), (4, 0), (2, 3))
    assert c[2] == pytest.approx((4, 3)) and c[3] == pytest.approx((0, 3))
    assert size_of(corners_from_edge((0, 0), (4, 0), (2, -3))) == pytest.approx((4, 3))   # pulled the other way
    r = corners_from_size((1, 1), 4, 3, 30)
    assert size_of(r) == pytest.approx((4, 3))
    assert room_box_tool.parse_size('4,20 x 3,50') == (4.2, 3.5)
    assert room_box_tool.parse_size('420*350') == (4.2, 3.5)      # centimetres
    assert room_box_tool.parse_size('4,2') is None


def test_room_from_an_edge_gives_clear_size_floor_and_one_undo(window):
    tool = room_box_tool
    window._start_site_tool('room_box', '')
    for x, y in ((0, 0), (4.2, 0), (2, 3.5)):
        tool.click(window, 'room_box', x, y)
    doc = window.doc
    assert len(_walls(doc)) == 4
    t = _t(doc)
    assert _axis_areas(doc) == [pytest.approx((4.2 + t) * (3.5 + t), abs=.02)]   # the size asked is the inside size
    assert _floor_area(doc) > 4.2 * 3.5                                       # the floor came by itself
    window.stack.undo()                                                       # one Ctrl+Z: the whole room
    assert not _walls(doc) and not [e for e in doc.entities.values() if e.kind == 'room_floor']
    window.stack.redo()
    assert len(_walls(doc)) == 4


def test_same_as_drawing_the_walls_one_by_one(window):
    t = _t(window.doc)
    window._start_site_tool('room_box', '')
    for x, y in ((0, 0), (5, 0), (2, 4)):
        room_box_tool.click(window, 'room_box', x, y)
    by_room = (_segments(window.doc), _axis_areas(window.doc), round(_floor_area(window.doc), 2))

    other = MainWindow()
    try:
        c = other.plan_view.controller
        h = t / 2
        pts = [(-h, -h), (5 + h, -h), (5 + h, 4 + h), (-h, 4 + h)]
        for a, b in zip(pts, pts[1:] + pts[:1]):                             # the wall tool, wall by wall
            c._begin_wall(None, *a, shift=True); c.active.update(*b); c._commit_wall(); c.active = None
        by_walls = (_segments(other.doc), _axis_areas(other.doc), round(_floor_area(other.doc), 2))
    finally:
        other.hide()
    assert by_room == by_walls


def test_room_next_to_a_room_shares_the_wall(window):
    window._start_site_tool('room_place', '')
    window.plan_view.room_size = (4.0, 3.0)
    room_box_tool.click(window, 'room_place', 0, 0)
    t = _t(window.doc)
    window.plan_view.room_size = (3.0, 3.0)
    room_box_tool.click(window, 'room_place', 4.0 + t, 0)                     # next door, past the shared wall
    assert len(_walls(window.doc)) == 7                                       # 4 + 3: the shared wall once
    assert len(_axis_areas(window.doc)) == 2


def test_room_inside_a_space_merges_with_the_walls_it_touches(window):
    """Owner 18/10: «εάν κάνουμε δωμάτιο σε εσωτερικό χώρο οι τοίχοι που ακουμπάνε να συγχωνεύονται»."""
    window._start_site_tool('room_place', '')
    window.plan_view.room_size = (8.0, 6.0)
    room_box_tool.click(window, 'room_place', 0, 0)
    n_walls, n = len(_walls(window.doc)), len(window.stack.done)
    window._start_site_tool('room_box', '')                                   # a store room in the corner
    for x, y in ((0, 0), (2, 0), (1, 1.5)):                                   # its two sides lie on the room's faces
        room_box_tool.click(window, 'room_box', x, y)
    assert len(window.stack.done) == n + 1                                    # one undo step
    new = [e for e in _walls(window.doc)][n_walls:]
    assert len(_walls(window.doc)) - n_walls <= 4                             # two new partitions (+ the splits)
    assert len(_axis_areas(window.doc)) == 2                                  # big room + store room, closed
    t = _t(window.doc)
    for e in _walls(window.doc):                                              # no wall doubled on another
        p = e.params
        assert not (abs(float(p['x1']) - float(p['x2'])) < 1e-6 and abs(float(p['x1'])) < 1e-6 and float(p.get('thickness')) != t)
    window.stack.undo()
    assert len(_walls(window.doc)) == n_walls and len(_axis_areas(window.doc)) == 1


def test_turned_room(window):
    window._start_site_tool('room_box', '')                                   # a turned room (45°)
    s = math.sqrt(.5)
    for x, y in ((0, 0), (4 * s, 4 * s), (4 * s - 3 * s, 4 * s + 3 * s)):
        room_box_tool.click(window, 'room_box', x, y)
    t = _t(window.doc)
    assert _axis_areas(window.doc) == [pytest.approx((4 + t) * (3 + t), abs=.05)]


def test_esc_drops_the_draft_and_the_menu_has_the_tools(window):
    window._start_site_tool('room_box', '')
    room_box_tool.click(window, 'room_box', 0, 0)
    assert window.plan_view.room_draft
    window._cancel_interactions()
    assert not window.plan_view.room_draft and not _walls(window.doc)
    texts = []

    def walk(menu):
        for a in menu.actions():
            texts.append(a.text().replace('&&', '&'))
            if a.menu() is not None:
                walk(a.menu())
    for a in window.menuBar().actions():
        if a.menu() is not None:
            walk(a.menu())
    assert 'Δωμάτιο (ορθογώνιο)' in texts and 'Δωμάτιο με διαστάσεις…' in texts and 'Τοίχοι & δωμάτια' in texts


def test_a_room_next_door_follows_the_faces_and_lines_up(window):
    """Owner 21/10: «συνδέοντας το ένα δωμάτιο με το άλλο δεν ακολουθούσε κάποιο οδηγό, έπιανε από όπου ήθελε» —
    clicks a few cm off land on the neighbour's face corner, and the far side lines up with its corners."""
    window.plan_view.resetTransform(); window.plan_view.scale(40.0, -40.0)  # 40 px per metre: 14 px ≈ 35 cm
    window.plan_view.room_size = (4.0, 3.0)
    room_box_tool.click(window, 'room_place', 0, 0)
    t = _t(window.doc)
    # Next door on the east: start a little off the outer face corner, end a little off, depth near the top.
    window._start_site_tool('room_box', '')
    for x, y in ((4.0 + t + 0.03, 0.04), (7.03, 0.06), (6.0, 3.06)):
        room_box_tool.click(window, 'room_box', x, y)
    assert len(_axis_areas(window.doc)) == 2
    xs = sorted({round(float(e.params[k]), 3) for e in _walls(window.doc) for k in ('x1', 'x2')})
    ys = sorted({round(float(e.params[k]), 3) for e in _walls(window.doc) for k in ('y1', 'y2')})
    assert len(ys) == 2                                                       # top and bottom lined up: one Y each
    assert len(_walls(window.doc)) == 7                                       # the shared wall once


def test_snap_point_corner_face_guide():
    from archforge.architecture.room_box import snap_point, straighten
    corners = [(0.0, 0.0), (4.0, 0.0), (4.0, 3.0)]
    lines = [((0.0, 0.0), (4.0, 0.0))]
    assert snap_point(None, 4.03, 0.02, 0, .2, (corners, lines))[:2] == (4.0, 0.0)          # corner
    x, y, _g, kind = snap_point(None, 2.0, 0.1, 0, .2, (corners, lines))
    assert (x, y, kind) == (2.0, 0.0, 'face')
    x, y, guides, kind = snap_point(None, 6.0, 2.9, 0, .2, (corners, lines))
    assert (y, kind) == (3.0, 'guide') and guides                                         # lined up with (4, 3)
    assert straighten((0, 0), (3, 0.2)) == pytest.approx((math.hypot(3, .2), 0.0))
