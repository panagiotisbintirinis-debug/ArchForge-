"""Object Modifier: one panel for editing a placed library object.

Linked to the Inspector (it opens from there and every change refreshes it).
Size and placement, the palette material of each part, and the object's
sculpt modifiers are all edited through the shared commands, so every action
is undoable and an equivalent AI edit would converge on the same Document
state.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget,
)

from archforge.core.commands import UpdateEntity
from archforge.core.modifier_commands import RemoveSurfaceModifier, UpdateSurfaceModifier
from archforge.library.assets import load_asset
from archforge.library.objects import SIZE_KEYS, asset_parts, resized
from archforge.rendering.materials import MATERIAL_PRESETS


class ObjectModifierDialog(QDialog):
    def __init__(self, window, entity_id):
        super().__init__(window)
        self.window = window
        self.entity_id = str(entity_id)
        self.setWindowTitle("Object Modifier")
        self.resize(430, 640)
        self._building = False
        layout = QVBoxLayout(self)
        self.header = QLabel()
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        size_box = QGroupBox("Διαστάσεις & θέση")
        form = QFormLayout(size_box)
        self.size_spins = {}
        for key, label in zip(SIZE_KEYS, ("Πλάτος (cm)", "Βάθος (cm)", "Ύψος (cm)")):
            spin = QDoubleSpinBox()
            spin.setRange(0.1, 100000.0)
            spin.setDecimals(1)
            spin.editingFinished.connect(lambda k=key, w=spin: self.set_size(k, w.value()))
            form.addRow(label, spin)
            self.size_spins[key] = spin
        self.lock = QCheckBox("Κλείδωμα αναλογιών")
        self.lock.toggled.connect(lambda on: None if self._building else self.set_lock(on))
        form.addRow(self.lock)
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-360.0, 360.0)
        self.rotation.setDecimals(1)
        self.rotation.editingFinished.connect(lambda: self.set_rotation(self.rotation.value()))
        form.addRow("Περιστροφή (°)", self.rotation)
        self.elevation = QDoubleSpinBox()
        self.elevation.setRange(-100000.0, 100000.0)
        self.elevation.setDecimals(1)
        self.elevation.editingFinished.connect(lambda: self.set_elevation(self.elevation.value()))
        form.addRow("Υψόμετρο βάσης (cm)", self.elevation)
        reset = QPushButton("Αρχικό μέγεθος")
        reset.clicked.connect(self.reset_size)
        form.addRow(reset)
        layout.addWidget(size_box)

        mat_box = QGroupBox("Υλικά / χρώματα (παλέτα)")
        mv = QVBoxLayout(mat_box)
        self.parts = QListWidget()
        self.parts.itemDoubleClicked.connect(lambda item: self.choose_material(item.data(Qt.ItemDataRole.UserRole)))
        mv.addWidget(self.parts)
        row = QHBoxLayout()
        for text, run in (("Αλλαγή υλικού…", lambda: self.choose_material(self._current_part())),
                          ("Όλο το αντικείμενο…", lambda: self.choose_material(None)),
                          ("Αρχικά χρώματα", self.reset_materials)):
            b = QPushButton(text)
            b.clicked.connect(run)
            row.addWidget(b)
        mv.addLayout(row)
        layout.addWidget(mat_box)

        sculpt_box = QGroupBox("Sculpt (μη καταστροφικό)")
        sv = QVBoxLayout(sculpt_box)
        self.modifiers = QListWidget()
        self.modifiers.itemChanged.connect(self._modifier_toggled)
        sv.addWidget(self.modifiers)
        row = QHBoxLayout()
        start = QPushButton("Sculpt 3D…")
        start.setToolTip("Ενεργοποιεί το Sculpt στο 3D: σύρετε πάνω στο αντικείμενο")
        start.clicked.connect(self.start_sculpt)
        delete = QPushButton("Διαγραφή επιλεγμένου")
        delete.clicked.connect(lambda: self.remove_modifier(self._current_modifier()))
        row.addWidget(start)
        row.addWidget(delete)
        sv.addLayout(row)
        layout.addWidget(sculpt_box)
        self.refresh()

    # ---------------------------------------------------------------- state
    @property
    def entity(self):
        return self.window.doc.get(self.entity_id)

    def _execute(self, command):
        self.window.stack.execute(command)
        self.window.doc.select([self.entity_id])
        self.window._redraw_views(all_views=True)
        self.window.refresh_inspector()
        self.refresh()

    def refresh(self):
        if self.entity_id not in self.window.doc.entities:
            self.close()
            return
        self._building = True
        p = self.entity.params
        asset = load_asset(str(p["asset"]))
        prov = (asset or {}).get("provenance", {})
        native = (asset or {}).get("size")
        text = f"<b>{self.entity.name or 'Αντικείμενο'}</b>"
        if native:
            text += f"<br>αρχικό: {native[0] * 100:.0f}×{native[1] * 100:.0f}×{native[2] * 100:.0f} cm"
        if prov:
            text += f"<br>πηγή: {prov.get('source', '?')}"
            if prov.get("attribution"):
                text += f" — {prov['attribution']}"
        if asset is None:
            text += "<br><i>το αρχείο του αντικειμένου λείπει από αυτόν τον υπολογιστή (εμφανίζεται κουτί)</i>"
        self.header.setText(text)
        for key, spin in self.size_spins.items():
            spin.setValue(float(p[key]) * 100.0)
        self.lock.setChecked(bool(p.get("uniform", 1.0)))
        self.rotation.setValue(float(p.get("rotation", 0.0)))
        self.elevation.setValue(float(p["z"]) * 100.0)
        self.parts.clear()
        overrides = p.get("surface_materials") or {}
        whole = p.get("material_id")
        for k, (role, color, name) in enumerate(asset_parts(p), 1):
            mid = overrides.get(role) or whole
            finish = MATERIAL_PRESETS.get(mid, {}).get("name", "αρχικό χρώμα")
            item = QListWidgetItem(f"Τμήμα {k}" + (f" — {name}" if name else "") + f":  {finish}")
            item.setData(Qt.ItemDataRole.UserRole, role)
            item.setBackground(Qt.GlobalColor.white)
            item.setForeground(Qt.GlobalColor.black)
            item.setToolTip(color)
            self.parts.addItem(item)
        self.modifiers.clear()
        for mid, mod in self.window.doc.surface_modifiers.items():
            if mod.target.owner_id != self.entity_id:
                continue
            amount = float(mod.params.get("amount", 0.0)) * 100.0
            item = QListWidgetItem(f"{mod.name or mod.operation}  ({mod.operation}, {amount:.1f} cm)")
            item.setData(Qt.ItemDataRole.UserRole, mid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if mod.enabled else Qt.CheckState.Unchecked)
            self.modifiers.addItem(item)
        self._building = False

    def _current_part(self):
        item = self.parts.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _current_modifier(self):
        item = self.modifiers.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    # -------------------------------------------------------------- actions
    def set_size(self, key, centimetres):
        if self._building:
            return
        p = self.entity.params
        if abs(float(p[key]) * 100.0 - float(centimetres)) < 1e-6:
            return
        self._execute(UpdateEntity(self.entity_id, resized(p, key, float(centimetres) / 100.0)))

    def set_lock(self, on):
        self._execute(UpdateEntity(self.entity_id, {"uniform": 1.0 if on else 0.0}))

    def set_rotation(self, degrees):
        if self._building or abs(float(self.entity.params.get("rotation", 0.0)) - degrees) < 1e-9:
            return
        self._execute(UpdateEntity(self.entity_id, {"rotation": float(degrees) % 360.0}))

    def set_elevation(self, centimetres):
        if self._building or abs(float(self.entity.params["z"]) * 100.0 - centimetres) < 1e-6:
            return
        self._execute(UpdateEntity(self.entity_id, {"z": float(centimetres) / 100.0}))

    def reset_size(self):
        asset = load_asset(str(self.entity.params["asset"]))
        if asset is None:
            return
        self._execute(UpdateEntity(self.entity_id, dict(zip(SIZE_KEYS, (float(v) for v in asset["size"])))))

    def choose_material(self, role):
        """Open the shared palette dialog for one part (or the whole object)."""
        self.window._open_materials(self.entity_id, part_role=role)
        self.refresh()

    def set_part_material(self, role, material_id):
        if material_id not in MATERIAL_PRESETS:
            raise KeyError(material_id)
        if role is None:
            changes = {"material_id": material_id, "surface_materials": {}}
        else:
            surface_map = dict(self.entity.params.get("surface_materials") or {})
            surface_map[role] = material_id
            changes = {"surface_materials": surface_map}
        self._execute(UpdateEntity(self.entity_id, changes))

    def reset_materials(self):
        self._execute(UpdateEntity(self.entity_id, {"material_id": "", "surface_materials": {}}))

    def _modifier_toggled(self, item):
        if self._building:
            return
        self.set_modifier_enabled(item.data(Qt.ItemDataRole.UserRole),
                                  item.checkState() == Qt.CheckState.Checked)

    def set_modifier_enabled(self, modifier_id, enabled):
        self._execute(UpdateSurfaceModifier(str(modifier_id), {"enabled": bool(enabled)}))

    def remove_modifier(self, modifier_id):
        if modifier_id:
            self._execute(RemoveSurfaceModifier(str(modifier_id)))

    def start_sculpt(self):
        self.window.doc.select([self.entity_id])
        if hasattr(self.window, "_show_3d_view"):
            self.window._show_3d_view()
        action = getattr(self.window, "sculpt_action", None)
        if action is not None:
            action.setChecked(True)


class CabinetModifierDialog(QDialog):
    """Object Modifier for parametric cabinets and wardrobes.

    Size changes keep panel thicknesses and gaps; the number of doors follows
    the width unless the user sets it.  Finishes are per role (carcass,
    fronts, handles, plinth, worktop...) from the shared palette.  Front
    style, handle and mechanism are choices of the same entity (one undo).
    """

    def __init__(self, window, entity_id):
        from PySide6.QtWidgets import QComboBox, QSpinBox
        from archforge.kitchen.cabinets import BLIND_SIDES, FRONT_STYLES, HANDLE_NAMES, TYPES
        super().__init__(window)
        self.window = window
        self.entity_id = str(entity_id)
        self.setWindowTitle("Object Modifier — ντουλάπι")
        self.resize(420, 640)
        self._building = False
        layout = QVBoxLayout(self)
        self.header = QLabel()
        layout.addWidget(self.header)
        box = QGroupBox("Τύπος & διαστάσεις")
        form = QFormLayout(box)
        self.kind = QComboBox()
        for key, (name, _d) in TYPES.items():
            self.kind.addItem(name, key)
        self.kind.currentIndexChanged.connect(lambda _i: self.set_param("cabinet_type", self.kind.currentData()))
        form.addRow("Τύπος", self.kind)
        self.cm = {}
        for key, label in (("width", "Πλάτος (cm)"), ("depth", "Βάθος (cm)"), ("height", "Ύψος (cm)"),
                           ("plinth", "Πόδι/βάση (cm)"), ("z", "Υψόμετρο (cm)")):
            spin = QDoubleSpinBox()
            spin.setRange(0.0 if key in ("plinth", "z") else 10.0, 100000.0)
            spin.setDecimals(1)
            spin.editingFinished.connect(lambda k=key, w=spin: self.set_param(k, w.value() / 100.0))
            form.addRow(label, spin)
            self.cm[key] = spin
        self.counts = {}
        for key, label in (("doors", "Πόρτες"), ("drawers", "Συρτάρια"), ("shelves", "Ράφια")):
            spin = QSpinBox()
            spin.setRange(0, 20)
            spin.editingFinished.connect(lambda k=key, w=spin: self.set_param(k, w.value()))
            form.addRow(label, spin)
            self.counts[key] = spin
        self.rotation = QDoubleSpinBox()
        self.rotation.setRange(-360.0, 360.0)
        self.rotation.editingFinished.connect(lambda: self.set_param("rotation", self.rotation.value() % 360.0))
        form.addRow("Περιστροφή (°)", self.rotation)
        self.worktop = QCheckBox("Πάγκος εργασίας")
        self.worktop.toggled.connect(lambda on: self.set_param("worktop", 1.0 if on else 0.0))
        form.addRow(self.worktop)
        self.handle = QComboBox()
        for h, label in HANDLE_NAMES.items():
            self.handle.addItem(label, h)
        self.handle.currentIndexChanged.connect(lambda _i: self.set_param("handle", self.handle.currentData()))
        form.addRow("Χερούλι", self.handle)
        self.front_style = QComboBox()
        for key, label in FRONT_STYLES.items():
            self.front_style.addItem(label, key)
        self.front_style.currentIndexChanged.connect(lambda _i: self.set_param("front_style", self.front_style.currentData()))
        form.addRow("Πρόσοψη", self.front_style)
        self.mechanism = QComboBox()          # filled per type in refresh()
        self.mechanism.currentIndexChanged.connect(lambda _i: self.set_param("mechanism", self.mechanism.currentData()))
        form.addRow("Μηχανισμός", self.mechanism)
        self.blind_side = QComboBox()
        for key, label in BLIND_SIDES.items():
            self.blind_side.addItem(label, key)
        self.blind_side.currentIndexChanged.connect(lambda _i: self.set_param("blind_side", self.blind_side.currentData()))
        form.addRow("Τυφλό τμήμα", self.blind_side)
        layout.addWidget(box)
        mat = QGroupBox("Υλικά (παλέτα)")
        mv = QVBoxLayout(mat)
        self.parts = QListWidget()
        self.parts.itemDoubleClicked.connect(lambda item: self.choose_material(item.data(Qt.ItemDataRole.UserRole)))
        mv.addWidget(self.parts)
        row = QHBoxLayout()
        for text, run in (("Αλλαγή υλικού…", lambda: self.choose_material(self._current_role())),
                          ("Όλο το ντουλάπι…", lambda: self.choose_material(None)),
                          ("Αρχικά", self.reset_materials)):
            b = QPushButton(text)
            b.clicked.connect(run)
            row.addWidget(b)
        mv.addLayout(row)
        layout.addWidget(mat)
        self.refresh()

    @property
    def entity(self):
        return self.window.doc.get(self.entity_id)

    def _execute(self, command):
        self.window.stack.execute(command)
        self.window.doc.select([self.entity_id])
        self.window._redraw_views(all_views=True)
        self.window.refresh_inspector()
        self.refresh()

    def refresh(self):
        from archforge.kitchen.cabinets import MECHANISMS, ROLE_NAMES, TYPES, cabinet_roles, mechanisms_for
        if self.entity_id not in self.window.doc.entities:
            self.close()
            return
        self._building = True
        p = self.entity.params
        self.header.setText(f"<b>{self.entity.name or TYPES[p['cabinet_type']][0]}</b>")
        self.kind.setCurrentIndex(self.kind.findData(p["cabinet_type"]))
        for key, spin in self.cm.items():
            spin.setValue(float(p.get(key, 0.0)) * 100.0)
        for key, spin in self.counts.items():
            spin.setValue(int(p.get(key, 0)))
        self.rotation.setValue(float(p.get("rotation", 0.0)))
        self.worktop.setChecked(bool(p.get("worktop", 0.0)))
        self.handle.setCurrentIndex(self.handle.findData(p.get("handle", "bar")))
        self.front_style.setCurrentIndex(self.front_style.findData(p.get("front_style", "flat")))
        self.mechanism.clear()
        for key in mechanisms_for(p["cabinet_type"]):
            self.mechanism.addItem(MECHANISMS[key][0], key)
        self.mechanism.setCurrentIndex(max(0, self.mechanism.findData(p.get("mechanism", "none"))))
        self.blind_side.setCurrentIndex(self.blind_side.findData(p.get("blind_side", "left")))
        self.blind_side.setEnabled(p["cabinet_type"] == "corner_blind")
        self.parts.clear()
        overrides = p.get("surface_materials") or {}
        for role in cabinet_roles(p):
            mid = overrides.get(role) or p.get("material_id")
            finish = MATERIAL_PRESETS.get(mid, {}).get("name", "αρχικό")
            item = QListWidgetItem(f"{ROLE_NAMES.get(role, role)}:  {finish}")
            item.setData(Qt.ItemDataRole.UserRole, role)
            self.parts.addItem(item)
        self._building = False

    def _current_role(self):
        item = self.parts.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def set_param(self, key, value):
        """Change one parameter; width also re-derives the door count."""
        if self._building:
            return
        from archforge.kitchen.cabinets import DEFAULT_MECHANISM, TYPES, auto_doors, mechanisms_for
        p = self.entity.params
        if p.get(key, {"front_style": "flat", "mechanism": "none", "blind_side": "left"}.get(key)) == value:
            return
        changes = {key: value}
        if key == "width" and int(p.get("doors", 0)) == auto_doors(p["cabinet_type"], float(p["width"])):
            changes["doors"] = auto_doors(p["cabinet_type"], float(value)) if int(p.get("doors", 0)) else 0
        if key == "cabinet_type":
            name, d = TYPES[value]
            changes.update({k: d[k] for k in ("depth", "height", "plinth", "drawers", "shelves", "worktop")})
            changes["doors"] = auto_doors(value, float(p["width"])) if d["doors"] else 0
            changes["z"] = float(p["z"]) + (d["z"] - TYPES[p["cabinet_type"]][1]["z"])
            if value in ("corner", "corner_blind") or p["cabinet_type"] in ("corner", "corner_blind"):
                changes["width"] = d["width"]           # corner units have their own plan size
                changes["doors"] = auto_doors(value, d["width"]) if d["doors"] else 0
            if p.get("mechanism", "none") not in mechanisms_for(value) or value in DEFAULT_MECHANISM:
                changes["mechanism"] = DEFAULT_MECHANISM.get(value, "none")
            if value == "corner_blind":
                changes["blind_side"] = p.get("blind_side", "left")
        self._execute(UpdateEntity(self.entity_id, changes))

    def choose_material(self, role):
        self.window._open_materials(self.entity_id, part_role=role)
        self.refresh()

    def set_role_material(self, role, material_id):
        if material_id not in MATERIAL_PRESETS:
            raise KeyError(material_id)
        if role is None:
            changes = {"material_id": material_id, "surface_materials": {}}
        else:
            surface_map = dict(self.entity.params.get("surface_materials") or {})
            surface_map[role] = material_id
            changes = {"surface_materials": surface_map}
        self._execute(UpdateEntity(self.entity_id, changes))

    def reset_materials(self):
        self._execute(UpdateEntity(self.entity_id, {"material_id": "", "surface_materials": {}}))


def add_cabinet_choices(window, form, entity_id):
    """Front style, handle and mechanism of a cabinet in the Inspector (Ιδιότητες)."""
    from PySide6.QtWidgets import QComboBox
    from archforge.kitchen.cabinets import FRONT_STYLES, HANDLE_NAMES, MECHANISMS, mechanisms_for
    p = window.doc.get(entity_id).params
    choices = (("front_style", "Πρόσοψη", FRONT_STYLES, "flat"),
               ("handle", "Χερούλι", HANDLE_NAMES, "bar"),
               ("mechanism", "Μηχανισμός", {k: MECHANISMS[k][0] for k in mechanisms_for(p["cabinet_type"])}, "none"))
    combos = {}
    for key, label, options, default in choices:
        combo = QComboBox()
        for value, name in options.items():
            combo.addItem(name, value)
        combo.setCurrentIndex(max(0, combo.findData(p.get(key, default))))
        combo.currentIndexChanged.connect(
            lambda _i, k=key, w=combo: window._set_entity_choice(entity_id, k, w.currentData()))
        form.addRow(label, combo)
        combos[key] = combo
    return combos
