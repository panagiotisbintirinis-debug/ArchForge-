"""Owner (14/10): the 8 menus of `docs/mockups/menou_2026-10-14.png` — Έδαφος / Δομικά / Η/Μ as submenus of
«Κατασκευή», the 2D drawing menu called «CAD», Τομή / Εσωτερική όψη in «Προβολή», no empty or repeated menus."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    app = QApplication.instance() or QApplication([])
    w = MainWindow()
    yield w
    w._mark_clean(); w.close(); app.processEvents()


def _top(window):
    return {a.text(): a.menu() for a in window.menuBar().actions()}


def _leaves(menu):
    out = []
    for a in menu.actions():
        if a.isSeparator():
            continue
        out.extend(_leaves(a.menu()) if a.menu() is not None else [a])
    return out


def _titles(menu):
    return [a.text().replace('&&', '&') for a in menu.actions() if not a.isSeparator()]


def test_menu_bar_is_the_eight_menus_in_order(window):
    from archforge.ui.main_menus import MAIN_MENUS
    assert [a.text() for a in window.menuBar().actions()] == list(MAIN_MENUS)
    assert len(MAIN_MENUS) == 8 and 'CAD' in MAIN_MENUS


def test_no_menu_or_submenu_is_empty(window):
    def walk(menu, path):
        assert menu.actions(), path
        for a in menu.actions():
            if a.menu() is not None:
                if not a.menu().actions():
                    a.menu().aboutToShow.emit()          # filled on first open (kitchen catalogue)
                walk(a.menu(), path + [a.text()])
    for title, menu in _top(window).items():
        walk(menu, [title])


def test_terrain_structure_and_mep_live_in_build(window):
    build = _top(window)['Κατασκευή']
    titles = _titles(build)
    for sub in ('Δομικά', 'Η/Μ εγκαταστάσεις', 'Έδαφος & περιβάλλον'):
        assert sub in titles, titles
    assert titles.index('Όροφοι') < titles.index('Δομικά') < titles.index('Ανακαίνιση (φάσεις)')
    # Same QMenu objects as before, so the installers' references still work.
    assert window._mockup_terrain_menu.menuAction() in build.actions()
    assert window._structure_menu.menuAction() in build.actions()
    for removed in ('Έδαφος', 'Δομικά', 'Μηχανολογικά', 'Κουζίνα', 'Υλικά', 'Γλυπτική', 'Βοηθός AI', 'Απεικόνιση', 'Σχεδίαση'):
        assert removed not in _top(window)


def test_each_3d_switch_appears_once_under_view(window):
    from archforge.ui.main_menus import LAYER_TEXTS
    every = [a.text() for m in _top(window).values() for a in _leaves(m)]
    for text in LAYER_TEXTS:
        assert every.count(text) == 1, text
    assert set(LAYER_TEXTS) <= set(_titles(window._view_show3d_menu))


def test_section_and_interior_view_are_in_view_menu(window):
    view = _titles(_top(window)['Προβολή'])
    assert view[:3] == ['Όψεις', 'Τομή (σύρε γραμμή στην κάτοψη)', 'Εσωτερική όψη (σύρε γραμμή στην κάτοψη)']
    assert 'Τομή (σύρε γραμμή στην κάτοψη)' not in [a.text() for a in _leaves(_top(window)['CAD'])]


def test_file_menu_groups_import_and_export(window):
    file_titles = _titles(_top(window)['Αρχείο'])
    assert {'Εισαγωγή', 'Εξαγωγή'} <= set(file_titles)
    assert 'Τιμές & προσφορά…' not in file_titles
    exports = _titles(window._file_export_menu)
    assert exports.count('STL (για εκτύπωση)…') == 1 and any(t.startswith('Εξαγωγή PDF') for t in exports)
    assert any(t.startswith('Εισαγωγή μοντέλου glTF') for t in _titles(window._file_import_menu))
    assert not any(t.startswith('Εισαγωγή μοντέλου glTF') for t in _titles(_top(window)['Βιβλιοθήκη']))


def test_kitchen_and_materials_under_library(window):
    library = _top(window)['Βιβλιοθήκη']
    assert {'Κουζίνα & μπάνιο', 'Υλικά'} <= set(_titles(library))
    kitchen = next(a.menu() for a in library.actions() if a.text().replace('&&', '&') == 'Κουζίνα & μπάνιο')
    assert _titles(kitchen)[0] == 'Σχεδίασε κουζίνα (ελεύθερα)…' and not any(t.startswith('Κουζίνα εδώ') for t in _titles(kitchen))
    assert 'Μπάνιο εδώ (Βοηθός)…' in _titles(kitchen)


def test_moved_entries_still_run(window):
    build = _top(window)['Κατασκευή']
    column = next(a for a in _leaves(build) if a.text() == 'Κολώνα')
    column.trigger()
    assert window.plan_view.controller.tool == 'structural_column'
    grid = next(a for a in _leaves(_top(window)['CAD']) if a.text() == 'Κάνναβος')
    grid.trigger()
    assert not window._mockup_grid_check.isChecked()
    tools = _top(window)['Εργαλεία']
    assert window.sculpt_action in tools.actions()
