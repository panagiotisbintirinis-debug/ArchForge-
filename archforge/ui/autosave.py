"""Autosave and crash recovery for the main window.

Every few minutes (default 3) and after every few committed commands (default
20) a snapshot of the Document (``to_dict()``) is written to this session's
recovery file in the user data folder — never over the user's project.  The
snapshot is taken on the UI thread (the Document is not shared between
threads); writing it runs on a background thread so a large project does not
freeze the mouse.  Autosave only reads the Document: the undo stack, the
"clean" baseline and the file the user saved are untouched.

The recovery file is removed after a normal save, a project switch and a
normal close.  A file left behind means the program did not close normally:
on the next start ``offer_recovery`` asks, in Greek, whether to recover it.
A lock file next to it (QLockFile) tells a crashed session's file from the
one a second running ArchForge window is still writing.
"""
from __future__ import annotations

import copy
import json
import os
import threading
import time

from PySide6.QtCore import QLockFile, QObject, QTimer

from archforge.project import persistence

DEFAULT_MINUTES = 3
DEFAULT_COMMANDS = 20


def _settings_path():
    from archforge.library.assets import data_dir
    return os.path.join(os.fspath(data_dir()), 'settings.json')


def load_settings():
    try:
        with open(_settings_path(), encoding='utf8') as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_settings(changes):
    data = load_settings()
    data.update(changes)
    persistence.atomic_write_json(_settings_path(), data)


class Autosave(QObject):
    def __init__(self, window, enabled=True, minutes=None, every_commands=None):
        super().__init__(window)
        self.window = window
        settings = load_settings()
        self.minutes = float(settings.get('autosave_minutes', DEFAULT_MINUTES) if minutes is None else minutes)
        self.every_commands = int(settings.get('autosave_commands', DEFAULT_COMMANDS)
                                  if every_commands is None else every_commands)
        self.enabled = bool(enabled)
        self.path = None                 # this session's recovery file (created on the first write)
        self._lock = None
        self._thread = None
        self._changes = 0                # committed commands since the last snapshot
        self._last_written = None        # the snapshot on disk (skip identical rewrites)
        self.last_saved_at = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.save_now)
        self._apply_interval()

    # ------------------------------------------------------------ settings
    def _apply_interval(self):
        self.timer.stop()
        if self.enabled and self.minutes > 0:
            self.timer.start(int(self.minutes * 60_000))

    def set_minutes(self, minutes, persist=True):
        self.minutes = max(0.0, float(minutes))
        if persist:
            save_settings({'autosave_minutes': self.minutes})
        self._apply_interval()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self._apply_interval()

    # --------------------------------------------------------------- write
    def note_change(self):
        """A command was committed (stack listener): count toward the every-X-commands save."""
        if not self.enabled:
            return
        self._changes += 1
        if self.every_commands > 0 and self._changes >= self.every_commands:
            # After the command has finished and the views redrew, not inside it.
            QTimer.singleShot(0, self.save_now)

    def _snapshot(self):
        data = self.window.doc.to_dict()
        # to_dict shares these with the live Document; the writer thread needs its own.
        for key in ('levels', 'materials', 'constructions'):
            data[key] = copy.deepcopy(data[key])
        return data

    def save_now(self, wait=False):
        """Write the recovery file if there is unsaved work; returns True if a write started."""
        if not self.enabled:
            return False
        if self._thread is not None and self._thread.is_alive():
            if not wait:
                return False             # the next tick or command catches up
            self._thread.join()
        data = self._snapshot()
        self._changes = 0
        if data == self.window._clean_state:
            self.discard()               # nothing unsaved (e.g. undone back to the saved state)
            return False
        if data == self._last_written:
            return False
        if self.path is None:
            self.path = persistence.new_recovery_path()
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._lock = QLockFile(self.path + '.lock')
            self._lock.setStaleLockTime(0)
            self._lock.tryLock(0)
        self._last_written = data
        project_path = self.window.current_path
        saved_at = time.time()
        self._thread = threading.Thread(
            target=self._write, args=(self.path, data, project_path, saved_at),
            name='archforge-autosave', daemon=True)
        self._thread.start()
        self.last_saved_at = saved_at
        self.window.statusBar().showMessage(
            'Αυτόματη αποθήκευση ανάκτησης ' + time.strftime('%H:%M', time.localtime(saved_at)), 2500)
        if wait:
            self._thread.join()
        return True

    def _write(self, path, data, project_path, saved_at):
        try:
            persistence.write_recovery(path, data, project_path, saved_at)
        except Exception:
            self._last_written = None    # retry on the next tick; the user's file is not involved

    def wait(self):
        if self._thread is not None:
            self._thread.join()

    def discard(self):
        """The work is saved (or deliberately dropped): remove this session's recovery file."""
        self.wait()
        self._changes = 0
        self._last_written = None
        if self.path is not None and os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except OSError:
                pass

    def shutdown(self):
        """Normal close: no recovery file and no lock left behind."""
        self.timer.stop()
        self.discard()
        if self._lock is not None:
            self._lock.unlock()
            self._lock = None
        self.enabled = False

    # ------------------------------------------------------------ recovery
    def pending_recoveries(self):
        """Recovery files of sessions that are not running any more, newest first.

        Each returned item holds its lock (so a second window does not offer
        it too) until ``release`` or ``drop``.
        """
        found = []
        for info in persistence.list_recoveries(exclude=(self.path,)):
            lock = QLockFile(info.path + '.lock')
            lock.setStaleLockTime(0)
            if not lock.tryLock(0):
                continue                 # another ArchForge window is still using it
            if not info.is_newer_than_project():
                # Saved later than the crash: the project file already has it.
                lock.unlock()
                persistence.remove_recovery(info.path)
                continue
            info.lock = lock
            found.append(info)
        return found

    @staticmethod
    def release(info):
        lock = getattr(info, 'lock', None)
        if lock is not None:
            lock.unlock()
            info.lock = None

    @classmethod
    def drop(cls, info):
        cls.release(info)
        persistence.remove_recovery(info.path)
