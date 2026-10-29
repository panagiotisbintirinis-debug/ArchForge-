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
