"""Κωδικοί προμηθευτή και «Δικά μου υλικά» στον διάλογο «Υλικά / επιφάνειες».

* ``UserMaterialDialog``: «Νέο υλικό…» / «Επεξεργασία…» — όνομα, κωδικός,
  προμηθευτής, χρώμα (QColorDialog), βασική εμφάνιση (ένα έτοιμο υλικό του
  οποίου παίρνει τραχύτητα και μοτίβο) και κατηγορία, με ζωντανό δείγμα.
* ``import_codes``: «Εισαγωγή κωδικών από αρχείο…» — CSV (και από Excel σε
  ελληνικά Windows: ``;`` και cp1253) με προεπισκόπηση πριν την εισαγωγή.
* ``add_material_rows``: οι γραμμές «Υλικό» του πάνελ Ιδιότητες με τον κωδικό.

The data side (no Qt) is ``rendering/user_materials.py``.
"""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from archforge.rendering import user_materials as um
from archforge.rendering.materials import material_categories, materials_in_category


def _base_combo(parent, current=um.DEFAULT_BASE):
    from archforge.ui.pattern_swatch import material_icon
    combo = QComboBox(parent)
    combo.setIconSize(QSize(20, 20))
    combo.setMaxVisibleItems(20)
    for category in material_categories():
        for material_id, spec in materials_in_category(category):
            combo.addItem(material_icon(material_id, 20), f"{spec['name']}  · {category}", material_id)
    combo.setCurrentIndex(max(0, combo.findData(current)))
    return combo


class UserMaterialDialog(QDialog):
    """«Νέο υλικό» — or editing one of the user's own materials."""

    def __init__(self, parent=None, material_id=None, spec=None, category=""):
        super().__init__(parent)
        self.material_id = material_id
        spec = dict(spec or {})
        self.setWindowTitle("Επεξεργασία υλικού" if material_id else "Νέο υλικό")
        layout = QVBoxLayout(self)
        intro = QLabel("Δικό σου υλικό, π.χ. μια μελαμίνη ή έναν πάγκο του προμηθευτή σου, με τον "
                       "κωδικό που παραγγέλνεις. Μένει στον υπολογιστή σου για όλα τα έργα και "
                       "αντιγράφεται στο έργο όταν το χρησιμοποιήσεις.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color:#5B6778;")
        layout.addWidget(intro)
        form = QFormLayout()
        layout.addLayout(form)

        self.name = QLineEdit(str(spec.get("name", "")), self)
        self.name.setPlaceholderText("π.χ. Μελαμίνη δρυς φυσική")
        form.addRow("Όνομα", self.name)
        self.code = QLineEdit(str(spec.get("code", "")), self)
        self.code.setPlaceholderText("όπως στο δειγματολόγιο του προμηθευτή")
        form.addRow("Κωδικός", self.code)
        self.supplier = QLineEdit(str(spec.get("supplier", "")), self)
        self.supplier.setPlaceholderText("προαιρετικό")
        form.addRow("Προμηθευτής", self.supplier)

        self.base = _base_combo(self, spec.get("base", um.DEFAULT_BASE))
        self.base.setToolTip("Από αυτό το υλικό παίρνει γυάλισμα και μοτίβο (νερά ξύλου, κόκκοι πέτρας…)")
        form.addRow("Βασική εμφάνιση", self.base)

        self._color = um.normalise_color(spec.get("color")) or ""
        color_row = QHBoxLayout()
        self.color_button = QPushButton("Επιλογή χρώματος…", self)
        self.color_button.clicked.connect(self._pick_color)
        self.color_from_base = QPushButton("Χρώμα της βάσης", self)
        self.color_from_base.clicked.connect(self._color_of_base)
        color_row.addWidget(self.color_button)
        color_row.addWidget(self.color_from_base)
        form.addRow("Χρώμα", color_row)

        self.category = QComboBox(self)
        self.category.setEditable(True)
        self.category.addItem(um.DEFAULT_CATEGORY)
        for name in material_categories():
            self.category.addItem(name)
        self.category.setCurrentText(str(spec.get("category") or category or um.DEFAULT_CATEGORY))
        self.category.setToolTip("Σε ποια λίστα του διαλόγου Υλικά θα φαίνεται (μπορείς να γράψεις νέα)")
        form.addRow("Κατηγορία", self.category)

        self.preview = QLabel(self)
        self.preview.setFixedSize(360, 110)
        self.preview.setStyleSheet("border: 1px solid #747b82;")
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Αποθήκευση")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Άκυρο")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.base.currentIndexChanged.connect(lambda *_: self._refresh())
        if not self._color:
            self._color_of_base()
        self._refresh()

    def _color_of_base(self):
        from archforge.rendering.materials import MATERIAL_PRESETS
        self._color = MATERIAL_PRESETS[self.base.currentData()]["color"]
        self._refresh()

    def _pick_color(self):
        color = QColorDialog.getColor(QColor(self._color or "#ffffff"), self, "Χρώμα υλικού")
        if color.isValid():
            self._color = color.name()
            self._refresh()

    def set_color(self, hex_color):        # tests / scripted use
        self._color = um.normalise_color(hex_color) or self._color
        self._refresh()

    def spec(self) -> dict:
        return um.build_spec(self.name.text(), self._color, self.base.currentData(),
                             self.category.currentText(), self.code.text(), self.supplier.text())

    def _refresh(self):
        from archforge.ui.pattern_swatch import material_swatch
        self.color_button.setText(f"Επιλογή χρώματος…  {self._color}")
        self.color_button.setStyleSheet(
            f"QPushButton {{ border-left: 22px solid {self._color}; padding: 4px 8px; }}")
        image = material_swatch("", self.preview.width(), self.preview.height(), spec=self.spec())
        self.preview.setPixmap(QPixmap.fromImage(image))

    def _accept(self):
        if not self.name.text().strip() and not self.code.text().strip():
            QMessageBox.information(self, "Νέο υλικό", "Γράψε ένα όνομα ή έναν κωδικό.")
            return
        self.material_id = um.save_material(self.material_id, self.spec())
        self.accept()


# ------------------------------------------------------------------ CSV ---

def import_codes(parent, path=None, exec_dialog=True):
    """«Εισαγωγή κωδικών από αρχείο…». Returns the number imported (0 = cancelled)."""
    if path is None:
        path, _ = QFileDialog.getOpenFileName(
            parent, "Εισαγωγή κωδικών από αρχείο", "",
            "Λίστα κωδικών (*.csv *.txt);;Όλα τα αρχεία (*)")
        if not path:
            return 0
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as exc:
        QMessageBox.warning(parent, "Εισαγωγή κωδικών", f"Δεν ανοίγει το αρχείο:\n{exc}")
        return 0
    dialog = CodeImportDialog(parent, data)
    if exec_dialog and dialog.exec() != QDialog.DialogCode.Accepted:
        return 0
    return dialog.commit()


class CodeImportDialog(QDialog):
    """Preview: how many codes, which rows are skipped and why, base look for all."""

    def __init__(self, parent, data: bytes):
        super().__init__(parent)
        self.data = data
        self.setWindowTitle("Εισαγωγή κωδικών από αρχείο")
        self.resize(560, 520)
        layout = QVBoxLayout(self)
        help_text = QLabel("Στήλες: <b>κωδικός ; όνομα ; χρώμα</b> (#rrggbb, προαιρετικό) "
                           "<b>; κατηγορία ; προμηθευτής</b> (προαιρετικά). "
                           "Δεκτά: διαχωριστικό «;» ή «,», αρχείο από Excel (ελληνικά Windows) ή UTF-8.")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)
        form = QFormLayout()
        layout.addLayout(form)
        self.base = _base_combo(self, um.DEFAULT_BASE)
        form.addRow("Βασική εμφάνιση", self.base)
        self.category = QComboBox(self)
        self.category.setEditable(True)
        for name in (um.DEFAULT_CATEGORY,) + tuple(material_categories()):
            self.category.addItem(name)
        self.category.setCurrentText("Μελαμίνες")
        form.addRow("Κατηγορία (όπου λείπει)", self.category)
        self.supplier = QLineEdit(self)
        self.supplier.setPlaceholderText("προαιρετικό — όπου λείπει από το αρχείο")
        form.addRow("Προμηθευτής", self.supplier)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.rows = QListWidget(self)
        self.rows.setIconSize(QSize(24, 24))
        layout.addWidget(self.rows, 2)
        self.skipped_label = QLabel("Γραμμές που παραλείπονται:", self)
        layout.addWidget(self.skipped_label)
        self.skipped = QListWidget(self)
        layout.addWidget(self.skipped, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Άκυρο")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for signal in (self.base.currentIndexChanged, self.category.currentTextChanged, self.supplier.textChanged):
            signal.connect(lambda *_: self.refresh())
        self.refresh()

    def parsed(self):
        return um.parse_csv(self.data, self.base.currentData(), self.category.currentText(), self.supplier.text())

    def refresh(self):
        from archforge.ui.pattern_swatch import material_swatch
        result = self.parsed()
        self.result = result
        self.rows.clear()
        updated = 0
        for material_id, spec in result["rows"]:
            again = material_id in um.user_materials()
            updated += again
            icon = QPixmap.fromImage(material_swatch("", 24, 24, spec=spec))
            text = um.label(spec["name"], spec["code"], spec["supplier"]) + f"  · {spec['category']}"
            item = QListWidgetItem(icon, text + ("  (ενημέρωση)" if again else ""))
            self.rows.addItem(item)
        self.skipped.clear()
        for line, reason in result["skipped"]:
            self.skipped.addItem(f"γραμμή {line}: {reason}")
        self.skipped.setVisible(bool(result["skipped"]))
        self.skipped_label.setVisible(bool(result["skipped"]))
        sep = {";": "«;»", ",": "«,»", "\t": "tab"}[result["separator"]]
        n = len(result["rows"])
        self.summary.setText(
            f"<b>{n} κωδικοί</b> για εισαγωγή" + (f" ({updated} υπάρχουν ήδη και ενημερώνονται)" if updated else "")
            + f" · παραλείπονται {len(result['skipped'])} γραμμές · διαχωριστικό {sep}")
        self.ok.setText(f"Εισαγωγή {n}")
        self.ok.setEnabled(n > 0)

    def commit(self) -> int:
        rows = self.result["rows"]
        um.save_many(dict(rows))
        return len(rows)


# ---------------------------------------------------- Properties panel ---

def material_rows(doc, entity):
    """``[(label, text)]``: each finish the element shows, with its code."""
    from archforge.rendering.materials import material_name
    out = []
    names = _role_names(entity)
    for role, material_id in um.assignments(doc, entity):
        code = um.code_for(entity, role, material_id, doc)
        where = "Υλικό" if not role else f"Υλικό · {names.get(role, role)}"
        out.append((where, um.label(material_name(material_id, doc), code["code"], code["supplier"])))
    return out


def _role_names(entity):
    if entity.kind == "wall":
        return {"exterior": "πλευρά Α", "interior": "πλευρά Β"}
    try:
        if entity.kind == "cabinet":
            from archforge.kitchen.cabinets import ROLE_NAMES
            return {k: v.lower() for k, v in ROLE_NAMES.items()}
        if entity.kind in ("door", "window"):
            from archforge.architecture.joinery import ROLE_NAMES
            return {k: v.lower() for k, v in ROLE_NAMES.items()}
    except Exception:
        pass
    return {}


def add_material_rows(window, form, entity):
    for where, text in material_rows(window.doc, entity):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setToolTip("Αλλαγή υλικού ή κωδικού: δεξί κλικ → Υλικά")
        form.addRow(where, label)
