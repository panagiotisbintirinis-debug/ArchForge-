"""Εγκαταστάσεις › Θέρμανση › «Θερμογέφυρες…» (κριτική v5 k7): οι θέσεις και τα μήκη από το σχέδιο, το ψ από εσάς.

Μία γραμμή ανά είδος: πόσες θέσεις, συνολικό μήκος, ψ [W/(m·K)], κωδικός λεπτομέρειας (π.χ. ΤΟΤΕΕ 20701-1), πηγή, Ψ·l.
Το ψ το γράφει ο χρήστης· κενό = δεν μετράει και λέγεται. «Εφαρμογή» = μία αναίρεση. «Δείξε» επιλέγει τις θέσεις του
είδους στην κάτοψη. Από κάτω η ενδεικτική ισχύς θέρμανσης με τις θερμογέφυρες.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from archforge.mep import thermal_bridges as TB

TITLE = "Θερμογέφυρες"
COLUMNS = ("Είδος", "Θέσεις", "Μήκος m", "ψ W/(m·K)", "Κωδικός λεπτομέρειας", "Πηγή", "Ψ·l W/K")
EDITABLE = (3, 4, 5)


def _num(text):
    text = str(text or "").strip().replace(",", ".")
    return None if not text else float(text)


def _gr(v, digits=2):
    return "" if v is None else f"{v:.{digits}f}".replace(".", ",")


class ThermalBridgesDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle(TITLE)
        self.resize(900, 460)
        root = QVBoxLayout(self)
        intro = QLabel("Οι θέσεις και τα μήκη βγαίνουν από το σχέδιο. Το ψ, ο κωδικός λεπτομέρειας και η πηγή "
                       "γράφονται από εσάς (μελέτη, ΤΟΤΕΕ 20701-1, φύλλο κατασκευαστή) — το πρόγραμμα δεν βάζει τιμή. "
                       "Είδος χωρίς ψ δεν μετράει και λέγεται. Δεν βρίσκονται ακόμη: " + TB.NOT_FOUND + ".")
        intro.setWordWrap(True)
        root.addWidget(intro)
        self.table = QTableWidget(0, len(COLUMNS), self)
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.table)
        row = QHBoxLayout()
        show = QPushButton("Δείξε στην κάτοψη", self)
        show.clicked.connect(self.show_selected)
        row.addWidget(show); row.addStretch(1)
        root.addLayout(row)
        self.power = QLabel(self); self.power.setWordWrap(True)
        root.addWidget(self.power)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close, self)
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Εφαρμογή")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Κλείσιμο")
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.refresh()

    def refresh(self):
        s = TB.summary(self.window.doc)
        self.rows = s["rows"]
        self.table.setRowCount(len(self.rows))
        for r, row in enumerate(self.rows):
            cells = (row["label"], str(row["count"]), _gr(row["length_m"]), _gr(row["psi"], 3), row["code"],
                     row["source"], _gr(row["psi_l"], 2) if row["psi_l"] is not None else "χωρίς ψ")
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c not in EDITABLE:
                    from PySide6.QtCore import Qt
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(r, c, item)
        from archforge.mep.heat_load import heat_load
        h = heat_load(self.window.doc)
        bridges = dict(h["parts"]).get("Θερμογέφυρες", 0)
        missing = f" · χωρίς ψ: {s['missing_n']} θέσεις, {_gr(s['missing_m'], 1)} m" if s["missing_n"] else ""
        self.power.setText(f"H_TB = Σ Ψ·l = {_gr(s['h_tb'], 2)} W/K → {bridges} W με ΔT {h['delta_t']:g} K · "
                           f"ενδεικτική ισχύς θέρμανσης ≈ {_gr(h['kw'], 1)} kW{missing}")
        return s

    def commands(self):
        """One command per kind the user changed (None when nothing changed); raises ValueError on a bad ψ."""
        cat = TB.catalogue(self.window.doc)
        out = []
        for r, row in enumerate(self.rows):
            psi = _num(self.table.item(r, 3).text())
            code, source = self.table.item(r, 4).text().strip(), self.table.item(r, 5).text().strip()
            if psi is not None and psi < -1.0:
                raise ValueError(f"{row['label']}: ψ {psi} W/(m·K) — ελέγξτε την τιμή")
            old = cat[row["type"]]
            if (psi, code, source) != (old["psi"], old["code"], old["source"]):
                out.append((row["type"], psi, code, source))
        return out

    def apply(self):
        try:
            changed = self.commands()
        except ValueError as exc:
            self.window.statusBar().showMessage(f"⚠ {TITLE}: {exc}", 8000)
            return None
        if not changed:
            self.window.statusBar().showMessage(f"{TITLE}: καμία αλλαγή", 4000)
            return None
        doc = self.window.doc
        # One undo for the whole table: build the final catalogue on top of the stored one.
        values = {k: dict(v) for k, v in ((TB.entity(doc).params.get("values") if TB.entity(doc) else None) or {}).items()}
        for key, psi, code, source in changed:
            if psi is None and not code and not source:
                values.pop(key, None)
            else:
                values[key] = {"psi": psi, "code": code, "source": source}
        from archforge.core.commands import AddEntity, UpdateEntity
        from archforge.core.model import Entity
        e = TB.entity(doc)
        command = (AddEntity(Entity(TB.KIND, {"values": values}, name="Θερμογέφυρες: ψ του έργου")) if e is None
                   else UpdateEntity(e.id, {"values": values}))
        self.window.stack.execute(command)
        self.refresh()
        self.window.statusBar().showMessage(f"{TITLE}: εφαρμόστηκαν {len(changed)} · Ctrl+Z = αναίρεση", 6000)
        return command

    def show_selected(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.rows):
            return []
        ids = [i for i in self.rows[r]["ids"] if i in self.window.doc.entities]
        self.window.doc.select(ids)
        self.window._redraw_views(all_views=True)
        self.window.statusBar().showMessage(f"{self.rows[r]['label']}: {self.rows[r]['count']} θέσεις, "
                                            f"{_gr(self.rows[r]['length_m'])} m — επιλεγμένα στην κάτοψη", 6000)
        return ids


def show(window):
    dialog = ThermalBridgesDialog(window)
    dialog.exec()
    return dialog
