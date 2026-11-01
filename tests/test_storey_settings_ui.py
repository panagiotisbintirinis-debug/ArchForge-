"""Storey table and icon menus operate on original live commands/document."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QToolBar

from archforge.core.commands import _restore_document_state
from archforge.ui import storey_settings, task_icons, toolbar_custom
from archforge.ui.main_window import MainWindow
from test_storey_height_edits import house


def test_storey_editor_both_heights_one_atomic_undo_and_same_qaction():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        document, (_lower, upper, door, slab, ceiling, stairs, furniture) = house()
        _restore_document_state(window.doc, document.to_dict(), [])
        window._refresh_floor_selector()
        original = window.doc.to_dict()
        action = window._storey_settings_action
        assert action in window._work_sections[("Έργο", "Όροφοι")].actions()
        assert action in toolbar_custom.catalog(window).values()
        assert action in window._tool_groups["storey"].items
        dialog = storey_settings.StoreySettings(window)
        assert window.doc.to_dict() == original
        row = dialog.names.index("Floor 1")
        dialog.table.setCurrentCell(row, 0)
        assert dialog.elevation.value() == 3.7
        assert dialog.height.value() == 2.7
        dialog.elevation.setValue(3.2)
        dialog.height.setValue(2.9)
        done = len(window.stack.done)
        dialog.apply_changes()
        assert len(window.stack.done) == done + 1
        assert window.doc.levels["Floor 1"] == 3.2
        assert window.doc.get(upper.id).params["z"] == 3.2
        assert window.doc.get(upper.id).params["height"] == 2.9
        assert window.doc.get(ceiling.id).params["level_z"] == 3.2
        assert window.doc.get(ceiling.id).params["offset_z"] == 2.9
        assert window.doc.get(stairs.id).params["upper_z"] == 3.2
        assert window.doc.get(furniture.id).params["z"] == 3.2
        assert window.doc.get(door.id).parent_id == upper.id
        assert window.floor_selector.currentData()[1] == 3.2
        assert window.doc.entities[upper.id] is not None
        window.stack.undo()
        assert window.doc.to_dict() == original
        dialog.close()
    finally:
        window._mark_clean()
        window.close()
        app.processEvents()


def test_initial_icons_are_on_original_commands_and_row_is_user_owned():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        paths = toolbar_custom.catalog(window)
        action = paths["Κατασκευή / Ανοίγματα / Πόρτα"]
        assert not action.icon().isNull()
        configs = toolbar_custom.prefs(window)["personal_menus"]
        assert toolbar_custom.prefs(window)["task_icons_seeded"] is True
        # Fresh test workspace has no prior personal layouts.
        assert len(configs) >= 1
        starter = next(c for c in configs if c["id"] == "starter_task_icons")
        assert starter["show_labels"] is False
        bar = window._personal_menus.surfaces[starter["id"]][0]
        assert isinstance(bar, QToolBar)
        assert bar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert action in bar.actions()
        assert any(a is action for a in window._work_sections[("Κατασκευή", "Ανοίγματα")].actions())
        assert len([a for a in paths.values() if not a.icon().isNull()]) >= 80
        # Manual deletion is not silently undone by the starter installer.
        configs.remove(starter)
        task_icons.install(window)
        assert not any(c["id"] == "starter_task_icons" for c in configs)
    finally:
        window._mark_clean()
        window.close()
        app.processEvents()
