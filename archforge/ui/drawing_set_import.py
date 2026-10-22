"""Αρχείο ▸ Εισαγωγή ▸ «Σύνολο σχεδίων (πολλά PDF)…» (owner 22/10: «πάνω από δύο PDF σε σειρά … να συγχωνευτούν
παραμετρικά για να δώσουν το αποτέλεσμα»).

The sheets are read and related (project/drawing_set.py); after one confirmation (what was found, which altitude
is ±0,00) the project is made in one undoable step:

* every placed sheet becomes an underlay where it belongs (plans on their storey, the site plan at ±0,00);
* storeys per building from the floor levels written (OLD VILLA: ±0,00 = +131,80, lower floor −2,80 → +129,00);
* each plan is built on its storey (walls, doors / windows, room names, floor — ui/building_from_underlay.py);
* the ground from the site plan's altitudes (sloped plots: the building sits in the slope, as the section shows).
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox, QProgressDialog

FLOOR_NAMES = {"basement": "Υπόγειο", "lower": "Κάτω όροφος", "ground": "Ισόγειο", "upper": "Πάνω όροφος", "roof": "Δώμα"}
KIND_NAMES = {"plan": "κάτοψη", "section": "τομή", "site": "γενική διάταξη", "elevation": "όψη"}


def read(window, paths):
    """Sheets of ``paths`` (progress shown; Esc stops) — None when stopped."""
    from archforge.project.drawing_set import read_sheet
    progress = QProgressDialog("Ανάγνωση σχεδίων…", "Διακοπή", 0, len(paths), window)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    sheets = []
    for i, path in enumerate(paths):
        progress.setValue(i)
        progress.setLabelText(f"Ανάγνωση {i + 1}/{len(paths)}: {path.split('/')[-1]}")
        QApplication.processEvents()
        if progress.wasCanceled():
            return None
        sheets.append(read_sheet(path))
    progress.setValue(len(paths))
    return sheets


def plan_storeys(sheets, placed, reference):
    """``{sheet index: (storey name, z)}`` for the placed plans; z = floor altitude − ``reference``."""
    from archforge.project.drawing_set import building_zero, floor_altitude
    out = {}
    for i, s in enumerate(sheets):
        if i not in placed or s.kind != "plan":
            continue
        zero = building_zero([t for t in sheets if t.building == s.building])
        alt = floor_altitude(s, zero)
        if alt is None:
            continue
        name = f"{s.building.title() or 'Κτίριο'} — {FLOOR_NAMES.get(s.floor, 'στάθμη')} {alt:+.2f}".replace(".", ",")
        out[i] = (name, round(alt - reference, 3), alt)
    # Two sheets of one building at one altitude (the plan and the pool-room plan) share the storey.
    first = {}
    for i, (name, z, alt) in sorted(out.items(), key=lambda kv: FLOOR_NAMES.get(sheets[kv[0]].floor) is None):
        key = (sheets[i].building, alt)
        first.setdefault(key, name)
        out[i] = (first[key], z, alt)
    return out


def default_reference(sheets, storeys):
    """±0,00: the ground floor's altitude (the first ground floor plan), else the lowest plan."""
    ground = [alt for i, (_n, _z, alt) in storeys.items() if sheets[i].floor == "ground"]
    alts = [alt for _n, _z, alt in storeys.values()]
    return ground[0] if ground else (min(alts) if alts else 0.0)


def summary_text(sheets, placed, storeys):
    lines = []
    for i, s in enumerate(sheets):
        where = placed.get(i)
        what = f"{s.building or 'οικόπεδο'} · {KIND_NAMES.get(s.kind, s.kind)}" + (f" · {FLOOR_NAMES.get(s.floor, '')}" if s.floor else "")
        scale = f"1:{s.scale}" if s.scale else "κλίμακα ;"
        if where is None:
            how = "χωρίς θέση" + (" (τομή: στην καρτέλα τομής)" if s.kind == "section" else " — «Ταίριασμα με 2 σημεία» μετά")
        else:
            how = where[1]
        storey = f" → {storeys[i][0]}" if i in storeys else ""
        lines.append(f"• {s.path.split('/')[-1]}: {what}, {scale} — {how}{storey}")
    return "\n".join(lines)


def import_set(window, paths=None, reference=None, ask=True):
    """The whole flow; returns ``{"sheets", "placed", "storeys", "built", "terrain"}`` or None."""
    from archforge.core.commands import AddEntity, CreateFloorLevel
    from archforge.core.model import Entity
    from archforge.project.drawing_set import relate
    from archforge.project.underlay import pdf_params
    from archforge.ui import building_from_underlay as B
    if paths is None:
        paths, _f = QFileDialog.getOpenFileNames(window, "Σύνολο σχεδίων (πολλά PDF)", "", "PDF (*.pdf)")
    if not paths:
        return None
    sheets = read(window, list(paths))
    if sheets is None:
        return None
    placed = relate(sheets)
    probe = plan_storeys(sheets, placed, 0.0)
    if reference is None:
        reference = default_reference(sheets, probe)
    if ask:
        reference, ok = QInputDialog.getDouble(
            window, "Σύνολο σχεδίων", summary_text(sheets, placed, probe) +
            "\n\nΠοιο απόλυτο υψόμετρο είναι το ±0,00 του έργου;", float(reference), -500.0, 9000.0, 2)
        if not ok:
            return None
    storeys = plan_storeys(sheets, placed, float(reference))
    doc, stack = window.doc, window.stack
    since = len(stack.done)
    QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    built, terrain = {}, None
    try:
        for i, (sim, _how) in sorted(placed.items(), key=lambda kv: (sheets[kv[0]].kind != "site", storeys.get(kv[0], ("", 0.0))[1])):
            s = sheets[i]
            z = storeys[i][1] if i in storeys else 0.0
            if i in storeys:
                name = storeys[i][0]
                existing = next((n for n, v in doc.levels.items() if abs(float(v) - z) < 1e-3), None)
                if existing is None:
                    stack.execute(CreateFloorLevel(name, z))
                else:
                    window._refresh_floor_selector(); window._activate_level_by_name(existing)
            params = pdf_params(s.path, s.page, s.scale or 100, s.page_size, z)
            params.update(m_per_unit=s.metres_per_pt * sim.scale, rotation=sim.turn, x=sim.shift[0], y=sim.shift[1])
            u = Entity("underlay", params, name=f"Υπόβαθρο {s.path.split('/')[-1]}")
            stack.execute(AddEntity(u))
            if s.kind == "plan" and i in storeys:
                from archforge.architecture.building_from_drawing import analyse_sheet
                built[i] = B.build(window, u.id, found=analyse_sheet(s, sim), ask=False)
            if s.kind == "site":
                pts = [(*sim.apply((x, y)), v) for v, c, x, y in s.levels() if not c and v >= B.ALTITUDE_MIN]
                if len(pts) >= 3:
                    from archforge.site.survey import terrain_from_survey
                    terrain = terrain_from_survey(doc, pts, in_place=True, altitude_ref=float(reference))
                    stack.execute(AddEntity(Entity("terrain", terrain, name="Έδαφος")))
    finally:
        QApplication.restoreOverrideCursor()
    stack.squash(since, "Σύνολο σχεδίων")
    window._refresh_floor_selector()
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    done = {"sheets": sheets, "placed": placed, "storeys": storeys, "built": built, "terrain": terrain}
    text = (f"{len(placed)} από {len(sheets)} σχέδια στη θέση τους · {len(set(n for n, _z, _a in storeys.values()))} όροφοι · "
            f"τοίχοι {sum(b['walls'] for b in built.values() if b)} · έδαφος από {len(terrain['points']) if terrain else 0} υψόμετρα"
            " — Ctrl+Z αναιρεί όλο το σύνολο")
    window.statusBar().showMessage(text, 20000)
    if ask:
        QMessageBox.information(window, "Σύνολο σχεδίων", summary_text(sheets, placed, storeys) + "\n\n" + text)
    return done
