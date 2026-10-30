"""Διάταξη 2, approved by the owner on 14/10 (`docs/mockups/diataxi2_2026-10-14.png`)."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPoint, Qt


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1536, 1000); w.show(); app.processEvents()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def test_first_row_has_name_quick_buttons_and_the_menus_on_the_right(window):
    row = window.menuWidget()
    assert row is window._top_row and window.menuBar() is window._top_menu_bar
    assert window._top_menu_bar.parentWidget() is row
    assert [b.defaultAction() for b in window._quick_buttons] == [window.save_action, window.undo_action, window.redo_action]
    # menus at the right end of the row, the name at the left
    assert window._top_menu_bar.geometry().right() > row.width() - 40
    assert window._project_name_label.geometry().left() < 200
    window.setWindowTitle('ArchForge — σπίτι.archforge[*]')
    assert window._project_name_label.text() == '— σπίτι.archforge'
    # the moved menus still work
    assert window._main_menus['Αρχείο'].actions()


def test_window_keeps_its_size_on_a_laptop(window):
    assert window.height() <= 1000 and window.minimumSizeHint().height() <= 900


def test_tool_groups_are_movable_bars_with_a_title_that_opens_the_group(window):
    groups = window._tool_groups
    assert list(groups) == ['select', 'build', 'library', 'storey']
    for g in groups.values():
        assert g.isVisible() and g.isMovable() and g.isFloatable()
    assert groups['build'].caption.text() == 'Κατασκευή ▾'
    assert groups['build'].caption.menu() is window._main_menus['Κατασκευή']
    assert groups['build'].caption.menu().isTearOffEnabled()          # 📌 stays open
    assert groups['library'].caption.menu() is window._main_menus['Βιβλιοθήκη']
    assert window.floor_selector in groups['storey'].items and window.floor_selector.isVisible()
    # the old bars are not shown twice
    for bar in (window._mockup_ribbon, window._mockup_floor_bar, window._mockup_camera_bar, window._mockup_snap_bar):
        assert bar.isHidden()


def test_group_buttons_run_the_same_commands(window):
    wall = next(a for a in window._tool_groups['build'].items if hasattr(a, 'text') and a.text() == 'Τοίχος')
    wall.trigger()
    assert window.plan_view.controller.tool == 'wall'
    window._layout2_object_action  # exists
    on = window.sculpt_action.isChecked()
    window._layout2_sculpt_action.trigger()
    assert window.sculpt_action.isChecked() != on
    window._layout2_sculpt_action.trigger()


def test_view_settings_sit_on_the_drawing(window):
    corner = window._central_tabs.cornerWidget(Qt.Corner.TopRightCorner)
    assert corner is window._view_settings and corner.isVisible()
    for w in (window._mockup_view_button, window._mockup_style_button, window._mockup_grid_check,
              window._mockup_snap_check, window._mockup_snap_size):
        assert w.parentWidget() is corner and w.isVisible()


def test_common_palette_bottom_right_draggable_and_configurable(window):
    from PySide6.QtWidgets import QApplication
    palette = window._common_palette
    host = palette.parentWidget()
    assert palette.isVisible()
    assert palette.geometry().right() > host.width() * 0.6 and palette.geometry().bottom() > host.height() * 0.6
    assert {'tool.select', 'edit.move', 'edit.rotate', 'edit.delete', 'edit.undo', 'view.zoom_all'} <= set(palette.buttons)
    palette.buttons['edit.move'].click()
    assert window.plan_view.controller.tool == 'move'
    # dragged: stays inside, and keeps its distance from the corner when the window resizes
    palette.drag_to(QPoint(-50, -50))
    assert palette.pos() == QPoint(0, 0)
    off = palette.offset
    window.resize(1400, 950); QApplication.processEvents()
    assert palette.offset == off and palette.pos().x() == max(0, host.width() - palette.width() - off.x())
    # ⚙ hides a button; the panel menu closes and reopens the palette
    palette.choose_menu.aboutToShow.emit()                   # ⚙ = the same «Προσαρμογή» as a right click
    hide_move = next(a for a in palette.choose_menu.actions() if a.text() == palette.buttons['edit.move'].text())
    hide_move.setChecked(False)
    assert 'edit.move' not in palette.shown()
    palette.toggle_action.setChecked(False); assert palette.isHidden()
    panels = next(a.menu() for a in window._work_sections[('⚙ Ρυθμίσεις', 'Περιβάλλον')].actions() if a.text() == 'Πάνελ')
    assert palette.toggle_action in panels.actions()
    palette.toggle_action.setChecked(True); assert palette.isVisible()


def test_panels_are_on_the_right_properties_above(window):
    from PySide6.QtWidgets import QDockWidget
    docks = [d for d in window.findChildren(QDockWidget) if d.isVisible() and not d.isFloating()]
    assert docks
    for d in docks:
        assert window.dockWidgetArea(d) == Qt.DockWidgetArea.RightDockWidgetArea, d.objectName()
    project = next(d for d in docks if d.objectName() == 'approved_project_library')
    assert window.dock.geometry().bottom() < project.geometry().top()


def test_layout_version_was_raised():
    from archforge.ui.workspace_layout import LAYOUT_VERSION
    assert LAYOUT_VERSION >= 3


def test_no_start_guide_box_over_an_empty_plan(window):
    """Owner 14/10: «βγάλε τον οδηγό Ξεκίνα» (the box over an empty project)."""
    from archforge.ui import plan_overlay
    assert not hasattr(plan_overlay, 'EMPTY_HINT')
    window.plan_view.viewport().grab()                                 # paints without it
