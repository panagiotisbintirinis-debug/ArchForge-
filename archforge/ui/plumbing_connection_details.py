"""Adds an editable connection/assembly detail page to the Plumbing report tab."""
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
        "Δεξί κλικ σε σημείο: όρισε assembly / πρόσθεσε εξάρτημα. "
        "Χωρίς επιλογή το ArchForge δεν μαντεύει βάνες ή ρακόρ."
    )
    return tree


def _assembly_editor(tab, point_id):
    from archforge.core.commands import UpdateEntity

    point = tab.window.doc.get(point_id)
    assembly = copy.deepcopy(point.params.get("connection_assembly") or {})

    dialog = QDialog(tab)
    dialog.setWindowTitle("Assembly σύνδεσης")
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
        return

    assembly["name"] = name.text().strip()
    assembly["source_kind"] = str(source_kind.currentData())
    assembly["rule_status"] = str(status.currentData())
    assembly["rule_source"] = rule_source.text().strip()
    assembly.setdefault("components", [])
    tab.window.stack.execute(UpdateEntity(point_id, {"connection_assembly": assembly}))
    tab.window._redraw_views(all_views=True)
    tab.refresh()


def _component_editor(tab, point_id):
    from archforge.core.commands import UpdateEntity
    from archforge.mep.plumbing_accessories import ACCESSORY_TYPES

    point = tab.window.doc.get(point_id)
    assembly = copy.deepcopy(point.params.get("connection_assembly") or {})
    if not assembly:
        assembly = {
            "name": f"Σύνδεση {point.name or point.params.get('point_type', '')}",
            "source_kind": "professional_selection",
            "rule_status": "MODEL_SELECTED",
            "rule_source": "",
            "components": [],
        }

    dialog = QDialog(tab)
    dialog.setWindowTitle("Προσθήκη εξαρτήματος σύνδεσης")
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
        return

    component = {
        "accessory_type": str(kind.currentData()),
        "quantity": float(qty.value()),
        "unit": str(unit.currentData()),
    }
    if manufacturer.text().strip(): component["manufacturer"] = manufacturer.text().strip()
    if product_ref.text().strip(): component["product_ref"] = product_ref.text().strip()
    if description.text().strip(): component["description"] = description.text().strip()
    assembly.setdefault("components", []).append(component)
    tab.window.stack.execute(UpdateEntity(point_id, {"connection_assembly": assembly}))
    tab.window._redraw_views(all_views=True)
    tab.refresh()


def _remove_component(tab, point_id, component_index):
    from archforge.core.commands import UpdateEntity

    point = tab.window.doc.get(point_id)
    assembly = copy.deepcopy(point.params.get("connection_assembly") or {})
    components = list(assembly.get("components") or [])
    if not (0 <= int(component_index) < len(components)):
        return
    components.pop(int(component_index))
    assembly["components"] = components
    tab.window.stack.execute(UpdateEntity(point_id, {"connection_assembly": assembly}))
    tab.window._redraw_views(all_views=True)
    tab.refresh()


def _tree_menu(tab, pos):
    tree = tab.connection_details
    item = tree.itemAt(pos)
    if item is None:
        return
    data = item.data(0, Qt.ItemDataRole.UserRole)
    if not isinstance(data, dict) or not data.get("point_id"):
        return
    point_id = str(data["point_id"])
    menu = QMenu(tree)
    if data.get("component_index") is None:
        edit = menu.addAction("Assembly — ονομασία / πηγή…")
        add = menu.addAction("+ Προσθήκη εξαρτήματος…")
        chosen = menu.exec(tree.viewport().mapToGlobal(pos))
        if chosen is edit:
            _assembly_editor(tab, point_id)
        elif chosen is add:
            _component_editor(tab, point_id)
    else:
        remove = menu.addAction("Αφαίρεση εξαρτήματος")
        chosen = menu.exec(tree.viewport().mapToGlobal(pos))
        if chosen is remove:
            _remove_component(tab, point_id, int(data["component_index"]))


def _refresh_connections(tab):
    from archforge.mep.plumbing import route_plumbing
    from archforge.mep.plumbing_assemblies import connection_assembly_details

    tree = getattr(tab, "connection_details", None)
    if tree is None:
        return
    tree.clear()

    routed = route_plumbing(tab.window.doc)
    network_label = {"cold": "Κρύο", "hot": "Ζεστό"}
    for index, manifold in enumerate(routed.get("manifolds", ())):
        system = str(manifold.get("system", "cold"))
        outlets = list(manifold.get("outlets", ()))
        parent = QTreeWidgetItem(tree, [
            f"Συλλέκτης {network_label.get(system, system)}",
            "Derived manifold",
            f"{len(outlets)} έξοδοι",
            "1", "pcs", "—",
            "MODEL_DERIVED_ENGINEER_REVIEW",
            "route_plumbing",
        ])
        parent.setToolTip(0, "Ο συλλέκτης είναι πραγματικό κοστολογήσιμο στοιχείο του μονοσωλήνιου συστήματος.")
        QTreeWidgetItem(parent, [
            "", "",
            "Βάνες / ρακόρ / ερμάριο: απαιτείται ρητή επιλογή assembly ή προϊόντος",
            "—", "—", "—", "UNCONFIGURED", "—",
        ])

    grouped = {}
    for row in connection_assembly_details(tab.window.doc):
        grouped.setdefault(row["point_id"], []).append(row)

    for point_id, rows in grouped.items():
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
        parent.setData(0, Qt.ItemDataRole.UserRole, {"point_id": point_id, "component_index": None})
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
            child.setData(0, Qt.ItemDataRole.UserRole, {"point_id": point_id, "component_index": component_index})
            child.setToolTip(2, str(component.get("why", "")))
            component_index += 1
        parent.setExpanded(True)


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
