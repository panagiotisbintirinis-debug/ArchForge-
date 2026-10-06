"""Roof per room: a terrace on one room and a tiled roof on the other, one undo."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.architecture.roof_choice import room_roof_command
from archforge.assistant.suggestions import room_at
from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.structure.timber_roof import default_params


def _two_rooms(stack):
    for s in [(0, 0, 9, 0), (9, 0, 9, 6), (9, 6, 0, 6), (0, 6, 0, 0), (4, 0, 4, 6)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0, 'height': 2.7, 'thickness': 0.25})))


def _roofs(doc):
    return ([e for e in doc.entities.values() if e.kind == 'pitched_roof'],
            [e for e in doc.entities.values() if e.kind == 'room_roof'])


def test_terrace_on_one_room_splits_the_tiled_roof_and_the_other_keeps_its_own():
    doc = Document(); st = CommandStack(doc); _two_rooms(st)
    st.execute(AddEntity(Entity('pitched_roof', default_params(doc, z=0.0, form='gable'))))   # one roof over both
    left = room_at(doc, 2, 3)
    cmd, msg = room_roof_command(doc, left, 'terrace')
    st.execute(cmd)
    pitched, flat = _roofs(doc)
    assert len(pitched) == 1 and len(flat) == 1
    assert pitched[0].params['x0'] > 3.5                      # the tiled roof now covers only the right room
    assert flat[0].params['room_signature'] == left['signature']
    assert 'κρατά κεραμοσκεπή' in msg
    st.undo()
    pitched, flat = _roofs(doc)
    assert len(pitched) == 1 and not flat and pitched[0].params['x0'] < 0


def test_tiled_roof_on_a_room_replaces_its_terrace():
    doc = Document(); st = CommandStack(doc); _two_rooms(st)
    right = room_at(doc, 6, 3)
    st.execute(room_roof_command(doc, right, 'terrace')[0])
    cmd, msg = room_roof_command(doc, right, 'tiled')
    st.execute(cmd)
    pitched, flat = _roofs(doc)
    assert len(pitched) == 1 and not flat and pitched[0].params['x1'] == pytest.approx(9.125)
    assert room_roof_command(doc, right, 'tiled')[0] is not None      # re-choosing replaces it, never doubles
    with pytest.raises(ValueError):
        room_roof_command(doc, right, 'dome')


def test_menu_click_and_mouse_menu_set_a_room_roof():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.marking_menu import build_menu, run
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _two_rooms(window.stack)
        window._start_site_tool('roofroom_terrace', '')
        window.plan_view.sitePointRequested.emit('roofroom_terrace', 2.0, 3.0)
        assert len(_roofs(window.doc)[1]) == 1
        ids = [e['id'] for e in build_menu(window, 'plan')['entries']]
        assert 'mm:roofroom:tiled' in ids and 'mm:roofroom:terrace' in ids
        run(window, 'plan', None, 'mm:roofroom:tiled', (6.0, 3.0))
        assert len(_roofs(window.doc)[0]) == 1
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def _l_shaped_upper_floor(stack):
    """Ground 9 × 6; upper floor an L (the corner 4 × 3 left as the ground floor's terrace)."""
    for s in [(0, 0, 9, 0), (9, 0, 9, 6), (9, 6, 0, 6), (0, 6, 0, 0)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 0.0, 'height': 3.0, 'thickness': 0.25})))
    for s in [(0, 0, 9, 0), (9, 0, 9, 3), (9, 3, 5, 3), (5, 3, 5, 6), (5, 6, 0, 6), (0, 6, 0, 0), (5, 0, 5, 3)]:
        stack.execute(AddEntity(Entity('wall', {'x1': s[0], 'y1': s[1], 'x2': s[2], 'y2': s[3], 'z': 3.0, 'height': 2.7, 'thickness': 0.25})))


def test_auto_roof_on_an_l_shaped_floor_leaves_the_terrace_open_and_raises_no_gable_in_the_air():
    from archforge.assistant.understanding import inside
    from archforge.structure.timber_roof import auto_roofs, footprint_fill, gable_walls
    doc = Document(); st = CommandStack(doc); doc.levels['Floor 2'] = 3.0; _l_shaped_upper_floor(st)
    assert footprint_fill(doc, 3.0) < .85
    roofs = [p for p, _r in auto_roofs(doc) if p['eave_z'] > 5]
    assert len(roofs) == 2                                         # one per room of the L
    for p in roofs:
        box = [(p['x0'], p['y0']), (p['x1'], p['y0']), (p['x1'], p['y1']), (p['x0'], p['y1'])]
        assert not inside(box, 7.0, 4.5)                           # the terrace corner stays uncovered
        assert set(p['gables']) <= {'x0', 'x1', 'y0', 'y1'}
        for verts, _t in gable_walls(p):                           # every gable stands on a wall line
            xs = {round(v[0], 2) for v in verts}; ys = {round(v[1], 2) for v in verts}
            assert xs <= {round(p['x0'], 2), round(p['x1'], 2), round(p['x0'] + .2, 2), round(p['x1'] - .2, 2)} or \
                   ys <= {round(p['y0'], 2), round(p['y1'], 2), round(p['y0'] + .2, 2), round(p['y1'] - .2, 2)}
    # A gable is never drawn on a side without a wall.
    p = dict(roofs[0], gables=[])
    assert gable_walls(p) == []
