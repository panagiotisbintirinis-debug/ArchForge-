"""Slab tools of the main window: storey slabs, slab openings / atria, railing round an opening.

Owner: «Να μπορώ στις πλάκες να κόβω τμήματα εσωτερικά για αίθρια ή
εσωτερικά μπαλκόνια.»  With the mouse:

* «Οπή πλάκας / αίθριο»: drag a rectangle in the plan, or click the corners
  of a polygon (double click / Enter / click on the first corner closes it),
  Esc cancels; a dashed ghost with its size and area follows the cursor;
* right click in a room: «Αίθριο σε αυτόν τον χώρο» / «Κενό πλάκας
  (εσωτερικό μπαλκόνι) σε αυτόν τον χώρο» — the opening is the room and
  follows its walls;
* right click on an opening: «Κάγκελο γύρω από την οπή» (one click),
  move (handle / Μετακίνηση), Delete.

Every action is one command on the window's stack (one undo).  ``SlabDraft``
is plain UI state (no Qt) so tests drive it directly.
"""
from __future__ import annotations

import math

from archforge.architecture import storey_slabs as S
from archforge.core.commands import AddEntity, UpdateEntity

DRAG_MIN = 0.20          # a press-drag shorter than this is a click (polygon mode)
CLOSE_REACH = 0.15


class SlabDraft:
    def __init__(self):
        self.points = []
        self.cursor = None
        self.press = None

    @staticmethod
    def _snap(x, y):
        return round(float(x), 2), round(float(y), 2)

    def rectangle(self):
        """Rectangle of the drag in progress (press point → cursor), or None."""
        if self.press is None or self.cursor is None or self.points:
            return None
        (x0, y0), (x1, y1) = self.press, self.cursor
        if abs(x1 - x0) < DRAG_MIN or abs(y1 - y0) < DRAG_MIN:
            return None
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

    def down(self, x, y):
        self.press = self._snap(x, y)
        self.cursor = self.press

    def move(self, x, y):
        self.cursor = self._snap(x, y)

    def up(self, x, y):
        """Mouse released: the finished outline (rectangle drag or closed polygon), else None."""
        self.cursor = self._snap(x, y)
        rect = self.rectangle()
        self.press = None
        if rect is not None:
            return rect
        p = self.cursor
        if len(self.points) >= 3 and math.hypot(p[0] - self.points[0][0], p[1] - self.points[0][1]) <= CLOSE_REACH:
            return self.finish()
        if not self.points or math.hypot(p[0] - self.points[-1][0], p[1] - self.points[-1][1]) >= 0.01:
            self.points.append(p)
        return None

    def finish(self):
        pts = list(self.points)
        self.points = []
        return pts if len(pts) >= 3 else None

    def preview(self):
        rect = self.rectangle()
        if rect is not None:
            return rect
        pts = list(self.points)
        if pts and self.cursor is not None:
            pts.append(self.cursor)
        return pts

    def label(self):
        """Ghost text: «2,40 × 1,80 m · 4,32 m²»."""
        pts = self.preview()
        if len(pts) < 2:
            return ''
        xs, ys = [q[0] for q in pts], [q[1] for q in pts]
        text = f"{max(xs) - min(xs):.2f} × {max(ys) - min(ys):.2f} m".replace('.', ',')
        if len(pts) >= 3:
            area = abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
                           for i in range(len(pts)))) / 2
            text += f" · {area:.2f} m²".replace('.', ',')
        return text


# --- window actions -------------------------------------------------------------------------------

def _refresh(window, select=None):
    if select is not None:
        window.doc.select([select])
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    window.refresh_inspector()


def auto_storey_slab(window, kind):
    """«Δάπεδα / Δώμα (αυτόματα)»: one slab over the whole active storey (replaces per-room ones) — one undo."""
    doc = window.doc
    level_z = float(doc.work_plane.origin[2])
    if not doc.active_room_faces():
        window.statusBar().showMessage('Δεν υπάρχουν κλειστοί χώροι στον ενεργό όροφο', 4000)
        return None
    command, entity = S.storey_slab_command(doc, kind, level_z, doc.active_level_name())
    what = 'Πλάκα δαπέδου' if kind == 'room_floor' else 'Πλάκα δώματος'
    if command is None:
        window.statusBar().showMessage(f'{what}: υπάρχει ήδη και καλύπτει όλο τον όροφο', 5000)
        return None
    window.stack.execute(command)
    _refresh(window)
    slab = entity or next((e for e in doc.entities.values() if e.kind == kind and e.params.get('scope') == 'storey'
                           and abs(float(e.params['level_z']) - level_z) < 1e-4), None)
    g = S.storey_slab_geometry(doc, slab) if slab is not None else None
    if g is None:
        window.statusBar().showMessage(f'{what}: κανένας χώρος του ορόφου δεν τη χρειάζεται (όροφος από πάνω ή κεραμοσκεπή)', 7000)
    else:
        window.statusBar().showMessage(f"{what}: {g['area']:.2f} m² σε όλο τον όροφο — ακολουθεί τους τοίχους · "
                                       'οπές/αίθρια με δεξί κλικ · Ctrl+Z για αναίρεση', 8000)
    return slab


def start_opening_tool(window):
    window.plan_view._slab_draft = None
    window._start_site_tool('slab_opening', 'Οπή πλάκας / αίθριο: σύρε ορθογώνιο ή κλικ στις γωνίες '
                            '(διπλό κλικ / Enter / κλικ στην πρώτη γωνία = κλείσιμο) · Esc = ακύρωση')


def place_opening(window, points, use='void'):
    try:
        entity = S.opening_entity(window.doc, points=points, use=use)
        window.stack.execute(AddEntity(entity))
    except (ValueError, KeyError) as exc:
        window.statusBar().showMessage(f'Οπή πλάκας: {exc}', 6000)
        return None
    _refresh(window, entity.id)
    area = S.opening_area(window.doc, entity)
    window.statusBar().showMessage(f'{entity.name} {area:.2f} m² — κόβει: {S.CUTS[entity.params["cuts"]].lower()} · '
                                   'δεξί κλικ: κάγκελο γύρω · Delete: διαγραφή · Ctrl+Z', 8000)
    return entity


def room_opening(window, x, y, use='atrium'):
    """The room at (x, y) becomes an atrium / inner balcony (an opening that follows its walls) — one undo."""
    entity = S.room_opening_entity(window.doc, x, y, use)
    if entity is None:
        window.statusBar().showMessage('Κλικ μέσα σε κλειστό χώρο χωρίς οπή (ο χώρος έχει ήδη γίνει οπή;)', 6000)
        return None
    window.stack.execute(AddEntity(entity))
    _refresh(window, entity.id)
    window.statusBar().showMessage(f'{entity.name}: όλος ο χώρος ({S.opening_area(window.doc, entity):.2f} m²) — '
                                   'η πλάκα κόβεται στους τοίχους του · Ctrl+Z για αναίρεση', 8000)
    return entity


def opening_railing(window, eid, railing_type='balusters'):
    """Closed railing round an opening, on the slab side, 1.00 m (ΝΟΚ — προς έλεγχο) — one undo."""
    from archforge.architecture.railings import TYPES, default_params
    from archforge.core.model import Entity
    opening = window.doc.get(eid)
    points = S.railing_points(window.doc, opening)
    if not points:
        window.statusBar().showMessage('Η οπή δεν έχει περίγραμμα (ο χώρος δεν είναι κλειστός)', 6000)
        return None
    z = float(opening.params['level_z'])
    if opening.params.get('cuts') == 'roof':
        # Atrium / light well in the slab above: the railing stands on that slab (δώμα).
        slab = next((e for e in window.doc.entities.values() if e.kind == 'room_roof' and e.params.get('scope') == 'storey'
                     and abs(float(e.params['level_z']) - z) < 1e-4), None)
        z += float(slab.params['offset_z']) + float(slab.params['thickness']) if slab else 0.0
    railing = Entity('railing', default_params(railing_type, points, z=z, closed=1),
                     name=f"{TYPES[railing_type]['label']} οπής")
    window.stack.execute(AddEntity(railing))
    _refresh(window, railing.id)
    window.statusBar().showMessage('Κάγκελο γύρω από την οπή, ύψος 1,00 m — τύπος/υλικά στις Ιδιότητες · Ctrl+Z', 8000)
    return railing


# --- Ιδιότητες ---------------------------------------------------------------------------------------

def is_slab_panel(entity):
    return entity.kind == 'slab_opening' or (entity.kind in S.SLAB_KINDS and entity.params.get('scope') == 'storey')


def add_rows(window, eid):
    from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QLabel, QPushButton
    doc, form = window.doc, window.form
    entity = doc.get(eid)
    p = dict(entity.params)

    def apply(changes):
        try:
            window.stack.execute(UpdateEntity(eid, changes))
        except (ValueError, KeyError) as exc:
            window.statusBar().showMessage(f'Η τιμή δεν έγινε δεκτή — {exc}', 6000)
        window._redraw_views(all_views=True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, window.refresh_inspector)

    def spin(label, key, lo, hi):
        box = QDoubleSpinBox()
        box.setDecimals(2)
        box.setRange(lo, hi)
        box.setSingleStep(0.01)
        box.setValue(float(p.get(key, 0.0)))
        box.editingFinished.connect(lambda w=box: abs(w.value() - float(p.get(key, 0.0))) > 1e-9 and apply({key: w.value()}))
        form.addRow(label, box)

    if entity.kind == 'slab_opening':
        for key, label, options in (('use', 'Χρήση', S.USES), ('cuts', 'Κόβει', S.CUTS)):
            box = QComboBox()
            for value, text in options.items():
                box.addItem(text, value)
            box.setCurrentIndex(max(0, box.findData(p.get(key))))
            box.currentIndexChanged.connect(lambda _i, w=box, k=key: w.currentData() != p.get(k) and apply(
                {k: w.currentData()} if k == 'cuts' else {k: w.currentData()}))
            form.addRow(label, box)
        poly = S.opening_polygon(doc, entity)
        if poly:
            xs, ys = [q[0] for q in poly], [q[1] for q in poly]
            info = (f"Εμβαδόν {S.opening_area(doc, entity):.2f} m² · {max(xs) - min(xs):.2f} × {max(ys) - min(ys):.2f} m"
                    + (' · ακολουθεί τους τοίχους του χώρου' if p.get('room_id') else ' · σύρε τη λαβή για μετακίνηση'))
            form.addRow('Μέγεθος', QLabel(info.replace('.', ',')))
        note = QLabel(f'<i>Δομικά: {S.REINFORCEMENT_NOTE}</i>')
        note.setWordWrap(True)
        form.addRow('', note)
        button = QPushButton('Κάγκελο γύρω από την οπή')
        button.clicked.connect(lambda _=False: opening_railing(window, eid))
        form.addRow(button)
        return
    spin('Πάχος πλάκας (m)', 'thickness', 0.08, 0.60)
    spin('Στάθμη πάνω από τον όροφο (m)', 'offset_z', -5.0, 20.0)
    if entity.kind == 'room_roof':
        spin('Προεξοχή (m)', 'overhang', 0.0, 2.0)
    g = S.storey_slab_geometry(doc, entity)
    if g is None:
        text = 'Κανένας χώρος του ορόφου δεν τη χρειάζεται'
    else:
        holes = sum(len(hs) for _o, hs in g['islands'])
        text = (f"{g['area']:.2f} m² · {g['area'] * g['thickness']:.2f} m³ σκυρόδεμα · "
                f"{len(g['islands'])} τμήμα(τα), {holes} οπή(ές) — ακολουθεί τους τοίχους").replace('.', ',')
    label = QLabel(text)
    label.setWordWrap(True)
    form.addRow('Πλάκα ορόφου', label)


def install_menus(window):
    """«Οπή πλάκας / αίθριο» in Αυτόματα ▾ (next to Δάπεδα / Δώμα) and in the Κατασκευή menu."""
    from PySide6.QtGui import QAction
    # Keep the menu bar's actions alive while their menus are used (PySide drops the wrappers otherwise).
    bar_actions = [a for a in window.menuBar().actions() if a.text().replace('&', '') == 'Κατασκευή' and a.menu()]
    targets = [getattr(window, '_mockup_auto_menu', None)] + [a.menu() for a in bar_actions][:1]
    window._slab_opening_actions = []
    for menu in targets:
        if menu is None:
            continue
        action = QAction('Οπή πλάκας / αίθριο (σχεδίαση)', window)
        action.setToolTip('Σύρε ορθογώνιο ή κλικ στις γωνίες στην κάτοψη· για ολόκληρο χώρο: δεξί κλικ μέσα του')
        action.triggered.connect(lambda _=False: start_opening_tool(window))
        try:
            menu.addAction(action)
        except RuntimeError:                              # a menu the shell replaced
            continue
        window._slab_opening_actions.append(action)
