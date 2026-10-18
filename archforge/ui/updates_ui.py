"""Αρχείο ▸ Έλεγχος για ενημερώσεις… and the quiet check when the packaged program starts (archforge/updates.py)."""
from __future__ import annotations

import os
import threading

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from archforge import updates


class _Relay(QObject):
    found = Signal(object, bool)      # release (or None), asked by the human


def install(window):
    relay = _Relay(window)
    relay.found.connect(lambda rel, asked: _answer(window, rel, asked))
    window._update_relay = relay
    action = QAction("Έλεγχος για ενημερώσεις…", window)
    action.triggered.connect(lambda: check(window, asked=True))
    window.check_updates_action = action
    if updates.packaged():
        QTimer.singleShot(4000, lambda: check(window, asked=False))
    return action


def check(window, asked):
    """Ask GitHub in the background (the window never waits on the network)."""
    if not updates.packaged():
        if asked:
            QMessageBox.information(window, "Ενημερώσεις",
                                    "Το πρόγραμμα τρέχει από τον κώδικα (όχι από το πακέτο): ενημερώνεται με git pull.")
        return
    relay = window._update_relay
    threading.Thread(target=lambda: relay.found.emit(updates.available_update(), asked), daemon=True).start()


def _answer(window, rel, asked):
    if rel is None:
        if asked:
            build = updates.current_build() or {}
            QMessageBox.information(window, "Ενημερώσεις",
                                    f"Έχεις την τελευταία έκδοση ({build.get('sha', '')[:7]}).")
        return
    size = f" · {rel['size'] / 1048576:.0f} MB" if rel["size"] else ""
    reply = QMessageBox.question(
        window, "Νέα έκδοση ArchForge",
        f"Υπάρχει νέα έκδοση ({rel['sha'][:7]}{size}).\n\nΕνημέρωση τώρα; Το πρόγραμμα θα κλείσει και θα ξανανοίξει "
        "μόνο του — τα έργα σου και η βιβλιοθήκη σου μένουν όπως είναι.")
    if reply != QMessageBox.StandardButton.Yes:
        return
    dialog = QProgressDialog("Κατέβασμα νέας έκδοσης…", "Ακύρωση", 0, 100, window)
    dialog.setWindowTitle("Ενημέρωση")
    dialog.setMinimumDuration(0)

    def progress(done, total):
        dialog.setValue(int(done * 100 / total) if total else 0)
        QApplication.processEvents()
        return not dialog.wasCanceled()
    try:
        new_dir = updates.download(rel["url"], progress)
    except InterruptedError:
        return
    except Exception as exc:
        dialog.close()
        QMessageBox.warning(window, "Ενημέρωση", f"Η ενημέρωση δεν κατέβηκε:\n{exc}")
        return
    dialog.close()
    window.close()                        # asks about unsaved work; «Άκυρο» keeps the program open
    if window.isVisible():
        return
    updates.run_install_script(updates.install_script(new_dir, updates.program_dir(), os.getpid()))
    QApplication.instance().quit()
