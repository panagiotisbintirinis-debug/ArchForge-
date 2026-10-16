"""Σύνδεση της αυτόματης αποθήκευσης με το κύριο παράθυρο (Qt).

Χρήση στο ``MainWindow.__init__`` (στο τέλος, όταν υπάρχουν ``doc``/``statusBar``)::

    from .autosave_glue import install_autosave, offer_recovery
    install_autosave(self)
    QTimer.singleShot(0, lambda: offer_recovery(self))

Η αυτόματη αποθήκευση δεν πρέπει ποτέ να ρίξει την εφαρμογή: κάθε σφάλμα
καταγράφεται και εμφανίζεται στη γραμμή κατάστασης.
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
import weakref
from typing import List, Optional

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication, QMessageBox

from archforge.project import autosave as _autosave
from archforge.project.autosave import AutoSaver, Recoverable

log = logging.getLogger(__name__)

DEFAULT_INTERVAL_MS = 60_000


def _status(window, text: str, timeout: int = 5000) -> None:
    try:
        bar = window.statusBar() if hasattr(window, 'statusBar') else None
        if bar is not None:
            bar.showMessage(text, timeout)
    except Exception:
        pass


def _resolve_directory(directory):
    if directory is not None:
        return directory
    if os.environ.get(_autosave.ENV_DIR):
        return None
    # Σε δοκιμές (offscreen) δεν γεμίζουμε τον φάκελο του χρήστη.
    try:
        if QGuiApplication.platformName() == 'offscreen':
            return tempfile.mkdtemp(prefix='archforge-autosave-')
    except Exception:
        pass
    return None


class _CloseWatcher(QObject):
    """Μετά από αποδεκτό κλείσιμο του παραθύρου σβήνει τα αρχεία της συνεδρίας."""

    def __init__(self, window):
        super().__init__(window)
        self._window = window

    def eventFilter(self, obj, event):
        if obj is self._window and event.type() == QEvent.Type.Close:
            # Το closeEvent του παραθύρου μπορεί να ακυρώσει το κλείσιμο
            # («Άκυρο» στις μη αποθηκευμένες αλλαγές)· ελέγχουμε μετά.
            QTimer.singleShot(0, self._after_close)
        return False

    def _after_close(self):
        try:
            if not self._window.isVisible():
                finish_autosave(self._window)
        except RuntimeError:
            pass  # το παράθυρο έχει ήδη καταστραφεί


def install_autosave(window, interval_ms: int = DEFAULT_INTERVAL_MS, directory=None,
                     keep: int = _autosave.DEFAULT_KEEP) -> AutoSaver:
    """Ξεκινά περιοδική αυτόματη αποθήκευση του ``window.doc``."""
    existing = getattr(window, '_autosaver', None)
    if existing is not None:
        return existing
    saver = AutoSaver(directory=_resolve_directory(directory), keep=keep)
    window._autosaver = saver
    window._autosave_finished = False
    timer = QTimer(window)
    timer.setInterval(int(interval_ms))
    ref = weakref.ref(window)
    timer.timeout.connect(lambda: (lambda w: w is not None and autosave_now(w))(ref()))
    timer.start()
    window._autosave_timer = timer
    watcher = _CloseWatcher(window)
    window.installEventFilter(watcher)
    window._autosave_close_watcher = watcher
    app = QApplication.instance()
    if app is not None:
        # Αδύναμη αναφορά: η σύνδεση δεν κρατά ζωντανό το παράθυρο.

        def _on_quit():
            target = ref()
            if target is not None:
                finish_autosave(target)

        app.aboutToQuit.connect(_on_quit)
        window._autosave_quit_slot = _on_quit
    return saver


def autosave_now(window, force: bool = False) -> bool:
    """Μία αυτόματη αποθήκευση (αν άλλαξε κάτι). Δεν πετά ποτέ εξαίρεση."""
    saver: Optional[AutoSaver] = getattr(window, '_autosaver', None)
    if saver is None or getattr(window, '_autosave_finished', False):
        return False
    try:
        wrote = saver.autosave(window.doc, getattr(window, 'current_path', None), force=force)
        if not wrote:
            saver.heartbeat()
        return wrote
    except Exception as exc:
        log.exception('Η αυτόματη αποθήκευση απέτυχε')
        _status(window, f'Η αυτόματη αποθήκευση απέτυχε: {exc}', 8000)
        return False


def finish_autosave(window) -> None:
    """Κανονικό κλείσιμο: σταματά τον χρονοδιακόπτη και σβήνει τα αρχεία της συνεδρίας."""
    if getattr(window, '_autosave_finished', True):
        return
    window._autosave_finished = True
    try:
        timer = getattr(window, '_autosave_timer', None)
        if timer is not None:
            timer.stop()
    except RuntimeError:
        pass
    try:
        window._autosaver.finish()
    except Exception:
        log.exception('Αποτυχία καθαρισμού αυτόματης αποθήκευσης')


def _describe(item: Recoverable) -> str:
    when = time.strftime('%d/%m/%Y %H:%M', time.localtime(item.timestamp))
    name = os.path.basename(item.original_path) if item.original_path else 'έργο χωρίς όνομα'
    return f'{when} — {name}'


def restore_into_window(window, item: Recoverable) -> bool:
    """Φορτώνει την αυτόματη αποθήκευση στο παράθυρο όπως το «Άνοιγμα» (``_replace_project``).

    Το έργο μένει «μη αποθηκευμένο»: η κατάσταση αναφοράς γίνεται το αρχείο στον
    δίσκο (ή κενό έργο), ώστε το κλείσιμο να ρωτήσει για αποθήκευση.
    """
    from archforge.core.model import Document
    doc = _autosave.recover(item)
    original = item.original_path if item.original_path and os.path.exists(item.original_path) else None
    window._replace_project(doc, original)
    try:
        clean = Document.load(original).to_dict() if original else Document().to_dict()
    except Exception:
        clean = {}
    window._clean_state = clean
    # Το ανακτημένο έργο γράφεται αμέσως ως αυτόματη αποθήκευση αυτής της συνεδρίας,
    # πριν σβηστεί η παλιά: δεν υπάρχει στιγμή χωρίς αντίγραφο.
    if getattr(window, '_autosaver', None) is not None:
        autosave_now(window, force=True)
    _autosave.discard(item)
    _status(window, f'Επαναφέρθηκε η αυτόματη αποθήκευση ({item.entity_count} στοιχεία)', 6000)
    return True


def offer_recovery(window, directory=None) -> List[Recoverable]:
    """Στην εκκίνηση: αν υπάρχουν αυτόματες αποθηκεύσεις από κατάρρευση, ρωτά τον χρήστη.

    Με ``window._no_modal_dialogs`` (δοκιμές) δεν ανοίγει διάλογο· επιστρέφει τη λίστα.
    """
    saver = getattr(window, '_autosaver', None)
    if directory is None and saver is not None:
        directory = saver.directory
    try:
        items = _autosave.find_recoverable(directory, exclude_session=getattr(saver, 'session_id', None))
    except Exception:
        log.exception('Αποτυχία αναζήτησης αυτόματων αποθηκεύσεων')
        return []
    if not items or getattr(window, '_no_modal_dialogs', False):
        return items
    for item in list(items):
        box = QMessageBox(window)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle('Επαναφορά εργασίας')
        box.setText(
            f'Βρέθηκε αυτόματη αποθήκευση από {_describe(item)} ({item.entity_count} στοιχεία).\n'
            'Το πρόγραμμα δεν είχε κλείσει κανονικά. Επαναφορά;'
        )
        restore = box.addButton('Επαναφορά', QMessageBox.ButtonRole.AcceptRole)
        reject = box.addButton('Απόρριψη', QMessageBox.ButtonRole.DestructiveRole)
        later = box.addButton('Αργότερα', QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(restore)
        box.setEscapeButton(later)
        box.exec()
        clicked = box.clickedButton()
        if clicked is restore:
            try:
                restore_into_window(window, item)
            except Exception as exc:
                log.exception('Αποτυχία επαναφοράς')
                QMessageBox.warning(window, 'Επαναφορά', f'Η επαναφορά απέτυχε: {exc}')
                continue
            break  # ένα έργο τη φορά· τα υπόλοιπα θα προταθούν στην επόμενη εκκίνηση
        if clicked is reject:
            try:
                _autosave.discard(item)
            except Exception:
                log.exception('Αποτυχία απόρριψης')
            continue
        break  # Αργότερα
    return items
