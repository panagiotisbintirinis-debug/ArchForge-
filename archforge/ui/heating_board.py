"""«Πίνακας συλλεκτών θέρμανσης»: one table per manifold, a row per circuit (mep/heating_layout.manifold_schedule)."""
from __future__ import annotations


def show(window):
    from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout
    from archforge.mep.heating_layout import MAX_CIRCUIT, PROVENANCE, SIZE_RULE, manifold_schedule, route_heating_cached
    route = route_heating_cached(window.doc)
    boards = manifold_schedule(route)
    dialog = QDialog(window)
    dialog.setWindowTitle("Πίνακας συλλεκτών θέρμανσης")
    layout = QVBoxLayout(dialog)
    rep = route["report"]
    layout.addWidget(QLabel(f"{rep['system_label']} · {rep['distribution_label']} · {rep['circuits']} κυκλώματα"
                            + (f" · μέγιστο κύκλωμα {MAX_CIRCUIT:.0f} m" if rep["system"] == "underfloor" else "")))
    if not boards:
        layout.addWidget(QLabel("Χωρίς συλλέκτες (δισωλήνιο ή χωρίς πηγή θέρμανσης)."))
    heads = ("Κύκλωμα", "Χώρος", "Τροφοδοτεί", "Φ", "Μήκος (m)", "Προσαγωγή", "Επιστροφή")
    for b in boards:
        layout.addWidget(QLabel(f"{b['manifold']} — στάθμη {b['floor']:+.2f} · {b['totals']['circuits']} κυκλώματα · "
                                f"{b['totals']['length_m']:.0f} m σωλήνα" + (" · ομάδα ανάμιξης" if b["mixing"] else "")))
        table = QTableWidget(len(b["rows"]), len(heads))
        table.setHorizontalHeaderLabels(heads)
        for i, r in enumerate(b["rows"]):
            for j, v in enumerate((r["no"], r["room"], r["what"], f"Φ{r['dn']}", f"{r['length_m']:.1f}" + (" ⚠" if r["flag"] else ""),
                                   r["supply"], r["return"])):
                table.setItem(i, j, QTableWidgetItem(str(v)))
        table.resizeColumnsToContents()
        layout.addWidget(table)
    layout.addWidget(QLabel(SIZE_RULE))
    note = QLabel(PROVENANCE)
    note.setWordWrap(True)
    layout.addWidget(note)
    dialog.resize(760, 520)
    if not getattr(window, "_no_modal_dialogs", False):
        dialog.exec()
    return boards
