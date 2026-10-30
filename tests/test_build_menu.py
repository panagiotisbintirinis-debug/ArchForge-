"""Owner (2026-10-14): «συμπύκνωσε σε υπομενού πρώτα τις κατασκευές»; since 30/10 (owner «ναι στο 4») «Κατασκευή» is
the work menu of mockup v4: shell, openings, railings, slabs, stairs, roof, structure — short, by kind of element."""
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


def _leaves(menu, seen=None):
    seen = set() if seen is None else seen
    out = []
    for a in menu.actions():
        if a.isSeparator():
            continue
        if a.menu() is not None:
            if id(a.menu()) not in seen:
                seen.add(id(a.menu())); out += _leaves(a.menu(), seen)
        else:
            out.append(a)
    return out


def _build(window):
    return next(a.menu() for a in window.menuBar().actions() if a.text().replace('&', '') == 'Κατασκευή')


def test_build_menu_is_short_submenus_by_kind_with_icons(window):
    top = [a for a in _build(window).actions() if not a.isSeparator()]
    titles = [a.text().replace('&&', '&') for a in top]
    assert titles == ['Κέλυφος', 'Ανοίγματα', 'Κάγκελα', 'Πλάκες', 'Σκάλα·Ράμπα', 'Στέγη', 'Φέρων οργανισμός']
    assert all(a.menu() is not None and not a.icon().isNull() for a in top)
    # Storeys, phases, quantities and kitchens have their own work menus now (Έργο, Σχέδια, Διαμόρφωση).
    assert not {'Όροφοι', 'Επιμετρήσεις & τιμές', 'Ανακαίνιση (φάσεις)', 'Ντουλάπια / κουζίνα'} & set(titles)


def test_nothing_was_lost_from_the_build_menu(window):
    """Every command that was in «Κατασκευή» before the regroupings is still reachable from the menu bar."""
    leaves = {a.text().replace('&&', '&') for t in window.menuBar().actions() if t.menu() for a in _leaves(t.menu())}
    for text in ('Υπόγειο', 'Επιμέτρηση εργασιών (ανά χώρο)…', 'Τεμάχια Isotex (αναγωγή)…', 'Λίστα υλικών με τιμές (Excel)…',
                 'Εξαγωγή PDF (κατόψεις, επιμέτρηση, προσφορά)…', 'Οπή πλάκας / αίθριο (σχεδίαση)', 'Μπαλκόνι (σχεδίαση)',
                 'Τεμάχια ICF (αναγωγή)…', 'Γυψοσανίδες — υλικά (αναγωγή)…', 'Σε χώρο (κλικ στον χώρο)', 'Δημιουργία εδάφους',
                 'Επιλεγμένα → Καθαίρεση', 'Δίρριχτη', 'Ξύλινη', 'Κάγκελο σκάλας (κλικ σε σκάλα)', 'Πόρτα', 'Σκάλα',
                 'Κολώνα', 'Οπλισμός πλακών…', 'Ηλεκτρολογικός πίνακας', 'Φυτό: Δέντρο'):
        assert text in leaves, text


def test_a_submenu_entry_still_runs_its_tool(window):
    door = next(a for a in _leaves(_build(window)) if a.text() == 'Πόρτα')
    door.trigger()
    assert window.plan_view.controller.tool == 'door'
