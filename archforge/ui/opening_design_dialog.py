"""«Σχεδιασμός κουφώματος» — solver πάνω στους πίνακες της ΤΟΤΕΕ 20701-2/2021 (ιδιοκτήτης 05/11).

Για ένα κούφωμα (πλάτος × ύψος, πλάτος πλαισίου, κουτί ρολού αν έχει) και έναν στόχο «Uw ≤» (η απαίτηση του κουφώματος
ή το Umax του Πίν. 5α / 5β για τη ζώνη και το είδος του έργου): κάθε συνδυασμός πλαισίου (Πίν. 10) × υαλοπίνακα (Πίν. 9)
× αποστάτη (Πίν. 11α/β) με το Uw του (σχέση 2.10 / 2.17). Πλαίσια με εύρος στον Πίν. 10 δείχνουν το μέγιστο Uf που
πρέπει να δηλώνει ο κατασκευαστής. «Εφαρμογή»: υλικό πλαισίου, υαλοπίνακας, αποστάτης, πλάτος πλαισίου στο κούφωμα —
μία αναίρεση. Τιμές κατασκευαστή που υπάρχουν ήδη στο κούφωμα υπερισχύουν, όπως ορίζει η ΤΟΤΕΕ.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)

from archforge.mep import opening_thermal as O
from archforge.mep import totee_20701_2_2021 as T

GROUPS = {"": "Όλα τα πλαίσια", "metal": "Μεταλλικά", "synthetic": "Συνθετικά", "wood": "Ξύλινα"}


def _num(v, d=2):
    return "—" if v is None else f"{v:.{d}f}".replace(".", ",")


class OpeningDesignDialog(QDialog):
    def __init__(self, window, opening_id):
        super().__init__(window)
        self.window, self.doc = window, window.doc
        self.opening_id = opening_id
        o = self.doc.get(opening_id)
        p = o.params
        self.setWindowTitle("Σχεδιασμός κουφώματος — ΤΟΤΕΕ 20701-2/2021 (Πίν. 9–12, σχ. 2.10 / 2.17)")
        self.setMinimumSize(1050, 620)
        lay = QVBoxLayout(self)
        used, src = O.uw(self.doc, o)
        mark = p.get("mark") or ("Π" if o.kind == "window" else "Θ")
        lay.addWidget(QLabel(f"{mark} · {float(p.get('width', 0)):.2f} × {float(p.get('height', 0)):.2f} m".replace(".", ",")
                             + f" · Uw σήμερα {_num(used)} ({src or 'δεν υπολογίστηκε'})"))
        form = QFormLayout(); lay.addLayout(form)
        limit, limit_src = T.u_max_project(self.doc, "opening")
        self.target = QDoubleSpinBox(); self.target.setRange(0.3, 7.0); self.target.setDecimals(2); self.target.setSuffix(" W/m²K")
        self.target.setValue(float(p.get("uw_required") or limit or 1.6))
        self.target_note = QLabel("απαίτηση του κουφώματος" if p.get("uw_required") else
                                  (f"Umax {limit_src}" if limit else "χωρίς ζώνη στο έργο: δώστε στόχο"))
        row = QHBoxLayout(); row.addWidget(self.target); row.addWidget(self.target_note); row.addStretch(1)
        form.addRow("Στόχος Uw ≤", row)
        self.frame_width = QDoubleSpinBox(); self.frame_width.setRange(0.0, 30.0); self.frame_width.setDecimals(1)
        self.frame_width.setSuffix(" cm"); self.frame_width.setSpecialValueText("— δώστε το πλάτος πλαισίου")
        self.frame_width.setValue(float(p.get("frame_width") or 0) * 100)
        form.addRow("Ορατό πλάτος πλαισίου", self.frame_width)
        filters = QHBoxLayout()
        self.group = QComboBox()
        for k, label in GROUPS.items():
            self.group.addItem(label, k)
        self.gas = QComboBox(); self.gas.addItem("Όλα τα αέρια", "")
        for k, label in T.GAS_LABEL.items():
            self.gas.addItem(label, k)
        self.spacer = QComboBox(); self.spacer.addItem("Κάθε αποστάτης", "")
        for k, label in T.SPACERS.items():
            self.spacer.addItem(label, k)
        self.only_ok = QCheckBox("Μόνο όσα πετυχαίνουν τον στόχο"); self.only_ok.setChecked(True)
        self.one_per_frame = QCheckBox("Ένας ανά πλαίσιο (ο απλούστερος που αρκεί)"); self.one_per_frame.setChecked(True)
        for w in (self.group, self.gas, self.spacer, self.only_ok, self.one_per_frame):
            filters.addWidget(w)
        filters.addStretch(1)
        form.addRow("Φίλτρα", filters)
        usb, box, _t = O._box(o)
        self.usb, self.box = usb, box
        if box:
            lay.addWidget(QLabel(f"Με κουτί ρολού: Usb {_num(usb)} σε ύψος {box * 100:.0f} cm (σχέση 2.17)"))
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Πλαίσιο (Πίν. 10)", "Υαλοπίνακας (Πίν. 9)", "Αποστάτης", "Uf", "Ug", "Ψg",
                                              "Uw", "Περιθώριο", "Uf ≤ (κατασκευαστή)"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in range(2, 9):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lay.addWidget(self.table, 1)
        self.note = QLabel(); self.note.setWordWrap(True); self.note.setStyleSheet("color:palette(mid);font-size:11px")
        lay.addWidget(self.note)
        buttons = QHBoxLayout(); buttons.addStretch(1)
        self.apply_btn = QPushButton("Εφαρμογή στο κούφωμα"); self.apply_btn.clicked.connect(self.apply)
        close = QPushButton("Κλείσιμο"); close.clicked.connect(self.reject)
        buttons.addWidget(self.apply_btn); buttons.addWidget(close)
        lay.addLayout(buttons)
        self.options = []
        for w in (self.target, self.frame_width):
            w.valueChanged.connect(self.solve)
        for w in (self.group, self.gas, self.spacer):
            w.currentIndexChanged.connect(self.solve)
        self.only_ok.toggled.connect(self.solve)
        self.one_per_frame.toggled.connect(self.solve)
        self.solve()

    def solve(self, *_):
        o = self.doc.get(self.opening_id)
        bf = self.frame_width.value() / 100.0
        self.table.setRowCount(0)
        self.options = []
        if bf <= 0:
            self.note.setText("Δώστε το ορατό πλάτος πλαισίου (από το φύλλο του κατασκευαστή): η ΤΟΤΕΕ δεν το ορίζει.")
            return []
        group = self.group.currentData()
        frames = [k for k, v in T.TABLE_10.items() if not group or v[0].startswith(group)]
        gases = (self.gas.currentData(),) if self.gas.currentData() else tuple(T.GAS_LABEL)
        spacers = (self.spacer.currentData(),) if self.spacer.currentData() else tuple(T.SPACERS)
        try:
            opts = O.design(o.params.get("width", 1.0), o.params.get("height", 1.0), bf, self.target.value(), frames,
                            gases, spacers, box=self.box, usb=self.usb)
        except ValueError as exc:
            self.note.setText(str(exc))
            return []
        if self.only_ok.isChecked():
            opts = [x for x in opts if x["ok"]]
        if self.one_per_frame.isChecked():
            seen, first = set(), []
            for x in opts:
                if x["frame"] not in seen:
                    seen.add(x["frame"]); first.append(x)
            opts = first
        self.options = opts
        self.table.setRowCount(len(opts))
        target = self.target.value()
        for r, x in enumerate(opts):
            frame = T.TABLE_10[x["frame"]]
            cells = [frame[1], T.glazing_short(x["glazing"]), "βελτιωμένος" if x["spacer"] == "warm" else "συνήθης",
                     _num(x["uf"]) if x["uf"] is not None else f"{frame[2][0]:g}–{frame[2][1]:g}".replace(".", ","),
                     _num(x["ug"], 1), _num(x["psi_g"]), _num(x["uw"]),
                     _num(target - x["uw"]) if x["uw"] is not None else "",
                     _num(x["uf_needed"]) if x["uf_needed"] is not None else ""]
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if c == 6 and x["uw"] is not None:
                    it.setForeground(QColor("#2e7d32") if x["ok"] else QColor("#c62828"))
                self.table.setItem(r, c, it)
        n_ok = sum(1 for x in opts if x["ok"])
        self.note.setText(f"{len(opts)} συνδυασμοί ({n_ok} πετυχαίνουν Uw ≤ {_num(target)}). Πρώτα όσοι περνούν με Uf του "
                          "Πίν. 10: η συνηθέστερη σύνθεση (διπλός πριν από τριπλό, αέρας / αργό πριν από κρυπτό, συνήθης "
                          "αποστάτης), μετά το μικρότερο περιθώριο· μετά τα πλαίσια με εύρος στον "
                          "Πίν. 10, με το μέγιστο Uf που πρέπει να δηλώνει ο κατασκευαστής. Τιμές ενδεικτικές της ΤΟΤΕΕ "
                          "(πηγή ΕΝ ISO 10077-1): η δήλωση επιδόσεων του κατασκευαστή υπερισχύει.")
        if opts:
            self.table.selectRow(0)
        return opts

    def apply(self, index=None):
        """Frame material, glazing, spacer and frame width of the chosen row on the opening — one undo."""
        from archforge.core.commands import CompositeCommand, UpdateEntity
        if index is None:
            rows = {i.row() for i in self.table.selectedItems()}
            index = min(rows) if rows else None
        if index is None or not (0 <= index < len(self.options)):
            return None
        x = self.options[index]
        cmd = UpdateEntity(self.opening_id, {"frame_material": x["frame"], "glazing": x["glazing"], "spacer": x["spacer"],
                                             "frame_width": self.frame_width.value() / 100.0})
        self.window.stack.execute(CompositeCommand([cmd], label="Σχεδιασμός κουφώματος (ΤΟΤΕΕ)"))
        o = self.doc.get(self.opening_id)
        maker = [k for k in ("u_value", "uf", "ug", "psi_g") if o.params.get(k)]
        used, src = O.uw(self.doc, o)
        msg = f"Κούφωμα: Uw {_num(used)} ({src})" + (f" · υπερισχύουν τα στοιχεία κατασκευαστή: {', '.join(maker)}"
                                                       if maker else "") + " · Ctrl+Z = αναίρεση"
        self.window.statusBar().showMessage(msg, 10000)
        self.note.setText(msg)
        return x


def open_for(window, opening_id):
    dlg = OpeningDesignDialog(window, opening_id)
    dlg.show()
    return dlg
