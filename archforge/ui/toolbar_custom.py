"""The human arranges the tool buttons (owner 15/10: «μικρά εικονίδια ή δώσε μου τη δυνατότητα να τροποποιώ εγώ
το μενού κατά βούληση — επιλέγω το μέγεθος και να προσθέτω ή αφαιρώ εργαλεία ανά κουμπί»).

* Icon size for every tool group and the «Κοινά» palette: Μικρά / Μεσαία / Μεγάλα, with or without the name
  under the icon (Προβολή ▸ Μέγεθος εικονιδίων, or right click on any group).
* Right click on a group (or on «Κοινά»): each of its buttons can be hidden / shown, and **any command of the
  menus** can be added to it as a button («Πρόσθεσε εργαλείο ▸», the menus as they are); an added button is
  removed the same way.
* Remembered with the layout (``layout.ini``, presentation only — never in the Document); «Επαναφορά
  διάταξης» brings the default buttons and size back.

Commands are found by their menu path (e.g. ``Κατασκευή / Στέγη / Δίρριχτη``), so an added button is the
very same QAction as the menu entry — same command, same key, same undo.
"""
from __future__ import annotations

import json

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QToolButton

ICON_SIZES = (("Μικρά", 16), ("Μεσαία", 20), ("Μεγάλα", 26))
DEFAULTS = {"icon_size": 20, "text": True, "hidden": {}, "added": {}, "palette_cols": 5}
SEP = " / "


# --------------------------------------------------------------------------- state
def prefs(window):
    if not hasattr(window, "_ui_prefs"):
        window._ui_prefs = json.loads(json.dumps(DEFAULTS))
    return window._ui_prefs


def _settings(window, settings=None):
    if settings is not None:
        return settings
    from archforge.ui.workspace_layout import layout_settings, persistence_enabled
    return layout_settings() if persistence_enabled() else getattr(window, "_ui_prefs_settings", None)


def save(window, settings=None):
    s = _settings(window, settings)
    if s is not None:
        s.setValue("custom/prefs", json.dumps(prefs(window), ensure_ascii=False))
        s.sync()


def load(window, settings=None):
    """Read the saved arrangement and apply it (nothing saved: the defaults)."""
    s = _settings(window, settings)
    raw = s.value("custom/prefs") if s is not None else None
    data = json.loads(json.dumps(DEFAULTS))
    if raw:
        try:
            got = json.loads(raw)
            data.update({k: got[k] for k in DEFAULTS if k in got})
        except (TypeError, ValueError):
            pass
    window._ui_prefs = data
    apply(window)
    return data


def reset(window, settings=None):
    window._ui_prefs = json.loads(json.dumps(DEFAULTS))
    for target in _targets(window):
        for key in list(target.custom_buttons):
            target.remove_custom(key)
    apply(window)
    save(window, settings)


# --------------------------------------------------------------------------- the commands of the menus
def catalog(window):
    """``{path: QAction}`` of every command in the menu bar (leaves, by their menu path)."""
    out = {}
    icons = window.__dict__.setdefault("_catalog_icons", {}) if hasattr(window, "__dict__") else {}

    def walk(menu, path, icon=None):
        for a in menu.actions():
            if a.isSeparator() or not a.text():
                continue
            text = a.text().replace("&&", "&")
            if a.menu() is not None:
                if not a.menu().actions():
                    a.menu().aboutToShow.emit()           # filled on first open
                sub_icon = a.menu().icon()
                walk(a.menu(), path + (text,), icon if sub_icon.isNull() else sub_icon)
            elif a.isEnabled():
                key = SEP.join(path + (text,))
                out.setdefault(key, a)
                if a.icon().isNull() and icon is not None:
                    icons[key] = icon                 # an added button shows its submenu's icon
    for top in window.menuBar().actions():
        if top.menu() is not None:
            walk(top.menu(), (top.text().replace("&&", "&"),))
    window._catalog_icons = icons
    return out


def _fill_catalog(window, menu, on_pick):
    """The menu bar mirrored as submenus; a click on a command calls ``on_pick(path)``."""
    def build(parent, source, path):
        for a in source.actions():
            if a.isSeparator() or not a.text():
                continue
            text = a.text().replace("&&", "&")
            if a.menu() is not None:
                if not a.menu().actions():
                    a.menu().aboutToShow.emit()
                sub = parent.addMenu(a.menu().icon(), text.replace("&", "&&"))
                build(sub, a.menu(), path + (text,))
            elif a.isEnabled():
                item = parent.addAction(a.icon(), text.replace("&", "&&"))
                item.triggered.connect(lambda _=False, p=SEP.join(path + (text,)): on_pick(p))
    menu.clear()
    for top in window.menuBar().actions():
        if top.menu() is not None:
            name = top.text().replace("&&", "&")
            build(menu.addMenu(name), top.menu(), (name,))


# --------------------------------------------------------------------------- applying
def _targets(window):
    out = list(getattr(window, "_tool_groups", {}).values())
    palette = getattr(window, "_common_palette", None)
    if palette is not None:
        out.append(palette)
    return out


def apply(window):
    p = prefs(window)
    size, text = int(p["icon_size"]), bool(p["text"])
    cat = None
    for target in _targets(window):
        key = target.custom_key
        for path in p["added"].get(key, []):
            if path in target.custom_buttons:
                continue
            cat = cat if cat is not None else catalog(window)
            if path in cat:
                target.add_custom(path, cat[path])
        for label, button in target.labelled_buttons():
            button.setVisible(label not in p["hidden"].get(key, []))
        target.set_icon_size(size, text)
    for a in getattr(window, "_icon_size_actions", ()):
        a.setChecked(a.data() == size)
    act = getattr(window, "_icon_text_action", None)
    if act is not None:
        act.setChecked(text)


def set_icon_size(window, size, settings=None):
    prefs(window)["icon_size"] = int(size)
    apply(window); save(window, settings)


def set_text(window, on, settings=None):
    prefs(window)["text"] = bool(on)
    apply(window); save(window, settings)


def set_palette_cols(window, n, settings=None):
    prefs(window)["palette_cols"] = int(n)
    apply(window); save(window, settings)


def set_shown(window, target, label, on, settings=None):
    hidden = prefs(window)["hidden"].setdefault(target.custom_key, [])
    if on and label in hidden:
        hidden.remove(label)
    elif not on and label not in hidden:
        hidden.append(label)
    apply(window); save(window, settings)


def add_tool(window, target, path, settings=None):
    added = prefs(window)["added"].setdefault(target.custom_key, [])
    if path not in added:
        added.append(path)
    apply(window); save(window, settings)
    window.statusBar().showMessage(f"«{path.split(SEP)[-1]}» μπήκε στην ομάδα «{target.custom_title}» — "
                                   "δεξί κλικ στην ομάδα για αφαίρεση", 6000)


def remove_tool(window, target, path, settings=None):
    added = prefs(window)["added"].setdefault(target.custom_key, [])
    if path in added:
        added.remove(path)
    target.remove_custom(path)
    apply(window); save(window, settings)


# --------------------------------------------------------------------------- the right-click menu
def customize_menu(window, target):
    """«Προσαρμογή» of one group / the palette: its buttons, add a command, icon size."""
    menu = QMenu(window)
    menu.addSection(f"Κουμπιά: {target.custom_title}")
    for label, button in target.labelled_buttons():
        path = next((p for p, b in target.custom_buttons.items() if b is button), None)
        a = menu.addAction(label.replace("&", "&&"))
        a.setCheckable(True); a.setChecked(not button.isHidden())
        if path is not None:
            a.toggled.connect(lambda on, p=path: (not on) and remove_tool(window, target, p))
            a.setToolTip("Πρόσθετο κουμπί: αφαιρείται")
        else:
            a.toggled.connect(lambda on, l=label: set_shown(window, target, l, on))
    add = menu.addMenu("Πρόσθεσε εργαλείο")
    add.aboutToShow.connect(lambda: _fill_catalog(window, add, lambda p: add_tool(window, target, p)))
    menu.addSeparator()
    sizes = menu.addMenu("Μέγεθος εικονιδίων")
    _size_entries(window, sizes, keep=False)
    if target.custom_key == "common":
        # Any shape: one column (upright), a row, or in between.
        cols = menu.addMenu("Στήλες")
        group = QActionGroup(cols); group.setExclusive(True)
        for n, name in ((1, "1 (κάθετα)"), (2, "2"), (3, "3"), (5, "5"), (10, "10 (οριζόντια)")):
            a = QAction(name, cols); a.setCheckable(True); a.setChecked(int(prefs(window).get("palette_cols", 5)) == n)
            a.triggered.connect(lambda _=False, k=n: set_palette_cols(window, k))
            group.addAction(a); cols.addAction(a)
    menu.addSeparator()
    reset_action = menu.addAction("Επαναφορά κουμπιών και μεγέθους")
    reset_action.triggered.connect(lambda: reset(window))
    return menu


def _size_entries(window, menu, keep=True):
    group = QActionGroup(menu); group.setExclusive(True)
    made = []
    for name, size in ICON_SIZES:
        a = QAction(name, menu); a.setCheckable(True); a.setData(size)
        a.setChecked(int(prefs(window)["icon_size"]) == size)
        a.triggered.connect(lambda _=False, s=size: set_icon_size(window, s))
        group.addAction(a); menu.addAction(a); made.append(a)
    menu.addSeparator()
    text = QAction("Όνομα κάτω από το εικονίδιο", menu); text.setCheckable(True)
    text.setChecked(bool(prefs(window)["text"]))
    text.toggled.connect(lambda on: set_text(window, on))
    menu.addAction(text)
    if keep:
        window._icon_size_actions, window._icon_text_action = made, text
    return made


def install(window):
    """Right click on every group and on «Κοινά»; Προβολή ▸ Μέγεθος εικονιδίων; saved arrangement loaded."""
    for target in _targets(window):
        target.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        target.customContextMenuRequested.connect(
            lambda pos, t=target: customize_menu(window, t).exec(t.mapToGlobal(pos)))
    view = getattr(window, "view_menu", None)
    if view is not None:
        sizes = QMenu("Μέγεθος εικονιδίων", view)
        _size_entries(window, sizes)
        bars = getattr(window, "_toolbars_menu", None)
        before = bars.menuAction() if bars is not None and bars.menuAction() in view.actions() else None
        view.insertMenu(before, sizes) if before is not None else view.addMenu(sizes)
        window._icon_size_menu = sizes
    reset_action = getattr(window, "_reset_layout_action", None)
    if reset_action is not None:
        reset_action.triggered.connect(lambda: reset(window))
    load(window)


# --------------------------------------------------------------------------- the target protocol (mixin)
class CustomizableButtons:
    """What a group / the palette offers: named buttons, added buttons by menu path, an icon size."""
    custom_key = ""
    custom_title = ""

    def labelled_buttons(self):
        raise NotImplementedError

    def add_custom(self, path, action):
        raise NotImplementedError

    def remove_custom(self, path):
        b = self.custom_buttons.pop(path, None)
        if b is not None:
            b.hide(); b.setParent(None); b.deleteLater()

    def set_icon_size(self, size, text):
        # The frame follows the icons: smaller icons → smaller names and tighter buttons, both ways.
        px = 10 if size <= 16 else (11 if size <= 20 else 12)
        for _label, b in self.labelled_buttons():
            b.setIconSize(QSize(size, size))
            b.setStyleSheet(f"QToolButton {{ font-size:{px}px; }}")   # the window's stylesheet wins over setFont
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon if text
                                 else Qt.ToolButtonStyle.ToolButtonIconOnly)


def make_button(action, label=None, icon=None):
    b = QToolButton(); b.setAutoRaise(True); b.setDefaultAction(action)
    if label:
        b.setText(label)
    if action.icon().isNull():
        from archforge.ui.menu_icons import icon as drawn
        b.setIcon(icon if icon is not None and not icon.isNull() else drawn("more"))
    b.setToolTip(action.toolTip() or action.text().replace("&&", "&"))
    return b
