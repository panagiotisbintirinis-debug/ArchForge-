"""Αρχείο ▸ Εισαγωγή ▸ «Σχέδιο μηχανικού (PDF / DXF) ως υπόβαθρο…», calibration with two clicks, properties.

The underlay goes under the active storey; everything is one undoable command.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QPushButton, QSlider

from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity


def import_drawing(window, path=None, unit=None, scale=None, page=None):
    """Ask for the file (and unit / scale / page) and add the underlay; returns the entity or None."""
    from archforge.project import underlay as U
    if path is None:
        path, _f = QFileDialog.getOpenFileName(window, "Σχέδιο μηχανικού ως υπόβαθρο", "",
                                               "Σχέδια (*.pdf *.dxf);;PDF (*.pdf);;DXF (*.dxf)")
    if not path:
        return None
    z = float(window.doc.work_plane.origin[2])
    name = os.path.basename(path)
    try:
        if path.lower().endswith(".dxf"):
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            if unit is None:
                options = []
                for u in U.DXF_UNITS:
                    w, h = U.dxf_size_m(text, u)
                    options.append(f"{u} → το σχέδιο γίνεται {w:.2f} × {h:.2f} m".replace(".", ","))
                choice, ok = QInputDialog.getItem(window, "Μονάδες του DXF", "Σε τι μονάδες σχεδιάστηκε; (δες ποιο μέγεθος είναι λογικό)",
                                                  options, 0, False)
                if not ok:
                    return None
                unit = list(U.DXF_UNITS)[options.index(choice)]
            params = U.dxf_params(path, text, unit, z)
        else:
            from PySide6.QtPdf import QPdfDocument
            pdf = QPdfDocument(window)
            if pdf.load(path) != QPdfDocument.Error.None_:
                raise ValueError("Το PDF δεν άνοιξε")
            if page is None:
                page = 0
                if pdf.pageCount() > 1:
                    page, ok = QInputDialog.getInt(window, "Σελίδα", f"Ποια σελίδα (1–{pdf.pageCount()});", 1, 1, pdf.pageCount())
                    if not ok:
                        return None
                    page -= 1
            if scale is None:
                scale, ok = QInputDialog.getDouble(window, "Κλίμακα σχεδίου", "Κλίμακα από την πινακίδα, 1 : ", 50.0, 1.0, 10000.0, 0)
                if not ok:
                    return None
            pt = pdf.pagePointSize(page)
            params = U.pdf_params(path, page, scale, (pt.width(), pt.height()), z)
    except (OSError, ValueError) as exc:
        QMessageBox.warning(window, "Υπόβαθρο", str(exc))
        return None
    # Never takes plan clicks (not design geometry); selected from the project tree for its properties.
    entity = Entity("underlay", params, name=f"Υπόβαθρο {name}")
    window.stack.execute(AddEntity(entity))
    window._redraw_views(all_views=True)
    window.statusBar().showMessage("Υπόβαθρο: έλεγξε την κλίμακα — Ιδιότητες ▸ «Βαθμονόμηση (2 κλικ)» σε γνωστή διάσταση", 10000)
    return entity


def start_calibration(window, eid):
    window._underlay_calibration = {"id": eid, "points": []}
    window._start_site_tool("underlay_calibrate", "Βαθμονόμηση υποβάθρου: κλικ στην αρχή και στο τέλος μιας γνωστής διάστασης")


def calibration_click(window, x, y, real=None):
    """Two clicks, then the real distance: one UpdateEntity (undo)."""
    from archforge.project.underlay import calibrated
    state = getattr(window, "_underlay_calibration", None)
    if not state:
        return None
    state["points"].append((float(x), float(y)))
    if len(state["points"]) < 2:
        window.statusBar().showMessage("Βαθμονόμηση: τώρα κλικ στο τέλος της διάστασης", 6000)
        return None
    a, b = state["points"]
    window._underlay_calibration = None
    if real is None:
        import math
        real, ok = QInputDialog.getDouble(window, "Βαθμονόμηση", f"Πραγματική απόσταση (m) — τώρα {math.dist(a, b):.3f} m:",
                                          round(math.dist(a, b), 3), 0.001, 100000.0, 3)
        if not ok:
            return None
    e = window.doc.get(state["id"])
    try:
        changes = calibrated(e.params, a, b, float(real))
    except ValueError as exc:
        window.statusBar().showMessage(str(exc), 6000)
        return None
    window.stack.execute(UpdateEntity(e.id, changes))
    window.plan_view.controller.set_tool("select")
    window._redraw_views(all_views=True)
    window.statusBar().showMessage(f"Υπόβαθρο βαθμονομήθηκε: {real:g} m", 6000)
    return changes


def add_rows(window, eid):
    """Properties of an underlay: opacity, calibration, lock."""
    e = window.doc.get(eid)
    p = e.params
    slider = QSlider(); from PySide6.QtCore import Qt; slider.setOrientation(Qt.Orientation.Horizontal)
    slider.setRange(5, 100); slider.setValue(int(round(float(p.get("opacity", 0.6)) * 100)))
    slider.sliderReleased.connect(lambda w=slider: window._set_entity_choice(eid, "opacity", w.value() / 100.0))
    window.form.addRow("Διαφάνεια", slider)
    cal = QPushButton("Βαθμονόμηση (2 κλικ σε γνωστή διάσταση)"); cal.clicked.connect(lambda: start_calibration(window, eid))
    window.form.addRow(cal)
    from PySide6.QtWidgets import QLabel
    window.form.addRow("Αρχείο", QLabel(os.path.basename(str(p.get("path", "")))))
    if p.get("source") == "pdf" and not os.path.exists(str(p.get("path", ""))):
        window.form.addRow("", QLabel("⚠ Το αρχείο PDF δεν βρέθηκε στη θέση του"))
    return True
