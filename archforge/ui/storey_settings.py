"""Explicit storey elevations and independent interior clear heights.

The table is a view on the *existing* Document levels.  No parallel storey
model is maintained; Apply goes through the same CommandStack as the editor.
"""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)
from PySide6.QtCore import Qt

from archforge.core.commands import CompositeCommand
from archforge.core.storey_height import (
    ChangeStoreyClearHeight, ChangeStoreyElevation, clear_height,
)


class StoreySettings(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Όροφοι — στάθμες και καθαρά ύψη")
        self.resize(810, 460)
        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "Διάλεξε όροφο. Η στάθμη μετακινεί τα συνδεδεμένα στοιχεία του ορόφου και προσαρμόζει "
            "σκάλες/ράμπες. Το καθαρό ύψος αλλάζει την οροφή και τους συνδεδεμένους τοίχους, "
            "χωρίς να μετακινεί την επόμενη στάθμη."
        ))
        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(("#", "Όνομα", "Στάθμη (m)",
                                              "Ως επόμενο (m)", "Καθαρό ύψος (m)"))
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table, 1)
        fields = QFormLayout()
        self.elevation = QDoubleSpinBox(self)
        self.elevation.setDecimals(3)
        self.elevation.setRange(-1000.0, 1000.0)
        self.elevation.setSingleStep(.1)
        self.elevation.setSuffix(" m")
        fields.addRow("Στάθμη δαπέδου (απόλυτο Z)", self.elevation)
        self.height = QDoubleSpinBox(self)
        self.height.setDecimals(3)
        self.height.setRange(.001, 1000.0)
        self.height.setSingleStep(.1)
        self.height.setSuffix(" m")
        fields.addRow("Καθαρό εσωτερικό ύψος", self.height)
        root.addLayout(fields)
        self.hint = QLabel("", self)
        self.hint.setWordWrap(True)
        root.addWidget(self.hint)
        buttons = QHBoxLayout()
        root.addLayout(buttons)
        self.apply_button = QPushButton("Εφαρμογή — μία αναίρεση", self)
        self.apply_button.clicked.connect(self.apply_changes)
        buttons.addWidget(self.apply_button)
        buttons.addStretch(1)
        close = QPushButton("Κλείσιμο", self)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        self.table.currentCellChanged.connect(self._choose_row)
        self.refresh()

    def refresh(self, preferred=None):
        doc = self.window.doc
        self.names = [n for n, _z in sorted(doc.levels.items(), key=lambda item: float(item[1]))]
        self.table.blockSignals(True)
        self.table.setRowCount(len(self.names))
        for row, name in enumerate(self.names):
            z = float(doc.levels[name])
            next_z = float(doc.levels[self.names[row + 1]]) if row + 1 < len(self.names) else None
            try:
                inside = f"{clear_height(doc, name):.3f}"
            except ValueError:
                inside = "—"
            values = (str(row + 1), str(name), f"{z:.3f}",
                      f"{next_z - z:.3f}" if next_z is not None else "—", inside)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, column, item)
        self.table.blockSignals(False)
        active = preferred or doc.active_level_name()
        self.table.selectRow(self.names.index(active) if active in self.names else 0) if self.names else None
        self._choose_row()

    def _choose_row(self, *_args):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.names):
            self.apply_button.setEnabled(False)
            return
        name = self.names[row]
        self.elevation.setValue(float(self.window.doc.levels[name]))
        try:
            self.height.setValue(clear_height(self.window.doc, name))
        except ValueError as exc:
            self.height.setEnabled(False)
            self.hint.setText(f"Καθαρό ύψος: {exc}. Για τον συγκεκριμένο όροφο χρειάζεται χειροκίνητη επιλογή στοιχείων.")
        else:
            self.height.setEnabled(True)
            self.hint.setText("Οι τιμές είναι γεωμετρικές, όχι έλεγχος κανονισμών ή στατικής επάρκειας. "
                              "Αλλαγές στις σκάλες, στη στέγη και στον φέροντα οργανισμό απαιτούν έλεγχο μηχανικού.")
        self.apply_button.setEnabled(True)

    def apply_changes(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.names):
            return
        name = self.names[row]
        doc = self.window.doc
        commands = []
        new_z = self.elevation.value()
        if abs(new_z - float(doc.levels[name])) > 1e-5:
            commands.append(ChangeStoreyElevation(name, new_z))
        if self.height.isEnabled():
            try:
                previous_height = clear_height(doc, name)
            except ValueError:
                previous_height = None
            if previous_height is not None and abs(self.height.value() - previous_height) > 1e-5:
                commands.append(ChangeStoreyClearHeight(name, self.height.value()))
        if not commands:
            return
        try:
            # One complete Undo step if both fields changed.  The stack rolls
            # the document back atomically if any dependent relation refuses.
            self.window.stack.execute(CompositeCommand(commands, label="Ύψη ορόφου"))
        except (ValueError, PermissionError, RuntimeError, KeyError) as exc:
            QMessageBox.warning(self, "Δεν εφαρμόστηκε η αλλαγή", str(exc))
            return
        self.window._redraw_views(all_views=True)
        self.window.refresh_inspector()
        self.window.statusBar().showMessage(f"Ο όροφος «{name}» ενημερώθηκε — Ctrl+Z για αναίρεση", 5000)
        self.refresh(name)


def open_settings(window):
    dialog = StoreySettings(window)
    window._storey_settings_dialog = dialog  # keep alive while modeless
    dialog.show()
    dialog.raise_()
    return dialog


def install(window):
    action = QAction("Ρυθμίσεις ορόφων — στάθμη και καθαρό ύψος…", window)
    action.triggered.connect(lambda _=False: open_settings(window))
    section = getattr(window, "_work_sections", {}).get(("Έργο", "Όροφοι"))
    if section is not None:
        section.addAction(action)
    floor_group = getattr(window, "_tool_groups", {}).get("storey")
    if floor_group is not None:
        button = floor_group.add(action, text="Ύψη ορόφων")
        button.setText("")
        button.setToolTip("Ύψη ορόφων — στάθμη δαπέδου / καθαρό ύψος")
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFixedWidth(30)  # beside the floor selector, never forces a wider editor
    window._storey_settings_action = action
    return action
