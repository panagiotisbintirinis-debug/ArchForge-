"""Human-owned control surfaces.  These are presentations of existing QActions.

Personal menus never copy commands or alter the Document.  All customisation is
stored in the same user layout preferences as the existing ribbons and mouse
marking menus.  The original work menus remain a complete recovery path.
"""
from __future__ import annotations

import json
from uuid import uuid4

from PySide6.QtCore import QEvent, QObject, QSize, QTimer, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDockWidget, QFileDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QScrollArea, QSpinBox, QTabWidget,
    QToolBar, QToolButton, QVBoxLayout, QWidget,
)

from archforge.ui import toolbar_custom

MODES = (("Σταθερό", "docked"), ("Αναδυόμενο", "popup"), ("Ιπτάμενο", "floating"))
BUTTONS = (("Αριστερό", Qt.MouseButton.LeftButton, "left"),
           ("Μεσαίο / ροδέλα", Qt.MouseButton.MiddleButton, "middle"),
           ("Δεξί", Qt.MouseButton.RightButton, "right"),
           ("Πίσω (πλευρικό)", Qt.MouseButton.BackButton, "back"),
           ("Εμπρός (πλευρικό)", Qt.MouseButton.ForwardButton, "forward"))
MAX_CUSTOM_MENUS = 20
MAX_COMMANDS = 40


def _menus(window):
    p = toolbar_custom.prefs(window)
    if not isinstance(p.get("personal_menus"), list):
        p["personal_menus"] = []
    return p["personal_menus"]


def _buttons(window):
    p = toolbar_custom.prefs(window)
    if not isinstance(p.get("mouse_buttons"), dict):
        p["mouse_buttons"] = {}
    return p["mouse_buttons"]


def _catalog(window):
    # QAction identity (and its undo, model, check state and other connections)
    # is shared by each launcher, ribbon and original menu.
    return toolbar_custom.catalog(window)


def _resolve_saved_path(window, path, actions=None):
    """Keep a saved binding usable if a command moves in a later menu revision."""
    if not isinstance(path, str):
        return None
    actions = _catalog(window) if actions is None else actions
    if path in actions:
        return path
    from archforge.ui.main_menus import resolve_path
    updated = resolve_path(window, path)
    return updated if updated in actions else None


def _all_original_actions(menu):
    """Traverse the live QAction objects, including nested menu commands."""
    for action in menu.actions():
        yield action
        if action.menu() is not None:
            yield from _all_original_actions(action.menu())


def _persist(window):
    toolbar_custom.save(window)
    from archforge.ui.workspace_layout import persistence_enabled, save_layout
    if persistence_enabled():
        save_layout(window)


def push_3d_bindings(window):
    """Deliver user click assignments to both authoritative 3D WebGL views."""
    context = _buttons(window).get("3d", {})
    if not isinstance(context, dict):
        context = {}
    codes = {"left": "0", "middle": "1", "right": "2", "back": "3", "forward": "4"}
    payload = {}
    for key, code in codes.items():
        value = context.get(key)
        if isinstance(value, str) and value:
            payload[code] = value
    script = "if (window.afSetMouseButtons) window.afSetMouseButtons(" + json.dumps(payload) + ");"
    for name in ("pbr_view", "structural_view"):
        view = getattr(window, name, None)
        web = getattr(view, "web_view", None)
        if web is not None:
            web.page().runJavaScript(script)


class _FloatingMenu(QDockWidget):
    """A resizable floating user menu that remembers manual moves and resizing."""

    def __init__(self, title, window, config):
        super().__init__(title, window)
        self._window = window
        self._config = config
        self._track = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(500)
        self._timer.timeout.connect(lambda: _persist(window))

    def _remember(self):
        if getattr(self, "_track", False):
            self._config.update(x=self.pos().x(), y=self.pos().y(),
                                width=self.width(), height=self.height())
            self._timer.start()

    def moveEvent(self, event):
        super().moveEvent(event)
        self._remember()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._remember()


class MouseButtonDispatcher(QObject):
    """Optional click-only assignments; untouched gestures use the native editor.

    A mapped click is emitted on release, so a drag cannot accidentally run a
    command.  It is active only while the Select tool is idle; drawing, sculpt,
    selection handles and all intermediate transactions retain their handling.
    """

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.views = {}
        self.pending = {}
        self.suppress_context = set()
        self.available_paths = set(_catalog(window)) if _buttons(window) else set()
        for view, context in ((getattr(window, "plan_view", None), "plan"),
                              (getattr(window, "pbr_view", None), "3d"),
                              (getattr(window, "structural_view", None), "3d")):
            if view is not None and hasattr(view, "viewport"):
                viewport = view.viewport()
                self.views[viewport] = context
                viewport.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Qt can invoke event filters while QObject.__init__ is still running.
        context = getattr(self, "views", {}).get(watched)
        if context is None:
            return False
        t = event.type()
        if t == QEvent.Type.ContextMenu and watched in self.suppress_context:
            self.suppress_context.discard(watched)
            event.accept()
            return True
        if t not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick,
                     QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease):
            return False
        if t == QEvent.Type.MouseMove and watched in self.pending:
            # While a user-assigned click is pending, do not rotate or draw.
            event.accept()
            return True
        if t == QEvent.Type.MouseButtonRelease and watched in self.pending:
            button, start, path = self.pending.pop(watched)
            if event.button() == button:
                distance = (event.position() - start).manhattanLength()
                if distance <= 8:
                    from archforge.ui.mouse_menus import run_menu_path
                    run_menu_path(self.window, path)
                event.accept()
                return True
        if t != QEvent.Type.MouseButtonPress:
            return False
        plan = getattr(self.window, "plan_view", None)
        if plan is None or str(plan.controller.tool) != "select" or plan.controller.active is not None:
            return False
        sculpt = getattr(self.window, "sculpt_action", None)
        if sculpt is not None and sculpt.isChecked():
            return False
        for _title, qt_button, key in BUTTONS:
            if event.button() != qt_button:
                continue
            context_bindings = _buttons(self.window).get(context, {})
            path = context_bindings.get(key, "") if isinstance(context_bindings, dict) else ""
            if not path:
                return False
            if path not in self.available_paths:
                self.available_paths = set(_catalog(self.window))
                if _resolve_saved_path(self.window, path) is None:
                    return False
            self.pending[watched] = (qt_button, event.position(), path)
            if qt_button == Qt.MouseButton.RightButton:
                self.suppress_context.add(watched)
            event.accept()
            return True
        return False


class PersonalMenus:
    """Toolbar, floating palette or popup with the exact original QActions."""

    def __init__(self, window):
        self.window = window
        self.surfaces = {}
        self.apply()

    def _remove(self):
        for bar, launcher in self.surfaces.values():
            if launcher is not None:
                launcher.hide()
                launcher.setParent(None)
                launcher.deleteLater()
            if isinstance(bar, QToolBar):
                self.window.removeToolBar(bar)
            elif isinstance(bar, QDockWidget):
                if isinstance(bar, _FloatingMenu):
                    bar._track = False
                    bar._timer.stop()
                self.window.removeDockWidget(bar)
            bar.hide()
            bar.setParent(None)
            bar.deleteLater()
        self.surfaces.clear()

    def apply(self):
        self._remove()
        configs = _menus(self.window)[:MAX_CUSTOM_MENUS]
        if not configs:
            return
        actions = _catalog(self.window)
        for config in configs:
            if not isinstance(config, dict) or not isinstance(config.get("id"), str):
                continue
            ident = config["id"]
            title = str(config.get("title") or "Δικό μου μενού")[:80]
            mode = config.get("mode", "docked")
            try:
                size = max(16, min(48, int(config.get("size", 24))))
                width = max(120, min(900, int(config.get("width", 280))))
                height = max(80, min(750, int(config.get("height", 180))))
            except (TypeError, ValueError):
                size, width, height = 24, 280, 180
            stored_paths = config.get("commands", [])
            paths = [_resolve_saved_path(self.window, p, actions) for p in stored_paths[:MAX_COMMANDS]] \
                if isinstance(stored_paths, list) else []
            paths = [p for p in paths if p is not None]
            launcher = None
            if mode == "popup":
                from PySide6.QtWidgets import QMenu
                bar = QWidget(self.window)  # popup launcher alone; no duplicate toolbar
                launcher = QToolButton(self.window._top_row)
                menu = QMenu(title, launcher)  # destroyed with launcher on each live reconfiguration
                menu.setMinimumWidth(width)
                menu.setMinimumHeight(height)
                menu.setStyleSheet(f"QMenu::item {{ padding: {max(5, size // 3)}px 14px; font-size: {max(11, size // 2)}px; }}")
                for path in paths:
                    menu.addAction(actions[path])
                launcher.setText(title + " ▾")
                launcher.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                launcher.setMenu(menu)
                launcher.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
                layout = self.window._top_row.layout()
                anchor = getattr(self.window, "_top_menu_bar", None)
                at = layout.indexOf(anchor) if anchor is not None else -1
                layout.insertWidget(at if at >= 0 else layout.count(), launcher)
                bar.hide()
            elif mode == "floating":
                # QToolBar has no setFloating() API.  A real QDockWidget is
                # movable, closable and resizable by the user and by code.
                bar = _FloatingMenu(title, self.window, config)
                bar.setObjectName("personal_menu_" + ident)
                bar.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable |
                                QDockWidget.DockWidgetFeature.DockWidgetMovable |
                                QDockWidget.DockWidgetFeature.DockWidgetFloatable)
                contents = QWidget(bar)
                grid = QGridLayout(contents)
                grid.setContentsMargins(6, 6, 6, 6)
                columns = max(1, min(6, (width - 20) // max(84, size * 3)))
                for index, path in enumerate(paths):
                    button = QToolButton(contents)
                    button.setDefaultAction(actions[path])
                    button.setIconSize(QSize(size, size))
                    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                    grid.addWidget(button, index // columns, index % columns)
                grid.setRowStretch((len(paths) + columns - 1) // columns, 1)
                scroll = QScrollArea(bar)
                scroll.setWidgetResizable(True)
                scroll.setWidget(contents)
                bar.setWidget(scroll)
                self.window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, bar)
                bar.setFloating(True)
                bar.resize(width, height)
                if isinstance(config.get("x"), int) and isinstance(config.get("y"), int):
                    bar.move(config["x"], config["y"])
                bar.show()
                bar._track = True
            else:
                bar = QToolBar(title, self.window)
                bar.setObjectName("personal_menu_" + ident)
                bar.setMovable(True)
                bar.setFloatable(True)
                bar.setIconSize(QSize(size, size))
                bar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
                for path in paths:
                    bar.addAction(actions[path])
                self.window.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
                bar.show()
            self.surfaces[ident] = (bar, launcher)

    def capture_positions(self):
        for conf in _menus(self.window):
            surface = self.surfaces.get(conf.get("id"))
            if surface and conf.get("mode") == "floating":
                bar = surface[0]
                conf["x"], conf["y"] = bar.pos().x(), bar.pos().y()
                conf["width"], conf["height"] = bar.width(), bar.height()


class ControlCenter(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Διαχείριση περιβάλλοντος — ποντίκι, μενού και συντομεύσεις")
        self.resize(1050, 650)
        root = QVBoxLayout(self)
        tabs = QTabWidget(self); root.addWidget(tabs, 1)
        page = QWidget(); tabs.addTab(page, "Προσωπικά μενού")
        layout = QHBoxLayout(page)
        left = QVBoxLayout(); layout.addLayout(left, 1)
        left.addWidget(QLabel("Τα δικά μου μενού"))
        self.groups = QListWidget(); left.addWidget(self.groups, 1)
        bar = QHBoxLayout(); left.addLayout(bar)
        for title, callback in (("+ Νέο", self._add_group), ("Διαγραφή", self._delete_group)):
            btn = QPushButton(title); btn.clicked.connect(callback); bar.addWidget(btn)
        center = QVBoxLayout(); layout.addLayout(center, 2)
        center.addWidget(QLabel("Όνομα"))
        self.name = QLineEdit(); center.addWidget(self.name)
        center.addWidget(QLabel("Εμφάνιση"))
        self.mode = QComboBox()
        for name, value in MODES:
            self.mode.addItem(name, value)
        center.addWidget(self.mode)
        center.addWidget(QLabel("Μέγεθος εικονιδίων (px)"))
        self.size = QSpinBox(); self.size.setRange(16, 48); self.size.setSingleStep(4)
        center.addWidget(self.size)
        center.addWidget(QLabel("Πλάτος / ύψος μενού (px)"))
        dimensions = QHBoxLayout(); center.addLayout(dimensions)
        self.width = QSpinBox(); self.width.setRange(120, 900); self.width.setSingleStep(20)
        self.height = QSpinBox(); self.height.setRange(80, 750); self.height.setSingleStep(20)
        dimensions.addWidget(self.width); dimensions.addWidget(self.height)
        center.addWidget(QLabel("Εντολές του μενού — η ίδια λειτουργία, χωρίς αντίγραφα"))
        self.commands = QListWidget(); center.addWidget(self.commands, 1)
        order = QHBoxLayout(); center.addLayout(order)
        for label, callback in (("Αφαίρεση", self._remove_command), ("↑", lambda: self._move(-1)),
                                ("↓", lambda: self._move(1))):
            btn = QPushButton(label); btn.clicked.connect(callback); order.addWidget(btn)
        right = QVBoxLayout(); layout.addLayout(right, 2)
        right.addWidget(QLabel("Όλες οι διαθέσιμες εντολές"))
        self.search = QLineEdit(); self.search.setPlaceholderText("Αναζήτηση…")
        right.addWidget(self.search)
        self.catalog = QListWidget(); right.addWidget(self.catalog, 1)
        add = QPushButton("Προσθήκη στην ομάδα →"); right.addWidget(add)
        add.clicked.connect(self._add_command)
        self.catalog.itemDoubleClicked.connect(lambda _it: self._add_command())
        self.search.textChanged.connect(self._fill_catalog)
        self.groups.currentRowChanged.connect(self._load_group)
        self.name.editingFinished.connect(self._save_group)
        self.mode.currentIndexChanged.connect(self._save_group)
        self.size.valueChanged.connect(self._save_group)
        self.width.valueChanged.connect(self._save_group)
        self.height.valueChanged.connect(self._save_group)
        mouse_page = QWidget(); tabs.addTab(mouse_page, "Κουμπιά ποντικιού")
        mouse = QVBoxLayout(mouse_page)
        mouse.addWidget(QLabel("Προαιρετική εντολή με κλικ (2D / 3D). Χωρίς ανάθεση, όλα τα κλικ και οι κινήσεις παραμένουν όπως είναι.\n"
                               "Η ανάθεση αντικαθιστά και το σύρσιμο του αντίστοιχου κουμπιού.\n"
                               "Ισχύει μόνο στην Επιλογή, ώστε να μη διακόπτει σχεδίαση ή Sculpt."))
        self.bindings = {}
        available = sorted(_catalog(window))
        for context, caption in (("plan", "Κάτοψη 2D"), ("3d", "Προβολές 3D / Φέρων")):
            mouse.addWidget(QLabel("<b>" + caption + "</b>"))
            for title, _button, key in BUTTONS:
                line = QHBoxLayout(); mouse.addLayout(line)
                line.addWidget(QLabel(title))
                combo = QComboBox(); combo.addItem("Αρχική λειτουργία", "")
                for path in available:
                    combo.addItem(path, path)
                context_bindings = _buttons(window).get(context, {})
                current = context_bindings.get(key, "") if isinstance(context_bindings, dict) else ""
                index = combo.findData(current)
                combo.setCurrentIndex(max(0, index))
                combo.currentIndexChanged.connect(lambda _i, c=context, b=key, w=combo: self._bind(c, b, w.currentData()))
                line.addWidget(combo, 1)
                self.bindings[(context, key)] = combo
        mouse.addStretch(1)
        existing = QWidget(); tabs.addTab(existing, "Υπάρχοντα εργαλεία")
        other = QVBoxLayout(existing)
        other.addWidget(QLabel("Οι υπάρχουσες ρυθμίσεις παραμένουν διαθέσιμες, με την ίδια συμπεριφορά."))
        other.addWidget(QLabel("Εργαλειογραμμές — απόκρυψη ή εμφάνιση, χωρίς διαγραφή εντολών"))
        self.originals = QListWidget()
        for name, group in getattr(window, "_tool_groups", {}).items():
            from PySide6.QtWidgets import QListWidgetItem
            item = QListWidgetItem(group.custom_title)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if group.isVisible() else Qt.CheckState.Unchecked)
            self.originals.addItem(item)
        self.originals.itemChanged.connect(self._toggle_original)
        other.addWidget(self.originals)
        configure = QPushButton("Πρόσθεση / αφαίρεση εντολών στην επιλεγμένη εργαλειογραμμή…")
        configure.clicked.connect(self._configure_original)
        other.addWidget(configure)
        for title, callback in (("Κυκλικό μενού ποντικιού ανά εργασία…", self._radial),
                                ("Συντομεύσεις πληκτρολογίου…", self._shortcuts)):
            btn = QPushButton(title); btn.clicked.connect(callback); other.addWidget(btn)
        other.addStretch(1)
        footer = QHBoxLayout(); root.addLayout(footer)
        for title, callback in (("Εξαγωγή ρυθμίσεων…", self._export), ("Εισαγωγή ρυθμίσεων…", self._import),
                                ("Επαναφορά προσωπικών μενού", self._reset)):
            btn = QPushButton(title); btn.clicked.connect(callback); footer.addWidget(btn)
        footer.addStretch(1)
        close = QPushButton("Αποθήκευση και κλείσιμο")
        close.clicked.connect(self.accept); footer.addWidget(close)
        self._fill_catalog()
        self._fill_groups()

    def _current(self):
        row = self.groups.currentRow()
        menus = _menus(self.window)
        return menus[row] if 0 <= row < len(menus) else None

    def _fill_groups(self, keep=None):
        if keep is None:
            keep = self.groups.currentRow()
        self.groups.blockSignals(True)
        self.groups.clear()
        for config in _menus(self.window):
            self.groups.addItem(str(config.get("title") or "Δικό μου μενού"))
        self.groups.blockSignals(False)
        self.groups.setCurrentRow(min(max(0, keep), self.groups.count() - 1))
        self._load_group()

    def _fill_catalog(self, *_):
        text = self.search.text().strip().lower()
        self.catalog.clear()
        for path in sorted(_catalog(self.window)):
            if text in path.lower():
                self.catalog.addItem(path)

    def _load_group(self, *_):
        conf = self._current()
        for widget in (self.name, self.mode, self.size, self.width, self.height):
            widget.blockSignals(True)
        self.name.setEnabled(conf is not None)
        self.mode.setEnabled(conf is not None)
        self.size.setEnabled(conf is not None)
        self.width.setEnabled(conf is not None)
        self.height.setEnabled(conf is not None)
        self.name.setText(str(conf.get("title", "")) if conf else "")
        self.mode.setCurrentIndex(max(0, self.mode.findData(conf.get("mode", "docked")))) if conf else None
        self.size.setValue(int(conf.get("size", 24))) if conf else None
        self.width.setValue(int(conf.get("width", 280))) if conf else None
        self.height.setValue(int(conf.get("height", 180))) if conf else None
        self.commands.clear()
        if conf:
            self.commands.addItems(conf.get("commands", []))
        for widget in (self.name, self.mode, self.size, self.width, self.height):
            widget.blockSignals(False)

    def _commit(self):
        self.window._personal_menus.apply()
        _persist(self.window)

    def _add_group(self):
        if len(_menus(self.window)) >= MAX_CUSTOM_MENUS:
            QMessageBox.warning(self, "Όριο", "Μπορείς να έχεις έως 20 προσωπικά μενού.")
            return
        self.window._personal_menus.capture_positions()
        _menus(self.window).append({"id": uuid4().hex, "title": "Δικό μου μενού", "mode": "popup", "size": 24,
                                    "width": 280, "height": 180, "commands": []})
        self._fill_groups(len(_menus(self.window)) - 1)
        self._commit()

    def _delete_group(self):
        conf = self._current()
        if conf is None:
            return
        self.window._personal_menus.capture_positions()
        _menus(self.window).remove(conf)
        self._fill_groups()
        self._commit()

    def _save_group(self, *_):
        conf = self._current()
        if conf is None:
            return
        self.window._personal_menus.capture_positions()
        conf.update(title=self.name.text().strip() or "Δικό μου μενού",
                    mode=self.mode.currentData(), size=self.size.value(),
                    width=self.width.value(), height=self.height.value())
        self.groups.currentItem().setText(conf["title"])
        self._commit()

    def _add_command(self):
        conf, item = self._current(), self.catalog.currentItem()
        if conf is None or item is None:
            return
        path = item.text()
        if path not in conf["commands"] and len(conf["commands"]) < MAX_COMMANDS:
            self.window._personal_menus.capture_positions()
            conf["commands"].append(path)
            self._load_group()
            self._commit()

    def _remove_command(self):
        conf, row = self._current(), self.commands.currentRow()
        if conf is not None and 0 <= row < len(conf["commands"]):
            self.window._personal_menus.capture_positions()
            conf["commands"].pop(row)
            self._load_group()
            self._commit()

    def _move(self, delta):
        conf, row = self._current(), self.commands.currentRow()
        if conf is None or not 0 <= row + delta < len(conf["commands"]):
            return
        self.window._personal_menus.capture_positions()
        items = conf["commands"]
        items[row], items[row + delta] = items[row + delta], items[row]
        self._load_group()
        self.commands.setCurrentRow(row + delta)
        self._commit()

    def _bind(self, context, button, path):
        _buttons(self.window).setdefault(context, {})[button] = path or ""
        if context == "3d":
            push_3d_bindings(self.window)
        _persist(self.window)

    def _radial(self):
        from archforge.ui.mouse_menus import open_editor
        open_editor(self.window)

    def _shortcuts(self):
        from archforge.ui.shortcuts import open_dialog
        open_dialog(self.window)

    def _toggle_original(self, item):
        group = getattr(self.window, "_tool_groups", {}).get(item.data(Qt.ItemDataRole.UserRole))
        if group is not None:
            group.setVisible(item.checkState() == Qt.CheckState.Checked)
            _persist(self.window)

    def _configure_original(self):
        item = self.originals.currentItem()
        group = getattr(self.window, "_tool_groups", {}).get(item.data(Qt.ItemDataRole.UserRole)) if item else None
        if group is not None:
            toolbar_custom.customize_menu(self.window, group).exec(self.mapToGlobal(self.rect().center()))

    def _reset(self):
        if QMessageBox.question(self, "Επαναφορά", "Να αφαιρεθούν μόνο τα προσωπικά μενού; Οι εντολές δεν διαγράφονται.") != QMessageBox.StandardButton.Yes:
            return
        _menus(self.window).clear()
        self._fill_groups()
        self._commit()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Εξαγωγή ρυθμίσεων", "archforge-controls.json", "JSON (*.json)")
        if path:
            self.window._personal_menus.capture_positions()
            data = {"archforge_controls": 1, "personal_menus": _menus(self.window),
                    "mouse_buttons": _buttons(self.window)}
            from archforge.project.persistence import atomic_write_text
            try:
                atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
            except OSError as exc:
                QMessageBox.warning(self, "Εξαγωγή", str(exc))

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Εισαγωγή ρυθμίσεων", "", "JSON (*.json)")
        if not path:
            return
        try:
            from archforge.project.persistence import read_user_json
            data = read_user_json(path)
            if data.get("archforge_controls") != 1 or not isinstance(data.get("personal_menus"), list) or not isinstance(data.get("mouse_buttons"), dict):
                raise ValueError("Μη έγκυρο αρχείο ρυθμίσεων ArchForge")
            valid = set(_catalog(self.window))
            menus = []
            for raw in data["personal_menus"][:MAX_CUSTOM_MENUS]:
                if not isinstance(raw, dict):
                    continue
                conf = {"id": uuid4().hex, "title": str(raw.get("title") or "Δικό μου μενού")[:80],
                              "mode": raw.get("mode") if raw.get("mode") in ("docked", "popup", "floating") else "popup",
                              "size": max(16, min(48, int(raw.get("size", 24)))),
                              "width": max(120, min(900, int(raw.get("width", 280)))),
                              "height": max(80, min(750, int(raw.get("height", 180)))),
                              "commands": [p for p in raw.get("commands", [])[:MAX_COMMANDS]
                                           if _resolve_saved_path(self.window, p, valid) is not None]}
                if isinstance(raw.get("x"), int) and isinstance(raw.get("y"), int):
                    conf.update(x=raw["x"], y=raw["y"])
                menus.append(conf)
            buttons = {}
            for context in ("plan", "3d"):
                raw = data["mouse_buttons"].get(context, {})
                if isinstance(raw, dict):
                    buttons[context] = {key: value for key, value in raw.items()
                                        if key in {b[2] for b in BUTTONS}
                                        and _resolve_saved_path(self.window, value, valid) is not None}
            toolbar_custom.prefs(self.window)["personal_menus"] = menus
            toolbar_custom.prefs(self.window)["mouse_buttons"] = buttons
            push_3d_bindings(self.window)
            self._fill_groups()
            for (context, key), widget in self.bindings.items():
                widget.blockSignals(True)
                widget.setCurrentIndex(max(0, widget.findData(buttons.get(context, {}).get(key, ""))))
                widget.blockSignals(False)
            self._commit()
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            QMessageBox.warning(self, "Εισαγωγή", str(exc))

    def accept(self):
        self.window._personal_menus.capture_positions()
        _persist(self.window)
        super().accept()

    def closeEvent(self, event):
        self.window._personal_menus.capture_positions()
        _persist(self.window)
        super().closeEvent(event)


def open_center(window):
    dialog = ControlCenter(window)
    window._control_center = dialog
    dialog.show()
    dialog.raise_()
    return dialog


def install(window):
    """Run after work-menu regrouping, so saved command paths are canonical."""
    window._personal_menus = PersonalMenus(window)
    from archforge.ui.workspace_layout import persistence_enabled, restore_layout
    if persistence_enabled():
        restore_layout(window)  # personal QToolBars now exist, unlike the earlier layout2 restore
    window._mouse_button_dispatcher = MouseButtonDispatcher(window)
    push_3d_bindings(window)
    action = QAction("Διαχείριση περιβάλλοντος, ποντικιού και μενού…", window)
    action.triggered.connect(lambda _=False: open_center(window))
    section = getattr(window, "_work_sections", {}).get(("⚙ Ρυθμίσεις", "Χειρισμός"))
    if section is None:
        section = getattr(window, "_work_menus", {}).get("⚙ Ρυθμίσεις")
    if section is not None:
        section.addSeparator()
        section.addAction(action)
    window._control_center_action = action
    return action
