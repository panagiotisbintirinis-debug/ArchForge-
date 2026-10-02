from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QWidget


@dataclass(frozen=True)
class WorkspaceDockSpec:
    """View-owned description of one dockable ArchForge workspace region.

    Dock layout is presentation state only. It must never become authoritative
    design state or mutate the Document merely because a panel is hidden,
    floated, resized, or moved.
    """

    key: str
    title: str
    area: Qt.DockWidgetArea
    allowed_areas: Qt.DockWidgetArea = Qt.DockWidgetArea.AllDockWidgetAreas


def install_workspace_dock(
    window: QMainWindow,
    spec: WorkspaceDockSpec,
    widget: QWidget,
) -> QDockWidget:
    """Install a real, user-hideable workspace panel on ``window``.

    The native ``toggleViewAction`` is intentionally retained on the dock so
    the View menu can expose the exact same visibility state Qt uses for the
    real widget. This avoids a parallel boolean/UI model.
    """

    dock = QDockWidget(spec.title, window)
    dock.setObjectName(f"workspace_dock_{spec.key}")
    dock.setAllowedAreas(spec.allowed_areas)
    dock.setWidget(widget)
    window.addDockWidget(spec.area, dock)

    action = dock.toggleViewAction()
    action.setObjectName(f"workspace_toggle_{spec.key}")
    action.setText(spec.title)
    dock.workspace_toggle_action = action
    return dock


def add_workspace_toggles(view_menu, docks: Iterable[QDockWidget]) -> None:
    """Expose native dock visibility actions in a View-menu section."""

    docks = tuple(docks)
    if not docks:
        return
    view_menu.addSeparator()
    for dock in docks:
        view_menu.addAction(dock.toggleViewAction())
