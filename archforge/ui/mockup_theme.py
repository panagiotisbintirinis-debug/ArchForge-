"""Approved ArchForge mockup visual shell.

Presentation only: it styles and arranges the existing real ArchForge widgets.
It does not replace PlanView, PBRViewport, Document, CommandStack, or tools.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

APPROVED_MOCKUP_STYLE = """
QMainWindow { background:#F1F4F8; }
QWidget { font-family:'Segoe UI'; font-size:12px; color:#1E2A3B; }
QMenuBar { background:#FFFFFF; border-bottom:1px solid #D8DEE8; padding:2px; }
QMenuBar::item { padding:8px 11px; background:transparent; }
QMenuBar::item:selected { background:#E8EEF7; border-radius:5px; }
QToolBar { background:#FFFFFF; border:0; border-bottom:1px solid #D8DEE8; spacing:4px; padding:5px 8px; }
QToolButton { border:1px solid transparent; border-radius:6px; padding:5px 7px; }
QToolButton:hover { background:#E8EEF7; }
QToolButton:checked { background:#CFE0FA; border-color:#2F6BD6; }
QPushButton { background:#FFFFFF; border:1px solid #D8DEE8; border-radius:5px; padding:5px 8px; }
QPushButton:hover { background:#E8EEF7; }
QPushButton:checked { background:#CFE0FA; border-color:#2F6BD6; }
QComboBox, QLineEdit, QDoubleSpinBox { background:#FFFFFF; border:1px solid #D8DEE8; border-radius:5px; padding:3px 6px; min-height:22px; }
QTabWidget::pane { border:1px solid #D8DEE8; background:#FFFFFF; }
QTabBar::tab { padding:7px 13px; background:#F7F9FC; color:#5B6778; border:1px solid #D8DEE8; border-bottom:0; }
QTabBar::tab:selected { background:#FFFFFF; color:#1E2A3B; font-weight:600; border-top:2px solid #2F6BD6; }
QDockWidget { background:#FFFFFF; titlebar-close-icon:none; titlebar-normal-icon:none; }
QDockWidget::title { background:#F7F9FC; border:1px solid #D8DEE8; padding:7px 8px; font-weight:600; }
QTreeWidget, QListWidget { background:#FFFFFF; border:1px solid #D8DEE8; outline:0; }
QTreeWidget::item:selected, QListWidget::item:selected { background:#CFE0FA; color:#1E2A3B; }
QStatusBar { background:#FFFFFF; border-top:1px solid #D8DEE8; }
QSplitter::handle { background:#F1F4F8; width:5px; height:5px; }
"""

def apply_approved_mockup_theme(window):
    """Apply the approved mockup shell without replacing any working editor."""
    window.setWindowTitle("ArchForge")
    window.resize(1536, 1000)
    window.setStyleSheet(APPROVED_MOCKUP_STYLE)

    # Match the approved composition: project/library left, properties/AI right,
    # views/rendering below, while the real Floor Plan / 3D / Structural editor
    # remains the authoritative central widget.
    docks = {d.objectName(): d for d in window.findChildren(QDockWidget)}
    project = docks.get("workspace_dock_project")
    library = docks.get("workspace_dock_library")
    props = docks.get("workspace_dock_properties")
    ai = docks.get("workspace_dock_ai")
    views = docks.get("workspace_dock_views")

    if project:
        project.setWindowTitle("Έργο / Επίπεδα / Υλικά")
        window.addDockWidget(Qt.LeftDockWidgetArea, project)
    if library:
        library.setWindowTitle("Βιβλιοθήκη")
        window.addDockWidget(Qt.LeftDockWidgetArea, library)
    if project and library:
        # Vertical stack like the approved mockup, not tabified.
        window.splitDockWidget(project, library, Qt.Vertical)

    if props:
        props.setWindowTitle("Ιδιότητες")
        window.addDockWidget(Qt.RightDockWidgetArea, props)
    if ai:
        ai.setWindowTitle("AI")
        window.addDockWidget(Qt.RightDockWidgetArea, ai)
    if props and ai:
        window.tabifyDockWidget(props, ai)
        props.raise_()

    if views:
        views.setWindowTitle("Προβολές / Στυλ Rendering")
        window.addDockWidget(Qt.BottomDockWidgetArea, views)

    # Practical proportions corresponding to the 1536px reference.
    if project and library:
        window.resizeDocks([project, library], [265, 265], Qt.Horizontal)
        window.resizeDocks([project, library], [360, 420], Qt.Vertical)
    if props:
        window.resizeDocks([props], [280], Qt.Horizontal)
    if views:
        window.resizeDocks([views], [125], Qt.Vertical)

    # Keep every region user-resizable/dockable.
    for dock in (project, library, props, ai, views):
        if dock:
            dock.setFeatures(
                QDockWidget.DockWidgetMovable |
                QDockWidget.DockWidgetFloatable |
                QDockWidget.DockWidgetClosable
            )
