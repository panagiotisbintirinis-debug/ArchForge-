"""Dedicated Plumbing details/report tab.

The floor plan stays drawing-first.  Technical detail, quantities/BOM and rule
provenance live here instead of being printed over pipe runs.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHeaderView, QLabel, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

TAB_TITLE = "Υδραυλικά"


def _n(value, decimals=2):
    if value is None:
        return "—"
    return f"{float(value):.{decimals}f}".replace(".", ",")


def _length(a, b):
    return math.dist(tuple(float(v) for v in a), tuple(float(v) for v in b))


class PlumbingTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._stale = True
        self.setObjectName("plumbing_details_tab")
        self.setProperty("archforge_report_tab", True)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        title = QLabel("Υδραυλικά — τεχνικές λεπτομέρειες")
        title.setStyleSheet("font-weight:600;font-size:15px")
        root.addWidget(title)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.pages = QTabWidget()
        self.network = self._tree(["Δίκτυο", "Διάμετρος", "Μήκος", "Από", "Προς", "Κατάσταση"])
        self.bom = self._tree(["Κωδικός", "Περιγραφή", "Κατηγορία", "Ποσότητα", "Μονάδα", "Κατάσταση", "Πηγή"])
        self.rules = self._tree(["Κατάσταση", "Κανόνας", "Τιμή", "Πηγή", "Σημείωση"])
        self.pages.addTab(self.network, "Δίκτυο")
        self.pages.addTab(self.bom, "Ποσότητες / BOM")
        self.pages.addTab(self.rules, "Κανόνες & Πηγές")
        root.addWidget(self.pages, 1)

        self.note = QLabel(
            "Η κάτοψη δείχνει μόνο τις σωληνώσεις. Οι διάμετροι, τα μήκη, οι ποσότητες και η προέλευση των κανόνων "
            "παρουσιάζονται εδώ. ENGINEER_REVIEW / DESIGN_DEFAULT δεν αποτελούν επαληθευμένη κανονιστική απαίτηση."
        )
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:palette(mid);font-size:11px")
        root.addWidget(self.note)

    @staticmethod
    def _tree(headers):
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setStretchLastSection(True)
        return tree

    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def refresh(self):
        from archforge.mep.plumbing import route_plumbing
        from archforge.mep.plumbing_costing import plumbing_quantities
        from archforge.mep.plumbing_rules import plumbing_rule_audit

        self._stale = False
        routed = route_plumbing(self.window.doc)
        quantities = plumbing_quantities(self.window.doc)

        self.network.clear()
        total = {"cold": 0.0, "hot": 0.0}
        labels = {"cold": "Κρύο", "hot": "Ζεστό"}
        for network in ("cold", "hot"):
            for a, b, diameter in routed.get(network, ()):
                length = _length(a, b)
                total[network] += length
                QTreeWidgetItem(self.network, [
                    labels[network], f"Ø{int(diameter)}", f"{_n(length)} m",
                    f"({_n(a[0])}, {_n(a[1])}, {_n(a[2])})",
                    f"({_n(b[0])}, {_n(b[1])}, {_n(b[2])})",
                    "ENGINEER_REVIEW",
                ])

        self.bom.clear()
        for line in quantities:
            quantity = _n(line.quantity, 2)
            QTreeWidgetItem(self.bom, [
                str(line.code), str(line.description), str(line.category), quantity,
                str(line.unit), str(line.rule_status or ""), str(line.rule_source or line.source or ""),
            ])

        self.rules.clear()
        grouped = plumbing_rule_audit()
        order = ("VERIFIED_STANDARD", "MANUFACTURER_DATA", "CALCULATED", "DESIGN_DEFAULT", "ENGINEER_REVIEW")
        for status in order:
            for rule in grouped.get(status, ()):
                value = "—" if rule.value is None else str(rule.value)
                if rule.unit and value != "—":
                    value = f"{value} {rule.unit}"
                QTreeWidgetItem(self.rules, [
                    status, rule.label, value, rule.source or "—", rule.note or "",
                ])

        unserved = len(routed.get("report", {}).get("unserved", ()))
        self.summary.setText(
            f"Κρύο: {_n(total['cold'])} m   ·   Ζεστό: {_n(total['hot'])} m   ·   "
            f"Γραμμές BOM: {len(quantities)}" + (f"   ·   Μη εξυπηρετούμενα σημεία: {unserved}" if unserved else "")
        )
        return {"route": routed, "quantities": quantities, "rules": grouped}


def install(window):
    tab = PlumbingTab(window)
    window._plumbing_tab = tab
    window.stack.listeners.append(tab.mark_stale)

    menu = getattr(window, "_mockup_plumbing_menu", None)
    if menu is not None:
        menu.addSeparator()
        action = QAction("Υδραυλικά — λεπτομέρειες", menu)
        action.setToolTip("Δίκτυο, ποσότητες/BOM και κανόνες χωρίς πληροφορίες πάνω στην κάτοψη")
        action.triggered.connect(lambda _=False: show(window))
        menu.addAction(action)
        window._plumbing_details_action = action
    return tab


def show(window):
    tab = getattr(window, "_plumbing_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    return tab.refresh()
