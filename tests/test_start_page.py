"""Owner 23/10: a start page like Home Designer's dashboard, the ArchForge mark behind it; recent projects; a new
project asks its details (title, client, place, plot, engineer, ±0,00 altitude) with the brief."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("ARCHFORGE_DATA", str(tmp_path / "data"))
    return tmp_path


def test_recent_projects_newest_first_only_existing(data):
    from archforge.ui import start_page as SP
    a, b = data / "a.archforge", data / "b.archforge"
    a.write_text("{}"); b.write_text("{}")
    SP.remember(str(a)); SP.remember(str(b)); SP.remember(str(a)); SP.remember(str(data / "x.bak"))
    assert SP.recent() == [str(a), str(b)]
    b.unlink()
    assert SP.recent() == [str(a)]


def test_start_page_tab_actions_and_menu(data):
    from PySide6.QtWidgets import QApplication, QPushButton
    from archforge.ui.main_window import MainWindow
    from archforge.ui import start_page as SP
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        page = SP.show_start(w)
        assert w._central_tabs.currentWidget() is page and w._central_tabs.tabText(0) == "Αρχική"
        texts = {b.text() for b in page.findChildren(QPushButton)}
        assert {"Νέο έργο", "Άνοιγμα έργου…", "Άνοιγμα δείγματος…", "Από τα σχέδια του μηχανικού (PDF)…"} <= texts
        assert not SP.mark_path(100).isEmpty()
        path = str(data / "villa.archforge")
        w.current_path = path
        assert w.save()
        assert SP.recent()[0] == path
        page.refresh()
        assert "villa.archforge" in {b.text() for b in page.findChildren(QPushButton)}
        w._no_modal_dialogs = True
        page._go(w.new_project)
        assert w._central_tabs.indexOf(page) < 0                     # it steps aside for the project
        w._start_action.trigger()
        assert w._central_tabs.currentWidget() is page
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_project_details_with_the_brief(data):
    from PySide6.QtWidgets import QApplication
    from archforge.project.brief import details_text, get_brief
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    try:
        w._apply_project_brief({"project_type": "new", "title": "Βίλα Παρασκευά", "client": "Μάρομ", "address": "Αίγινα",
                                "altitude": 114.0})
        b = get_brief(w.doc)
        assert b["title"] == "Βίλα Παρασκευά" and b["altitude"] == 114.0
        assert details_text(w.doc) == "Βίλα Παρασκευά · Μάρομ · Αίγινα"
        w._update_window_title()
        assert "Βίλα Παρασκευά" in w.windowTitle()
        w.stack.undo()
        assert get_brief(w.doc) is None
    finally:
        w._mark_clean(); w.close(); app.processEvents()
