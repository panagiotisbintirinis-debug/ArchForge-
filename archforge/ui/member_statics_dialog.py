"""«Στατικά μέλους»: one column / beam — internal actions per combination, the M/V
envelope, its cross-section with the bars, and fields for the width/height, bars and
stirrups that re-check at once; «Προτεινόμενη λύση» fills the preferred solution,
«Εφαρμογή» stores section + bars in the Document (one undo).

Pure view over ``structure/analysis/member.py``: the dialog never designs anything itself.
"""
from __future__ import annotations

from html import escape

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from archforge.structure.analysis.member import (STIRRUP_BARS, apply_command, member_entry, proposal, rebar_of,
                                                 recheck)
from archforge.structure.analysis.sections import BARS
from archforge.structure.analysis.rc import COVER


class EnvelopeView(QWidget):
    """Beam: bending moment envelope (sagging down, as drawn by engineers) and shear."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.points = []
        self.setMinimumSize(360, 180)

    def set_points(self, points):
        self.points = list(points)
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if len(self.points) < 2:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            return
        w, h = self.width(), self.height()
        L = self.points[-1][0] or 1.0
        mmax = max(max(abs(a[1]), abs(a[2])) for a in self.points) or 1.0
        vmax = max(a[3] for a in self.points) or 1.0
        x0, x1 = 40.0, w - 12.0
        # Upper band: M (sagging + drawn downward), lower band: |V|.
        mid, band = h * 0.36, h * 0.28
        vbase, vband = h - 18.0, h * 0.22

        def X(s):
            return x0 + (x1 - x0) * s / L

        p.setPen(QPen(QColor("#888"), 1))
        p.drawLine(QPointF(x0, mid), QPointF(x1, mid))
        p.drawLine(QPointF(x0, vbase), QPointF(x1, vbase))
        for idx, color in ((2, "#c0392b"), (1, "#2c6fbb")):
            path = QPainterPath(QPointF(X(self.points[0][0]), mid))
            for a in self.points:
                path.lineTo(QPointF(X(a[0]), mid + band * a[idx] / mmax))
            path.lineTo(QPointF(X(self.points[-1][0]), mid))
            c = QColor(color)
            c.setAlpha(60)
            p.fillPath(path, c)
            p.setPen(QPen(QColor(color), 1.5))
            p.drawPath(path)
        path = QPainterPath(QPointF(X(self.points[0][0]), vbase))
        for a in self.points:
            path.lineTo(QPointF(X(a[0]), vbase - vband * a[3] / vmax))
        path.lineTo(QPointF(X(self.points[-1][0]), vbase))
        c = QColor("#27864a")
        c.setAlpha(60)
        p.fillPath(path, c)
        p.setPen(QPen(QColor("#27864a"), 1.5))
        p.drawPath(path)
        p.setPen(QColor("#222"))
        f = QFont(p.font())
        f.setPointSizeF(8)
        p.setFont(f)
        hog = min(a[1] for a in self.points)
        sag = max(a[2] for a in self.points)
        p.drawText(QPointF(4, 12), f"M (kNm): + {sag:.1f} (κάτω) / − {abs(hog):.1f} (άνω ίνα)")
        p.drawText(QPointF(4, vbase - vband - 4), f"|V| max {vmax:.1f} kN")
        p.drawText(QPointF(x1 - 60, h - 4), f"L = {L:.2f} m")


class SectionView(QWidget):
    """Cross-section with the bars and the stirrup, to scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.b, self.h, self.kind, self.design = 0.25, 0.25, "column", {}
        self.setMinimumSize(170, 170)

    def set_section(self, b, h, kind, design):
        self.b, self.h, self.kind, self.design = b, h, kind, design or {}
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        pad = 18.0
        k = min((self.width() - 2 * pad) / self.b, (self.height() - 2 * pad) / self.h)
        W, H = self.b * k, self.h * k
        ox, oy = (self.width() - W) / 2, (self.height() - H) / 2
        p.setPen(QPen(QColor("#555"), 1.2))
        p.setBrush(QColor("#d9d6cf"))
        p.drawRect(QRectF(ox, oy, W, H))
        c = (COVER - 0.004) * k
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor("#7a5230"), 1.2))
        p.drawRoundedRect(QRectF(ox + c, oy + c, W - 2 * c, H - 2 * c), 3, 3)
        p.setBrush(QColor("#3b3b3b"))
        p.setPen(Qt.PenStyle.NoPen)

        def bars(xs_ys, d):
            r = max(2.0, d / 2000 * k)
            for x, y in xs_ys:
                p.drawEllipse(QPointF(ox + x * k, oy + y * k), r, r)

        d = self.design
        if self.kind == "beam":
            for side, y in (("top", None), ("bottom", None)):
                if side not in d:
                    continue
                n, dia = d[side]["n"], d[side]["d"]
                cc = COVER + dia / 2000
                yy = cc if side == "top" else self.h - cc
                xs = [cc + (self.b - 2 * cc) * i / max(n - 1, 1) for i in range(n)]
                bars([(x, yy) for x in xs], dia)
        elif "bars" in d:
            nb, nh, dia = d["bars"]["nb"], d["bars"]["nh"], d["bars"]["d"]
            cc = COVER + dia / 2000
            xs = [cc + (self.b - 2 * cc) * i / max(nb - 1, 1) for i in range(nb)]
            ys = [cc + (self.h - 2 * cc) * i / max(nh - 1, 1) for i in range(nh)]
            pts = {(x, cc) for x in xs} | {(x, self.h - cc) for x in xs} | {(cc, y) for y in ys} | {(self.b - cc, y) for y in ys}
            bars(sorted(pts), dia)
        p.setPen(QColor("#222"))
        p.drawText(QPointF(ox, oy - 4), f"b {self.b * 100:.0f} cm")
        p.save()
        p.translate(ox - 4, oy + H)
        p.rotate(-90)
        p.drawText(QPointF(0, 0), f"{'h' if self.kind == 'beam' else 'd'} {self.h * 100:.0f} cm")
        p.restore()


def _bar_combo(parent, values, current):
    box = QComboBox(parent)
    for v in values:
        box.addItem(f"Ø{v}", v)
    box.setCurrentIndex(max(0, box.findData(int(current))))
    return box


class MemberStaticsDialog(QDialog):
    def __init__(self, window, entity_id):
        super().__init__(window)
        self.window, self.doc, self.entity_id = window, window.doc, entity_id
        from archforge.structure.analysis.settings import get_settings
        self.settings = get_settings(self.doc)
        self.entry, self.error = member_entry(self.doc, entity_id)
        self.design = None
        self.applied = False
        self.setWindowTitle("Στατικά μέλους")
        self.resize(940, 640)
        root = QVBoxLayout(self)
        self.header = QLabel(self)
        self.header.setWordWrap(True)
        root.addWidget(self.header)
        if self.entry is None:
            self.header.setText(f"<b>⚠ {escape(self.error or 'Δεν υπάρχει ανάλυση')}</b>")
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
            buttons.rejected.connect(self.reject)
            root.addWidget(buttons)
            return
        e = self.entry
        what = "Κολόνα" if e["kind"] == "column" else "Δοκός"
        self.header.setText(
            f"<b>{what} {escape(e['name'])}</b> · {'οπλισμένο σκυρόδεμα' if e['material'] == 'rc' else 'χάλυβας ' + escape(str(e.get('section', '')))}"
            f" · μήκος {e['length_m']:.2f} m"
            + (f" · άνοιγμα {e['span_m']:.2f} m" if 'span_m' in e else '')
            + "<br><small>Εντατικά από την τελευταία ανάλυση όλου του φορέα· ο επανέλεγχος κρατά τα ίδια εντατικά. "
              "Μετά την «Εφαρμογή» ο φορέας ξαναλύνεται με τη νέα διατομή.</small>")
        body = QHBoxLayout()
        root.addLayout(body, 1)
        left = QVBoxLayout()
        body.addLayout(left, 3)
        self.table = QTableWidget(len(e["combos"]), 5, self)
        self.table.setHorizontalHeaderLabels(["Συνδυασμός", "N (kN)", "V (kN)", "My (kNm)", "Mz (kNm)"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for r, c in enumerate(e["combos"]):
            for col, text in enumerate((c["combo"], f"{c['N']:.1f}", f"{c['V']:.1f}", f"{c['My']:.1f}", f"{c['Mz']:.1f}")):
                item = QTableWidgetItem(text)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, col, item)
        left.addWidget(QLabel("<b>Εντατικά ανά συνδυασμό</b> (ακραίες τιμές κατά μήκος· N θλίψη +)"))
        left.addWidget(self.table, 1)
        if e["kind"] == "beam":
            self.envelope = EnvelopeView(self)
            self.envelope.set_points(e.get("diagram", ()))
            left.addWidget(QLabel("<b>Περιβάλλουσα M / V</b>"))
            left.addWidget(self.envelope, 1)
        right = QVBoxLayout()
        body.addLayout(right, 2)
        self.section_view = SectionView(self)
        right.addWidget(self.section_view, 1)
        self.fields = {}
        if e["material"] == "rc":
            right.addWidget(self._build_fields())
        else:
            right.addWidget(QLabel("Χαλύβδινη διατομή: η κατάλληλη διατομή επιλέγεται αυτόματα από τον κατάλογο."))
        self.result = QLabel(self)
        self.result.setWordWrap(True)
        self.result.setTextFormat(Qt.TextFormat.RichText)
        right.addWidget(self.result)
        row = QHBoxLayout()
        self.propose_button = QPushButton("Προτεινόμενη λύση", self)
        self.apply_button = QPushButton("Εφαρμογή", self)
        self.undo_button = QPushButton("Αναίρεση", self)
        self.undo_button.setEnabled(False)
        close = QPushButton("Κλείσιμο", self)
        self.propose_button.clicked.connect(self.fill_proposal)
        self.apply_button.clicked.connect(self.apply)
        self.undo_button.clicked.connect(self.undo)
        close.clicked.connect(self.reject)
        row.addWidget(self.undo_button)
        for b in (self.propose_button, self.apply_button):
            b.setEnabled(e["material"] == "rc")
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(close)
        root.addLayout(row)
        self.recheck()

    # ------------------------------------------------------------------ fields
    def _build_fields(self):
        e = self.entry
        group = QGroupBox("Διατομή και οπλισμός (αλλάζεις → επανέλεγχος)", self)
        form = QFormLayout(group)

        def spin_cm(value, lo, hi):
            s = QDoubleSpinBox(group)
            s.setRange(lo, hi)
            s.setDecimals(0)
            s.setSingleStep(5)
            s.setSuffix(" cm")
            s.setValue(round(value * 100))
            return s

        def spin_n(value, lo, hi):
            s = QSpinBox(group)
            s.setRange(lo, hi)
            s.setValue(int(value))
            return s

        f = self.fields
        f["b"] = spin_cm(e["b"], 20, 200)
        f["h"] = spin_cm(e["h"], 20, 200)
        form.addRow("Πλάτος b", f["b"])
        form.addRow("Ύψος h" if e["kind"] == "beam" else "Βάθος d", f["h"])
        if e["kind"] == "beam":
            for side, label in (("bottom", "Κάτω (άνοιγμα)"), ("top", "Άνω (στήριξη)")):
                bars = e.get(side) or {"n": 2, "d": 14}
                f[side + "_n"] = spin_n(bars["n"], 2, 12)
                f[side + "_d"] = _bar_combo(group, BARS, bars["d"])
                line = QHBoxLayout()
                line.addWidget(f[side + "_n"])
                line.addWidget(QLabel("×"))
                line.addWidget(f[side + "_d"])
                form.addRow(label, line)
        else:
            bars = e.get("bars") or {"nb": 3, "nh": 3, "d": 16}
            f["nb"] = spin_n(bars["nb"], 2, 9)
            f["nh"] = spin_n(bars["nh"], 2, 9)
            f["d"] = _bar_combo(group, BARS, bars["d"])
            line = QHBoxLayout()
            for w, t in ((f["nb"], "κατά b"), (f["nh"], "κατά d")):
                line.addWidget(w)
                line.addWidget(QLabel(t))
            line.addWidget(f["d"])
            form.addRow("Ράβδοι ανά πλευρά", line)
        st = e.get("stirrups") or {"d": 8, "s": 0.20, "s_crit": 0.10}
        f["sw_d"] = _bar_combo(group, STIRRUP_BARS, st["d"])
        f["s"] = spin_cm(st["s"], 5, 40)
        f["s_crit"] = spin_cm(st["s_crit"], 5, 40)
        for key in ("s", "s_crit"):
            f[key].setDecimals(1)
            f[key].setSingleStep(2.5)
            f[key].setValue(round(st[key] * 100, 1))
        line = QHBoxLayout()
        line.addWidget(f["sw_d"])
        line.addWidget(QLabel("κρίσιμη περιοχή /"))
        line.addWidget(f["s_crit"])
        line.addWidget(QLabel("υπόλοιπο /"))
        line.addWidget(f["s"])
        form.addRow("Συνδετήρες", line)
        for w in f.values():
            sig = w.currentIndexChanged if isinstance(w, QComboBox) else w.valueChanged
            sig.connect(lambda *_a: self.recheck())
        return group

    def values(self):
        """(b, h, rebar) from the fields."""
        f = self.fields
        b, h = f["b"].value() / 100, f["h"].value() / 100
        if self.entry["kind"] == "beam":
            rebar = {side: {"n": f[side + "_n"].value(), "d": f[side + "_d"].currentData()} for side in ("bottom", "top")}
        else:
            rebar = {"d": f["d"].currentData(), "nb": f["nb"].value(), "nh": f["nh"].value()}
        rebar["stirrups"] = {"d": f["sw_d"].currentData(), "s": round(f["s"].value() / 100, 3),
                             "s_crit": round(f["s_crit"].value() / 100, 3)}
        return b, h, rebar

    def set_values(self, b, h, rebar):
        f = self.fields
        for w in f.values():
            w.blockSignals(True)
        f["b"].setValue(round(b * 100))
        f["h"].setValue(round(h * 100))
        if self.entry["kind"] == "beam":
            for side in ("bottom", "top"):
                if side in rebar:
                    f[side + "_n"].setValue(rebar[side]["n"])
                    f[side + "_d"].setCurrentIndex(f[side + "_d"].findData(rebar[side]["d"]))
        elif "d" in rebar:
            f["nb"].setValue(rebar["nb"])
            f["nh"].setValue(rebar["nh"])
            f["d"].setCurrentIndex(f["d"].findData(rebar["d"]))
        st = rebar.get("stirrups")
        if st:
            f["sw_d"].setCurrentIndex(f["sw_d"].findData(st["d"]))
            f["s"].setValue(round(st["s"] * 100, 1))
            f["s_crit"].setValue(round(st["s_crit"] * 100, 1))
        for w in f.values():
            w.blockSignals(False)
        self.recheck()

    # ------------------------------------------------------------------ actions
    def recheck(self):
        e = self.entry
        if e["material"] != "rc":
            self.design = e
            self.section_view.set_section(e["b"], e["h"], e["kind"], {})
        else:
            b, h, rebar = self.values()
            self.design = recheck(e, self.settings, b, h, rebar)
            self.section_view.set_section(b, h, e["kind"], self.design)
        self.result.setText(self._result_html(self.design))
        return self.design

    def _result_html(self, d):
        u = min(float(d.get("utilisation", 0.0)), 9.99)
        color = "#27864a" if d.get("ok", True) else "#c0392b"
        lines = [f"<b style='color:{color}'>{'✓ Επαρκεί' if d.get('ok', True) else '⚠ Δεν επαρκεί'}</b> · "
                 f"αξιοποίηση <b>{u:.0%}</b>"]
        if self.entry["kind"] == "beam" and self.entry["material"] == "rc":
            i = self.entry["inputs"]
            for side, M, label in (("bottom", i["M_sag"], "M+ (άνοιγμα)"), ("top", i["M_hog"], "M− (στήριξη)")):
                if side in d:
                    lines.append(f"{label}: M<sub>Ed</sub> {M:.1f} ≤ M<sub>Rd</sub> {d[side].get('MRd', 0):.1f} kNm "
                                 f"(As {d[side]['As_cm2']:.2f} / απαιτ. {d[side]['As_req_cm2']:.2f} cm²)")
            if "VRd_s" in d:
                lines.append(f"V<sub>Ed</sub> {i['V']:.1f} · V<sub>Rd,s</sub> {d['VRd_s']:.1f} · V<sub>Rd,max</sub> {d['VRd_max']:.1f} kN")
            if "l_d" in d:
                lines.append(f"Βέλος: l/d {d['l_d']} (όριο {d['l_d_lim']})")
        elif self.entry["material"] == "rc":
            cap = d.get("capacity")
            if cap:
                lines.append(f"N<sub>Ed</sub> {cap['N']:.1f} / N<sub>Rd</sub> {cap['NRd']:.0f} kN · "
                             f"M<sub>Rd,y</sub> {cap['MRdy']:.1f} · M<sub>Rd,z</sub> {cap['MRdz']:.1f} kNm (στο N max)")
            lines.append(f"M<sub>Ed,y</sub> {d.get('My_max', 0):.1f} · M<sub>Ed,z</sub> {d.get('Mz_max', 0):.1f} kNm "
                         f"(με ελάχιστη εκκεντρότητα{' και 2ας τάξης' if d.get('slender') else ''}) · νd {d.get('nu_d', 0):.2f}")
            if "bars" in d:
                lines.append(f"Διαμήκης {d['bars']['n']}Ø{d['bars']['d']} · ρ {d['bars']['rho']:.2f} %")
            if "VRd_s" in d:
                lines.append(f"V<sub>Ed</sub> {self.entry['inputs']['V']:.1f} · V<sub>Rd,s</sub> {d['VRd_s']:.1f} kN")
        for c in d.get("checks", []):
            lines.append(f"<span style='color:#c0392b'>⚠ {escape(c)}</span>")
        lines.append("<small><i>Προμελέτη (EN 1992-1-1 / EN 1998-1 ΚΠΜ) — όχι στατική μελέτη αδειοδοτημένου μηχανικού.</i></small>")
        return "<br>".join(lines)

    def fill_proposal(self):
        b, h, d = proposal(self.doc, self.entry, self.settings)
        self.set_values(b, h, rebar_of(d))
        return d

    def _reload(self):
        """Re-solve the frame with the Document as it is now and show this member again."""
        entry, error = member_entry(self.doc, self.entity_id)
        if entry is None:
            self.result.setText(f"<b>⚠ {escape(error or '')}</b>")
            return None
        self.entry = entry
        if self.entry["kind"] == "beam" and hasattr(self, "envelope"):
            self.envelope.set_points(entry.get("diagram", ()))
        for r, c in enumerate(entry["combos"][:self.table.rowCount()]):
            for col, text in enumerate((c["combo"], f"{c['N']:.1f}", f"{c['V']:.1f}", f"{c['My']:.1f}", f"{c['Mz']:.1f}")):
                self.table.item(r, col).setText(text)
        if self.fields:
            self.set_values(entry["b"], entry["h"], rebar_of(entry))
        else:
            self.recheck()
        return entry

    def _refresh_window(self, text):
        w = self.window
        for name in ("_refresh_project_tree", "_schedule_assistant_refresh"):
            if hasattr(w, name):
                getattr(w, name)()
        if hasattr(w, "_redraw_views"):
            w._redraw_views(all_views=True)
        if hasattr(w, "statusBar"):
            w.statusBar().showMessage(text, 9000)

    def undo(self):
        """Back to the section and bars before the last «Εφαρμογή» (the same Ctrl+Z step)."""
        if not self.applied:
            return None
        self.window.stack.undo()
        self.applied = False
        self.undo_button.setEnabled(False)
        self._refresh_window(f"{self.entry['name']}: αναίρεση διατομής/οπλισμού")
        return self._reload()

    def apply(self):
        """Store section + bars (one undo), re-solve the whole frame and show the new result;
        the dialog stays open so the change is seen at once in the drawing and here."""
        b, h, rebar = self.values()
        try:
            self.window.stack.execute(apply_command(self.doc, self.entity_id, b, h, rebar))
        except (PermissionError, ValueError) as exc:          # locked layer / entity, invalid size
            self.result.setText(self.result.text() + f"<br><b style='color:#c0392b'>⚠ {escape(str(exc))}</b>")
            return None
        self.applied = True
        self.undo_button.setEnabled(True)
        self._refresh_window(f"{self.entry['name']}: διατομή {b * 100:.0f}/{h * 100:.0f} και οπλισμός αποθηκεύτηκαν "
                             "— «Αναίρεση» ή Ctrl+Z")
        self._reload()
        return rebar
