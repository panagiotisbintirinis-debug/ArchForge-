"""Owner (2026-10-14): «συμπύκνωσε σε υπομενού πρώτα τις κατασκευές» (Home Designer's Build menu as reference)."""
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
    assert len(top) <= 16
    for expected in ('Κουφώματα', 'Κάγκελα & μπαλκόνια', 'Πέργκολα', 'Δάπεδα & πλάκες', 'Στέγη', 'Σκάλα / Ράμπα',
                     'Ντουλάπια / κουζίνα', 'Όροφοι', 'Επιμετρήσεις & τιμές', 'Ανακαίνιση (φάσεις)'):
        assert expected in titles, (expected, titles)
    assert titles.index('Κουφώματα') < titles.index('Στέγη') < titles.index('Επιμετρήσεις & τιμές')
    assert all(not a.icon().isNull() for a in top if a.menu() is not None)


def test_nothing_was_lost_from_the_build_menu(window):
    """Every command that was in «Κατασκευή» before the regrouping is still reachable from it."""
    leaves = {a.text().replace('&&', '&') for a in _leaves(_build(window))}
    for text in ('Υπόγειο', 'Επιμέτρηση εργασιών (ανά χώρο)…', 'Τεμάχια Isotex (αναγωγή)…', 'Λίστα υλικών με τιμές (Excel)…',
                 'Εξαγωγή PDF (κατόψεις, επιμέτρηση, προσφορά)…', 'Οπή πλάκας / αίθριο (σχεδίαση)', 'Μπαλκόνι (σχεδίαση)',
                 'Τεμάχια ICF (αναγωγή)…', 'Γυψοσανίδες — υλικά (αναγωγή)…', 'Σε χώρο (κλικ στον χώρο)', 'Έδαφος (οικόπεδο)',
                 'Επιλεγμένα → Καθαίρεση', 'Δίρριχτη', 'Ξύλινη', 'Κάγκελο σκάλας (κλικ σε σκάλα)', 'Πόρτα', 'Σκάλα',
                 'Κολώνα', 'Σκελετός στέγης στο 3D'):
        assert text in leaves, text


def test_a_submenu_entry_still_runs_its_tool(window):
    door = next(a for a in _leaves(_build(window)) if a.text() == 'Πόρτα')
    door.trigger()
    assert window.plan_view.controller.tool == 'door'
