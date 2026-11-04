"""One wall-type/layers editor for the Wall menu and an existing wall's Properties.

All materials come from construction.building_materials, all edits go through
architecture.wall_assemblies and the window's CommandStack.  Built-in types
remain immutable: customization creates a project type with one undo step.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMenu, QMessageBox,
                               QPushButton, QScrollArea, QToolButton, QVBoxLayout, QWidget)

from archforge.architecture import wall_assemblies as wa
from archforge.architecture.wall_types import is_project_type, label as type_label, wall_types
from archforge.construction.building_materials import MATERIALS, ROLES, by_category


class WallDetailsDialog(QDialog):
    """Edit the next wall's type, or just one already placed wall.

    Rows are staged until Save.  No structural/thermal values are invented:
    a newly chosen material has **zero** thickness until the human enters it.
    """

    def __init__(self, window, wall_type="generic", wall_id=None):
        super().__init__(window)
        self.window, self.doc = window, window.doc
        self.wall_id = str(wall_id) if wall_id is not None else None
        self.result_key = None
        self._layer_widgets = []
        self.setWindowTitle("Λεπτομέρειες τοίχου — τύπος και στρώσεις")
        self.setMinimumWidth(900)
        main = QVBoxLayout(self)
        form = QFormLayout()
        main.addLayout(form)

        self.type_combo = QComboBox(self)
        self.type_combo.setObjectName("wallDetailsType")
        for key, (name, _layers) in wall_types(self.doc).items():
            self.type_combo.addItem(name, key)
        i = self.type_combo.findData(str(wall_type))
        self.type_combo.setCurrentIndex(max(0, i))
        form.addRow("Τύπος τοίχου", self.type_combo)

        self.name_edit = QLineEdit(self)
        self.name_edit.setObjectName("wallDetailsName")
        form.addRow("Όνομα σύνθεσης", self.name_edit)

        self.context = QLabel(self)
        self.context.setWordWrap(True)
        form.addRow("Ισχύς αλλαγής", self.context)
        self.scope_box = QCheckBox("Αλλαγή σύνθεσης για όλους τους τοίχους αυτού του τύπου", self)
        self.scope_box.setObjectName("wallDetailsAllOfType")
        self.scope_box.setChecked(False)  # a selected wall never changes its neighbours by surprise
        form.addRow("", self.scope_box)

        main.addWidget(QLabel("Στρώσεις από την εξωτερική προς την εσωτερική παρειά"))
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumHeight(230)
        host = QWidget(scroll)
        self.rows_layout = QVBoxLayout(host)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(host)
        main.addWidget(scroll)

        additions = QHBoxLayout()
        self.add_outside = self._material_button("+ Στρώση εξωτερικά", "outside")
        self.add_inside = self._material_button("+ Στρώση εσωτερικά", "inside")
        additions.addWidget(self.add_outside)
        additions.addWidget(self.add_inside)
        main.addLayout(additions)

        self.total_label = QLabel(self)
        self.total_label.setObjectName("wallDetailsTotal")
        main.addWidget(self.total_label)
        self.note = QLabel(self)
        self.note.setWordWrap(True)
        main.addWidget(self.note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Αποθήκευση")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Ακύρωση")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main.addWidget(buttons)

        self.type_combo.currentIndexChanged.connect(self._type_changed)
        self._type_changed()

    def available_material_ids(self):
        return tuple(MATERIALS)

    def _material_button(self, title, side):
        button = QToolButton(self)
        button.setText(title)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(button)
        for category, materials in by_category().items():
            group = menu.addMenu(category)
            for material in materials:
                action = group.addAction(material.name)
                action.setData(material.id)
                action.triggered.connect(lambda _=False, mid=material.id, pos=side: self.add_layer(mid, pos))
        button.setMenu(menu)
        return button

    def _type_changed(self, *_):
        key = str(self.type_combo.currentData() or "generic")
        self.name_edit.setText(type_label(key, self.doc))
        self._set_rows(wa.layer_specs(self.doc, key))
        if self.wall_id is None:
            n = len(wa.walls_of_type(self.doc, key))
            self.context.setText((f"Τύπος έργου: επεξεργασία κοινής σύνθεσης για {n} τοίχους."
                                  if is_project_type(key) else
                                  "Έτοιμος τύπος: η προσαρμογή δημιουργεί νέα σύνθεση του έργου, χωρίς αλλαγή άλλων τοίχων."))
        else:
            self.context.setText("Η αλλαγή θα εφαρμοστεί μόνο σε αυτόν τον τοίχο, εκτός αν επιλέξεις ρητά όλους.")
        old = str(self.doc.get(self.wall_id).params.get("wall_type", "generic")) if self.wall_id else None
        self.scope_box.setVisible(bool(self.wall_id and old == key and is_project_type(key)))
        if self.scope_box.isVisible():
            n = len(wa.walls_of_type(self.doc, key))
            self.scope_box.setText(f"Εφαρμογή της αλλαγής και στους {n} τοίχους αυτού του τύπου")
        if key.startswith("isotex_"):
            self.note.setText("Isotex: οι βασικές στρώσεις είναι του συγκεκριμένου τεμαχίου. "
                              "Για τελείωμα διάλεξε Σοβά ή Γυψοσανίδα από τη βιβλιοθήκη και όρισε το πάχος. "
                              "Τα δημοσιευμένα τεχνικά στοιχεία χρειάζονται έλεγχο με το φύλλο προϊόντος.")
        elif key == "generic":
            self.note.setText("Γενικός τοίχος: δεν έχει ορισμένη κατασκευαστική σύνθεση. "
                              "Επίλεξε τύπο ή πρόσθεσε υλικά και δώσε τα πραγματικά πάχη τους.")
        else:
            self.note.setText("Το συνολικό πάχος ακολουθεί το άθροισμα των στρώσεων. "
                              "Οι τιμές λ των υλικών είναι ενδεικτικές, όχι επαληθευμένη ενεργειακή μελέτη.")

    def _set_rows(self, specs):
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._layer_widgets = []
        for index, spec in enumerate(specs):
            row = QWidget(self)
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 2, 0, 2)
            line.addWidget(QLabel(f"{index + 1}."))
            mat = QComboBox(row)
            for m in MATERIALS.values():
                mat.addItem(f"{m.name} ({m.category})", m.id)
                mat.setItemData(mat.count() - 1, f"{m.name} — {m.category}", Qt.ItemDataRole.ToolTipRole)
            mat.setCurrentIndex(max(0, mat.findData(spec["material"])))
            mat.setMinimumWidth(245)
            line.addWidget(mat, 3)
            role = QComboBox(row)
            for k, name in ROLES.items():
                role.addItem(name, k)
            role.setCurrentIndex(max(0, role.findData(spec.get("role") or MATERIALS[spec["material"]].role)))
            line.addWidget(role, 2)
            thick = QDoubleSpinBox(row)
            thick.setObjectName("wallLayerThickness")
            thick.setDecimals(2)
            thick.setRange(0.0, 100000.0)  # no arbitrary 2 m UI veto; model validation remains authoritative
            thick.setSingleStep(0.5)
            thick.setSuffix(" cm")
            thick.setValue(float(spec["thickness"]) * 100)
            thick.valueChanged.connect(self._refresh_total)
            line.addWidget(thick)
            mat.currentIndexChanged.connect(lambda _i, m=mat, r=role: r.setCurrentIndex(
                max(0, r.findData(MATERIALS[m.currentData()].role))))
            up = QPushButton("↑", row)
            down = QPushButton("↓", row)
            remove = QPushButton("−", row)
            up.setToolTip("Μετακίνηση στρώσης προς τα έξω")
            down.setToolTip("Μετακίνηση στρώσης προς τα μέσα")
            remove.setToolTip("Αφαίρεση στρώσης")
            up.setEnabled(index > 0)
            down.setEnabled(index + 1 < len(specs))
            up.clicked.connect(lambda _=False, i=index: self.move_layer(i, -1))
            down.clicked.connect(lambda _=False, i=index: self.move_layer(i, 1))
            remove.clicked.connect(lambda _=False, i=index: self.remove_layer(i))
            for b in (up, down, remove):
                b.setFixedWidth(32)
                line.addWidget(b)
            self.rows_layout.addWidget(row)
            self._layer_widgets.append({"material": mat, "role": role, "thickness": thick})
            mat.currentIndexChanged.connect(self._refresh_total)   # another material = another λ → U again
        self._refresh_total()

    def layer_specs(self):
        return [{"material": r["material"].currentData(), "role": r["role"].currentData(),
                 "thickness": round(r["thickness"].value() / 100.0, 4)} for r in self._layer_widgets]

    def _refresh_total(self, *_):
        specs = self.layer_specs()
        if not specs:
            self.total_label.setText('Δεν έχει οριστεί σύνθεση· το γεωμετρικό πάχος του γενικού τοίχου διατηρείται.')
            return
        total = sum(r["thickness"] for r in specs)
        pending = any(r["thickness"] <= 0 for r in specs)
        self.total_label.setText(f"Συνολικό πάχος στρώσεων: {total * 100:.2f} cm" +
                                 (" · Συμπλήρωσε το πάχος της νέας στρώσης" if pending else "") + self.u_text(specs))

    def u_text(self, specs=None):
        """« · U 0,48 W/m²K από τα λ των στρώσεων» — live, as layers / materials / thicknesses change (κριτική v5:
        «U ζωντανά μέσα στο +/−»). The same formula as the program (wall_types.indicative_u, EN ISO 6946 for walls)."""
        from archforge.architecture.wall_types import RSE, RSI
        from archforge.construction.building_materials import material
        specs = self.layer_specs() if specs is None else specs
        r, unknown, unverified = RSI + RSE, [], False
        for spec in specs:
            if spec["thickness"] <= 0:
                continue
            m = material(spec["material"], self.doc)
            lam = getattr(m, "conductivity", None)
            if not lam:
                unknown.append(m.name)
                continue
            r += spec["thickness"] / float(lam)
            unverified = unverified or getattr(m, "conductivity_status", "") == "UNVERIFIED"
        if unknown:
            return f" · U: λείπει το λ ({', '.join(unknown)})"
        if r <= RSI + RSE:
            return ""
        key = str(self.type_combo.currentData() or "")
        note = " · Isotex: το πρόγραμμα κρατά το U του φυλλαδίου όσο ο πυρήνας μένει ίδιος" if key.startswith("isotex_") else ""
        return (f" · U {1.0 / r:.2f} W/m²K".replace(".", ",") +
                (" (λ τυπικά, προς επαλήθευση)" if unverified else " (λ από φύλλο προϊόντος)") + note)

    def add_layer(self, material_id, side="inside"):
        if material_id not in MATERIALS:
            raise ValueError("Άγνωστο υλικό δόμησης")
        rows = self.layer_specs()
        spec = {"material": material_id, "thickness": 0.0, "role": MATERIALS[material_id].role}
        index = 0 if side == "outside" else len(rows)
        rows.insert(index, spec)
        self._set_rows(rows)
        self._layer_widgets[index]["thickness"].setFocus()
        return self._layer_widgets[index]

    def move_layer(self, index, direction):
        rows = self.layer_specs()
        target = index + direction
        if 0 <= index < len(rows) and 0 <= target < len(rows):
            rows[index], rows[target] = rows[target], rows[index]
            self._set_rows(rows)

    def remove_layer(self, index):
        rows = self.layer_specs()
        if 0 <= index < len(rows):
            del rows[index]
            self._set_rows(rows)

    def accept(self):
        from archforge.architecture.curved_wall import spread_command
        from archforge.core.commands import CompositeCommand
        key = str(self.type_combo.currentData() or "generic")
        name = self.name_edit.text().strip()
        rows = self.layer_specs()
        original = wa.layer_specs(self.doc, key)
        original_name = type_label(key, self.doc)
        changed = rows != original or name != original_name
        if changed and not rows:
            QMessageBox.warning(self, "Σύνθεση τοίχου", "Διάλεξε τουλάχιστον μία στρώση με θετικό πάχος.")
            return
        try:
            if changed:
                rows = wa.clean_layers(rows)
            if self.wall_id is None:
                if changed and is_project_type(key):
                    self.window.stack.execute(wa.edit_type_command(self.doc, key, name=name, rows=rows))
                elif changed:
                    title = name if name != original_name else f"{name} — προσαρμογή"
                    base = wa.validated_base_type(self.doc, key)
                    key, cmd = wa.new_type_command(self.doc, title, rows, base_type=base)
                    self.window.stack.execute(cmd)
                self.window.plan_view.controller.wall_choice = None if key == "generic" else key
                self.window._set_active_tool("wall")
            else:
                old = self.doc.get(self.wall_id).params.get("wall_type", "generic")
                if changed and self.scope_box.isVisible() and self.scope_box.isChecked() and old == key:
                    self.window.stack.execute(wa.edit_type_command(self.doc, key, name=name, rows=rows))
                elif changed:
                    title = name if name != original_name else f"{name} — {self.doc.get(self.wall_id).name or 'τοίχος'}"
                    base = wa.validated_base_type(self.doc, key)
                    key, create = wa.new_type_command(self.doc, title, rows, base_type=base)
                    edit = spread_command(self.doc, self.wall_id, {"wall_type": key,
                                                                     "thickness": sum(r["thickness"] for r in rows)})
                    self.window.stack.execute(CompositeCommand([create, edit], label="Σύνθεση επιλεγμένου τοίχου"))
                elif old != key:
                    changes = {"wall_type": key}
                    if original:
                        changes["thickness"] = sum(r["thickness"] for r in original)
                    self.window.stack.execute(spread_command(self.doc, self.wall_id, changes))
            self.result_key = key
            self.window._redraw_views(all_views=True)
            self.window.refresh_inspector()
        except (ValueError, KeyError) as exc:
            QMessageBox.warning(self, "Μη έγκυρη σύνθεση", str(exc))
            return
        super().accept()
