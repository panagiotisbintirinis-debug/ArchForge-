"""100 bot χρήστες: ολοκληρωμένα κτίρια (κέλυφος, διακόσμηση, Η/Μ, έξοδοι) ΜΟΝΟ όπως άνθρωπος.

Ιδιοκτήτης 06/11: «πριν πάει σε πραγματικούς χρήστες … αυστηρά τρόποι χρήσης ως άνθρωπος σε 100 bot για πολύπλοκα
ολοκληρωμένα σχέδια κτιρίου, διακόσμησης και λειτουργίας, και επιστρέφουν τα λάθη».

Κανόνας: το bot **ενεργεί** μόνο με ό,τι έχει ένας άνθρωπος — μενού, κουμπιά, κλικ / διπλό κλικ / σύρσιμο / δεξί κλικ
στην κάτοψη, πλήκτρα, απαντήσεις σε διαλόγους (το κουμπί που θα πατούσε ένας χρήστης, όνομα αρχείου που θα έγραφε).
Δεν καλεί συναρτήσεις του προγράμματος. Ο **ελεγκτής** (όχι το bot) κοιτάζει μέσα στο έργο για να κρίνει αν κάτι
έγινε, και στο τέλος ελέγχει: έγκυρα στοιχεία, αποθήκευση → άνοιγμα ίδιο, αναίρεση όλων → άδειο, επανάληψη όλων → ίδιο.

    QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 python scripts/user_drive/bots.py fleet --n 100 --jobs 4
    ... python scripts/user_drive/bots.py one --seed 7          # ένα bot, με εκτύπωση βημάτων

Βγάζει `scripts/user_drive/out/bots/bot_<seed>.json` και την αναφορά `docs/BOTS_REPORT.md` (λάθη ομαδοποιημένα).
"""
from __future__ import annotations

import json, math, os, random, re, subprocess, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(HERE, 'out', 'bots')
REPORT = os.path.join(ROOT, 'docs', 'BOTS_REPORT.md')

# Μηνύματα της γραμμής κατάστασης που λένε ότι κάτι χάλασε (όχι απλή ενημέρωση του χρήστη).
BAD_STATUS = re.compile(r'Traceback|Exception|Error\b|σφάλμα|απέτυχε|δεν βγήκε|δεν διαβάστηκε|δεν αποθηκεύτηκε', re.I)
GREEK = re.compile(r'[\u0370-\u03ff\u1f00-\u1fff]')
ENGLISH = re.compile(r'[A-Za-z]{3,} [A-Za-z]{2,} [A-Za-z]{2,}')
# Θόρυβος του Qt στο cloud (χωρίς GPU / WebEngine): δεν είναι λάθη του ArchForge.
QT_NOISE = re.compile(r'QRhi|Vulkan|GPU|WebEngine|OpenGL|zygote|AA_ShareOpenGLContexts|propagateSizeHints|'
                      r'QFont|This plugin does not support|libpng|Release of profile|js:|QPainter::|'
                      r'QWindowsWindow|qt\.qpa|QBackingStore|Populating font family', re.I)


# ----------------------------------------------------------------------------------------------- scenario
def scenario(seed):
    """Ένα κτίριο από το «σκίτσο» του χρήστη: τύπος, περίγραμμα, κάνναβος χώρων, όροφοι, τι θα βάλει."""
    r = random.Random(seed)
    kind = r.choice(['μονοκατοικία', 'διώροφη', 'πολυκατοικία', 'με υπόγειο', 'κατάστημα + κατοικία', 'Γ σχήμα'])
    W = round(r.uniform(8, 16), 1); D = round(r.uniform(7, 13), 1)
    shape = 'L' if kind == 'Γ σχήμα' or r.random() < 0.2 else 'rect'
    W2 = round(W * r.uniform(0.45, 0.65), 1) if shape == 'L' else W     # το βόρειο τμήμα του Γ είναι στενότερο
    D1 = round(D * r.uniform(0.5, 0.65), 1) if shape == 'L' else D
    floors = {'μονοκατοικία': 1, 'διώροφη': 2, 'πολυκατοικία': r.randint(3, 4), 'με υπόγειο': r.randint(1, 2),
              'κατάστημα + κατοικία': 2, 'Γ σχήμα': r.randint(1, 2)}[kind]
    basement = kind == 'με υπόγειο' or r.random() < 0.15
    nx = max(1, min(3, int(W // 4))); ny = max(1, min(3, int(D // 3.5)))
    xs = sorted(round(W * (i + r.uniform(-0.12, 0.12)) / (nx + 1), 2) for i in range(1, nx + 1))
    ys = sorted(round(D * (j + r.uniform(-0.12, 0.12)) / (ny + 1), 2) for j in range(1, ny + 1))
    if shape == 'L':
        xs = [x for x in xs if abs(x - W2) > 0.8]
        ys = [y for y in ys if abs(y - D1) > 0.8] + [D1]
        ys.sort()
    return dict(seed=seed, kind=kind, shape=shape, W=W, D=D, W2=W2, D1=D1, floors=floors, basement=basement,
                xs=xs, ys=ys, roof=r.choice(['tiled', 'tiled', 'flat']), jitter=r.uniform(0.0, 0.04),
                order=r.sample(['deco', 'mep', 'structure', 'cad', 'outside', 'materials'], 6), mistakes=r.random() < 0.6,
                railing=r.choice(['Κάγκελα κάθετα', 'Οριζόντιες ράβδοι', 'Τζάμι με ορθοστάτες', 'Τζάμι σε χωνευτό προφίλ',
                                  'Πάνελ συμπαγές', 'Πάνελ διάτρητο', 'Συρματόσχοινο inox', 'Ξύλινο', 'Κτιστό στηθαίο']),
                fence=r.choice(['Κάγκελα κάθετα', 'Ξύλινο', 'Κτιστό στηθαίο', 'Πάνελ διάτρητο']),
                pool=r.random() < 0.5, n_materials=r.randint(3, 8), n_furniture=r.randint(2, 6),
                edits=r.random() < 0.7)


def outline(s):
    W, D, W2, D1 = s['W'], s['D'], s['W2'], s['D1']
    if s['shape'] == 'L':
        return [(0, 0), (W, 0), (W, D1), (W2, D1), (W2, D), (0, D), (0, 0)]
    return [(0, 0), (W, 0), (W, D), (0, D), (0, 0)]


def inside(s, x, y):
    if not (0 < x < s['W'] and 0 < y < s['D']):
        return False
    return not (s['shape'] == 'L' and x > s['W2'] and y > s['D1'])


def partitions(s):
    """Εσωτερικοί τοίχοι από τοίχο σε τοίχο (κομμένοι στο περίγραμμα του Γ)."""
    W, D, W2, D1 = s['W'], s['D'], s['W2'], s['D1']
    segs = []
    for x in s['xs']:
        segs.append(((x, 0), (x, D if x < W2 else D1)))
    for y in s['ys']:
        if s['shape'] == 'L' and abs(y - D1) < 1e-6:
            segs.append(((0, y), (W2, y)))
        else:
            segs.append(((0, y), (W if y < D1 else W2, y)))
    return segs


def cells(s):
    """Οι χώροι του κάνναβου: κέντρο, διαστάσεις, ρόλος (σαλόνι, κουζίνα, μπάνιο, υπνοδωμάτιο, χολ)."""
    X = [0] + s['xs'] + [s['W']]; Y = [0] + s['ys'] + [s['D']]
    out = []
    for i in range(len(X) - 1):
        for j in range(len(Y) - 1):
            x0, x1, y0, y1 = X[i], X[i + 1], Y[j], Y[j + 1]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if inside(s, cx, cy):
                out.append(dict(x0=x0, x1=x1, y0=y0, y1=y1, cx=cx, cy=cy, area=(x1 - x0) * (y1 - y0)))
    out.sort(key=lambda c: -c['area'])
    roles = ['σαλόνι', 'κουζίνα'] + ['υπνοδωμάτιο'] * 8
    for i, c in enumerate(out):
        c['role'] = roles[i] if i < len(roles) else 'υπνοδωμάτιο'
    if len(out) >= 3:
        out[-1]['role'] = 'μπάνιο'
    return out


# ----------------------------------------------------------------------------------------------- the bot
class Bot:
    def __init__(self, seed, verbose=False):
        import builtins
        self.seed = seed; self.verbose = verbose; self.s = scenario(seed)
        self.rng = random.Random(seed * 7919 + 1)
        self.dir = os.path.join(OUT, f'bot_{seed}'); os.makedirs(self.dir, exist_ok=True)
        self.findings = []; self.steps = []; self.step = 'εκκίνηση'; self.status_log = []
        self.windows_seen = []
        self._hooks()
        from PySide6.QtWidgets import QApplication
        self.app = QApplication.instance() or QApplication([])
        from archforge.ui.main_window import MainWindow
        MainWindow._ask_recovery = lambda _self, info: 'discard'      # «Απόρριψη» στην ανάκτηση εργασίας
        self.w = MainWindow(); self.w.resize(1600, 1000); self.w.show(); self.pump(6)
        self.w.statusBar().messageChanged.connect(self._status)

    # -- the observer ---------------------------------------------------------------------------------
    def find(self, kind, text, detail=''):
        f = dict(kind=kind, step=self.step, text=str(text)[:400], detail=str(detail)[:2500])
        self.findings.append(f)
        if self.verbose:
            print(f'    !! [{kind}] {text}')

    def _status(self, msg):
        if msg:
            self.status_log.append((self.step, msg))
            if BAD_STATUS.search(msg):
                self.find('μήνυμα σφάλματος', msg)
            elif ENGLISH.search(msg) and not GREEK.search(msg) and not msg.startswith(('X ', 'PBR Viewport')):
                self.find('αγγλικό μήνυμα στον χρήστη', msg)

    def _hooks(self):
        bot = self

        def excepthook(t, v, tb):
            bot.find('εξαίρεση', f'{t.__name__}: {v}', ''.join(traceback.format_exception(t, v, tb))[-2500:])
        sys.excepthook = excepthook
        from PySide6.QtCore import qInstallMessageHandler, QtMsgType

        def qt_msg(mode, ctx, msg):
            if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg) and not QT_NOISE.search(msg):
                bot.find('προειδοποίηση Qt', msg)
        qInstallMessageHandler(qt_msg)
        from PySide6.QtWidgets import QMessageBox, QInputDialog, QFileDialog, QDialog, QDialogButtonBox, QPushButton

        def box(level):
            def f(parent, title, text, *a, **k):
                bot.windows_seen.append((bot.step, f'{level}: {title}'))
                if level in ('critical',):
                    bot.find('μήνυμα σφάλματος', f'{title}: {text}')
                elif level == 'warning':
                    bot.find('προειδοποίηση χρήστη', f'{title}: {text}')
                if bot.verbose:
                    print(f'    [{level}] {title} | {str(text)[:140]}')
                return QMessageBox.StandardButton.Yes if level == 'question' else QMessageBox.StandardButton.Ok
            return staticmethod(f)
        for lv in ('question', 'information', 'warning', 'critical'):
            setattr(QMessageBox, lv, box(lv))

        def get(kind):
            def f(parent, title, label, *a, **k):
                bot.windows_seen.append((bot.step, f'ερώτηση: {title}'))
                if bot.answers:
                    return bot.answers.pop(0), True
                if kind == 'item':
                    items = a[0] if a else k.get('items', [''])
                    idx = a[1] if len(a) > 1 else k.get('current', 0)
                    return (items[idx] if items else ''), True
                default = a[0] if a else k.get('value', k.get('text', ''))
                return default, True
            return staticmethod(f)
        for name, kind in (('getDouble', 'double'), ('getInt', 'int'), ('getText', 'text'), ('getItem', 'item'),
                           ('getMultiLineText', 'text')):
            setattr(QInputDialog, name, get(kind))

        def save_name(parent, title='', start='', pattern='', *a, **k):
            ext = re.search(r'\*(\.\w+)', pattern or '')
            base = os.path.basename(start) if start else re.sub(r'\W+', '_', title or 'arxeio')[:30]
            if ext and ext.group(1).lower() == '.archforge':
                base = 'ergo.archforge'
            if ext and not base.lower().endswith(ext.group(1).lower()):
                base = os.path.splitext(base)[0] + ext.group(1)
            path = os.path.join(bot.dir, base or 'arxeio')
            bot.windows_seen.append((bot.step, f'αποθήκευση αρχείου: {title} → {os.path.basename(path)}'))
            return path, pattern
        QFileDialog.getSaveFileName = staticmethod(save_name)

        def open_name(parent, title='', start='', pattern='', *a, **k):
            path = bot.open_queue.pop(0) if bot.open_queue else ''
            bot.windows_seen.append((bot.step, f'άνοιγμα αρχείου: {title} → {os.path.basename(path) or "(άκυρο)"}'))
            return path, pattern
        QFileDialog.getOpenFileName = staticmethod(open_name)
        QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ''))
        QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: bot.dir)
        bot.open_queue = []; bot.answers = []; bot.choose_in_dialogs = False

        OK_TEXTS = ('OK', 'Ok', 'Εντάξει', 'Εφαρμογή', 'Αποθήκευση', 'Υπολογισμός', 'Εξαγωγή', 'Δημιουργία', 'Ναι',
                    'Συνέχεια', 'Τοποθέτηση', 'Κλείσιμο', 'Close')

        def exec_(dlg, *a, **k):
            """Ένας άνθρωπος βλέπει τον διάλογο και πατά το «OK» του (ή το προεπιλεγμένο κουμπί)."""
            title = dlg.windowTitle() or type(dlg).__name__
            bot.windows_seen.append((bot.step, f'διάλογος: {title}'))
            if isinstance(dlg, QMessageBox):
                text = dlg.text()
                if dlg.icon() == QMessageBox.Icon.Critical:
                    bot.find('μήνυμα σφάλματος', f'{title}: {text}')
                b = dlg.defaultButton() or (dlg.buttons()[0] if dlg.buttons() else None)
                if b is not None:
                    dlg.show(); bot.pump(); b.click(); bot.pump()
                    return dlg.standardButton(b) or 0
                return 0
            dlg.show(); bot.pump(4)
            clicked = None
            for bb in dlg.findChildren(QDialogButtonBox):
                for b in bb.buttons():
                    role = bb.buttonRole(b)
                    if role in (QDialogButtonBox.ButtonRole.AcceptRole, QDialogButtonBox.ButtonRole.YesRole) and b.isEnabled():
                        clicked = b; break
                if clicked: break
            if clicked is None:
                for b in dlg.findChildren(QPushButton):
                    if b.isVisible() and b.isEnabled() and (b.isDefault() or b.text().replace('&', '') in OK_TEXTS):
                        clicked = b; break
            if bot.choose_in_dialogs:
                bot.choose(dlg)
            if clicked is not None:
                clicked.click(); bot.pump(4)
            else:
                bot.find('διάλογος χωρίς «OK»', f'{title}: κανένα κουμπί αποδοχής')
            if dlg.isVisible():                       # still open: the person closes it with «Χ» (= Άκυρο)
                dlg.reject(); bot.pump()
            return dlg.result()
        QDialog.exec = exec_
        QDialog.exec_ = exec_
        QMessageBox.exec = exec_

    def choose(self, dlg):
        """Ο χρήστης διαλέγει κάτι στον διάλογο: μια γραμμή λίστας (κλικ) και τιμή στις λίστες επιλογής (βελάκια)."""
        from PySide6.QtWidgets import QComboBox, QListWidget
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        for cb in dlg.findChildren(QComboBox):
            if cb.isVisible() and cb.isEnabled() and cb.count() > 1:
                for _ in range(self.rng.randint(0, cb.count() - 1)):
                    QTest.keyClick(cb, Qt.Key.Key_Down)
                self.pump(2)
        for lw in dlg.findChildren(QListWidget):
            if lw.isVisible() and lw.count():
                item = lw.item(self.rng.randrange(lw.count()))
                lw.scrollToItem(item); self.pump(1)
                r = lw.visualItemRect(item)
                QTest.mouseClick(lw.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, r.center())
                self.pump(2)

    # -- hands ----------------------------------------------------------------------------------------
    def pump(self, n=3):
        for _ in range(n):
            self.app.processEvents()

    @property
    def plan(self):
        return self.w.plan_view

    def hand(self, x, y):
        j = self.s['jitter']
        return x + self.rng.uniform(-j, j), y + self.rng.uniform(-j, j)

    def _pos(self, x, y):
        from PySide6.QtCore import QPointF
        return self.plan.mapFromScene(QPointF(x, y))

    def see(self, x, y):
        from PySide6.QtCore import QPointF
        self.plan.centerOn(QPointF(x, y)); self.pump()

    def zoom_to_site(self):
        """Ροδέλα προς τα πίσω ώσπου να χωρά όλο το οικόπεδο (κτίριο + 10 m γύρω), μετά κέντρο με τη μέση."""
        from PySide6.QtGui import QWheelEvent
        from PySide6.QtCore import QPointF, QPoint, Qt
        from PySide6.QtWidgets import QApplication
        s = self.s; need_w = s['W'] + 22; need_h = s['D'] + 22
        vp = self.plan.viewport()
        for _ in range(40):
            k = self.plan.transform().m11()
            if vp.width() / k >= need_w and vp.height() / k >= need_h:
                break
            c = QPointF(vp.width() / 2, vp.height() / 2)
            QApplication.sendEvent(vp, QWheelEvent(c, vp.mapToGlobal(c), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton,
                                                   Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False))
            self.pump(1)
        self.see(s['W'] / 2, s['D'] / 2 - 3)

    def move(self, x, y):
        from PySide6.QtTest import QTest
        QTest.mouseMove(self.plan.viewport(), self._pos(x, y)); self.pump(1)

    def click(self, x, y, exact=False):
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        if not exact:
            x, y = self.hand(x, y)
        self.move(x - 0.2, y - 0.1); self.move(x, y)
        QTest.mouseClick(self.plan.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, self._pos(x, y))
        self.pump()

    def dbl(self, x, y):
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import QEvent, QPointF, Qt
        from PySide6.QtWidgets import QApplication
        x, y = self.hand(x, y)
        self.click(x, y, exact=True)
        p = QPointF(self._pos(x, y))
        for t, b in ((QEvent.Type.MouseButtonDblClick, Qt.MouseButton.LeftButton),
                     (QEvent.Type.MouseButtonRelease, Qt.MouseButton.NoButton)):
            QApplication.sendEvent(self.plan.viewport(), QMouseEvent(t, p, p, Qt.MouseButton.LeftButton, b,
                                                                     Qt.KeyboardModifier.NoModifier))
        self.pump()

    def drag(self, x1, y1, x2, y2):
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        vp = self.plan.viewport(); a = self._pos(*self.hand(x1, y1)); b = self._pos(*self.hand(x2, y2))
        QTest.mouseMove(vp, a); QTest.mousePress(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, a)
        for i in range(1, 11):
            QTest.mouseMove(vp, a + (b - a) * (i / 10)); self.pump(1)
        QTest.mouseRelease(vp, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b); self.pump()

    def key(self, name):
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        QTest.keyClick(self.plan.viewport(), getattr(Qt.Key, 'Key_' + name)); self.pump()

    def esc(self):
        self.key('Escape')

    def menu(self, *path):
        """Κλικ στη γραμμή μενού και σε κάθε υπομενού ώς την εντολή (το κείμενο όπως το βλέπει ο χρήστης)."""
        actions = self.w.menuBar().actions()
        for i, name in enumerate(path):
            act = next((a for a in actions if a.text().replace('&&', '&').replace('&', '') == name.replace('&', '')
                        and a.isVisible()), None)
            if act is None:
                raise LookupError(f'δεν υπάρχει στο μενού: {" ▸ ".join(path[:i + 1])}')
            if act.menu() is not None and i < len(path) - 1:
                act.menu().aboutToShow.emit(); self.pump(1); actions = act.menu().actions()
            else:
                if not act.isEnabled():
                    raise LookupError(f'ανενεργή εντολή: {" ▸ ".join(path)}')
                act.trigger(); self.pump(4); return act
        raise LookupError(f'υπομενού χωρίς εντολή: {" ▸ ".join(path)}')

    def menu_items(self, *path):
        actions = self.w.menuBar().actions()
        for name in path:
            act = next((a for a in actions if a.text().replace('&', '') == name.replace('&', '')), None)
            if act is None or act.menu() is None:
                return []
            act.menu().aboutToShow.emit(); actions = act.menu().actions()
        return [a.text().replace('&&', '&') for a in actions if a.text() and not a.isSeparator() and a.isVisible()]

    def button(self, *texts):
        from PySide6.QtWidgets import QToolBar, QToolButton
        for tb in self.w.findChildren(QToolBar):
            if not tb.isVisible():
                continue
            for a in list(tb.actions()) + [b.defaultAction() for b in tb.findChildren(QToolButton) if b.defaultAction()]:
                if a.text().replace('\n', ' ').strip() in texts and a.isVisible() and a.isEnabled():
                    a.trigger(); self.pump(3); return a
        raise LookupError(f'δεν υπάρχει κουμπί: {" / ".join(texts)}')

    def right(self, x, y):
        from PySide6.QtGui import QContextMenuEvent
        self.plan.hide_marking_menu()
        pos = self._pos(x, y)
        self.plan.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos,
                                                     self.plan.viewport().mapToGlobal(pos)))
        self.pump()
        return self.plan._marking_menu

    def mm(self, x, y, action_id):
        """Δεξί κλικ και κλικ στο κουμπί του μενού ποντικιού (ανοίγοντας υπομενού όπως ο χρήστης)."""
        sys.path.insert(0, HERE)
        from user import U
        menu = self.right(x, y)
        if menu is None:
            raise LookupError('δεξί κλικ: δεν άνοιξε μενού')
        for sub in U._submenu_path(menu.menu.get('entries', ()), action_id) or ():
            if action_id in menu.buttons:
                break
            menu.open_submenu(sub); self.pump()
        if action_id in menu.buttons:
            menu.buttons[action_id].click(); self.pump(3); return
        more = getattr(menu, 'more_button', None); more = more.menu() if more else None
        acts = {a.data(): a for a in (more.actions() if more else [])}
        if action_id not in acts:
            self.plan.hide_marking_menu()
            raise LookupError(f'μενού ποντικιού: δεν έχει «{action_id}» (έχει {list(menu.buttons)})')
        acts[action_id].trigger(); self.pump(3)

    def floors(self):
        sel = self.w.floor_selector
        return [sel.itemText(i) for i in range(sel.count())]

    def pick_floor(self, index):
        """«Σχεδιάζω στο:» — ο χρήστης διαλέγει από τη λίστα ορόφων (κατά σειρά από κάτω)."""
        sel = self.w.floor_selector
        items = [(i, sel.itemData(i)) for i in range(sel.count())]
        items = [(i, d) for i, d in items if isinstance(d, (tuple, list)) and len(d) > 1]
        items.sort(key=lambda t: float(t[1][1]) if isinstance(t[1][1], (int, float)) else 0.0)
        if not items:
            raise LookupError('ο επιλογέας ορόφων είναι άδειος')
        i = items[min(index, len(items) - 1)][0]
        from PySide6.QtTest import QTest
        from PySide6.QtCore import Qt
        if not sel.isVisible() or not sel.isEnabled():
            raise LookupError('ο επιλογέας ορόφων δεν φαίνεται')
        for _ in range(sel.count() + 1):           # βελάκια πάνω στη λίστα «Σχεδιάζω στο:» ως τον όροφο
            if sel.currentIndex() == i:
                break
            QTest.keyClick(sel, Qt.Key.Key_Down if sel.currentIndex() < i else Qt.Key.Key_Up); self.pump(2)
        if sel.currentIndex() != i:
            raise LookupError('ο όροφος δεν διαλέγεται με τα βελάκια')
        self.pump(4)

    def close_windows(self):
        """Κλείνει όποιο παράθυρο άνοιξε η εντολή (όπως το «Χ» του χρήστη)."""
        from PySide6.QtWidgets import QApplication, QWidget
        for wd in QApplication.topLevelWidgets():
            if wd is self.w or not wd.isVisible() or not isinstance(wd, QWidget):
                continue
            if wd.isWindow() and type(wd).__name__ not in ('QMenu', 'QToolTip'):
                self.windows_seen.append((self.step, f'παράθυρο: {wd.windowTitle() or type(wd).__name__}'))
                wd.close(); self.pump()
        self.plan.hide_marking_menu()

    # -- observer helpers ----------------------------------------------------------------------------
    def count(self, *kinds):
        es = self.w.doc.entities.values()
        return sum(1 for e in es if not kinds or e.kind in kinds)

    def do(self, name, fn, expect=None, kinds=()):
        """Ένα βήμα του χρήστη. ``expect``: 'more' = πρέπει να προστεθούν στοιχεία (των ``kinds``)."""
        self.step = name
        before = self.count(*kinds); t0 = time.perf_counter(); n0 = len(self.findings)
        ok = True
        import faulthandler
        faulthandler.dump_traceback_later(180, repeat=True)          # a hung step tells where (in bot_<seed>.err)
        try:
            fn()
        except LookupError as exc:
            self.find('δεν βρέθηκε εντολή', exc); ok = False
        except Exception as exc:                                         # noqa: BLE001
            self.find('εξαίρεση', f'{type(exc).__name__}: {exc}', traceback.format_exc()[-2500:]); ok = False
        faulthandler.cancel_dump_traceback_later()
        dt = time.perf_counter() - t0
        self.close_windows()
        after = self.count(*kinds)
        if ok and expect == 'more' and after <= before and len(self.findings) == n0:
            said = [m for st, m in self.status_log if st == name and not m.startswith(('X ', 'Εργαλείο', 'Επιλογή', 'Ακυρώθηκε'))]
            last = said[-1] if said else ''
            if last:
                self.find('δεν έγινε (με εξήγηση)', f'{name} — {last}')
            else:
                self.find('δεν έγινε τίποτα', name)
        if dt > 20:
            self.find('αργό', f'{name}: {dt:.0f} s')
        self.steps.append(dict(step=name, s=round(dt, 2), added=after - before))
        if self.verbose:
            print(f'  {dt:6.1f}s {after - before:+4d}  {name}')
        return after - before

    # -- the work ------------------------------------------------------------------------------------
    def tool(self, *texts):
        """Εργαλείο από τη γραμμή εργαλείων (ελληνικό ή αγγλικό κουμπί)."""
        self.button(*texts)

    def select_tool(self):
        try:
            self.tool('Select', 'Επιλογή')
        except LookupError:
            self.esc()

    def walls(self, points):
        self.tool('Τοίχος (κλικ στις γωνίες)', 'Wall', 'Τοίχος')
        for x, y in points:
            self.click(x, y)
        self.esc(); self.select_tool()

    def wall(self, a, b):
        self.tool('Τοίχος (κλικ στις γωνίες)', 'Wall', 'Τοίχος')
        self.click(*a); self.dbl(*b); self.esc(); self.select_tool()

    def place(self, menu_path, points, kinds=(), double=True):
        """Εντολή από μενού και κλικ στα σημεία (διπλό, αν το απλό δεν έβαλε τίποτα)."""
        def run():
            self.menu(*menu_path)
            for x, y in points:
                n = self.count(); m = len(self.status_log)
                self.click(x, y)
                said = [t for _, t in self.status_log[m:] if not t.startswith(('X ', 'Εργαλείο'))]
                if self.count() == n and double and not said:          # nothing happened, nothing said: try twice
                    self.dbl(x, y)
            self.esc(); self.select_tool()
        return self.do(' ▸ '.join(menu_path[-2:]) + f' ×{len(points)}', run, 'more', kinds)

    def storey(self, level_index, label):
        s = self.s; O = outline(s); rng = self.rng
        self.do(f'{label}: περίγραμμα', lambda: self.walls(O), 'more', ('wall',))
        if s['mistakes'] and rng.random() < 0.5:
            def oops():                    # ξεκινά τοίχο λάθος και τον ακυρώνει με Esc
                self.tool('Τοίχος (κλικ στις γωνίες)', 'Wall', 'Τοίχος'); self.click(s['W'] / 2, s['D'] / 2)
                self.move(s['W'] / 2 + 1, s['D'] / 2); self.esc(); self.esc(); self.select_tool()
            self.do(f'{label}: τοίχος που ακυρώνεται (Esc)', oops)
        for a, b in partitions(s):
            self.do(f'{label}: εσωτερικός τοίχος', lambda a=a, b=b: self.wall(a, b), 'more', ('wall',))
        C = cells(s)
        doors = []
        X = [0] + s['xs'] + [s['W']]
        for c in C:                                                       # πόρτα προς τον δυτικό / νότιο γείτονα
            if c['x0'] > 0 and inside(s, c['x0'] - 0.3, c['cy']):
                doors.append((c['x0'], c['cy']))
            elif c['y0'] > 0 and inside(s, c['cx'], c['y0'] - 0.3):
                doors.append((c['cx'], c['y0']))
        if level_index == 0:
            liv = C[0]; doors.append((liv['cx'], 0.0 if liv['y0'] == 0 else liv['y0']))
        self.place(('Κατασκευή', 'Ανοίγματα', 'Πόρτα'), doors, ('opening', 'door'))
        wins = []
        for c in C:
            if c['y0'] == 0: wins.append((c['cx'] + 0.4, 0.0))
            if c['x0'] == 0: wins.append((0.0, c['cy']))
            if abs(c['x1'] - s['W']) < 1e-6: wins.append((s['W'], c['cy']))
            if abs(c['y1'] - s['D']) < 1e-6 or (s['shape'] == 'L' and abs(c['y1'] - s['D1']) < 1e-6 and c['x0'] >= s['W2']):
                wins.append((c['cx'], c['y1']))
        self.place(('Κατασκευή', 'Ανοίγματα', 'Παράθυρο'), wins, ('opening', 'window'))
        return C

    def interiors(self, C, level_index):
        """Διακόσμηση και λειτουργία: κουζίνα, μπάνιο, φώτα, πρίζες, είδη υγιεινής."""
        s = self.s
        for c in C:
            if c['role'] == 'κουζίνα' and level_index == 0:
                def kitchen(c=c):
                    self.menu('Διαμόρφωση', 'Κουζίνα·ντουλάπια', 'Ντουλάπια / κουζίνα', 'Κάτω ντουλάπι')
                    y = c['y1'] - 0.35
                    self.click(c['x1'] - 0.35, y); self.dbl(c['x0'] + 0.35, y); self.key('Return'); self.esc()
                    self.select_tool()
                self.do('κουζίνα κατά μήκος τοίχου', kitchen, 'more', ('cabinet',))
            if c['role'] == 'μπάνιο':
                def bath(c=c):
                    self.select_tool(); self.mm(c['cx'], c['cy'], 'mm:layout:bath'); self.mm(c['cx'], c['cy'], 'mm:layout:apply')
                n = self.do('μπάνιο εδώ (μενού ποντικιού)', bath, 'more')
                if n <= 0:
                    self.place(('Εγκαταστάσεις', 'Ύδρευση', 'Νιπτήρας'), [(c['x0'] + 0.4, c['cy'])])
                    self.place(('Εγκαταστάσεις', 'Ύδρευση', 'Λεκάνη WC'), [(c['x1'] - 0.4, c['cy'])])
                    self.place(('Εγκαταστάσεις', 'Ύδρευση', 'Ντουζιέρα'), [(c['cx'], c['y1'] - 0.5)])
                self.place(('Εγκαταστάσεις', 'Αερισμός', 'Ανεμιστήρας απαγωγής μπάνιου'), [(c['cx'], c['y1'] - 0.1)])
        self.place(('Εγκαταστάσεις', 'Φωτισμός', 'Φωτιστικό οροφής'), [(c['cx'], c['cy']) for c in C])
        socks = self.menu_items('Εγκαταστάσεις', 'Ηλεκτρολογικά', 'Πρίζες')
        if socks:
            self.place(('Εγκαταστάσεις', 'Ηλεκτρολογικά', 'Πρίζες', socks[0]), [(c['x0'] + 0.15, c['cy']) for c in C])
        sw = self.menu_items('Εγκαταστάσεις', 'Ηλεκτρολογικά', 'Διακόπτες')
        if sw:
            self.place(('Εγκαταστάσεις', 'Ηλεκτρολογικά', 'Διακόπτες', sw[0]), [(c['x0'] + 0.15, c['y0'] + 0.5) for c in C])
        if level_index == 0:
            self.place(('Εγκαταστάσεις', 'Ηλεκτρολογικά', 'Ηλεκτρικός πίνακας'), [(C[0]['x0'] + 0.15, C[0]['y0'] + 1.0)])

    def run(self):
        s = self.s; rng = self.rng; t0 = time.perf_counter()
        self.do('Στοιχεία έργου (ερωτήσεις)', lambda: self.menu('Έργο', 'Στοιχεία έργου', 'Στοιχεία έργου (ερωτήσεις)…'))
        self.zoom_to_site()
        all_cells = []
        if s['basement']:
            self.do('Υπόγειο', lambda: self.menu('Έργο', 'Όροφοι', 'Υπόγειο'))
            self.do('επιλογή υπογείου', lambda: self.pick_floor(0))
            self.do('Υπόγειο: περίγραμμα', lambda: self.walls(outline(s)), 'more', ('wall',))
            self.do('επιστροφή στο ισόγειο', lambda: self.pick_floor(1))
        base = 1 if s['basement'] else 0
        for k in range(s['floors']):
            label = 'Ισόγειο' if k == 0 else f'{k}ος όροφος'
            if k > 0:
                self.do(f'νέος όροφος ({label})', lambda: self.menu('Έργο', 'Όροφοι', 'Όροφος'))
                self.do(f'επιλογή {label}', lambda k=k: self.pick_floor(base + k))
            C = self.storey(k, label)
            all_cells.append(C)
            if k > 0:
                def balcony(k=k):
                    self.menu('Κατασκευή', 'Πλάκες', 'Μπαλκόνι (σχεδίαση)'); self.drag(1.0, 0.0, min(s['W'] - 1, 6.0), -1.6)
                    self.esc(); self.select_tool()
                if self.do(f'{label}: μπαλκόνι νότια (σύρσιμο)', balcony, 'more') > 0:
                    def rail():
                        self.menu('Κατασκευή', 'Κάγκελα', s['railing'])
                        for p_ in [(1.0, -1.55), (min(s['W'] - 1, 6.0), -1.55)]:
                            self.click(*p_)
                        self.dbl(min(s['W'] - 1, 6.0), -0.1); self.esc(); self.select_tool()
                    self.do(f'{label}: κάγκελο μπαλκονιού «{s["railing"]}»', rail, 'more')
            if k == 0 and s['floors'] > 1:
                hall = next((c for c in C if c['role'] == 'σαλόνι'), C[0])
                L = min(3.6, hall['x1'] - hall['x0'] - 0.6)
                def stair(hall=hall, L=L):
                    self.menu('Κατασκευή', 'Σκάλα·Ράμπα', 'Σκάλα')
                    self.drag(hall['x0'] + 0.25, hall['y1'] - 0.7, hall['x0'] + 0.25 + L, hall['y1'] - 0.7)
                    self.esc(); self.select_tool()
                self.do('σκάλα στο σαλόνι (σύρσιμο)', stair, 'more', ('stair',))
            if 'deco' in s['order'][:2] or k == 0:
                self.interiors(C, k)
        self.do('επιλογή ισογείου', lambda: self.pick_floor(base))
        for part in s['order']:
            getattr(self, 'part_' + part)(all_cells)
        if s['roof'] == 'tiled':
            names = self.menu_items('Κατασκευή', 'Στέγη', 'Με κεραμίδια (ξύλινη στέγη)')
            if names:
                self.do('στέγη με κεραμίδια (αυτόματα)',
                        lambda: self.menu('Κατασκευή', 'Στέγη', 'Με κεραμίδια (ξύλινη στέγη)', names[0]), 'more')
            else:
                self.find('δεν βρέθηκε εντολή', 'Στέγη ▸ Με κεραμίδια: άδειο υπομενού')
        else:
            self.do('επίπεδη στέγη', lambda: self.menu('Κατασκευή', 'Στέγη', 'Χωρίς κεραμίδια (επίπεδη / δώμα)',
                                                       'Αυτόματη επίπεδη στέγη (μόνο όπου δεν υπάρχει όροφος από πάνω)'), 'more')
        if s['edits']:
            self.part_edits(all_cells)
        self.part_outputs()
        self.final_checks()
        self.total = time.perf_counter() - t0

    def part_structure(self, cells_):
        self.do('πρόταση φέροντος από τους τοίχους',
                lambda: self.menu('Κατασκευή', 'Φέρων οργανισμός', 'Πρόταση φέροντος οργανισμού από τους τοίχους'), 'more')
        self.do('υπολογισμός φέροντα',
                lambda: self.menu('Κατασκευή', 'Φέρων οργανισμός', 'Υπολογισμός φέροντα: κολόνες, δοκάρια, βάσεις'))
        self.do('αρίθμηση κολονών / δοκών',
                lambda: self.menu('Κατασκευή', 'Φέρων οργανισμός', 'Αρίθμηση κολονών / δοκών (Κ1, Δ1 …)'))
        self.do('δάπεδα (αυτόματα)', lambda: self.menu('Κατασκευή', 'Πλάκες', 'Δάπεδα (αυτόματα)'), 'more')

    def part_mep(self, cells_):
        self.do('θέρμανση: σώματα σε κάθε χώρο',
                lambda: self.menu('Εγκαταστάσεις', 'Θέρμανση', 'Σώματα σε κάθε χώρο (αυτόματα)'), 'more')
        self.do('ενδεικτική ισχύς θέρμανσης', lambda: self.menu('Εγκαταστάσεις', 'Θέρμανση', 'Ενδεικτική ισχύς θέρμανσης…'))
        C = cells_[0]
        self.place(('Εγκαταστάσεις', 'Ύδρευση', 'Παροχή κρύου νερού'), [(C[0]['x0'] + 0.2, 0.2)])
        self.place(('Εγκαταστάσεις', 'Ασθενή (δίκτυο·TV)', 'Πρίζα TV / SAT'), [(C[0]['x1'] - 0.15, C[0]['cy'])])
        self.do('ανάλυση ηλεκτρολογικών',
                lambda: self.menu('Εγκαταστάσεις', 'Ηλεκτρολογικά', 'Ανάλυση ηλεκτρολογικών — σχέδιο & κόστος…'))

    def part_deco(self, cells_):
        s = self.s
        self.place(('Διαμόρφωση', 'Περιβάλλων χώρος', 'Φυτό: Δέντρο'), [(-3, -3), (s['W'] + 3, -2)])
        self.place(('Διαμόρφωση', 'Περιβάλλων χώρος', 'Φυτό: Θάμνος'), [(-1.5, 2), (-1.5, 4)])
        if self.rng.random() < 0.5:
            def pool():
                self.menu('Διαμόρφωση', 'Περιβάλλων χώρος', 'Πισίνα'); self.drag(2, -8, 8, -4.5); self.esc(); self.select_tool()
            self.do('πισίνα (σύρσιμο)', pool, 'more')
        pg = self.menu_items('Διαμόρφωση', 'Περιβάλλων χώρος', 'Πέργκολα')
        if pg:
            def perg():
                self.menu('Διαμόρφωση', 'Περιβάλλων χώρος', 'Πέργκολα', pg[0]); self.drag(1, -0.1, 5, -3.5)
                self.esc(); self.select_tool()
            self.do(f'πέργκολα «{pg[0]}» (σύρσιμο)', perg, 'more')
        def material():
            self.select_tool(); self.dbl(s['W'] / 2, 0.0); self.menu('Διαμόρφωση', 'Υλικά', 'Υλικό στο επιλεγμένο…')
        self.do('υλικό σε εξωτερικό τοίχο', material)
        def obj():
            self.menu('Διαμόρφωση', 'Βιβλιοθήκη', 'Τοποθέτηση αντικειμένου…'); c = cells_[0][0]
            self.click(c['cx'], c['cy']); self.esc(); self.select_tool()
        self.do('αντικείμενο βιβλιοθήκης στο σαλόνι', obj)
        self.do('έδαφος', lambda: self.menu('Διαμόρφωση', 'Έδαφος', 'Δημιουργία εδάφους'), 'more')

    def part_outside(self, cells_):
        """Περιβάλλων χώρος: οικόπεδο, περίφραξη, μονοπάτι, πεζοδρόμιο, δρόμος, πισίνα με σχήμα, πέργκολες, φυτά."""
        s = self.s; W, D = s['W'], s['D']
        X0, Y0, X1, Y1 = -8, -10, W + 8, D + 6
        plot = [(X0, Y0), (X1, Y0), (X1, Y1), (X0, Y1)]
        def boundary():
            self.menu('Διαμόρφωση', 'Έδαφος', 'Οικόπεδο: σχεδίαση ορίων (κλικ στις κορυφές)')
            for p_ in plot:
                self.click(*p_)
            self.click(*plot[0]); self.esc(); self.select_tool()
        self.do('όρια οικοπέδου', boundary, 'more')
        def fence():
            self.menu('Κατασκευή', 'Κάγκελα', s['fence'])
            for p_ in plot[1:] + [plot[0]]:
                self.click(p_[0] - 0.3 if p_[0] > 0 else p_[0] + 0.3, p_[1] - 0.3 if p_[1] > 0 else p_[1] + 0.3)
            self.dbl(X0 + 0.3, Y0 + 0.3); self.esc(); self.select_tool()
        self.do(f'περίφραξη «{s["fence"]}»', fence, 'more')
        for name, pts in (('Μονοπάτι', [(W / 2, -0.3), (W / 2, -4), (W / 2 + 3, -8)]),
                          ('Πεζοδρόμιο', [(X0, Y0 - 1.5), (X1, Y0 - 1.5)]),
                          ('Δρόμος', [(X0 - 5, Y0 - 6), (X1 + 5, Y0 - 6)])):
            def run(name=name, pts=pts):
                self.menu('Διαμόρφωση', 'Περιβάλλων χώρος', name)
                for p_ in pts[:-1]:
                    self.click(*p_)
                self.dbl(*pts[-1]); self.esc(); self.select_tool()
            self.do(f'{name.lower()} (κλικ, διπλό κλικ στο τέλος)', run, 'more')
        if s['pool']:
            def pool():
                self.menu('Διαμόρφωση', 'Περιβάλλων χώρος', 'Πισίνα με σχεδίαση σχήματος (γωνίες, καμπύλες)')
                for p_ in [(W + 2, 1), (W + 6, 1), (W + 6, 5), (W + 2, 5)]:
                    self.click(*p_)
                self.click(W + 2, 1); self.key('Return'); self.esc(); self.select_tool()
            self.do('πισίνα με σχήμα', pool, 'more')
        pg = self.menu_items('Διαμόρφωση', 'Περιβάλλων χώρος', 'Πέργκολα')
        for name in self.rng.sample(pg, min(2, len(pg))):
            def perg(name=name):
                self.menu('Διαμόρφωση', 'Περιβάλλων χώρος', 'Πέργκολα', name)
                x = self.rng.uniform(-6, W - 3)
                self.drag(x, Y1 - 4.5, x + 3, Y1 - 1.5); self.esc(); self.select_tool()
            self.do(f'πέργκολα «{name}» στον κήπο', perg, 'more')
        trees = [(self.rng.uniform(X0 + 1, X1 - 1), self.rng.uniform(Y1 - 3, Y1 - 0.5)) for _ in range(self.rng.randint(3, 8))]
        self.place(('Διαμόρφωση', 'Περιβάλλων χώρος', 'Φυτό: Δέντρο'), trees)

    def part_materials(self, cells_):
        """Διαφορετικά υλικά: ο χρήστης διαλέγει πλευρά, κατηγορία και υλικό στον διάλογο, σε τοίχους και πλάκες."""
        s = self.s; C = cells_[0]
        spots = [(s['W'] / 2, 0.0, 'εξωτερικός τοίχος νότια'), (0.0, s['D'] / 2, 'εξωτερικός τοίχος δυτικά')]
        spots += [(x, s['D'] * 0.2, 'εσωτερικός τοίχος') for x in s['xs']]
        spots += [(c['cx'], c['cy'], f'δάπεδο / χώρος ({c["role"]})') for c in C]
        for x, y, what in self.rng.sample(spots, min(s['n_materials'], len(spots))):
            def mat(x=x, y=y):
                self.select_tool(); self.dbl(x, y)
                self.choose_in_dialogs = True
                try:
                    self.menu('Διαμόρφωση', 'Υλικά', 'Υλικό στο επιλεγμένο…')
                finally:
                    self.choose_in_dialogs = False
                self.esc()
            self.do(f'υλικό: {what}', mat)
        for c in self.rng.sample(C, min(s['n_furniture'], len(C))):
            def furn(c=c):
                self.choose_in_dialogs = True
                try:
                    self.menu('Διαμόρφωση', 'Βιβλιοθήκη', 'Τοποθέτηση αντικειμένου…')
                finally:
                    self.choose_in_dialogs = False
                self.click(c['cx'] + 0.3, c['cy'] + 0.2); self.esc(); self.select_tool()
            self.do(f'αντικείμενο βιβλιοθήκης ({c["role"]})', furn, 'more')

    def part_cad(self, cells_):
        s = self.s
        self.do('διαστάσεις εξωτερικές', lambda: self.menu('Σχέδια', 'Διαστάσεις', 'Αυτόματες διαστάσεις: εξωτερικές'))
        self.do('διαστάσεις εσωτερικές',
                lambda: self.menu('Σχέδια', 'Διαστάσεις', 'Αυτόματες διαστάσεις: εσωτερικές (καθαρά χώρων)'))
        def tape():
            self.menu('Σχέδια', 'Διαστάσεις', 'Μεζούρα (μέτρηση με 2 κλικ)')
            for p in [(0.15, s['D'] / 3), (s['W'] - 0.15, s['D'] / 3), (s['W'] / 2, s['D'] / 3 + 0.5)]:
                self.click(*p)
            self.esc(); self.select_tool()
        self.do('μεζούρα', tape, 'more', ('dimension',))
        def line():
            self.menu('Σχέδια', 'Σχεδίαση 2D', 'Γραμμή'); self.click(-2, -1); self.dbl(-2, s['D'] + 1); self.esc()
            self.select_tool()
        self.do('γραμμή 2D', line, 'more', ('drafting',))
        def text():
            self.answers.append('ΚΑΤΟΨΗ ΙΣΟΓΕΙΟΥ'); self.menu('Σχέδια', 'Σχεδίαση 2D', 'Κείμενο'); self.click(s['W'] / 2, -2)
            self.answers.clear(); self.esc(); self.select_tool()
        self.do('κείμενο 2D', text, 'more', ('drafting',))
        def section():
            self.menu('Σχέδια', 'Τομές', 'Τομή (σύρε γραμμή στην κάτοψη)'); self.drag(-1, s['D'] / 2, s['W'] + 1, s['D'] / 2)
            self.esc(); self.select_tool()
        self.do('τομή (σύρσιμο)', section, 'more')

    def part_edits(self, cells_):
        s = self.s; rng = self.rng
        def move_door():
            self.select_tool()
            doors = [(c['x0'], c['cy']) for c in cells_[0] if c['x0'] > 0]
            if not doors:
                return
            x, y = doors[0]; self.dbl(x, y); self.key('Delete')
        self.do('διαγραφή μιας εσωτερικής πόρτας (κλικ + Delete)', move_door)
        def undo_redo():
            for _ in range(rng.randint(2, 6)):
                self.menu('Επεξεργασία', 'Αναίρεση')
            for _ in range(rng.randint(1, 6)):
                self.menu('Επεξεργασία', 'Επανάληψη')
        self.do('μερικές αναιρέσεις / επαναλήψεις', undo_redo)
        def move_wall():
            if not s['xs']:
                return
            x = s['xs'][0]
            self.select_tool(); self.dbl(x, s['D'] * 0.3); self.menu('Επεξεργασία', 'Μετακίνηση')
            self.click(x, s['D'] * 0.3); self.click(x + 0.3, s['D'] * 0.3); self.esc(); self.select_tool()
        self.do('μετακίνηση εσωτερικού τοίχου 30 cm', move_wall)
        def room_dims():
            self.menu('Επεξεργασία', 'Διαστάσεις δωματίου… (κλικ μέσα του)'); c = cells_[0][-1]
            self.click(c['cx'], c['cy']); self.esc(); self.select_tool()
        self.do('διαστάσεις δωματίου', room_dims)

    def part_outputs(self):
        self.do('λίστες', lambda: self.menu('Σχέδια', 'Λίστες', 'Λίστες (κουφώματα · κέλυφος · χώροι · κυκλώματα)'))
        self.do('έλεγχος συγκρούσεων',
                lambda: self.menu('Σχέδια', 'Έλεγχος συγκρούσεων', 'Έλεγχος συγκρούσεων (Η/Μ · φέρων · κουφώματα · έπιπλα)'))
        self.do('ήλιος και άνεμος', lambda: self.menu('Σχέδια', 'Ήλιος και άνεμος',
                                                     'Ήλιος και άνεμος (ηλιασμός κουφωμάτων, άνεμος περιοχής, μπαλκόνια)…'))
        self.do('θερμομονώσεις', lambda: self.menu('Έργο', 'Αρχείο', 'Θερμομονώσεις (θερμική εικόνα όψης, σήμερα / πρόταση)'))
        self.do('έλεγχος ποιότητας', lambda: self.menu('Σχέδια', 'Έλεγχος', 'Έλεγχος ποιότητας'))
        self.do('επιμέτρηση εργασιών', lambda: self.menu('Σχέδια', 'Επιμετρήσεις·τιμές', 'Επιμέτρηση εργασιών (ανά χώρο)…'))
        self.do('τιμές & προσφορά', lambda: self.menu('Σχέδια', 'Επιμετρήσεις·τιμές', 'Τιμές & προσφορά…'))
        for name, path, ext in (('PDF', ('Σχέδια', 'Εκτύπωση·PDF', 'Εξαγωγή PDF (κατόψεις, επιμέτρηση, προσφορά)…'), '.pdf'),
                                ('IFC', ('Σχέδια', 'Εξαγωγή', 'IFC για μηχανικούς (BIM)…'), '.ifc'),
                                ('DXF', ('Σχέδια', 'Εξαγωγή', 'DXF κατόψεις ανά όροφο…'), '.dxf')):
            t_start = time.time() - 1
            self.do(f'εξαγωγή {name}', lambda path=path: self.menu(*path))
            new = [f for f in os.listdir(self.dir) if f.lower().endswith(ext)
                   and os.path.getmtime(os.path.join(self.dir, f)) >= t_start]
            if not new:
                self.find('δεν βγήκε αρχείο', f'εξαγωγή {name}: κανένα {ext}')
            elif any(os.path.getsize(os.path.join(self.dir, f)) == 0 for f in new):
                self.find('δεν βγήκε αρχείο', f'εξαγωγή {name}: άδειο αρχείο')
        self.do('φύλλα σχεδίων', lambda: self.menu('Σχέδια', 'Φύλλα σχεδίων', 'Φύλλα σχεδίων (A4–A0: κατόψεις, τομές, λίστες, πινακίδα)…'))

    # -- the auditor ---------------------------------------------------------------------------------
    def orphans(self):
        ents = self.w.doc.entities
        for e in list(ents.values()):
            if e.parent_id and e.parent_id not in ents:
                self.find('ορφανό στοιχείο', f'{e.kind} με γονέα που δεν υπάρχει', f'{e.id} → {e.parent_id}')

    def kind_counts(self):
        out = {}
        for e in self.w.doc.entities.values():
            out[e.kind] = out.get(e.kind, 0) + 1
        return out

    def snapshot(self):
        return {e.id: (e.kind, json.dumps(e.params, sort_keys=True, default=str)) for e in self.w.doc.entities.values()}

    def final_checks(self):
        from archforge.core.model import validate_params
        self.step = 'έλεγχος: έγκυρα στοιχεία'
        for e in list(self.w.doc.entities.values()):
            try:
                validate_params(e.kind, e.params)
            except Exception as exc:                                     # noqa: BLE001
                self.find('μη έγκυρο στοιχείο', f'{e.kind}: {exc}')
        self.orphans()
        snap = self.snapshot(); kinds = {}
        for k, _ in snap.values():
            kinds[k] = kinds.get(k, 0) + 1
        self.kinds = kinds
        path = os.path.join(self.dir, 'ergo.archforge')
        if os.path.exists(path):
            os.remove(path)
        self.do('αποθήκευση (Έργο ▸ Αρχείο ▸ Αποθήκευση)', lambda: self.menu('Έργο', 'Αρχείο', 'Αποθήκευση'))
        if not os.path.exists(path):
            self.find('αποθήκευση', 'δεν γράφτηκε αρχείο έργου', str(os.listdir(self.dir)))
            return
        self.do('νέο έργο', lambda: self.menu('Έργο', 'Αρχείο', 'Νέο έργο'))
        if self.count():
            self.find('νέο έργο', f'το νέο έργο έχει {self.count()} στοιχεία')
        self.open_queue.append(path)
        self.do('άνοιγμα του αρχείου', lambda: self.menu('Έργο', 'Αρχείο', 'Άνοιγμα έργου…'))
        self.step = 'έλεγχος: αποθήκευση → άνοιγμα'
        again = self.snapshot()
        if set(again) != set(snap):
            self.find('αποθήκευση ≠ άνοιγμα', f'{len(snap)} στοιχεία πριν, {len(again)} μετά',
                      f'λείπουν {sorted({snap[i][0] for i in set(snap) - set(again)})}, '
                      f'νέα {sorted({again[i][0] for i in set(again) - set(snap)})}')
        else:
            diff = [i for i in snap if snap[i] != again[i]]
            if diff:
                self.find('αποθήκευση ≠ άνοιγμα', f'{len(diff)} στοιχεία άλλαξαν παραμέτρους',
                          f'είδη: {sorted({snap[i][0] for i in diff})}')
        # Αναίρεση όλων στο αρχικό έργο ξανά: ανοίγουμε, χτίζουμε δεν ξαναγίνεται — ελέγχουμε στο ανοιγμένο:
        # μία αλλαγή + αναίρεση πρέπει να το αφήσει ίδιο.
        self.step = 'έλεγχος: αλλαγή + αναίρεση'
        s = self.s
        def change():
            self.wall((-4, -4), (-4, -1))
        self.do('ένας τοίχος έξω από το κτίριο', change, 'more', ('wall',))
        self.do('αναίρεση (μενού)', lambda: self.menu('Επεξεργασία', 'Αναίρεση'))
        if self.snapshot() != again:
            self.find('αναίρεση', 'μετά από έναν τοίχο και μία αναίρεση το έργο δεν είναι ίδιο')

    def report(self):
        return dict(seed=self.seed, scenario=self.s, findings=self.findings, steps=self.steps,
                    windows=self.windows_seen[-200:], status=[x for x in self.status_log if not x[1].startswith("X ")][-400:], kinds=getattr(self, 'kinds', {}),
                    seconds=round(getattr(self, 'total', 0), 1))


def undo_all_check(bot):
    """Αναίρεση όλων ως την αρχή και επανάληψη όλων (Επεξεργασία ▸ Αναίρεση / Επανάληψη) σε ένα χτισμένο έργο."""
    full = bot.snapshot(); n = 0
    bot.step = 'έλεγχος: αναίρεση όλων'
    act_u = None
    slow = 0.0
    while n < 3000:
        t = time.perf_counter()
        try:
            bot.menu('Επεξεργασία', 'Αναίρεση')       # γκρίζο στο μενού = τέλος (όπως το βλέπει ο χρήστης)
        except LookupError:
            break
        n += 1; slow = max(slow, time.perf_counter() - t)
    left = bot.count()
    if left:
        kinds = sorted({e.kind for e in bot.w.doc.entities.values()})
        if set(kinds) - {'project_brief', 'level', 'design_climate', 'site', 'terrain'}:
            bot.find('αναίρεση όλων', f'μετά από {n} αναιρέσεις έμειναν {left} στοιχεία', str(kinds))
    bot.step = 'έλεγχος: επανάληψη όλων'
    m = 0
    while m < 3000:
        t = time.perf_counter()
        try:
            bot.menu('Επεξεργασία', 'Επανάληψη')
        except LookupError:
            break
        m += 1; slow = max(slow, time.perf_counter() - t)
    if bot.w.stack.can_undo is False or bot.w.stack.can_redo:
        bot.find('αναίρεση όλων', 'η κατάσταση του μενού Αναίρεση / Επανάληψη δεν συμφωνεί με το έργο')
    if slow > 3:
        bot.find('αργό', f'μία αναίρεση / επανάληψη πήρε έως {slow:.0f} s')
    back = bot.snapshot()
    if set(back) != set(full):
        kf = {}; kb = {}
        for k, _ in full.values(): kf[k] = kf.get(k, 0) + 1
        for k, _ in back.values(): kb[k] = kb.get(k, 0) + 1
        if kf != kb:
            bot.find('επανάληψη όλων', f'μετά από {m} επαναλήψεις δεν ξαναβγήκε το ίδιο έργο',
                     str({k: (kf.get(k, 0), kb.get(k, 0)) for k in set(kf) | set(kb) if kf.get(k, 0) != kb.get(k, 0)}))
        else:
            changed = sorted({full[i][0] for i in set(full) - set(back)})
            bot.find('επανάληψη: νέα αναγνωριστικά', f'ίδια στοιχεία, άλλα ids ({len(set(full) - set(back))})', str(changed))
    else:
        diff = [i for i in full if full[i] != back[i]]
        if diff:
            bot.find('επανάληψη όλων', f'{len(diff)} στοιχεία με άλλες παραμέτρους', str(sorted({full[i][0] for i in diff})))
    bot.orphans()
    return n, m


def run_one(seed, verbose=False):
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen'); os.environ.setdefault('QTWEBENGINE_DISABLE_SANDBOX', '1')
    os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--no-sandbox')
    sys.path.insert(0, ROOT)
    bot = Bot(seed, verbose)
    try:
        if verbose:
            print('σενάριο:', json.dumps(bot.s, ensure_ascii=False))
        original_final = bot.final_checks

        def final_with_undo():
            try:
                undo_all_check(bot)
            except Exception as exc:                                     # noqa: BLE001
                bot.find('εξαίρεση', f'αναίρεση όλων: {exc}', traceback.format_exc()[-2000:])
            original_final()
        bot.final_checks = final_with_undo
        bot.run()
    except Exception as exc:                                             # noqa: BLE001
        bot.find('διακοπή bot', f'{type(exc).__name__}: {exc}', traceback.format_exc()[-2500:])
    rep = bot.report()
    with open(os.path.join(OUT, f'bot_{seed}.json'), 'w', encoding='utf-8') as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    try:
        bot.w._mark_clean()
    except Exception:                                                    # noqa: BLE001
        pass
    os._exit(0)                                                          # no Qt teardown questions


# ----------------------------------------------------------------------------------------------- fleet
def norm(text):
    t = re.sub(r'\d+([.,]\d+)?', '#', text)
    t = re.sub(r"0x[0-9a-f]+|'[0-9a-f]{8,}'|[0-9a-f]{12,}", '…', t)
    return t[:220]


def fleet(n, jobs, start=1, timeout=1500):
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QTWEBENGINE_DISABLE_SANDBOX='1',
               QTWEBENGINE_CHROMIUM_FLAGS='--no-sandbox')
    seeds = list(range(start, start + n)); running = {}; done = {}
    t0 = time.time()
    while seeds or running:
        while seeds and len(running) < jobs:
            sd = seeds.pop(0)
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), 'one', '--seed', str(sd), '--quiet'],
                                 cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=open(os.path.join(OUT, f'bot_{sd}.err'), 'w'))
            running[sd] = (p, time.time())
        for sd, (p, ts) in list(running.items()):
            rc = p.poll()
            if rc is None and time.time() - ts > timeout:
                p.kill(); rc = 'timeout'
            if rc is not None:
                done[sd] = rc; del running[sd]
                print(f'bot {sd:3d}: {rc}  ({len(done)}/{n}, {time.time() - t0:.0f} s)', flush=True)
        time.sleep(1)
    aggregate(sorted(done), done)


def aggregate(seeds, codes=None):
    reports = []
    for sd in seeds:
        p = os.path.join(OUT, f'bot_{sd}.json')
        if os.path.exists(p):
            reports.append(json.load(open(p, encoding='utf-8')))
        else:
            err = open(os.path.join(OUT, f'bot_{sd}.err'), encoding='utf-8', errors='replace').read()[-1500:] \
                if os.path.exists(os.path.join(OUT, f'bot_{sd}.err')) else ''
            why = 'κόλλησε (χρονικό όριο)' if codes and codes.get(sd) == 'timeout' else 'κατέρρευσε'
            reports.append(dict(seed=sd, scenario=scenario(sd), steps=[], kinds={}, seconds=0,
                                findings=[dict(kind='κατάρρευση / κόλλημα', step=';', text=why, detail=err)]))
    groups = {}
    for r in reports:
        for f in r['findings']:
            key = (f['kind'], norm(f['text']))
            g = groups.setdefault(key, dict(kind=f['kind'], text=f['text'], bots=set(), steps=set(), detail=f['detail'],
                                            first=r['seed']))
            g['bots'].add(r['seed']); g['steps'].add(norm(f['step']))
    order = ['κατάρρευση / κόλλημα', 'διακοπή bot', 'εξαίρεση', 'μη έγκυρο στοιχείο', 'αποθήκευση ≠ άνοιγμα',
             'ορφανό στοιχείο', 'αναίρεση όλων', 'επανάληψη όλων', 'επανάληψη: νέα αναγνωριστικά', 'αναίρεση', 'αποθήκευση', 'νέο έργο', 'δεν βγήκε αρχείο',
             'μήνυμα σφάλματος', 'αγγλικό μήνυμα στον χρήστη', 'δεν βρέθηκε εντολή', 'δεν έγινε τίποτα', 'αργό', 'προειδοποίηση Qt',
             'προειδοποίηση χρήστη']
    gl = sorted(groups.values(), key=lambda g: (order.index(g['kind']) if g['kind'] in order else 99, -len(g['bots'])))
    clean = sum(1 for r in reports if not r['findings'])
    steps = sum(len(r['steps']) for r in reports)
    ents = sum(sum(r.get('kinds', {}).values()) for r in reports)
    kinds = {}
    for r in reports:
        kinds[r['scenario']['kind']] = kinds.get(r['scenario']['kind'], 0) + 1
    L = ['# Αναφορά 100 bot χρηστών', '',
         f'Bot: **{len(reports)}** · βήματα: **{steps}** · στοιχεία που έφτιαξαν: **{ents}** · '
         f'χωρίς κανένα εύρημα: **{clean}** · ομάδες ευρημάτων: **{len(gl)}**', '',
         'Κτίρια: ' + ' · '.join(f'{k} {v}' for k, v in sorted(kinds.items())), '',
         'Κάθε bot ενεργεί μόνο όπως άνθρωπος (μενού, κουμπιά, κλικ / σύρσιμο / δεξί κλικ στην κάτοψη, πλήκτρα, το «OK» '
         'των διαλόγων). Ο ελεγκτής κοιτάζει το έργο: έγκυρα στοιχεία, αποθήκευση → άνοιγμα ίδιο, αναίρεση όλων → άδειο, '
         'επανάληψη όλων → ίδιο, αρχεία εξαγωγής. Εργαλείο: `scripts/user_drive/bots.py`.', '',
         '| # | Είδος | Bot | Εύρημα | Πού (βήμα) | Πρώτο bot |', '|---|---|---|---|---|---|']
    for i, g in enumerate(gl, 1):
        txt = g['text'].replace('|', '/').replace('\n', ' ')[:160]
        st = '; '.join(sorted(g['steps']))[:120].replace('|', '/')
        L.append(f'| {i} | {g["kind"]} | {len(g["bots"])} | {txt} | {st} | {g["first"]} |')
    L += ['', '## Λεπτομέρειες (εξαιρέσεις / καταρρεύσεις)', '']
    for i, g in enumerate(gl, 1):
        if g['detail'] and g['kind'] in ('εξαίρεση', 'διακοπή bot', 'κατάρρευση / κόλλημα', 'μη έγκυρο στοιχείο',
                                         'αποθήκευση ≠ άνοιγμα', 'αναίρεση όλων', 'επανάληψη όλων'):
            L += [f'### {i}. {g["text"][:120]}', '', '```', g['detail'][-1800:], '```', '']
    with open(REPORT, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(L) + '\n')
    print(f'αναφορά: {REPORT} — {len(gl)} ομάδες, {clean}/{len(reports)} καθαρά bot')


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['one', 'fleet', 'report'])
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--n', type=int, default=100)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--start', type=int, default=1)
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()
    if a.mode == 'one':
        run_one(a.seed, verbose=not a.quiet)
    elif a.mode == 'fleet':
        fleet(a.n, a.jobs, a.start)
    else:
        aggregate(list(range(a.start, a.start + a.n)))
