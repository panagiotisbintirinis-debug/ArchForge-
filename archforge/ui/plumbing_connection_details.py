"""Editable plumbing connection/manifold assembly details in the report tab."""
from __future__ import annotations

import copy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QHeaderView, QLineEdit, QMenu, QTreeWidget, QTreeWidgetItem,
)


def _new_tree():
    tree = QTreeWidget()
    tree.setHeaderLabels([
        "Σημείο / στοιχείο", "Assembly", "Εξάρτημα", "Ποσότητα", "Μονάδα",
        "Προϊόν", "Κατάσταση", "Πηγή",
    ])
    tree.setRootIsDecorated(True)
    tree.setAlternatingRowColors(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    tree.header().setStretchLastSection(True)
    tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    tree.setToolTip(
        "Δεξί κλικ σε σημείο ή συλλέκτη: όρισε assembly / πρόσθεσε εξάρτημα. "
        "Χωρίς επιλογή το ArchForge δεν μαντεύει βάνες ή ρακόρ."
    )
    return tree


def _assembly_meta_dialog(parent, assembly, title):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    form = QFormLayout(dialog)
    name = QLineEdit(str(assembly.get("name", "")))
    source_kind = QComboBox()
    for value, label in (
        ("professional_selection", "Επιλογή επαγγελματία"),
        ("manufacturer_data", "Στοιχεία κατασκευαστή"),
        ("project_specification", "Προδιαγραφή έργου"),
    ):
        source_kind.addItem(label, value)
    idx = source_kind.findData(str(assembly.get("source_kind", "professional_selection")))
    source_kind.setCurrentIndex(max(0, idx))

    status = QComboBox()
    for value in ("MODEL_SELECTED", "MANUFACTURER_DATA", "ENGINEER_REVIEW"):
        status.addItem(value, value)
    idx = status.findData(str(assembly.get("rule_status", "MODEL_SELECTED")))
    status.setCurrentIndex(max(0, idx))

    rule_source = QLineEdit(str(assembly.get("rule_source", "")))
    form.addRow("Ονομασία", name)
    form.addRow("Πηγή επιλογής", source_kind)
    form.addRow("Κατάσταση", status)
    form.addRow("Πηγή / datasheet", rule_source)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    out = copy.deepcopy(assembly)
    out["name"] = name.text().strip()
    out["source_kind"] = str(source_kind.currentData())
    out["rule_status"] = str(status.currentData())
    out["rule_source"] = rule_source.text().strip()
    out.setdefault("components", [])
    return out


def _component_dialog(parent):
    from archforge.mep.plumbing_accessories import ACCESSORY_TYPES

    dialog = QDialog(parent)
    dialog.setWindowTitle("Προσθήκη εξαρτήματος")
    form = QFormLayout(dialog)
    kind = QComboBox()
    for key, (label, _why) in sorted(ACCESSORY_TYPES.items(), key=lambda kv: kv[1][0]):
        kind.addItem(label, key)
    qty = QDoubleSpinBox(); qty.setRange(0.0, 9999.0); qty.setDecimals(3); qty.setValue(1.0)
    unit = QComboBox(); unit.addItem("τεμ.", "pcs"); unit.addItem("m", "m")
    manufacturer = QLineEdit(); product_ref = QLineEdit(); description = QLineEdit()
    form.addRow("Εξάρτημα", kind)
    form.addRow("Ποσότητα", qty)
    form.addRow("Μονάδα", unit)
    form.addRow("Κατασκευαστής", manufacturer)
    form.addRow("Κωδικός προϊόντος", product_ref)
    form.addRow("Περιγραφή override", description)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
    form.addRow(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    component = {
        "accessory_type": str(kind.currentData()),
        "quantity": float(qty.value()),
        "unit": str(unit.currentData()),
    }
    if manufacturer.text().strip(): component["manufacturer"] = manufacturer.text().strip()
    if product_ref.text().strip(): component["product_ref"] = product_ref.text().strip()
    if description.text().strip(): component["description"] = description.text().strip()
    return component


def _point_assembly(tab, point_id):
    point = tab.window.doc.get(point_id)
    return copy.deepcopy(point.params.get("connection_assembly") or {})


def _save_point_assembly(tab, point_id, assembly):
    from archforge.core.commands import UpdateEntity
    tab.window.stack.execute(UpdateEntity(point_id, {"connection_assembly": assembly}))
    tab.window._redraw_views(all_views=True)
    tab.refresh()


def _edit_point_assembly(tab, point_id):
    assembly = _point_assembly(tab, point_id)
    updated = _assembly_meta_dialog(tab, assembly, "Assembly σύνδεσης")
    if updated is not None:
        _save_point_assembly(tab, point_id, updated)


def _add_point_component(tab, point_id):
    point = tab.window.doc.get(point_id)
    assembly = _point_assembly(tab, point_id)
    if not assembly:
        assembly = {
            "name": f"Σύνδεση {point.name or point.params.get('point_type', '')}",
            "source_kind": "professional_selection",
            "rule_status": "MODEL_SELECTED",
            "rule_source": "",
            "components": [],
        }
    component = _component_dialog(tab)
    if component is None:
        return
    assembly.setdefault("components", []).append(component)
    _save_point_assembly(tab, point_id, assembly)


def _remove_point_component(tab, point_id, component_index):
    assembly = _point_assembly(tab, point_id)
    components = list(assembly.get("components") or [])
    if not (0 <= int(component_index) < len(components)):
        return
    components.pop(int(component_index)); assembly["components"] = components
    _save_point_assembly(tab, point_id, assembly)


def _manifold_assembly(tab, supply_id, manifold_key):
    supply = tab.window.doc.get(supply_id)
    store = supply.params.get("manifold_assemblies") or {}
    raw = store.get(manifold_key) or {}
    return copy.deepcopy(raw) if isinstance(raw, dict) else {}


def _save_manifold_assembly(tab, supply_id, manifold_key, assembly):
    from archforge.core.commands import UpdateEntity
    supply = tab.window.doc.get(supply_id)
    store = copy.deepcopy(supply.params.get("manifold_assemblies") or {})
    store[manifold_key] = assembly
    tab.window.stack.execute(UpdateEntity(supply_id, {"manifold_assemblies": store}))
    tab.window._redraw_views(all_views=True)
    tab.refresh()


def _edit_manifold_assembly(tab, supply_id, manifold_key):
    assembly = _manifold_assembly(tab, supply_id, manifold_key)
    updated = _assembly_meta_dialog(tab, assembly, "Assembly συλλέκτη")
    if updated is not None:
        _save_manifold_assembly(tab, supply_id, manifold_key, updated)


def _add_manifold_component(tab, supply_id, manifold_key):
    assembly = _manifold_assembly(tab, supply_id, manifold_key)
    if not assembly:
        assembly = {
            "name": "Assembly συλλέκτη",
            "source_kind": "professional_selection",
            "rule_status": "MODEL_SELECTED",
            "rule_source": "",
            "components": [],
        }
    component = _component_dialog(tab)
    if component is None:
        return
    assembly.setdefault("components", []).append(component)
    _save_manifold_assembly(tab, supply_id, manifold_key, assembly)


def _remove_manifold_component(tab, supply_id, manifold_key, component_index):
    assembly = _manifold_assembly(tab, supply_id, manifold_key)
    components = list(assembly.get("components") or [])
    if not (0 <= int(component_index) < len(components)):
        return
    components.pop(int(component_index)); assembly["components"] = components
    _save_manifold_assembly(tab, supply_id, manifold_key, assembly)


def _tree_menu(tab, pos):
    tree = tab.connection_details
    item = tree.itemAt(pos)
    if item is None:
        return
    data = item.data(0, Qt.ItemDataRole.UserRole)
    if not isinstance(data, dict):
        return
    scope = data.get("scope")
    menu = QMenu(tree)

    if scope == "point" and data.get("point_id"):
        point_id = str(data["point_id"])
        if data.get("component_index") is None:
            edit = menu.addAction("Assembly — ονομασία / πηγή…")
            add = menu.addAction("+ Προσθήκη εξαρτήματος…")
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen is edit: _edit_point_assembly(tab, point_id)
            elif chosen is add: _add_point_component(tab, point_id)
        else:
            remove = menu.addAction("Αφαίρεση εξαρτήματος")
            if menu.exec(tree.viewport().mapToGlobal(pos)) is remove:
                _remove_point_component(tab, point_id, int(data["component_index"]))
        return

    if scope == "manifold" and data.get("supply_id") and data.get("manifold_key"):
        supply_id, key = str(data["supply_id"]), str(data["manifold_key"])
        if data.get("component_index") is None:
            edit = menu.addAction("Assembly συλλέκτη — ονομασία / πηγή…")
            add = menu.addAction("+ Προσθήκη εξαρτήματος συλλέκτη…")
            chosen = menu.exec(tree.viewport().mapToGlobal(pos))
            if chosen is edit: _edit_manifold_assembly(tab, supply_id, key)
            elif chosen is add: _add_manifold_component(tab, supply_id, key)
        else:
            remove = menu.addAction("Αφαίρεση εξαρτήματος συλλέκτη")
            if menu.exec(tree.viewport().mapToGlobal(pos)) is remove:
                _remove_manifold_component(tab, supply_id, key, int(data["component_index"]))


def _append_group(tree, rows, *, scope):
    if not rows:
        return
    first = rows[0]
    assembly_name = first.get("assembly_name") or "Δεν έχει επιλεγεί assembly"
    configured = any(r.get("component") for r in rows)
    parent = QTreeWidgetItem(tree, [
        str(first.get("point_label", "")),
        assembly_name,
        "" if configured else "Δεν έχουν δηλωθεί εξαρτήματα",
        "", "", "",
        str(first.get("rule_status", "UNCONFIGURED")),
        str(first.get("rule_source") or first.get("source_kind") or ""),
    ])
    data = {"scope": scope, "component_index": None}
    if scope == "point":
        data["point_id"] = str(first.get("point_id", ""))
    else:
        data["supply_id"] = str(first.get("supply_id", ""))
        data["manifold_key"] = str(first.get("manifold_key", ""))
    parent.setData(0, Qt.ItemDataRole.UserRole, data)
    parent.setToolTip(
        0,
        "Δεξί κλικ: όρισε το assembly ή πρόσθεσε ακριβή εξαρτήματα. "
        "Το ArchForge δεν δημιουργεί κρυφά εξαρτήματα από μνήμη.",
    )
    component_index = 0
    for row in rows:
        component = row.get("component")
        if not component:
            continue
        product = " / ".join(
            x for x in (component.get("manufacturer", ""), component.get("product_ref", "")) if x
        ) or "—"
        child = QTreeWidgetItem(parent, [
            "", "", str(component.get("description", "")),
            f"{float(component.get('quantity', 0.0)):g}",
            str(component.get("unit", "pcs")), product,
            str(component.get("rule_status", "MODEL_SELECTED")),
            str(component.get("rule_source") or component.get("source_kind") or ""),
        ])
        child_data = dict(data); child_data["component_index"] = component_index
        child.setData(0, Qt.ItemDataRole.UserRole, child_data)
        child.setToolTip(2, str(component.get("why", "")))
        component_index += 1
    parent.setExpanded(True)


def _refresh_connections(tab):
    from archforge.mep.plumbing_assemblies import (
        connection_assembly_details,
        manifold_assembly_details,
    )

    tree = getattr(tab, "connection_details", None)
    if tree is None:
        return
    tree.clear()

    manifold_groups = {}
    for row in manifold_assembly_details(tab.window.doc):
        manifold_groups.setdefault(row["manifold_key"], []).append(row)
    for _key, rows in manifold_groups.items():
        _append_group(tree, rows, scope="manifold")

    point_groups = {}
    for row in connection_assembly_details(tab.window.doc):
        point_groups.setdefault(row["point_id"], []).append(row)
    for _point_id, rows in point_groups.items():
        _append_group(tree, rows, scope="point")


def install() -> None:
    """Patch PlumbingTab before MainWindow instances are created."""
    from archforge.ui import plumbing_tab

    cls = plumbing_tab.PlumbingTab
    if getattr(cls, "_archforge_connection_details_installed", False):
        return

    original_init = cls.__init__
    original_refresh = cls.refresh

    def init(self, window):
        original_init(self, window)
        self.connection_details = _new_tree()
        self.connection_details.customContextMenuRequested.connect(lambda pos: _tree_menu(self, pos))
        self.pages.addTab(self.connection_details, "Συνδέσεις & Εξαρτήματα")

    def refresh(self):
        original_refresh(self)
        _refresh_connections(self)

    cls.__init__ = init
    cls.refresh = refresh
    cls._archforge_connection_details_installed = True
