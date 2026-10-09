"""Συντομεύσεις πληκτρολογίου που αλλάζουν (Επεξεργασία / Βοήθεια → «Συντομεύσεις πληκτρολογίου…»).

One registry of the frequent commands: id → Greek name, category, default key.
``ShortcutManager`` owns one window-level QAction per command (the existing
Undo / Save / Delete … actions are adopted, not duplicated), applies the user's
keys from ``settings.json`` in the user data folder (``ui/autosave.py``; never
the project, never layout.ini) and shows each key next to the same command in
the menus (inactive mirror) and in the ribbon tooltips.

Keys that already have a meaning while working are kept out (``RESERVED``):
Esc cancels, Enter finishes, Tab / Space cycle options, R turns what is dragged.
"""
from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCursor, QKeySequence
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QKeySequenceEdit, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QToolBar, QVBoxLayout,
)

SETTINGS_KEY = 'shortcuts'

# (id, όνομα, κατηγορία, προεπιλογή, κείμενα ίδιων εντολών σε μενού/ribbon για να φαίνεται το πλήκτρο)
ACTIONS = (
    ('tool.select', 'Επιλογή', 'Εργαλεία', 'S', ('Επιλογή',)),
    ('tool.wall', 'Τοίχος', 'Εργαλεία', 'W', ('Τοίχος',)),
    ('tool.door', 'Πόρτα', 'Εργαλεία', 'D', ('Πόρτα',)),
    ('tool.window', 'Παράθυρο', 'Εργαλεία', 'N', ('Παράθυρο',)),
    ('tool.opening', 'Άνοιγμα (χωρίς κούφωμα)', 'Εργαλεία', 'O', ('Άνοιγμα',)),
    ('tool.stair', 'Σκάλα', 'Εργαλεία', 'A', ('Σκάλα',)),
    ('tool.ramp', 'Ράμπα', 'Εργαλεία', 'P', ('Ράμπα',)),
    ('tool.railing', 'Κάγκελα', 'Εργαλεία', 'K', ()),
    ('tool.column', 'Κολόνα', 'Εργαλεία', 'I', ('Κολώνα',)),
    ('tool.beam', 'Δοκός', 'Εργαλεία', 'B', ('Δοκός',)),
    ('tool.sculpt', 'Γλυπτική (Sculpt)', 'Εργαλεία', 'C', ('Γλυπτική',)),
    ('edit.move', 'Μετακίνηση', 'Επεξεργασία', 'M', ()),
    ('edit.rotate', 'Περιστροφή', 'Επεξεργασία', 'Shift+R', ()),
    ('edit.stretch', 'Τέντωμα', 'Επεξεργασία', 'T', ()),
    ('edit.delete', 'Διαγραφή', 'Επεξεργασία', 'Del', ()),
    ('edit.undo', 'Αναίρεση', 'Επεξεργασία', 'Ctrl+Z', ()),
    ('edit.redo', 'Επανάληψη', 'Επεξεργασία', 'Ctrl+Y', ()),
    ('edit.duplicate', 'Διπλασιασμός', 'Επεξεργασία', 'Ctrl+D', ()),
    ('file.new', 'Νέο έργο', 'Αρχείο', 'Ctrl+N', ()),
    ('file.open', 'Άνοιγμα έργου…', 'Αρχείο', 'Ctrl+O', ()),
    ('file.save', 'Αποθήκευση', 'Αρχείο', 'Ctrl+S', ()),
    ('view.plan', 'Κάτοψη (2D)', 'Προβολή', 'F2', ()),
    ('view.3d', '3D προοπτική', 'Προβολή', 'F3', ('3D', '3D Προοπτική')),
    ('view.top', 'Πάνω', 'Προβολή', 'Ctrl+1', ('Πάνω',)),
    ('view.front', 'Πρόσοψη', 'Προβολή', 'Ctrl+2', ('Πρόσοψη',)),
    ('view.side', 'Πλάγια', 'Προβολή', 'Ctrl+3', ('Πλάγια',)),
    ('view.zoom_all', 'Ζουμ σε όλα', 'Προβολή', 'Home', ()),
    ('env.arch', 'Περιβάλλον Αρχιτεκτονικό', 'Περιβάλλον', 'Alt+1', ('Αρχιτεκτονικό',)),
    ('env.structure', 'Περιβάλλον Φέρων', 'Περιβάλλον', 'Alt+2', ('Φέρων',)),
    ('env.mep', 'Περιβάλλον Η/Μ', 'Περιβάλλον', 'Alt+3', ('Η/Μ',)),
    ('panel.layers', 'Layers (πάνελ)', 'Πάνελ', 'F6', ('Layers',)),
    ('aid.grid', 'Κάνναβος', 'Βοηθήματα', 'F7', ()),
    ('aid.snap', 'Έλξη', 'Βοηθήματα', 'F9', ()),
    ('panel.properties', 'Ιδιότητες (πάνελ)', 'Πάνελ', 'F4', ()),
    ('panel.assistant', 'Βοηθός (πάνελ)', 'Πάνελ', 'F5', ()),
    ('panel.library', 'Βιβλιοθήκη: αναζήτηση', 'Πάνελ', 'Ctrl+F', ()),
    ('assist.kitchen', 'Κουζίνα εδώ', 'Βοηθός', 'Shift+K', ('Κουζίνα εδώ…',)),
    ('assist.bath', 'Μπάνιο εδώ', 'Βοηθός', 'Shift+B', ('Μπάνιο εδώ…',)),
    ('help.shortcuts', 'Συντομεύσεις πληκτρολογίου…', 'Βοήθεια', 'Ctrl+F1', ()),
)
NAMES = {a[0]: a[1] for a in ACTIONS}
CATEGORIES = tuple(dict.fromkeys(a[2] for a in ACTIONS))
# Keys with a meaning of their own while working (plan_view / library_drag / layout_assist).
RESERVED = {
    'Esc': 'Esc ακυρώνει ό,τι είναι σε εξέλιξη',
    'Return': 'Enter τελειώνει τον τοίχο / την οπή / το κάγκελο',
    'Enter': 'Enter τελειώνει τον τοίχο / την οπή / το κάγκελο',
    'Tab': 'Tab αλλάζει επιλογή (σκάλα, διάταξη)',
    'Space': 'Διάστημα αλλάζει επιλογή κατά τη σχεδίαση',
    'R': 'R στρίβει 90° ό,τι σέρνεις',
}


def norm(seq):
    """Portable text of a key sequence ('' for none)."""
    if isinstance(seq, QKeySequence):
        return seq.toString(QKeySequence.SequenceFormat.PortableText)
    return QKeySequence(str(seq or '')).toString(QKeySequence.SequenceFormat.PortableText)


def display(seq):
    return QKeySequence(norm(seq)).toString(QKeySequence.SequenceFormat.NativeText)


def defaults():
    return {a[0]: norm(a[3]) for a in ACTIONS}


def duplicate_defaults():
    seen, out = {}, []
    for action_id, key in defaults().items():
        if key and key in seen:
            out.append((seen[key], action_id, key))
        seen.setdefault(key, action_id)
    return out


def reserved_reason(seq):
    return RESERVED.get(norm(seq))


def owner_of(mapping, seq, exclude=None):
    key = norm(seq)
    if not key:
        return None
    return next((i for i, k in mapping.items() if k == key and i != exclude), None)


def load_overrides():
    from archforge.ui.autosave import load_settings
    raw = load_settings().get(SETTINGS_KEY, {})
    return {str(k): norm(v) for k, v in raw.items() if k in NAMES} if isinstance(raw, dict) else {}


def save_overrides(overrides):
    from archforge.ui.autosave import save_settings
    save_settings({SETTINGS_KEY: dict(overrides)})


# --------------------------------------------------------------------------- what each command does
def _tool(name):
    return lambda w: w._set_active_tool(name)


def _plan_xy(w):
    """Plan point under the mouse when it is over the plan (for «Κουζίνα / Μπάνιο εδώ»)."""
    plan = w.plan_view
    pos = plan.viewport().mapFromGlobal(QCursor.pos())
    if plan.isVisible() and plan.viewport().rect().contains(pos):
        return plan._plan_xy_at(pos)
    return None


def _dock(name):
    def run(w):
        dock = getattr(w, name, None)
        if dock is not None:
            dock.show()
            dock.raise_()
    return run


def _central(index):
    def run(w):
        central = getattr(w, '_central_tabs', None)
        if index == 0:
            if central is not None:
                central.setCurrentIndex(0)
            w.view = w.plan_view
            w.plan_view.setFocus()
        else:
            w._set_pbr_camera('orbit')
    return run


def _workspace(name):
    def run(w):
        from archforge.ui.layers_panel import set_workspace
        set_workspace(w, name)
    return run


def _railing(w):
    from archforge.architecture.railings import TYPES
    w._start_railing_tool(next(iter(TYPES)))


def _duplicate(w):
    from archforge.ui.object_menu import run_object_op
    ids = list(w.doc.selection)
    if not ids:
        w.statusBar().showMessage('Διπλασιασμός: δεν υπάρχει επιλογή', 3000)
        return
    for eid in ids:
        run_object_op(w, eid, 'duplicate')


def _zoom_all(w):
    plan = w.plan_view
    rect = None
    for item in plan._entity_items:
        r = item.sceneBoundingRect()
        rect = r if rect is None else rect.united(r)
    if rect is None or rect.isEmpty():
        w.statusBar().showMessage('Ζουμ σε όλα: η κάτοψη είναι άδεια', 3000)
        return
    plan.fitInView(rect.adjusted(-1.0, -1.0, 1.0, 1.0), Qt.AspectRatioMode.KeepAspectRatio)
    plan.redraw()


def _layout(arg):
    def run(w):
        from archforge.ui.layout_assist import run as layout_run
        layout_run(w, arg, None, _plan_xy(w))
    return run


def _library(w):
    search = getattr(w, '_library_search', None)
    if search is not None:
        for dock in getattr(w, '_approved_docks', ())[:1]:
            dock.show()
            dock.raise_()
        search.setFocus()
        search.selectAll()


def _toggle(attr):
    def run(w):
        target = getattr(w, attr, None)
        if target is not None:
            target.toggle()
    return run


RUN = {
    'tool.select': _tool('select'), 'tool.wall': _tool('wall'), 'tool.door': _tool('door'),
    'tool.window': _tool('window'), 'tool.opening': _tool('opening_rect'), 'tool.railing': _railing,
    'tool.column': _tool('structural_column'), 'tool.beam': _tool('structural_beam'),
    'edit.move': _tool('move'), 'edit.rotate': _tool('rotate'), 'edit.stretch': _tool('stretch'),
    'edit.duplicate': _duplicate,
    'view.plan': _central(0), 'view.3d': _central(1),
    'view.top': lambda w: w._set_pbr_camera('top'), 'view.front': lambda w: w._set_pbr_camera('front'),
    'view.side': lambda w: w._set_pbr_camera('side'), 'view.zoom_all': _zoom_all,
    'env.arch': _workspace('arch'), 'env.structure': _workspace('structure'), 'env.mep': _workspace('mep'),
    'panel.layers': _dock('_layers_dock'), 'panel.properties': _dock('dock'), 'panel.assistant': _dock('_assistant_dock'),
    'panel.library': _library,
    'aid.grid': _toggle('_mockup_grid_check'), 'aid.snap': _toggle('snap_action'),
    'assist.kitchen': _layout('kitchen'), 'assist.bath': _layout('bath'),
    'help.shortcuts': lambda w: open_dialog(w),
}
# Existing window actions taken over (they already sit in the menus and keep their own slot).
ADOPT = {
    'edit.undo': 'undo_action', 'edit.redo': 'redo_action', 'edit.delete': 'delete_action',
    'file.new': 'new_action', 'file.open': 'open_action', 'file.save': 'save_action',
    'tool.stair': 'stair_action', 'tool.ramp': 'ramp_action', 'tool.sculpt': 'sculpt_action',
}


class ShortcutManager:
    def __init__(self, window, overrides=None):
        self.window = window
        self.overrides = load_overrides() if overrides is None else dict(overrides)
        self.actions = {}
        self.mirrors = {}            # id → [(QAction, base tooltip)]
        for action_id, name, _cat, _default, _texts in ACTIONS:
            action = getattr(window, ADOPT[action_id], None) if action_id in ADOPT else None
            if action is None:
                action = QAction(name, window)
                action.triggered.connect(lambda _=False, i=action_id: RUN[i](self.window))
            elif action_id != 'tool.sculpt':
                action.setText(name)           # the menus showed «Undo», «Save» …
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            window.addAction(action)
            self.actions[action_id] = action
        self._silence_legacy()
        self._find_mirrors()
        self.apply()

    # ---------------------------------------------------------------- state
    def mapping(self):
        out = defaults()
        out.update(self.overrides)
        return out

    def key(self, action_id):
        return self.mapping().get(action_id, '')

    def label(self, action_id):
        return display(self.key(action_id))

    def conflict(self, action_id, seq):
        """Name of the command that already has ``seq`` (or the reason it is reserved), else None."""
        reason = reserved_reason(seq)
        if reason:
            return reason
        other = owner_of(self.mapping(), seq, exclude=action_id)
        return NAMES[other] if other else None

    def assign(self, action_id, seq, steal=False):
        """Set a key; returns the other command's id when ``seq`` is taken and not ``steal``."""
        key = norm(seq)
        if key and reserved_reason(key):
            raise ValueError(reserved_reason(key))
        other = owner_of(self.mapping(), key, exclude=action_id)
        if other and not steal:
            return other
        if other:
            self._set(other, '')
        self._set(action_id, key)
        self.apply()
        save_overrides(self.overrides)
        return None

    def _set(self, action_id, key):
        if key == defaults()[action_id]:
            self.overrides.pop(action_id, None)
        else:
            self.overrides[action_id] = key

    def reset(self):
        self.overrides = {}
        self.apply()
        save_overrides(self.overrides)

    def export(self, path):
        with open(path, 'w', encoding='utf8') as handle:
            json.dump({'archforge_shortcuts': 1, 'keys': self.mapping()}, handle, ensure_ascii=False, indent=1)

    def import_(self, path):
        with open(path, encoding='utf8') as handle:
            raw = json.load(handle)
        keys = raw.get('keys', raw) if isinstance(raw, dict) else {}
        mapping = defaults()
        mapping.update({k: norm(v) for k, v in keys.items() if k in NAMES and not reserved_reason(v)})
        seen = {}
        for action_id, key in mapping.items():
            if key and key in seen:
                mapping[action_id] = ''          # the first owner keeps a repeated key
            seen.setdefault(key, action_id)
        self.overrides = {}
        for action_id, key in mapping.items():
            self._set(action_id, key)
        self.apply()
        save_overrides(self.overrides)

    # ---------------------------------------------------------------- Qt
    def apply(self):
        mapping = self.mapping()
        for action_id, action in self.actions.items():
            action.setShortcut(QKeySequence(mapping[action_id]))
        for action_id, mirrors in self.mirrors.items():
            text = display(mapping[action_id])
            for action, tip in mirrors:
                if action.property('af_shortcut_mirror_menu'):
                    # Shown in the menu column only: a widget shortcut of the menu, never a second window shortcut.
                    action.setShortcut(QKeySequence(mapping[action_id]))
                else:
                    action.setToolTip(f'{tip} · Συντόμευση: {text}' if text else tip)
        hook = getattr(self.window, '_after_shortcuts_changed', None)
        if callable(hook):
            hook()

    def _silence_legacy(self):
        """The old development toolbars (hidden) kept S/W/D/N/G/T/R on their own actions."""
        own = set(map(id, self.actions.values()))
        for bar in self.window.findChildren(QToolBar):
            if bar.objectName() not in ('tools_toolbar',):
                continue
            for action in bar.actions():
                if id(action) not in own and not action.shortcut().isEmpty():
                    action.setShortcut(QKeySequence())

    def _find_mirrors(self):
        by_text = {}
        for action_id, _name, _cat, _default, texts in ACTIONS:
            for text in texts:
                by_text.setdefault(text, action_id)
        own = set(map(id, self.actions.values()))
        for action in self.window.findChildren(QAction):
            action_id = by_text.get(action.text())
            if action_id is None or id(action) in own:
                continue
            widgets = action.associatedObjects()
            in_bar = any(isinstance(o, QToolBar) for o in widgets)
            if not in_bar:
                action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
                action.setProperty('af_shortcut_mirror_menu', True)
            self.mirrors.setdefault(action_id, []).append((action, action.toolTip() if in_bar else ''))


def install(window):
    manager = ShortcutManager(window)
    window.shortcuts = manager
    action = QAction('Συντομεύσεις πληκτρολογίου…', window)
    action.triggered.connect(lambda: open_dialog(window))
    window._shortcuts_dialog_action = action
    menus = getattr(window, '_mockup_menus', {})
    for name in ('Επεξεργασία', 'Βοήθεια'):
        menu = menus.get(name)
        if menu is not None:
            menu.addSeparator()
            menu.addAction(action)
    manager.mirrors.setdefault('help.shortcuts', []).append((action, ''))
    action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
    action.setProperty('af_shortcut_mirror_menu', True)
    manager.apply()
    return manager


def hint(window, action_id):
    """« (Del)» for labels, '' when there is no key."""
    manager = getattr(window, 'shortcuts', None)
    text = manager.label(action_id) if manager is not None else display(defaults().get(action_id, ''))
    return f' ({text})' if text else ''


# --------------------------------------------------------------------------- dialog
class ShortcutsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.manager = window.shortcuts
        self.setWindowTitle('Συντομεύσεις πληκτρολογίου')
        self.resize(640, 560)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.search = QLineEdit(self)
        self.search.setPlaceholderText('Αναζήτηση εντολής ή πλήκτρου…')
        self.category = QComboBox(self)
        self.category.addItem('Όλες οι κατηγορίες', '')
        for cat in CATEGORIES:
            self.category.addItem(cat, cat)
        top.addWidget(self.search, 1)
        top.addWidget(self.category)
        lay.addLayout(top)
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(('Κατηγορία', 'Εντολή', 'Συντόμευση'))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel('Νέα συντόμευση:', self))
        self.editor = QKeySequenceEdit(self)
        self.editor.setMaximumSequenceLength(1)
        edit_row.addWidget(self.editor, 1)
        self.assign_button = QPushButton('Ορισμός', self)
        self.clear_button = QPushButton('Χωρίς πλήκτρο', self)
        self.default_button = QPushButton('Προεπιλογή', self)
        for b in (self.assign_button, self.clear_button, self.default_button):
            edit_row.addWidget(b)
        lay.addLayout(edit_row)
        self.message = QLabel('Διάλεξε εντολή, πάτα τον νέο συνδυασμό πλήκτρων και «Ορισμός».', self)
        self.message.setWordWrap(True)
        lay.addWidget(self.message)
        bottom = QHBoxLayout()
        self.reset_button = QPushButton('Επαναφορά προεπιλογών', self)
        self.export_button = QPushButton('Εξαγωγή…', self)
        self.import_button = QPushButton('Εισαγωγή…', self)
        close = QPushButton('Κλείσιμο', self)
        for b in (self.reset_button, self.export_button, self.import_button):
            bottom.addWidget(b)
        bottom.addStretch(1)
        bottom.addWidget(close)
        lay.addLayout(bottom)
        self.search.textChanged.connect(self.fill)
        self.category.currentIndexChanged.connect(self.fill)
        self.table.itemSelectionChanged.connect(self._selected)
        self.editor.keySequenceChanged.connect(self._preview)
        self.assign_button.clicked.connect(lambda: self.set_key(self.editor.keySequence()))
        self.clear_button.clicked.connect(lambda: self.set_key(''))
        self.default_button.clicked.connect(lambda: self.set_key(defaults()[self.current()] if self.current() else ''))
        self.reset_button.clicked.connect(self._reset)
        self.export_button.clicked.connect(self._export)
        self.import_button.clicked.connect(self._import)
        close.clicked.connect(self.accept)
        self.fill()

    def fill(self):
        keep = self.current()
        text = self.search.text().strip().lower()
        cat = self.category.currentData()
        mapping = self.manager.mapping()
        self.table.setRowCount(0)
        for action_id, name, category, _default, _texts in ACTIONS:
            key = display(mapping[action_id])
            if cat and category != cat:
                continue
            if text and text not in name.lower() and text not in key.lower() and text not in category.lower():
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, value in enumerate((category, name, key)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, action_id)
                self.table.setItem(row, col, item)
            if action_id == keep:
                self.table.selectRow(row)

    def current(self):
        items = self.table.selectedItems() if hasattr(self, 'table') else []
        return items[0].data(Qt.ItemDataRole.UserRole) if items else None

    def select(self, action_id):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == action_id:
                self.table.selectRow(row)
                return True
        return False

    def _selected(self):
        action_id = self.current()
        if action_id:
            self.editor.setKeySequence(QKeySequence(self.manager.key(action_id)))
            self.message.setText(f'«{NAMES[action_id]}»: {self.manager.label(action_id) or "χωρίς πλήκτρο"}'
                                 f' · προεπιλογή: {display(defaults()[action_id]) or "—"}')

    def _preview(self, seq):
        action_id = self.current()
        if action_id and norm(seq) and norm(seq) != self.manager.key(action_id):
            taken = self.manager.conflict(action_id, seq)
            if taken:
                self.message.setText(f'Το {display(seq)} χρησιμοποιείται ήδη από «{taken}».'
                                     if not reserved_reason(seq) else f'Το {display(seq)} είναι δεσμευμένο: {taken}.')

    def set_key(self, seq, ask=True):
        action_id = self.current()
        if not action_id:
            self.message.setText('Διάλεξε πρώτα μια εντολή από τον πίνακα.')
            return False
        key = norm(seq)
        reason = reserved_reason(key)
        if reason:
            self.message.setText(f'Το {display(key)} είναι δεσμευμένο: {reason}.')
            return False
        other = self.manager.assign(action_id, key)
        if other:
            text = f'Το {display(key)} χρησιμοποιείται ήδη από «{NAMES[other]}».'
            if not ask or QMessageBox.question(
                    self, 'Σύγκρουση συντόμευσης', text + f'\nΝα δοθεί στο «{NAMES[action_id]}» (το «{NAMES[other]}» μένει χωρίς πλήκτρο);'
            ) != QMessageBox.StandardButton.Yes:
                self.message.setText(text + ' Δεν άλλαξε τίποτα.')
                return False
            self.manager.assign(action_id, key, steal=True)
        self.fill()
        self.select(action_id)
        self.message.setText(f'«{NAMES[action_id]}»: {display(key) or "χωρίς πλήκτρο"} — αποθηκεύτηκε.')
        return True

    def _reset(self):
        self.manager.reset()
        self.fill()
        self.message.setText('Όλες οι συντομεύσεις γύρισαν στις προεπιλογές.')

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Εξαγωγή συντομεύσεων', 'archforge-συντομεύσεις.json', 'JSON (*.json)')
        if path:
            self.manager.export(path)
            self.message.setText(f'Εξήχθησαν στο {path}')

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Εισαγωγή συντομεύσεων', '', 'JSON (*.json)')
        if path:
            try:
                self.manager.import_(path)
            except (OSError, ValueError) as exc:
                self.message.setText(f'Η εισαγωγή απέτυχε: {exc}')
                return
            self.fill()
            self.message.setText('Οι συντομεύσεις εισήχθησαν.')


def open_dialog(window):
    dialog = ShortcutsDialog(window)
    window._shortcuts_dialog = dialog
    dialog.show()
    dialog.raise_()
    return dialog
