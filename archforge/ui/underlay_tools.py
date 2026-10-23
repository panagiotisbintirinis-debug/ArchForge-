"""Αρχείο ▸ Εισαγωγή ▸ «Σχέδιο μηχανικού (PDF / DXF) ως υπόβαθρο…», calibration with two clicks, properties.

The underlay goes under the active storey — or, from a section tab («Υπόβαθρο τομής…»), under that
section, placed with two clicks there; everything is one undoable command.
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QPushButton, QSlider

from archforge.core.commands import AddEntity, UpdateEntity
from archforge.core.model import Entity


def import_drawing(window, path=None, unit=None, scale=None, page=None, section_id=None):
    """Ask for the file (and unit / scale / page) and add the underlay; returns the entity or None.

    With ``section_id`` it is the underlay of that section (drawn only in its tab)."""
    from archforge.project import underlay as U
    if path is None:
        title = "Τομή μηχανικού ως υπόβαθρο" if section_id else "Σχέδιο μηχανικού ως υπόβαθρο"
        path, _f = QFileDialog.getOpenFileName(window, title, "",
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
                found, how = detect_scale(path, page)
                scale, ok = QInputDialog.getDouble(
                    window, "Κλίμακα σχεδίου",
                    (f"Βρέθηκε 1:{found} ({how}) — έλεγξέ την.\n" if found else
                     "Η κλίμακα δεν γράφεται στο σχέδιο ούτε βγαίνει από διαστάσεις:\nδώσε μία και μετά «Ταίριασμα με 2 σημεία».\n")
                    + "Κλίμακα, 1 : ", float(found or 50), 1.0, 10000.0, 0)
                if not ok:
                    return None
            pt = pdf.pagePointSize(page)
            params = U.pdf_params(path, page, scale, (pt.width(), pt.height()), z)
    except (OSError, ValueError) as exc:
        QMessageBox.warning(window, "Υπόβαθρο", str(exc))
        return None
    if section_id:
        params = U.for_section(params, section_id)
    # Never takes plan clicks (not design geometry); selected from the project tree for its properties.
    entity = Entity("underlay", params, name=f"Υπόβαθρο {'τομής ' if section_id else ''}{name}")
    window.stack.execute(AddEntity(entity))
    window._redraw_views(all_views=True)
    if section_id:
        _refresh_section(window, fit=True)
        start_placing(window, entity.id)
        return entity
    window.statusBar().showMessage("Υπόβαθρο: έλεγξε την κλίμακα — Ιδιότητες ▸ «Βαθμονόμηση (2 κλικ)» σε γνωστή διάσταση", 10000)
    return entity


def detect_scale(path, page=0):
    """(1:N, how) from the drawing: «SCALE 1:50» written on it, else its dimensions (drawing_text); (None, '')."""
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from archforge.project import drawing_text as T
    from archforge.project.underlay import pdf_vector_segments
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        texts = T.pdf_texts(path, page)
        written = T.scale(texts)
        if written:
            return written, "γράφεται στο σχέδιο"
        n, votes = T.scale_from_dimensions(texts, pdf_vector_segments(path, page))
        return (n, f"από {votes} διαστάσεις") if n else (None, "")
    except Exception:                                   # noqa: BLE001 — a drawing without text: ask
        return None, ""
    finally:
        QApplication.restoreOverrideCursor()


def _refresh_section(window, fit=False):
    panel = getattr(window, "_section_panel", None)
    if panel is not None:
        panel.refresh(fit=fit)


def _section_tab(window, eid):
    """Section underlay: bring its section tab forward (the clicks go there); None for a plan underlay."""
    sid = window.doc.get(eid).params.get("section_id")
    if sid and sid in window.doc.entities:
        from archforge.ui.section_view import open_section
        panel = getattr(window, "_section_panel", None)
        if panel is None or panel.view.entity_id != sid or not panel.isVisible():
            open_section(window, sid)
    return sid


def start_calibration(window, eid):
    window._underlay_calibration = {"id": eid, "points": [], "mode": "calibrate"}
    if _section_tab(window, eid):
        window.statusBar().showMessage("Βαθμονόμηση στην τομή: κλικ στην αρχή και στο τέλος μιας γνωστής διάστασης "
                                       "του σχεδίου (π.χ. ύψος ορόφου) — Esc ακύρωση", 0)
        return
    window._start_site_tool("underlay_calibrate", "Βαθμονόμηση υποβάθρου: κλικ στην αρχή και στο τέλος μιας γνωστής διάστασης")


def start_placing(window, eid):
    """Two clicks in the section: a point of the drawing (e.g. its ±0,00 at the building's edge), then where it belongs."""
    window._underlay_calibration = {"id": eid, "points": [], "mode": "place"}
    _section_tab(window, eid)
    window.statusBar().showMessage("Τοποθέτηση τομής: κλικ σε ένα σημείο του σχεδίου (π.χ. ±0,00 στην άκρη του κτιρίου), "
                                   "μετά κλικ εκεί που ανήκει στην τομή του ArchForge — Esc ακύρωση", 0)


ALIGN_STEPS = ("Ταίριασμα: κλικ σε ένα σημείο του σχεδίου (π.χ. γωνία κτιρίου)",
               "Ταίριασμα: κλικ εκεί που ανήκει αυτό το σημείο (η ίδια γωνία στο μοντέλο)",
               "Ταίριασμα: κλικ σε δεύτερο σημείο του σχεδίου, μακριά από το πρώτο",
               "Ταίριασμα: κλικ εκεί που ανήκει το δεύτερο σημείο")


def start_aligning(window, eid):
    """Four clicks: two drawing points and where each belongs — scale, turn and place (a masterplan)."""
    window._underlay_calibration = {"id": eid, "points": [], "mode": "align"}
    if not _section_tab(window, eid):
        window._start_site_tool("underlay_calibrate", ALIGN_STEPS[0])
    window.statusBar().showMessage(ALIGN_STEPS[0] + " — Esc ακύρωση", 0)


def calibration_click(window, x, y, real=None):
    """Two clicks, then the real distance (or, placing, the move; aligning, four clicks): one UpdateEntity (undo)."""
    from archforge.project.underlay import aligned, calibrated, moved
    state = getattr(window, "_underlay_calibration", None)
    if not state:
        return None
    state["points"].append((float(x), float(y)))
    if state.get("mode") == "align":
        if len(state["points"]) < 4:
            window.statusBar().showMessage(ALIGN_STEPS[len(state["points"])] + " — Esc ακύρωση", 0)
            return None
        window._underlay_calibration = None
        a, a2, b, b2 = state["points"]
        e = window.doc.get(state["id"])
        try:
            changes = aligned(e.params, a, a2, b, b2)
        except ValueError as exc:
            window.statusBar().showMessage(str(exc), 6000)
            return None
        window.stack.execute(UpdateEntity(e.id, changes))
        if e.params.get("section_id"):
            _refresh_section(window)
        else:
            window.plan_view.controller.set_tool("select")
            window._redraw_views(all_views=True)
        scale_n = changes["m_per_unit"] / (25.4 / 72.0 / 1000.0) if e.params.get("source") == "pdf" else None
        window.statusBar().showMessage("Ταιριάστηκε" + (f" — κλίμακα 1:{scale_n:.0f}" if scale_n else "")
                                       + f", στροφή {changes['rotation']:.1f}° · Ctrl+Z αναιρεί".replace(".", ","), 10000)
        return changes
    placing = state.get("mode") == "place"
    if len(state["points"]) < 2:
        window.statusBar().showMessage("Τοποθέτηση: τώρα κλικ εκεί που ανήκει αυτό το σημείο" if placing else
                                       "Βαθμονόμηση: τώρα κλικ στο τέλος της διάστασης", 0 if placing else 6000)
        return None
    a, b = state["points"]
    window._underlay_calibration = None
    e = window.doc.get(state["id"])
    section = bool(e.params.get("section_id"))
    if placing:
        changes = moved(e.params, a, b)
        window.stack.execute(UpdateEntity(e.id, changes))
        _refresh_section(window)
        window.statusBar().showMessage("Υπόβαθρο τοποθετήθηκε — έλεγξε ένα γνωστό ύψος με «Βαθμονόμηση» · Ctrl+Z αναιρεί", 8000)
        return changes
    if real is None:
        import math
        real, ok = QInputDialog.getDouble(window, "Βαθμονόμηση", f"Πραγματική απόσταση (m) — τώρα {math.dist(a, b):.3f} m:",
                                          round(math.dist(a, b), 3), 0.001, 100000.0, 3)
        if not ok:
            return None
    try:
        changes = calibrated(e.params, a, b, float(real))
    except ValueError as exc:
        window.statusBar().showMessage(str(exc), 6000)
        return None
    window.stack.execute(UpdateEntity(e.id, changes))
    if section:
        _refresh_section(window)
    else:
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
    align = QPushButton("Ταίριασμα με 2 σημεία (κλίμακα, στροφή, θέση)"); align.clicked.connect(lambda: start_aligning(window, eid))
    align.setToolTip("Δύο σημεία του σχεδίου και πού ανήκει το καθένα — π.χ. το masterplan πάνω στα κτίρια")
    window.form.addRow(align)
    sid = p.get("section_id")
    if not sid and p.get("source") == "pdf":
        from archforge.ui import building_from_underlay as B
        build = QPushButton("Κτίριο από το υπόβαθρο (τοίχοι, κουφώματα, χώροι)")
        build.setToolTip("Στον ενεργό όροφο: τοίχοι, πόρτες/παράθυρα από τις ετικέτες «w: … | h: …», ονόματα χώρων, δάπεδο — μία αναίρεση")
        build.clicked.connect(lambda: B.build(window, eid))
        ground = QPushButton("Έδαφος από τα υψόμετρα του σχεδίου")
        ground.setToolTip("Κάθε υψόμετρο που γράφει το σχέδιο (+111.80m, 126.00m …) γίνεται σημείο εδάφους")
        ground.clicked.connect(lambda: B.terrain(window, eid))
        window.form.addRow(build); window.form.addRow(ground)
    if sid:
        place = QPushButton("Τοποθέτηση στην τομή (2 κλικ)"); place.clicked.connect(lambda: start_placing(window, eid))
        window.form.addRow(place)
        from PySide6.QtWidgets import QLabel as _L
        window.form.addRow("Τομή", _L(window.doc.get(sid).name if sid in window.doc.entities else "⚠ η γραμμή τομής διαγράφηκε"))
    from PySide6.QtWidgets import QLabel
    window.form.addRow("Αρχείο", QLabel(os.path.basename(str(p.get("path", "")))))
    if p.get("source") == "pdf" and not os.path.exists(str(p.get("path", ""))):
        window.form.addRow("", QLabel("⚠ Το αρχείο PDF δεν βρέθηκε στη θέση του"))
    return True
