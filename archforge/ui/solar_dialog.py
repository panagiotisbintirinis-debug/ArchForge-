"""Σχέδια ▸ Ηλιασμός κουφωμάτων: ώρες άμεσου ήλιου και σκίαση κάθε παραθύρου / πόρτας ανά μήνα (06/11).

Θέση (γεωγραφικό πλάτος) και βορράς του έργου αλλάζουν εδώ — μία αναίρεση. Ο υπολογισμός είναι ``site/solar_study.py``.
Κλικ σε γραμμή = το κούφωμα επιλέγεται στο σχέδιο.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from archforge.site import solar_study as SS


def _num(v, d=1):
    return "—" if v is None else f"{v:.{d}f}".replace(".", ",")


class SolarDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.doc = window, window.doc
        self.result = None
        self.setWindowTitle("Ηλιασμός κουφωμάτων")
        self.resize(900, 620)
        lay = QVBoxLayout(self)
        top = QHBoxLayout(); lay.addLayout(top)
        self.month = QComboBox()
        for i, m in enumerate(SS.MONTHS, 1):
            self.month.addItem(m, i)
        self.month.setCurrentIndex(11)
        s = SS.site(self.doc)
        self.lat = QDoubleSpinBox(); self.lat.setRange(-66, 66); self.lat.setDecimals(2); self.lat.setSuffix("° Β")
        self.lat.setValue(s["latitude"])
        self.north = QDoubleSpinBox(); self.north.setRange(0, 359.9); self.north.setDecimals(1); self.north.setSuffix("°")
        self.north.setValue(s["north_deg"])
        self.north.setToolTip("Πόσες μοίρες δεξιόστροφα από το «πάνω» (+y) της κάτοψης δείχνει ο πραγματικός βορράς")
        for w in (QLabel("Μήνας"), self.month, QLabel("Γεωγρ. πλάτος"), self.lat, QLabel("Βορράς από το +y"), self.north):
            top.addWidget(w)
        save = QPushButton("Κράτα θέση / βορρά"); save.clicked.connect(self.save_site); top.addWidget(save)
        run = QPushButton("Υπολογισμός"); run.clicked.connect(self.run); top.addWidget(run)
        top.addStretch(1)
        self.note = QLabel(); self.note.setWordWrap(True); self.note.setStyleSheet("color:palette(mid);font-size:11px")
        lay.addWidget(self.note)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Κούφωμα", "Όροφος", "Βλέπει", "Ώρες ήλιου", "Δυνατές", "Σκίαση %",
                                              "Από", "Έως"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._select)
        lay.addWidget(self.table, 1)
        self.summary = QLabel(); self.summary.setWordWrap(True); lay.addWidget(self.summary)
        self._say()

    def _say(self):
        s = SS.site(self.doc)
        self.note.setText("Ηλιακή ώρα (όχι ώρα ρολογιού), μέση μέρα του μήνα, ακτίνες κάθε "
                          f"{SS.STEP_MIN} λεπτά από 9 σημεία κάθε κουφώματος απέναντι στο μοντέλο 3D (κτίριο, φυτά, "
                          "έδαφος· όχι γειτονικά κτίρια)."
                          + (" Προεπιλογές: " + ", ".join(s["assumed"]) + "." if s["assumed"] else ""))

    def save_site(self):
        cmd = SS.set_site_command(self.doc, self.lat.value(), self.north.value())
        self.window.stack.execute(cmd)
        self._say()
        self.window.statusBar().showMessage("Ηλιασμός: θέση και βορράς του έργου · Ctrl+Z = αναίρεση", 6000)

    def run(self):
        s = SS.site(self.doc)
        if abs(s["latitude"] - self.lat.value()) > 1e-9 or abs(s["north_deg"] - self.north.value()) > 1e-9:
            self.save_site()
        self.result = SS.study(self.doc, int(self.month.currentData()))
        rows = self.result["rows"]
        self.table.setRowCount(len(rows))
        from archforge.quantities.schedules import _storey
        for r, row in enumerate(rows):
            e = self.doc.get(row["id"])
            name = (e.params.get("mark") or e.name or ("Παράθυρο" if row["kind"] == "window" else "Πόρτα")) if e else row["id"]
            cells = [name, _storey(self.doc, row["storey_z"]), row["facing"], _num(row["sun_h"]), _num(row["possible_h"]),
                     _num(row["shaded_pct"], 0), SS.hhmm(row["first"]), SS.hhmm(row["last"])]
            for c, text in enumerate(cells):
                it = QTableWidgetItem(text); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.table.setItem(r, c, it)
        by = {}
        for row in rows:
            by.setdefault(row["facing"], []).append(row["sun_h"])
        self.summary.setText(f"{SS.MONTHS[self.result['month'] - 1]}: μέρα {_num(self.result['day_h'])} ώρες · "
                             + " · ".join(f"{k}: {_num(sum(v) / len(v))} ώρες κατά μέσο όρο ({len(v)})"
                                          for k, v in sorted(by.items(), key=lambda kv: SS.COMPASS.index(kv[0]))))
        return self.result

    def _select(self):
        ids = {i.data(Qt.ItemDataRole.UserRole) for i in self.table.selectedItems()}
        ids = [i for i in ids if i in self.doc.entities]
        if ids:
            self.doc.select(ids)
            self.window._redraw_views(all_views=True)
            self.window.refresh_inspector()


def show(window):
    dlg = SolarDialog(window)
    window._solar_dialog = dlg
    dlg.show()
    return dlg
