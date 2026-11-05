"""«Θερμομονώσεις»: η θερμική εικόνα μιας όψης σήμερα και με την πρόταση, όπως το mockup v2 (ιδιοκτήτης 05/11).

* Επιλογή όψης (εξωτερικοί τοίχοι με σύνθεση), πλευρά (από έξω — προεπιλογή — / από μέσα), παλέτα (iron, rainbow, γκρι,
  5 σημείων, Rainbow HC / Arctic ως προσέγγιση, ζώνες του χρήστη σε °C) και κλίμακα (αυτόματη / ίδια με φωτογραφία).
* Οι εικόνες από τον υπολογισμό 3Δ αγωγής (``mep.facade_thermal``), σήμερα και πρόταση στην ίδια κλίμακα.
* «Συντεταγμένες» κάθε στοιχείου στην παλέτα: U, θ, θέση %, χρώμα — σύγκριση με το χρώμα της κάμερας.
* Σύνθεση πρότασης με το ίδιο εργαλείο +/− στρώσεων (``wall_details_dialog``, ιδιοκτήτης 04/11: «δεν χάνεται ποτέ»)·
  η πρόταση δεν αλλάζει τίποτα στο έργο.
* Για τον πελάτη: W σήμερα / πρόταση / μείωση, και Umax της ζώνης (ΤΟΤΕΕ 20701-2 Πίν. 6).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QGridLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from archforge.ui.wall_details_dialog import WallDetailsDialog

TAB_TITLE = "Θερμομονώσεις"
IMAGE_W = 480


def _num(v, d=2):
    return f"{v:.{d}f}".replace(".", ",").replace("-", "−")


def pixmap(rgb, width=IMAGE_W):
    """A QPixmap of a ``(rows, cols, 3)`` uint8 array, scaled smoothly to ``width``."""
    import numpy as np
    a = np.ascontiguousarray(rgb)
    h, w = a.shape[:2]
    img = QImage(a.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(img).scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)


def legend_pixmap(lo, hi, palette, zones, width=240, height=12):
    import numpy as np
    from archforge.mep import thermal_compare as C
    row = np.linspace(lo, hi, width).reshape(1, width)
    return pixmap(np.repeat(C.to_rgb(row, lo, hi, palette, zones), height, axis=0), width)


class ProfileWidget(QWidget):
    """«Διάχυση στη σύνδεση»: surface temperature along a line across the frame's edge."""

    def __init__(self):
        super().__init__()
        self.profile = None
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_profile(self, profile):
        self.profile = profile
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().adjusted(40, 10, -10, -22)
        p.fillRect(self.rect(), self.palette().base())
        prof = self.profile
        if not prof or len(prof["s"]) < 2:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Χωρίς κολόνα / δοκό στην όψη: δεν υπάρχει σύνδεση")
            return
        s, th = prof["s"], prof["theta"]
        lo, hi = min(th), max(th)
        span = (hi - lo) or 1.0
        smax = s[-1] or 1.0
        x = lambda v: r.left() + r.width() * v / smax
        y = lambda v: r.bottom() - r.height() * (v - lo) / span
        p.fillRect(int(r.left()), int(r.top()), int(x(prof["edge"]) - r.left()), int(r.height()), QColor(80, 60, 30, 90))
        p.setPen(QPen(QColor(245, 170, 60), 2))
        for i in range(1, len(s)):
            p.drawLine(QPointF(x(s[i - 1]), y(th[i - 1])), QPointF(x(s[i]), y(th[i])))
        p.setPen(self.palette().text().color())
        p.drawText(int(r.left()) + 4, int(r.top()) + 14, f"{_num(th[0])} °C")
        p.drawText(int(r.right()) - 60, int(r.bottom()) - 4, f"{_num(th[-1])} °C")
        p.drawText(int(r.left()), int(r.bottom()) + 16, "0")
        p.drawText(int(r.right()) - 40, int(r.bottom()) + 16, f"{round(smax * 100)} cm")


class ProposalLayersDialog(WallDetailsDialog):
    """The +/− layer editor of the wall dialog, for the proposal only: Save keeps the rows, the project is untouched."""

    def __init__(self, window, wall_type, specs=None):
        super().__init__(window, wall_type=wall_type)
        self.setWindowTitle("Σύνθεση πρότασης — στρώσεις (το έργο δεν αλλάζει)")
        form = self.layout().itemAt(0).layout()
        for w in (self.type_combo, self.name_edit, self.context, self.scope_box):
            w.setVisible(False)
            label = form.labelForField(w)
            if label is not None:
                label.setVisible(False)
        if specs is not None:
            self._set_rows(specs)
        self.note.setText("Η πρόταση μένει στην καρτέλα «Θερμομονώσεις»: το έργο αλλάζει μόνο από «Λεπτομέρειες τοίχου».")
        self.result_specs = None

    def accept(self):
        self.result_specs = [r for r in self.layer_specs() if r["thickness"] > 0]
        QDialog.accept(self)


class ZonesDialog(QDialog):
    """The user's zone palette: «από; έως; #χρώμα» per line, in °C or °F (converted to °C on import)."""

    def __init__(self, parent, text=""):
        super().__init__(parent)
        self.setWindowTitle("Παλέτα ζωνών (ισόθερμες)")
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Μία ζώνη ανά γραμμή: «από; έως; #RRGGBB» — κενό = ανοιχτό άκρο (π.χ. «105; ; #B71C1C»)."))
        self.edit = QPlainTextEdit(text)
        lay.addWidget(self.edit)
        row = QHBoxLayout(); row.addWidget(QLabel("Μονάδα του πίνακα:"))
        self.unit = QComboBox(); self.unit.addItem("°C", "C"); self.unit.addItem("°F (μετατρέπεται σε °C)", "F")
        row.addWidget(self.unit); row.addStretch(1); lay.addLayout(row)
        self.error = QLabel(); self.error.setStyleSheet("color:#d9534f"); lay.addWidget(self.error)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject); lay.addWidget(bb)
        self.zones = None

    def accept(self):
        from archforge.mep import thermal_compare as C
        try:
            self.zones = C.zones_in_celsius(C.parse_zones(self.edit.toPlainText()), self.unit.currentData())
        except ValueError as exc:
            self.error.setText(str(exc))
            return
        super().accept()


def _ro(text, tip=None):
    it = QTableWidgetItem(text)
    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if tip:
        it.setToolTip(tip)
    return it


class ThermalFacadeTab(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._stale = True
        self._proposals = {}                    # wall id → {"specs": [...] or None, "uw": float or None}
        self.zones = None
        self.result = None
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); outer.addWidget(scroll)
        host = QWidget(); scroll.setWidget(host)
        root = QVBoxLayout(host); root.setContentsMargins(10, 8, 10, 8)

        bar = QHBoxLayout()
        title = QLabel("Θερμομονώσεις — θερμική εικόνα όψης"); title.setStyleSheet("font-weight:600;font-size:15px")
        bar.addWidget(title)
        self.facade_combo = QComboBox(); self.facade_combo.setMinimumWidth(280)
        self.side_combo = QComboBox(); self.side_combo.addItem("Από έξω", "exterior"); self.side_combo.addItem("Από μέσα", "interior")
        self.palette_combo = QComboBox()
        from archforge.mep import thermal_compare as C
        for key, (label, _stops, _status) in C.PALETTES.items():
            self.palette_combo.addItem(label, key)
        self.palette_combo.addItem("ζώνες του χρήστη (°C)…", C.ZONES)
        self.scale_combo = QComboBox(); self.scale_combo.addItem("Κλίμακα: αυτόματη", "auto")
        self.scale_combo.addItem("ίδια με φωτογραφία: min / max", "fixed")
        self.min_spin, self.max_spin = QDoubleSpinBox(), QDoubleSpinBox()
        for s, v in ((self.min_spin, 0.0), (self.max_spin, 10.0)):
            s.setRange(-60.0, 200.0); s.setDecimals(1); s.setSuffix(" °C"); s.setValue(v); s.setEnabled(False)
        bar.addStretch(1)
        insulation = QPushButton("Μονώσεις…")
        insulation.setToolTip("Θερμομόνωση και στεγάνωση ανά επιφάνεια (καρτέλα «Μονώσεις»)")
        insulation.clicked.connect(lambda: __import__("archforge.ui.insulation_tab", fromlist=["show"]).show(window))
        bar.addWidget(insulation)
        root.addLayout(bar)
        bar = QHBoxLayout()
        for w in (QLabel("Όψη:"), self.facade_combo, self.side_combo, self.palette_combo, self.scale_combo,
                  self.min_spin, self.max_spin):
            bar.addWidget(w)
        bar.addStretch(1)
        root.addLayout(bar)
        self.header = QLabel(); self.header.setStyleSheet("color:palette(mid);font-size:11px"); self.header.setWordWrap(True)
        root.addWidget(self.header)

        grid = QGridLayout(); root.addLayout(grid, 1)
        left, right = QVBoxLayout(), QVBoxLayout()
        grid.addLayout(left, 0, 0); grid.addLayout(right, 0, 1)
        grid.setColumnStretch(0, 3); grid.setColumnStretch(1, 2)

        self.today_box = QGroupBox("Σήμερα — όπως η μελέτη"); tl = QVBoxLayout(self.today_box)
        self.today_img = QLabel(); self.today_img.setAlignment(Qt.AlignmentFlag.AlignLeft); tl.addWidget(self.today_img)
        leg = QHBoxLayout(); self.lo_label, self.legend, self.hi_label = QLabel(), QLabel(), QLabel()
        for w in (self.lo_label, self.legend, self.hi_label):
            leg.addWidget(w)
        leg.addStretch(1); tl.addLayout(leg)
        left.addWidget(self.today_box)
        self.profile_box = QGroupBox("Διάχυση στη σύνδεση (θερμοκρασία επιφάνειας)"); pl = QVBoxLayout(self.profile_box)
        self.profile = ProfileWidget(); pl.addWidget(self.profile)
        self.profile_note = QLabel(); self.profile_note.setWordWrap(True)
        self.profile_note.setStyleSheet("color:palette(mid);font-size:11px"); pl.addWidget(self.profile_note)
        left.addWidget(self.profile_box)
        self.prop_box = QGroupBox("Με την πρόταση"); ql = QVBoxLayout(self.prop_box)
        self.prop_img = QLabel("Χωρίς πρόταση: «Σύνθεση πρότασης (+/−)…» ή Uw πρότασης")
        ql.addWidget(self.prop_img)
        left.addWidget(self.prop_box); left.addStretch(1)

        coords = QGroupBox("«Συντεταγμένες» κάθε στοιχείου στην παλέτα"); cl = QVBoxLayout(coords)
        self.coords = QTableWidget(0, 8)
        self.coords.setHorizontalHeaderLabels(["Στοιχείο", "U", "θ σήμερα", "θέση", "U πρότ.", "θ πρόταση", "θέση", "χρώμα"])
        self.coords.verticalHeader().setVisible(False)
        self.coords.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.coords.setMaximumHeight(130)
        cl.addWidget(self.coords)
        hint = QLabel("Με «ίδια με φωτογραφία» η θέση στην παλέτα συγκρίνεται κατευθείαν με το χρώμα της κάμερας. "
                      "Στην εικόνα γράφεται θερμοκρασία, όχι ποιότητα μόνωσης.")
        hint.setWordWrap(True); hint.setStyleSheet("color:palette(mid);font-size:11px"); cl.addWidget(hint)
        right.addWidget(coords)
        self.today_layers_box = QGroupBox("Σύνθεση — σήμερα"); sl = QVBoxLayout(self.today_layers_box)
        self.today_layers = self._layers_table(); sl.addWidget(self.today_layers)
        right.addWidget(self.today_layers_box)
        pbox = QGroupBox("Σύνθεση — πρόταση"); bl = QVBoxLayout(pbox)
        self.prop_layers = self._layers_table(); bl.addWidget(self.prop_layers)
        prow = QHBoxLayout()
        self.compose_btn = QPushButton("Σύνθεση πρότασης (+/−)…"); self.compose_btn.clicked.connect(self.compose)
        self.clear_btn = QPushButton("Χωρίς πρόταση"); self.clear_btn.clicked.connect(self.clear_proposal)
        self.uw_check = QCheckBox("Uw πρότασης"); self.uw_spin = QDoubleSpinBox()
        self.uw_spin.setRange(0.3, 7.0); self.uw_spin.setDecimals(2); self.uw_spin.setValue(1.4); self.uw_spin.setSuffix(" W/m²K")
        self.uw_spin.setEnabled(False)
        for w in (self.compose_btn, self.clear_btn, self.uw_check, self.uw_spin):
            prow.addWidget(w)
        prow.addStretch(1); bl.addLayout(prow)
        right.addWidget(pbox)
        client = QGroupBox("Για τον πελάτη"); kl = QHBoxLayout(client)
        self.w_today, self.w_prop, self.w_red = QLabel("—"), QLabel("—"), QLabel("—")
        for cap, lab, colour in (("Σήμερα", self.w_today, "#f0805a"), ("Πρόταση", self.w_prop, "#6fd08c"),
                                 ("Μείωση", self.w_red, "#6fd08c")):
            box = QVBoxLayout(); box.addWidget(QLabel(cap))
            lab.setStyleSheet(f"font-size:22px;font-weight:700;color:{colour}"); box.addWidget(lab); kl.addLayout(box)
        right.addWidget(client)
        self.umax = QLabel(); self.umax.setWordWrap(True); self.umax.setStyleSheet("font-size:11px")
        right.addWidget(self.umax); right.addStretch(1)

        self.facade_combo.activated.connect(lambda _i: self.recompute())
        self.side_combo.activated.connect(lambda _i: self.recompute())
        self.palette_combo.activated.connect(self._palette_chosen)
        self.scale_combo.activated.connect(self._scale_chosen)
        self.min_spin.editingFinished.connect(self.recompute)
        self.max_spin.editingFinished.connect(self.recompute)
        self.uw_check.toggled.connect(self._uw_toggled)
        self.uw_spin.editingFinished.connect(self._uw_changed)

    # ------------------------------------------------------------------ state
    def _layers_table(self):
        t = QTableWidget(0, 5)
        t.setHorizontalHeaderLabels(["Υλικό (έξω → μέσα)", "cm", "λ", "R", "Πηγή λ"])
        t.verticalHeader().setVisible(False)
        h = t.horizontalHeader()
        for c in range(4):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        t.setMaximumHeight(210)
        return t

    def wall_id(self):
        return self.facade_combo.currentData()

    def proposal(self):
        return self._proposals.setdefault(self.wall_id(), {"specs": None, "uw": None})

    def mark_stale(self):
        self._stale = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh()

    def refresh(self):
        """Re-list the façades (keeping the chosen one) and recompute."""
        from archforge.mep import thermal_compare as C
        self._stale = False
        current = self.wall_id()
        self.facade_combo.blockSignals(True)
        self.facade_combo.clear()
        for wid, label in C.facades(self.window.doc):
            self.facade_combo.addItem(label, wid)
        i = self.facade_combo.findData(current)
        self.facade_combo.setCurrentIndex(max(0, i))
        self.facade_combo.blockSignals(False)
        return self.recompute()

    def _palette_chosen(self, _i):
        from archforge.mep import thermal_compare as C
        if self.palette_combo.currentData() == C.ZONES:
            dlg = ZonesDialog(self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.zones = dlg.zones
            elif self.zones is None:
                self.palette_combo.setCurrentIndex(0)
        self.recompute()

    def _scale_chosen(self, _i):
        fixed = self.scale_combo.currentData() == "fixed"
        if fixed and self.result is not None:
            self.min_spin.setValue(self.result["lo"]); self.max_spin.setValue(self.result["hi"])
        self.min_spin.setEnabled(fixed); self.max_spin.setEnabled(fixed)
        self.recompute()

    def _uw_toggled(self, on):
        self.uw_spin.setEnabled(on)
        self.proposal()["uw"] = self.uw_spin.value() if on else None
        self.recompute()

    def _uw_changed(self):
        if self.uw_check.isChecked():
            self.proposal()["uw"] = self.uw_spin.value()
            self.recompute()

    def compose(self):
        from archforge.architecture.wall_assemblies import layer_specs
        wid = self.wall_id()
        if wid is None:
            return None
        doc = self.window.doc
        wall_type = doc.get(wid).params.get("wall_type", "generic")
        specs = self.proposal()["specs"] or layer_specs(doc, wall_type)
        dlg = ProposalLayersDialog(self.window, wall_type, specs)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.set_proposal_layers(dlg.result_specs)
        return dlg

    def set_proposal_layers(self, specs):
        """``[{"material", "thickness" m, "role"}]`` exterior first, or None; recomputes."""
        self.proposal()["specs"] = list(specs) if specs else None
        return self.recompute()

    def clear_proposal(self):
        self._proposals[self.wall_id()] = {"specs": None, "uw": None}
        self.uw_check.blockSignals(True); self.uw_check.setChecked(False); self.uw_check.blockSignals(False)
        self.uw_spin.setEnabled(False)
        return self.recompute()

    # ------------------------------------------------------------------ compute + show
    def _proposal_layers(self):
        from archforge.construction.building_materials import material
        from archforge.mep import facade_thermal as F
        specs = self.proposal()["specs"]
        if not specs:
            return None
        doc = self.window.doc
        out = []
        for s in specs:
            m = material(s["material"], doc)
            if m is None or not m.conductivity or float(s["thickness"]) <= 0:
                continue
            out.append(F.layer(doc, s["material"], s["thickness"], s.get("role")))
        return out or None

    def recompute(self):
        from archforge.mep import thermal_compare as C
        wid = self.wall_id()
        if wid is None or wid not in self.window.doc.entities:
            self.result = None
            self.header.setText("Καμία εξωτερική όψη με σύνθεση τοίχου: δώσε τύπο στους εξωτερικούς τοίχους "
                                "(Επεξεργασία › Επιλογή εξωτερικών τοίχων → Τύπος).")
            self.today_img.clear(); self.prop_img.clear(); self.coords.setRowCount(0)
            return None
        prop = self.proposal()
        self.uw_check.blockSignals(True); self.uw_check.setChecked(prop["uw"] is not None); self.uw_check.blockSignals(False)
        self.uw_spin.setEnabled(prop["uw"] is not None)
        if prop["uw"] is not None:
            self.uw_spin.setValue(prop["uw"])
        palette = self.palette_combo.currentData()
        zones = self.zones if palette == C.ZONES else None
        if palette == C.ZONES and not zones:
            palette = "iron"
        scale = (self.min_spin.value(), self.max_spin.value()) if self.scale_combo.currentData() == "fixed" else None
        side = self.side_combo.currentData()
        try:
            r = C.compare(self.window.doc, wid, layers=self._proposal_layers(), opening_u=prop["uw"], side=side,
                          scale=scale, palette=palette, zones=zones)
        except ValueError as exc:
            self.result = None
            self.header.setText(f"Δεν υπολογίστηκε: {exc}")
            return None
        self.result = r
        self._show(r, palette, zones)
        return r

    def _show(self, r, palette, zones):
        from archforge.mep import thermal_compare as C
        side = r["side"]
        key = "theta" if side == "exterior" else "theta_inside"
        t = r["today"]
        self.header.setText(
            f"{self.facade_combo.currentText()} · θi {_num(t['theta_i'], 1)} °C / θe {_num(t['theta_e'], 1)} °C"
            + (f" · ζώνη {r['zone']}" if r["zone"] else "")
            + f" · {'από έξω (θse)' if side == 'exterior' else 'από μέσα (θsi)'} · υπολογισμός 3Δ αγωγής (EN ISO 10211)"
            + ("" if palette in ("iron", "rainbow", "gray", C.ZONES) else
               f" · παλέτα {C.PALETTES[palette][0]}"))
        self.today_img.setPixmap(pixmap(C.to_rgb(t[key], r["lo"], r["hi"], palette, zones)))
        self.lo_label.setText(f"{_num(r['lo'], 1)} °C")
        self.hi_label.setText(f"{_num(r['hi'], 1)} °C")
        self.legend.setPixmap(legend_pixmap(r["lo"], r["hi"], palette, zones))
        p = r["proposal"]
        if p is not None:
            self.prop_img.setPixmap(pixmap(C.to_rgb(p[key], r["lo"], r["hi"], palette, zones)))
            self.prop_box.setTitle("Με την πρόταση — ίδια κλίμακα με το «σήμερα»")
        else:
            self.prop_img.clear()
            self.prop_img.setText("Χωρίς πρόταση: «Σύνθεση πρότασης (+/−)…» ή Uw πρότασης")
            self.prop_box.setTitle("Με την πρόταση")
        prof = C.junction_profile(t, side)
        self.profile.set_profile(prof)
        if prof:
            self.profile_box.setTitle(f"Διάχυση στη {prof['label']} (θερμοκρασία επιφάνειας)")
            self.profile_note.setText(
                "Η θερμότητα περνά πλάγια μέσα σε όλο το πάχος: η μετάβαση απλώνεται, όπως στη φωτογραφία — δεν είναι "
                f"«απόλυτη» τιμή ανά υλικό. Απώλειες 3Δ της όψης: {round(t['watts'])} W.")
        else:
            self.profile_note.setText("")
        self._fill_coords(r)
        self._fill_layers(self.today_layers, t["layers"])
        self._fill_layers(self.prop_layers, p["layers"] if p is not None and self.proposal()["specs"] else [])
        w_now, w_p = r["watts"]
        self.w_today.setText(f"{round(w_now)} W")
        self.w_prop.setText("—" if w_p is None else f"{round(w_p)} W")
        self.w_red.setText("—" if r["reduction"] is None else f"{_num(r['reduction'] * 100, 0)} %")
        if r["u_max"] is not None:
            frame = next((x["u"] for x in r["rows"] if x["kind"] == 1), None)
            masonry = next((x["u"] for x in r["rows"] if x["kind"] == 0), None)
            self.umax.setText(f"Umax {r['u_max_source']}: τοίχοι {_num(r['u_max'])} — "
                              f"τοιχοποιία σήμερα {_num(masonry) if masonry else '—'}"
                              + (f", κολόνες/δοκοί σήμερα {_num(frame)}" if frame else ""))
        else:
            self.umax.setText("Umax: χωρίς ζώνη στο έργο (Θέρμανση › Θερμοκρασίες σχεδιασμού…)")

    def _fill_coords(self, r):
        rows = r["rows"]
        self.coords.setRowCount(len(rows))
        for i, x in enumerate(rows):
            cells = [x["label"], "—" if x["u"] is None else _num(x["u"]), f"{_num(x['theta'], 1)} °C",
                     f"{round(x['pos'] * 100)} %"]
            if "theta_proposal" in x:
                cells += ["—" if x["u_proposal"] is None else _num(x["u_proposal"]),
                          f"{_num(x['theta_proposal'], 1)} °C", f"{round(x['pos_proposal'] * 100)} %"]
            else:
                cells += ["", "", ""]
            for c, text in enumerate(cells):
                self.coords.setItem(i, c, _ro(text))
            sw = _ro("", f"σήμερα {x['colour']}" + (f" · πρόταση {x['colour_proposal']}" if "colour_proposal" in x else ""))
            sw.setBackground(QColor(x["colour"]))
            self.coords.setItem(i, 7, sw)

    def _fill_layers(self, table, layers):
        from archforge.construction.building_materials import material
        doc = self.window.doc
        table.setRowCount(len(layers))
        for i, (mid, d, lam, _role) in enumerate(layers):
            m = material(mid, doc)
            src = getattr(m, "conductivity_source", "") or getattr(m, "conductivity_status", "") or ""
            for c, text in enumerate((m.name if m else mid, _num(d * 100, 1), _num(lam, 3), _num(d / lam, 2), str(src))):
                table.setItem(i, c, _ro(text, str(src) if c == 4 else None))


def install(window):
    tab = ThermalFacadeTab(window)
    window._thermal_facade_tab = tab
    window.stack.listeners.append(tab.mark_stale)
    return tab


def show(window, wall_id=None):
    tab = getattr(window, "_thermal_facade_tab", None)
    tabs = getattr(window, "_central_tabs", None)
    if tab is None or tabs is None:
        return None
    if tabs.indexOf(tab) < 0:
        tabs.addTab(tab, TAB_TITLE)
    tabs.setCurrentWidget(tab)
    tab.refresh()
    if wall_id is not None:
        i = tab.facade_combo.findData(wall_id)
        if i >= 0:
            tab.facade_combo.setCurrentIndex(i)
            tab.recompute()
    return tab
