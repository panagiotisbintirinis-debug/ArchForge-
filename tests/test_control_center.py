"""Custom control surfaces must reuse commands and preserve the editor/document."""
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPointF, QSettings, Qt
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtWidgets import QApplication, QGraphicsView, QHBoxLayout, QMainWindow, QMenuBar, QWidget

from archforge.ui import control_center, toolbar_custom


def sample_window():
    app = QApplication.instance() or QApplication([])
    window = QMainWindow()
    window._source_bar = window.menuBar()
    menu = window._source_bar.addMenu("Κατασκευή")
    window._source_menu = menu  # keep the PySide wrapper (production: _work_menus)
    action = menu.addAction("Τοίχος")
    fired = []
    action.triggered.connect(lambda: fired.append("wall"))
    menu.setParent(window, menu.windowFlags())  # same ownership transfer as layout2._install_top_row
    top = QWidget()
    top.setLayout(QHBoxLayout())
    menubar = QMenuBar(top)
    menubar.addMenu(menu)
    top.layout().addWidget(menubar)
    window.setMenuWidget(top)
    window.menuBar = lambda: menubar
    window._top_row = top
    window._top_menu_bar = menubar
    window._ui_prefs = {**toolbar_custom.DEFAULTS, "personal_menus": [], "mouse_buttons": {}}
    return app, window, action, fired


def test_modes_share_original_action_and_keep_original_menu():
    app, window, action, fired = sample_window()
    try:
        cfg = {"id": "example", "title": "Δικά μου", "commands": ["Κατασκευή / Τοίχος"], "size": 28}
        window._ui_prefs["personal_menus"].append(cfg)
        menus = control_center.PersonalMenus(window)
        for mode in ("popup", "docked", "floating"):
            cfg["mode"] = mode
            menus.apply()
            bar, launcher = menus.surfaces["example"]
            if mode == "popup":
                assert launcher.menu().actions()[0] is action
            elif mode == "docked":
                assert bar.actions()[0] is action
                assert bar.iconSize().width() == 28
            else:
                assert bar.isFloating()
                contents = bar.widget().widget()
                assert contents.layout().itemAt(0).widget().defaultAction() is action
            action.trigger()
            assert window.menuBar().actions()[0].menu().actions()[0] is action
        assert fired == ["wall"] * 3
        menus._remove()
    finally:
        window.close()
        app.processEvents()


def test_saved_config_survives_reload_without_entering_document(tmp_path):
    app, window, _action, _fired = sample_window()
    settings = QSettings(str(tmp_path / "layout.ini"), QSettings.Format.IniFormat)
    try:
        window._ui_prefs["personal_menus"] = [{"id": "a", "title": "Νέο", "commands": ["Κατασκευή / Τοίχος"],
                                                "mode": "popup", "size": 32}]
        window._ui_prefs["mouse_buttons"] = {"plan": {"back": "Κατασκευή / Τοίχος"}}
        toolbar_custom.save(window, settings)
        window._ui_prefs = {}
        toolbar_custom.load(window, settings)
        assert window._ui_prefs["personal_menus"][0]["size"] == 32
        assert window._ui_prefs["mouse_buttons"]["plan"]["back"] == "Κατασκευή / Τοίχος"
        toolbar_custom.reset(window, settings)
        assert window._ui_prefs["personal_menus"][0]["title"] == "Νέο"
        assert window._ui_prefs["mouse_buttons"]["plan"]["back"] == "Κατασκευή / Τοίχος"
    finally:
        window.close()
        app.processEvents()


def test_menu_reorganization_retains_saved_command_relationships():
    app, window, action, fired = sample_window()
    try:
        old_path = "Παλιό / Δημιουργία τοίχου"
        window._menu_aliases = {old_path: "Κατασκευή / Τοίχος"}
        window._ui_prefs["personal_menus"] = [{"id": "old", "title": "Σχέδια",
                                                 "mode": "docked", "commands": [old_path]}]
        window._ui_prefs["mouse_buttons"] = {"plan": {"back": old_path}}
        menus = control_center.PersonalMenus(window)
        assert menus.surfaces["old"][0].actions() == [action]
        view = QGraphicsView(window)
        view.controller = SimpleNamespace(tool="select", active=None)
        window.plan_view = view
        dispatcher = control_center.MouseButtonDispatcher(window)
        pane = view.viewport()
        for kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            event = QMouseEvent(kind, QPointF(25, 25), QPointF(25, 25), QPointF(25, 25),
                                Qt.MouseButton.BackButton,
                                Qt.MouseButton.BackButton if kind == QEvent.Type.MouseButtonPress
                                else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
            assert dispatcher.eventFilter(pane, event)
        assert fired == ["wall"]
        menus._remove()
    finally:
        window.close()
        app.processEvents()


def test_3d_webgl_buttons_use_the_existing_menu_command():
    from PySide6.QtCore import QObject
    from archforge.ui.pbr_viewport import PBRInteractionBridge, pbr_page_html
    app, window, action, fired = sample_window()
    try:
        class View(QObject):
            pass

        view = View()
        view.marking_menu_window = window
        bridge = PBRInteractionBridge(view)
        bridge.runControlAction("Κατασκευή / Τοίχος")
        assert fired == ["wall"]
        assert window.menuBar().actions()[0].menu().actions()[0] is action
        html = pbr_page_html()
        assert "afSetMouseButtons" in html and "bridge.runControlAction(press.path)" in html

        class Page:
            def __init__(self):
                self.scripts = []
            def runJavaScript(self, script):
                self.scripts.append(script)

        page = Page()
        window.pbr_view = SimpleNamespace(web_view=SimpleNamespace(page=lambda: page))
        window.structural_view = SimpleNamespace(web_view=SimpleNamespace(page=lambda: page))
        window._ui_prefs["mouse_buttons"] = {"3d": {"right": "Κατασκευή / Τοίχος"}}
        control_center.push_3d_bindings(window)
        assert len(page.scripts) == 2 and '"2":' in page.scripts[0]
    finally:
        window.close()
        app.processEvents()


def test_personal_menu_profile_export_import(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    app, window, original, _fired = sample_window()
    path = tmp_path / "controls.json"
    try:
        window._personal_menus = control_center.PersonalMenus(window)
        editor = control_center.ControlCenter(window)
        editor._add_group()
        editor._current()["commands"] = ["Κατασκευή / Τοίχος"]
        editor._commit()
        editor._bind("plan", "back", "Κατασκευή / Τοίχος")
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(path), "JSON (*.json)"))
        monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a: (str(path), "JSON (*.json)"))
        editor._export()
        assert path.exists()
        window._ui_prefs["personal_menus"].clear()
        window._ui_prefs["mouse_buttons"].clear()
        editor._import()
        assert window._ui_prefs["personal_menus"][0]["commands"] == ["Κατασκευή / Τοίχος"]
        assert window._ui_prefs["mouse_buttons"]["plan"]["back"] == "Κατασκευή / Τοίχος"
        assert window.menuBar().actions()[0].menu().actions()[0] is original
        editor.accept()
    finally:
        window.close()
        app.processEvents()


def test_mouse_button_assignment_dispatches_same_action_only_in_select_mode():
    app, window, action, fired = sample_window()
    try:
        view = QGraphicsView(window)
        view.controller = SimpleNamespace(tool="select", active=None)
        window.plan_view = view
        window._ui_prefs["mouse_buttons"] = {"plan": {"back": "Κατασκευή / Τοίχος"}}
        manager = control_center.MouseButtonDispatcher(window)
        pane = view.viewport()

        def event(kind):
            return QMouseEvent(kind, QPointF(25, 25), QPointF(25, 25), QPointF(25, 25),
                               Qt.MouseButton.BackButton,
                               Qt.MouseButton.BackButton if kind == QEvent.Type.MouseButtonPress
                               else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)

        assert manager.eventFilter(pane, event(QEvent.Type.MouseButtonPress))
        assert manager.eventFilter(pane, event(QEvent.Type.MouseButtonRelease))
        assert fired == ["wall"]
        view.controller.tool = "wall"
        assert not manager.eventFilter(pane, event(QEvent.Type.MouseButtonPress))
        assert fired == ["wall"]
        assert window.menuBar().actions()[0].menu().actions()[0] is action
    finally:
        window.close()
        app.processEvents()


def test_real_archforge_control_center_preserves_work_menus_and_document():
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        control_center._catalog(window)
        before = {(a.text(), a.objectName()) for top in window.menuBar().actions() if top.menu()
                  for a in control_center._all_original_actions(top.menu())}
        original_shortcuts = dict(window.shortcuts.actions)
        document = window.doc.to_dict()
        assert window._control_center_action in window._work_sections[("⚙ Ρυθμίσεις", "Χειρισμός")].actions()
        editor = control_center.ControlCenter(window)
        editor._add_group()
        editor.search.setText("Τοίχος")
        assert editor.catalog.count() > 0
        editor.catalog.setCurrentRow(0)
        editor._add_command()
        editor.mode.setCurrentIndex(editor.mode.findData("floating"))
        editor.size.setValue(32)
        editor.width.setValue(320)
        assert window._personal_menus.surfaces
        after = {(a.text(), a.objectName()) for top in window.menuBar().actions() if top.menu()
                 for a in control_center._all_original_actions(top.menu())}
        assert before == after
        assert all(window.shortcuts.actions[key] is action for key, action in original_shortcuts.items())
        assert window.doc.to_dict() == document
        editor.accept()
    finally:
        window._mark_clean()
        window.close()
        app.processEvents()
