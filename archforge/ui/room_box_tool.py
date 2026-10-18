"""Κατασκευή ▸ Δωμάτιο (ορθογώνιο) / Δωμάτιο με διαστάσεις… in the plan (owner 18/10).

Δωμάτιο (ορθογώνιο): click the start and the end of one side, then pull the rectangle out and click (the
clear size is written next to it); Enter types the size instead.  Δωμάτιο με διαστάσεις…: type width × depth,
then one click places its corner.  The walls are made by ``ViewportController.draw_room_box`` (one undo step).
"""
from __future__ import annotations

import re

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPen, QPolygonF
from PySide6.QtWidgets import QInputDialog

from archforge.architecture.room_box import corners_from_edge, corners_from_size, label

HINT = ('Δωμάτιο: κλικ στην αρχή και στο τέλος μιας πλευράς, μετά τράβα το ορθογώνιο και κλικ · '
        'Enter = πληκτρολόγηση διαστάσεων · Esc = ακύρωση')


def start(window, sized=False):
    view = window.plan_view
    view.room_draft = None
    if sized:
        size = _ask(window)
        if size is None:
            return
        view.room_size = size
        window._start_site_tool('room_place', f'Δωμάτιο {size[0]:.2f} × {size[1]:.2f} m: κλικ στη θέση της κάτω '
                                              'αριστερής γωνίας (εσωτερικά) · Esc = ακύρωση'.replace('.', ','))
    else:
        window._start_site_tool('room_box', HINT)


def parse_size(text):
    """«4,20 x 3,5» / «4.2*3.5» / «4.2 3.5» → (4.2, 3.5) in metres; None when it is not two positive numbers."""
    nums = re.findall(r'\d+(?:[.,]\d+)?', str(text))
    if len(nums) != 2:
        return None
    w, d = (float(n.replace(',', '.')) for n in nums)
    if w > 50 and d > 50:                     # typed in centimetres
        w, d = w / 100.0, d / 100.0
    return (w, d) if w > 0.3 and d > 0.3 else None


def _ask(window):
    text, ok = QInputDialog.getText(window, 'Δωμάτιο με διαστάσεις',
                                    'Καθαρές διαστάσεις πλάτος × βάθος (m), π.χ. 4,20 x 3,50:')
    if not ok:
        return None
    size = parse_size(text)
    if size is None:
        window.statusBar().showMessage('Γράψε δύο διαστάσεις, π.χ. 4,20 x 3,50', 6000)
    return size


def click(window, tool, x, y):
    view = window.plan_view
    if tool == 'room_place':
        w, d = getattr(view, 'room_size', None) or (4.0, 3.0)
        return _make(window, corners_from_size((x, y), w, d))
    draft = list(getattr(view, 'room_draft', None) or [])
    draft.append((float(x), float(y)))
    if len(draft) < 3:
        view.room_draft = draft
        window.statusBar().showMessage('Δωμάτιο: κλικ στο τέλος της πλευράς' if len(draft) == 1 else
                                       'Δωμάτιο: τράβα το ορθογώνιο και κλικ · Enter = διαστάσεις', 0)
        view.viewport().update()
        return None
    view.room_draft = None
    corners = corners_from_edge(draft[0], draft[1], draft[2])
    return _make(window, corners)


def ask_size(view):
    """Enter while drawing: the size typed; along the side already given (or level, from the first click)."""
    window = view.window()
    draft = list(getattr(view, 'room_draft', None) or [])
    if not draft:
        return start(window, sized=True)
    size = _ask(window)
    if size is None:
        return None
    import math
    a = draft[0]
    angle = 0.0
    if len(draft) > 1:
        angle = math.degrees(math.atan2(draft[1][1] - a[1], draft[1][0] - a[0]))
    corners = corners_from_size(a, size[0], size[1], angle)
    cur = getattr(view, '_cursor_xy', None)
    if cur is not None and len(draft) > 1:
        # Pulled to the other side of the first edge: the room goes that way.
        flipped = corners_from_size(a, size[0], -size[1], angle)
        side = lambda c: (c[3][0] - a[0]) * (cur[0] - a[0]) + (c[3][1] - a[1]) * (cur[1] - a[1])
        if side(flipped) > side(corners):
            corners = flipped
    view.room_draft = None
    return _make(window, corners)


def _make(window, corners):
    if corners is None:
        return None
    try:
        made = window.plan_view.controller.draw_room_box(corners)
    except (ValueError, RuntimeError) as exc:
        window.statusBar().showMessage(f'Το δωμάτιο δεν έγινε: {exc}', 8000)
        return None
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    window.statusBar().showMessage(f'Δωμάτιο {label(corners)} · {len(made)} τοίχοι · Ctrl+Z = αναίρεση', 8000)
    return made


def preview_corners(view):
    cur = getattr(view, '_cursor_xy', None)
    if cur is None:
        return None
    if view.controller.tool == 'room_place':
        w, d = getattr(view, 'room_size', None) or (4.0, 3.0)
        return corners_from_size(cur, w, d)
    draft = getattr(view, 'room_draft', None) or []
    if len(draft) == 1:
        return [draft[0], cur]
    if len(draft) == 2:
        return corners_from_edge(draft[0], draft[1], cur)
    return None


def paint_preview(view, painter):
    pts = preview_corners(view)
    if not pts:
        return
    pen = QPen(QColor(40, 120, 200))
    pen.setCosmetic(True)
    pen.setWidthF(2.0)
    pen.setStyle(Qt.PenStyle.DashLine)
    painter.save()
    painter.setPen(pen)
    if len(pts) == 2:
        painter.drawLine(QPointF(*pts[0]), QPointF(*pts[1]))
    else:
        painter.drawPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    painter.resetTransform()
    import math
    if len(pts) == 2:
        text = f'{math.dist(*pts):.2f} m'.replace('.', ',')
    else:
        text = label(pts)
    at = view.mapFromScene(QPointF(*pts[-1]))
    painter.setPen(QColor(20, 70, 140))
    painter.drawText(at.x() + 12, at.y() - 8, text)
    painter.restore()


# ------------------------------------------------------------------ changing a drawn house by numbers
def wall_angle(window):
    """Γωνία τοίχου…: the selected wall's corner angle typed (its far corner and the walls joined there follow)."""
    from PySide6.QtWidgets import QInputDialog
    from archforge.architecture.room_resize import corner_angle, set_corner_angle_command
    doc = window.doc
    wid = next((i for i in doc.selection if i in doc.entities and doc.get(i).kind == 'wall'), None)
    if wid is None:
        window.statusBar().showMessage('Γωνία τοίχου: επίλεξε πρώτα έναν τοίχο (κλικ πάνω του)', 6000)
        return None
    current, ref = corner_angle(doc, wid)
    what = 'με τον τοίχο που ενώνεται στην αρχή του' if ref else 'με τον άξονα X'
    value, ok = QInputDialog.getDouble(window, 'Γωνία τοίχου', f'Γωνία {what} (°):', round(current, 1), 1.0, 359.0, 1)
    if not ok:
        return None
    return set_wall_angle(window, wid, value)


def set_wall_angle(window, wid, value):
    from archforge.architecture.room_resize import set_corner_angle_command
    try:
        window.stack.execute(set_corner_angle_command(window.doc, wid, value))
    except Exception as exc:                          # noqa: BLE001 — e.g. a locked layer: said, not hidden
        window.statusBar().showMessage(f'Γωνία τοίχου: {exc}', 8000)
        return None
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    window.statusBar().showMessage(f'Γωνία τοίχου {value:g}° · Ctrl+Z = αναίρεση', 6000)
    return wid


def start_resize(window):
    window._start_site_tool('room_resize', 'Διαστάσεις δωματίου: κλικ μέσα στο δωμάτιο · Esc = ακύρωση')


def resize_at(window, x, y, size=None):
    """Click inside a room → its clear size typed (width × depth); one side per direction moves."""
    from archforge.architecture.room_resize import resize_room_command, room_size
    from archforge.geometry.regions import point_in_polygon
    face = next((f for f in window.doc.active_room_faces() if point_in_polygon(x, y, f.polygon)), None)
    if face is None:
        window.statusBar().showMessage('Διαστάσεις δωματίου: κλικ μέσα σε κλειστό χώρο', 6000)
        return None
    got = room_size(window.doc, face)
    if got is None:
        window.statusBar().showMessage('Διαστάσεις δωματίου: μόνο τετράπλευρο δωμάτιο — για άλλα σχήματα '
                                       'μετακίνησε τους τοίχους (διπλό κλικ στην απόσταση)', 8000)
        return None
    if size is None:
        text, ok = QInputDialog.getText(window, 'Διαστάσεις δωματίου', 'Καθαρές διαστάσεις πλάτος × βάθος (m):',
                                        text=f'{got[0][0]:.2f} x {got[0][1]:.2f}'.replace('.', ','))
        if not ok:
            return None
        size = parse_size(text)
        if size is None:
            window.statusBar().showMessage('Γράψε δύο διαστάσεις, π.χ. 3,50 x 3,00', 6000)
            return None
    try:
        command = resize_room_command(window.doc, face, *size)
        if command is not None:
            window.stack.execute(command)
    except Exception as exc:                          # noqa: BLE001 — e.g. a locked layer: said, not hidden
        window.statusBar().showMessage(f'Διαστάσεις δωματίου: {exc}', 8000)
        return None
    window.plan_view.controller.set_tool('select')
    window._redraw_views(all_views=True)
    window.refresh_inspector()
    window.statusBar().showMessage(f'Δωμάτιο {size[0]:.2f} × {size[1]:.2f} m · Ctrl+Z = αναίρεση'.replace('.', ','), 6000)
    return size
