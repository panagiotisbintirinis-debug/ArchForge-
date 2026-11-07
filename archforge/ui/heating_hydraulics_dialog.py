"""Εγκαταστάσεις ▸ Θέρμανση ▸ «Υδραυλικός υπολογισμός…» (07/11): παροχές, ταχύτητες, Δp ανά κύκλωμα και συλλέκτη
(``mep/heating_hydraulics``).  Θερμοκρασίες προσαγωγής / επιστροφής της πηγής εδώ — «Εφαρμογή» = μία αναίρεση."""
from __future__ import annotations

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QPlainTextEdit,
                               QVBoxLayout)

TITLE = "Υδραυλικός υπολογισμός θέρμανσης"


class HeatingHydraulicsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        from archforge.mep.heating_hydraulics import temperatures
        self.window = window
        self.setWindowTitle(TITLE)
        root = QVBoxLayout(self)
        intro = QLabel("Παροχή κάθε κυκλώματος από το φορτίο του χώρου του, πτώση πίεσης Darcy–Weisbach (Colebrook–White). "
                       "Προμελέτη για τον μηχανολόγο — δεν διαλέγει κυκλοφορητή ούτε εξισορροπεί.")
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        ts, tr, _src = temperatures(window.doc)
        self.supply, self.ret = QDoubleSpinBox(self), QDoubleSpinBox(self)
        for box, value in ((self.supply, ts), (self.ret, tr)):
            box.setRange(20.0, 95.0); box.setDecimals(1); box.setSuffix(" °C"); box.setValue(value)
        form.addRow("Προσαγωγή", self.supply)
        form.addRow("Επιστροφή", self.ret)
        root.addLayout(form)
        self.text = QPlainTextEdit(self); self.text.setReadOnly(True); self.text.setMinimumSize(760, 360)
        root.addWidget(self.text, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close, self)
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Εφαρμογή")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Κλείσιμο")
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.show_result()

    def show_result(self):
        from archforge.mep.heating_hydraulics import hydraulics, summary_lines
        try:
            r = hydraulics(self.window.doc)
            lines = summary_lines(r) if r["manifolds"] or r["two_pipe"] else \
                ["Δεν υπάρχουν κυκλώματα: βάλτε πηγή θέρμανσης και σώματα (ή ενδοδαπέδια) — Εγκαταστάσεις ▸ Θέρμανση."]
        except ValueError as exc:
            lines = [f"⚠ {exc}"]
        self.text.setPlainText("\n".join(lines))

    def apply(self):
        from archforge.core.commands import UpdateEntity
        from archforge.mep.heating_layout import source_of
        src = source_of(self.window.doc)
        if src is None:
            self.window.statusBar().showMessage(f"{TITLE}: δεν υπάρχει πηγή θέρμανσης για να κρατήσει τις θερμοκρασίες", 6000)
            return
        if self.supply.value() <= self.ret.value():
            self.window.statusBar().showMessage(f"{TITLE}: η προσαγωγή πρέπει να είναι πάνω από την επιστροφή", 6000)
            return
        self.window.stack.execute(UpdateEntity(src.id, {"flow_temp": self.supply.value(), "return_temp": self.ret.value()}))
        self.show_result()
        self.window.statusBar().showMessage(f"{TITLE}: εφαρμόστηκε · Ctrl+Z = αναίρεση", 6000)


def show(window):
    d = HeatingHydraulicsDialog(window)
    window._heating_hydraulics_dialog = d
    d.show()
    return d
