"""Ιδιότητες κουφώματος (πόρτα/παράθυρο): τύπος και παράμετροι στα ελληνικά.

Κάθε αλλαγή είναι ένα UpdateEntity (ένα undo). Η γεωμετρία 3D και το
σύμβολο κάτοψης παράγονται από αυτές τις παραμέτρους (architecture/joinery.py).
"""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLabel, QPushButton, QSpinBox

from archforge.architecture import joinery
from archforge.core.commands import UpdateEntity


def _apply(window, eid, changes):
    entity = window.doc.get(eid)
    if all(entity.params.get(k) == v for k, v in changes.items()):
        return
    try:
        window.stack.execute(UpdateEntity(eid, changes))
    except ValueError as exc:
        window.statusBar().showMessage(f'Το κούφωμα δεν χωρά: {exc}', 5000)
        return
    window._redraw_views(all_views=True)
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, window.refresh_inspector)


def _combo(options, current):
    combo = QComboBox()
    for value, label in options.items():
        combo.addItem(label if isinstance(label, str) else label[0], value)
    combo.setCurrentIndex(max(0, combo.findData(current)))
    return combo


def add_opening_rows(window, form, entity):
    """Γραμμές Ιδιοτήτων για door/window· επιστρέφει τα κλειδιά που χειρίζεται."""
    eid, kind, p = entity.id, entity.kind, entity.params
    r = joinery.resolved(kind, p)
    typ = r['opening_type']
    combo = _combo(joinery.TYPES[kind], typ)
    # Αλλαγή τύπου: φύλλα ξανά αυτόματα (ένα undo).
    combo.currentIndexChanged.connect(
        lambda _i, w=combo: _apply(window, eid, {'opening_type': w.currentData(), 'leaves': 0}))
    form.addRow('Τύπος κουφώματος', combo)
    if typ == 'basic':
        return set(joinery.KEYS)
    lo, hi = joinery.LEAF_RANGE[typ]
    if hi > lo:
        spin = QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(r['leaves'])
        spin.editingFinished.connect(lambda w=spin: _apply(window, eid, {'leaves': w.value()}))
        form.addRow('Φύλλα', spin)
    if typ in joinery.SWINGING or typ in ('pocket', 'folding') or (r['shading'] == 'shutters' and r['leaves'] == 1):
        label = 'Μεντεσέδες' if typ in joinery.SWINGING else 'Μαζεύει προς'
        hinge = _combo(joinery.HINGES, r['hinge'])
        hinge.currentIndexChanged.connect(lambda _i, w=hinge: _apply(window, eid, {'hinge': w.currentData()}))
        form.addRow(label, hinge)
    if typ == 'pocket' and not joinery.pocket_fits(window.doc, entity):
        warn = QLabel('⚠ Η θήκη της χωνευτής δεν χωρά σε αυτή την πλευρά του τοίχου — άλλαξε πλευρά ή μετακίνησε την πόρτα')
        warn.setWordWrap(True)
        form.addRow('', warn)
    if typ in joinery.SWINGING:
        swing = _combo(joinery.SWINGS, r['swing'])
        swing.currentIndexChanged.connect(lambda _i, w=swing: _apply(window, eid, {'swing': w.currentData()}))
        form.addRow('Φορά ανοίγματος', swing)
    if typ in joinery.GLAZED:
        for key, label in (('bars_v', 'Καΐτια κάθετα'), ('bars_h', 'Καΐτια οριζόντια')):
            spin = QSpinBox()
            spin.setRange(0, 8)
            spin.setValue(r[key])
            spin.editingFinished.connect(lambda w=spin, k=key: _apply(window, eid, {k: w.value()}))
            form.addRow(label, spin)
        if typ not in joinery.SLIDING:
            transom = QDoubleSpinBox()
            transom.setDecimals(0)
            transom.setRange(0, 150)
            transom.setSuffix(' cm')
            transom.setValue(r['transom'] * 100)
            transom.editingFinished.connect(lambda w=transom: _apply(window, eid, {'transom': w.value() / 100.0}))
            form.addRow('Φεγγίτης πάνω (0 = χωρίς)', transom)
        shading = _combo(joinery.SHADINGS, r['shading'])
        shading.currentIndexChanged.connect(lambda _i, w=shading: _apply(window, eid, {'shading': w.currentData()}))
        form.addRow('Ρολό / παντζούρια', shading)
    if kind == 'window':
        ledge = _combo(joinery.LEDGES, r['ledge'])
        ledge.currentIndexChanged.connect(lambda _i, w=ledge: _apply(window, eid, {'ledge': w.currentData()}))
        form.addRow('Ποδιά / περβάζι', ledge)
    finish = _combo(joinery.FINISHES, r['finish'])
    finish.currentIndexChanged.connect(lambda _i, w=finish: _apply(window, eid, {'finish': w.currentData()}))
    form.addRow('Υλικό κουφώματος', finish)
    button = QPushButton('Χρώμα ανά τμήμα (κάσα, φύλλο, τζάμι…)')
    button.clicked.connect(lambda _=False: window._open_materials(eid))
    form.addRow(button)
    return set(joinery.KEYS)


def start_preset(window, key):
    """Βιβλιοθήκη → Κουφώματα: εργαλείο πόρτας/παραθύρου με έτοιμο τύπο και μέγεθος."""
    pr = joinery.preset(key)
    window._set_active_tool(pr['kind'])
    for view in (window.plan_view.controller, window.pbr_view):
        view.opening_preset = pr
    window.statusBar().showMessage(f"{pr['name']}: κλικ πάνω σε τοίχο για τοποθέτηση — Esc για τέλος", 6000)
    return pr
