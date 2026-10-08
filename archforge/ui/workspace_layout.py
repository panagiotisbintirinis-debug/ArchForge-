"""Mouse-first workspace: movable bars, view/style popups, a remembered layout.

Presentation state only. Where the bars and panels sit is kept with Qt's
``saveState`` in the user's data folder (``layout.ini``) — never in the
Document — and «Προβολή → Επαναφορά διάταξης» brings back the default.
Icons are drawn here with QPainter (no image files, nothing to license).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QApplication, QDockWidget, QMenu, QToolBar, QToolButton

LAYOUT_VERSION = 2          # bump when bars/panels are added or renamed
INK = QColor(40, 62, 92)
ACCENT = QColor(47, 107, 214)


def level_label(name):
    """Storey name as the human reads it (Ground → Ισόγειο, Floor 2 → 1ος όροφος); ids stay as stored."""
    from archforge.output.pdf import level_name
    return level_name(name)


# --------------------------------------------------------------------------- icons
def _pen(color=INK, width=4.0):
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _box(p, front=True, top=True):
    """Small isometric house block used by the camera icons."""
    p.drawPolygon(QPolygonF([QPointF(14, 26), QPointF(32, 16), QPointF(50, 26), QPointF(32, 36)]))
    p.drawLine(QPointF(14, 26), QPointF(14, 46)); p.drawLine(QPointF(50, 26), QPointF(50, 46))
    p.drawLine(QPointF(32, 36), QPointF(32, 56))
    p.drawLine(QPointF(14, 46), QPointF(32, 56)); p.drawLine(QPointF(50, 46), QPointF(32, 56))


def _draw(name, p):
    p.setPen(_pen()); p.setBrush(Qt.BrushStyle.NoBrush)
    if name == "select":
        p.setBrush(QColor(255, 255, 255))
        p.drawPolygon(QPolygonF([QPointF(18, 8), QPointF(18, 50), QPointF(29, 40), QPointF(37, 56),
                                 QPointF(44, 52), QPointF(36, 37), QPointF(50, 36)]))
    elif name == "wall":
        p.setBrush(QColor(200, 210, 224))
        p.drawRect(QRectF(8, 22, 48, 20))
        p.setPen(_pen(INK, 2.5))
        for x in (20, 32, 44):
            p.drawLine(QPointF(x, 22), QPointF(x, 42))
        p.setPen(_pen(ACCENT, 4)); p.drawPoint(QPointF(8, 32)); p.drawPoint(QPointF(56, 32))
    elif name == "elements":
        p.drawLine(QPointF(10, 54), QPointF(54, 54)); p.drawLine(QPointF(14, 54), QPointF(14, 14))
        p.setPen(_pen(ACCENT, 3.5)); p.drawArc(QRectF(-26, 14, 80, 80), 0 * 16, 90 * 16)
        p.drawLine(QPointF(14, 54), QPointF(54, 54))
    elif name == "sculpt":
        p.drawLine(QPointF(14, 50), QPointF(42, 22))
        p.setBrush(ACCENT); p.drawEllipse(QPointF(46, 18), 8, 8)
        p.setBrush(Qt.BrushStyle.NoBrush); p.drawArc(QRectF(6, 40, 20, 16), 180 * 16, 180 * 16)
    elif name == "materials":
        for i, c in enumerate((QColor(214, 120, 70), QColor(120, 170, 90), QColor(90, 140, 210))):
            p.setBrush(c); p.drawRoundedRect(QRectF(8 + i * 10, 10 + i * 8, 28, 36), 4, 4)
    elif name == "auto":
        p.drawLine(QPointF(12, 52), QPointF(40, 24))
        p.setPen(_pen(ACCENT, 3.5))
        for cx, cy, r in ((46, 16, 7), (24, 14, 4), (52, 38, 4)):
            p.drawLine(QPointF(cx - r, cy), QPointF(cx + r, cy)); p.drawLine(QPointF(cx, cy - r), QPointF(cx, cy + r))
    elif name == "floor_add":
        p.setBrush(QColor(200, 210, 224))
        p.drawPolygon(QPolygonF([QPointF(6, 44), QPointF(28, 34), QPointF(50, 44), QPointF(28, 54)]))
        p.setBrush(QColor(255, 255, 255))
        p.drawPolygon(QPolygonF([QPointF(6, 30), QPointF(28, 20), QPointF(50, 30), QPointF(28, 40)]))
        p.setPen(_pen(ACCENT, 5)); p.drawLine(QPointF(52, 6), QPointF(52, 22)); p.drawLine(QPointF(44, 14), QPointF(60, 14))
    elif name == "views":
        _box(p)
        p.setPen(_pen(ACCENT, 3.5)); p.drawEllipse(QPointF(50, 12), 8, 5); p.drawPoint(QPointF(50, 12))
    elif name == "style":
        p.setBrush(QColor(255, 236, 170)); p.drawEllipse(QPointF(32, 32), 13, 13)
        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(QPointF(32 + 19 * math.cos(a), 32 + 19 * math.sin(a)),
                       QPointF(32 + 27 * math.cos(a), 32 + 27 * math.sin(a)))
    elif name == "top":
        p.drawRect(QRectF(12, 12, 40, 40)); p.drawLine(QPointF(32, 12), QPointF(32, 34)); p.drawLine(QPointF(12, 34), QPointF(52, 34))
        p.setPen(_pen(ACCENT, 3)); p.drawLine(QPointF(32, 2), QPointF(32, 9))
    elif name == "front":
        p.drawPolygon(QPolygonF([QPointF(10, 30), QPointF(32, 10), QPointF(54, 30)]))
        p.drawRect(QRectF(14, 30, 36, 24)); p.setPen(_pen(ACCENT, 3)); p.drawRect(QRectF(27, 40, 10, 14))
    elif name == "side":
        p.drawPolygon(QPolygonF([QPointF(8, 30), QPointF(20, 12), QPointF(56, 12), QPointF(56, 30)]))
        p.drawRect(QRectF(8, 30, 48, 24)); p.setPen(_pen(ACCENT, 3)); p.drawRect(QRectF(18, 36, 10, 8)); p.drawRect(QRectF(36, 36, 10, 8))
    elif name == "orbit":
        _box(p); p.setPen(_pen(ACCENT, 3)); p.drawArc(QRectF(4, 4, 56, 56), 30 * 16, 120 * 16)
    elif name == "grid":
        p.setPen(_pen(INK, 2.5))
        for v in (12, 26, 40, 54):
            p.drawLine(QPointF(v, 8), QPointF(v, 56)); p.drawLine(QPointF(8, v), QPointF(56, v))
    elif name == "snap":
        p.drawArc(QRectF(12, 10, 40, 40), 0, 180 * 16)
        p.drawLine(QPointF(12, 30), QPointF(12, 46)); p.drawLine(QPointF(52, 30), QPointF(52, 46))
        p.setPen(_pen(ACCENT, 6)); p.drawLine(QPointF(12, 48), QPointF(12, 54)); p.drawLine(QPointF(52, 48), QPointF(52, 54))
    else:
        p.drawEllipse(QPointF(32, 32), 20, 20)


def make_icon(name):
    """A plain line icon drawn in code (64 px, scaled by Qt)."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    _draw(name, p)
    p.end()
    return QIcon(pix)


# --------------------------------------------------------------------------- popups
def popup_button(bar, text, icon, menu, tip):
    """«Κείμενο ▾» button on a bar: one click opens the menu under the mouse."""
    button = QToolButton(bar)
    button.setText(text)
    button.setIcon(make_icon(icon))
    button.setToolTip(tip)
    button.setMenu(menu)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    bar.addWidget(button)
    return button


def build_menu(parent, title, specs, checkable=False):
    """QMenu from ``(label, run, icon_name)``; checkable ones are exclusive (one style at a time)."""
    menu = QMenu(title, parent)
    group = QActionGroup(menu) if checkable else None
    for label, run, icon in specs:
        action = QAction(make_icon(icon) if icon else QIcon(), label, menu)
        action.triggered.connect(lambda _=False, r=run: r())
        if group is not None:
            action.setCheckable(True)
            group.addAction(action)
        menu.addAction(action)
    return menu


# --------------------------------------------------------------------------- layout
def layout_settings():
    from archforge.library.assets import data_dir
    return QSettings(str(data_dir() / "layout.ini"), QSettings.Format.IniFormat)


def persistence_enabled():
    """Only the real application remembers its layout (tests and scripts start from the default)."""
    app = QApplication.instance()
    return app is not None and app.applicationName() == "ArchForge"


def _named(window):
    """Every bar and panel needs an objectName for saveState."""
    for k, widget in enumerate(window.findChildren(QToolBar) + window.findChildren(QDockWidget)):
        if not widget.objectName():
            widget.setObjectName(f"{type(widget).__name__.lower()}_{k}")


def save_layout(window, settings=None):
    settings = settings or layout_settings()
    _named(window)
    settings.setValue("window/state", window.saveState(LAYOUT_VERSION))
    settings.setValue("window/geometry", window.saveGeometry())
    settings.sync()


def restore_layout(window, settings=None):
    """Put bars/panels where the human left them; False when nothing (or an older layout) is saved."""
    settings = settings or layout_settings()
    state = settings.value("window/state")
    geometry = settings.value("window/geometry")
    if geometry is not None:
        window.restoreGeometry(geometry)
    return bool(state is not None and window.restoreState(state, LAYOUT_VERSION))


def reset_layout(window):
    """Default arrangement: every working bar and panel back in its place."""
    default = getattr(window, "_default_layout_state", None)
    if default is not None:
        window.restoreState(default, LAYOUT_VERSION)
    for bar in getattr(window, "_workspace_bars", ()):
        bar.setVisible(True)
    for dock in getattr(window, "_workspace_panels", ()):
        dock.setFloating(False)
        dock.setVisible(True)
    window.statusBar().showMessage("Η διάταξη επανήλθε στην αρχική", 3000)


def install_workspace_layout(window, bars, panels):
    """Bars and panels movable / floatable / closable; default captured; saved layout restored."""
    _named(window)
    for bar in bars:
        bar.setMovable(True)
        bar.setFloatable(True)
        bar.setAllowedAreas(Qt.ToolBarArea.AllToolBarAreas)
    for dock in panels:
        dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable
                         | QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        dock.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
    window._workspace_bars = tuple(bars)
    window._workspace_panels = tuple(panels)
    window._default_layout_state = window.saveState(LAYOUT_VERSION)
    reset = QAction("Επαναφορά διάταξης", window)
    reset.setToolTip("Γραμμές εργαλείων και πάνελ πίσω στη θέση τους")
    reset.triggered.connect(lambda: reset_layout(window))
    # Place kept for the coming panels/workspaces (Layers panel, «Φέρων» environment for columns/beams):
    # insert their actions before this separator, so they sit above the layout reset.
    anchor = window.view_menu.addSeparator()
    anchor.setObjectName("view_menu_workspaces_anchor")
    window._view_menu_workspaces_anchor = anchor
    window.view_menu.addSeparator()
    window.view_menu.addAction(reset)
    window._reset_layout_action = reset
    if persistence_enabled():
        restore_layout(window)


# Property names as the Ιδιότητες panel shows them (the stored keys stay English).
PARAM_LABELS = {
    "x": "Θέση X", "y": "Θέση Y", "z": "Στάθμη", "x1": "Αρχή X", "y1": "Αρχή Y", "x2": "Τέλος X", "y2": "Τέλος Y",
    "x0": "Αρχή X", "y0": "Αρχή Y", "cx": "Κέντρο X", "cy": "Κέντρο Y",
    "height": "Ύψος", "thickness": "Πάχος", "width": "Πλάτος", "depth": "Βάθος", "length": "Μήκος",
    "rotation": "Περιστροφή (°)", "offset": "Μετατόπιση", "sill": "Ποδιά", "overhang": "Προεξοχή",
    "floor_level": "Στάθμη δαπέδου", "upper_z": "Άνω στάθμη", "upper_floor_z": "Στάθμη επάνω ορόφου",
    "eave_z": "Στάθμη γείσου", "diameter_x": "Διάμετρος X", "diameter_y": "Διάμετρος Y",
    "elevation": "Υψόμετρο", "radius": "Ακτίνα", "pitch_deg": "Κλίση (°)", "slope": "Κλίση",
    "value": "Τιμή", "surface_u": "Θέση στην επιφάνεια",
}


def param_label(key):
    return PARAM_LABELS.get(key, key)
