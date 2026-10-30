"""Διάταξη 2 of the screen, approved by the owner on 14/10 («καλό φαίνεται»): `docs/mockups/diataxi2_2026-10-14.png`.

1. A thin first row: logo and project name · quick Save / Undo / Redo · the 8 small menus at the top right.
2. A second row of **tool groups** (Επιλογή · Κατασκευή · Βιβλιοθήκη · Όροφος · Περιβάλλον): each one a movable
   bar (dragged along the row, to another edge, or floating), with its title under the buttons; «Κατασκευή ▾»
   opens the rest of the group, like AutoCAD's ribbon panels, and the dashed line at the top pins it open (📌).
3. «Κοινά» — the everyday edit commands as a small palette over the drawing, bottom right, dragged anywhere by
   its handle; ⚙ chooses its buttons.
4. View settings on the drawing, top right: Προβολή ▾ · Στυλ ▾ · Κάμερες ▾ · Κάνναβος · Έλξη / βήμα.
5. Panels on the right (the hand is there): Ιδιότητες above, Έργο / Βιβλιοθήκη / Βοηθός / Layers / Κάμερες below.

Presentation only: every button is an action or a widget that already existed (moved here, never duplicated),
so menus, keys and the mouse menu stay the same commands.  Where things sit is remembered with the rest of the
layout (``workspace_layout.LAYOUT_VERSION`` was raised, so an older saved layout is not restored over this).
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QBoxLayout, QDockWidget, QFrame, QGridLayout, QHBoxLayout, QScrollArea, QLabel, QMenu, QMenuBar, QSizePolicy, QStyle,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

ACCENT = "#2F6BD6"

STYLE = """
QWidget#top_row { background:#FFFFFF; border-bottom:1px solid #D8DEE8; }
QLabel#app_name { font-weight:700; font-size:14px; color:#1E2A3B; }
QLabel#project_name { color:#6B7686; font-size:13px; }
QMenuBar#main_menu_bar { background:transparent; border:0; }
QMenuBar#main_menu_bar::item { padding:5px 9px; border-radius:4px; }
QToolButton#quick { padding:3px; }
QWidget#tool_group QToolButton { padding:1px 2px; margin:0; }
QToolBar[afgroup="true"] { padding:0px; spacing:0px; border:0; }
QToolBar#workspace_bar QToolButton { padding:1px 6px; font-size:11px; }
QToolBar#workspace_bar QLabel { font-size:11px; }
QToolButton#group_title { color:#5B6778; font-size:10px; padding:0 4px; margin:0; border:0; max-height:13px; }
QToolButton#group_title:hover { color:#2F6BD6; background:#E8EEF7; }
QFrame#view_settings { background:transparent; }
QFrame#common_palette { background:#FFFFFF; border:1px solid #C9D2DF; border-radius:8px; }
QLabel#palette_handle { color:#8A96A8; font-size:12px; padding:0 1px; }
QLabel#palette_title { color:#6B7686; font-size:10px; }
QFrame#common_palette QToolButton { padding:1px 2px; margin:0; }
"""

# «Κοινά»: (shortcut id, label, icon); shown unless switched off with ⚙.
COMMON = (("tool.select", "Επιλογή", "select"), ("edit.move", "Μετακ.", "move"), ("edit.rotate", "Περιστρ.", "rotate"),
          ("edit.stretch", "Τέντωμα", "stretch"), ("edit.duplicate", "Αντίγραφο", "duplicate"),
          ("edit.delete", "Διαγραφή", "delete"), ("edit.undo", "Αναίρεση", "undo"), ("edit.redo", "Επανάληψη", "redo"),
          ("view.zoom_all", "Ζουμ όλο", "zoom"))


# --------------------------------------------------------------------------- small icons (drawn, no files)
def _icon(kind, size=32):
    from PySide6.QtCore import QPointF, QRectF
    from PySide6.QtGui import QPen, QPolygonF
    pix = QPixmap(size, size); pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.scale(size / 32.0, size / 32.0)
    ink, accent = QColor(40, 62, 92), QColor(47, 107, 214)
    pen = QPen(ink, 2.2); pen.setCapStyle(Qt.PenCapStyle.RoundCap); pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin); p.setPen(pen)
    if kind == "logo":
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(accent); p.drawRoundedRect(QRectF(2, 2, 28, 28), 6, 6)
        p.setBrush(QColor(255, 255, 255)); p.drawPolygon(QPolygonF([QPointF(9, 24), QPointF(16, 8), QPointF(23, 24),
                                                                    QPointF(19.5, 24), QPointF(16, 15.5), QPointF(12.5, 24)]))
    elif kind == "save":
        p.drawRoundedRect(QRectF(5, 5, 22, 22), 3, 3); p.drawRect(QRectF(10, 5, 11, 7)); p.drawRect(QRectF(9, 17, 14, 10))
    elif kind in ("undo", "redo"):
        if kind == "redo":
            p.translate(32, 0); p.scale(-1, 1)
        p.drawArc(QRectF(8, 9, 18, 16), 90 * 16, -200 * 16)
        p.drawLine(QPointF(17, 9), QPointF(10, 9)); p.drawLine(QPointF(10, 9), QPointF(13, 5)); p.drawLine(QPointF(10, 9), QPointF(13, 13))
    elif kind == "move":
        for a, b in (((16, 4), (16, 28)), ((4, 16), (28, 16))):
            p.drawLine(QPointF(*a), QPointF(*b))
        for tip, l, r in (((16, 4), (13, 8), (19, 8)), ((16, 28), (13, 24), (19, 24)),
                          ((4, 16), (8, 13), (8, 19)), ((28, 16), (24, 13), (24, 19))):
            p.drawLine(QPointF(*tip), QPointF(*l)); p.drawLine(QPointF(*tip), QPointF(*r))
    elif kind == "rotate":
        p.drawArc(QRectF(6, 6, 20, 20), 60 * 16, 280 * 16)
        p.setPen(QPen(accent, 2.2)); p.drawLine(QPointF(21, 5), QPointF(22, 10)); p.drawLine(QPointF(22, 10), QPointF(17, 11))
    elif kind == "stretch":
        p.drawRect(QRectF(5, 10, 12, 12)); p.setPen(QPen(accent, 2.2))
        p.drawLine(QPointF(17, 16), QPointF(28, 16)); p.drawLine(QPointF(28, 16), QPointF(24, 12)); p.drawLine(QPointF(28, 16), QPointF(24, 20))
    elif kind == "duplicate":
        p.drawRect(QRectF(5, 5, 15, 15)); p.setBrush(QColor(255, 255, 255)); p.drawRect(QRectF(12, 12, 15, 15))
    elif kind == "delete":
        p.setPen(QPen(QColor(200, 60, 50), 2.6)); p.drawLine(QPointF(8, 8), QPointF(24, 24)); p.drawLine(QPointF(24, 8), QPointF(8, 24))
    elif kind == "zoom":
        p.drawEllipse(QRectF(5, 5, 22, 22)); p.drawLine(QPointF(16, 10), QPointF(16, 22)); p.drawLine(QPointF(10, 16), QPointF(22, 16))
    elif kind == "joinery":
        p.drawRect(QRectF(6, 5, 9, 22)); p.setPen(QPen(accent, 2)); p.drawRect(QRectF(18, 7, 9, 9)); p.drawLine(QPointF(22.5, 7), QPointF(22.5, 16))
    elif kind == "slab":
        p.setBrush(QColor(210, 214, 220))
        p.drawPolygon(QPolygonF([QPointF(3, 18), QPointF(17, 11), QPointF(29, 16), QPointF(15, 23)]))
    elif kind == "roof":
        p.setBrush(QColor(196, 90, 70)); p.drawPolygon(QPolygonF([QPointF(3, 17), QPointF(16, 5), QPointF(29, 17)]))
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawRect(QRectF(7, 17, 18, 11))
    elif kind == "stair":
        p.drawPolyline(QPolygonF([QPointF(3, 28), QPointF(3, 23), QPointF(9, 23), QPointF(9, 18), QPointF(15, 18),
                                  QPointF(15, 13), QPointF(21, 13), QPointF(21, 8), QPointF(28, 8)]))
    elif kind == "object":
        p.drawRect(QRectF(6, 9, 20, 16)); p.drawLine(QPointF(6, 9), QPointF(11, 4)); p.drawLine(QPointF(26, 9), QPointF(31, 4))
        p.drawLine(QPointF(11, 4), QPointF(31, 4))
    elif kind == "gear":
        p.drawEllipse(QRectF(10, 10, 12, 12))
        for k in range(8):
            import math
            a = k * math.pi / 4
            p.drawLine(QPointF(16 + 8 * math.cos(a), 16 + 8 * math.sin(a)), QPointF(16 + 12 * math.cos(a), 16 + 12 * math.sin(a)))
    p.end()
    return QIcon(pix)


# --------------------------------------------------------------------------- 1. first row
def _install_top_row(window):
    old = window.menuBar()
    menus = [a.menu() for a in old.actions() if a.menu() is not None]
    # The old bar is deleted by setMenuWidget below; the menus it parented must survive it.
    for m in old.findChildren(QMenu, options=Qt.FindChildOption.FindDirectChildrenOnly):
        m.setParent(window, m.windowFlags())
    bar = QMenuBar(); bar.setObjectName("main_menu_bar"); bar.setNativeMenuBar(False)
    for m in menus:
        bar.addMenu(m)
    row = QWidget(); row.setObjectName("top_row")
    row.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    h = QHBoxLayout(row); h.setContentsMargins(10, 2, 6, 2); h.setSpacing(6)
    logo = QLabel(); logo.setPixmap(_icon("logo", 20).pixmap(20, 20)); h.addWidget(logo)
    name = QLabel("ArchForge"); name.setObjectName("app_name"); h.addWidget(name)
    project = QLabel(); project.setObjectName("project_name"); h.addWidget(project)
    h.addStretch(1)
    quick = []
    for action, kind in ((window.save_action, "save"), (window.undo_action, "undo"), (window.redo_action, "redo")):
        if action.icon().isNull():
            action.setIcon(_icon(kind))
        b = QToolButton(); b.setObjectName("quick"); b.setDefaultAction(action); b.setAutoRaise(True)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly); b.setIconSize(QSize(18, 18))
        h.addWidget(b); quick.append(b)
    sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine); sep.setStyleSheet("color:#D8DEE8"); h.addWidget(sep)
    bar.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
    h.addWidget(bar)
    window.setMenuWidget(row)
    # QMainWindow.menuBar() would make a new, empty bar now that the menu widget is a row; the code and tests
    # ask the window for its menu bar, so answer with the real one.
    window.menuBar = lambda: bar

    def show_name(title=None):
        title = window.windowTitle() if title is None else title
        text = title.replace("[*]", "").split("—", 1)[-1].strip() if "—" in title else ""
        project.setText(f"— {text}" if text else "")
    window.windowTitleChanged.connect(show_name)
    show_name()
    window._top_row, window._top_menu_bar, window._quick_buttons, window._project_name_label = row, bar, quick, project
    return row


# --------------------------------------------------------------------------- 2. tool groups
from archforge.ui.toolbar_custom import CustomizableButtons, SEP, make_button


class ToolGroup(QToolBar, CustomizableButtons):
    """A movable bar: a row of buttons with the group's title under them; «Τίτλος ▾» opens ``menu``.
    Right click: hide / show its buttons, add any menu command, icon size (``toolbar_custom``)."""

    def __init__(self, window, key, title, menu=None):
        super().__init__(title, window)
        self.custom_key, self.custom_title = key, title
        self.custom_buttons = {}                # menu path → button the human added
        self._labelled = []                     # (label, button) in order
        self.setObjectName(f"group_{key}")
        self.setProperty("afgroup", True)
        self.setMovable(True)
        self.setFloatable(True)
        self.items = []                         # actions / widgets in order (for tests and the ⚙ of later)
        box = QWidget(); box.setObjectName("tool_group")
        v = QVBoxLayout(box); v.setContentsMargins(1, 0, 1, 0); v.setSpacing(0)
        self.row = QBoxLayout(QBoxLayout.Direction.LeftToRight); self.row.setSpacing(0); v.addLayout(self.row)
        # Dragged to the left / right edge (or floated upright) the buttons stack top to bottom.
        self.orientationChanged.connect(lambda o: self.row.setDirection(
            QBoxLayout.Direction.TopToBottom if o == Qt.Orientation.Vertical else QBoxLayout.Direction.LeftToRight))
        caption = QToolButton(box); caption.setObjectName("group_title"); caption.setAutoRaise(True)
        caption.setText(f"{title} ▾" if menu is not None else title)
        if menu is not None:
            menu.setTearOffEnabled(True)        # the dashed line on top = 📌 pin it open
            caption.setMenu(menu)
            caption.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            caption.setStyleSheet("QToolButton::menu-indicator { image:none; width:0; }")
            caption.setToolTip(f"Όλα τα εργαλεία της ομάδας «{title}» · η διακεκομμένη γραμμή πάνω = μένει ανοιχτό")
        else:
            caption.setEnabled(False)
        v.addWidget(caption, 0, Qt.AlignmentFlag.AlignHCenter)
        self.caption, self.menu = caption, menu
        self.addWidget(box)

    def add(self, action=None, *, widget=None, menu=None, icon=None, text=None):
        if widget is not None:
            widget.setParent(self.row.parentWidget())
            widget.show()
            self.row.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
            self.items.append(widget)
            return widget
        b = QToolButton(); b.setAutoRaise(True)
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon); b.setIconSize(QSize(26, 26))
        if action is not None:
            if icon is not None and action.icon().isNull():
                action.setIcon(icon)
            b.setDefaultAction(action)
            if text:
                b.setText(text)
            self.items.append(action)
        else:
            b.setText(text or menu.title().replace("&&", "&")); b.setIcon(icon or menu.icon())
            b.setMenu(menu); b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            b.setToolTip(menu.title().replace("&&", "&"))
            self.items.append(menu)
        self.row.addWidget(b)
        self._labelled.append((b.text().replace("&&", "&"), b))
        return b

    def labelled_buttons(self):
        return list(self._labelled)

    def add_custom(self, path, action):
        b = make_button(action, path.split(SEP)[-1], getattr(self.window(), "_catalog_icons", {}).get(path))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.row.addWidget(b)
        self.custom_buttons[path] = b
        self._labelled.append((path.split(SEP)[-1], b))
        return b

    def remove_custom(self, path):
        b = self.custom_buttons.get(path)
        self._labelled = [(l, x) for l, x in self._labelled if x is not b]
        CustomizableButtons.remove_custom(self, path)

    def actions_in_group(self):
        """Every action reachable from the buttons (menu buttons count with their whole menu)."""
        out = []
        for item in self.items:
            if isinstance(item, QAction):
                out.append(item)
            elif isinstance(item, QMenu):
                out.append(item.menuAction()); out.extend(_all_actions(item))
        return out


def _all_actions(menu):
    out = []
    for a in menu.actions():
        out.append(a)
        if a.menu() is not None:
            out.extend(_all_actions(a.menu()))
    return out


def _sub(menu, title):
    for a in menu.actions() if menu is not None else ():
        if a.menu() is not None and a.text().replace("&&", "&") == title:
            return a.menu()
    return None


def _with_menu(button, source):
    """The group's button keeps its click and gets ``source``'s ▾ menu (the Τοίχος / Γλυπτική choices built with the
    ribbon in approved_mockup_shell.py — one menu, not a copy)."""
    menu = source.menu() if source is not None else None
    if button is not None and menu is not None:
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
    return button


def _install_groups(window):
    from archforge.ui.workspace_layout import make_icon
    menus = getattr(window, "_main_menus", {})
    build, library = menus.get("Κατασκευή"), menus.get("Βιβλιοθήκη")
    keys = getattr(getattr(window, "shortcuts", None), "actions", {}) or {}
    groups = {}

    select = ToolGroup(window, "select", "Επιλογή")
    select.add(keys.get("tool.select"), icon=make_icon("select"), text="Επιλογή")
    groups["select"] = select

    construct = ToolGroup(window, "build", "Κατασκευή", build)
    wall = construct.add(keys.get("tool.wall"), icon=make_icon("wall"), text="Τοίχος")
    _with_menu(wall, getattr(window, "_mockup_wall_button", None))      # «Τοίχος ▾»: είδος, γυάλινος (owner 29/10)
    window._layout2_wall_button = wall
    for title, icon, text in (("Κουφώματα", "joinery", None), ("Σκάλα / Ράμπα", "stair", "Σκάλα"),
                              ("Δάπεδα & πλάκες", "slab", "Πλάκα"), ("Στέγη", "roof", None)):
        sub = _sub(build, title)
        if sub is not None:
            construct.add(menu=sub, icon=_icon(icon), text=text or title)
    groups["build"] = construct
    # «Υψόμετρο» (terrain rectangle) belongs to Έδαφος & περιβάλλον; keep it one click away there.
    terrain = getattr(window, "_mockup_terrain_menu", None)
    rect = getattr(window, "_terrain_rectangle_action", None)
    if terrain is not None and rect is not None and rect not in terrain.actions():
        regions = getattr(window, "_terrain_regions_menu", None)
        terrain.insertAction(regions.menuAction() if regions is not None else None, rect)

    lib = ToolGroup(window, "library", "Βιβλιοθήκη", library)
    obj = QAction(_icon("object"), "Αντικείμενο", window)
    obj.setToolTip("Τοποθέτηση αντικειμένου από τη βιβλιοθήκη")
    obj.triggered.connect(lambda: window._choose_library_asset())
    window._layout2_object_action = obj
    lib.add(obj)
    mats = QAction(make_icon("materials"), "Υλικά", window)
    mats.setToolTip("Υλικό στο επιλεγμένο αντικείμενο")
    mats.triggered.connect(lambda: window._open_selected_materials())
    window._layout2_materials_action = mats
    lib.add(mats)
    sculpt = QAction(make_icon("sculpt"), "Γλυπτική", window)
    sculpt.setToolTip("Γλυπτική: πλάσε την επιφάνεια με το ποντίκι (δεξί κλικ: εργασία, ροδέλα: πινέλο)")
    sculpt.setCheckable(True)
    sculpt.triggered.connect(lambda _=False: window.sculpt_action.toggle())
    window.sculpt_action.toggled.connect(sculpt.setChecked)
    window._layout2_sculpt_action = sculpt
    window._layout2_sculpt_button = _with_menu(lib.add(sculpt), getattr(window, "_mockup_sculpt_button", None))
    brush = getattr(window, "_mockup_brush_action", None)        # «Πινέλο» υλικού (owner 28/10)
    if brush is not None:
        window._layout2_brush_button = lib.add(brush)
    groups["library"] = lib

    storeys = _sub(build, "Όροφοι")
    floor = ToolGroup(window, "storey", "Όροφος", storeys)
    floor.add(widget=window.floor_selector)
    floor.add(getattr(window, "_mockup_add_floor_action", None), text="+ Όροφος")
    floor.add(getattr(window, "_mockup_basement_action", None), text="Υπόγειο")
    groups["storey"] = floor

    old_bars = [getattr(window, n, None) for n in ("_mockup_ribbon", "_mockup_floor_bar", "_mockup_camera_bar", "_mockup_snap_bar")]
    env = window.findChild(QToolBar, "workspace_bar")
    first = next((b for b in old_bars if b is not None), None)
    for g in groups.values():
        if first is not None:
            window.insertToolBar(first, g)
        else:
            window.addToolBar(Qt.ToolBarArea.TopToolBarArea, g)
    if env is not None:
        window.removeToolBar(env)
        if first is not None:
            window.insertToolBar(first, env)
        else:
            window.addToolBar(Qt.ToolBarArea.TopToolBarArea, env)
        env.show()
    # The old bars are emptied into the groups / the drawing: hidden, and out of «Γραμμές εργαλείων».
    bars_menu = getattr(window, "_toolbars_menu", None)
    for b in old_bars:
        if b is None:
            continue
        b.hide()
        if bars_menu is not None and b.toggleViewAction() in bars_menu.actions():
            bars_menu.removeAction(b.toggleViewAction())
    if bars_menu is not None:
        anchor = bars_menu.actions()[0] if bars_menu.actions() else None
        for g in groups.values():
            toggle = g.toggleViewAction(); toggle.setText(g.windowTitle())
            bars_menu.insertAction(anchor, toggle)
    lock = getattr(window, "_toolbars_lock_action", None)
    if lock is not None:
        lock.toggled.connect(lambda on: [g.setMovable(not on) for g in groups.values()])
    window._tool_groups = groups
    return groups


# --------------------------------------------------------------------------- 4. view settings on the drawing
def _install_view_settings(window):
    tabs = getattr(window, "_central_tabs", None)
    if tabs is None:
        return None
    frame = QFrame(); frame.setObjectName("view_settings")
    h = QHBoxLayout(frame); h.setContentsMargins(0, 0, 4, 2); h.setSpacing(4)
    moved = []
    for attr in ("_mockup_view_button", "_mockup_style_button", "_cameras_button"):
        b = getattr(window, attr, None)
        if b is None:
            continue
        for bar in window.findChildren(QToolBar):
            for a in list(bar.actions()):
                if bar.widgetForAction(a) is b:
                    bar.removeAction(a)
        b.setParent(frame); b.setAutoRaise(True); b.setIconSize(QSize(18, 18)); b.show()
        h.addWidget(b); moved.append(b)
    for attr, label in (("_mockup_grid_check", None), ("_mockup_snap_check", None), ("_mockup_snap_size", None)):
        w = getattr(window, attr, None)
        if w is None:
            continue
        for bar in window.findChildren(QToolBar):
            for a in list(bar.actions()):
                if bar.widgetForAction(a) is w:
                    bar.removeAction(a)
        w.setParent(frame); w.show(); h.addWidget(w); moved.append(w)
    tabs.setCornerWidget(frame, Qt.Corner.TopRightCorner)
    frame.show()
    window._view_settings = frame
    return frame


# --------------------------------------------------------------------------- 3. «Κοινά»
def _palette_cols(window):
    from archforge.ui.toolbar_custom import prefs
    return prefs(window).get("palette_cols", 5)


class CommonPalette(QFrame, CustomizableButtons):
    """The everyday commands over the drawing; dragged by ⋮⋮, ⚙ chooses the buttons."""

    MARGIN = 14

    def __init__(self, window, host):
        super().__init__(host)
        self.window_ = window
        self.setObjectName("common_palette")
        self.custom_key, self.custom_title = "common", "Κοινά"
        self.custom_buttons = {}
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.offset = None                  # distance of the bottom-right corner from the host's; None = default
        self._drag = None
        from archforge.ui.workspace_layout import make_icon
        keys = getattr(getattr(window, "shortcuts", None), "actions", {}) or {}
        outer = QVBoxLayout(self); outer.setContentsMargins(2, 1, 2, 1); outer.setSpacing(0)
        top = QHBoxLayout(); top.setSpacing(2)
        handle = QLabel("⋮⋮"); handle.setObjectName("palette_handle"); handle.setCursor(Qt.CursorShape.SizeAllCursor)
        handle.setToolTip("Σύρε για να τη μετακινήσεις όπου θέλεις")
        top.addWidget(handle); self.handle = handle
        self.buttons = {}
        grid = QGridLayout(); grid.setSpacing(0); self.grid = grid
        for action_id, label, icon in COMMON:
            action = keys.get(action_id)
            if action is None:
                continue
            if action.icon().isNull():
                action.setIcon(make_icon("select") if icon == "select" else _icon(icon))
            b = QToolButton(); b.setAutoRaise(True); b.setDefaultAction(action)
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon); b.setIconSize(QSize(20, 20))
            b.setText(label)
            n = len(self.buttons)
            grid.addWidget(b, n // 5, n % 5); self.buttons[action_id] = b
        top.addLayout(grid)
        outer.addLayout(top)
        foot = QHBoxLayout(); foot.setContentsMargins(2, 0, 0, 0)
        title = QLabel("Κοινά"); title.setObjectName("palette_title"); foot.addWidget(title); foot.addStretch(1)
        gear = QToolButton(); gear.setAutoRaise(True); gear.setIcon(_icon("gear")); gear.setIconSize(QSize(12, 12))
        gear.setToolTip("Ποια κουμπιά έχει η παλέτα"); gear.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        gear.setStyleSheet("QToolButton::menu-indicator { image:none; width:0; }")
        choose = QMenu(gear)
        # ⚙ = the same «Προσαρμογή» as a right click: its buttons, add any menu command, icon size.
        def fill_choose():
            from archforge.ui.toolbar_custom import customize_menu
            choose.clear()
            for a in customize_menu(window, self).actions():
                choose.addAction(a)
            choose.addSeparator()
            hide = choose.addAction("Κλείσιμο παλέτας (Προβολή ▸ Πάνελ ▸ Κοινά)")
            hide.triggered.connect(lambda: self.toggle_action.setChecked(False))
        choose.aboutToShow.connect(fill_choose)
        gear.setMenu(choose); foot.addWidget(gear)
        outer.addLayout(foot)
        self.choose_menu = choose
        self.toggle_action = QAction("Κοινά (παλέτα)", window); self.toggle_action.setCheckable(True)
        self.toggle_action.setChecked(True); self.toggle_action.toggled.connect(self.setVisible)
        host.installEventFilter(self)
        handle.installEventFilter(self)
        self.adjustSize()
        self.place()
        self.raise_()

    def set_shown(self, action_id, on):
        b = self.buttons.get(action_id)
        if b is not None:
            from archforge.ui.toolbar_custom import set_shown
            set_shown(self.window_, self, b.text(), on)

    def labelled_buttons(self):
        return [(b.text(), b) for b in self.buttons.values()] + [(p.split(SEP)[-1], b) for p, b in self.custom_buttons.items()]

    def add_custom(self, path, action):
        b = make_button(action, path.split(SEP)[-1], getattr(self.window_, "_catalog_icons", {}).get(path))
        b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.custom_buttons[path] = b
        self._relayout()
        return b

    def remove_custom(self, path):
        CustomizableButtons.remove_custom(self, path)
        self._relayout()

    def set_icon_size(self, size, text):
        CustomizableButtons.set_icon_size(self, size, text)
        self._relayout()

    def _relayout(self):
        """Visible buttons packed in rows of five (a hidden one leaves no hole)."""
        for b in list(self.buttons.values()) + list(self.custom_buttons.values()):
            self.grid.removeWidget(b)
        k = 0
        for b in list(self.buttons.values()) + list(self.custom_buttons.values()):
            if b.testAttribute(Qt.WidgetAttribute.WA_WState_ExplicitShowHide) and b.isHidden():
                continue                          # hidden by the human (not merely not shown yet)
            cols = max(1, int(_palette_cols(self.window_)))
            self.grid.addWidget(b, k // cols, k % cols); k += 1
        self.adjustSize(); self.place()

    def shown(self):
        return [i for i, b in self.buttons.items() if not b.isHidden()]

    def place(self):
        host = self.parentWidget()
        if host is None:
            return
        self.adjustSize()
        off = self.offset or QPoint(self.MARGIN, self.MARGIN + 22)      # above the scale bar / status hint
        x = host.width() - self.width() - off.x()
        y = host.height() - self.height() - off.y()
        x = max(0, min(x, host.width() - self.width())); y = max(0, min(y, host.height() - self.height()))
        self.move(x, y)

    def eventFilter(self, obj, event):
        host = self.parentWidget()
        if obj is host and event.type() == QEvent.Type.Resize:
            self.place()
        elif obj is self.handle:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag = event.globalPosition().toPoint() - self.pos()
                return True
            if t == QEvent.Type.MouseMove and self._drag is not None:
                self.drag_to(event.globalPosition().toPoint() - self._drag)
                return True
            if t == QEvent.Type.MouseButtonRelease and self._drag is not None:
                self._drag = None
                return True
        return False

    def drag_to(self, pos):
        """Top-left at ``pos`` (host coordinates), kept inside; remembered as distance from the bottom-right."""
        host = self.parentWidget()
        x = max(0, min(pos.x(), host.width() - self.width()))
        y = max(0, min(pos.y(), host.height() - self.height()))
        self.offset = QPoint(host.width() - self.width() - x, host.height() - self.height() - y)
        self.move(x, y)


def _install_common_palette(window):
    host = window.centralWidget()
    palette = CommonPalette(window, host)
    panels = None
    for a in getattr(window, "view_menu", QMenu()).actions():
        if a.menu() is not None and a.text() == "Πάνελ":
            panels = a.menu()
    if panels is not None:
        panels.addSeparator(); panels.addAction(palette.toggle_action)
    palette.show()
    window._common_palette = palette
    return palette


# --------------------------------------------------------------------------- 5. panels on the right
def _arrange_panels(window):
    docks = {d.objectName(): d for d in window.findChildren(QDockWidget)}
    props = window.dock
    below = [docks.get(n) for n in ("approved_project_library", "approved_assistant", "layers_panel", "cameras_dock")]
    below = [d for d in below if d is not None and d is not props]
    if not below:
        return
    for d in below:
        # Tall panels (the Βοηθός is ~840 px) scroll inside the lower half instead of stretching the window.
        inner = d.widget()
        if inner is not None and not isinstance(inner, QScrollArea) and inner.minimumSizeHint().height() > 260:
            scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(inner); d.setWidget(scroll)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props)
    first = below[0]
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, first)
    window.splitDockWidget(props, first, Qt.Orientation.Vertical)
    for d in below[1:]:
        window.tabifyDockWidget(first, d)
    first.raise_(); props.raise_()
    window.resizeDocks([props], [340], Qt.Orientation.Horizontal)
    window.resizeDocks([props, first], [430, 470], Qt.Orientation.Vertical)
    window._layout2_right_docks = (props, *below)


def install_layout2(window):
    window.setStyleSheet(window.styleSheet() + STYLE)
    _install_top_row(window)
    _install_groups(window)
    _install_view_settings(window)
    _arrange_panels(window)
    _install_common_palette(window)
    from archforge.ui import toolbar_custom
    toolbar_custom.install(window)              # right click on a group: its buttons, add a command, icon size
    from archforge.ui import mouse_menus
    mouse_menus.install(window)                 # Εργαλεία ▸ Μενού ποντικιού: the right-click menu per task, by the human
    from archforge.ui.workspace_layout import LAYOUT_VERSION, guard_work_area, persistence_enabled, restore_layout
    guard_work_area(window)                     # the plan / 3D keeps its room whatever the panels do
    # The default captured before this regrouping is stale: take it again (same version as the saved one).
    window._default_layout_state = window.saveState(LAYOUT_VERSION)
    window._workspace_bars = tuple(getattr(window, "_tool_groups", {}).values()) + tuple(
        b for b in (window.findChild(QToolBar, "workspace_bar"),) if b is not None)
    window._workspace_panels = tuple(getattr(window, "_layout2_right_docks", ())) or getattr(window, "_workspace_panels", ())
    if persistence_enabled():
        restore_layout(window)
    return window
