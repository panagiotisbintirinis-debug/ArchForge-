import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from archforge.core.commands import SetLevel
from archforge.ui.main_window import MainWindow


def _window():
    QApplication.instance() or QApplication([])
    return MainWindow()


def _make_authoritative_edit(window):
    # Levels are serialized authoritative Document state, so this exercises the
    # same state that save/load and the clean baseline compare.
    window.stack.execute(SetLevel("Mezzanine", 2.5))


def test_new_project_cancel_preserves_dirty_project(monkeypatch):
    window = _window()
    original_doc = window.doc
    original_stack = window.stack
    _make_authoritative_edit(window)

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert window.new_project() is False

    assert window.doc is original_doc
    assert window.stack is original_stack
    assert window.doc.levels["Mezzanine"] == 2.5


def test_new_project_discard_replaces_dirty_project(monkeypatch):
    window = _window()
    original_doc = window.doc
    _make_authoritative_edit(window)

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    assert window.new_project() is True

    assert window.doc is not original_doc
    assert window.current_path is None
    assert "Mezzanine" not in window.doc.levels


def test_undo_back_to_clean_baseline_does_not_prompt(monkeypatch):
    window = _window()
    _make_authoritative_edit(window)
    window.stack.undo()

    def unexpected_prompt(*args, **kwargs):
        raise AssertionError("clean baseline must not prompt")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_prompt)
    assert window.new_project() is True

    assert window.current_path is None
