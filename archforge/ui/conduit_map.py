"""Geometric conduit schedule from the Document; installation study still required."""
from __future__ import annotations


def show(window):
    from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout
    from archforge.mep.conduits import conduit_map
    m = conduit_map(window.doc)
    dialog = QDialog(window)
    dialog.setWindowTitle("Χάρτης σωληνώσεων")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel(f"{m['conduits']} σωληνώσεις · {len(m['pieces'])} κομμάτια · "
                            + ", ".join(f"Φ{dn} {v:.1f} m" for dn, v in m["by_size"].items())
                            + (f" · διπλού δομήματος {m['outdoor_m']:.1f} m" if m["outdoor_m"] else "")
                            + f" · κουτιά χωρισμού {len(m['split_boxes'])}"))
    heads = ("Κομμάτι", "Από", "Προς", "Μήκος (m)", "Φ εξ.", "Ø εσωτ.", "Καμπύλες", "Γραμμές", "Αγωγοί", "Πλήρωση", "Όριο έργου", "Σειρά")
    table = QTableWidget(len(m["pieces"]), len(heads))
    table.setHorizontalHeaderLabels(heads)
    for i, p in enumerate(m["pieces"]):
        values = (p["id"], p["from"], p["to"], f"{p['length_m']:.2f}",
                  (f"{p['count']}×" if p["count"] > 1 else "") + f"Φ{p['dn']}" + (" διπλού δομ." if p["outdoor"] else ""),
                  f"{p['inner_mm']:g} mm", str(p["bends"]), ", ".join(p["lines"]), p["conductors"], f"{p['fill'] * 100:.1f}%", f"{p['fill_limit'] * 100:g}%", p["profile_name"])
        for j, v in enumerate(values):
            table.setItem(i, j, QTableWidgetItem(v))
    table.resizeColumnsToContents()
    layout.addWidget(table)
    for w in m["warnings"] + m["review"]:
        layout.addWidget(QLabel("⚠ " + w))
    note = QLabel(m["rule"])
    note.setWordWrap(True)
    layout.addWidget(note)
    dialog.resize(980, 600)
    if not getattr(window, "_no_modal_dialogs", False):
        dialog.exec()
    return m
