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
        assert SP.is_shown(w) and page.parent() is w                # over the window, not a tab of the drawing
        assert all(w._central_tabs.widget(i) is not page for i in range(w._central_tabs.count()))
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
        assert not SP.is_shown(w)                                   # it steps aside for the project
        w._start_action.trigger()
        assert SP.is_shown(w)
        page.close_button.click()                                   # ✕ = back to the drawing
        assert not SP.is_shown(w)
    finally:
        w._mark_clean(); w.close(); app.processEvents()


def test_start_page_is_its_own_environment_not_a_tab(data):
    """Owner 23/10: «παλιό αρχείο, κάνω επιλογή και με πετάει στην Αρχική» · «η Αρχική άλλο περιβάλλον, όχι στο
    σχεδιαστικό» — it covers the window under the menu bar; the plan stays tab 0; opening a project from the File
    menu takes it away, and a plan tool never brings it back."""
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui import start_page as SP
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w.resize(1200, 800); w.show(); app.processEvents()
    try:
        tabs = w._central_tabs
        plan_tab = tabs.widget(0)
        page = SP.show_start(w); app.processEvents()
        assert tabs.widget(0) is plan_tab and SP.is_shown(w)
        assert page.geometry().top() >= w.menuBar().geometry().bottom()           # the menus stay usable
        assert page.geometry().bottom() >= w.rect().bottom() - 1                  # the drawing is hidden under it
        path = str(data / "old.archforge")
        w.current_path = path
        assert w.save()
        w._no_modal_dialogs = True
        assert w.open(path) is not False                           # Αρχείο ▸ Άνοιγμα, not the page's link
        assert not SP.is_shown(w) and tabs.currentWidget() is plan_tab
        w._start_view_line_tool('section')                         # a plan tool: the plan, never the start page
        assert tabs.currentWidget() is plan_tab and not SP.is_shown(w)
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
