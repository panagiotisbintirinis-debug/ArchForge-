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
    assert report['columns'] == 16 and report['beams'] == 2 * 9
    cols = [e for e in entities if e.kind == 'structural_column']
    assert {round(e.params['height'], 2) for e in cols} == {3.0, 2.7}           # to the slab / to the roof
    beams = [e for e in entities if e.kind == 'structural_beam']
    assert {round(e.params['z'] + e.params['height'], 2) for e in beams} == {3.0, 5.7}
    st.execute(AddEntities(entities))
    assert propose_frame(doc)[0] == []                                          # nothing doubled
    r = analyze(doc)
    assert r['error'] is None and len(r['members']) == 16 + 18


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
