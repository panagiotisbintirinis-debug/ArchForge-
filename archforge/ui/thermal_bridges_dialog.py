"""Εγκαταστάσεις › Θέρμανση › «Θερμογέφυρες…» (κριτική v5 k7): οι θέσεις και τα μήκη από το σχέδιο, το ψ από εσάς.

Μία γραμμή ανά είδος: πόσες θέσεις, συνολικό μήκος, ψ [W/(m·K)], κωδικός λεπτομέρειας, πηγή, Ψ·l.
05/11: από την ΤΟΤΕΕ 20701-2, Πίνακας 15 (``mep/totee_20701_2.py``). Ο χρήστης λέει πού είναι η θερμομόνωση (τοίχοι,
πλάκες, κουφώματα) και «Συμπλήρωση από ΤΟΤΕΕ» γράφει τη βασική περίπτωση κάθε είδους· η στήλη «Πίν. 15» δίνει κάθε
περίπτωση της κατηγορίας με τα α/β/γ (π.χ. δοκός που διακόπτει τη θερμομόνωση). Δικό σας ψ γράφεται κι αυτό με το χέρι.
Κενό = δεν μετράει και λέγεται. «Εφαρμογή» = μία αναίρεση. «Δείξε» επιλέγει τις θέσεις του είδους στην κάτοψη.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from archforge.mep import thermal_bridges as TB

TITLE = "Θερμογέφυρες"
from archforge.mep import totee_20701_2 as T2

COLUMNS = ("Είδος", "Θέσεις", "Μήκος m", "ψ W/(m·K)", "Κωδικός λεπτομέρειας", "Πηγή", "Ψ·l W/K", "Πίν. 15")
CASE = 7
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
        intro = QLabel("Οι θέσεις και τα μήκη βγαίνουν από το σχέδιο. Το ψ: πείτε πού είναι η θερμομόνωση και "
                       "«Συμπλήρωση από ΤΟΤΕΕ» (20701-2, Πίνακας 15), ή διαλέξτε περίπτωση ανά γραμμή, ή γράψτε δικό σας "
                       "(μελέτη, φύλλο κατασκευαστή). Είδος χωρίς ψ δεν μετράει και λέγεται. Δεν βρίσκονται ακόμη: "
                       + TB.NOT_FOUND + ".")
        intro.setWordWrap(True)
        root.addWidget(intro)
        scheme = QHBoxLayout()
        self.schemes = {}
        for key, options in T2.SCHEMES.items():
            box = QComboBox(self)
            for value, label in options.items():
                box.addItem(label, value)
            if key == "opening":
                box.setCurrentIndex(box.findData("apart"))
            self.schemes[key] = box
            scheme.addWidget(box)
        fill = QPushButton("Συμπλήρωση από ΤΟΤΕΕ", self)
        fill.setToolTip("ΤΟΤΕΕ 20701-2/2010, Πίνακας 15: η βασική περίπτωση κάθε είδους για αυτή τη θέση θερμομόνωσης "
                        "(χωρίς τα α/β/γ — διαλέξτε τα ανά γραμμή αν ισχύουν)")
        fill.clicked.connect(self.fill_from_totee)
        scheme.addWidget(fill)
        root.addLayout(scheme)
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
            # Every case of the type's category in Πίνακας 15, with its α/β/γ.
            box = QComboBox(self.table)
            box.addItem("—", None)
            for code, text, psi in T2.cases(row["type"]):
                box.addItem(f"{code[3:]} · {psi:+.2f} · {text}".replace(".", ",", 2), code)
            current = row["code"].split("· ")[-1] if row["code"].startswith("ΤΟΤΕΕ 20701-2") else None
            if current:
                box.setCurrentIndex(max(0, box.findData("15." + current)))
            box.currentIndexChanged.connect(lambda _i, r=r, b=box: self._case_chosen(r, b.currentData()))
            self.table.setCellWidget(r, CASE, box)
        from archforge.mep.heat_load import heat_load
        h = heat_load(self.window.doc)
        bridges = dict(h["parts"]).get("Θερμογέφυρες", 0)
        missing = f" · χωρίς ψ: {s['missing_n']} θέσεις, {_gr(s['missing_m'], 1)} m" if s["missing_n"] else ""
        self.power.setText(f"H_TB = Σ Ψ·l = {_gr(s['h_tb'], 2)} W/K → {bridges} W με ΔT {h['delta_t']:g} K · "
                           f"ενδεικτική ισχύς θέρμανσης ≈ {_gr(h['kw'], 1)} kW{missing}")
        return s

    def _case_chosen(self, r, code):
        """A row of Πίνακας 15 chosen: its ψ, code and source go into the row (saved with «Εφαρμογή»)."""
        if code is None:
            return
        e = T2.entry(code)
        self.table.item(r, 3).setText(_gr(e["psi"], 3))
        self.table.item(r, 4).setText(e["code"])
        self.table.item(r, 5).setText(e["source"])

    def fill_from_totee(self):
        """The base case of every type for the insulation scheme chosen above; returns how many rows were filled."""
        walls, slab, opening = (self.schemes[k].currentData() for k in ("walls", "slab", "opening"))
        n = 0
        for r, row in enumerate(self.rows):
            code = T2.base_case(row["type"], walls, slab, opening)
            if code is None:
                continue
            box = self.table.cellWidget(r, CASE)
            box.blockSignals(True); box.setCurrentIndex(max(0, box.findData(code))); box.blockSignals(False)
            self._case_chosen(r, code)
            n += 1
        self.window.statusBar().showMessage(f"{TITLE}: {n} είδη από ΤΟΤΕΕ 20701-2 Πίν. 15 — «Εφαρμογή» για να μείνουν",
                                            8000)
        return n

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


def power_text(doc):
    """The indicative heating power with each part and what is left out (nothing in the project changes)."""
    from archforge.mep.heat_load import heat_load, summary
    r = heat_load(doc)
    lines = [summary(r), ""] + [f"{name}: {watts} W" for name, watts in r["parts"]]
    return "\n".join(lines)


def show_power(window):
    """Εγκαταστάσεις › Θέρμανση › «Ενδεικτική ισχύς θέρμανσης…» (Σ10): only the calculation, no emitters added."""
    text = power_text(window.doc)
    window.statusBar().showMessage(text.splitlines()[0][:220], 12000)
    if not getattr(window, "_no_modal_dialogs", False):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(window, "Ενδεικτική ισχύς θέρμανσης", text)
    return text
