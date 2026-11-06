"""Σχέδια ▸ Ήλιος και άνεμος (06/11): ηλιασμός κουφωμάτων, άνεμος της περιοχής, μπαλκόνια.

* Κουφώματα: ώρες άμεσου ήλιου και σκίαση κάθε παραθύρου / πόρτας ανά μήνα (``site/solar_study.py``).
* Άνεμος: ο σταθμός της ΤΟΤΕΕ 20701-3 του έργου, επικρατούσα διεύθυνση / μποφόρ / m/s και θερμοκρασίες Ιαν, Φεβ, Ιουλ,
  Αυγ, πυξίδα με τον βορρά και τους ανέμους πάνω στην κάτοψη· δική σας διεύθυνση χειμώνα / καλοκαιριού (``site/wind.py``).
* Μπαλκόνια: έκθεση στον άνεμο, ώρες ήλιου και θερμοκρασίες ανά μήνα.
Θέση, βορράς και άνεμος αλλάζουν εδώ — μία αναίρεση η καθεμία. Κλικ σε γραμμή = το στοιχείο επιλέγεται στο σχέδιο.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QPushButton,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from archforge.site import solar_study as SS
from archforge.site import wind as W


def _num(v, d=1):
    return "—" if v is None else f"{v:.{d}f}".replace(".", ",")


class SolarDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window, self.doc = window, window.doc
        self.result = None
        self.setWindowTitle("Ήλιος και άνεμος")
        self.resize(1000, 680)
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
        self.tabs = QTabWidget(); lay.addWidget(self.tabs, 1)
        page = QWidget(); pl = QVBoxLayout(page); self.tabs.addTab(page, "Κουφώματα (ήλιος)")
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["Κούφωμα", "Όροφος", "Βλέπει", "Ώρες ήλιου", "Δυνατές", "Σκίαση %",
                                              "Από", "Έως"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._select)
        pl.addWidget(self.table, 1)
        self.summary = QLabel(); self.summary.setWordWrap(True); pl.addWidget(self.summary)
        self._wind_page()
        self._balcony_page()
        self._say()
        self.show_wind()

    # ------------------------------------------------------------ wind
    def _wind_page(self):
        page = QWidget(); lay = QHBoxLayout(page); self.tabs.addTab(page, "Άνεμος")
        left = QVBoxLayout(); lay.addLayout(left, 2)
        self.station = QLabel(); self.station.setWordWrap(True); left.addWidget(self.station)
        self.wind_table = QTableWidget(0, 8)
        self.wind_table.setHorizontalHeaderLabels(["Μήνας", "Από", "Μποφόρ", "m/s", "Μέση ελάχ. °C", "Μέση μέγ. °C",
                                                   "Απόλυτη ελάχ. / μέγ.", "Πηγή"])
        self.wind_table.verticalHeader().setVisible(False)
        self.wind_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.wind_table.horizontalHeader().setStretchLastSection(True)
        left.addWidget(self.wind_table, 1)
        own = QHBoxLayout(); left.addLayout(own)
        self.winter_dir, self.summer_dir = QComboBox(), QComboBox()
        for box in (self.winter_dir, self.summer_dir):
            box.addItem("όπως η ΤΟΤΕΕ", "")
            for d in W.TS.DIRECTIONS:
                box.addItem(d, d)
        for w in (QLabel("Δική σας διεύθυνση — χειμώνας"), self.winter_dir, QLabel("καλοκαίρι"), self.summer_dir):
            own.addWidget(w)
        keep = QPushButton("Κράτα"); keep.clicked.connect(self.save_wind); own.addWidget(keep); own.addStretch(1)
        self.compass = Compass(); lay.addWidget(self.compass, 1)

    def show_wind(self):
        cl = W.climate(self.doc)
        s = SS.site(self.doc)
        st = cl["station"]
        lat = f"{s['latitude']:.2f}".replace(".", ",")
        self.station.setText((f"Σταθμός: {st} · γεωγραφικό πλάτος {lat}° ({s['latitude_from']})"
                              if st else "Χωρίς σταθμό ΤΟΤΕΕ (δική σας θερμοκρασία σχεδιασμού).")
                             + (" · " + " · ".join(cl["notes"]) if cl["notes"] else ""))
        self.wind_table.setRowCount(len(cl["months"]))
        num = lambda v, d=1: "—" if v is None else f"{v:.{d}f}".replace(".", ",")
        for r, (m, w) in enumerate(cl["months"].items()):
            cells = [W.MONTH_NAMES[m], w["dir"] or "—", num(w["bf"]), num(w["ms"]), num(w["mean_min"]), num(w["mean_max"]),
                     f"{num(w['abs_min'])} / {num(w['abs_max'])}", w["from"] or "—"]
            for c, t in enumerate(cells):
                it = QTableWidgetItem(t); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.wind_table.setItem(r, c, it)
        from archforge.mep.design_climate import entity
        own = dict(entity(self.doc).params) if entity(self.doc) is not None else {}
        self.winter_dir.setCurrentIndex(max(0, self.winter_dir.findData(own.get("wind_dir_winter") or "")))
        self.summer_dir.setCurrentIndex(max(0, self.summer_dir.findData(own.get("wind_dir_summer") or "")))
        self.compass.set_state(s["north_deg"], cl["months"][1]["dir"], cl["months"][7]["dir"])
        return cl

    def save_wind(self):
        self.window.stack.execute(W.set_command(self.doc, self.winter_dir.currentData(), self.summer_dir.currentData()))
        self.window.statusBar().showMessage("Άνεμος του έργου · Ctrl+Z = αναίρεση", 6000)
        return self.show_wind()

    # ------------------------------------------------------------ balconies
    def _balcony_page(self):
        page = QWidget(); lay = QVBoxLayout(page); self.tabs.addTab(page, "Μπαλκόνια")
        row = QHBoxLayout(); lay.addLayout(row)
        run = QPushButton("Υπολογισμός μπαλκονιών"); run.clicked.connect(self.run_balconies); row.addWidget(run)
        row.addWidget(QLabel("Ιανουάριος, Φεβρουάριος (χειμώνας) · Ιούλιος, Αύγουστος (καλοκαίρι): οι μήνες της ΤΟΤΕΕ 20701-3 Παρ. Α"))
        row.addStretch(1)
        self.balcony_table = QTableWidget(0, 8)
        self.balcony_table.setHorizontalHeaderLabels(["Μπαλκόνι", "Μήνας", "Άνεμος από", "Έκθεση", "Ώρες ήλιου",
                                                      "Μέση ελάχ. °C", "Μέση μέγ. °C", "Πηγή ανέμου"])
        self.balcony_table.verticalHeader().setVisible(False)
        self.balcony_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.balcony_table.horizontalHeader().setStretchLastSection(True)
        self.balcony_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.balcony_table.itemSelectionChanged.connect(lambda: self._select(self.balcony_table))
        lay.addWidget(self.balcony_table, 1)
        self.balcony_note = QLabel(); self.balcony_note.setWordWrap(True); lay.addWidget(self.balcony_note)

    def run_balconies(self):
        res = W.balcony_study(self.doc)
        rows = res["rows"]
        self.balcony_table.setRowCount(len(rows))
        num = lambda v, d=1: "—" if v is None else f"{v:.{d}f}".replace(".", ",")
        from archforge.quantities.schedules import _storey
        names = {}
        for row in rows:
            names.setdefault(row["id"], f"Μπαλκόνι {len(names) + 1} ({_storey(self.doc, row['level'])})")
        for r, row in enumerate(rows):
            w = row["wind"]
            wind = "—" if not w["dir"] else (f"{w['dir']} {num(w['bf'])} Bf" + (f" · {num(w['ms'])} m/s" if w["ms"] else ""))
            cells = [names[row["id"]], W.MONTH_NAMES[row["month"]], wind, row["exposure"] or "—", num(row["sun_h"]),
                     num(w["mean_min"]), num(w["mean_max"]), w["from"] or "—"]
            for c, t in enumerate(cells):
                it = QTableWidgetItem(t); it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                it.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.balcony_table.setItem(r, c, it)
        self.balcony_note.setText("Κανένα μπαλκόνι στο έργο (Κατασκευή ▸ Μπαλκόνι)." if not rows else
                                  "Έκθεση: πλευρά με κάγκελο που κοιτά ως 67,5° από τον άνεμο = εκτεθειμένο· το κτίριο "
                                  "ανάμεσα (ως 15 m) = προστατευμένο. Θερμοκρασίες του σταθμού, όχι του μπαλκονιού.")
        return res

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

    def _select(self, table=None):
        table = table if table is not None else self.table
        ids = {i.data(Qt.ItemDataRole.UserRole) for i in table.selectedItems()}
        ids = [i for i in ids if i in self.doc.entities]
        if ids:
            self.doc.select(ids)
            self.window._redraw_views(all_views=True)
            self.window.refresh_inspector()


class Compass(QWidget):
    """The plan's north and the prevailing winds, drawn as the plan is turned (up = the plan's +y)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(220, 220)
        self.north, self.winter, self.summer = 0.0, None, None

    def set_state(self, north_deg, winter, summer):
        self.north, self.winter, self.summer = float(north_deg), winter, summer
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2); r = min(self.width(), self.height()) / 2 - 24
        p.setPen(QPen(QColor(150, 150, 150), 1)); p.drawEllipse(c, r, r)

        def at(true_deg, k):           # screen point at true azimuth (plan up = +y; true north = north_deg clockwise)
            a = math.radians(true_deg + self.north)
            return QPointF(c.x() + k * r * math.sin(a), c.y() - k * r * math.cos(a))
        tip = at(0, 1.0)
        p.setPen(QPen(QColor(30, 30, 30), 1.5)); p.setBrush(QColor(30, 30, 30))
        p.drawPolygon(QPolygonF([tip, at(-8, 0.72), at(8, 0.72)])); p.drawLine(c, tip)
        p.drawText(at(0, 1.18) - QPointF(5, -5), "Β")
        arrows = [(self.winter, QColor(30, 100, 210), "χειμώνας"), (self.summer, QColor(220, 120, 20), "καλοκαίρι")]
        if self.winter and self.winter == self.summer:                 # one arrow, one label
            arrows = [(self.winter, QColor(110, 60, 160), "χειμώνας και καλοκαίρι")]
        for i, (d, colour, label) in enumerate(arrows):
            if not d:
                continue
            deg = W.TS.DIRECTION_DEG[d]
            start, end = at(deg, 0.95), at(deg, 0.25)              # the wind comes FROM its direction
            p.setPen(QPen(colour, 3)); p.drawLine(start, end)
            v = end - start; L = math.hypot(v.x(), v.y()) or 1.0; ux, uy = v.x() / L, v.y() / L
            head = QPolygonF([end, end - QPointF(ux * 12 - uy * 6, uy * 12 + ux * 6), end - QPointF(ux * 12 + uy * 6, uy * 12 - ux * 6)])
            p.setBrush(colour); p.drawPolygon(head)
            # The label in the widget's corner (never clipped), in the arrow's colour.
            p.drawText(QPointF(6, self.height() - 8 - 16 * i), f"Άνεμος από {d}: {label}")
        p.end()


def show(window):
    dlg = SolarDialog(window)
    window._solar_dialog = dlg
    dlg.show()
    return dlg
