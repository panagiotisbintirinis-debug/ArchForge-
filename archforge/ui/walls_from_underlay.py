"""Κατασκευή ▸ Τοίχοι & δωμάτια ▸ Τοίχοι από το υπόβαθρο… (architecture/walls_from_lines.py).

The walls found in the active storey's underlay (DXF, or PDF exported from CAD) are made in one undoable step and
left selected: Delete removes the wrong ones, Ctrl+Z all of them.
"""
from __future__ import annotations

from collections import Counter

from PySide6.QtWidgets import QMessageBox


def propose(window):
    """[(a, b, thickness)] found in the underlays of the active storey."""
    from archforge.architecture.walls_from_lines import find_walls
    from archforge.project.underlay import underlay_model_segments, underlays
    z = float(window.doc.work_plane.origin[2])
    segs = []
    for e in underlays(window.doc, z):
        # Walls are drawn with the dark pens; a drawing with no dark lines at all (a coloured export) keeps them all.
        lines = underlay_model_segments(e.params, dark_only=True)
        segs += lines or underlay_model_segments(e.params)
    return find_walls(segs), len(segs)


def make(window, walls):
    from archforge.core.commands import AddEntities
    from archforge.core.interaction import next_name
    from archforge.core.model import Entity
    doc = window.doc
    z = float(doc.work_plane.origin[2])
    above = sorted(float(v) for v in doc.levels.values() if float(v) > z + 1e-6)
    height = (above[0] - z) if above else 2.7
    ents = []
    for a, b, t in walls:
        e = Entity('wall', {'x1': a[0], 'y1': a[1], 'x2': b[0], 'y2': b[1], 'z': z, 'height': height,
                            'thickness': float(t)}, name=next_name(doc, 'wall'))
        ents.append(e)
    window.stack.execute(AddEntities(ents))
    from archforge.architecture.storey_slabs import auto_floor_command
    floor = auto_floor_command(doc, z)
    if floor is not None:
        window.stack.amend(floor)
    doc.select([e.id for e in ents])
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    return ents


def run(window, ask=True):
    from archforge.project.underlay import underlays
    if not underlays(window.doc, float(window.doc.work_plane.origin[2])):
        QMessageBox.information(window, 'Τοίχοι από το υπόβαθρο',
                                'Δεν υπάρχει υπόβαθρο σε αυτόν τον όροφο.\nΑρχείο ▸ Εισαγωγή ▸ Σχέδιο μηχανικού (PDF / DXF).')
        return None
    try:
        walls, n_lines = propose(window)
    except Exception as exc:                          # noqa: BLE001 — a PDF that cannot be read: said, not hidden
        QMessageBox.warning(window, 'Τοίχοι από το υπόβαθρο', f'Το σχέδιο δεν διαβάζεται: {exc}')
        return None
    if not walls:
        QMessageBox.information(window, 'Τοίχοι από το υπόβαθρο', (
            'Δεν βρέθηκαν τοίχοι (ζεύγη παράλληλων γραμμών 6–70 cm).\n' +
            ('Το σχέδιο δεν έχει γραμμές — μάλλον είναι σκαναρισμένο: οι τοίχοι σχεδιάζονται με το χέρι πάνω του.'
             if n_lines == 0 else f'Διαβάστηκαν {n_lines} γραμμές· έλεγξε την κλίμακα (βαθμονόμηση) του υποβάθρου.')))
        return None
    by_t = Counter(round(t * 100) for _a, _b, t in walls)
    summary = ' · '.join(f'{c}× {t} cm' for t, c in sorted(by_t.items(), key=lambda kv: -kv[1]))
    if ask and QMessageBox.question(window, 'Τοίχοι από το υπόβαθρο', (
            f'Βρέθηκαν {len(walls)} τοίχοι ({summary}).\n\nΝα μπουν; Θα μείνουν επιλεγμένοι: Delete για όσους '
            'είναι λάθος, Ctrl+Z για όλους.')) != QMessageBox.StandardButton.Yes:
        return None
    ents = make(window, walls)
    window.statusBar().showMessage(f'Τοίχοι από το υπόβαθρο: {len(ents)} ({summary}) — έλεγξέ τους · Ctrl+Z = όλοι', 12000)
    return ents
