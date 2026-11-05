"""«Λίστες» (κριτική v5 k9): καρτέλα που ανοίγει όταν τη ζητάς — όχι παράθυρο που κλειδώνει, όχι μόνιμος χάρτης.

Πάνω: Κουφώματα · Κέλυφος · Χώροι · Κυκλώματα (``quantities/schedules.py``). Κάθε γραμμή έχει «Πώς μετρήθηκε».
Ζωντανή: ξαναγράφεται 250 ms μετά από κάθε αλλαγή/αναίρεση. Αμφίδρομη επιλογή: κλικ σε γραμμή → τα αντικείμενά της
επιλέγονται στο σχέδιο· επιλογή στο σχέδιο → οι γραμμές τους φωτίζονται. Γράφεται επιτόπου: κωδικός κουφώματος
(Π1, Θ1…) και όνομα χώρου (το όνομα δίνει και τη χρήση: «Μπάνιο» → πλακάκια τοίχου), καθένα με μία αναίρεση.
Πάνω από τη λίστα ο έλεγχος πληρότητας: ό,τι λείπει για να είναι σωστή, αντί για λάθος ποσότητα σιωπηλά.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QTabBar, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from archforge.quantities import schedules as S

TAB_TITLE = "Λίστες"
NAMES = {"openings": "Κουφώματα", "envelope": "Κέλυφος", "rooms": "Χώροι", "circuits": "Κυκλώματα"}


def _text(v):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:g}".replace(".", ",")
    return str(v)


class ListsTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.setObjectName("live_lists_tab")
        self.key = "openings"
        self.data = None
        self._filling = False
        root = QVBoxLayout(self); root.setContentsMargins(10, 8, 10, 8); root.setSpacing(6)
        self.bar = QTabBar(self)
        for key, name in NAMES.items():
            self.bar.addTab(name)
        self.bar.currentChanged.connect(self._choose)
        root.addWidget(self.bar)
        self.check = QLabel(self); self.check.setWordWrap(True); self.check.setStyleSheet("color:#b45309")
        root.addWidget(self.check)
        self.table = QTableWidget(0, 0, self)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._rows_selected)
        self.table.itemChanged.connect(self._edited)
        root.addWidget(self.table, 1)
        foot = QHBoxLayout()
        self.total = QLabel(self); self.total.setStyleSheet("font-weight:600")
        self.live = QLabel(self); self.live.setStyleSheet("color:palette(mid);font-size:11px")
        foot.addWidget(self.total); foot.addStretch(1); foot.addWidget(self.live)
        from PySide6.QtWidgets import QPushButton
        for text, run in (("PDF αυτής της λίστας…", lambda: self.export_pdf(keys=[self.key])),
                          ("PDF όλων…", lambda: self.export_pdf()), ("Excel όλων…", lambda: self.export_xlsx())):
            b = QPushButton(text, self); b.clicked.connect(lambda _=False, r=run: r()); foot.addWidget(b)
        root.addLayout(foot)
        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.setInterval(250)
        self._timer.timeout.connect(self.refresh)
        self._stale = True

    # ------------------------------------------------------------ live
    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self._timer.start()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def _choose(self, index):
        self.key = list(NAMES)[index]
        self.refresh()

    def show_list(self, key):
        self.bar.setCurrentIndex(list(NAMES).index(key))
        if self.key != key:
            self._choose(list(NAMES).index(key))
        return self.data

    def refresh(self):
        self._stale = False
        try:
            self.data = S.LISTS[self.key](self.window.doc)
        except Exception as exc:                        # noqa: BLE001 — said, the tab stays usable
            self.data = {"title": NAMES[self.key], "rows": [], "columns": [], "check": [f"δεν υπολογίστηκε: {exc}"],
                         "editable": {}, "total": ""}
        d = self.data
        self._filling = True
        try:
            self.table.clear()
            self.table.setColumnCount(len(d["columns"]))
            self.table.setHorizontalHeaderLabels([label for _k, label in d["columns"]])
            self.table.setRowCount(len(d["rows"]))
            for r, row in enumerate(d["rows"]):
                for c, (key, _label) in enumerate(d["columns"]):
                    item = QTableWidgetItem(_text(row.get(key)))
                    if key not in d["editable"]:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    if key == "how":
                        item.setForeground(QColor(110, 110, 110))
                    if key == "mark" and row.get("auto_mark"):
                        item.setForeground(QColor(140, 140, 140))
                        item.setToolTip("αυτόματος κωδικός — γράψτε δικό σας για να μείνει σταθερός")
                    self.table.setItem(r, c, item)
            self.table.resizeColumnsToContents()
        finally:
            self._filling = False
        self.check.setText(" · ".join(d["check"]) if d["check"] else "Πλήρες: δεν λείπει τίποτα για αυτή τη λίστα.")
        self.total.setText(d.get("total", ""))
        import datetime
        self.live.setText(f"Ζωντανή · {datetime.datetime.now():%H:%M:%S} · κλικ σε γραμμή = επιλογή στο σχέδιο")
        self.follow_selection()
        return d

    # ------------------------------------------------------------ export (the same lists, as they are now)
    def _project(self):
        import os
        path = getattr(self.window, "current_path", None)
        return os.path.splitext(os.path.basename(path))[0] if path else ""

    def _ask(self, title, default, pattern):
        from PySide6.QtWidgets import QFileDialog
        path, _f = QFileDialog.getSaveFileName(self, title, default, pattern)
        return path or None

    def export_pdf(self, path=None, keys=None):
        """The chosen lists (all by default) to an A4 landscape PDF; returns the path."""
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument
        from PySide6.QtCore import QMarginsF
        if path is None:
            path = self._ask("Λίστες (PDF)", "listes.pdf" if not keys else f"{NAMES[keys[0]].lower()}.pdf", "PDF (*.pdf)")
            if not path:
                return None
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        writer = QPdfWriter(path)
        writer.setPageLayout(QPageLayout(QPageSize(QPageSize.PageSizeId.A4), QPageLayout.Orientation.Landscape,
                                         QMarginsF(12, 12, 12, 12), QPageLayout.Unit.Millimeter))
        writer.setResolution(150)
        doc = QTextDocument()
        doc.setDefaultStyleSheet("body{font-size:9pt} th{background:#e8e8e8} td,th{padding:2px}")
        doc.setHtml(S.html(self.window.doc, keys, self._project()))
        doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
        doc.print_(writer)
        self.window.statusBar().showMessage(f"{TAB_TITLE}: {path}", 8000)
        return path

    def export_xlsx(self, path=None, keys=None):
        """The chosen lists (all by default) to .xlsx, one sheet each; returns the path."""
        if path is None:
            path = self._ask("Λίστες (Excel)", "listes.xlsx", "Excel (*.xlsx)")
            if not path:
                return None
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        S.write_xlsx(self.window.doc, path, keys)
        self.window.statusBar().showMessage(f"{TAB_TITLE}: {path} — ένα φύλλο ανά λίστα", 8000)
        return path

    # ------------------------------------------------------------ two-way selection
    def _rows_selected(self):
        if self._filling or self.data is None:
            return
        rows = sorted({i.row() for i in self.table.selectedItems()})
        ids = [i for r in rows for i in self.data["rows"][r]["ids"] if i in self.window.doc.entities]
        if not ids:
            return
        self._filling = True
        try:
            self.window.doc.select(list(dict.fromkeys(ids)))
            self.window._redraw_views(all_views=True)
            self.window.refresh_inspector()
        finally:
            self._filling = False

    def follow_selection(self):
        """Selection made in the drawing → its rows are highlighted (and scrolled to)."""
        if self._filling or self.data is None:
            return
        chosen = set(self.window.doc.selection)
        self._filling = True
        try:
            self.table.clearSelection()
            first = None
            for r, row in enumerate(self.data["rows"]):
                if chosen and chosen & set(row["ids"]):
                    for c in range(self.table.columnCount()):
                        self.table.item(r, c).setSelected(True)
                    first = r if first is None else first
            if first is not None:
                self.table.scrollToItem(self.table.item(first, 0))
        finally:
            self._filling = False

    # ------------------------------------------------------------ edits in place (one undo each)
    def _edited(self, item):
        if self._filling or self.data is None:
            return
        key = self.data["columns"][item.column()][0]
        row = self.data["rows"][item.row()]
        doc = self.window.doc
        try:
            if key == "mark":
                command = S.set_mark_command(doc, row["ids"][0], item.text())
            elif key == "uw":
                command = S.set_u_command(doc, row["ids"][0], item.text())
            elif key in ("uf", "ug", "psi_g", "frame_width", "g_value", "maker"):
                from archforge.mep.opening_thermal import set_command
                command = set_command(doc, row["ids"][0], key, item.text())
            elif key == "name":
                command = S.rename_room_command(doc, row["signature"], item.text())
            else:
                return
        except ValueError as exc:
            self.window.statusBar().showMessage(f"⚠ {TAB_TITLE}: {exc}", 8000)
            self.refresh()
            return
        self.window.stack.execute(command)
        self.window._redraw_views(all_views=True)
        self.window.statusBar().showMessage(f"{NAMES[self.key]}: «{item.text().strip()}» · Ctrl+Z = αναίρεση", 6000)
        self.refresh()


def install(window):
    tab = ListsTab(window)
    window._lists_tab = tab
    window.stack.listeners.append(tab.mark_stale)
    for view in (getattr(window, "plan_view", None), getattr(window, "pbr_view", None)):
        signal = getattr(view, "selectionChangedByView", None)
        if signal is not None:
            signal.connect(tab.follow_selection)
    return tab


def show(window, key=None):
    """Bring the «Λίστες» tab forward (added after the drawing tabs the first time), on the list ``key``."""
    tab = getattr(window, "_lists_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    if key:
        tab.show_list(key)
    return tab.refresh()
