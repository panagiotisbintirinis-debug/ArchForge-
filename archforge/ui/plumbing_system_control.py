"""Visible plumbing connection-system selector for the Plumbing report tab.

The choice is authoritative project intent: it updates ``pipe_system`` on the
cold-water supply point through the normal CommandStack. Routing, quantities
and the technical plan then re-derive from the same Document.

This UI does not assert that the currently encoded diameters are hydraulically
verified. Diameter selection remains ENGINEER_REVIEW until a sourced hydraulic
method is implemented.
"""
from __future__ import annotations

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from archforge.core.commands import UpdateEntity
from archforge.mep.plumbing import DEFAULT_SYSTEM, PIPE_SYSTEMS, pipe_system


SYSTEM_LABELS = {
    "multilayer": "Πολυστρωματική — διακλαδώσεις",
    "copper": "Χαλκός — διακλαδώσεις",
    "manifold": "Μονοσωλήνιο — πίνακες υδροληψίας",
}


def water_supply_point(doc):
    return next(
        (
            entity for entity in doc.entities.values()
            if entity.kind == "plumbing_point"
            and str(entity.params.get("point_type", "")) == "water_supply"
        ),
        None,
    )


def set_plumbing_system(window, system_key: str) -> bool:
    """Change the project's plumbing topology through CommandStack.

    Returns False when there is no cold-water supply yet. Invalid system keys
    are rejected rather than silently falling back to a different topology.
    """
    system_key = str(system_key)
    if system_key not in PIPE_SYSTEMS:
        raise ValueError(f"unsupported plumbing system: {system_key}")
    supply = water_supply_point(window.doc)
    if supply is None:
        return False
    current = str(supply.params.get("pipe_system", DEFAULT_SYSTEM))
    if current == system_key:
        return True
    window.stack.execute(UpdateEntity(supply.id, {"pipe_system": system_key}))
    return True


class PlumbingSystemControl(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title = QLabel("Σύστημα σύνδεσης:")
        title.setStyleSheet("font-weight:600")
        layout.addWidget(title)

        self.combo = QComboBox(self)
        for key in ("multilayer", "copper", "manifold"):
            self.combo.addItem(SYSTEM_LABELS[key], key)
        self.combo.setMinimumWidth(280)
        self.combo.setToolTip(
            "Αλλάζει την πραγματική τοπολογία του δικτύου και προκαλεί νέο routing. "
            "Οι διατομές παραμένουν ENGINEER_REVIEW μέχρι επαληθευμένο υδραυλικό υπολογισμό."
        )
        layout.addWidget(self.combo)

        self.status = QLabel(self)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:palette(mid);font-size:11px")
        layout.addWidget(self.status, 1)

        self.combo.activated.connect(self._activated)
        self.refresh()

    def showEvent(self, event):
        """Always re-read the currently loaded project when this control appears."""
        super().showEvent(event)
        self.refresh()

    def _activated(self, index):
        key = self.combo.itemData(int(index))
        if key is None:
            return
        if not set_plumbing_system(self.window, str(key)):
            self.refresh()
            self.window.statusBar().showMessage(
                "Πρόσθεσε πρώτα Παροχή κρύου νερού για να επιλέξεις σύστημα σύνδεσης",
                5000,
            )
            return
        label = SYSTEM_LABELS[str(key)]
        self.window.statusBar().showMessage(
            f"Υδραυλικά: {label} — το δίκτυο επαναχαράχθηκε από το ίδιο μοντέλο",
            4500,
        )
        # Keep the control and report in sync immediately after the command.
        self.refresh()
        tab = getattr(self.window, "_plumbing_tab", None)
        if tab is not None:
            tab.mark_stale()

    def refresh(self):
        supply = water_supply_point(self.window.doc)
        blocker = QSignalBlocker(self.combo)
        try:
            if supply is None:
                self.combo.setEnabled(False)
                self.combo.setCurrentIndex(0)
                self.status.setText("Χρειάζεται Παροχή κρύου νερού")
                return
            self.combo.setEnabled(True)
            key = pipe_system(self.window.doc)
            index = self.combo.findData(key)
            if index >= 0:
                self.combo.setCurrentIndex(index)
            if key == "manifold":
                self.status.setText("Κάθε σημείο τροφοδοτείται από συλλέκτη / πίνακα με ανεξάρτητη γραμμή")
            else:
                self.status.setText("Διακλαδωτό δίκτυο")
        finally:
            del blocker


def install(window):
    if getattr(window, "_plumbing_system_control", None) is not None:
        return window._plumbing_system_control
    tab = getattr(window, "_plumbing_tab", None)
    if tab is None or tab.layout() is None:
        return None
    control = PlumbingSystemControl(window, tab)
    tab.layout().insertWidget(1, control)
    window._plumbing_system_control = control
    window.stack.listeners.append(control.refresh)

    # Project loading can replace/rebind the live Document/CommandStack while the
    # report tab remains visible. The report already refreshes from window.doc;
    # make that same refresh authoritative for the selector too so it never keeps
    # stale "no supply" state from the previous/new empty document.
    original_refresh = tab.refresh
    if not getattr(tab, "_plumbing_system_refresh_wrapped", False):
        def refresh_with_system(*args, **kwargs):
            result = original_refresh(*args, **kwargs)
            control.refresh()
            return result
        tab.refresh = refresh_with_system
        tab._plumbing_system_refresh_wrapped = True

    return control


def install_on_class(MainWindow):
    """Install after plumbing_tab has completed its MainWindow wrapper."""
    if getattr(MainWindow, "_archforge_plumbing_system_control_installed", False):
        return
    original_init = MainWindow.__init__

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        install(self)

    MainWindow.__init__ = wrapped_init
    MainWindow._archforge_plumbing_system_control_installed = True
