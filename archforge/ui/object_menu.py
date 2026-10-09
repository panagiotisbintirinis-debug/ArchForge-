"""Mouse-menu actions for placed objects (shared by the plan and the 3D view).

Δεξί κλικ σε έπιπλο, ντουλάπι, είδος υγιεινής, σημείο Η/Μ, σκάλα, κάγκελο,
πέργκολα: Περιστροφή 90°, Καθρέφτισμα, Διπλασιασμός, Διαγραφή· σε πόρτα /
παράθυρο: Αλλαγή πλευράς μεντεσέ, Αλλαγή φοράς (μέσα ↔ έξω).  Κάθε επιλογή
είναι μία εντολή από ``core.object_ops`` (ένα undo).
"""
from __future__ import annotations

from archforge.core import object_ops

LABELS = {
    'rot90': 'Περιστροφή 90°',
    'rot-90': 'Περιστροφή −90°',
    'mirror': 'Καθρέφτισμα',
    'duplicate': 'Διπλασιασμός',
    'hinge': 'Αλλαγή πλευράς μεντεσέ',
    'swing': 'Αλλαγή φοράς (μέσα ↔ έξω)',
    'delete': 'Διαγραφή',
}


def marking_entries(entity):
    """Extra marking-menu entries ``[(id, label)]`` for one entity."""
    if entity.kind in ('door', 'window'):
        return [('mm:obj:hinge', LABELS['hinge']), ('mm:obj:swing', LABELS['swing'])]
    if entity.kind not in object_ops.USER_PLACED_KINDS or entity.locked:
        return []
    return [(f'mm:obj:{op}', LABELS[op]) for op in ('rot90', 'mirror', 'duplicate')]


def command_for(doc, eid, op):
    if op == 'rot90':
        return object_ops.rotate_command(doc, eid, 90.0)
    if op == 'rot-90':
        return object_ops.rotate_command(doc, eid, -90.0)
    if op == 'mirror':
        return object_ops.mirror_command(doc, eid)
    if op in ('hinge', 'swing'):
        return object_ops.flip_command(doc, eid, op)
    if op == 'delete':
        return object_ops.delete_command(doc, eid)
    return None


def run_object_op(window, eid, op):
    """Carry out one action; returns the executed command (or None)."""
    doc = window.doc
    if eid not in doc.entities:
        return None
    entity = doc.get(eid)
    name = entity.name or entity.kind
    new_ids = []
    try:
        if op == 'duplicate':
            command, new_ids = object_ops.duplicate_command(doc, eid)
        else:
            command = command_for(doc, eid, op)
        if command is None:
            window.statusBar().showMessage(f'{LABELS.get(op, op)}: δεν ισχύει για {name}', 4000)
            return None
        window.stack.execute(command)
    except (ValueError, KeyError) as exc:
        window.statusBar().showMessage(f'{LABELS.get(op, op)}: {exc}', 5000)
        return None
    if op == 'delete':
        doc.select([])
    else:
        doc.select(new_ids or [eid])
    pbr = getattr(window, 'pbr_view', None)
    if pbr is not None and getattr(pbr, '_evaluation_cache', None) is not None:
        pbr._evaluation_cache.clear()
    window._redraw_views(all_views=True)
    if hasattr(window, 'refresh_inspector'):
        window.refresh_inspector()
    window.statusBar().showMessage(f'{LABELS.get(op, op)} — {name} · Ctrl+Z = αναίρεση', 4000)
    return command


def add_open_joinery_action(window, *menus):
    """Προβολή / Στυλ → «Ανοιχτά κουφώματα στο 3D» (επιλογή προβολής, όχι Document)."""
    from PySide6.QtGui import QAction
    action = getattr(window, 'open_joinery_action', None)
    if action is None:
        action = QAction('Ανοιχτά κουφώματα στο 3D', window)
        action.setCheckable(True)
        action.setToolTip('Πόρτες και παράθυρα ανοιχτά στο 3D (φύλλα στον μεντεσέ τους, συρόμενα συρμένα)· '
                          'γωνία ανά κούφωμα στις Ιδιότητες')
        action.toggled.connect(lambda on: set_open_joinery(window, on))
        window.open_joinery_action = action
    for menu in menus:
        if menu is not None:
            menu.addSeparator()
            menu.addAction(action)
    return action


def set_open_joinery(window, on):
    from archforge.rendering import fixtures
    fixtures.set_show_open(on)
    pbr = getattr(window, 'pbr_view', None)
    if pbr is not None:
        if getattr(pbr, '_evaluation_cache', None) is not None:
            pbr._evaluation_cache.clear()
        pbr.redraw(force_full=True)
    window.statusBar().showMessage('Κουφώματα στο 3D: ' + ('ανοιχτά' if on else 'κλειστά'), 3000)
