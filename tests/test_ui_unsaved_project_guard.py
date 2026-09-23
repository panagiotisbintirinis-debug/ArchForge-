import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from archforge.core.commands import Command
from archforge.ui.main_window import MainWindow


class SetUnits(Command):
    def __init__(self, units):
        self.units = units
        self.before = None

    def do(self, doc):
        if self.before is None:
            self.before = doc.units
        doc.units = self.units

    def undo(self, doc):
        doc.units = self.before


def _window():
    QApplication.instance() or QApplication([])
    return MainWindow()


def test_new_project_cancel_preserves_dirty_project(monkeypatch):
    window = _window()
    original_doc = window.doc
    original_stack = window.stack
    window.stack.execute(SetUnits("cm"))

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    window.new_project()

    assert window.doc is original_doc
    assert window.stack is original_stack
    assert window.doc.units == "cm"


def test_new_project_discard_replaces_dirty_project(monkeypatch):
    window = _window()
    original_doc = window.doc
    window.stack.execute(SetUnits("cm"))

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    window.new_project()

    assert window.doc is not original_doc
    assert window.current_path is None


def test_undo_back_to_clean_baseline_does_not_prompt(monkeypatch):
    window = _window()
    window.stack.execute(SetUnits("cm"))
    window.stack.undo()

    def unexpected_prompt(*args, **kwargs):
        raise AssertionError("clean baseline must not prompt")

    monkeypatch.setattr(QMessageBox, "warning", unexpected_prompt)
    window.new_project()

    assert window.current_path is None
