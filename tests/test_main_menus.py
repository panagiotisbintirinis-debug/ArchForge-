"""The menu bar after the regrouping: since 30/10 (owner «ναι στο 4») the work menus of mockup v4 — Έργο ·
Επεξεργασία · Κατασκευή · Εγκαταστάσεις · Διαμόρφωση · Σχέδια · Προβολή · ⚙ Ρυθμίσεις (``main_menus.organize_work_menus``
over the 8 menus of 14/10).  No empty or repeated menus; the installers' menu references still reach their commands."""
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


def _section(window, top, title):
    return next(a.menu() for a in _top(window)[top].actions() if a.menu() is not None and a.text().replace('&&', '&') == title)


def _titles(menu):
    return [a.text().replace('&&', '&') for a in menu.actions() if not a.isSeparator()]


def test_menu_bar_is_the_work_menus_not_the_old_eight(window):
    from archforge.ui.main_menus import MAIN_MENUS, WORK_MENUS
    titles = [a.text() for a in window.menuBar().actions()]
    assert titles == list(WORK_MENUS)
    assert not {'Αρχείο', 'CAD', 'Βιβλιοθήκη', 'Εργαλεία', 'Βοήθεια'} & set(titles) and len(MAIN_MENUS) == 8

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


def test_terrain_structure_and_mep_have_their_work_menus(window):
    assert {'Φέρων οργανισμός', 'Στέγη', 'Ανοίγματα'} <= set(_titles(_top(window)['Κατασκευή']))
    assert {'Ύδρευση', 'Ηλεκτρολογικά', 'Θέρμανση'} <= set(_titles(_top(window)['Εγκαταστάσεις']))
    assert 'Έδαφος' in _titles(_top(window)['Διαμόρφωση'])
    # The commands of the old Έδαφος / Δομικά menus are all in the bar (they were split between work menus).
    every = {a.text() for m in _top(window).values() for a in _leaves(m)}
    assert {'Δημιουργία εδάφους', 'Πισίνα', 'Κολώνα', 'Οπλισμός πλακών…', 'Φύλλο ξυλοτύπου (PDF)…'} <= every
    for removed in ('Έδαφος', 'Δομικά', 'Μηχανολογικά', 'Κουζίνα', 'Υλικά', 'Γλυπτική', 'Βοηθός AI', 'Απεικόνιση', 'Σχεδίαση'):
        assert removed not in _top(window)

def test_each_3d_switch_appears_once_under_view(window):
    from archforge.ui.main_menus import LAYER_TEXTS
    every = [a.text() for m in _top(window).values() for a in _leaves(m)]
    for text in LAYER_TEXTS:
        assert every.count(text) == 1, text
    assert set(LAYER_TEXTS) <= set(_titles(window._view_show3d_menu))


def test_section_and_interior_view_are_drawings(window):
    assert 'Τομή (σύρε γραμμή στην κάτοψη)' in _titles(_section(window, 'Σχέδια', 'Τομές'))
    assert 'Εσωτερική όψη (σύρε γραμμή στην κάτοψη)' in _titles(_section(window, 'Σχέδια', 'Όψεις'))
    assert 'Τομή (σύρε γραμμή στην κάτοψη)' not in [a.text() for a in _leaves(_top(window)['Προβολή'])]

def test_files_import_in_project_export_in_drawings(window):
    files = _titles(_section(window, 'Έργο', 'Αρχείο'))
    assert {'Νέο έργο', 'Αποθήκευση'} <= set(files) and 'Τιμές & προσφορά…' not in files
    exports = _titles(_section(window, 'Σχέδια', 'Εξαγωγή'))
    assert exports.count('STL (για εκτύπωση)…') == 1
    assert any(t.startswith('Εξαγωγή PDF') for t in _titles(_section(window, 'Σχέδια', 'Εκτύπωση·PDF')))
    assert any(t.startswith('Εισαγωγή μοντέλου glTF') for t in _titles(_section(window, 'Έργο', 'Εισαγωγή')))
    assert not any(t.startswith('Εισαγωγή μοντέλου glTF') for t in _titles(_section(window, 'Διαμόρφωση', 'Βιβλιοθήκη')))

def test_kitchen_and_materials_in_layout(window):
    assert {'Κουζίνα·ντουλάπια', 'Υλικά', 'Βιβλιοθήκη'} <= set(_titles(_top(window)['Διαμόρφωση']))
    kitchen = _section(window, 'Διαμόρφωση', 'Κουζίνα·ντουλάπια')
    texts = [a.text() for a in _leaves(kitchen)]
    if not texts:
        for a in kitchen.actions():
            if a.menu() is not None:
                a.menu().aboutToShow.emit()                  # the kitchen catalogue fills on open
        texts = [a.text() for a in _leaves(kitchen)]
    assert 'Σχεδίασε κουζίνα (ελεύθερα)…' in texts and not any(t.startswith('Κουζίνα εδώ') for t in texts)
    assert 'Μπάνιο εδώ (Βοηθός)…' in texts

def test_moved_entries_still_run(window):
    column = next(a for a in _leaves(_top(window)['Κατασκευή']) if a.text() == 'Κολώνα')
    column.trigger()
    assert window.plan_view.controller.tool == 'structural_column'
    grid = next(a for a in window._quick_actions if a.text() == 'Κάνναβος')       # a button of the first row (v4)
    grid.trigger()
    assert not window._mockup_grid_check.isChecked()
    assert window.sculpt_action in _leaves(_top(window)['Διαμόρφωση'])

