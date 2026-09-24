import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from archforge.core.commands import SetLevel
from archforge.ui.main_window import MainWindow


_APP = QApplication.instance() or QApplication([])


class _CloseEventProbe:
    """Minimal close-event contract used by MainWindow.closeEvent."""

    def __init__(self):
        self._accepted = True

    def accept(self):
        self._accepted = True

    def ignore(self):
        self._accepted = False

    def isAccepted(self):
        return self._accepted


def _window():
    return MainWindow()


def _dirty(window):
    window.stack.execute(SetLevel("Mezzanine", 2.5))


def test_close_cancel_ignores_event_and_preserves_dirty_project(monkeypatch):
    window = _window()
    original_doc = window.doc
    state = window.doc.to_dict()
    _dirty(window)
    dirty_state = window.doc.to_dict()
    assert dirty_state != state

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    event = _CloseEventProbe()
    window.closeEvent(event)

    assert not event.isAccepted()
    assert window.doc is original_doc
    assert window.doc.to_dict() == dirty_state


def test_close_discard_accepts_without_replacing_or_mutating_document(monkeypatch):
    window = _window()
    original_doc = window.doc
    _dirty(window)
    dirty_state = window.doc.to_dict()

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    event = _CloseEventProbe()
    window.closeEvent(event)

    assert event.isAccepted()
    assert window.doc is original_doc
    assert window.doc.to_dict() == dirty_state


def test_close_save_accepts_only_after_successful_save(monkeypatch):
    window = _window()
    _dirty(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )

    monkeypatch.setattr(window, "save", lambda: False)
    failed_event = _CloseEventProbe()
    window.closeEvent(failed_event)
    assert not failed_event.isAccepted()

    monkeypatch.setattr(window, "save", lambda: True)
    saved_event = _CloseEventProbe()
    window.closeEvent(saved_event)
    assert saved_event.isAccepted()


def test_clean_project_close_does_not_prompt(monkeypatch):
    window = _window()

    def unexpected_prompt(*args, **kwargs):
        raise AssertionError("clean project must close without prompting")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_prompt)
    event = _CloseEventProbe()
    window.closeEvent(event)

    assert event.isAccepted()
