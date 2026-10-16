"""Plasterboard ceiling tools of the main window (construction/drywall.py), and the ICF / plasterboard take-offs.

With the mouse:

* «Ψευδοροφή σε χώρο»: click inside a room — the ceiling is the whole room
  and follows its walls (bathroom / kitchen: moisture-resistant boards
  proposed automatically);
* «Ψευδοροφή — σχεδίαση»: drag a rectangle or click the corners of a
  polygon (double click / Enter / click on the first corner closes it), Esc
  cancels; a dashed ghost with its size and area follows the cursor;
* right click in a room: «Ψευδοροφή γυψοσανίδας σε αυτόν τον χώρο»;
* right click on a ceiling: Ιδιότητες / Διαγραφή; Delete deletes it.

Every action is one command on the window's stack (one undo).
"""
from __future__ import annotations

from archforge.construction import drywall as D
from archforge.core.commands import AddEntity, UpdateEntity


def _refresh(window, select=None):
    if select is not None:
        window.doc.select([select])
    window._redraw_views(all_views=True)
    window._refresh_project_tree()
    window.refresh_inspector()


def start_room_tool(window):
    window._start_site_tool('drywallroom', 'Ψευδοροφή γυψοσανίδας: κλικ μέσα στον χώρο — όλος ο χώρος, ακολουθεί τους τοίχους · '
                            'Esc = τέλος')


def start_draw_tool(window):
    window.plan_view._slab_draft = None
    window._start_site_tool('drywall_ceiling', 'Ψευδοροφή γυψοσανίδας: σύρε ορθογώνιο ή κλικ στις γωνίες '
                            '(διπλό κλικ / Enter / κλικ στην πρώτη γωνία = κλείσιμο) · Esc = ακύρωση')


def _add(window, params, name):
    from archforge.core.model import Entity
    params['board'] = D.suggested_board(window.doc, params)
    entity = Entity('drywall_ceiling', params, name=name)
    try:
        window.stack.execute(AddEntity(entity))
    except (ValueError, KeyError) as exc:
        window.statusBar().showMessage(f'Ψευδοροφή: {exc}', 6000)
        return None
    _refresh(window, entity.id)
    r = D.count_ceiling(window.doc, entity)
    wet = ' · υγρός χώρος: ανθυγρή σανίδα' if params['board'] == 'moisture' else ''
    window.statusBar().showMessage(
        f"{entity.name} {r['area_m2']:.2f} m², Ψ/Ο +{r['level_m']:.2f}".replace('.', ',') + f"{wet} — ύψος, σανίδα, μόνωση, σκαλί στις Ιδιότητες · "
        'Delete: διαγραφή · Ctrl+Z', 9000)
    return entity


def place_drawn(window, points):
    level_z = float(window.doc.work_plane.origin[2])
    return _add(window, D.default_params(points=points, level_z=level_z), 'Ψευδοροφή')


def place_in_room(window, x, y):
    """The room at (x, y) of the active storey gets a suspended ceiling over all of it — one undo."""
    from archforge.architecture.room_identity import reconcile_room_bindings
    from archforge.geometry.regions import point_in_polygon
    doc = window.doc
    z = float(doc.work_plane.origin[2])
    for face, room_id in reconcile_room_bindings(doc, z=z):
        if point_in_polygon(float(x), float(y), face.polygon):
            if any(e.kind == 'drywall_ceiling' and e.params.get('room_id') == room_id for e in doc.entities.values()):
                window.statusBar().showMessage('Ο χώρος έχει ήδη ψευδοροφή — άλλαξέ τη στις Ιδιότητες', 6000)
                return None
            name = doc.room_metadata(face.signature).get('name')
            return _add(window, D.default_params(room_id=room_id, level_z=z), f'Ψευδοροφή {name}' if name else 'Ψευδοροφή')
    window.statusBar().showMessage('Κλικ μέσα σε κλειστό χώρο (τοίχοι γύρω-γύρω)', 6000)
    return None


# --- Ιδιότητες ---------------------------------------------------------------------------------------

def add_rows(window, eid):
    from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLabel
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

    def spin(label, key, lo, hi, cm=True, default=0.0):
        box = QDoubleSpinBox()
        box.setDecimals(1 if cm else 2)
        box.setRange(lo * 100 if cm else lo, hi * 100 if cm else hi)
        box.setSuffix(' cm' if cm else '')
        value = float(p.get(key, default))
        box.setValue(value * 100 if cm else value)
        box.editingFinished.connect(lambda w=box: abs(w.value() / (100 if cm else 1) - value) > 1e-9
                                    and apply({key: round(w.value() / (100 if cm else 1), 4)}))
        form.addRow(label, box)

    def combo(label, key, options, current):
        box = QComboBox()
        for value, text in options.items():
            box.addItem(text, value)
        box.setCurrentIndex(max(0, box.findData(current)))
        box.currentIndexChanged.connect(lambda _i, w=box: w.currentData() != current and apply({key: w.currentData()}))
        form.addRow(label, box)

    r = D.count_ceiling(doc, entity)
    spin('Απόσταση από την πλάκα', 'drop', D.MIN_DROP, D.MAX_DROP, default=D.DEFAULT_DROP)
    combo('Σανίδα', 'board', {k: v[0] for k, v in D.BOARDS.items()}, p.get('board', 'standard'))
    if p.get('board') != 'moisture' and D.room_use(doc, p) in D.WET_USES:
        hint = QLabel('<i>Υγρός χώρος: προτείνεται ανθυγρή σανίδα</i>')
        form.addRow('', hint)
    combo('Στρώσεις', 'layers', {1: 'Μονή στρώση', 2: 'Διπλή στρώση'}, int(p.get('layers', 1)))
    spin('Μόνωση ορυκτοβάμβακα (0 = όχι)', 'insulation', 0.0, 0.20)
    cove = QCheckBox('Σκαλί περιμετρικά με κρυφό φωτισμό')
    cove.setChecked(bool(int(p.get('cove', 0))))
    cove.toggled.connect(lambda on: apply({'cove': 1 if on else 0}))
    form.addRow('Κρυφός φωτισμός', cove)
    if int(p.get('cove', 0)):
        spin('Πλάτος σκαλιού', 'cove_width', 0.10, 1.00, default=0.30)
        spin('Ύψος σκαλιού', 'cove_depth', 0.03, 0.50, default=0.10)
    if r:
        info = (f"{r['area_m2']:.2f} m² · Ψ/Ο +{r['level_m']:.2f} από το δάπεδο · "
                f"CD {r['cd_m']:.1f} m, UD {r['ud_m']:.1f} m, {r['hangers']} αναρτήσεις, {r['sheets']} φύλλα"
                + (' · ακολουθεί τους τοίχους του χώρου' if p.get('room_id') else ''))
        label = QLabel(info.replace('.', ','))
        label.setWordWrap(True)
        form.addRow('Ψευδοροφή', label)
    note = QLabel(f'<i>Υλικά: {D.NOTE} — Κατασκευή → Γυψοσανίδες (υλικά)</i>')
    note.setWordWrap(True)
    form.addRow('', note)


# --- take-off dialogs ------------------------------------------------------------------------------

def _dialog(window, title, html, sheet, default, attr):
    from PySide6.QtWidgets import QDialog, QPushButton, QTextBrowser, QVBoxLayout
    dialog = QDialog(window)
    dialog.setWindowTitle(title)
    dialog.resize(1000, 600)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser(dialog)
    browser.setHtml(html)
    layout.addWidget(browser)
    export = QPushButton(f'Λίστα «{sheet}» σε Excel (με στήλη τιμών)…', dialog)
    export.clicked.connect(lambda: window._export_priced_lists(only=(sheet,), default=default))
    layout.addWidget(export)
    setattr(window, attr, browser)
    if not getattr(window, '_no_modal_dialogs', False):
        dialog.exec()


def show_icf(window):
    """ICF straight / corner blocks per wall, storey and type, closures and concrete (pre-design take-off)."""
    from archforge.construction.icf import icf_html, take_off_icf
    result = take_off_icf(window.doc)
    _dialog(window, 'Τεμάχια ICF', icf_html(result), 'ICF', 'icf.xlsx', '_icf_view')
    return result


def show_drywall(window):
    from archforge.construction.drywall import drywall_html, take_off_drywall
    result = take_off_drywall(window.doc)
    _dialog(window, 'Γυψοσανίδες — υλικά', drywall_html(result), 'Γυψοσανίδες', 'gypsosanides.xlsx', '_drywall_view')
    return result


def install_menus(window):
    """Κατασκευή → «Ψευδοροφή γυψοσανίδας ▸», «Τεμάχια ICF (αναγωγή)…», «Γυψοσανίδες — υλικά (αναγωγή)…»."""
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu
    # Keep the menu bar's actions alive while their menus are used (PySide drops the wrappers otherwise).
    bar_actions = [a for a in window.menuBar().actions() if a.text().replace('&', '') == 'Κατασκευή' and a.menu()]
    window._drywall_actions = []
    for menu in [a.menu() for a in bar_actions][:1]:
        sub = QMenu('Ψευδοροφή γυψοσανίδας', window)
        for text, run in (('Σε χώρο (κλικ στον χώρο)', lambda: start_room_tool(window)),
                          ('Σχεδίαση (ορθογώνιο ή πολύγωνο)', lambda: start_draw_tool(window))):
            action = QAction(text, window)
            action.triggered.connect(lambda _=False, r=run: r())
            sub.addAction(action)
            window._drywall_actions.append(action)
        try:
            menu.addMenu(sub)
        except RuntimeError:
            continue
        for text, run, attr in (('Τεμάχια ICF (αναγωγή)…', lambda: show_icf(window), '_icf_action'),
                                ('Γυψοσανίδες — υλικά (αναγωγή)…', lambda: show_drywall(window), '_drywall_takeoff_action')):
            action = QAction(text, window)
            action.triggered.connect(lambda _=False, r=run: r())
            menu.addAction(action)
            setattr(window, attr, action)
        window._drywall_menu = sub
