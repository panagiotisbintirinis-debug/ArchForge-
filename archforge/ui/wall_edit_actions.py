"""Mouse-menu actions on a wall: move it by a typed distance, split it where clicked.

Both go through the shared commands of ``architecture/wall_edit.py`` (one undo each).
"""
from __future__ import annotations


def direction_words(params):
    """(+ side, − side) of a move in plan words: right/left for a vertical wall, up/down otherwise."""
    from archforge.architecture.wall_edit import wall_normal
    nx, ny = wall_normal(params)
    return ('δεξιά', 'αριστερά') if abs(nx) >= abs(ny) else ('πάνω', 'κάτω')


def move_by(window, eid, centimetres):
    from archforge.architecture.wall_edit import MoveWall
    try:
        window.stack.execute(MoveWall(eid, float(centimetres) / 100.0))
    except ValueError as exc:
        window.statusBar().showMessage(f'⚠ {exc}', 6000)
        return False
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    window.statusBar().showMessage(f'Ο τοίχος μετακινήθηκε {float(centimetres):+.0f} cm (μαζί ό,τι είναι πάνω του) · Ctrl+Z = αναίρεση', 5000)
    return True


def move_by_dialog(window, eid):
    from PySide6.QtWidgets import QInputDialog
    if eid not in window.doc.entities or window.doc.get(eid).kind != 'wall':
        return False
    plus, minus = direction_words(window.doc.get(eid).params)
    value, ok = QInputDialog.getDouble(
        window, 'Μετακίνηση τοίχου',
        f'Απόσταση σε cm (+ προς τα {plus}, − προς τα {minus}).\n'
        'Οι ενωμένοι τοίχοι τεντώνουν, πόρτες/παράθυρα και ό,τι ακουμπά πάνω του πάνε μαζί.',
        0.0, -5000.0, 5000.0, 1)
    if not ok or abs(value) < 1e-9:
        return False
    return move_by(window, eid, value)


def split_here(window, eid, plan_xy):
    from archforge.architecture.wall_edit import SplitWalls, split_at_point
    if eid not in window.doc.entities or window.doc.get(eid).kind != 'wall' or plan_xy is None:
        return False
    try:
        cuts = split_at_point(window.doc, eid, float(plan_xy[0]), float(plan_xy[1]))
        command = SplitWalls(cuts)
        window.stack.execute(command)
    except ValueError as exc:
        window.statusBar().showMessage(f'⚠ {exc}', 6000)
        return False
    window.doc.select([eid] + command.new_ids)
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    window.statusBar().showMessage('Ο τοίχος χωρίστηκε σε δύο κομμάτια — το καθένα παίρνει δικό του υλικό/χρώμα', 5000)
    return True
