"""Adds a connection/assembly detail page to the Plumbing report tab."""
from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QTreeWidget, QTreeWidgetItem


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
    tree.setToolTip(
        "Ακριβή εξαρτήματα ανά σύνδεση. Χωρίς επιλεγμένο assembly το ArchForge δεν μαντεύει βάνες/ρακόρ."
    )
    return tree


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
            "",
            "",
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
        parent.setToolTip(
            0,
            "Τα εξαρτήματα αυτής της σύνδεσης προέρχονται μόνο από ρητή επιλογή. Δεν δημιουργούνται από μνήμη ή συνήθεια.",
        )
        for row in rows:
            component = row.get("component")
            if not component:
                continue
            product = " / ".join(
                x for x in (component.get("manufacturer", ""), component.get("product_ref", "")) if x
            ) or "—"
            child = QTreeWidgetItem(parent, [
                "",
                "",
                str(component.get("description", "")),
                f"{float(component.get('quantity', 0.0)):g}",
                str(component.get("unit", "pcs")),
                product,
                str(component.get("rule_status", "MODEL_SELECTED")),
                str(component.get("rule_source") or component.get("source_kind") or ""),
            ])
            child.setToolTip(2, str(component.get("why", "")))
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
        self.pages.addTab(self.connection_details, "Συνδέσεις & Εξαρτήματα")

    def refresh(self):
        original_refresh(self)
        _refresh_connections(self)

    cls.__init__ = init
    cls.refresh = refresh
    cls._archforge_connection_details_installed = True
