"""«Πίνακας» tab at the end of the design: the electrical board with its figures in view.

Everything shown is derived from the Document by ``mep.electrical_board.analyse``;
the three settings (supply, diversity, cable allowance) are params of the
panel point, changed through ``UpdateEntity`` (undo, save/load).
Click a circuit = its points are selected in the drawing; click a wall = the wall.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

TAB_TITLE = "Ηλεκτρ. πίνακας"


def _n(v, d=1):
    if v is None:
        return "—"
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


class BoardTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.result = None
        self._stale = True
        self._updating = False
        self.setObjectName("electrical_board_tab")
        root = QVBoxLayout(self); root.setContentsMargins(10, 8, 10, 8); root.setSpacing(8)

        head = QHBoxLayout(); head.setSpacing(8)
        title = QLabel("Ηλεκτρολογικός πίνακας"); title.setStyleSheet("font-weight:600;font-size:15px")
        head.addWidget(title); head.addStretch(1)
        # Entered by the user from the ΔΕΔΔΗΕ connection and the study: 0 = not entered, no hidden defaults.
        def spin(prefix, suffix, hi, step, decimals, tip):
            w = QDoubleSpinBox(); w.setRange(0.0, hi); w.setSingleStep(step); w.setDecimals(decimals)
            w.setPrefix(prefix); w.setSuffix(suffix); w.setSpecialValueText(prefix + "— εισάγετε"); w.setToolTip(tip)
            return w
        self.kva = spin("Παροχή ", " kVA", 1000.0, 1.0, 1, "Ισχύς παροχής από την αίτηση/σύμβαση σύνδεσης ΔΕΔΔΗΕ")
        self.phases = QComboBox(); self.phases.setToolTip("Φάσεις της παροχής (ΔΕΔΔΗΕ)")
        for label, value in (("Φάσεις: — εισάγετε", 0), ("Μονοφασική", 1), ("Τριφασική", 3)):
            self.phases.addItem(label, value)
        self.fuse = spin("Ασφάλεια ", " A", 1000.0, 1.0, 0, "Ασφάλεια παροχής από την αίτηση/σύμβαση σύνδεσης ΔΕΔΔΗΕ")
        self.factor = spin("Ταυτοχρ. ", "", 1.0, 0.05, 2, "Συντελεστής ταυτοχρονισμού της μελέτης (ηλεκτρολόγος)")
        self.waste = spin("Φύρα ", " %", 50.0, 1.0, 0, "Επιπλέον μέτρα καλωδίου για αγορά (ρύθμιση χρήστη)")
        self.waste.setSpecialValueText("Φύρα 0 %")
        self.method = QComboBox(); self.method.setToolTip("Μέθοδος εγκατάστασης για το Iz (ΕΛΟΤ HD 60364-5-52)")
        for label, value in (("B1: σωλήνας σε κτιστό τοίχο", "B1"), ("A1: σωλήνας σε θερμομονωτικό τοίχο", "A1")):
            self.method.addItem(label, value)
        self.method.activated.connect(lambda _i: self._set("install_method", self.method.currentData()))
        for w in (self.kva, self.phases, self.fuse, self.factor, self.waste, self.method):
            head.addWidget(w)
        self.kva.editingFinished.connect(lambda: self._set("supply_kva", float(self.kva.value())))
        self.phases.activated.connect(lambda _i: self._set("supply_phases", int(self.phases.currentData())))
        self.fuse.editingFinished.connect(lambda: self._set("supply_fuse_a", float(self.fuse.value())))
        self.factor.editingFinished.connect(lambda: self._set("demand_factor", float(self.factor.value())))
        self.waste.editingFinished.connect(lambda: self._set("waste_pct", float(self.waste.value())))
        self.excel = QPushButton("Excel…"); self.excel.clicked.connect(self.export_csv)
        self.pdf = QPushButton("PDF…"); self.pdf.clicked.connect(self.export_pdf)
        head.addWidget(self.excel); head.addWidget(self.pdf)
        root.addLayout(head)

        self.cards = QGridLayout(); self.cards.setHorizontalSpacing(8)
        self.card_labels = {}
        for col, key in enumerate(("installed", "demand", "supply", "main", "phases")):
            box = QFrame(); box.setFrameShape(QFrame.Shape.StyledPanel)
            v = QVBoxLayout(box); v.setContentsMargins(8, 4, 8, 4); v.setSpacing(0)
            cap, val = QLabel(), QLabel()
            cap.setStyleSheet("color:palette(mid);font-size:11px"); val.setStyleSheet("font-weight:600")
            val.setWordWrap(True)
            v.addWidget(cap); v.addWidget(val)
            self.cards.addWidget(box, 0, col)
            self.card_labels[key] = (box, cap, val)
        root.addLayout(self.cards)

        self.empty = QLabel("Δεν υπάρχουν κυκλώματα: βάλτε ηλεκτρικό πίνακα και σημεία "
                            "(Κατασκευή ▸ Η/Μ ▸ Ηλεκτρολογικά) — εδώ εμφανίζονται κυκλώματα, αγωγοί, μέτρα και ο πίνακας.")
        self.empty.setWordWrap(True); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty)

        self.pages = QTabWidget()
        self.circuits = self._tree(["Κύκλωμα", "Περιγραφή", "Φάση", "Ασφάλεια", "Διατομή", "Σημεία", "Χώροι",
                                    "Φορτίο", "Μήκος", "Ως πιο μακρινό", "Iz*", "ΔU*", "Έλεγχος"])
        self.circuits.itemClicked.connect(self._select_item)
        self.circuits.itemDoubleClicked.connect(lambda item, _c: self._select_item(item, show=True))
        self.walls = self._tree(["Θέση", "Κυκλώματα", "Σωλήνας"])
        self.walls.itemClicked.connect(self._select_item)
        self.walls.itemDoubleClicked.connect(lambda item, _c: self._select_item(item, show=True))
        self.purchase = self._tree(["Διατομή", "Μέτρα", "Με φύρα"])
        self.pages.addTab(self.circuits, "Κυκλώματα και αγωγοί")
        self.pages.addTab(self.walls, "Μέτρα ανά τοίχο")
        self.pages.addTab(self.purchase, "Αγορά καλωδίων")
        root.addWidget(self.pages, 1)

        self.warnings = QLabel(); self.warnings.setWordWrap(True); self.warnings.setStyleSheet("color:#b45309")
        self.provenance = QLabel(); self.provenance.setWordWrap(True); self.provenance.setStyleSheet("color:palette(mid);font-size:11px")
        root.addWidget(self.warnings); root.addWidget(self.provenance)

    @staticmethod
    def _tree(headers):
        t = QTreeWidget(); t.setHeaderLabels(headers); t.setRootIsDecorated(True); t.setAlternatingRowColors(True)
        t.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        t.header().setStretchLastSection(True)
        return t

    # ----------------------------------------------------------------------------------- settings (shared command)
    def _set(self, key, value):
        if self._updating or self.result is None:
            return
        pid = self.result["settings"]["panel"]
        if pid is None or self.window.doc.get(pid).params.get(key) == value:
            return
        from archforge.core.commands import UpdateEntity
        self.window.stack.execute(UpdateEntity(pid, {key: value}))
        self.refresh()

    # ------------------------------------------------------------------------------------------------- content
    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def refresh(self):
        from archforge.mep.electrical_board import analyse
        self._stale = False
        r = self.result = analyse(self.window.doc)
        b = r["board"]
        has = bool(r["circuits"])
        self.empty.setVisible(not has)
        self.pages.setVisible(has)
        for w in (self.kva, self.phases, self.fuse, self.factor, self.waste, self.method, self.excel, self.pdf):
            w.setEnabled(has)
        self._updating = True
        try:
            conf = r["settings"]
            self.kva.setValue(conf["supply_kva"]); self.fuse.setValue(conf["supply_fuse_a"])
            self.phases.setCurrentIndex(max(0, self.phases.findData(conf["supply_phases"])))
            self.factor.setValue(conf["demand_factor"])
            self.waste.setValue(conf["waste_pct"])
            self.method.setCurrentIndex(max(0, self.method.findData(conf["install_method"])))
        finally:
            self._updating = False
        cards = {}
        if b:
            todo = "— εισάγετε"
            cards = {"installed": ("Εγκατεστημένη ισχύς (άθροισμα σημείων)", f"{_n(b['installed_w'] / 1000)} kW"),
                     "demand": ("Ζήτηση (συντελεστής μελέτης)", f"{_n(b['demand_kva'])} kVA · ×{_n(b['demand_factor'], 2)}"
                                if b["demand_kva"] is not None else todo),
                     "supply": ("Παροχή ΔΕΔΔΗΕ (όπως εισήχθη)",
                                " · ".join(x for x in ((f"{_n(b['supply_kva'])} kVA" if b["supply_kva"] else ""),
                                                       {1: "μονοφασική", 3: "τριφασική"}.get(b["phases"], ""),
                                                       (f"{_n(b['fuse_a'], 0)} A" if b["fuse_a"] else "")) if x) or todo),
                     "main": ("Γενικός διακόπτης", b["main_switch"].replace("Γενικός διακόπτης ", "") if b["main_switch"] else todo),
                     "phases": ("Φάσεις", " · ".join(f"{k} {_n(v / 1000)} kW" for k, v in b["phase_w"].items())
                                + (f" · ανισορροπία {_n(b['imbalance_pct'], 0)} %" if b["imbalance_pct"] is not None else "")
                                if b["phases"] else todo)}
        for key, (box, cap, val) in self.card_labels.items():
            box.setVisible(key in cards)
            if key in cards:
                cap.setText(cards[key][0]); val.setText(cards[key][1])
        self._fill_circuits(r)
        self._fill_walls(r)
        self._fill_purchase(r)
        notes = [f"⚠ {w}" for w in r["warnings"]]
        if r.get("practice_conflicts"):
            notes += ["Διαφωνίες με την πρακτική εγκαταστάτη (απόφαση ηλεκτρολόγου):"] + [f"  ≠ {c}" for c in r["practice_conflicts"]]
        self.warnings.setText("\n".join(notes))
        self.warnings.setVisible(bool(notes))
        lines = [r["provenance"], "* Iz και ΔU: ενδεικτικός έλεγχος με τιμές ENGINEER_REVIEW (σύνοψη ΕΛΟΤ HD 60364-5-52), "
                 "χωρίς k1/k2 — όχι απόδειξη συμμόρφωσης", "Κατάσταση κανόνων (μόνο τα επαληθευμένα είναι τεχνική απαίτηση· κανένας δεν είναι ακόμη):"] + [f" • {u}" for u in r["unverified"]]
        self.provenance.setText("\n".join(lines))
        self.provenance.setVisible(has)
        return r

    def _fill_circuits(self, r):
        t = self.circuits; t.clear()
        for c in r["circuits"]:
            item = QTreeWidgetItem([c["id"], c["label"], c.get("phase", ""), f"{c['breaker_a']} A", f"{_n(c['mm2'])} mm²",
                                    str(c["points"]), ", ".join(c["rooms"]), f"{c['load_w']} W · {_n(c['current_a'])} A",
                                    f"{_n(c['conduit_m'])} m", f"{_n(c['farthest_m'])} m",
                                    f"{_n(c['iz_a'])} A", f"{_n(c['drop_pct'], 2)} % / {_n(c['drop_limit_pct'], 0)} %",
                                    "✓" if c["ok"] else "⚠ " + ", ".join(c["notes"])])
            item.setData(0, Qt.ItemDataRole.UserRole, list(c["point_ids"]))
            if not c["ok"]:
                item.setForeground(12, Qt.GlobalColor.darkYellow)
            line_m = float(c["conduit_m"])
            for code, label, s in c["conductors"]:
                QTreeWidgetItem(item, [code, label, "", "", f"{_n(s)} mm²", "", "", "", f"{_n(line_m)} m", "", "", "", ""])
            if c["switch_leg"]:
                leg = max(0.0, (c["wire_m"].get(c["mm2"], 0.0) - 3 * line_m) / 2)
                for code, label in (("L", "Φάση προς διακόπτες"), ("R", "Επιστροφή διακόπτη")):
                    QTreeWidgetItem(item, [code, label, "", "", f"{_n(c['mm2'])} mm²", "", "", "", f"{_n(leg)} m", "", "", "", ""])
            t.addTopLevelItem(item)

    def _fill_walls(self, r):
        t = self.walls; t.clear()
        for w in r["walls"]:
            item = QTreeWidgetItem([w["label"], " ".join(w["circuits"]), f"{_n(w['conduit_m'], 2)} m"])
            item.setData(0, Qt.ItemDataRole.UserRole, [w["wall"]] if w["wall"] else [])
            for s, m in w["by_section"].items():
                QTreeWidgetItem(item, [f"Καλώδιο {_n(s)} mm²", "", f"{_n(m, 2)} m"])
            t.addTopLevelItem(item)

    def _fill_purchase(self, r):
        t = self.purchase; t.clear()
        for p in r["purchase"]:
            t.addTopLevelItem(QTreeWidgetItem([f"{_n(p['mm2'])} mm²", f"{_n(p['metres'])} m", f"{_n(p['with_waste'])} m"]))

    def _select_item(self, item, _column=0, show=False):
        while item.parent() is not None:
            item = item.parent()
        ids = [i for i in (item.data(0, Qt.ItemDataRole.UserRole) or []) if i in self.window.doc.entities]
        if not ids:
            return
        self.window.doc.select(ids)
        self.window.refresh_inspector()
        self.window._redraw_views(all_views=True)
        if show:
            tabs = getattr(self.window, "_central_tabs", None)
            if tabs is not None:
                tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------------------------------------- export
    def export_csv(self, path=None):
        from archforge.mep.electrical_board import board_csv
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, "Εξαγωγή πίνακα (Excel)", "ilektrologikos_pinakas.csv", "CSV (*.csv)")
        if not path:
            return None
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            fh.write(board_csv(self.result or self.refresh()))
        return path

    def export_pdf(self, path=None):
        from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, "Εξαγωγή πίνακα (PDF)", "ilektrologikos_pinakas.pdf", "PDF (*.pdf)")
        if not path:
            return None
        writer = QPdfWriter(path); writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4)); writer.setResolution(150)
        doc = QTextDocument(); doc.setHtml(board_html(self.result or self.refresh()))
        doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size().toSizeF())
        doc.print_(writer)
        return path


def board_html(r):
    from html import escape as e
    b = r["board"]
    rows = "".join(f"<tr><td>{e(c['id'])}</td><td>{e(c['label'])}</td><td>{e(c.get('phase', ''))}</td><td>{c['breaker_a']} A</td>"
                   f"<td>{_n(c['mm2'])}</td><td>{' + '.join(code for code, *_x in c['conductors'])}{' + επιστρ.' if c['switch_leg'] else ''}</td>"
                   f"<td>{c['points']}</td><td>{c['load_w']} W</td><td>{_n(c['conduit_m'])} m</td><td>{_n(c['farthest_m'])} m</td><td>{_n(c['iz_a'])} A</td><td>{_n(c['drop_pct'], 2)} %</td>"
                   f"<td>{'✓' if c['ok'] else '⚠ ' + e(', '.join(c['notes']))}</td></tr>" for c in r["circuits"])
    sections = sorted({s for w in r["walls"] for s in w["by_section"]})
    walls = "".join(f"<tr><td>{e(w['label'])}</td><td>{e(' '.join(w['circuits']))}</td><td>{_n(w['conduit_m'], 2)}</td>"
                    + "".join(f"<td>{_n(w['by_section'].get(s, 0), 2)}</td>" for s in sections) + "</tr>" for w in r["walls"])
    buy = "".join(f"<tr><td>{_n(p['mm2'])} mm²</td><td>{_n(p['metres'])}</td><td>{_n(p['with_waste'])}</td></tr>"
                  for p in r["purchase"])
    head = ""
    if b:
        todo = "— δεν εισήχθη"
        head = (f"<p>Εγκατεστημένη ισχύς (άθροισμα σημείων) {_n(b['installed_w'] / 1000)} kW · "
                f"ζήτηση {(_n(b['demand_kva']) + ' kVA') if b['demand_kva'] is not None else todo}<br>"
                f"Παροχή ΔΕΔΔΗΕ (όπως εισήχθη): {(_n(b['supply_kva']) + ' kVA') if b['supply_kva'] else todo}, "
                f"{ {1: 'μονοφασική', 3: 'τριφασική'}.get(b['phases'], todo)}, ασφάλεια {(_n(b['fuse_a'], 0) + ' A') if b['fuse_a'] else todo}</p>")
    tbl = 'border="1" cellspacing="0" cellpadding="3" width="100%"'
    return (f"<h2>Ηλεκτρολογικός πίνακας</h2>{head}"
            f"<h3>Κυκλώματα</h3><table {tbl}><tr><th>Κ</th><th>Περιγραφή</th><th>Φάση</th><th>Ασφάλεια</th><th>mm²</th>"
            f"<th>Αγωγοί</th><th>Σημεία</th><th>Φορτίο</th><th>Σωλήνας</th><th>Ως πιο μακρινό</th><th>Iz*</th><th>ΔU*</th><th>Έλεγχος</th></tr>{rows}</table>"
            f"<h3>Μέτρα ανά τοίχο (m)</h3><table {tbl}><tr><th>Θέση</th><th>Κυκλώματα</th><th>Σωλήνας</th>"
            + "".join(f"<th>{_n(s)} mm²</th>" for s in sections) + f"</tr>{walls}</table>"
            f"<h3>Αγορά καλωδίων (φύρα {_n(r['waste_pct'], 0)} %)</h3><table {tbl}><tr><th>Διατομή</th><th>Μέτρα</th>"
            f"<th>Με φύρα</th></tr>{buy}</table>"
            + "".join(f"<p>⚠ {e(w)}</p>" for w in r["warnings"])
            + ("<p><b>Διαφωνίες με την πρακτική εγκαταστάτη (απόφαση ηλεκτρολόγου)</b><br>"
               + "<br>".join(e(c) for c in r.get("practice_conflicts", [])) + "</p>" if r.get("practice_conflicts") else "")
            + "<p><small>* Iz/ΔU: ενδεικτικός έλεγχος, τιμές προς έλεγχο από ηλεκτρολόγο (χωρίς k1/k2)</small></p>"
            + "<p><b>Κατάσταση κανόνων (μόνο τα επαληθευμένα είναι τεχνική απαίτηση)</b><br>" + "<br>".join(e(u) for u in r["unverified"]) + "</p>"
            + f"<p><small>{e(r['provenance'])}<br>{e(r['circuit_provenance'])}</small></p>")


def install(window):
    """Prepare the «Ηλεκτρ. πίνακας» page; it joins the central tabs only when asked for (like «Τομή»),
    so the approved layout keeps its two drawing tabs. It follows every committed change."""
    tab = BoardTab(window)
    window._board_tab = tab
    window.stack.listeners.append(tab.mark_stale)
    return tab


def show(window):
    """Bring the tab forward (menu «Ηλεκτρολογικός πίνακας»), adding it after the drawing tabs the first time."""
    tab = getattr(window, "_board_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    return tab.refresh()
