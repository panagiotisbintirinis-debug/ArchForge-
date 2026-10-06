"""Columns and beams proposed from the walls, after drawing walls and rooms."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntities, AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.structure.layout import column_points, propose_frame


def _house(stack, z=0.0, x_max=12.0):
    for s in [(0, 0, x_max, 0), (x_max, 0, x_max, 6), (x_max, 6, 0, 6), (0, 6, 0, 0), (5, 0, 5, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': z, 'height': 2.7, 'thickness': 0.2})))


def test_columns_at_corners_junctions_and_every_6m_never_in_an_opening():
    doc = Document(); st = CommandStack(doc); _house(st)
    pts = column_points(doc, 0.0)
    for corner in [(0, 0), (12, 0), (12, 6), (0, 6), (5, 0), (5, 6)]:
        assert corner in pts
    # 7 m between x=5 and x=12 → one intermediate column on both long walls.
    assert (8.5, 0.0) in pts and (8.5, 6.0) in pts and len(pts) == 8
    # A window where that column would go moves it to the side of the opening.
    south = next(e for e in doc.entities.values() if e.kind == 'wall' and e.params['y1'] == 0 and e.params['y2'] == 0)
    st.execute(AddEntity(Entity('window', {'offset': 8.5, 'width': 1.2, 'height': 1.4, 'sill': 0.9}, parent_id=south.id)))
    moved = [p for p in column_points(doc, 0.0) if p[1] == 0.0 and 5 < p[0] < 12]
    assert moved and all(not (7.75 < x < 9.25) for x, _y in moved)


def test_frame_for_two_storeys_analyses_and_does_not_duplicate():
    from archforge.structure.analysis import analyze
    doc = Document(); st = CommandStack(doc); doc.levels['Floor 2'] = 3.0
    _house(st, 0.0); _house(st, 3.0)
    entities, report = propose_frame(doc)
    # 9 beams on the walls + the x = 8.5 axis beam across the 7 m room (it splits the slab), per storey.
    assert report['columns'] == 16 and report['beams'] == 2 * 10
    cols = [e for e in entities if e.kind == 'structural_column']
    assert {round(e.params['height'], 2) for e in cols} == {3.0, 2.7}           # to the slab / to the roof
    beams = [e for e in entities if e.kind == 'structural_beam']
    assert {round(e.params['z'] + e.params['height'], 2) for e in beams} == {3.0, 5.7}
    st.execute(AddEntities(entities))
    assert propose_frame(doc)[0] == []                                          # nothing doubled
    r = analyze(doc)
    assert r['error'] is None and len(r['members']) == 16 + 20


def test_assistant_proposes_and_understands_columns_where_needed():
    from archforge.assistant.suggestions import Proposal, apply, propose
    from archforge.assistant.target import actions_for, match, target_at
    doc = Document(); st = CommandStack(doc); _house(st)
    s3 = next(p for p in propose(doc) if p.key == 'S-3')
    assert '8 κολόνες' in s3.title
    action = match('ΘΕΛΩ ΝΑ ΜΟΥ ΒΑΛΕΙΣ ΚΟΛΟΝΕΣ ΟΠΟΥ ΧΡΕΙΑΖΕΤΑΙ', actions_for(doc, target_at(doc, 2.0, 3.0)))
    assert action is not None and action.key == 'frame'
    apply(st, Proposal(action.key, 'hint', action.label, '', '', (), action.build))
    assert sum(e.kind == 'structural_column' for e in doc.entities.values()) == 8
    assert not any(p.key == 'S-3' for p in propose(doc))
    st.undo()
    assert not any(e.kind == 'structural_column' for e in doc.entities.values())


def test_menu_command_adds_frame_and_runs_analysis():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        assert any(a.text() == 'Πρόταση φέροντος οργανισμού από τους τοίχους' for a in w._structure_menu.actions())
        _house(w.stack)
        report = w._propose_frame()
        assert report['columns'] == 8
        from archforge.structure.analysis import fresh_result
        assert fresh_result(w.doc) is not None and 'Φέρων: 8 κολόνες' in w.statusBar().currentMessage()
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_grid_follows_the_loads_not_every_wall_junction():
    """A 10 × 9 house: two close parallel walls, short partitions and a leftover 5 cm piece."""
    from archforge.structure.layout import grid_axes, _walls
    from archforge.mep.ventilation import exterior_walls
    doc = Document(); st = CommandStack(doc)
    segs = [(0, 0, 10, 0), (10, 0, 10, 9), (10, 9, 0, 9), (0, 9, 0, 0),          # shell
            (4.0, 0, 4.0, 9), (4.6, 5, 4.6, 9),                                  # two close parallel walls
            (0, 5, 4.0, 5), (4.6, 5, 10, 5), (7.5, 5, 7.5, 9),                   # rooms
            (2.0, 5, 2.0, 5.05)]                                                 # leftover piece
    for x1, y1, x2, y2 in segs:
        st.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7, 'thickness': 0.2})))
    walls = _walls(doc, 0.0)
    assert len(walls) == len(segs) - 1                                           # the 5 cm piece is not structure
    ext = {w.id for w, _n in exterior_walls(doc, 0.0)}
    xs, ys = grid_axes(walls, ext, 'x'), grid_axes(walls, ext, 'y')
    assert all(b - a <= 6.0 + 1e-6 for a, b in zip(xs, xs[1:])) and all(b - a <= 6.0 + 1e-6 for a, b in zip(ys, ys[1:]))
    assert all(b - a >= 2.0 - 1e-6 for a, b in zip(xs, xs[1:]))                  # never two axes 60 cm apart
    pts = column_points(doc, 0.0)
    close = [(p, q) for p in pts for q in pts if p < q and ((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2) ** .5 < 1.2]
    assert not close
    assert len(pts) <= 9                                                          # a grid, not a column per junction


def test_columns_never_hang_outside_the_facade():
    doc = Document(); st = CommandStack(doc); _house(st)                 # walls 20 cm, columns 40/40
    entities, _r = propose_frame(doc)
    for e in entities:
        if e.kind != 'structural_column':
            continue
        x, y, h = e.params['x'], e.params['y'], e.params['width'] / 2
        assert x - h >= -0.1 - 1e-6 and x + h <= 12.1 + 1e-6 and y - h >= -0.1 - 1e-6 and y + h <= 6.1 + 1e-6
    corner = min((e for e in entities if e.kind == 'structural_column'), key=lambda e: e.params['x'] + e.params['y'])
    assert (corner.params['x'], corner.params['y']) == pytest.approx((0.1, 0.1))   # outer faces flush, inwards both ways


def test_lower_storey_carries_every_column_of_the_storey_above():
    doc = Document(); st = CommandStack(doc); doc.levels['Floor 2'] = 3.0
    _house(st, 0.0, x_max=7.0)                                            # ground 7 × 6
    for s in [(0, 0, 7, 0), (7, 0, 7, 6), (7, 6, 0, 6), (0, 6, 0, 0), (3.5, 0, 3.5, 6)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 3.0, 'height': 2.7, 'thickness': 0.2})))
    entities, _r = propose_frame(doc)
    cols = [e for e in entities if e.kind == 'structural_column']
    upper = [(round(e.params['x'], 1), round(e.params['y'], 1)) for e in cols if e.params['z'] == 3.0]
    lower = [(round(e.params['x'], 1), round(e.params['y'], 1)) for e in cols if e.params['z'] == 0.0]
    for u in upper:
        assert any(abs(u[0] - l[0]) <= .3 and abs(u[1] - l[1]) <= .3 for l in lower), u


def test_3d_scene_hides_members_inside_walls_and_shows_what_sticks_out():
    from archforge.ui.pbr_viewport import members_hidden_in_walls
    doc = Document(); st = CommandStack(doc)
    for s in [(0, 0, 8, 0), (8, 0, 8, 6), (8, 6, 0, 6), (0, 6, 0, 0)]:
        st.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0, 'height': 2.5, 'thickness': 0.3})))
    def col(x, y, size):
        e = Entity('structural_column', {'x': x, 'y': y, 'z': 0.0, 'width': size, 'depth': size, 'height': 3.0, 'rotation': 0.0,
                                         'role': 'structural', 'construction': 'reinforced_concrete', 'section': 'rectangular',
                                         'base_level': 'Ground', 'top_level': 'Unassigned'})
        st.execute(AddEntity(e)); return e
    def beam(x1, y1, x2, y2):
        e = Entity('structural_beam', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 2.5, 'width': .25, 'height': .5, 'role': 'structural',
                                       'construction': 'reinforced_concrete', 'section': 'rectangular', 'level': 'Ground'})
        st.execute(AddEntity(e)); return e
    inside = col(4.0, 0.0, .25)                 # 25 cm column in a 30 cm wall: plastered over
    thick = col(0.0, 3.0, .40)                  # thicker than the wall: shows in the room
    over_wall = beam(0, 0, 8, 0)                # on the wall: hidden
    free = beam(4, 0, 4, 6)                     # across the room: a downstand, visible
    hidden = members_hidden_in_walls(doc)
    assert inside.id in hidden and over_wall.id in hidden
    assert thick.id not in hidden and free.id not in hidden
