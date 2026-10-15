"""«Υλικά & τιμές» — one card per trade, prices, order list and quote (owner 15/10).

Owner: «κάθε επάγγελμα έχει τα δικά του υλικά, τα δεδομένα τα παίρνει από το σχέδιο και τιμολογεί βάσει όγκου,
μέτρων, τετραγωνικών … του πλακατζή δεν τον ενδιαφέρουν τα ηλεκτρολογικά, εκτός αν είναι ο ίδιος πελάτης —
πρέπει να υπάρχουν καρτέλες υλικών ανά εργασία με τιμές και με επιλογή εξόδου της λίστας για παραγγελία».

Each card is one list of ``quantities.materials.all_lists`` (one trade): its quantities come from the drawing
in the unit of the work (m, m², m³, τεμ.), the professional types material and labour per unit (one
``UpdateEntity`` on the price list, undo), and gets: the **order list** (materials and quantities, CSV for
Excel/the supplier) and the **quote for that trade only** (PDF).  Ticking several cards gives one combined
quote — when the same professional or the same client takes them.  Costing: ``quantities.quote.costed``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

TAB_TITLE = "Υλικά & τιμές"
SUMMARY = "Σύνολο έργου"
# Honest scope of the construction cost: what the program does NOT measure yet (owner 15/10: «τα μετράει σχεδόν όλα»).
NOT_MEASURED = ("οπλισμός και καλούπια (από τη στατική μελέτη)", "κονιάματα/κόλλες (από τα φύλλα των προϊόντων)",
                "τεμάχια τούβλων/κεραμιδιών όσο δεν έχεις δώσει τεμ./m² από το φύλλο",
                "χώρος εργασίας/πρανή, αφράτευση και επιχώσεις των εκσκαφών")
COLUMNS = ["Είδος", "Μον.", "Ποσότητα", "Υλικό €/μον.", "Εργασία €/μον.", "Σύνολο", "Γιατί"]


def _num(v):
    return "" if v is None else f"{float(v):g}".replace(".", ",")


def order_csv(name, rows):
    """Order list of one trade: code; item; unit; quantity — no prices (for the supplier). Study items marked."""
    from archforge.quantities.quote import row_meta
    lines = [f"Λίστα παραγγελίας — {name}", "Κωδικός;Είδος;Μονάδα;Ποσότητα"]
    for row in rows:
        desc, unit, qty, meta = row_meta(row)
        lines.append(";".join([meta["code"], str(desc), str(unit), "από τη μελέτη" if qty is None else _num(qty)]))
    return "\n".join(lines) + "\n"


class TradesTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._stale = True
        self._filling = False
        self.setObjectName("trades_tab")
        root = QVBoxLayout(self); root.setContentsMargins(10, 8, 10, 8)
        head = QHBoxLayout()
        title = QLabel("Υλικά & τιμές ανά επάγγελμα"); title.setStyleSheet("font-weight:600;font-size:15px")
        head.addWidget(title); head.addStretch(1)
        self.order = QPushButton("Λίστα παραγγελίας…"); self.order.clicked.connect(lambda: self.export_order())
        self.offer = QPushButton("Προσφορά…"); self.offer.clicked.connect(lambda: self.export_offer())
        self.offer.setToolTip("Προσφορά για τα επιλεγμένα επαγγέλματα (☑) — ή μόνο για την ανοιχτή καρτέλα")
        head.addWidget(self.order); head.addWidget(self.offer)
        root.addLayout(head)
        self.empty = QLabel("Δεν υπάρχουν ακόμη ποσότητες: σχεδίασε ή εισήγαγε το σχέδιο και βάλε τα στοιχεία της δουλειάς σου.")
        self.empty.setWordWrap(True)
        root.addWidget(self.empty)
        self.cards = QTabWidget(); root.addWidget(self.cards, 1)
        self.summary = QLabel(); self.summary.setWordWrap(True); root.addWidget(self.summary)
        self.tables, self.checks = {}, {}

    # ------------------------------------------------------------------------------------------------ content
    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def lists(self):
        from archforge.quantities.materials import all_lists
        return all_lists(self.window.doc)

    def refresh(self):
        from archforge.quantities.quote import costed, money
        self._stale = False
        current = self.cards.tabText(self.cards.currentIndex()) if self.cards.count() else None
        ticked = {n for n, c in self.checks.items() if c.isChecked()}
        self._filling = True
        try:
            self.cards.clear(); self.tables, self.checks = {}, {}
            lists = self.lists()
            if lists:
                self.cards.addTab(self._summary_page(lists), SUMMARY)
            for name, title, rows, notes in lists:
                page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(0, 6, 0, 0)
                check = QCheckBox("Στην προσφορά (ίδιος τεχνίτης ή ίδιος πελάτης)"); check.setChecked(name in ticked)
                v.addWidget(QLabel(title)); v.addWidget(check)
                table = QTableWidget(len(rows), len(COLUMNS)); table.setHorizontalHeaderLabels(COLUMNS)
                table.verticalHeader().setVisible(False)
                for i, r in enumerate(costed(self.window.doc, name, rows)):
                    cells = [r["description"], r["unit"], "από τη μελέτη" if r["quantity"] is None else _num(r["quantity"]),
                             None, None, money(r["amount"]) if r["amount"] is not None else "—", r["why"]]
                    for j, text in enumerate(cells):
                        if j in (3, 4):
                            continue
                        item = QTableWidgetItem(str(text)); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                        table.setItem(i, j, item)
                    table.item(i, 0).setData(Qt.ItemDataRole.UserRole, r["code"])
                    table.item(i, 0).setToolTip(f"{r['code']} · κανόνας: {r['status']}")
                    entry = self._book().get(r["code"], {})
                    for j, key in ((3, "material"), (4, "labour")):
                        table.setItem(i, j, QTableWidgetItem(_num(entry.get(key))))
                table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
                table.horizontalHeader().setStretchLastSection(True)
                table.itemChanged.connect(lambda item, t=table: self._price_edited(t, item))
                v.addWidget(table, 1)
                if name in ("Τοιχοποιίες", "Κεραμοσκεπή"):
                    pieces = QPushButton("Τεμάχια ανά m² (από το φύλλο του προϊόντος)…")
                    pieces.clicked.connect(lambda _=False, n=name, r=rows: self.ask_pieces(n, r))
                    v.addWidget(pieces)
                v.addWidget(QLabel("\n".join(notes))) if notes else None
                self.cards.addTab(page, name)
                self.tables[name], self.checks[name] = table, check
        finally:
            self._filling = False
        if current:
            for i in range(self.cards.count()):
                if self.cards.tabText(i) == current:
                    self.cards.setCurrentIndex(i)
        has = bool(self.tables)
        self.empty.setVisible(not has); self.cards.setVisible(has)
        self.order.setEnabled(has); self.offer.setEnabled(has)
        self._summary()

    def _summary_page(self, lists):
        """Construction cost: every trade's material, labour, total and unpriced items, with the grand total."""
        from archforge.quantities.quote import money, quote
        page = QWidget(); v = QVBoxLayout(page); v.setContentsMargins(0, 6, 0, 0)
        v.addWidget(QLabel("Κόστος κατασκευής — όλα τα επαγγέλματα με τις τιμές του έργου"))
        table = QTableWidget(len(lists) + 1, 5)
        table.setHorizontalHeaderLabels(["Επάγγελμα", "Υλικά", "Εργασία", "Σύνολο", "Είδη χωρίς τιμή"])
        table.verticalHeader().setVisible(False)
        for i, (name, _t, _r, _n) in enumerate(lists):
            q = quote(self.window.doc, only=(name,))
            for j, text in enumerate((name, money(q["material"]), money(q["labour"]), money(q["subtotal"]), str(q["missing"]))):
                item = QTableWidgetItem(text); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable); table.setItem(i, j, item)
        q = quote(self.window.doc)
        for j, text in enumerate(("Σύνολο (χωρίς ΦΠΑ)", money(q["material"]), money(q["labour"]), money(q["subtotal"]),
                                  str(q["missing"]))):
            item = QTableWidgetItem(text); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            f = item.font(); f.setBold(True); item.setFont(f); table.setItem(len(lists), j, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        v.addWidget(table, 1)
        note = QLabel(f"Με ΦΠΑ {q['vat']:g}%: {money(q['total'])}."
                      + (f" {q['missing']} είδη χωρίς τιμή ή ποσότητα δεν μετράνε στο σύνολο." if q["missing"] else "")
                      + "\nΔεν μετριούνται ακόμη: " + ", ".join(NOT_MEASURED) + " — το σύνολο δεν τα περιλαμβάνει.")
        note.setWordWrap(True); v.addWidget(note)
        self.summary_table = table
        return page

    def _book(self):
        from archforge.quantities.quote import trade_prices
        return trade_prices(self.window.doc)

    def _summary(self):
        from archforge.quantities.quote import money, quote
        names = self.selected_trades()
        if not names:
            self.summary.setText(""); return
        q = quote(self.window.doc, only=tuple(names))
        self.summary.setText(f"{', '.join(names)}: υλικά {money(q['material'])} · εργασία {money(q['labour'])} · "
                             f"ΦΠΑ {q['vat']:g}% · σύνολο {money(q['total'])}"
                             + (f" · {q['missing']} είδη χωρίς τιμή (δεν μετράνε)" if q["missing"] else ""))

    def selected_trades(self):
        """Ticked cards; else the open card; the «Σύνολο έργου» card = every trade (construction cost)."""
        ticked = [n for n, c in self.checks.items() if c.isChecked()]
        if ticked:
            return ticked
        if not self.cards.count():
            return []
        current = self.cards.tabText(self.cards.currentIndex())
        return list(self.tables) if current == SUMMARY else [current]

    # ------------------------------------------------------------------------------------------- price edits
    def _price_edited(self, table, item):
        if self._filling or item.column() not in (3, 4):
            return
        code = table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        key = "material" if item.column() == 3 else "labour"
        text = item.text().strip().replace("€", "").replace(",", ".")
        try:
            value = None if not text else round(float(text), 4)
        except ValueError:
            self.window.statusBar().showMessage(f"«{text}» δεν είναι αριθμός", 6000)
            return
        self.set_price(code, key, value)

    def set_price(self, code, key, value):
        """One UpdateEntity (or AddEntity) on the project's price list."""
        from archforge.core.commands import AddEntity, UpdateEntity
        from archforge.core.model import Entity
        from archforge.quantities.quote import price_entity
        e = price_entity(self.window.doc)
        trade = dict((e.params.get("trade_prices") or {}) if e else {})
        entry = dict(trade.get(code, {}))
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = float(value)
        if entry:
            trade[code] = entry
        else:
            trade.pop(code, None)
        if e is None:
            self.window.stack.execute(AddEntity(Entity("price_list", {"trade_prices": trade}, name="Τιμές & προσφορά")))
        else:
            self.window.stack.execute(UpdateEntity(e.id, {"trade_prices": trade}))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.refresh)

    def ask_pieces(self, name, rows):
        from PySide6.QtWidgets import QInputDialog
        from archforge.quantities.quote import row_meta
        keys = []
        for row in rows:
            desc, _u, _q, meta = row_meta(row)
            code = meta["code"]
            if code.startswith("masonry.") and not code.endswith(".pieces"):
                keys.append((desc, code.split(".", 1)[1]))
            elif code.startswith("roof.tiles.") and not code.endswith(".pieces"):
                keys.append((desc, "tile." + code.split(".")[2]))
        if not keys:
            return None
        desc, ok = QInputDialog.getItem(self, "Τεμάχια ανά m²", "Για ποιο;", [d for d, _k in keys], 0, False)
        if not ok:
            return None
        key = dict(keys)[desc]
        value, ok = QInputDialog.getDouble(self, "Τεμάχια ανά m²", f"{desc}\nτεμάχια ανά m² όπως γράφει το φύλλο του προϊόντος:",
                                           1.0, 0.01, 1000.0, 2)
        return self.set_pieces(key, value) if ok else None

    def set_pieces(self, key, value):
        """Pieces per m² of a brick / tile type, from its data sheet: one undoable change."""
        from archforge.core.commands import AddEntity, UpdateEntity
        from archforge.core.model import Entity
        e = next((x for x in self.window.doc.entities.values() if x.kind == "construction_spec"), None)
        pieces = dict((e.params.get("pieces_per_m2") or {}) if e else {})
        if value:
            pieces[key] = float(value)
        else:
            pieces.pop(key, None)
        if e is None:
            self.window.stack.execute(AddEntity(Entity("construction_spec", {"pieces_per_m2": pieces}, name="Στοιχεία προϊόντων")))
        else:
            self.window.stack.execute(UpdateEntity(e.id, {"pieces_per_m2": pieces}))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.refresh)
        return pieces

    # ----------------------------------------------------------------------------------------------- exports
    def export_order(self, path=None, name=None):
        name = name or self.cards.tabText(self.cards.currentIndex())
        if name == SUMMARY:
            # Whole-project order list: every trade one after the other.
            if path is None:
                path, _f = QFileDialog.getSaveFileName(self, "Λίστα παραγγελίας — όλο το έργο", "paraggelia_ergou.csv", "CSV (*.csv)")
            if not path:
                return None
            with open(path, "w", encoding="utf-8-sig", newline="") as fh:
                fh.write("\n".join(order_csv(n, r) for n, _t, r, _no in self.lists()))
            return path
        rows = next((r for n, _t, r, _no in self.lists() if n == name), [])
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, f"Λίστα παραγγελίας — {name}", f"paraggelia_{name}.csv", "CSV (*.csv)")
        if not path:
            return None
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(order_csv(name, rows))
        return path

    def export_offer(self, path=None):
        from archforge.output.pdf import export_pdf
        names = self.selected_trades()
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, "Προσφορά (PDF)", "prosfora.pdf", "PDF (*.pdf)")
        if not path:
            return None
        return export_pdf(self.window.doc, path, include=("quote",), only=tuple(names))


def install(window):
    """Prepare the page; it joins the central tabs when asked for (like «Τομή»), keeping the approved layout."""
    tab = TradesTab(window)
    window._trades_tab = tab
    window.stack.listeners.append(tab.mark_stale)
    return tab


def show(window, trade=None):
    tab = getattr(window, "_trades_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    tab.refresh()
    if trade:
        for i in range(tab.cards.count()):
            if tab.cards.tabText(i) == trade:
                tab.cards.setCurrentIndex(i)
    return tab
