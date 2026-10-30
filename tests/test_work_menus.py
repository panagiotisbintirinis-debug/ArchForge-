"""Work menus of mockup v4 (owner 30/10 «ναι στο 4»): every command moved to its home, none lost, old paths resolve."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.ui.main_menus import WORK_MENUS, _target, resolve_path
from archforge.ui.menu_map import UNPLACED, home


@pytest.fixture
def window():
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from archforge.ui.main_window import MainWindow
    w = MainWindow()
    yield w
    w._mark_clean(); w.close()


def _leaves(menu, path=()):
    for a in menu.actions():
        if a.isSeparator() or not a.text():
            continue
        p = path + (a.text().replace('&&', '&'),)
        if a.menu() is not None:
            yield from _leaves(a.menu(), p)
        else:
            yield p, a


def _bar(w):
    return [(a.text(), a.menu()) for a in w.menuBar().actions() if a.menu() is not None]


def test_bar_is_the_work_menus_in_order(window):
    names = [t for t, _m in _bar(window)]
    assert names == [n for n in WORK_MENUS if n in names]
    assert names[:1] == ['Έργο'] and {'Κατασκευή', 'Εγκαταστάσεις', 'Διαμόρφωση', 'Σχέδια', 'Προβολή', '⚙ Ρυθμίσεις'} <= set(names)


def test_every_command_sits_where_the_map_says_once(window):
    from archforge.ui.toolbar_custom import SEP
    from archforge.ui.main_menus import old_menu_path
    seen, alive = {}, []
    for top, menu in _bar(window):
        for path, a in _leaves(menu, (top,)):
            alive.append(a)                                                     # ids stay unique while held
            assert id(a) not in seen, f'{path} also at {seen[id(a)]}'          # one home per command
            seen[id(a)] = path
            old = old_menu_path(a)
            if old is None:
                continue                                                        # added after the move (e.g. plumbing details)
            h = home(old)
            assert h != UNPLACED, old
            want_top, want_section = _target(h)
            assert path[0] == want_top, (old, path)
            if want_section:
                assert want_section.replace('&&', '&') in path, (old, path)
    assert len(seen) > 250
    assert all(SEP in k and SEP in v for k, v in window._menu_aliases.items())


def test_known_homes(window):
    found = {path[-1]: path for top, menu in _bar(window) for path, _a in _leaves(menu, (top,))}
    assert found['Πόρτα'][:2] == ('Κατασκευή', 'Ανοίγματα')
    assert found['IFC για μηχανικούς (BIM)…'][:2] == ('Σχέδια', 'Εξαγωγή')
    assert found['Αναίρεση'][0] == 'Επεξεργασία'
    assert found['Συντομεύσεις πληκτρολογίου…'][:2] == ('⚙ Ρυθμίσεις', 'Χειρισμός')


def test_old_paths_still_find_the_command(window):
    from archforge.ui.mouse_menus import _find_action
    from archforge.ui.toolbar_custom import catalog
    cat = catalog(window)
    assert window._menu_aliases
    checked = 0
    for old, new in window._menu_aliases.items():
        assert resolve_path(window, old) == new
        a = _find_action(window, new)
        if a is None:
            continue              # a name holding « / » itself cannot be found by path (old limitation of SEP)
        assert _find_action(window, old) is a, old
        if a.menu() is None and new in cat:
            assert cat[old] is cat[new]
        checked += 1
    assert checked > 100


def test_grid_snap_and_assistant_are_always_at_hand_in_the_first_row(window):
    """Mockup v4 step 3 (first part): Κάνναβος · Έλξη · Βοηθός are buttons of the first row, not menu entries."""
    from archforge.ui.mouse_menus import _find_action
    from archforge.ui.toolbar_custom import catalog
    quick = window._quick_actions
    assert {a.text() for a in quick} >= {'Κάνναβος', 'Βοηθός (πάνελ)'} and any(a.text().startswith('Έλξη') for a in quick)
    in_menus = [a for _top, m in _bar(window) for _p, a in _leaves(m)]
    assert not any(a in in_menus for a in quick)                                  # one home: the row
    shown = [b.defaultAction() for b in window._quick_buttons]
    assert all(a in shown for a in quick) and window.undo_action in shown
    grid = next(a for a in quick if a.text() == 'Κάνναβος')
    grid.trigger(); assert not window._mockup_grid_check.isChecked()               # same command as before
    cat = catalog(window)
    for old, a in window._quick_paths.items():                                     # saved paths still find it
        assert cat[old] is a and _find_action(window, old) is a
    assert 'Μονάδες μέτρησης…' in [a.text() for a in window._work_sections[('⚙ Ρυθμίσεις', 'Γενικά')].actions()]
