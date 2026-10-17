"""Material-economy page for the Plumbing report tab."""
from __future__ import annotations

from PySide6.QtWidgets import QHeaderView, QLabel, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


def _page(tab):
    page = QWidget()
    layout = QVBoxLayout(page)
    note = QLabel(
        "Σύγκριση υλικών — όχι κανονιστική επιλογή. Το ArchForge δεν αλλάζει αυτόματα σύστημα. "
        "Τα μήκη προκύπτουν από την ίδια χάραξη του μοντέλου· οι τρέχουσες διατομές παραμένουν ENGINEER_REVIEW."
    )
    note.setWordWrap(True)
    tree = QTreeWidget()
    tree.setHeaderLabels(["Σύστημα", "Σωλήνα συνολικά", "Συλλέκτες", "Επιλεγμένα εξαρτήματα", "Χωρίς σύνδεση", "Κατάσταση"])
    tree.setRootIsDecorated(False)
    tree.setAlternatingRowColors(True)
    tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    tree.header().setStretchLastSection(True)
    layout.addWidget(note)
    layout.addWidget(tree, 1)
    tab.material_economy_tree = tree
    return page


def _refresh(tab):
    from archforge.mep.plumbing_economy import compare_systems, least_pipe_length_candidate

    tree = getattr(tab, "material_economy_tree", None)
    if tree is None:
        return
    tree.clear()
    rows = compare_systems(tab.window.doc)
    least = least_pipe_length_candidate(tab.window.doc)
    for row in rows:
        suffix = "  ← τρέχον" if row["current"] else ""
        if least and row["system"] == least["system"]:
            suffix += "  · λιγότερα m σωλήνα"
        item = QTreeWidgetItem(tree, [
            str(row["label"]) + suffix,
            f"{row['pipe_m']:.2f} m".replace(".", ","),
            str(row["manifolds"]),
            f"{row['selected_components']:g}",
            str(row["unserved"]),
            str(row["status"]),
        ])
        item.setToolTip(0, "Σύγκριση σχεδιασμού μόνο. Η μικρότερη ποσότητα σωλήνα δεν υπερισχύει τεχνικών απαιτήσεων ή επιλογής συστήματος.")


def install() -> None:
    from archforge.ui import plumbing_tab
    cls = plumbing_tab.PlumbingTab
    if getattr(cls, "_archforge_material_economy_installed", False):
        return
    original_init = cls.__init__
    original_refresh = cls.refresh

    def init(self, window):
        original_init(self, window)
        self.material_economy_page = _page(self)
        self.pages.addTab(self.material_economy_page, "Οικονομία υλικών")

    def refresh(self):
        original_refresh(self)
        _refresh(self)

    cls.__init__ = init
    cls.refresh = refresh
    cls._archforge_material_economy_installed = True
