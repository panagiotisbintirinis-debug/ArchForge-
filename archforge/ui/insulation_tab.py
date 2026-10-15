"""«Μονώσεις»: every surface of the building with its thermal insulation and waterproofing (owner 15/10).

Top: the choice per category of surface (material, thickness, waterproofing system) — one undoable change on
the ``insulation_spec`` entity.  Below: every surface (flat roofs, floors on the ground, tiled roofs, exterior
walls, plasterboard ceilings, wet-room floors) with its area and what it has, from the element itself or from
the choice; «— επιλέξτε» where nothing is chosen.  Click a row: the element is selected in the drawing.
Quantities and prices: «Υλικά & τιμές» ▸ «Μονώσεις».
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

TAB_TITLE = "Μονώσεις"


def _num(v, d=2):
    return f"{v:.{d}f}".replace(".", ",")


class InsulationTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._stale = True
        self._filling = False
        root = QVBoxLayout(self); root.setContentsMargins(10, 8, 10, 8)
        head = QHBoxLayout()
        title = QLabel("Μονώσεις — θερμομόνωση και στεγάνωση ανά επιφάνεια"); title.setStyleSheet("font-weight:600;font-size:15px")
        head.addWidget(title); head.addStretch(1)
        prices = QPushButton("Υλικά && τιμές…")
        prices.clicked.connect(lambda: __import__("archforge.ui.trades_tab", fromlist=["show"]).show(window, "Μονώσεις"))
        head.addWidget(prices)
        root.addLayout(head)
        root.addWidget(QLabel("Επιλογή ανά κατηγορία (ισχύει όπου το στοιχείο δεν έχει δική του σύνθεση):"))
        self.spec = QTableWidget(0, 5)
        self.spec.setHorizontalHeaderLabels(["Κατηγορία", "Θερμομόνωση", "Πάχος", "Στεγάνωση", "Εμβαδόν"])
        self.spec.verticalHeader().setVisible(False)
        root.addWidget(self.spec)
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Επιφάνεια", "Όροφος", "Κατηγορία", "m²", "Θερμομόνωση", "Στεγάνωση", "Από"])
        self.table.verticalHeader().setVisible(False)
        self.table.itemClicked.connect(self._select)
        root.addWidget(self.table, 1)
        self.note = QLabel(); self.note.setWordWrap(True); self.note.setStyleSheet("color:palette(mid);font-size:11px")
        root.addWidget(self.note)

    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def refresh(self):
        from archforge.construction.insulation import (CATEGORIES, NEEDS_WATERPROOFING, THERMAL, WATERPROOFING, spec,
                                                       surfaces, thermal_label)
        self._stale = False
        self._filling = True
        try:
            items = surfaces(self.window.doc)
            chosen = spec(self.window.doc)
            area = {}
            for s in items:
                area[s["category"]] = area.get(s["category"], 0.0) + s["area"]
            cats = [c for c in CATEGORIES if c in area]
            self.spec.clearContents(); self.spec.setRowCount(0)        # drop the previous cell widgets
            self.spec.setRowCount(len(cats))
            for i, cat in enumerate(cats):
                label = QTableWidgetItem(CATEGORIES[cat]); label.setFlags(label.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.spec.setItem(i, 0, label)
                thermal = QComboBox(); thermal.addItem("— επιλέξτε", None)
                for k, v in THERMAL.items():
                    thermal.addItem(v, k)
                thermal.setCurrentIndex(max(0, thermal.findData(chosen[cat]["thermal"])) if chosen[cat]["thermal"] else 0)
                thermal.activated.connect(lambda _i, w=thermal, c=cat: self.set_choice(c, "thermal", w.currentData()))
                self.spec.setCellWidget(i, 1, thermal)
                thick = QDoubleSpinBox(); thick.setRange(0.0, 50.0); thick.setDecimals(1); thick.setSuffix(" cm")
                thick.setSpecialValueText("— από το φύλλο"); thick.setValue((chosen[cat]["thickness"] or 0.0) * 100)
                thick.editingFinished.connect(lambda w=thick, c=cat: self.set_choice(c, "thickness", w.value() / 100 or None))
                self.spec.setCellWidget(i, 2, thick)
                if cat in NEEDS_WATERPROOFING:
                    wp = QComboBox(); wp.addItem("— επιλέξτε", None)
                    for k, v in WATERPROOFING.items():
                        wp.addItem(v, k)
                    wp.setCurrentIndex(max(0, wp.findData(chosen[cat]["waterproofing"])) if chosen[cat]["waterproofing"] else 0)
                    wp.activated.connect(lambda _i, w=wp, c=cat: self.set_choice(c, "waterproofing", w.currentData()))
                    self.spec.setCellWidget(i, 3, wp)
                else:
                    self.spec.setItem(i, 3, QTableWidgetItem("—"))
                self.spec.setItem(i, 4, QTableWidgetItem(f"{_num(area[cat])} m²"))
            self.spec.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.spec.setFixedHeight(28 + 30 * max(1, len(cats)))
            self.table.setRowCount(len(items))
            for i, s in enumerate(items):
                thermal = (f"{thermal_label(s['thermal'])}" + (f" {_num(s['thickness'] * 100, 1)} cm" if s["thickness"] else "")
                           if s["thermal"] else "— επιλέξτε")
                wp = (WATERPROOFING.get(s["waterproofing"], s["waterproofing"]) if s["waterproofing"]
                      else ("— επιλέξτε" if s["category"] in NEEDS_WATERPROOFING else "—"))
                cells = [s["label"], s["storey"] or "—", CATEGORIES[s["category"]], _num(s["area"]), thermal, wp,
                         "στοιχείο" if s["source"] == "element" else "επιλογή κατηγορίας"]
                for j, text in enumerate(cells):
                    item = QTableWidgetItem(str(text)); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if text == "— επιλέξτε":
                        item.setForeground(Qt.GlobalColor.darkYellow)
                    self.table.setItem(i, j, item)
                self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, s["element"])
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            self.table.horizontalHeader().setStretchLastSection(True)
            missing = sum(1 for s in items if not s["thermal"]) + sum(1 for s in items if s["category"] in NEEDS_WATERPROOFING
                                                                       and not s["waterproofing"])
            self.note.setText(f"{len(items)} επιφάνειες · {missing} επιλογές λείπουν. Εμβαδά από το σχέδιο· υλικό, πάχος και "
                              "σύστημα στεγάνωσης είναι επιλογή του μελετητή — το πρόγραμμα δεν βάζει τιμές λ, U ή πάχη "
                              "(ενεργειακή μελέτη ΚΕΝΑΚ από μηχανικό).")
            self.items = items
        finally:
            self._filling = False
        return self.items

    def set_choice(self, category, key, value):
        """One UpdateEntity (or AddEntity) on the project's insulation choice."""
        if self._filling:
            return
        from archforge.construction.insulation import spec_entity
        from archforge.core.commands import AddEntity, UpdateEntity
        from archforge.core.model import Entity
        e = spec_entity(self.window.doc)
        cats = {c: dict(v) for c, v in ((e.params.get("categories") or {}) if e else {}).items()}
        entry = cats.setdefault(category, {})
        if value is None:
            entry.pop(key, None)
        else:
            entry[key] = value
        if e is None:
            self.window.stack.execute(AddEntity(Entity("insulation_spec", {"categories": cats}, name="Μονώσεις")))
        else:
            self.window.stack.execute(UpdateEntity(e.id, {"categories": cats}))
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.refresh)

    def _select(self, item):
        eid = self.table.item(item.row(), 0).data(Qt.ItemDataRole.UserRole)
        if eid and eid in self.window.doc.entities:
            self.window.doc.select([eid]); self.window.refresh_inspector(); self.window._redraw_views(all_views=True)


def install(window):
    tab = InsulationTab(window)
    window._insulation_tab = tab
    window.stack.listeners.append(tab.mark_stale)
    return tab


def show(window):
    tab = getattr(window, "_insulation_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    tab.refresh()
    return tab
