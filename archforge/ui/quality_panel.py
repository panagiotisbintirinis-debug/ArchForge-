"""Προβολή ▸ Έλεγχος ποιότητας: η πύλη των σεναρίων ως πάνελ που ακολουθεί το σχέδιο (scenarios/live_gate.py).

* Ξανατρέχει μόνο του λίγο μετά από κάθε αλλαγή, όσο το πάνελ φαίνεται.
* «Δείξε μου» (ή διπλό κλικ): επιλέγει τα στοιχεία που αναφέρει ο έλεγχος και τα φέρνει στην κάτοψη.
* «Διόρθωση»: ανοίγει το εργαλείο που φτιάχνει ό,τι λείπει (Ολοκλήρωση κτιρίου, Πρόταση φέροντος).
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QDockWidget, QHBoxLayout, QLabel, QPushButton, QTreeWidget, QTreeWidgetItem,
                               QVBoxLayout, QWidget)

from archforge.scenarios.gate import FAIL, NA, PASS

MARK = {PASS: "✔", FAIL: "✖", NA: "—"}
FIX_LABELS = {"complete": "Ολοκλήρωση κτιρίου…", "frame": "Πρόταση φέροντος"}
DELAY_MS = 1500


def show_me(window, ids):
    """Select ``ids`` and fit them in the plan."""
    from archforge.core.plan_scene import build_plan_frame
    ids = [i for i in ids if i in window.doc.entities]
    if not ids:
        return False
    window.doc.select(ids)
    tabs = getattr(window, "_central_tabs", None)
    if tabs is not None:
        tabs.setCurrentIndex(0)
    pts = [q for p in build_plan_frame(window.doc).primitives if p.entity_id in ids for q in p.points]
    if pts:
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        window.plan_view.fitInView(QRectF(min(xs) - 2, min(ys) - 2, max(xs) - min(xs) + 4, max(ys) - min(ys) + 4),
                                   Qt.AspectRatioMode.KeepAspectRatio)
    window.plan_view.redraw()
    window.refresh_inspector()
    return True


def apply_fix(window, key):
    if key == "complete":
        action = getattr(window, "_complete_building_action", None)
        if action is not None:
            action.trigger()
            return True
    if key == "frame" and hasattr(window, "_propose_frame"):
        window._propose_frame()
        return True
    return False


class QualityPanel(QWidget):
    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.results = []
        lay = QVBoxLayout(self); lay.setContentsMargins(6, 4, 6, 4)
        top = QHBoxLayout()
        self.summary = QLabel("—"); f = self.summary.font(); f.setBold(True); self.summary.setFont(f)
        top.addWidget(self.summary, 1)
        self.only_problems = QCheckBox("Μόνο προβλήματα"); self.only_problems.setChecked(True)
        self.only_problems.toggled.connect(lambda _on: self._fill())
        top.addWidget(self.only_problems)
        now = QPushButton("Έλεγχος τώρα"); now.clicked.connect(lambda: self.refresh())
        top.addWidget(now)
        lay.addLayout(top)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Έλεγχος", "Σημείωση"]); self.tree.setColumnWidth(0, 260)
        self.tree.itemDoubleClicked.connect(lambda item, _c: self._show(item))
        self.tree.currentItemChanged.connect(lambda item, _p: self._enable(item))
        lay.addWidget(self.tree, 1)
        bar = QHBoxLayout()
        self.show_button = QPushButton("Δείξε μου"); self.show_button.clicked.connect(lambda: self._show(self.tree.currentItem()))
        self.fix_button = QPushButton("Διόρθωση"); self.fix_button.clicked.connect(lambda: self._fix(self.tree.currentItem()))
        bar.addWidget(self.show_button); bar.addWidget(self.fix_button); bar.addStretch(1)
        lay.addLayout(bar)
        self._enable(None)
        self.timer = QTimer(self); self.timer.setSingleShot(True); self.timer.timeout.connect(self.refresh)

    # --- running ----------------------------------------------------------------------------------
    def schedule(self):
        """After a change: run again a moment later, only while the panel is on screen."""
        if self.isVisible():
            self.timer.start(DELAY_MS)

    def refresh(self):
        from archforge.scenarios.live_gate import run, summary
        self.timer.stop()
        self.results = run(self.window)
        ok, bad, na = summary(self.results)
        self.summary.setText(f"✖ {bad} προβλήματα · ✔ {ok} · — {na}")
        self._fill()
        return self.results

    def _fill(self):
        self.tree.clear()
        groups = {}
        for r in self.results:
            if self.only_problems.isChecked() and r.status != FAIL:
                continue
            group = groups.get(r.section)
            if group is None:
                group = groups[r.section] = QTreeWidgetItem([r.section, ""])
                self.tree.addTopLevelItem(group); group.setExpanded(True)
            row = QTreeWidgetItem([f"{MARK[r.status]} {r.item}", r.note])
            row.setToolTip(0, r.item); row.setToolTip(1, r.note)
            row.setData(0, Qt.ItemDataRole.UserRole, r)
            group.addChild(row)
        if not groups:
            self.tree.addTopLevelItem(QTreeWidgetItem(["✔ Κανένα πρόβλημα", ""]))
        self._enable(None)

    # --- buttons ----------------------------------------------------------------------------------
    @staticmethod
    def _result(item):
        return item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None

    def _enable(self, item):
        r = self._result(item)
        self.show_button.setEnabled(bool(r and r.ids))
        self.fix_button.setEnabled(bool(r and r.fix and r.status == FAIL))
        self.fix_button.setText(FIX_LABELS.get(r.fix, "Διόρθωση") if r and r.fix else "Διόρθωση")

    def _show(self, item):
        r = self._result(item)
        return show_me(self.window, r.ids) if r else False

    def _fix(self, item):
        r = self._result(item)
        return apply_fix(self.window, r.fix) if r and r.fix else False


def listen(window):
    """Re-run after every change of the (current) command stack."""
    panel = getattr(window, "_quality_panel", None)
    if panel is not None:
        window.stack.listeners.append(panel.schedule)


def install(window):
    """Dock (hidden until asked) + Προβολή ▸ Έλεγχος ποιότητας."""
    panel = window._quality_panel = QualityPanel(window)
    dock = window._quality_dock = QDockWidget("Έλεγχος ποιότητας", window)
    dock.setObjectName("quality_dock")
    dock.setWidget(panel)
    window.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)
    dock.hide()
    dock.visibilityChanged.connect(lambda shown: shown and panel.refresh())
    listen(window)
    action = dock.toggleViewAction(); action.setText("Έλεγχος ποιότητας")
    action.setToolTip("Οι έλεγχοι της πύλης ποιότητας πάνω στο σχέδιο, με «Δείξε μου» και «Διόρθωση»")
    view = next((a.menu() for a in window.menuBar().actions() if a.text().replace("&", "") == "Προβολή" and a.menu()), None)
    if view is not None:
        view.addSeparator(); view.addAction(action)
    window._quality_action = action
    return panel
