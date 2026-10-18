"""«Στέγη: στρώσεις και λίστα κοπής»: layers view (build-up, G, U) and framing view (cutting list) of the selected
roof, else of every tiled roof (structure/roof_framing.py)."""
from __future__ import annotations


def show(window):
    from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget
    from archforge.structure.roof_framing import PROVENANCE, cutting_list, layers
    roofs = [window.doc.get(i) for i in window.doc.selection if i in window.doc.entities and window.doc.get(i).kind == "pitched_roof"] \
        or [e for e in window.doc.entities.values() if e.kind == "pitched_roof"]
    dialog = QDialog(window)
    dialog.setWindowTitle("Στέγη: στρώσεις και λίστα κοπής")
    outer = QVBoxLayout(dialog)
    if not roofs:
        outer.addWidget(QLabel("Δεν υπάρχει κεραμοσκεπή στο έργο."))
    tabs = QTabWidget()
    out = []
    for n, roof in enumerate(roofs, 1):
        p = roof.params
        lv, cl = layers(p), cutting_list(p)
        out.append((lv, cl))
        page = QWidget(); box = QVBoxLayout(page)
        box.addWidget(QLabel(f"Στρώσεις (από κάτω προς τα πάνω) · G = {lv['g_kn_m2']:.2f} kN/m² · U ≈ {lv['u_w_m2k']:.2f} W/m²K"))
        t1 = QTableWidget(len(lv["rows"]), 4); t1.setHorizontalHeaderLabels(("Στρώση", "Πάχος (cm)", "Βάρος (kN/m²)", "λ (W/mK)"))
        for i, (name, th, w, lam, _r) in enumerate(lv["rows"]):
            for j, v in enumerate((name, f"{th * 100:.1f}", f"{w:.2f}", "—" if lam is None else f"{lam:.3f}")):
                t1.setItem(i, j, QTableWidgetItem(v))
        t1.resizeColumnsToContents(); box.addWidget(t1)
        ridge = cl["ridge"]
        box.addWidget(QLabel(f"Ξυλεία · κυβισμός παραγγελίας {cl['volume_total_m3']:.2f} m³ · επιφάνεια κλίσης {cl['slope_area_m2']:.1f} m² · "
                             f"λάτες {cl['battens_m']:.0f} m · αντιλάτες {cl['counter_battens_m']:.0f} m"
                             + (f" · κορφιάς σε {ridge['posts'] + 1} ανοίγματα των {ridge['span_m']:.2f} m" if ridge else "")))
        heads = ("Κωδικοί", "Ξύλο", "Διατομή (cm)", "Τεμ.", "Μήκος παραγγελίας (m)", "Κοπές")
        t2 = QTableWidget(len(cl["rows"]), len(heads)); t2.setHorizontalHeaderLabels(heads)
        for i, r in enumerate(cl["rows"]):
            codes = r["codes"][0] + (f" … {r['codes'][-1]}" if len(r["codes"]) > 1 else "")
            for j, v in enumerate((codes, r["name"], r["section"], str(r["count"]), f"{r['order_m']:.2f}", " · ".join(r["cuts"]))):
                t2.setItem(i, j, QTableWidgetItem(v))
        t2.resizeColumnsToContents(); box.addWidget(t2)
        vol = QLabel("Κυβισμός ανά διατομή: " + ", ".join(f"{k}: {v:.3f} m³" for k, v in cl["volume_m3"].items()))
        vol.setWordWrap(True); box.addWidget(vol)
        tabs.addTab(page, roof.name or f"Στέγη {n}")
    outer.addWidget(tabs)
    note = QLabel(PROVENANCE); note.setWordWrap(True); outer.addWidget(note)
    dialog.resize(1000, 680)
    if not getattr(window, "_no_modal_dialogs", False):
        dialog.exec()
    return out
