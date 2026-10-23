"""Drive ArchForge offscreen the way a person does: ribbon/menu actions, clicks in the plan, marking menu.

Every step is counted; friction notes are collected in ``U.notes``.
"""
import os, sys, json
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
from PySide6.QtCore import Qt, QPointF, QPoint
from PySide6.QtWidgets import QApplication, QMessageBox, QInputDialog
from PySide6.QtTest import QTest

OUT = os.path.join(os.path.dirname(__file__), 'out')
os.makedirs(OUT, exist_ok=True)


class U:
    def __init__(self):
        self.app = QApplication.instance() or QApplication([])
        from archforge.ui.main_window import MainWindow
        # Work left by a killed earlier run: a person would answer «Απόρριψη» once.
        MainWindow._ask_recovery = lambda self, info: 'discard'
        self.w = MainWindow(); self.w.resize(1600, 1000); self.w.show(); self.pump()
        self.steps = 0; self.task = None; self.log = []; self.notes = []
        self.answers = []          # queued answers for modal dialogs

    # -- bookkeeping
    def pump(self, n=3):
        for _ in range(n): self.app.processEvents()

    def begin(self, task):
        self.task = task; self.steps = 0

    def end(self):
        self.log.append((self.task, self.steps)); print(f'[{self.steps:3d} βήματα] {self.task}')

    def note(self, text):
        self.notes.append((self.task, text)); print('  ΤΡΙΒΗ:', text)

    def status(self):
        return self.w.statusBar().currentMessage()

    @property
    def plan(self):
        return self.w.plan_view

    # -- input
    def _pos(self, x, y):
        return self.plan.mapFromScene(QPointF(x, y))

    def see(self, x, y):
        self.plan.centerOn(QPointF(x, y)); self.pump()

    def click(self, x, y, mods=Qt.KeyboardModifier.NoModifier, button=Qt.MouseButton.LeftButton):
        self.steps += 1
        QTest.mouseClick(self.plan.viewport(), button, mods, self._pos(x, y)); self.pump()

    def dbl(self, x, y):
        """A real double click: press/release, then the double-click event (one gesture = one step)."""
        self.click(x, y)
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent
        p = QPointF(self._pos(x, y))
        ev = QMouseEvent(QEvent.Type.MouseButtonDblClick, p, p, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.plan.viewport(), ev)
        rel = QMouseEvent(QEvent.Type.MouseButtonRelease, p, p, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.plan.viewport(), rel); self.pump()

    def drag(self, x1, y1, x2, y2):
        self.steps += 1
        vp = self.plan.viewport(); a = self._pos(x1, y1); b = self._pos(x2, y2)
        QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        for i in range(1, 9):
            p = a + (b - a) * (i / 8)
            QTest.mouseMove(vp, p)
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b); self.pump()

    def key(self, k, text=None):
        self.steps += 1
        QTest.keyClick(self.plan.viewport(), k); self.pump()

    def type(self, text):
        self.steps += 1                       # typing a value counts as one step
        QTest.keyClicks(self.plan.viewport(), text); self.pump()

    def menu(self, *path):
        """Menu bar path, e.g. menu('Κατασκευή', 'Στέγη', 'Δίρριχτη'): one step per level."""
        mb = self.w.menuBar(); actions = mb.actions()
        for i, name in enumerate(path):
            self.steps += 1
            act = next((a for a in actions if a.text().replace('&&', '&') == name), None)
            if act is None:
                raise LookupError(f'menu {path[:i+1]} not found; have {[a.text() for a in actions]}')
            if act.menu() is not None:
                act.menu().aboutToShow.emit(); actions = act.menu().actions()
            else:
                act.trigger(); self.pump(); return act

    def toolbar(self, text):
        from PySide6.QtWidgets import QToolBar, QToolButton
        for tb in self.w.findChildren(QToolBar):
            buttons = [b.defaultAction() for b in tb.findChildren(QToolButton) if b.defaultAction() is not None]
            for a in list(tb.actions()) + buttons:
                if a.text().replace('\n', ' ').strip() == text and a.isVisible():
                    self.steps += 1; a.trigger(); self.pump(); return a
        raise LookupError(text)

    def right(self, x, y):
        """A real right click in the plan (the view decides object / empty space)."""
        from PySide6.QtGui import QContextMenuEvent
        self.plan.hide_marking_menu()
        pos = self._pos(x, y)
        ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, self.plan.viewport().mapToGlobal(pos))
        self.plan.contextMenuEvent(ev); self.pump()
        return self.plan._marking_menu

    def mm(self, x, y, action_id, entity=None):
        """Right click at (x, y) in the plan, then click the item: 2 steps (3 if it is under «Περισσότερα»)."""
        self.steps += 1
        menu = self.right(x, y)
        # Inside a submenu (e.g. «Ανοίγματα ▸ Πόρτα»): open each level as a person would, one click each.
        for sub in self._submenu_path(menu.menu.get('entries', ()), action_id) or ():
            if action_id in menu.buttons:
                break
            self.steps += 1; menu.open_submenu(sub); self.pump()
        if action_id in menu.buttons:
            self.steps += 1; menu.buttons[action_id].click()
        else:
            more = getattr(menu, 'more_button', None); more = more.menu() if more else None
            acts = {a.data(): a for a in (more.actions() if more else [])}
            if action_id not in acts:
                raise LookupError(f'{action_id} not in menu: radial={list(menu.buttons)} more={list(acts)}')
            self.steps += 2; acts[action_id].trigger()
        self.pump()

    @staticmethod
    def _submenu_path(entries, action_id):
        """The submenu entries to open, outermost first, to reach ``action_id`` (None if it is not in one)."""
        for e in entries:
            kids = e.get('children') or ()
            if any(k.get('id') == action_id for k in kids):
                return [e]
            deeper = U._submenu_path(kids, action_id)
            if deeper:
                return [e] + deeper
        return None

    def mm_content(self, x, y):
        menu = self.right(x, y)
        more = getattr(menu, 'more_button', None); more = more.menu() if more else None
        radial = [e['id'] for e in menu.menu['entries'] if e['placement'] == 'radial']
        out = dict(center=menu.menu['center'], radial=radial, inline=[b for b in menu.buttons if b not in radial],
                   more=[a.data() for a in (more.actions() if more else [])])
        self.plan.hide_marking_menu(); return out

    def floor(self, name):
        """«Σχεδιάζω στο:» combo: 2 steps (open + pick)."""
        self.steps += 2
        self.w._activate_level_by_name(name); self.pump()

    def shot(self, name):
        self.w.grab().save(os.path.join(OUT, name + '.png'))

    def kinds(self):
        from collections import Counter
        return Counter(e.kind for e in self.w.doc.entities.values())


def auto_dialogs(u):
    """Answer modal questions like a person would (Yes), counting one step each."""
    orig_q = QMessageBox.question
    def q(*a, **k):
        u.steps += 1; print('  ΔΙΑΛΟΓΟΣ:', a[1] if len(a) > 1 else '', '|', (a[2] if len(a) > 2 else '')[:120].replace('\n', ' '))
        return QMessageBox.StandardButton.Yes
    QMessageBox.question = staticmethod(q)
    def info(*a, **k):
        print('  ΜΗΝΥΜΑ:', a[1] if len(a) > 1 else '', '|', str(a[2] if len(a) > 2 else '')[:200].replace('\n', ' ')); u.steps += 1
        return QMessageBox.StandardButton.Ok
    QMessageBox.information = staticmethod(info); QMessageBox.warning = staticmethod(info); QMessageBox.critical = staticmethod(info)
    def get(kind):
        def f(*a, **k):
            u.steps += 2
            if u.answers:
                v = u.answers.pop(0); print(f'  ΕΡΩΤΗΣΗ ({kind}):', a[1:3], '->', v); return v, True
            default = a[3] if len(a) > 3 else k.get('value', '')
            if kind == 'item':
                items = a[3]; idx = a[4] if len(a) > 4 else 0; default = items[idx]
            print(f'  ΕΡΩΤΗΣΗ ({kind}):', a[1:3], '-> προεπιλογή', default); return default, True
        return staticmethod(f)
    QInputDialog.getDouble = get('double'); QInputDialog.getInt = get('int')
    QInputDialog.getText = get('text'); QInputDialog.getItem = get('item')
