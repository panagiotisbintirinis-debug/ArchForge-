"""«Επιμέτρηση εργασιών» with everything the project measures, by choice (owner 30/10: «να βγαίνουν και οι σκάλες, τα
κουφώματα … σωληνώσεις, ηλεκτρολογικά, αν μη τι άλλο πρέπει να υπάρχει επιλογή … περιθώριο τιμολόγησης … κουζίνα με
κουτιά, τιμές, πορτάκια … πρέπει να έχω επιλογή να τα δείχνω όλα»).

Left: one tick per list the program measures (the per-room take-off, then every list of ``quantities/materials``:
Κουφώματα, Σκάλες, Ύδρευση, Αποχέτευση, Ηλεκτρολογικά, Κουζίνα, Στρώσεις …), «Όλα» / «Κανένα».  Right: each ticked
list with quantity, price per unit (the user's price book — never an invented price) and amount; at the bottom the
subtotal, the margin % (the project's own, one undo) and VAT.  CSV / Excel of what is ticked.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
                               QSplitter, QTextBrowser, QVBoxLayout, QWidget)

ROOMS = "Ανά χώρο"


def section_names(doc):
    from archforge.quantities.materials import all_lists
    return [ROOMS] + [name for name, _t, rows, _n in all_lists(doc) if rows]


def html(doc, chosen):
    """The report for the ticked ``chosen`` names (also for tests)."""
    from archforge.quantities.quote import money, quote
    from archforge.quantities.takeoff import COLUMNS, take_off
    parts = []
    if ROOMS in chosen:
        result = take_off(doc)
        rows = "".join("<tr>" + "".join(f"<td>{escape(str(r[k]))}</td>" for k, _l in COLUMNS) + "</tr>" for r in result["rooms"])
        t, d = result["totals"], result["demolition"]
        parts.append("<h3>Ανά χώρο</h3><table border=1 cellspacing=0 cellpadding=3><tr>"
                     + "".join(f"<th>{label}</th>" for _k, label in COLUMNS) + "</tr>" + rows
                     + "<tr><td><b>Σύνολο</b></td><td></td>" + "".join(f"<td><b>{t.get(k, '')}</b></td>" for k, _l in COLUMNS[2:])
                     + "</tr></table>"
                     + f"<p>Καθαιρέσεις: {d['count']} τοίχοι — {d['walls_m2']} m², {d['walls_m3']} m³ · νέα ανοίγματα σε "
                       f"υφιστάμενους: {d['openings_to_cut']} — {d['openings_to_cut_m2']} m²</p>"
                     + f"<p><i>{escape(result['provenance'])}</i></p>")
    lists = [n for n in chosen if n != ROOMS]
    if lists:
        q = quote(doc, only=tuple(lists))
        for (title, rows), trade in zip(q["sections"], q["by_trade"]):
            body = "".join(
                f"<tr><td>{escape(str(r['description']))}</td><td>{escape(str(r['unit']))}</td>"
                f"<td align=right>{'—' if r['quantity'] is None else str(r['quantity']).replace('.', ',')}</td>"
                f"<td align=right>{money(r['price'])}</td><td align=right>{money(r['amount'])}</td></tr>" for r in rows)
            missing = f" · <span style='color:#b45309'>{trade['missing']} χωρίς τιμή</span>" if trade["missing"] else ""
            parts.append(f"<h3>{escape(title)}</h3><table border=1 cellspacing=0 cellpadding=3 width=100%>"
                         "<tr><th>Είδος / εργασία</th><th>Μον.</th><th>Ποσότητα</th><th>€ / μον.</th><th>Σύνολο</th></tr>"
                         f"{body}<tr><td colspan=4><b>Σύνολο ενότητας</b>{missing}</td>"
                         f"<td align=right><b>{money(trade['subtotal'])}</b></td></tr></table>")
        parts.append("<h3>Σύνολα</h3><table cellpadding=3>"
                     f"<tr><td>Υποσύνολο (με τιμή)</td><td align=right>{money(q['subtotal'])}</td></tr>"
                     f"<tr><td>Περιθώριο {q['margin']:g} %</td><td align=right>{money(q['margin_amount'])}</td></tr>"
                     f"<tr><td>ΦΠΑ {q['vat']:g} %</td><td align=right>{money(q['vat_amount'])}</td></tr>"
                     f"<tr><td><b>Σύνολο</b></td><td align=right><b>{money(q['total'])}</b></td></tr></table>"
                     + (f"<p style='color:#b45309'>{q['missing']} γραμμές χωρίς τιμή — Κατασκευή ▸ Επιμετρήσεις & τιμές ▸ "
                        "Τιμές & προσφορά. Δεν μπαίνει ποτέ τιμή που δεν έδωσες.</p>" if q["missing"] else ""))
    return "<h2>Επιμέτρηση εργασιών</h2>" + ("".join(parts) or "<p>Διάλεξε αριστερά τι να φαίνεται.</p>")


def set_margin_command(doc, percent):
    """The project's margin % on the priced items (one undo); the price list is made when there is none."""
    from archforge.core.commands import AddEntity, UpdateEntity
    from archforge.core.model import Entity
    from archforge.quantities.quote import price_entity
    if float(percent) < 0:
        raise ValueError("το περιθώριο δεν είναι αρνητικό")
    e = price_entity(doc)
    if e is None:
        return AddEntity(Entity("price_list", {"margin": float(percent)}, name="Τιμές & προσφορά"))
    return UpdateEntity(e.id, {"margin": float(percent)})


class TakeoffDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Επιμέτρηση εργασιών")
        self.resize(1150, 680)
        lay = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal); lay.addWidget(split, 1)
        left = QWidget(); lv = QVBoxLayout(left); lv.setContentsMargins(0, 0, 0, 0)
        lv.addWidget(QLabel("Εμφάνιση"))
        self.sections = QListWidget()
        remembered = getattr(window, "_takeoff_sections", None)
        for name in section_names(window.doc):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if remembered is None or name in remembered else Qt.CheckState.Unchecked)
            self.sections.addItem(item)
        self.sections.itemChanged.connect(lambda _i: self.refresh())
        lv.addWidget(self.sections, 1)
        row = QHBoxLayout(); lv.addLayout(row)
        self.all_button, self.none_button = QPushButton("Όλα"), QPushButton("Κανένα")
        self.all_button.clicked.connect(lambda: self._tick(True)); self.none_button.clicked.connect(lambda: self._tick(False))
        row.addWidget(self.all_button); row.addWidget(self.none_button)
        lv.addWidget(QLabel("Περιθώριο τιμολόγησης"))
        from archforge.quantities.quote import settings
        self.margin = QDoubleSpinBox(); self.margin.setRange(0, 200); self.margin.setDecimals(1); self.margin.setSuffix(" %")
        self.margin.setValue(settings(window.doc)["margin"])
        self.margin.editingFinished.connect(self._set_margin)
        lv.addWidget(self.margin)
        split.addWidget(left)
        self.browser = QTextBrowser(); split.addWidget(self.browser)
        split.setStretchFactor(1, 4)
        buttons = QHBoxLayout(); lay.addLayout(buttons)
        csv = QPushButton("Αποθήκευση CSV (ανά χώρο)…"); csv.clicked.connect(self._save_csv)
        xlsx = QPushButton("Excel με τιμές (ό,τι είναι επιλεγμένο)…"); xlsx.clicked.connect(self._save_xlsx)
        buttons.addWidget(csv); buttons.addWidget(xlsx)
        self.refresh()

    def chosen(self):
        return [self.sections.item(i).text() for i in range(self.sections.count())
                if self.sections.item(i).checkState() == Qt.CheckState.Checked]

    def _tick(self, on):
        self.sections.blockSignals(True)
        for i in range(self.sections.count()):
            self.sections.item(i).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        self.sections.blockSignals(False)
        self.refresh()

    def refresh(self):
        self.window._takeoff_sections = set(self.chosen())
        self.browser.setHtml(html(self.window.doc, self.chosen()))

    def _set_margin(self):
        from archforge.quantities.quote import settings
        if abs(settings(self.window.doc)["margin"] - self.margin.value()) < 1e-9:
            return
        self.window.stack.execute(set_margin_command(self.window.doc, self.margin.value()))
        self.refresh()

    def _save_csv(self):
        from PySide6.QtWidgets import QFileDialog
        from archforge.quantities.takeoff import take_off, to_csv
        path, _ = QFileDialog.getSaveFileName(self, "Επιμέτρηση CSV", "epimetrisi.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(to_csv(take_off(self.window.doc)))

    def _save_xlsx(self):
        only = [n for n in self.chosen() if n != ROOMS]
        self.window._export_priced_lists(only=only or None)


def show(window):
    dlg = TakeoffDialog(window)
    window._takeoff_dialog = dlg
    window._takeoff_view = dlg.browser
    if not getattr(window, "_no_modal_dialogs", False):
        dlg.exec()
    return dlg
