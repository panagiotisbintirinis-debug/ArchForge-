"""Common price book (owner 17/10): saved once, prices every project; the project's own price wins."""
import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from archforge.core.commands import AddEntity, CommandStack
from archforge.core.model import Document, Entity
from archforge.quantities import price_book
from archforge.quantities.quote import costed, price_source


def _project(prices):
    doc = Document(); st = CommandStack(doc)
    st.execute(AddEntity(Entity('price_list', {'trade_prices': prices}, name='Τιμές')))
    return doc


def test_saved_prices_reach_every_project_and_project_prices_win():
    assert price_book.load() == {}                                       # starts empty: nothing invented
    a = _project({'x.code': {'material': 10.0, 'labour': 4.0}})
    assert price_book.save_project_prices(a) == 1
    other = Document()
    row = costed(other, 't', [('Είδος', 'τεμ.', 3.0, {'code': 'x.code'})])[0]
    assert row['amount'] == 42.0 and row['material'] == 30.0 and row['labour'] == 12.0
    assert row['price_source'] == 'κοινός τιμοκατάλογος' and price_source(other, 'x.code') == 'κοινός τιμοκατάλογος'
    own = _project({'x.code': {'material': 1.0, 'labour': 1.0}})
    assert costed(own, 't', [('Είδος', 'τεμ.', 3.0, {'code': 'x.code'})])[0]['amount'] == 6.0
    assert price_source(own, 'x.code') == 'έργο'
    missing = costed(other, 't', [('Άλλο', 'τεμ.', 1.0, {'code': 'never'})])[0]
    assert missing['amount'] is None and missing['price_source'] is None


def test_unreadable_book_is_empty_not_guessed(tmp_path):
    price_book.path().write_text('{not json', encoding='utf-8')
    assert price_book.load() == {}


def test_one_price_book_for_every_trade_whatever_the_format():
    """The tab writes trade_prices, the trade modules wrote entries: both read the same book (and the common one)."""
    from archforge.mep.project_pricebook import effective_prices, project_prices
    from archforge.quantities.quote import trade_prices
    doc = _project({'tab.code': {'material': 2.0, 'labour': 1.0}})
    pl = next(e for e in doc.entities.values() if e.kind == 'price_list')
    pl.params['entries'] = {'mod.code': {'material_unit_price': 5.0, 'labour_unit_price': None, 'currency': 'EUR'}}
    assert set(project_prices(doc)) == {'tab.code', 'mod.code'}
    assert trade_prices(doc)['mod.code'] == {'material': 5.0, 'labour': None}
    price_book.save({'common.code': {'material': 9.0, 'labour': 0.0}})
    eff = effective_prices(doc)
    assert eff['common.code'].source == 'price_book' and eff['tab.code'].material_unit_price == 2.0
