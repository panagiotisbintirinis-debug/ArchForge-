"""Σχέδια ▸ Φύλλα σχεδίων: φύλλα A4…A0 με κατόψεις, τομές, λίστες και σημειώσεις, πινακίδα, PDF (06/11).

Κάθε αλλαγή (νέο φύλλο, χαρτί, προβολή, κλίμακα, σειρά) = μία αναίρεση στο στοιχείο ``sheet``
(``output/sheets.py``). Η προεπισκόπηση είναι η ίδια σχεδίαση με το PDF.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
                               QListWidgetItem, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout)

from archforge.output import sheets as SH


class SheetsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.doc = window, window.doc
        self.setWindowTitle("Φύλλα σχεδίων")
        self.resize(1250, 780)
        root = QHBoxLayout(self)
        left = QVBoxLayout(); root.addLayout(left, 1)
        left.addWidget(QLabel("Φύλλα"))
        self.sheets = QListWidget(); self.sheets.currentRowChanged.connect(lambda _r: self.show_sheet())
        left.addWidget(self.sheets, 1)
        row = QHBoxLayout()
        b = QPushButton("+ Νέο φύλλο"); b.clicked.connect(self.add_sheet); row.addWidget(b)
        b = QPushButton("Διαγραφή"); b.clicked.connect(self.delete_sheet); row.addWidget(b)
        left.addLayout(row)
        b = QPushButton("Εξαγωγή PDF όλων…"); b.clicked.connect(lambda: self.export()); left.addWidget(b)

        mid = QVBoxLayout(); root.addLayout(mid, 2)
        form = QFormLayout(); mid.addLayout(form)
        self.title = QLineEdit(); self.title.editingFinished.connect(lambda: self.set_param("title", self.title.text()))
        self.number = QLineEdit(); self.number.editingFinished.connect(lambda: self.set_param("number", self.number.text()))
        self.paper = QComboBox(); self.paper.addItems(list(SH.PAPER))
        self.paper.activated.connect(lambda _i: self.set_param("paper", self.paper.currentText()))
        self.orient = QComboBox()
        for k, v in SH.ORIENTATIONS.items():
            self.orient.addItem(v, k)
        self.orient.activated.connect(lambda _i: self.set_param("orientation", self.orient.currentData()))
        form.addRow("Τίτλος", self.title); form.addRow("Αριθμός", self.number)
        form.addRow("Χαρτί", self.paper); form.addRow("Προσανατολισμός", self.orient)
        mid.addWidget(QLabel("Προβολές (μπαίνουν με τη σειρά, σε σειρές)"))
        self.views = QTableWidget(0, 3)
        self.views.setHorizontalHeaderLabels(["Προβολή", "Κλίμακα", "Τίτλος"])
        self.views.horizontalHeader().setStretchLastSection(True)
        self.views.verticalHeader().setVisible(False)
        self.views.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        mid.addWidget(self.views, 1)
        adds = QHBoxLayout()
        for text, fn in (("+ Κάτοψη", self.add_plan), ("+ Τομή", self.add_section), ("+ Λίστα", self.add_list),
                         ("+ Σημείωση", self.add_note)):
            b = QPushButton(text); b.clicked.connect(fn); adds.addWidget(b)
        mid.addLayout(adds)
        moves = QHBoxLayout()
        for text, fn in (("↑", lambda: self.move_view(-1)), ("↓", lambda: self.move_view(1)), ("−", self.remove_view)):
            b = QPushButton(text); b.setFixedWidth(40); b.clicked.connect(fn); moves.addWidget(b)
        moves.addStretch(1)
        mid.addLayout(moves)

        right = QVBoxLayout(); root.addLayout(right, 3)
        self.preview = QLabel(); self.preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll = QScrollArea(); scroll.setWidget(self.preview); scroll.setWidgetResizable(True)
        right.addWidget(scroll, 1)
        self.problems = QLabel(); self.problems.setWordWrap(True); self.problems.setStyleSheet("color:#b91c1c")
        right.addWidget(self.problems)
        self.refresh_list()

    # ------------------------------------------------------------ state
    def sheet(self):
        i = self.sheets.currentRow()
        items = SH.sheets_of(self.doc)
        return items[i] if 0 <= i < len(items) else None

    def refresh_list(self, select=None):
        items = SH.sheets_of(self.doc)
        self.sheets.blockSignals(True)
        self.sheets.clear()
        for e in items:
            self.sheets.addItem(QListWidgetItem(f"{e.params.get('number', '')} · {e.params['title']} ({e.params['paper']})"))
        self.sheets.blockSignals(False)
        ids = [e.id for e in items]
        self.sheets.setCurrentRow(ids.index(select) if select in ids else (0 if ids else -1))
        self.show_sheet()

    def show_sheet(self):
        e = self.sheet()
        for w in (self.title, self.number, self.paper, self.orient, self.views):
            w.setEnabled(e is not None)
        if e is None:
            self.preview.clear(); self.preview.setText("Δεν υπάρχει φύλλο: «+ Νέο φύλλο»"); self.views.setRowCount(0)
            self.problems.clear()
            return None
        p = e.params
        self.title.setText(p["title"]); self.number.setText(p.get("number", ""))
        self.paper.setCurrentText(p["paper"]); self.orient.setCurrentIndex(self.orient.findData(p["orientation"]))
        lay = SH.layout(self.doc, p)
        placed = {id(v): m for v, m, _xy in lay["placed"]}
        self.views.setRowCount(len(p["views"]))
        for r, v in enumerate(p["views"]):
            what = SH.VIEW_TYPES[v["type"]] + (f": {SH.view_title(self.doc, dict(v, title=''))}" if v["type"] != "note"
                                               else f": {v['text'][:30]}")
            self.views.setItem(r, 0, QTableWidgetItem(what))
            if v["type"] in ("plan", "section"):
                box = QComboBox(); box.addItem("αυτόματη", None)
                for s in SH.SCALES:
                    box.addItem(f"1:{s}", s)
                box.setCurrentIndex(max(0, box.findData(v.get("scale"))))
                box.activated.connect(lambda _i, row=r, b=box: self.set_view(row, "scale", b.currentData()))
                self.views.setCellWidget(r, 1, box)
            else:
                self.views.setItem(r, 1, QTableWidgetItem("—"))
            self.views.setItem(r, 2, QTableWidgetItem(v.get("title") or ""))
        img = SH.preview(self.doc, p, 1.6 if p["paper"] in ("A4", "A3") else 0.8)
        self.preview.setPixmap(QPixmap.fromImage(img))
        self.problems.setText(("Δεν μπήκαν: " + " · ".join(t for _v, t in lay["problems"])) if lay["problems"] else
                              (f"Κοινή κλίμακα κατόψεων / τομών: 1:{lay['scale']}" if lay.get("scale") else ""))
        return lay

    # ------------------------------------------------------------ edits (one undo each)
    def _update(self, changes, label="Φύλλο σχεδίου"):
        from archforge.core.commands import UpdateEntity
        e = self.sheet()
        if e is None:
            return None
        try:
            self.window.stack.execute(UpdateEntity(e.id, changes))
        except ValueError as exc:
            self.problems.setText(f"⚠ {exc}")
            return None
        self.refresh_list(select=e.id)
        return e.id

    def set_param(self, key, value):
        e = self.sheet()
        if e is not None and e.params.get(key) != value:
            return self._update({key: value})
        return None

    def set_view(self, row, key, value):
        e = self.sheet()
        views = [dict(v) for v in e.params["views"]]
        views[row][key] = value
        return self._update({"views": views})

    def add_view(self, view):
        e = self.sheet()
        if e is None:
            self.add_sheet()
            e = self.sheet()
        return self._update({"views": [dict(v) for v in e.params["views"]] + [view]})

    def move_view(self, step):
        e = self.sheet()
        rows = sorted({i.row() for i in self.views.selectedIndexes()})
        if e is None or not rows:
            return None
        i, j = rows[0], rows[0] + step
        views = [dict(v) for v in e.params["views"]]
        if not 0 <= j < len(views):
            return None
        views[i], views[j] = views[j], views[i]
        result = self._update({"views": views})
        self.views.selectRow(j)
        return result

    def remove_view(self):
        e = self.sheet()
        rows = sorted({i.row() for i in self.views.selectedIndexes()})
        if e is None or not rows:
            return None
        return self._update({"views": [dict(v) for k, v in enumerate(e.params["views"]) if k != rows[0]]})

    def add_sheet(self, paper="A3"):
        from archforge.core.commands import AddEntity
        e = SH.new_sheet(self.doc, "Φύλλο", paper)
        self.window.stack.execute(AddEntity(e))
        self.refresh_list(select=e.id)
        return e.id

    def delete_sheet(self):
        from archforge.core.commands import DeleteEntities
        e = self.sheet()
        if e is not None:
            self.window.stack.execute(DeleteEntities([e.id]))
            self.refresh_list()

    def _choose(self, title, label, items):
        if getattr(self.window, "_no_modal_dialogs", False):
            return items[0] if items else None
        names = [n for n, _v in items]
        text, ok = QInputDialog.getItem(self, title, label, names, 0, False)
        return next((it for it in items if it[0] == text), None) if ok else None

    def add_plan(self, z=None):
        if z is None:
            from archforge.ui.project_outline import _levels
            items = [(SH._storey_label(self.doc, lz), lz) for _n, lz in _levels(self.doc)] or [("Ισόγειο", 0.0)]
            pick = self._choose("Κάτοψη", "Ποιος όροφος;", items)
            if pick is None:
                return None
            z = pick[1]
        return self.add_view({"type": "plan", "ref": float(z), "scale": None})

    def add_section(self, eid=None):
        if eid is None:
            items = [(e.name or "Τομή", e.id) for e in self.doc.entities.values() if e.kind == "section_line"]
            if not items:
                self.problems.setText("Δεν υπάρχει τομή: σχεδιάστε μία (Προβολή ▾ ▸ Τομή) και ξαναδοκιμάστε.")
                return None
            pick = self._choose("Τομή", "Ποια τομή;", items)
            if pick is None:
                return None
            eid = pick[1]
        return self.add_view({"type": "section", "ref": eid, "scale": None})

    def add_list(self, key=None):
        if key is None:
            from archforge.ui.live_lists import NAMES
            pick = self._choose("Λίστα", "Ποια λίστα;", [(v, k) for k, v in NAMES.items()])
            if pick is None:
                return None
            key = pick[1]
        return self.add_view({"type": "list", "ref": key})

    def add_note(self, text=None):
        if text is None:
            if getattr(self.window, "_no_modal_dialogs", False):
                return None
            text, ok = QInputDialog.getMultiLineText(self, "Σημείωση", "Κείμενο της σημείωσης:")
            if not ok or not text.strip():
                return None
        return self.add_view({"type": "note", "text": text})

    def export(self, path=None):
        if path is None:
            if getattr(self.window, "_no_modal_dialogs", False):
                return None
            from PySide6.QtWidgets import QFileDialog
            path, _f = QFileDialog.getSaveFileName(self, "Φύλλα σχεδίων σε PDF", "Φύλλα.pdf", "PDF (*.pdf)")
            if not path:
                return None
        try:
            r = SH.export_sheets(self.doc, path)
        except ValueError as exc:
            self.problems.setText(f"⚠ {exc}")
            return None
        self.window.statusBar().showMessage(f"Φύλλα σχεδίων: {r['pages']} σελίδες — {path}"
                                            + (" · κάποιες προβολές δεν χώρεσαν (δείτε το φύλλο)" if r["problems"] else ""), 12000)
        return r


def show(window):
    dlg = SheetsDialog(window)
    window._sheets_dialog = dlg
    dlg.show()
    return dlg
