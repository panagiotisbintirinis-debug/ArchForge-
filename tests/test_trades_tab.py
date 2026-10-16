"""A card per trade: quantities from the drawing, the professional's prices, order list, quote per trade."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest


def test_cards_per_trade_prices_order_list_and_quote(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.ui.main_window import MainWindow
    from archforge.ui import trades_tab
    from archforge.quantities.quote import quote, trade_prices
    from tests.test_electrical import _house
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        window.plan_view.sitePointRequested.emit('elec_panel', 0.5, 0.5)
        window.plan_view.sitePointRequested.emit('elec_socket', 2.0, 0.5)
        tab = trades_tab.show(window, 'Ηλεκτρολογικά')
        tabs = window._central_tabs
        assert tabs.currentWidget() is tab and tabs.tabText(tabs.indexOf(tab)) == 'Υλικά & τιμές'
        names = [tab.cards.tabText(i) for i in range(tab.cards.count())]
        assert names[0] == 'Σύνολο έργου'
        assert 'Ηλεκτρολογικά' in names and 'Επιμέτρηση' in names                 # each trade its own card
        assert tab.cards.tabText(tab.cards.currentIndex()) == 'Ηλεκτρολογικά'
        assert window.view is window.plan_view                                    # drawing tools stay with the plan
        # The electrician types material and labour on the socket line: one undoable change each.
        table = tab.tables['Ηλεκτρολογικά']
        row = next(i for i in range(table.rowCount()) if table.item(i, 0).data(0x0100) == 'electrical.point.socket')
        table.item(row, 3).setText('4,5'); table.item(row, 4).setText('15')
        app.processEvents()
        assert trade_prices(window.doc)['electrical.point.socket'] == {'material': 4.5, 'labour': 15.0}
        q = quote(window.doc, only=('Ηλεκτρολογικά',))
        assert q['subtotal'] == 19.5 and q['material'] == 4.5 and q['labour'] == 15.0
        window._undo()
        assert trade_prices(window.doc)['electrical.point.socket'] == {'material': 4.5, 'labour': None}
        # Order list: materials and quantities only, for the supplier.
        path = tab.export_order(str(tmp_path / 'order.csv'), 'Ηλεκτρολογικά')
        text = open(path, encoding='utf-8-sig').read()
        assert text.startswith('Λίστα παραγγελίας — Ηλεκτρολογικά') and 'electrical.point.socket' in text and '€' not in text
        # The tiler's quote has no electrical lines; ticking both cards (same client) combines them.
        tab.cards.setCurrentIndex(names.index('Επιμέτρηση'))
        assert tab.selected_trades() == ['Επιμέτρηση']
        tab.checks['Επιμέτρηση'].setChecked(True); tab.checks['Ηλεκτρολογικά'].setChecked(True)
        assert set(tab.selected_trades()) == {'Επιμέτρηση', 'Ηλεκτρολογικά'}
        out = tab.export_offer(str(tmp_path / 'offer.pdf'))
        assert out['pages'] >= 1 and (tmp_path / 'offer.pdf').exists()
    finally:
        window._mark_clean(); window.close(); app.processEvents()


def test_project_total_is_the_construction_cost_of_every_trade(tmp_path):
    from PySide6.QtWidgets import QApplication
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.ui.main_window import MainWindow
    from archforge.ui import trades_tab
    from tests.test_electrical import _house
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        _house(window.stack)
        window.plan_view.sitePointRequested.emit('elec_panel', 0.5, 0.5)
        window.plan_view.sitePointRequested.emit('elec_socket', 2.0, 0.5)
        window.stack.execute(AddEntity(Entity('price_list', {'trade_prices': {
            'electrical.point.socket': {'material': 5.0, 'labour': 15.0}, 'desc:Βαφή τοίχων': {'material': 2.0, 'labour': 4.0}}})))
        tab = trades_tab.show(window, 'Σύνολο έργου')
        assert set(tab.selected_trades()) == set(tab.tables)                     # the total card = every trade
        t = tab.summary_table
        last = t.rowCount() - 1
        assert t.item(last, 0).text().startswith('Σύνολο')
        from archforge.quantities.quote import money, quote
        assert t.item(last, 3).text() == money(quote(window.doc)['subtotal'])
        paint = next(r for _t, sec in quote(window.doc, only=('Επιμέτρηση',))['sections'] for r in sec
                     if r['description'] == 'Βαφή τοίχων')
        assert quote(window.doc)['subtotal'] == pytest.approx(20.0 + paint['amount'])
        path = tab.export_order(str(tmp_path / 'all.csv'))
        text = open(path, encoding='utf-8-sig').read()
        assert 'Λίστα παραγγελίας — Ηλεκτρολογικά' in text and 'Λίστα παραγγελίας — Επιμέτρηση' in text
        assert any('τούβλων' in n for n in trades_tab.NOT_MEASURED)        # bricks counted only with the data sheet
    finally:
        window._mark_clean(); window.close(); app.processEvents()
