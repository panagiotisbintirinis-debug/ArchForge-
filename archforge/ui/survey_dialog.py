"""«Αποτύπωση από μετρήσεις…» (right click in a room ▸ Σε αυτόν τον χώρο): the measured sides and diagonals of a room
in a table, the corners numbered on the plan, «Υπολογισμός» shows how far each measurement is from the fitted room,
«Εφαρμογή» moves the walls (architecture/survey.py) — one undo."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from archforge.architecture import survey as S
from archforge.core.units import fmt_length

RED = QColor(200, 40, 40)


def _cm(v):
    return f"{v * 100:+.1f} εκ."


class SurveyDialog(QDialog):
    def __init__(self, window, face):
        super().__init__(window)
        self.w = window
        self.room = S.survey_room(window.doc, face)
        self.drawn = S.drawn(self.room["inner"])
        self.result = None
        n = self.room["corners"]
        self.setWindowTitle("Αποτύπωση από μετρήσεις")
        box = QVBoxLayout(self)
        box.addWidget(QLabel(f"Γωνίες 1–{n} στην κάτοψη (εσωτερικές παρειές). Γράψε τις μετρήσεις σε μέτρα "
                             f"(0,05 = 5 εκ.) — πλευρές και όσες διαγωνίους θέλεις· για {n} γωνίες χρειάζονται "
                             f"τουλάχιστον {2 * n - 3}.", self))
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Μέτρηση", "Σχέδιο (m)", "Μετρημένο (m)", "Σφάλμα"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        box.addWidget(self.table)
        self.rows = []                                         # (i, j, spin)
        for i in range(n):
            self._add_row(i, (i + 1) % n)
        diag = QHBoxLayout()
        self.di = QSpinBox(self); self.di.setRange(1, n); self.di.setValue(1)
        self.dj = QSpinBox(self); self.dj.setRange(1, n); self.dj.setValue(3 if n > 3 else 2)
        add = QPushButton("+ Διαγώνιος", self); add.clicked.connect(lambda: self.add_diagonal(self.di.value() - 1,
                                                                                               self.dj.value() - 1))
        diag.addWidget(QLabel("Από γωνία", self)); diag.addWidget(self.di)
        diag.addWidget(QLabel("σε γωνία", self)); diag.addWidget(self.dj); diag.addWidget(add)
        box.addLayout(diag)
        self.info = QLabel("", self)
        box.addWidget(self.info)
        buttons = QHBoxLayout()
        calc = QPushButton("Υπολογισμός", self); calc.clicked.connect(self.compute)
        ok = QPushButton("Εφαρμογή", self); ok.clicked.connect(self.apply)
        close = QPushButton("Κλείσιμο", self); close.clicked.connect(self.close)
        for b in (calc, ok, close):
            buttons.addWidget(b)
        box.addLayout(buttons)
        window.plan_view.survey_tool = self
        window.plan_view.redraw()

    # ---------------------------------------------------------------- rows
    def _label(self, i, j):
        n = self.room["corners"]
        side = j == (i + 1) % n or i == (j + 1) % n
        return f"{'Πλευρά' if side else 'Διαγώνιος'} {i + 1}–{j + 1}"

    def _add_row(self, i, j, value=None):
        r = self.table.rowCount(); self.table.insertRow(r)
        a, b = min(i, j), max(i, j)
        self.table.setItem(r, 0, QTableWidgetItem(self._label(i, j)))
        self.table.setItem(r, 1, QTableWidgetItem(fmt_length(self.drawn[(a, b)], "m")))   # metres, as the measured column
        spin = QDoubleSpinBox(self); spin.setDecimals(3); spin.setRange(0.0, 1000.0); spin.setSingleStep(0.01)
        spin.setSpecialValueText("—")                           # 0 = not measured
        if value is not None:
            spin.setValue(float(value))
        self.table.setCellWidget(r, 2, spin)
        self.table.setItem(r, 3, QTableWidgetItem(""))
        self.rows.append((i, j, spin))
        return r

    def add_diagonal(self, i, j, value=None):
        if i == j or any({a, b} == {i, j} for a, b, _s in self.rows):
            return None
        return self._add_row(i, j, value)

    def set_measure(self, i, j, value):
        """The measured distance between corners i and j (0-based) — a new row for a diagonal."""
        for a, b, spin in self.rows:
            if {a, b} == {i, j}:
                spin.setValue(float(value)); return
        self.add_diagonal(i, j, value)

    def measurements(self):
        return [(i, j, spin.value()) for i, j, spin in self.rows if spin.value() > 0]

    # ---------------------------------------------------------------- solve / apply
    def compute(self):
        try:
            self.result = S.solve(self.room["inner"], self.measurements())
        except ValueError as exc:
            self.info.setText(f"⚠ {exc}"); self.result = None; return None
        by = {frozenset((i, j)): e for i, j, _v, e in self.result["residuals"]}
        worst = max((abs(e) for e in by.values()), default=0.0)
        for r, (i, j, _spin) in enumerate(self.rows):
            e = by.get(frozenset((i, j)))
            item = QTableWidgetItem("" if e is None else _cm(e))
            if e is not None and abs(e) >= 0.01:
                item.setForeground(RED)
            self.table.setItem(r, 3, item)
        if not self.result["rank_ok"]:
            self.info.setText("⚠ Οι μετρήσεις δεν ορίζουν το σχήμα — πρόσθεσε διαγώνιο (π.χ. 1–3).")
        elif worst >= 0.01:
            self.info.setText(f"⚠ Μέγιστο σφάλμα {worst * 100:.1f} εκ. — έλεγξε τη μέτρηση με κόκκινο.")
        else:
            self.info.setText(f"✔ Οι μετρήσεις συμφωνούν (μέγιστο σφάλμα {worst * 100:.1f} εκ.).")
        return self.result

    def apply(self):
        if self.compute() is None or not self.result["rank_ok"]:
            return False
        try:
            self.w.stack.execute(S.apply_command(self.w.doc, self.room, self.result["corners"]))
        except ValueError as exc:
            self.info.setText(f"⚠ {exc}"); return False
        self.w._redraw_views(all_views=True)
        self.w.statusBar().showMessage("Αποτύπωση: οι τοίχοι πήγαν στις μετρήσεις · Ctrl+Z = αναίρεση", 8000)
        self.close()
        return True

    # ---------------------------------------------------------------- plan
    def paint(self, view):
        from PySide6.QtWidgets import QGraphicsTextItem
        for k, (x, y) in enumerate(self.room["inner"]):
            item = view._scene.addText("")
            item.setHtml(f'<span style="background-color:#c82828; color:#ffffff; font-weight:700">&nbsp;{k + 1}&nbsp;</span>')
            item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
            item.setPos(x, y); item.setZValue(60)

    def closeEvent(self, event):
        if getattr(self.w.plan_view, "survey_tool", None) is self:
            self.w.plan_view.survey_tool = None
            self.w.plan_view.redraw()
        super().closeEvent(event)


def open_survey(window, xy):
    """The room under ``xy`` (plan metres), its survey window."""
    from archforge.geometry.regions import point_in_polygon
    face = next((f for f in window.doc.active_room_faces() if xy and point_in_polygon(float(xy[0]), float(xy[1]),
                                                                                       f.polygon)), None)
    if face is None:
        window.statusBar().showMessage("Αποτύπωση: δεξί κλικ μέσα σε κλειστό χώρο", 6000)
        return None
    try:
        dlg = SurveyDialog(window, face)
    except ValueError as exc:
        window.statusBar().showMessage(f"Αποτύπωση: {exc}", 6000)
        return None
    window._survey_dialog = dlg
    dlg.show()
    return dlg
