"""Owner 30/10: Επιμέτρηση with everything, by choice — stairs, joinery, MEP, kitchen …, tiles per finish, a margin."""
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from archforge.core.model import Document

PROJECT = os.path.join(os.path.dirname(__file__), 'data', 'owner_111_two_storey.archforge')


def _doc():
    return Document.from_dict(json.load(open(PROJECT, encoding='utf-8')))


def test_every_measured_list_can_be_shown_with_prices_and_the_stairs_are_there():
    from archforge.ui.takeoff_view import ROOMS, html, section_names
    doc = _doc()
    names = section_names(doc)
    assert names[0] == ROOMS and {'Σκάλες', 'Κουφώματα', 'Ηλεκτρολογικά', 'Κουζίνα'} <= set(names)
    page = html(doc, names)
    assert 'Σκάλα 2: σκαλοπάτια' in page and 'Ντουλάπια κουζίνας' in page and 'Ανά χώρο' in page
    only_stairs = html(doc, ['Σκάλες'])
    assert 'σκαλοπάτια' in only_stairs and 'Ανά χώρο' not in only_stairs and 'Κουζίνα' not in only_stairs


def test_a_different_floor_tile_is_its_own_line():
    from archforge.assistant.understanding import read_drawing
    from archforge.core.commands import CommandStack, SetRoomMetadata
    from archforge.quantities.materials import takeoff_list
    doc = _doc(); stack = CommandStack(doc)
    room = read_drawing(doc)['storeys'][0]['rooms'][0]
    stack.execute(SetRoomMetadata(room['signature'], {'floor_finish': 'Πορσελάνη 60×60'}))
    rows = {d: q for d, _u, q in takeoff_list(doc)}
    assert 'Πλακάκια δαπέδου — Πορσελάνη 60×60' in rows and 'Πλακάκια δαπέδου' in rows      # two lines, two prices
    stack.undo()
    assert not any('—' in d for d in (d for d, _u, _q in takeoff_list(doc)) if d.startswith('Πλακάκια δαπέδου'))


def test_the_margin_goes_on_the_priced_items_before_vat_with_one_undo():
    from archforge.core.commands import CommandStack
    from archforge.quantities.price_book import save
    from archforge.quantities.quote import quote
    from archforge.ui.takeoff_view import set_margin_command
    doc = _doc(); stack = CommandStack(doc)
    save({'desc:Βαφή τοίχων': {'material': 2.0, 'labour': 3.0}})
    base = quote(doc)
    stack.execute(set_margin_command(doc, 10))
    q = quote(doc)
    assert q['margin_amount'] == pytest.approx(round(base['subtotal'] * 0.10, 2))
    assert q['total'] == pytest.approx(round(q['subtotal'] + q['margin_amount'] + q['vat_amount'], 2))
    assert q['vat_amount'] == pytest.approx(round((q['subtotal'] + q['margin_amount']) * q['vat'] / 100, 2))
    stack.undo()
    assert quote(doc)['margin_amount'] == 0.0


def test_the_window_ticks_and_unticks_lists_and_remembers_them():
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui.takeoff_view import show
    app = QApplication.instance() or QApplication([])
    w = MainWindow(); w._no_modal_dialogs = True
    try:
        dlg = show(w)
        dlg.none_button.click()
        assert dlg.chosen() == [] and 'Διάλεξε' in dlg.browser.toPlainText() and w._takeoff_sections == set()
        dlg.all_button.click()
        assert len(dlg.chosen()) == dlg.sections.count() and w._takeoff_sections == set(dlg.chosen())
        dlg.margin.setValue(12.5); dlg.margin.editingFinished.emit()
        from archforge.quantities.quote import settings
        assert settings(w.doc)['margin'] == 12.5
    finally:
        w._mark_clean(); w.close(); app.processEvents()
