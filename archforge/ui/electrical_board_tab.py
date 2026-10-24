"""«Πίνακας» tab at the end of the design: the electrical board with its figures in view.

Everything shown is derived from the Document by ``mep.electrical_board.analyse``;
the three settings (supply, diversity, cable allowance) are params of the
panel point, changed through ``UpdateEntity`` (undo, save/load).
Click a circuit = its points are selected in the drawing; click a wall = the wall.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QScrollArea, QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget)

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
        from archforge.mep.knx import CONTROL_SYSTEMS
        self.control = QComboBox(); self.control.setToolTip("Σύστημα ελέγχου — επιλογή του πελάτη (προεπιλογή: συμβατικό On/Off)")
        for value, label in CONTROL_SYSTEMS.items():
            self.control.addItem(label, value)
        self.control.activated.connect(lambda _i: self._set("control_system", self.control.currentData()))
        from archforge.mep.conduit_fill import CONDUIT_PROFILES
        self.pipe_profile = QComboBox(); self.pipe_profile.setObjectName('conduitProfile')
        for key,spec in CONDUIT_PROFILES.items():
            if key!='geonflex':self.pipe_profile.addItem(spec['name'],key)
        self.pipe_profile.setToolTip('Προφίλ γεωμετρικού υπολογισμού: εσωτερική διάμετρος από τον κατασκευαστή. Η καταλληλότητα εγκατάστασης χρειάζεται επιβεβαίωση.')
        self.pipe_profile.activated.connect(lambda _i: self._set('conduit_profile',self.pipe_profile.currentData()))
        self.pipe_max = QComboBox(); self.pipe_max.setObjectName('conduitMaxDiameter')
        for dn in (16,20,25,32,40,50):self.pipe_max.addItem(f'Μέγιστο Φ{dn}',dn)
        self.pipe_max.setToolTip('Ανώτατη διάμετρος για τη σύγκριση ενός ή περισσότερων σωλήνων. Ισχύει και η διαθεσιμότητα της επιλεγμένης σειράς.')
        self.pipe_max.activated.connect(lambda _i: self._set('conduit_max_dn',int(self.pipe_max.currentData())))
        self.pipe_fill = QDoubleSpinBox(); self.pipe_fill.setObjectName('conduitFillLimit')
        self.pipe_fill.setRange(1,99);self.pipe_fill.setDecimals(1);self.pipe_fill.setPrefix('Πλήρωση ≤ ');self.pipe_fill.setSuffix(' %')
        self.pipe_fill.setToolTip('Όριο έργου: ο ιδιοκτήτης επέλεξε 30%. Δεν είναι επαληθευμένη κανονιστική απαίτηση. Ονομαστικές εξωτερικές διάμετροι μονωμένων αγωγών, όχι διατομές χαλκού.')
        self.pipe_fill.editingFinished.connect(lambda: self._set('conduit_fill_limit',self.pipe_fill.value()/100))
        settings_grid = QGridLayout()
        for index,w in enumerate((self.control,self.kva,self.phases,self.fuse,self.factor,self.waste,self.method,
                                 self.pipe_profile,self.pipe_max,self.pipe_fill)):
            settings_grid.addWidget(w,index//4,index%4)
        self.kva.editingFinished.connect(lambda: self._set("supply_kva", float(self.kva.value())))
        self.phases.activated.connect(lambda _i: self._set("supply_phases", int(self.phases.currentData())))
        self.fuse.editingFinished.connect(lambda: self._set("supply_fuse_a", float(self.fuse.value())))
        self.factor.editingFinished.connect(lambda: self._set("demand_factor", float(self.factor.value())))
        self.waste.editingFinished.connect(lambda: self._set("waste_pct", float(self.waste.value())))
        self.excel = QPushButton("Excel…"); self.excel.clicked.connect(self.export_csv)
        self.pdf = QPushButton("PDF…"); self.pdf.clicked.connect(self.export_pdf)
        self.offer = QPushButton("Προσφορά…"); self.offer.setToolTip("Προσφορά προς τον πελάτη μόνο για τα ηλεκτρολογικά (PDF), "
                                                                    "με τις τιμές του «Τιμές & προσφορά»")
        self.offer.clicked.connect(self.export_offer)
        head.addWidget(self.excel); head.addWidget(self.pdf); head.addWidget(self.offer)
        root.addLayout(head)
        root.addLayout(settings_grid)
        self.pipe_note=QLabel('Γεωμετρική εκτίμηση με ονομαστικές διαμέτρους Nexans H07V-U/R · όριο πλήρωσης έργου, προς μηχανικό έλεγχο.')
        self.pipe_note.setWordWrap(True);root.addWidget(self.pipe_note)

        self.cards = QGridLayout(); self.cards.setHorizontalSpacing(8)
        self.card_labels = {}
        for col, key in enumerate(("installed", "demand", "supply", "main", "phases", "cost")):
            box = QFrame(); box.setFrameShape(QFrame.Shape.StyledPanel)
            v = QVBoxLayout(box); v.setContentsMargins(8, 4, 8, 4); v.setSpacing(0)
            cap, val = QLabel(), QLabel()
            cap.setWordWrap(True)
            cap.setStyleSheet("color:palette(mid);font-size:11px"); val.setStyleSheet("font-weight:600")
            val.setWordWrap(True)
            v.addWidget(cap); v.addWidget(val)
            self.cards.addWidget(box,col//3,col%3)
            self.card_labels[key] = (box, cap, val)
        root.addLayout(self.cards)

        self.empty = QLabel("Δεν υπάρχουν κυκλώματα: βάλτε ηλεκτρικό πίνακα και σημεία "
                            "(Κατασκευή ▸ Η/Μ ▸ Ηλεκτρολογικά) — εδώ εμφανίζονται κυκλώματα, αγωγοί, μέτρα και ο πίνακας.")
        self.empty.setWordWrap(True); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.empty)

        from archforge.ui.electrical_technical_plan import ElectricalTechnicalPlan
        self.technical_plan = ElectricalTechnicalPlan(window.doc,window.stack,self)
        self.technical_plan.setMinimumHeight(220)
        self.pages = QTabWidget()
        # The board as seen from the front, first: what the electrician recognises.
        from archforge.ui.board_front_view import BoardFrontView
        front_page = QWidget(); fv = QVBoxLayout(front_page); fv.setContentsMargins(0, 4, 0, 0)
        self.rcd_bar = QHBoxLayout(); self.rcd_bar.setSpacing(6)
        fv.addLayout(self.rcd_bar)
        self.front_view = BoardFrontView()
        self.front_view.circuit_clicked.connect(self._select_circuit)
        scroll = QScrollArea(); scroll.setWidget(self.front_view); scroll.setWidgetResizable(True)
        fv.addWidget(scroll, 1)
        self.pages.addTab(front_page, "Πρόσοψη πίνακα")
        self.circuits = self._tree(["Κύκλωμα", "Περιγραφή", "Φάση", "Ασφάλεια", "Διατομή", "Σημεία", "Χώροι",
                                    "Φορτίο", "Μήκος", "Ως πιο μακρινό", "Iz*", "ΔU*", "Έλεγχος", "Διαφορικός"])
        self.circuits.itemClicked.connect(self._select_item)
        self.circuits.itemDoubleClicked.connect(lambda item, _c: self._select_item(item, show=True))
        self.walls = self._tree(["Θέση", "Κυκλώματα", "Όδευση γραμμών"])
        self.walls.itemClicked.connect(self._select_item)
        self.walls.itemDoubleClicked.connect(lambda item, _c: self._select_item(item, show=True))
        self.purchase = self._tree(["Διατομή", "Μέτρα", "Με φύρα"])
        self.pages.addTab(self.circuits, "Κυκλώματα και αγωγοί")
        self.pages.addTab(self.walls, "Μέτρα ανά τοίχο")
        self.pages.addTab(self.purchase, "Αγορά καλωδίων")
        # Ασθενή (owner 17/10): network, TV and automation, drawn in 2D/3D on their own layer.
        lv_page = QWidget(); lv = QVBoxLayout(lv_page); lv.setContentsMargins(0, 4, 0, 0)
        row = QHBoxLayout()
        row.addWidget(QLabel("Καλώδιο δικτύου (κατηγορία από τη μελέτη):"))
        self.lv_cable = QComboBox(); self.lv_cable.setEditable(True)
        for text in ("", "Cat 6", "Cat 6A", "Cat 7"):
            self.lv_cable.addItem(text or "— εισάγετε", text)
        self.lv_cable.activated.connect(lambda _i: self._set_rack("network_cable", self.lv_cable.currentData() or ""))
        row.addWidget(self.lv_cable); row.addStretch(1)
        lv.addLayout(row)
        self.lv_tree = self._tree(["Σύστημα / σημείο", "Πλήθος", "Καλώδιο", "Σωλήνας", "Σημείωση"])
        self.lv_tree.itemClicked.connect(self._select_item)
        lv.addWidget(self.lv_tree, 1)
        self.lv_warnings = QLabel(); self.lv_warnings.setWordWrap(True); self.lv_warnings.setStyleSheet("color:#b45309")
        lv.addWidget(self.lv_warnings)
        self.lv_index = self.pages.addTab(lv_page, "Ασθενή — δίκτυο · TV · αυτοματισμοί")
        # Rules and their status: one tab of their own, one short line in view (owner 17/10: «μόνο θόρυβος»).
        self.provenance = QLabel(); self.provenance.setWordWrap(True); self.provenance.setStyleSheet("font-size:11px")
        self.provenance.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rules_scroll = QScrollArea(); rules_scroll.setWidget(self.provenance); rules_scroll.setWidgetResizable(True)
        self.rules_index = self.pages.addTab(rules_scroll, "Κατάσταση κανόνων")
        self.conduits = self._tree(['Σωλήνωση / κομμάτι','Πλήθος','Φ εξ.','Ø εσωτ.','Πλήρωση / όριο','Γραμμές','Αγωγοί','Μήκος','Από','Προς'])
        self.conduits.itemClicked.connect(self._select_item)
        self.pages.addTab(self.conduits,'Σωληνώσεις και καλωδιώσεις')
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.technical_plan); self.splitter.addWidget(self.pages)
        self.splitter.setCollapsible(0,False); self.splitter.setCollapsible(1,False)
        self.splitter.setSizes([280,420])
        root.addWidget(self.splitter,1)
        self.drawing_note = QLabel('Τεχνική κάτοψη: κάθε σωλήνωση χωριστά · ασθενή σε επάνω σειρά · '
                                  'wheel: zoom, σύρσιμο: μετακίνηση. Οι αποστάσεις μεταξύ σειρών είναι σχηματικές.')
        self.drawing_note.setWordWrap(True)
        root.addWidget(self.drawing_note)

        self.warnings = QLabel(); self.warnings.setWordWrap(True); self.warnings.setStyleSheet("color:#b45309")
        self.rules_line = QLabel(); self.rules_line.setStyleSheet("color:palette(mid);font-size:11px")
        root.addWidget(self.warnings); root.addWidget(self.rules_line)

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
        for w in (self.control, self.kva, self.phases, self.fuse, self.factor, self.waste, self.method, self.excel, self.pdf, self.offer):
            w.setEnabled(has)
        self._updating = True
        try:
            conf = r["settings"]
            self.kva.setValue(conf["supply_kva"]); self.fuse.setValue(conf["supply_fuse_a"])
            self.phases.setCurrentIndex(max(0, self.phases.findData(conf["supply_phases"])))
            self.factor.setValue(conf["demand_factor"])
            self.waste.setValue(conf["waste_pct"])
            self.method.setCurrentIndex(max(0, self.method.findData(conf["install_method"])))
            self.control.setCurrentIndex(max(0, self.control.findData(conf["control_system"])))
            self.pipe_profile.setCurrentIndex(max(0,self.pipe_profile.findData(conf['conduit_profile'])))
            self.pipe_max.setCurrentIndex(max(0,self.pipe_max.findData(conf['conduit_max_dn'])))
            self.pipe_fill.setValue(conf['conduit_fill_limit']*100)
            for w in (self.pipe_profile,self.pipe_max,self.pipe_fill):w.setEnabled(conf['panel'] is not None)
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
        if b:
            from archforge.quantities.materials import compare_control_options
            from archforge.quantities.quote import money
            options = compare_control_options(self.window.doc)
            current = options[r["settings"]["control_system"]]
            cost = {k: {kk: v[kk] for kk in ("total", "missing", "priced")} for k, v in options.items()}
            cards["cost"] = ("Κόστος υλικών — σύγκριση για τον πελάτη (τιμοκατάλογος έργου)",
                             "\n".join(f"{v['label'].split(' (')[0]}: " + (f"{money(v['total'])} · {len(v['missing'])} χωρίς τιμή"
                                                                           if v["priced"] else f"— βάλτε τιμές ({len(v['missing'])} είδη)")
                                       for v in options.values()))
            self.result["cost"] = cost; self.result["cost_current"] = current["total"]
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
        self.pages.setTabText(self.rules_index, f"Κατάσταση κανόνων ({len(r['unverified'])})")
        self.rules_line.setText(f"⚠ Κανένας από τους {len(r['unverified'])} κανόνες δεν είναι επαληθευμένος — "
                                "προμελέτη, προς έλεγχο από ηλεκτρολόγο μηχανικό · λεπτομέρειες: «Κατάσταση κανόνων»")
        self.rules_line.setVisible(has)
        self._fill_front(r)
        self._fill_low_voltage()
        self._fill_conduits(r)
        self.technical_plan.rebind(self.window.doc,self.window.stack)
        return r

    def _fill_conduits(self,r):
        from archforge.mep.conduits import conduit_map
        cmap = r['conduit_map'] = conduit_map(self.window.doc)
        by_cid = {c['id']: c for c in r['circuits']}
        self.conduits.clear()
        for p in cmap['pieces']:
            item = QTreeWidgetItem([p['id'],str(p['count']),f"Φ{p['dn']}",f"{p['inner_mm']:g} mm",
                                    f"{p['fill']*100:.1f}% / {p['fill_limit']*100:g}%",','.join(p['lines']),
                                    p['conductors'],f"{p['length_m']:.2f} m",p['from'],p['to']])
            ids = [pid for cid in p['line_ids'] for pid in by_cid.get(cid,{}).get('point_ids',())]
            ids += [cid.split(':',1)[1] for cid in p['line_ids'] if cid.startswith('switch:')]
            item.setData(0,Qt.ItemDataRole.UserRole,ids)
            item.setToolTip(0,f"{p['profile_name']} · {p['profile_source']}\nΟι ίδιες σωληνώσεις εμφανίζονται στην κάτοψη, στο 3D και στην επιμέτρηση. Ονομαστικές διαστάσεις αγωγών· έλεγχος εγκατάστασης εκκρεμεί.")
            for column in (0,4,7,8,9):
                item.setToolTip(column,item.toolTip(column)+'\n'+p['pulling']['summary'])
            self.conduits.addTopLevelItem(item)
        if cmap['warnings']:
            self.warnings.setText(self.warnings.text()+'\n'+'\n'.join(cmap['warnings']))
        if cmap['review']:
            self.pipe_note.setText(f"Έλξη / μελλοντική αντικατάσταση: {len(cmap['review'])} κομμάτια προς έλεγχο · μήκος και αλλαγές διεύθυνσης στις λεπτομέρειες κάθε γραμμής. Η πλήρωση δεν πιστοποιεί εύκολο πέρασμα· ακτίνες καμπυλών και πρόσβαση στα κουτιά ανεπιβεβαίωτες.")
        else:
            self.pipe_note.setText('Γεωμετρική εκτίμηση με ονομαστικές διαμέτρους Nexans H07V-U/R · όριο πλήρωσης έργου, προς μηχανικό έλεγχο.')

    # ------------------------------------------------------------------------------------------------ ασθενή
    def _set_rack(self, key, value):
        lv = self.result.get("low_voltage") if self.result else None
        if not lv or not lv["rack"] or self.window.doc.get(lv["rack"]).params.get(key) == value:
            return
        from archforge.core.commands import UpdateEntity
        self.window.stack.execute(UpdateEntity(lv["rack"], {key: value}))
        self.refresh()

    def _fill_low_voltage(self):
        from archforge.mep.low_voltage import SYSTEM_LABELS, lv_points, route_low_voltage_cached
        lv = self.result["low_voltage"] = route_low_voltage_cached(self.window.doc)
        t = self.lv_tree; t.clear()
        has = bool(lv_points(self.window.doc)) or bool(lv["knx"])
        if has and not self.pages.isVisible() and not self.result["circuits"]:
            self.empty.setVisible(False); self.pages.setVisible(True); self.pages.setCurrentIndex(self.lv_index)
        self.lv_cable.setEnabled(bool(lv["rack"]))
        self._updating = True
        try:
            i = self.lv_cable.findData(lv["cable"])
            if i < 0 and lv["cable"]:
                self.lv_cable.addItem(lv["cable"], lv["cable"]); i = self.lv_cable.findData(lv["cable"])
            self.lv_cable.setCurrentIndex(max(0, i))
        finally:
            self._updating = False
        if lv["rack"]:
            rack = QTreeWidgetItem(["Rack δικτύου / κατανεμητής", "1", "", "", "αφετηρία όλων των γραμμών (αστέρας)"])
            rack.setData(0, Qt.ItemDataRole.UserRole, [lv["rack"]]); t.addTopLevelItem(rack)
        for system in ("network", "tv"):
            tot = lv["totals"].get(system)
            if not tot:
                continue
            top = QTreeWidgetItem([SYSTEM_LABELS[system], str(tot["points"]), f"{_n(tot['cable_m'])} m",
                                   f"{_n(tot['conduit_m'])} m", "ένα καλώδιο ανά σημείο ως το rack"])
            top.setData(0, Qt.ItemDataRole.UserRole, [o["id"] for o in lv["outlets"] if o["system"] == system])
            for o in (o for o in lv["outlets"] if o["system"] == system):
                child = QTreeWidgetItem(top, [o["label"], "", f"{_n(o['cable_m'])} m", "", f"όροφος {_n(o['floor'], 2)} m"])
                child.setData(0, Qt.ItemDataRole.UserRole, [o["id"]])
            t.addTopLevelItem(top); top.setExpanded(True)
        k = lv["knx"]
        if k:
            top = QTreeWidgetItem([SYSTEM_LABELS["knx"], str(k["buttons"]), f"{_n(k['bus_m'])} m", "",
                                   f"ως την πιο μακρινή συσκευή {_n(k['bus_farthest_m'])} m"])
            for label, value in (("Μπουτόν στο bus", k["buttons"]), ("Διευθύνσεις DALI-2", k["dali_addresses"]),
                                 ("KNX-DALI gateways", k["dali_gateways"]), ("Κανάλια ρελέ (On/Off)", k["onoff_channels"])):
                QTreeWidgetItem(top, [label, str(value), "", "", ""])
            t.addTopLevelItem(top); top.setExpanded(True)
        elif lv_points(self.window.doc) or self.result["circuits"]:
            t.addTopLevelItem(QTreeWidgetItem(["Αυτοματισμοί", "", "", "", "συμβατικό σύστημα — KNX: επιλογή στην κορυφή"]))
        notes = lv["warnings"] + list(k.get("warnings", []) if k else [])
        if not lv_points(self.window.doc):
            notes.append("Βάλτε σημεία από Μηχανολογικά ▸ «Ασθενή (δίκτυο / TV)»: rack, πρίζες RJ45 / TV, Wi-Fi.")
        self.lv_warnings.setText("\n".join(f"⚠ {w}" if not w.startswith("Βάλτε") else w for w in notes))

    # ------------------------------------------------------------------------------------- board front view
    def _fill_front(self, r):
        from archforge.mep.electrical_board import front
        f = self.result["front"] = front(r) if r["circuits"] else None
        self.front_view.set_front(f)
        while self.rcd_bar.count():
            item = self.rcd_bar.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not f:
            return
        caption=QLabel('Διαφορικοί (ονομαστικό ρεύμα από τη μελέτη):')
        caption.setWordWrap(True)
        self.rcd_bar.addWidget(caption)
        ratings = list(r["settings"]["rcd_ratings"])
        for nb in f["neutral_bars"]:
            g = nb["group"]
            spin = QDoubleSpinBox(); spin.setRange(0.0, 400.0); spin.setDecimals(0); spin.setSingleStep(1.0)
            spin.setPrefix(f"Δ{g} "); spin.setSuffix(" A"); spin.setSpecialValueText(f"Δ{g} — εισάγετε")
            spin.setValue(float(ratings[g - 1]) if g - 1 < len(ratings) and ratings[g - 1] else 0.0)
            spin.editingFinished.connect(lambda g=g, spin=spin: self._rate_rcd(g, spin.value()))
            self.rcd_bar.addWidget(spin)
        note=QLabel('· κυκλώματα σε διαφορικό: στήλη «Διαφορικός» στα «Κυκλώματα και αγωγοί»')
        note.setWordWrap(True)
        self.rcd_bar.addWidget(note,1)

    def _rate_rcd(self, group, value):
        ratings = list(self.result["settings"]["rcd_ratings"])
        while len(ratings) < group:
            ratings.append(0.0)
        ratings[group - 1] = float(value)
        self._set("rcd_ratings", ratings)

    def _assign_rcd(self, circuit_id, group):
        groups = dict(self.result["settings"]["rcd_groups"])
        groups[circuit_id] = int(group)
        self._set("rcd_groups", groups)

    def _select_circuit(self, circuit_id):
        c = next((c for c in self.result["circuits"] if c["id"] == circuit_id), None) if self.result else None
        ids = [i for i in (c["point_ids"] if c else []) if i in self.window.doc.entities]
        if ids:
            self.window.doc.select(ids)
            if hasattr(self.window, "_redraw_views"):
                self.window._redraw_views(all_views=True)
        self.front_view.set_circuit(circuit_id)
        self.technical_plan.redraw()
        return ids

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
            groups = r["settings"]["rcd_groups"]
            used = max([int(v) for v in groups.values()] + [1])
            combo = QComboBox()
            for g in range(1, used + 2):
                combo.addItem(f"Δ{g}" + (" (νέος)" if g == used + 1 else ""), g)
            combo.setCurrentIndex(max(0, combo.findData(int(groups.get(c["id"], 1) or 1))))
            combo.activated.connect(lambda _i, cid=c["id"], combo=combo: self._assign_rcd(cid, combo.currentData()))
            t.setItemWidget(item, 13, combo)

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
        self.technical_plan.redraw()
        chosen=next((c for c in self.result['circuits'] if set(c['point_ids']).intersection(ids)),None) if self.result else None
        if chosen:self.front_view.set_circuit(chosen['id'])
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

    def export_offer(self, path=None):
        """Client quote for the electrical work only: materials + labour with the project's prices, VAT, totals."""
        from archforge.output.pdf import export_pdf
        if path is None:
            path, _f = QFileDialog.getSaveFileName(self, "Προσφορά ηλεκτρολογικών (PDF)", "prosfora_ilektrologikon.pdf", "PDF (*.pdf)")
        if not path:
            return None
        return export_pdf(self.window.doc, path, include=("quote",), only=("Ηλεκτρολογικά",))

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
