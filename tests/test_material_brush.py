"""«Πινέλο» υλικού (owner 28/10): choose in the Library, then every click paints — one undo per click, on a wall the
clicked face, Esc ends."""
import pytest

from archforge.core.commands import AddEntity
from archforge.core.model import Entity
from archforge.ui.material_brush import TOOL, paint, wall_side_role


def _wall(**kw):
    return Entity('wall', {'x1': 0.0, 'y1': 0.0, 'x2': 4.0, 'y2': 0.0, 'z': 0.0, 'height': 2.7, 'thickness': 0.2, **kw})


def test_the_clicked_half_of_the_wall_is_the_painted_face():
    wall = _wall()
    assert wall_side_role(wall, 2.0, 0.05) == 'exterior'     # side A = left of x1→x2
    assert wall_side_role(wall, 2.0, -0.05) == 'interior'
    reverse = _wall(x1=4.0, x2=0.0)
    assert wall_side_role(reverse, 2.0, 0.05) == 'interior'


@pytest.fixture
def window(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.rendering import user_materials as um
    from archforge.ui.main_window import MainWindow
    monkeypatch.setenv('ARCHFORGE_DATA', str(tmp_path / 'data'))
    um.reload()
    QApplication.instance() or QApplication([])
    w = MainWindow()
    w.resize(1200, 800)
    yield w
    w.hide()
    um.reload()


def _click(w, x, y):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    QTest.mouseClick(w.plan_view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     w.plan_view.mapFromScene(QPointF(x, y)))


def test_ribbon_brush_chooses_in_the_library_then_each_click_paints_one_undo(window, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog
    from archforge.ui.material_library import MaterialLibraryDialog
    w = window
    wall = _wall(); w.stack.execute(AddEntity(wall))
    box = Entity('box', {'x': 1.0, 'y': 2.0, 'z': 0.0, 'width': 1.0, 'depth': 1.0, 'height': 1.0})
    w.stack.execute(AddEntity(box))

    def choose(dialog):
        assert dialog.brush and dialog.entity is None
        item = next(dialog.grid.item(i) for i in range(dialog.grid.count())
                    if dialog.grid.item(i).data(Qt.ItemDataRole.UserRole) == 'wood_oak')
        dialog.grid.setCurrentItem(item)
        assert dialog.apply.isEnabled()                      # no object selected: the brush still takes the material
        dialog._apply()
        return dialog.result()
    monkeypatch.setattr(MaterialLibraryDialog, 'exec', choose)
    w._mockup_brush_action.trigger()
    assert w.plan_view.controller.tool == TOOL
    w.plan_view.centerOn(2.0, 1.0); w.plan_view.redraw()
    undo_before = len(w.stack.done)

    _click(w, 2.0, 0.06)                                     # side A half of the wall
    assert w.doc.get(wall.id).params['surface_materials'] == {'exterior': 'wood_oak'}
    _click(w, 1.5, 2.5)                                      # the box: whole object
    assert w.doc.get(box.id).params['material_id'] == 'wood_oak'
    assert len(w.stack.done) == undo_before + 2        # one undo per click

    w.stack.undo()
    assert not w.doc.get(box.id).params.get('material_id')
    assert w.doc.get(wall.id).params['surface_materials'] == {'exterior': 'wood_oak'}

    QTest.keyClick(w.plan_view.viewport(), Qt.Key.Key_Escape)
    assert w.plan_view.controller.tool == 'select'
    _click(w, 2.0, -0.06)                                    # after Esc a click selects, it does not paint
    assert w.doc.get(wall.id).params['surface_materials'] == {'exterior': 'wood_oak'}

    # «Κλείσιμο» in the Library starts nothing.
    monkeypatch.setattr(MaterialLibraryDialog, 'exec', lambda self: QDialog.DialogCode.Rejected)
    w._mockup_brush_action.trigger()
    assert w.plan_view.controller.tool == 'select'


def test_brush_click_on_empty_space_or_unsupported_kind_changes_nothing(window):
    w = window
    wall = _wall(); w.stack.execute(AddEntity(wall))
    w._brush_material_id = 'wood_oak'
    undo_before = len(w.stack.done)
    assert paint(w, None, 9.0, 9.0) is None
    from archforge.site.plants import SPECIES
    plant = Entity('plant', {'x': 5.0, 'y': 5.0, 'z': 0.0, 'species': 'tree', **SPECIES['tree']})
    w.stack.execute(AddEntity(plant)); undo_before += 1
    assert paint(w, plant.id, 5.0, 5.0) is None
    assert len(w.stack.done) == undo_before
    assert paint(w, wall.id, 2.0, -0.05) == 'interior'
    assert w.doc.get(wall.id).params['surface_materials'] == {'interior': 'wood_oak'}


# --- 3D (owner 29/10: «πρέπει να δουλεύει στο 3Δ περισσότερο») -----------------------------------------------------

def test_a_3d_click_paints_exactly_the_face_hit_where_the_object_keeps_one_finish_per_face():
    from archforge.core.model import Document
    from archforge.ui.material_brush import face_role
    doc = Document()
    wall, door = _wall(), Entity('door', {})
    box = Entity('box', {'x': 0, 'y': 0, 'z': 0, 'width': 1, 'depth': 1, 'height': 1})
    slab = Entity('floor', {})
    assert face_role(doc, wall, 'exterior') == 'exterior'
    assert face_role(doc, wall, 'top') == 'top'            # walls draw every face with its own finish
    assert face_role(doc, slab, 'edge') == 'edge'
    assert face_role(doc, door, 'leaf') == 'leaf'          # the browser's own parts (Φύλλο, Κάσα …)
    assert face_role(doc, box, 'front') == ''              # a box has one finish: the whole object
    assert face_role(doc, wall, '') == ''


def test_3d_bridge_paints_the_clicked_face_one_undo_and_esc_ends_the_brush_in_both_views(window):
    import json
    from archforge.ui.material_brush import start
    w = window
    wall = _wall(); w.stack.execute(AddEntity(wall))
    assert start(w, 'wood_oak')
    assert w.plan_view.controller.tool == TOOL and w.pbr_view.active_tool == TOOL
    done = len(w.stack.done)
    bridge = w.pbr_view.bridge
    if bridge is None:                                       # no WebEngine page here: the same slot object
        from archforge.ui.pbr_viewport import PBRInteractionBridge
        bridge = PBRInteractionBridge(w.pbr_view)
    bridge.paintMaterial(json.dumps({'entity_id': wall.id, 'surface_role': 'top'}))
    bridge.paintMaterial(json.dumps({'entity_id': wall.id, 'surface_role': 'interior'}))
    bridge.paintMaterial(json.dumps({'entity_id': '', 'surface_role': ''}))      # empty sky: nothing
    assert w.doc.get(wall.id).params['surface_materials'] == {'top': 'wood_oak', 'interior': 'wood_oak'}
    assert len(w.stack.done) == done + 2
    w.stack.undo()
    assert w.doc.get(wall.id).params['surface_materials'] == {'top': 'wood_oak'}
    bridge.endPaintMaterial()
    assert w.plan_view.controller.tool == 'select' and w.pbr_view.active_tool == 'select'


def test_another_tool_ends_the_brush_in_both_views(window):
    from archforge.ui.material_brush import start
    w = window
    assert start(w, 'wood_oak')
    w._set_active_tool('wall')
    assert w.plan_view.controller.tool != TOOL and w.pbr_view.active_tool != TOOL


def test_the_real_3d_page_sends_the_face_under_the_click():
    """The page's own raycast (headless Chromium, software WebGL): clicks with the brush report entity + face."""
    import json
    from archforge.core.model import Document
    from archforge.scenarios import click3d
    if not click3d.available():
        pytest.skip('χωρίς Node / Playwright / Chromium')
    doc = Document()
    wall = _wall(); doc.add(wall)
    calls = click3d.clicks(doc, TOOL, cols=12, rows=8)
    hits = {(json.loads(c[1])['entity_id'], json.loads(c[1])['surface_role']) for c in calls if c[0] == 'paintMaterial'}
    assert (wall.id, 'exterior') in hits or (wall.id, 'interior') in hits
    assert ('', '') in hits                                  # a click beside the wall paints nothing
