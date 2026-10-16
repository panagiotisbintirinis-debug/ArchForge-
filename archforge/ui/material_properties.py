"""«Ιδιότητες υλικού»: δεξί κλικ σε υλικό της Βιβλιοθήκης.

Χρώμα και ορατό μοτίβο (είδος, μέγεθος πλακιδίου, αρμός, χρώμα αρμού, φορά,
μετατόπιση σειρών) με ζωντανό δείγμα σε πραγματική κλίμακα.  Τα έτοιμα υλικά
δεν αλλάζουν: η αλλαγή αποθηκεύεται ως «δικό μου» αντίγραφο
(``rendering/user_materials.py``), ώστε τα παλιά έργα να μένουν ίδια.
Μόνο εμφάνιση: καμία φυσική ιδιότητα.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)

from archforge.rendering import user_materials as um
from archforge.rendering.patterns import PATTERN_NAMES, PATTERN_TYPES

OFFSETS = (("Χωρίς (σε κάνναβο)", 0.0), ("Μισό (τούβλο)", 0.5), ("Ένα τρίτο (σανίδες)", 1 / 3))


def _spin(parent, lo, hi, value, step, suffix, decimals=1):
    box = QDoubleSpinBox(parent)
    box.setRange(lo, hi)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setSuffix(suffix)
    box.setValue(value)
    return box


class MaterialPropertiesDialog(QDialog):
    def __init__(self, parent, material_id, doc=None):
        super().__init__(parent)
        self.material_id = str(material_id)
        self.saved_id = None
        self.doc = doc
        self._spec = um.editable_spec(self.material_id, doc)
        pattern = dict(self._spec.get("pattern") or {})
        self.setWindowTitle(f"Ιδιότητες υλικού — {self._spec.get('name', material_id)}")
        layout = QVBoxLayout(self)
        note = QLabel("Αλλαγή χρώματος και μοτίβου. Το έτοιμο υλικό δεν αλλάζει: "
                      "αποθηκεύεται ως «δικό μου» αντίγραφο για όλα τα έργα."
                      if not um.is_user_material(self.material_id) else
                      "Δικό σου υλικό: η αλλαγή ισχύει σε όλα τα έργα που το χρησιμοποιούν.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#5B6778;")
        layout.addWidget(note)
        form = QFormLayout()
        layout.addLayout(form)

        self._color = str(self._spec.get("color", "#9a9a9a"))
        self.color_button = QPushButton(self)
        self.color_button.clicked.connect(lambda: self._pick("_color", "Χρώμα υλικού"))
        form.addRow("Χρώμα", self.color_button)

        self.has_pattern = QCheckBox("Με μοτίβο (πλακάκια, πέτρα, σανίδες με αρμό)", self)
        self.has_pattern.setChecked(bool(pattern))
        form.addRow("", self.has_pattern)
        self.kind = QComboBox(self)
        for key in PATTERN_TYPES:
            self.kind.addItem(PATTERN_NAMES[key], key)
        self.kind.setCurrentIndex(max(0, self.kind.findData(pattern.get("type", "tiles"))))
        form.addRow("Μοτίβο", self.kind)
        self.unit_w = _spin(self, 0.1, 300.0, 100 * float(pattern.get("unit_w", 0.30)), 1.0, " cm")
        self.unit_h = _spin(self, 0.1, 300.0, 100 * float(pattern.get("unit_h", 0.30)), 1.0, " cm")
        form.addRow("Πλάτος πλακιδίου", self.unit_w)
        form.addRow("Ύψος πλακιδίου", self.unit_h)
        self.joint = _spin(self, 0.0, 80.0, 1000 * float(pattern.get("joint", 0.003)), 0.5, " mm")
        form.addRow("Αρμός", self.joint)
        self._joint_color = str(pattern.get("joint_color", "#a8a49b"))
        self.joint_button = QPushButton(self)
        self.joint_button.clicked.connect(lambda: self._pick("_joint_color", "Χρώμα αρμού"))
        form.addRow("Χρώμα αρμού", self.joint_button)
        self.direction = QComboBox(self)
        self.direction.addItems(["Όπως είναι", "Στροφή 90° (κάθετα)"])
        form.addRow("Φορά", self.direction)
        self.offset = QComboBox(self)
        for label, value in OFFSETS:
            self.offset.addItem(label, value)
        current = float(pattern.get("offset", 0.0))
        self.offset.setCurrentIndex(min(range(len(OFFSETS)), key=lambda i: abs(OFFSETS[i][1] - current)))
        form.addRow("Μετατόπιση σειρών", self.offset)

        self.preview = QLabel(self)
        self.preview.setFixedSize(360, 140)
        self.preview.setStyleSheet("border: 1px solid #747b82;")
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        self.problem = QLabel(self)
        self.problem.setStyleSheet("color:#b3261e;")
        layout.addWidget(self.problem)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Αποθήκευση")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Άκυρο")
        self.apply_button = buttons.addButton("Αποθήκευση και εφαρμογή στο επιλεγμένο",
                                              QDialogButtonBox.ButtonRole.AcceptRole)
        self.apply_to_selection = False
        self.apply_button.clicked.connect(lambda: setattr(self, "apply_to_selection", True))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        layout.addWidget(buttons)

        for box in (self.unit_w, self.unit_h, self.joint):
            box.valueChanged.connect(lambda *_: self._refresh())
        for combo in (self.kind, self.direction, self.offset):
            combo.currentIndexChanged.connect(lambda *_: self._refresh())
        self.has_pattern.toggled.connect(lambda *_: self._refresh())
        self._refresh()

    def _pick(self, attr, title):
        color = QColorDialog.getColor(QColor(getattr(self, attr)), self, title)
        if color.isValid():
            setattr(self, attr, color.name())
            self._refresh()

    def set_colors(self, color=None, joint_color=None):     # tests / scripted use
        self._color = um.normalise_color(color) or self._color
        self._joint_color = um.normalise_color(joint_color) or self._joint_color
        self._refresh()

    def spec(self) -> dict:
        """The edited spec; raises ValueError when the pattern is not valid."""
        if not self.has_pattern.isChecked():
            return um.with_properties(self._spec, color=self._color, pattern_type="")
        return um.with_properties(
            self._spec, color=self._color, pattern_type=self.kind.currentData(),
            unit_w=self.unit_w.value() / 100, unit_h=self.unit_h.value() / 100,
            joint=self.joint.value() / 1000, joint_color=self._joint_color,
            rotated=self.direction.currentIndex() == 1, offset=self.offset.currentData())

    def _refresh(self):
        from archforge.ui.pattern_swatch import material_swatch
        enabled = self.has_pattern.isChecked()
        for widget in (self.kind, self.unit_w, self.unit_h, self.joint, self.joint_button, self.direction, self.offset):
            widget.setEnabled(enabled)
        for button, color in ((self.color_button, self._color), (self.joint_button, self._joint_color)):
            button.setText(f"Επιλογή…  {color}")
            chip = QPixmap(22, 14)
            chip.fill(QColor(color))
            button.setIcon(QIcon(chip))
        try:
            spec = self.spec()
        except ValueError as exc:
            self.problem.setText(f"Δεν ταιριάζει: {exc}")
            self.ok_button.setEnabled(False)
            self.apply_button.setEnabled(False)
            return
        self.problem.setText("")
        self.ok_button.setEnabled(True)
        self.apply_button.setEnabled(True)
        image = material_swatch(self.material_id, self.preview.width(), self.preview.height(), spec=spec)
        self.preview.setPixmap(QPixmap.fromImage(image))

    def _accept(self):
        try:
            spec = self.spec()
        except ValueError as exc:
            QMessageBox.information(self, "Ιδιότητες υλικού", str(exc))
            return
        self.saved_id = um.save_properties(self.material_id, spec)
        self.accept()
