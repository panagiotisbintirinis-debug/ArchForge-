"""Owner 29–30/10: «Τοίχος ▾ … καμπύλος» · «ξεκίνησε τον καμπύλο τοίχο». An arc of ordinary walls, three clicks."""
import json
import math
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture import curved_wall as cw
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity


def test_arc_through_three_points_and_the_pieces_stay_on_the_circle():
    cx, cy, r, t0, sweep = cw.arc_through((0, 0), (6, 0), (3, 2))
    assert (cx, cy, r) == pytest.approx((3.0, -1.25, 3.25))
    assert sweep < 0                                                  # clockwise: over the top through (3, 2)
    n = cw.pieces_for(r, sweep)
    assert cw.deviation(r, sweep, n) <= cw.SAG + 1e-9
    for x, y in cw.points(cx, cy, r, t0, sweep, n):
        assert math.dist((x, y), (cx, cy)) == pytest.approx(r)
    with pytest.raises(ValueError):
        cw.arc_through((0, 0), (6, 0), (3, 0))                        # on one line


def test_a_curved_wall_is_walls_one_undo_saved_and_reshaped_with_its_ends():
    doc = Document(); stack = CommandStack(doc)
    command, walls = cw.create_command(doc, (0, 0), (6, 0), (3, 2), n=8)
    stack.execute(command)
    assert len(walls) == 8 and all(doc.get(w.id).kind == 'wall' for w in walls)
    ends = [(w.params['x1'], w.params['y1'], w.params['x2'], w.params['y2']) for w in cw.members(doc, walls[0].params['curve']['id'])]
    assert all(a[2:] == b[:2] for a, b in zip(ends, ends[1:]))       # joined end to end
    assert ends[0][:2] == pytest.approx((0, 0)) and ends[-1][2:] == pytest.approx((6, 0))
    cid = walls[0].params['curve']['id']
    copy = Document.from_dict(json.loads(json.dumps(doc.to_dict())))
    assert len(cw.members(copy, cid)) == 8
    reshape, new = cw.reshape_command(doc, cid, r=5.0)
    stack.execute(reshape)
    got = cw.members(doc, cid)
    assert cw.info(doc, got[0])['r'] == pytest.approx(5.0)
    assert (got[0].params['x1'], got[0].params['y1']) == pytest.approx((0, 0))
    assert (got[-1].params['x2'], got[-1].params['y2']) == pytest.approx((6, 0))
    mid = cw.points(*[float(got[0].params['curve'][k]) for k in ('cx', 'cy', 'r', 't0', 'sweep')], 2)[1]
    assert mid[1] > 0                                                 # still bulging the same way
    stack.undo()
    assert len(cw.members(doc, cid)) == 8
    stack.undo()
    assert not cw.members(doc, cid)


def test_height_on_one_piece_goes_to_the_whole_arc():
    doc = Document(); stack = CommandStack(doc)
    command, walls = cw.create_command(doc, (0, 0), (4, 0), (2, 1), n=4)
    stack.execute(command)
    stack.execute(cw.spread_command(doc, walls[1].id, {'height': 3.1}))
    assert all(doc.get(w.id).params['height'] == pytest.approx(3.1) for w in walls)
    stack.execute(cw.spread_command(doc, walls[1].id, {'x1': walls[1].params['x1']}))   # geometry: that piece only


def test_an_arc_closes_a_room_with_straight_walls():
    doc = Document(); stack = CommandStack(doc)
    for x1, y1, x2, y2 in ((0, 0, 6, 0), (6, 0, 6, 4), (0, 4, 0, 0)):
        stack.execute(AddEntity(Entity('wall', {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'z': 0.0, 'height': 2.7,
                                                 'thickness': 0.2})))
    command, _walls = cw.create_command(doc, (6, 4), (0, 4), (3, 6))
    stack.execute(command)
    faces = doc.active_room_faces()
    assert len(faces) == 1
    area = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(faces[0].polygon, faces[0].polygon[1:] + faces[0].polygon[:1]))) / 2
    assert area > 24                                                  # the rectangle plus the round bay


def test_three_clicks_in_the_plan_from_the_wall_menu(tmp_path):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1400, 900); w.show(); app.processEvents()
    try:
        w._no_modal_dialogs = True
        w.plan_view.controller.snap_enabled = False
        curved = w._mockup_wall_curved
        assert curved.isEnabled()
        curved.trigger()
        tool = w._curved_wall_tool
        assert tool.active and tool.bar.isVisible()
        pv = w.plan_view
        for x, y in ((0, 0), (6, 0), (3, 2)):
            pos = QPointF(pv.mapFromScene(x, y))
            e = QMouseEvent(QMouseEvent.Type.MouseButtonPress, pos, pv.viewport().mapToGlobal(pos), Qt.MouseButton.LeftButton,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
            pv.mousePressEvent(e)
            pv.mouseReleaseEvent(QMouseEvent(QMouseEvent.Type.MouseButtonRelease, pos, pv.viewport().mapToGlobal(pos),
                                             Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier))
        walls = [e for e in w.doc.entities.values() if e.kind == 'wall']
        assert len(walls) >= 4 and all(e.params.get('curve') for e in walls)
        r = walls[0].params['curve']['r']
        assert r == pytest.approx(3.25, abs=0.05)                     # clicks land on the plan points (± a pixel)
        assert tool.active and len(tool.points) == 1                  # the next arc starts where this one ended
        w.doc.select([walls[0].id]); w.refresh_inspector(); app.processEvents()
        from PySide6.QtWidgets import QPushButton
        assert any(b.text().startswith('Επιλογή όλου του τόξου') for b in w.findChildren(QPushButton))
        from archforge.ui.curved_wall_tool import reshape
        assert reshape(w, walls[0].params['curve']['id'], n=6)
        assert len([e for e in w.doc.entities.values() if e.kind == 'wall']) == 6
        tool.stop()
        assert not tool.active and not tool.bar.isVisible()
        from archforge.ui.marking_menu import run
        run(w, 'plan', None, 'mm:curvedwall:start')
        assert tool.active
        tool.stop()
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_doors_and_windows_stay_on_the_arc_when_it_is_reshaped():
    # Before 30/10 the check looked for host_id/wall_id, never matched, and deleting the pieces took the
    # window with them: it vanished silently on a new radius.
    doc = Document(); stack = CommandStack(doc)
    command, walls = cw.create_command(doc, (0, 0), (8, 0), (4, 3), n=8)
    stack.execute(command)
    piece = walls[5]
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    win = Entity('window', {'offset': 0.7, 'width': 0.5, 'height': 1.2, 'sill': 0.9}, parent_id=piece.id)
    stack.execute(AddEntity(win))
    def centre(e):
        h = doc.get(e.parent_id).params
        c = math.dist((h['x1'], h['y1']), (h['x2'], h['y2']))
        t = e.params['offset'] / c
        return (h['x1'] + (h['x2'] - h['x1']) * t, h['y1'] + (h['y2'] - h['y1']) * t)
    before = centre(doc.get(win.id))
    reshape, new = cw.reshape_command(doc, piece.params['curve']['id'], n=16)
    stack.execute(reshape)
    w = doc.get(win.id)
    assert w is not None and w.parent_id in {x.id for x in new}
    assert math.dist(centre(w), before) <= 0.25 + 0.02          # same place, at most nudged inside its piece
    stack.undo()
    assert doc.get(win.id).parent_id == piece.id
    with pytest.raises(ValueError, match='δεν χωράει'):
        cw.reshape_command(doc, piece.params['curve']['id'], n=96)
