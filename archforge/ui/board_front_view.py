"""The electrical board seen from the front: rails with the main switch, RCDs and breakers,
neutral bars per RCD, the earth bar, and the conductors between them (schematic).

Drawn only from ``mep.electrical_board.front(result)``; nothing here decides a rating.
Click a breaker = its circuit's points are selected in the drawing (``on_circuit``).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

# Drawing convention only — board.conductor_colours (UNVERIFIED against ΕΛΟΤ HD 308).
WIRE = {"L1": "#8B4513", "L2": "#222222", "L3": "#8a8a8a", "L": "#8B4513", "N": "#1f5fbf", "PE": "#3c9a3c"}
MW, DH, RAIL_GAP, PAD, BAR_STEP = 34.0, 96.0, 70.0, 26.0, 50.0


def _fmt(v, unit):
    return "—" if v in (None, 0, 0.0) else f"{float(v):g} {unit}".replace(".", ",")


class BoardFrontView(QWidget):
    circuit_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.front = None
        self.selected_circuit = None
        self._hits = []
        self.setMinimumSize(560, 360)

    def set_front(self, front):
        self.front = front
        outputs = front.get('outputs',[]) if front else []
        if self.selected_circuit not in {o['circuit'] for o in outputs}:
            self.selected_circuit = outputs[0]['circuit'] if outputs else None
        self._hits = []
        if front:
            rails = max(len(front["rails"]), 1)
            widest = max((sum(d["modules"] for d in r) for r in front["rails"]), default=12)
            bars = 1 + len(front["neutral_bars"])
            terms = max([len(front["earth_bar"])] + [len(n["terminals"]) for n in front["neutral_bars"]])
            self.setMinimumSize(int(max(600, 2 * PAD + max(widest, 12) * MW + 140, 2 * PAD + 160 + 30 * terms)),
                                int(130 + rails * (DH + RAIL_GAP) + bars * BAR_STEP + 90 +
                                    (60+24*max(len(o["conductors"]) for o in outputs) if outputs else 0)))
        self.update()

    def set_circuit(self,circuit_id):
        if self.front and any(o['circuit']==circuit_id for o in self.front.get('outputs',())):
            self.selected_circuit=circuit_id
            self.update()

    def _output_wiring(self,p,y,w):
        output=next((o for o in self.front.get('outputs',()) if o['circuit']==self.selected_circuit),None)
        if output is None:return y
        p.setPen(QColor('#1f2937'))
        p.drawText(QPointF(PAD,y),f"{output['circuit']} — σύνδεση προς {output['label']}")
        y+=18
        for code,_label,section in output['conductors']:
            source = (f"Ασφάλεια {output['circuit']} ({output.get('phase') or 'L'})" if code=='L' else
                      output['neutral_bar'] if code=='N' else 'Μπάρα PE' if code=='PE' else 'Έλεγχος DALI από τη μελέτη')
            p.setPen(QColor('#374151'));p.drawText(QRectF(PAD,y-10,210,20),Qt.AlignmentFlag.AlignVCenter,source)
            pen=QPen(QColor(WIRE.get(code,'#75608c')),2.2)
            if code.startswith('DA'):pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen);p.drawLine(QPointF(PAD+216,y),QPointF(w-PAD-135,y))
            p.drawEllipse(QPointF(w-PAD-135,y),3,3)
            p.setPen(QColor('#1f2937'))
            p.drawText(QPointF(w-PAD-123,y+4),f"{code} · {section:g} mm²".replace('.',','))
            y+=24
        return y+18

    # ------------------------------------------------------------------------------------------------ paint
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        f = self.front
        if not f:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "—")
            return
        font = QFont(p.font()); font.setPointSizeF(8.5); p.setFont(font)
        w = float(self.width())
        # Enclosure.
        p.setPen(QPen(QColor("#9aa3ad"), 2)); p.setBrush(QColor("#f3f4f6"))
        top = 64.0
        p.drawRoundedRect(QRectF(PAD - 10, top - 14, w - 2 * PAD + 20, self.height() - top - 10), 8, 8)
        # Incoming supply.
        p.setPen(QColor("#222"))
        bold = QFont(font); bold.setBold(True); bold.setPointSizeF(10); p.setFont(bold)
        sup = {1: "ΜΟΝΟΦΑΣΙΚΗ", 3: "ΤΡΙΦΑΣΙΚΗ"}.get(f["phases"], "ΦΑΣΕΙΣ: ;")
        p.drawText(QPointF(PAD, 22), f"ΠΑΡΟΧΗ ΔΕΔΔΗΕ · {sup}")
        p.setFont(font)
        if f["ask_phases"]:
            p.setPen(QColor("#c0392b"))
            p.drawText(QPointF(PAD, 40), "Επιλέξτε στην κορυφή «Μονοφασική» ή «Τριφασική» — από αυτό εξαρτώνται οι πόλοι "
                                         "του γενικού και των διαφορικών και η κατανομή φάσεων.")
        lines = ["L1", "L2", "L3"] if f["phases"] == 3 else ["L"]
        lines += ["N", "PE"]
        x0 = PAD + 6
        for i, c in enumerate(lines):
            p.setPen(QPen(QColor(WIRE[c]), 3))
            x = x0 + i * 8
            p.drawLine(QPointF(x, 46), QPointF(x, top + 6))
        self._hits = []
        y = top + 12
        rcd_out, rcd_in, main_rect, combs = {}, {}, None, {}
        for rail in f["rails"]:
            # DIN rail.
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor("#c9ced6"))
            p.drawRect(QRectF(PAD, y + DH / 2 - 6, w - 2 * PAD, 12))
            x = PAD + 70
            for d in rail:
                rect = QRectF(x, y, d["modules"] * MW - 2, DH)
                self._device(p, d, rect)
                if d["kind"] == "main":
                    main_rect = rect
                if d["kind"] == "rcd":
                    rcd_out[d["group"]] = QPointF(rect.center().x(), rect.bottom())
                    rcd_in[d["group"]] = rect
                if d["kind"] == "mcb":
                    self._hits.append((rect, d["circuit"]))
                    ph = d.get("phase") or "L"
                    p.setPen(QPen(QColor(WIRE.get(ph, WIRE["L"])), 2))
                    p.drawLine(QPointF(rect.center().x(), rect.top()), QPointF(rect.center().x(), rect.top() - 12))
                    combs.setdefault((d["group"], y), []).append(rect)
                x += d["modules"] * MW
            y += DH + RAIL_GAP
        # Supply → main; main → every RCD; each RCD → its breakers (comb busbar above them).
        live = QColor(WIRE["L1"] if f["phases"] == 3 else WIRE["L"])
        p.setBrush(Qt.BrushStyle.NoBrush)
        if main_rect is not None:
            p.setPen(QPen(live, 2.4))
            p.drawLine(QPointF(x0, top + 6), QPointF(x0, main_rect.top() - 6))
            p.drawLine(QPointF(x0, main_rect.top() - 6), QPointF(main_rect.center().x(), main_rect.top() - 6))
            p.drawLine(QPointF(main_rect.center().x(), main_rect.top() - 6), QPointF(main_rect.center().x(), main_rect.top()))
            for g, r in rcd_in.items():
                path = QPainterPath(QPointF(main_rect.left() + 8, main_rect.bottom()))
                path.lineTo(main_rect.left() + 8, main_rect.bottom() + 14 + 4 * g)
                path.lineTo(PAD + 50, main_rect.bottom() + 14 + 4 * g)
                path.lineTo(PAD + 50, r.top() - 8)
                path.lineTo(r.left() + 10, r.top() - 8)
                path.lineTo(r.left() + 10, r.top())
                p.drawPath(path)
        for (g, _y), rects in combs.items():
            first, last = rects[0], rects[-1]
            yb = first.top() - 12
            p.setPen(QPen(live, 3))
            p.drawLine(QPointF(first.center().x(), yb), QPointF(last.center().x(), yb))
            r = rcd_in.get(g)
            if r is not None:
                p.setPen(QPen(live, 2))
                path = QPainterPath(QPointF(r.right() - 10, r.top()))
                path.lineTo(r.right() - 10, r.top() - 18 if abs(r.top() - first.top()) < 1 else r.bottom() + 20)
                if abs(r.top() - first.top()) < 1:
                    path.lineTo(first.center().x(), r.top() - 18); path.lineTo(first.center().x(), yb)
                else:
                    path.lineTo(first.left() - 6, r.bottom() + 20); path.lineTo(first.left() - 6, yb)
                    path.lineTo(first.center().x(), yb)
                p.drawPath(path)
        # Neutral bars (one per RCD) and the earth bar.
        p.setFont(font)
        bar_x = PAD + 70
        for nb in f["neutral_bars"]:
            self._bar(p, QRectF(bar_x, y, max(160.0, 30.0 * (len(nb["terminals"]) + 1)), 18), nb["label"],
                      nb["terminals"], WIRE["N"], "#d4b26a")
            if nb["group"] in rcd_out:
                a = rcd_out[nb["group"]]
                path = QPainterPath(a); path.lineTo(a.x(), y - 8); path.lineTo(bar_x + 8, y - 8); path.lineTo(bar_x + 8, y)
                p.setPen(QPen(QColor(WIRE["N"]), 1.6)); p.setBrush(Qt.BrushStyle.NoBrush); p.drawPath(path)
            y += BAR_STEP
        self._bar(p, QRectF(bar_x, y, max(160.0, 30.0 * (len(f["earth_bar"]) + 1)), 18), "PE", f["earth_bar"],
                  WIRE["PE"], "#9fd59f")
        p.setPen(QPen(QColor(WIRE["PE"]), 2))
        p.drawLine(QPointF(x0 + 8 * (len(lines) - 1), top + 6), QPointF(x0 + 8 * (len(lines) - 1), y + 9))
        p.drawLine(QPointF(x0 + 8 * (len(lines) - 1), y + 9), QPointF(bar_x, y + 9))
        y += BAR_STEP
        y = self._output_wiring(p,y,w)
        p.setPen(QColor("#555"))
        p.drawText(QRectF(PAD, y - 12, w - 2 * PAD, 40), Qt.TextFlag.TextWordWrap,
                   "Σχηματικό (board.front_layout), όχι κατασκευαστικό σχέδιο · χρώματα αγωγών: σύμβαση σχεδίου — "
                   "κωδικοποίηση κατά ΕΛΟΤ HD 308 προς επαλήθευση · κλικ σε ασφάλεια = τα σημεία του κυκλώματος")

    def _device(self, p, d, rect):
        kind = d["kind"]
        fill = {"main": "#4b5563", "rcd": "#dbeafe", "mcb": "#ffffff"}[kind]
        p.setPen(QPen(QColor("#374151"), 1.2)); p.setBrush(QColor(fill))
        p.drawRoundedRect(rect, 3, 3)
        # Lever.
        lever = QRectF(rect.center().x() - 5, rect.top() + 34, 10, 20)
        p.setBrush(QColor("#111827" if kind != "main" else "#f9fafb")); p.drawRect(lever)
        ink = QColor("#f9fafb" if kind == "main" else "#111827")
        p.setPen(ink)
        small = QFont(p.font()); small.setPointSizeF(7.5); p.setFont(small)
        poles = f"{d['poles']}P" if d.get("poles") else "?P"
        if kind == "main":
            head, sub = "ΓΕΝΙΚΟΣ", f"{poles} {_fmt(d['rating_a'], 'A')}"
        elif kind == "rcd":
            head, sub = d["label"], f"{poles} {_fmt(d['rating_a'], 'A')} / {d['sensitivity_ma']} mA"
            p.drawText(QRectF(rect.left() + 3, rect.top() + 58, 18, 12), Qt.AlignmentFlag.AlignCenter, "T")
        else:
            head, sub = d["label"], _fmt(d["rating_a"], "A")
            ph = d.get("phase")
            if ph:
                p.fillRect(QRectF(rect.left() + 2, rect.top() + 2, rect.width() - 4, 4), QColor(WIRE.get(ph, WIRE["L"])))
        p.drawText(QRectF(rect.left(), rect.top() + 8, rect.width(), 12), Qt.AlignmentFlag.AlignCenter, head)
        p.drawText(QRectF(rect.left(), rect.top() + 20, rect.width(), 12), Qt.AlignmentFlag.AlignCenter, sub)
        if kind == "mcb":
            p.setPen(QColor("#111827"))
            p.drawText(QRectF(rect.left(), rect.bottom() - 26, rect.width(), 12), Qt.AlignmentFlag.AlignCenter,
                       d.get("phase") or "—")
            p.drawText(QRectF(rect.left() - 4, rect.bottom() - 14, rect.width() + 8, 12), Qt.AlignmentFlag.AlignCenter,
                       d.get("cable", ""))
            # Outgoing cable and what it feeds.
            p.save()
            p.translate(rect.center().x() + 3, rect.bottom() + 6)
            p.rotate(60)
            p.drawText(QPointF(0, 0), (d.get("use") or "")[:18])
            p.restore()

    @staticmethod
    def _bar(p, rect, label, terminals, wire, metal):
        p.setPen(QPen(QColor("#6b7280"), 1)); p.setBrush(QColor(metal)); p.drawRect(rect)
        p.setPen(QColor("#111827"))
        p.drawText(QPointF(rect.left() - 52, rect.center().y() + 4), label)
        for i, t in enumerate(terminals):
            cx = rect.left() + 22 + i * 30
            p.setPen(QPen(QColor("#374151"), 1)); p.setBrush(QColor("#9ca3af"))
            p.drawEllipse(QPointF(cx, rect.center().y()), 4, 4)
            p.setPen(QPen(QColor(wire), 1.6))
            p.drawLine(QPointF(cx, rect.bottom()), QPointF(cx, rect.bottom() + 8))
            p.setPen(QColor("#111827"))
            p.drawText(QRectF(cx - 15, rect.bottom() + 9, 30, 12), Qt.AlignmentFlag.AlignCenter,
                       "Παρ." if t == "ΠΑΡΟΧΗ" else t)

    def mousePressEvent(self, event):
        pos = event.position()
        for rect, cid in self._hits:
            if rect.contains(pos):
                self.set_circuit(cid)
                self.circuit_clicked.emit(cid)
                return
        super().mousePressEvent(event)

    def circuit_at(self, x, y):
        return next((cid for rect, cid in self._hits if rect.contains(QPointF(x, y))), None)
