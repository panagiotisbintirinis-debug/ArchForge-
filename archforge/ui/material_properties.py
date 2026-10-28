"""«Ιδιότητες υλικού»: δεξί κλικ σε υλικό της Βιβλιοθήκης.

Χρώμα και ορατό μοτίβο (είδος, μέγεθος πλακιδίου, αρμός, χρώμα αρμού, φορά,
μετατόπιση σειρών) με ζωντανό δείγμα σε πραγματική κλίμακα.  Τα έτοιμα υλικά
δεν αλλάζουν: η αλλαγή αποθηκεύεται ως «δικό μου» αντίγραφο
(``rendering/user_materials.py``), ώστε τα παλιά έργα να μένουν ίδια.
Προαιρετικά η ίδια φόρμα δέχεται φωτογραφία, που ενσωματώνεται στο υλικό
με πραγματικό πλάτος/ύψος δηλωμένο από τον χρήστη (χωρίς εξωτερικό path).
Μόνο εμφάνιση: καμία φυσική ιδιότητα.
"""
from __future__ import annotations

import base64
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, Qt, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel,
    QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget,
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


def _image_aspect(data: str) -> float | None:
    """Pixel width / height of the imported photograph (not a site measurement)."""
    if not data:
        return None
    try:
        image = QImage.fromData(base64.b64decode(data.partition(",")[2]), "JPEG")
    except (ValueError, OSError) as exc:
        from archforge.core.notices import not_computed
        not_computed("materials.photo", "Υλικό από φωτογραφία: η εικόνα δεν διαβάστηκε, το κλείδωμα αναλογιών δεν "
                     "ισχύει", exc=exc)
        return None
    if image.isNull() or image.height() <= 0:
        return None
    return image.width() / image.height()


class MaterialPropertiesDialog(QDialog):
    def __init__(self, parent, material_id, doc=None, *, embedded=False):
        super().__init__(parent)
        self.embedded = bool(embedded)
        if self.embedded:
            # Reuse the exact same editor as a panel in the main dark browser.
            # It is no longer a second top-level window when embedded.
            self.setWindowFlags(Qt.WindowType.Widget)
        self.material_id = str(material_id)
        self.saved_id = None
        self.doc = doc
        self._spec = um.editable_spec(self.material_id, doc)
        pattern = dict(self._spec.get("pattern") or {})
        photo = dict(self._spec.get("image_texture") or {})
        self._photo_data = str(photo.get("data") or "")
        self._photo_aspect = _image_aspect(self._photo_data)
        self.setWindowTitle(f"Ιδιότητες υλικού — {self._spec.get('name', material_id)}")
        layout = QVBoxLayout(self)
        note = QLabel("Χρώμα, μοτίβο ή φωτογραφία. Το έτοιμο υλικό δεν αλλάζει: "
                      "αποθηκεύεται ως «δικό μου» αντίγραφο για όλα τα έργα."
                      if not um.is_user_material(self.material_id) else
                      "Δικό σου υλικό: η αλλαγή ισχύει σε όλα τα έργα που το χρησιμοποιούν.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#5B6778;")
        if not self.embedded:
            layout.addWidget(note)
        form = QFormLayout()
        if self.embedded:
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(form)

        self._color = str(self._spec.get("color", "#9a9a9a"))
        self.color_button = QPushButton(self)
        self.color_button.clicked.connect(lambda: self._pick("_color", "Χρώμα υλικού"))
        form.addRow("Χρώμα", self.color_button)

        # The dark library exposes the same value above its preview; this
        # field is kept in the editor model so Save persists it atomically.
        self.roughness = _spin(self, 0.0, 1.0, float(self._spec.get("roughness", 0.6)), 0.05, "", 2)
        if not self.embedded:
            form.addRow("Τραχύτητα", self.roughness)

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

        # Same material editor and persistence as procedural stone; no second library.
        image_actions = QWidget(self)
        image_row = QHBoxLayout(image_actions)
        image_row.setContentsMargins(0, 0, 0, 0)
        self.image_button = QPushButton("Εικόνα…", self)
        self.image_button.setToolTip("Φωτογραφία πέτρας, ξύλου, φυλλωσιάς κ.λπ. (JPG/PNG)")
        self.image_button.clicked.connect(self._choose_image)
        image_row.addWidget(self.image_button)
        self.clear_image_button = QPushButton("Αφαίρεση εικόνας", self)
        self.clear_image_button.clicked.connect(self._remove_image)
        image_row.addWidget(self.clear_image_button)
        form.addRow("Υλικό από φωτογραφία", image_actions)
        self.image_info = QLabel("Ενσωματωμένη εικόνα" if self._photo_data else "Δεν έχει επιλεγεί εικόνα", self)
        self.image_info.setWordWrap(True)
        form.addRow("", self.image_info)
        self.image_width = _spin(self, 0.0, 1000.0, float(photo.get("width_m", 0.0)), 0.1, " m", 2)
        self.image_width.setSpecialValueText("Συμπλήρωσε πλάτος")
        self.image_height = _spin(self, 0.0, 1000.0, float(photo.get("height_m", 0.0)), 0.1, " m", 2)
        self.image_height.setSpecialValueText("Συμπλήρωσε ύψος")
        form.addRow("Πραγματικό πλάτος εικόνας", self.image_width)
        form.addRow("Πραγματικό ύψος εικόνας", self.image_height)
        self.aspect_lock = QCheckBox("Κλείδωμα αναλογιών φωτογραφίας", self)
        self.aspect_lock.setChecked(True)
        self.aspect_lock.setToolTip("Αλλαγή της μίας διάστασης υπολογίζει αυτόματα την άλλη χωρίς παραμόρφωση.")
        form.addRow("", self.aspect_lock)
        if self._photo_data:
            self.has_pattern.setChecked(False)

        self.preview = QLabel(self)
        if self.embedded:
            self.preview.setFixedSize(285, 110)
        else:
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
        if not self.embedded:
            layout.addWidget(buttons)
        else:
            # Parent-owned widgets not in a layout otherwise float at (0,0)
            # above the first editing row in Qt, even though unused here.
            buttons.hide()

        for box in (self.unit_w, self.unit_h, self.joint):
            box.valueChanged.connect(lambda *_: self._refresh())
        self.image_width.valueChanged.connect(lambda *_: self._photo_dimension_changed("width"))
        self.image_height.valueChanged.connect(lambda *_: self._photo_dimension_changed("height"))
        self.aspect_lock.toggled.connect(self._photo_lock_changed)
        for combo in (self.kind, self.direction, self.offset):
            combo.currentIndexChanged.connect(lambda *_: self._refresh())
        self.has_pattern.toggled.connect(lambda *_: self._refresh())
        self.roughness.valueChanged.connect(lambda *_: self._refresh())
        self._refresh()

    def _photo_dimension_changed(self, changed: str):
        if self._photo_data and self._photo_aspect and self.aspect_lock.isChecked():
            if changed == "width":
                other = self.image_height
                value = self.image_width.value() / self._photo_aspect
            else:
                other = self.image_width
                value = self.image_height.value() * self._photo_aspect
            previous = other.blockSignals(True)
            try:
                other.setValue(value)
            finally:
                other.blockSignals(previous)
        self._refresh()

    def _photo_lock_changed(self, checked: bool):
        if checked and self._photo_data:
            if self.image_width.value() > 0:
                self._photo_dimension_changed("width")
                return
            if self.image_height.value() > 0:
                self._photo_dimension_changed("height")
                return
        self._refresh()

    def _choose_image(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Υλικό από εικόνα", "", "Εικόνες (*.jpg *.jpeg *.png *.webp *.bmp)")
        if not filename:
            return
        reader = QImageReader(filename)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid() and max(size.width(), size.height()) > 1024:
            factor = 1024 / max(size.width(), size.height())
            reader.setScaledSize(QSize(max(1, round(size.width() * factor)),
                                       max(1, round(size.height() * factor))))
        image = reader.read()
        if image.isNull():
            QMessageBox.warning(self, "Υλικό από εικόνα", reader.errorString() or "Δεν διαβάστηκε η εικόνα.")
            return
        if max(image.width(), image.height()) > 1024:
            image = image.scaled(1024, 1024, Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
        # JPEG keeps each project's embedded texture modest and portable.
        opaque = QImage(image.size(), QImage.Format.Format_RGB32)
        opaque.fill(Qt.GlobalColor.white)
        painter = QPainter(opaque)
        painter.drawImage(0, 0, image)
        painter.end()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        if not opaque.save(buffer, "JPEG", 82):
            QMessageBox.warning(self, "Υλικό από εικόνα", "Δεν ήταν δυνατή η αποθήκευση της εικόνας.")
            return
        encoded = "data:image/jpeg;base64," + base64.b64encode(bytes(buffer.data())).decode("ascii")
        if len(encoded) > 1_250_000:
            QMessageBox.warning(self, "Υλικό από εικόνα", "Η φωτογραφία είναι πολύ μεγάλη.")
            return
        self._photo_data = encoded
        self._photo_aspect = opaque.width() / opaque.height()
        self.image_info.setText(Path(filename).name + " — ενσωματώνεται στο έργο")
        self.has_pattern.setChecked(False)
        self._photo_lock_changed(self.aspect_lock.isChecked())

    def _remove_image(self):
        self._photo_data = ""
        self._photo_aspect = None
        self.image_info.setText("Δεν έχει επιλεγεί εικόνα")
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
            result = um.with_properties(self._spec, color=self._color, pattern_type="")
            result["roughness"] = self.roughness.value()
            if self._photo_data:
                return um.with_image_texture(result, self._photo_data,
                                             self.image_width.value(), self.image_height.value())
            result.pop("image_texture", None)
            return result
        result = um.with_properties(
            self._spec, color=self._color, pattern_type=self.kind.currentData(),
            unit_w=self.unit_w.value() / 100, unit_h=self.unit_h.value() / 100,
            joint=self.joint.value() / 1000, joint_color=self._joint_color,
            rotated=self.direction.currentIndex() == 1, offset=self.offset.currentData())
        result["roughness"] = self.roughness.value()
        result.pop("image_texture", None)
        return result

    def _refresh(self):
        from archforge.ui.pattern_swatch import material_swatch
        enabled = self.has_pattern.isChecked()
        for widget in (self.kind, self.unit_w, self.unit_h, self.joint, self.joint_button, self.direction, self.offset):
            widget.setEnabled(enabled)
        photo_enabled = bool(self._photo_data)
        self.clear_image_button.setEnabled(photo_enabled)
        self.aspect_lock.setEnabled(photo_enabled and not enabled)
        for widget in (self.image_width, self.image_height):
            widget.setEnabled(photo_enabled and not enabled)
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
            if self._photo_data and not enabled:
                raw = base64.b64decode(self._photo_data.partition(",")[2])
                pending = QImage.fromData(raw, "JPEG")
                self.preview.setPixmap(QPixmap.fromImage(pending).scaled(
                    self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
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
