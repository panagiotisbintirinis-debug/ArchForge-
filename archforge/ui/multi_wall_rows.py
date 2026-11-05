"""Ιδιότητες με πολλούς τοίχους επιλεγμένους: σύνολα και αλλαγή τύπου σε όλους μαζί, μία αναίρεση (κριτική v5, k3/k4).

Πριν: «N επιλεγμένα» και τίποτα άλλο — 48–69 βήματα για να πάρουν τύπο 16–23 εξωτερικοί τοίχοι. Τώρα, με
«Επιλογή εξωτερικών τοίχων» ή «Επιλογή όμοιων» και ένα πεδίο, όλοι μαζί. Κάθε τοίχος αλλάζει με την ίδια εντολή που
χρησιμοποιεί ο ένας τοίχος (``curved_wall.spread_command``, τύπος + συνολικό πάχος των στρώσεων)· όλες μαζί = μία
αναίρεση. Οι στρώσεις του τύπου αλλάζουν στο ίδιο εργαλείο +/− («Στρώσεις…», `ui/wall_details_dialog.py`).
"""
from __future__ import annotations

import math

MIXED = "‹διάφοροι›"


def walls_of(doc, ids):
    ws = [doc.get(i) for i in ids if i in doc.entities]
    return ws if len(ws) > 1 and all(e.kind == "wall" for e in ws) else []


def set_type_all(window, ids, wall_type):
    """Every wall in ``ids`` gets ``wall_type`` (and its total thickness): one undo step. Returns how many changed."""
    from archforge.architecture.curved_wall import spread_command
    from archforge.architecture.wall_types import total_thickness
    doc, stack = window.doc, window.stack
    since = len(stack.done)
    changed = 0
    for eid in ids:
        if eid not in doc.entities or doc.get(eid).params.get("wall_type", "generic") == wall_type:
            continue
        changes = {"wall_type": str(wall_type)}
        t = total_thickness(wall_type, doc)
        if t > 0:
            changes["thickness"] = t
        stack.execute(spread_command(doc, eid, changes))
        changed += 1
    if changed > 1:
        stack.squash(since, "Τύπος τοίχων")
    return changed


def add_rows(window, ids):
    """Rows of the Properties form for several walls; False when the selection is not walls only."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QComboBox, QLabel, QPushButton
    from archforge.architecture import wall_types as wt
    walls = walls_of(window.doc, ids)
    if not walls:
        return False
    form = window.form
    length = sum(math.hypot(float(e.params["x2"]) - float(e.params["x1"]), float(e.params["y2"]) - float(e.params["y1"]))
                 for e in walls)
    try:
        from archforge.ui.select_similar import exterior_wall_ids
        ext = len(set(exterior_wall_ids(window.doc)) & {e.id for e in walls})
    except Exception:                                     # noqa: BLE001 — the count is a help, not a must
        ext = None
    form.addRow(QLabel(f"{len(walls)} τοίχοι επιλεγμένοι"))
    form.addRow("Συνολικό μήκος", QLabel(f"{length:.2f} m".replace(".", ",")))
    if ext is not None:
        form.addRow("Εξωτερικοί", QLabel(f"{ext} από {len(walls)}"))
    types = wt.wall_types(window.doc)
    current = {str(e.params.get("wall_type", "generic")) for e in walls}
    combo = QComboBox()
    if len(current) > 1:
        combo.addItem(MIXED, None)
    for key, entry in types.items():
        combo.addItem(entry[0], key)
    if len(current) == 1:
        combo.setCurrentIndex(max(0, combo.findData(next(iter(current)))))
    ids = [e.id for e in walls]

    def chosen(_index):
        key = combo.currentData()
        if key is None:
            return
        n = set_type_all(window, ids, key)
        window._redraw_views(all_views=True)
        window.statusBar().showMessage(f"Τύπος «{types[key][0]}» σε {n} τοίχους · Ctrl+Z = αναίρεση όλων μαζί", 8000)
        QTimer.singleShot(0, window.refresh_inspector)
    combo.currentIndexChanged.connect(chosen)
    form.addRow("Τύπος (όλων)", combo)
    layers = QPushButton("Στρώσεις…")
    layers.setToolTip("Το εργαλείο +/− των στρώσεων για τον τύπο αυτών των τοίχων")
    layers.setEnabled(len(current) == 1)
    layers.clicked.connect(lambda: window._open_wall_type_details(next(iter(current))))
    form.addRow("", layers)
    return True
