import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from archforge.ui.main_window import MainWindow


def test_new_project_replaces_authoritative_document_stack_and_rebinds_views():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    old_doc = window.doc
    old_stack = window.stack
    window.current_path = "/tmp/existing.archforge"
    old_doc.selection = ["stale-selection"]

    window.new_project()

    assert window.doc is not old_doc
    assert window.stack is not old_stack
    assert window.current_path is None
    assert window.doc.selection == []
    assert window.plan_view.doc is window.doc
    assert window.front_view.doc is window.doc
    assert window.pbr_view.doc is window.doc
    assert window.plan_view.stack is window.stack
    assert window.front_view.stack is window.stack
    assert window.pbr_view.stack is window.stack
    window.close()
