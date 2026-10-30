"""«Μονάδες μέτρησης…» (Επεξεργασία, next to the keyboard shortcuts): how lengths are shown and written for others
(``core/units.py`` — owner 30/10: cm by default, IFC in m or mm).  A program setting; the model stays in metres."""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from archforge.core import units


class UnitsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Μονάδες μέτρησης")
        lay = QVBoxLayout(self)
        form = QFormLayout(); lay.addLayout(form)
        self.display = QComboBox()
        for key, (label, _k, _d) in units.LENGTH_UNITS.items():
            self.display.addItem(label, key)
        self.display.setCurrentIndex(self.display.findData(units.display_unit()))
        self.ifc = QComboBox()
        for key, label in units.IFC_UNITS.items():
            self.ifc.addItem(label, key)
        self.ifc.setCurrentIndex(self.ifc.findData(units.ifc_unit()))
        form.addRow("Διαστάσεις στην κάτοψη", self.display)
        form.addRow("Εξαγωγή IFC", self.ifc)
        note = QLabel("Το μοντέλο κρατά πάντα μέτρα· αλλάζει μόνο ό,τι βλέπεις και ό,τι γράφεται για άλλους. "
                      "Η εισαγωγή IFC διαβάζει μόνη της τη μονάδα του αρχείου.")
        note.setWordWrap(True); lay.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel); lay.addWidget(buttons)
        buttons.accepted.connect(self.apply); buttons.rejected.connect(self.reject)
        self.buttons = buttons

    def apply(self):
        from archforge.project.persistence import UserDataError
        try:
            units.save(display=self.display.currentData(), ifc=self.ifc.currentData())
        except UserDataError as exc:
            self.window.statusBar().showMessage(f"Μονάδες: δεν αποθηκεύτηκαν — {exc}", 8000)
            return
        self.window._redraw_views(all_views=True)
        self.window.statusBar().showMessage(
            f"Διαστάσεις σε {units.LENGTH_UNITS[units.display_unit()][0]} · IFC σε {units.IFC_UNITS[units.ifc_unit()]}", 6000)
        self.accept()


def install(window):
    action = QAction("Μονάδες μέτρησης…", window)
    action.setToolTip("Διαστάσεις σε mm / cm / m · IFC σε m ή mm")
    action.triggered.connect(lambda: open_dialog(window))
    window._units_action = action
    menu = getattr(window, "_mockup_menus", {}).get("Επεξεργασία")
    if menu is not None:
        menu.addAction(action)
    return action


def open_dialog(window):
    dlg = UnitsDialog(window)
    window._units_dialog = dlg
    dlg.open()
    return dlg
