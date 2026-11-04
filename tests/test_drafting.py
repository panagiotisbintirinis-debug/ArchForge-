"""Owner: «εργαλεία CAD απλά και μαζί εργαλείο σημειώσεων» — lines, polylines, rectangles, circles, arcs and notes
in the plan (architecture/drafting.py, ui/drafting_tool.py): drawn, saved, moved, printed in PDF and DXF."""
import json
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture import drafting as DR
from archforge.core.commands import AddEntity, CommandStack, MoveEntities
from archforge.core.model import Document
from archforge.core.plan_scene import build_plan_frame


def _doc():
    doc = Document(); return doc, CommandStack(doc)


def test_entities_validate_save_and_draw_on_their_storey_only():
    doc, st = _doc()
    for e in (DR.line_entity([(0, 0), (3, 0), (3, 2)], 0.0), DR.rectangle_entity((0, 0), (2, 1), 0.0),
              DR.circle_entity((1, 1), (2, 1), 0.0), DR.arc_entity((0, 0), (1, 1), (2, 0), 0.0),
              DR.note_entity((1, 1), 'Νέα δοκός', 0.0, leader=(2, 2)), DR.line_entity([(0, 0), (1, 1)], 3.0)):
        st.execute(AddEntity(e))
    roles = [p.role for p in build_plan_frame(doc).primitives if p.role in ('cad-line', 'note', 'note-leader')]
    assert roles.count('cad-line') == 4 and roles.count('note') == 1 and roles.count('note-leader') == 3
    rect = next(p for p in build_plan_frame(doc).primitives if p.role == 'cad-line' and len(p.points) == 5)
    assert rect.points[0] == rect.points[-1]                                       # closed
    reopened = Document.from_dict(json.loads(json.dumps(doc.to_dict())))
    assert sorted(e.kind for e in reopened.entities.values()) == sorted(e.kind for e in doc.entities.values())
    from archforge.core.model import Entity
    with pytest.raises(ValueError):
        st.execute(AddEntity(Entity('cad_line', {'points': [[0, 0], [0, 0]], 'level_z': 0.0})))
    with pytest.raises(ValueError):
        st.execute(AddEntity(DR.note_entity((0, 0), '   ', 0.0)))
    with pytest.raises(ValueError):
        DR.arc_entity((0, 0), (1, 0), (2, 0), 0.0)                                 # three points on one line


def test_arc_through_three_points_passes_through_them():
    cx, cy, r, a0, a1 = DR.arc_through((0, 0), (1, 1), (2, 0))
    assert (cx, cy, r) == pytest.approx((1, 0, 1)) and (a0, a1) == pytest.approx((0, 180))
    pts = DR.arc_points(cx, cy, r, a0, a1)
    assert min(math.dist(p, (1, 1)) for p in pts) < 0.06                           # the middle click is on it
    cx, cy, r, a0, a1 = DR.arc_through((2, 0), (1, -1), (0, 0))                     # the other way round
    assert min(math.dist(p, (1, -1)) for p in DR.arc_points(cx, cy, r, a0, a1)) < 0.06


def test_move_and_undo_and_nothing_in_3d_or_ifc():
    doc, st = _doc()
    line = DR.line_entity([(0, 0), (1, 0)], 0.0); note = DR.note_entity((1, 1), 'Α', 0.0, leader=(0, 0))
    circle = DR.circle_entity((0, 0), (1, 0), 0.0)
    for e in (line, note, circle):
        st.execute(AddEntity(e))
    st.execute(MoveEntities([line.id, note.id, circle.id], 1.0, 2.0, 0.0))
    assert doc.get(line.id).params['points'] == [[1.0, 2.0], [2.0, 2.0]]
    assert (doc.get(note.id).params['leader_x'], doc.get(circle.id).params['cy']) == (1.0, 2.0)
    st.undo()
    assert doc.get(line.id).params['points'] == [[0.0, 0.0], [1.0, 0.0]]
    from archforge.geometry.mesh import TessellatedPreviewBackend
    assert not [b for b in TessellatedPreviewBackend().evaluate(doc).bodies if b.payload is not None and b.payload.vertices]
    from archforge.exchange.mapping import SKIP, plan_layer
    assert set(DR.KINDS) <= SKIP and plan_layer('cad-line') == 'A-DETL-GENF' and plan_layer('note') == 'A-ANNO-NOTE'


def test_dxf_writes_the_lines_and_the_note(tmp_path):
    ezdxf = pytest.importorskip('ezdxf')
    from archforge.exchange.dxf import export_dxf
    doc, st = _doc()
    st.execute(AddEntity(DR.rectangle_entity((0, 0), (2, 1), 0.0)))
    st.execute(AddEntity(DR.note_entity((1, 1), 'Σημείωση DXF', 0.0)))
    path = export_dxf(doc, str(tmp_path / 'plan.dxf'))['files'][0]
    msp = ezdxf.readfile(str(path)).modelspace()
    layers = {e.dxf.layer for e in msp}
    assert 'A-DETL-GENF' in layers and 'A-ANNO-NOTE' in layers
    assert any('Σημείωση DXF' in (getattr(e.dxf, 'text', '') or e.plain_text() if hasattr(e, 'plain_text') else '')
               for e in msp if e.dxftype() in ('TEXT', 'MTEXT'))


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 950); w.show(); app.processEvents()
    yield w, app
    w._mark_clean(); w.close(); app.processEvents()


def _clicks(w, app, points, double_last=False):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    view = w.plan_view
    pos = lambda x, y: view.mapFromScene(QPointF(x, y))
    for k, (x, y) in enumerate(points):
        QTest.mouseMove(view.viewport(), pos(x, y)); app.processEvents()
        if double_last and k == len(points) - 1:
            QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos(x, y))
        else:
            QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pos(x, y))
        app.processEvents()


def test_menus_and_mouse_draw_every_shape_and_a_note(window, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QInputDialog
    w, app = window
    w.plan_view.fitInView(-1, -1, 12, 10); app.processEvents()
    w.plan_view.controller.snap_enabled = False
    sections = w._work_sections
    draw, notes = sections[('Σχέδια', 'Σχεδίαση CAD')], sections[('Σχέδια', 'Σημειώσεις')]
    assert [a.text() for a in draw.actions()] == ['Γραμμή', 'Πολυγραμμή', 'Ορθογώνιο', 'Κύκλος', 'Τόξο (3 σημεία)']
    assert [a.text() for a in notes.actions()] == ['Σημείωση', 'Σημείωση με βέλος']
    acts = w._draft_actions

    def kinds():
        return sorted(e.kind for e in w.doc.entities.values() if e.kind in DR.KINDS)
    acts['rect'].trigger(); _clicks(w, app, [(1, 1), (4, 3)])
    acts['circle'].trigger(); _clicks(w, app, [(6, 2), (7, 2)])
    acts['arc'].trigger(); _clicks(w, app, [(1, 5), (2, 6), (3, 5)])
    acts['line'].trigger(); _clicks(w, app, [(5, 5), (8, 5), (8, 7)])              # two chained segments
    QTest.keyClick(w.plan_view.viewport(), Qt.Key.Key_Escape); app.processEvents()
    assert not w._draft_tool.active
    acts['polyline'].trigger(); _clicks(w, app, [(1, 8), (2, 9), (3, 8)], double_last=True)
    assert kinds() == ['cad_arc', 'cad_circle', 'cad_line', 'cad_line', 'cad_line', 'cad_line']
    circle = next(e for e in w.doc.entities.values() if e.kind == 'cad_circle')
    assert float(circle.params['r']) == pytest.approx(1.0, abs=0.05)

    monkeypatch.setattr(QInputDialog, 'getMultiLineText', staticmethod(lambda *a, **k: ('Νέα δοκός 25/50', True)))
    acts['leader'].trigger(); _clicks(w, app, [(2.5, 2), (5, 0.5)])
    note = next(e for e in w.doc.entities.values() if e.kind == 'note')
    assert note.params['text'] == 'Νέα δοκός 25/50' and float(note.params['leader_x']) == pytest.approx(2.5, abs=0.05)
    w._draft_tool.cancel()
    # Double click on the note in Επιλογή: change its text, one undo.
    w.plan_view.to_select(); app.processEvents()
    monkeypatch.setattr(QInputDialog, 'getMultiLineText', staticmethod(lambda *a, **k: ('Δοκός 30/60', True)))
    from PySide6.QtCore import QPoint, QPointF
    view = w.plan_view
    at = view.mapFromScene(QPointF(float(note.params['x']), float(note.params['y']))) + QPoint(10, -8)   # on the text
    QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, at)
    app.processEvents()
    assert w.doc.get(note.id).params['text'] == 'Δοκός 30/60'
    w.stack.undo()
    assert w.doc.get(note.id).params['text'] == 'Νέα δοκός 25/50'
