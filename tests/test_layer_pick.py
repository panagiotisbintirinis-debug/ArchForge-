"""Owner 30/10: «κάθε στρώση να είναι επιλέξιμη και δυνατότητα να αλλαχτεί» — a click on a layer of the selected
wall picks that layer (outline in the plan, row marked in Ιδιότητες, menu by the cursor) and changes it, one undo."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    w._no_modal_dialogs = True
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _wall(w, y=0.0, wall_type='brick_double_insulated', thickness=0.27):
    e = Entity('wall', {'x1': 0.0, 'y1': y, 'x2': 4.0, 'y2': y, 'z': 0.0, 'height': 2.7, 'thickness': thickness,
                        'wall_type': wall_type})
    w.stack.execute(AddEntity(e))
    return e.id


def test_the_layer_under_a_point_is_found_by_its_place_in_the_type():
    from archforge.core.commands import CommandStack
    from archforge.core.model import Document
    from archforge.ui.layer_pick import layer_at
    doc = Document(); st = CommandStack(doc)
    e = Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.27,
                        'wall_type': 'brick_double_insulated'})
    st.execute(AddEntity(e))
    # side A (+y) is the exterior: plaster 0.135…0.115, brick …0.025, XPS …−0.025, brick …−0.115, plaster
    assert [layer_at(doc, e.id, 2.0, y) for y in (0.125, 0.07, 0.0, -0.07, -0.125, 0.5)] == [0, 1, 2, 3, 4, None]


def test_a_click_on_a_selected_wall_picks_the_layer_and_its_menu_changes_it(window):
    from archforge.ui import layer_pick
    w = window
    eid = _wall(w); _wall(w, y=3.0)
    w.doc.select([eid]); w.refresh_inspector()
    assert layer_pick.pick(w, eid, 2.0, 0.0) == 2                       # the XPS
    assert layer_pick.current(w) == (eid, 2)
    assert [r['picked'] for r in w._wall_layer_rows] == [False, False, True, False, False]
    w._layer_menu_actions['material:mineral_wool'].trigger()
    p = w.doc.get(eid).params
    assert p['wall_type'].startswith('proj_')                            # built-in type → this wall's own copy
    from archforge.architecture.wall_types import layers
    assert layers(p['wall_type'], w.doc)[2].material_id == 'mineral_wool'
    assert layer_pick.current(w) == (eid, 2)                            # still that layer
    w.stack.undo()
    assert w.doc.get(eid).params['wall_type'] == 'brick_double_insulated'


def test_the_picked_layer_moves_out_and_is_removed_with_one_undo_each(window):
    from archforge.architecture.wall_types import layers
    from archforge.ui import layer_pick
    w = window
    eid = _wall(w)
    w.doc.select([eid])
    layer_pick.pick(w, eid, 2.0, 0.0)
    w._layer_menu_actions['out'].trigger()
    mats = [l.material_id for l in layers(w.doc.get(eid).params['wall_type'], w.doc)]
    assert mats[1] == 'xps' and layer_pick.current(w) == (eid, 1)
    layer_pick.pick(w, eid, 2.0, 0.0)
    w._layer_menu_actions['remove'].trigger()
    assert len(layers(w.doc.get(eid).params['wall_type'], w.doc)) == 4
    w.stack.undo(); w.stack.undo()
    assert w.doc.get(eid).params['wall_type'] == 'brick_double_insulated'


def test_clicks_in_the_plan_select_then_pick_and_the_layer_is_outlined(window):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    w = window
    eid = _wall(w)
    view = w.plan_view
    view.resize(900, 600); view.show(); view.controller.set_tool('select'); view.redraw()
    view.centerOn(2.0, 0.0)
    for _ in range(3):
        QApplication.processEvents()
    at = QPointF(view.mapFromScene(2.0, 0.0))

    def click():
        for kind in (QMouseEvent.Type.MouseButtonPress, QMouseEvent.Type.MouseButtonRelease):
            ev = QMouseEvent(kind, at, view.mapToGlobal(at.toPoint()).toPointF(), Qt.MouseButton.LeftButton,
                             Qt.MouseButton.LeftButton if kind == QMouseEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton,
                             Qt.KeyboardModifier.NoModifier)
            (view.mousePressEvent if kind == QMouseEvent.Type.MouseButtonPress else view.mouseReleaseEvent)(ev)
    click()
    assert list(w.doc.selection) == [eid] and view.layer_pick is None   # first click: the wall
    click()
    assert view.layer_pick == (eid, 2)                                  # second click: its layer (XPS at the axis)
    view.redraw()
    from PySide6.QtWidgets import QGraphicsPathItem
    assert any(isinstance(i, QGraphicsPathItem) and i.zValue() == 25 for i in view._scene.items())
