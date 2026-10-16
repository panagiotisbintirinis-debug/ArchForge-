"""Dedicated Plumbing details/report tab.

The normal floor plan stays drawing-first and clean. This tab owns a separate
read-only technical plan of the same authoritative Document: pipe diameters are
visible on that technical drawing, while quantities/BOM, rules and provenance
stay in tables below it.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QGraphicsTextItem, QHeaderView, QLabel, QSplitter,
    QTabWidget, QTableWidget, QTableWidgetItem, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from archforge.ui.plan_view import PlanView

TAB_TITLE = "Υδραυλικά"


def _n(value, decimals=2):
    if value is None:
        return "—"
    return f"{float(value):.{decimals}f}".replace(".", ",")


def _length(a, b):
    return math.dist(tuple(float(v) for v in a), tuple(float(v) for v in b))


class PlumbingTechnicalPlan(PlanView):
    """Read-only technical plan with wheel zoom and left-drag pan."""

    def __init__(self, doc, stack, parent=None):
        super().__init__(doc, stack, parent)
        self.setMinimumHeight(260)
        self.setToolTip("Τεχνική κάτοψη υδραυλικών — wheel: zoom · σύρε: μετακίνηση κάτοψης")
        self._pan_last = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def redraw(self):
        super().redraw()
        if not hasattr(self, "doc"):
            return
        try:
            from archforge.mep.plumbing import SCREED, route_plumbing_cached
            routed = route_plumbing_cached(self.doc)
            level = float(self.doc.work_plane.origin[2])
            for network in ("cold", "hot"):
                colour = QColor(31, 90, 160) if network == "cold" else QColor(190, 55, 45)
                for a, b, diameter in routed.get(network, ()):
                    if abs(float(a[2]) - float(b[2])) > 1e-9:
                        continue
                    if abs(float(a[2]) - (level + SCREED)) > 1e-6:
                        continue
                    x = (float(a[0]) + float(b[0])) / 2.0
                    y = (float(a[1]) + float(b[1])) / 2.0
                    item = self._scene.addText(f"Ø{int(diameter)}")
                    item.setDefaultTextColor(colour)
                    font = item.font(); font.setBold(True); item.setFont(font)
                    item.setFlag(QGraphicsTextItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                    item.setPos(x, y)
                    item.setZValue(80)
        except Exception:
            pass

    # This view is documentation-only. Left drag pans the view instead of
    # selecting/moving model entities; the inherited wheelEvent keeps zoom.
    def mousePressEvent(self, event):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._pan_last = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        event.accept()

    def mouseMoveEvent(self, event):
        if self._pan_last is not None:
            now = event.position()
            delta = now - self._pan_last
            self._pan_last = now
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(delta.y()))
        event.accept()

    def mouseReleaseEvent(self, event):
        self._pan_last = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def contextMenuEvent(self, event):
        event.accept()


class PlumbingTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._stale = True
        self.setObjectName("plumbing_details_tab")
        self.setProperty("archforge_report_tab", True)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        title = QLabel("Υδραυλικά — τεχνικές λεπτομέρειες")
        title.setStyleSheet("font-weight:600;font-size:15px")
        root.addWidget(title)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.technical_plan = PlumbingTechnicalPlan(window.doc, window.stack, self)

        self.pages = QTabWidget()
        self.network = self._tree(["Δίκτυο", "Διάμετρος", "Μήκος", "Από", "Προς", "Κατάσταση"])
        self.bom = self._bom_table()
        self.rules = self._tree(["Κατάσταση", "Κανόνας", "Τιμή", "Πηγή", "Σημείωση"])
        self.pages.addTab(self.network, "Δίκτυο")
        self.pages.addTab(self.bom, "Ποσότητες / BOM")
        self.pages.addTab(self.rules, "Κανόνες & Πηγές")

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.technical_plan)
        split.addWidget(self.pages)
        split.setCollapsible(0, False)
        split.setCollapsible(1, False)
        split.setSizes([330, 420])
        root.addWidget(split, 1)
        self._split = split

        self.note = QLabel(
            "Στην κανονική 2D κάτοψη φαίνονται μόνο οι σωληνώσεις. Στην τεχνική κάτοψη αυτής της καρτέλας "
            "φαίνονται οι διατομές Ø. Wheel = zoom, σύρσιμο = μετακίνηση. Το BOM διαβάζει το κοινό price_list "
            "του έργου· τιμές που δεν έχουν δοθεί παραμένουν —. ENGINEER_REVIEW / DESIGN_DEFAULT δεν αποτελούν "
            "επαληθευμένη κανονιστική απαίτηση."
        )
        self.note.setWordWrap(True)
        self.note.setStyleSheet("color:palette(mid);font-size:11px")
        root.addWidget(self.note)

    @staticmethod
    def _tree(headers):
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        tree.header().setStretchLastSection(True)
        return tree

    @staticmethod
    def _bom_table():
        headers = [
            "Κωδικός", "Περιγραφή", "Κατηγορία", "Ποσότητα", "Μονάδα",
            "Υλικό €/μον.", "Εργασία €/μον.", "Υλικό €", "Εργασία €", "Σύνολο €",
            "Τιμολόγηση", "Πηγή τιμής", "Κατάσταση", "Πηγή κανόνα",
        ]
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.setSortingEnabled(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(True)
        table.horizontalHeader().setSectionsMovable(True)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setToolTip("BOM τύπου φύλλου εργασίας — ταξινόμηση από τις κεφαλίδες, μία κοινή πηγή τιμών έργου")
        return table

    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def refresh(self):
        from archforge.mep.plumbing import route_plumbing
        from archforge.mep.plumbing_costing import plumbing_quote
        from archforge.mep.plumbing_rules import plumbing_rule_audit

        self._stale = False
        self.technical_plan.rebind(self.window.doc, self.window.stack)
        self.technical_plan.redraw()

        routed = route_plumbing(self.window.doc)
        quote = plumbing_quote(self.window.doc)
        quantities = quote["quantities"]
        priced_rows = quote["rows"]
        pricing = quote["summary"]

        self.network.clear()
        total = {"cold": 0.0, "hot": 0.0}
        labels = {"cold": "Κρύο", "hot": "Ζεστό"}
        for network in ("cold", "hot"):
            for a, b, diameter in routed.get(network, ()):
                length = _length(a, b)
                total[network] += length
                QTreeWidgetItem(self.network, [
                    labels[network], f"Ø{int(diameter)}", f"{_n(length)} m",
                    f"({_n(a[0])}, {_n(a[1])}, {_n(a[2])})",
                    f"({_n(b[0])}, {_n(b[1])}, {_n(b[2])})",
                    "ENGINEER_REVIEW",
                ])

        # Spreadsheet-style BOM driven by the exact rows of the shared costing
        # engine. The UI does not recalculate quantities or prices.
        self.bom.setSortingEnabled(False)
        self.bom.setRowCount(0)
        for row_index, row in enumerate(priced_rows):
            self.bom.insertRow(row_index)
            pricing_status = (
                "Πλήρης" if row.get("complete_price")
                else "Μερική" if row.get("partial_price")
                else "Χωρίς τιμή"
            )
            values = [
                str(row.get("code", "")),
                str(row.get("description", "")),
                str(row.get("category", "")),
                _n(row.get("quantity"), 2),
                str(row.get("unit", "")),
                _n(row.get("material_unit_price"), 4),
                _n(row.get("labour_unit_price"), 4),
                _n(row.get("material_cost"), 2),
                _n(row.get("labour_cost"), 2),
                _n(row.get("total_cost"), 2),
                pricing_status,
                str(row.get("price_source", "missing")),
                str(row.get("rule_status", "")),
                str(row.get("rule_source") or row.get("source") or ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col in (3, 5, 6, 7, 8, 9):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.bom.setItem(row_index, col, item)
        self.bom.setSortingEnabled(True)
        self.bom.resizeRowsToContents()

        self.rules.clear()
        grouped = plumbing_rule_audit()
        order = ("VERIFIED_STANDARD", "MANUFACTURER_DATA", "CALCULATED", "DESIGN_DEFAULT", "ENGINEER_REVIEW")
        for status in order:
            for rule in grouped.get(status, ()):
                value = "—" if rule.value is None else str(rule.value)
                if rule.unit and value != "—":
                    value = f"{value} {rule.unit}"
                QTreeWidgetItem(self.rules, [status, rule.label, value, rule.source or "—", rule.note or ""])

        unserved = len(routed.get("report", {}).get("unserved", ()))
        missing_prices = len(pricing.get("unpriced_codes", ()))
        price_text = (
            f"Προσφορά: {_n(pricing['subtotal'])} {pricing['currency']}"
            if pricing.get("complete") and priced_rows
            else f"Τιμολογημένο έως τώρα: {_n(pricing['subtotal'])} {pricing['currency']} · λείπουν {missing_prices} γραμμές τιμών"
        )
        self.summary.setText(
            f"Κρύο: {_n(total['cold'])} m   ·   Ζεστό: {_n(total['hot'])} m   ·   "
            f"Γραμμές BOM: {len(quantities)}   ·   {price_text}"
            + (f"   ·   Μη εξυπηρετούμενα σημεία: {unserved}" if unserved else "")
        )
        return {"route": routed, "quote": quote, "rules": grouped}


def install(window):
    if getattr(window, "_plumbing_tab", None) is not None:
        return window._plumbing_tab
    tab = PlumbingTab(window)
    window._plumbing_tab = tab
    window.stack.listeners.append(tab.mark_stale)

    menu = getattr(window, "_mockup_plumbing_menu", None)
    if menu is not None:
        menu.addSeparator()
        action = QAction("Υδραυλικά — λεπτομέρειες", menu)
        action.setToolTip("Τεχνική κάτοψη με διατομές, δίκτυο, ποσότητες/BOM και κανόνες")
        action.triggered.connect(lambda _=False: show(window))
        menu.addAction(action)
        window._plumbing_details_action = action
    return tab


def install_on_class(MainWindow):
    """Install the tab after the normal MainWindow and approved shell exist."""
    if getattr(MainWindow, "_archforge_plumbing_tab_installed", False):
        return
    original_init = MainWindow.__init__

    def wrapped_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        install(self)

    MainWindow.__init__ = wrapped_init
    MainWindow._archforge_plumbing_tab_installed = True


def show(window):
    tab = getattr(window, "_plumbing_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    window.view = window.plan_view
    return tab.refresh()
